from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.auth import hash_password


DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"
DEFAULT_USERS = [
    "admin@osmosense.local",
    "productor.vid@osmosense.local",
    "productor.olivo@osmosense.local",
    "regional@osmosense.local",
]
ALPHABET = string.ascii_letters + string.digits + "-_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rota contraseñas demo de OSMOSENSE antes de una demo cloud."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--user",
        action="append",
        default=None,
        help="Email de usuario a rotar. Puede repetirse. Si se omite rota usuarios demo.",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=None,
        metavar="EMAIL=PASSWORD",
        help="Define contraseña explícita para un usuario. Puede repetirse.",
    )
    parser.add_argument("--password-length", type=int, default=20)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Aplica cambios. Sin este flag solo muestra qué usuarios modificaría.",
    )
    parser.add_argument(
        "--hide-passwords",
        action="store_true",
        help="No imprime las contraseñas generadas/explícitas.",
    )
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    return cli_value or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def parse_explicit_passwords(values: list[str] | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError("--set debe tener formato EMAIL=PASSWORD.")
        email, password = value.split("=", 1)
        email = email.strip().lower()
        if not email or not password:
            raise ValueError("--set requiere email y password no vacíos.")
        if len(password) < 8:
            raise ValueError(f"La contraseña de {email} debe tener al menos 8 caracteres.")
        parsed[email] = password
    return parsed


def generate_password(length: int) -> str:
    if length < 12:
        raise ValueError("--password-length debe ser >= 12.")
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def target_users(args: argparse.Namespace, explicit: dict[str, str]) -> list[str]:
    users = [item.strip().lower() for item in (args.user or DEFAULT_USERS)]
    for email in explicit:
        if email not in users:
            users.append(email)
    return sorted(set(users))


def build_passwords(users: list[str], explicit: dict[str, str], length: int) -> dict[str, str]:
    return {
        email: explicit.get(email) or generate_password(length)
        for email in users
    }


def has_generated_passwords(users: list[str], explicit: dict[str, str]) -> bool:
    return any(email not in explicit for email in users)


def rotate_passwords(db_url: str, passwords: dict[str, str]) -> list[str]:
    import psycopg

    updated: list[str] = []
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for email, password in passwords.items():
                cur.execute(
                    """
                    UPDATE usuarios
                    SET password_hash = %s,
                        updated_at = now()
                    WHERE lower(email) = %s
                      AND activo = true
                    """,
                    [hash_password(password), email.lower()],
                )
                if cur.rowcount == 0:
                    raise RuntimeError(f"No se encontró usuario activo: {email}")
                updated.append(email)
        conn.commit()
    return updated


def print_plan(passwords: dict[str, str], show_passwords: bool) -> None:
    for email, password in passwords.items():
        if show_passwords:
            print(f"{email}: {password}")
        else:
            print(f"{email}: <oculta>")


def main() -> int:
    args = parse_args()
    explicit = parse_explicit_passwords(args.set)
    users = target_users(args, explicit)
    if args.confirm and args.hide_passwords and has_generated_passwords(users, explicit):
        print(
            "ERROR: --hide-passwords no puede usarse con contraseñas generadas automáticamente.",
            file=sys.stderr,
        )
        print("Usar --set EMAIL=PASSWORD para todos los usuarios o quitar --hide-passwords.", file=sys.stderr)
        return 2

    passwords = build_passwords(users, explicit, args.password_length)
    db_url = database_url(args.database_url)

    print("=== Rotación credenciales cloud OSMOSENSE ===")
    print("Database URL:", db_url)
    print("Usuarios objetivo:", len(users))

    if not args.confirm:
        print("Modo simulación. Agregar --confirm para aplicar cambios.")
        print_plan(passwords, show_passwords=not args.hide_passwords)
        return 0

    updated = rotate_passwords(db_url, passwords)
    print(f"Contraseñas rotadas: {len(updated)}")
    print_plan(passwords, show_passwords=not args.hide_passwords)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
