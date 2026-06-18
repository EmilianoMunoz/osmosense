from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.auth import hash_password


DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"


OPERATIVE_USERS = [
    {
        "email": "admin@osmosense.local",
        "nombre": "Administrador",
        "apellido": None,
        "dni": None,
        "rol": "admin",
        "cliente_id": None,
        "password": "admin123",
    },
    {
        "email": "productor.vid@osmosense.local",
        "nombre": "Martín",
        "apellido": "Videla",
        "dni": "30111222",
        "rol": "productor",
        "cliente_id": 1,
        "password": "cliente123",
    },
    {
        "email": "productor.olivo@osmosense.local",
        "nombre": "Laura",
        "apellido": "Olivera",
        "dni": "28777444",
        "rol": "productor",
        "cliente_id": 2,
        "password": "cliente123",
    },
    {
        "email": "regional@osmosense.local",
        "nombre": "Regional",
        "apellido": "DGI",
        "dni": None,
        "rol": "regional",
        "cliente_id": None,
        "password": "regional123",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recrea usuarios operativos para login contra PostGIS."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    return cli_value or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def main() -> int:
    args = parse_args()
    db_url = database_url(args.database_url)

    print("=== Carga usuarios operativos PostGIS ===")
    print("Database URL:", db_url)
    print("Dry run:", args.dry_run)

    if args.dry_run:
        for user in OPERATIVE_USERS:
            print(f"DRY usuario={user['email']} rol={user['rol']} cliente_id={user['cliente_id']}")
        return 0

    import psycopg

    query = """
        INSERT INTO usuarios (
            email,
            nombre,
            apellido,
            dni,
            rol,
            cliente_id,
            password_hash,
            activo,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, true, now())
        ON CONFLICT (email) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            apellido = EXCLUDED.apellido,
            dni = EXCLUDED.dni,
            rol = EXCLUDED.rol,
            cliente_id = EXCLUDED.cliente_id,
            password_hash = EXCLUDED.password_hash,
            activo = true,
            updated_at = now()
    """

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM usuarios")
            for user in OPERATIVE_USERS:
                cur.execute(
                    query,
                    [
                        user["email"],
                        user["nombre"],
                        user["apellido"],
                        user["dni"],
                        user["rol"],
                        user["cliente_id"],
                        hash_password(user["password"]),
                    ],
                )
        conn.commit()

    print(f"Usuarios operativos cargados: {len(OPERATIVE_USERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
