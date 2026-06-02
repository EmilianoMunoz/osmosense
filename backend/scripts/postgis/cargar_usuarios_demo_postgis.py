from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from backend.app.services.auth import hash_password


DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"


DEMO_USERS = [
    {
        "email": "admin",
        "nombre": "Administrador",
        "rol": "admin",
        "cliente_id": None,
        "password": "admin123",
    },
    {
        "email": "finca",
        "nombre": "Finca Demo Norte",
        "rol": "cliente_particular",
        "cliente_id": 1,
        "password": "cliente123",
    },
    {
        "email": "olivar",
        "nombre": "Olivar Demo Este",
        "rol": "cliente_particular",
        "cliente_id": 2,
        "password": "cliente123",
    },
    {
        "email": "regional",
        "nombre": "Regional DGI",
        "rol": "cliente_regional",
        "cliente_id": None,
        "password": "regional123",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga usuarios demo para login contra PostGIS."
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

    print("=== Carga usuarios demo PostGIS ===")
    print("Database URL:", db_url)
    print("Dry run:", args.dry_run)

    if args.dry_run:
        for user in DEMO_USERS:
            print(f"DRY usuario={user['email']} rol={user['rol']} cliente_id={user['cliente_id']}")
        return 0

    import psycopg

    query = """
        INSERT INTO usuarios (
            email,
            nombre,
            rol,
            cliente_id,
            password_hash,
            activo,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, true, now())
        ON CONFLICT (email) DO UPDATE SET
            nombre = EXCLUDED.nombre,
            rol = EXCLUDED.rol,
            cliente_id = EXCLUDED.cliente_id,
            password_hash = EXCLUDED.password_hash,
            activo = true,
            updated_at = now()
    """

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            for user in DEMO_USERS:
                cur.execute(
                    query,
                    [
                        user["email"],
                        user["nombre"],
                        user["rol"],
                        user["cliente_id"],
                        hash_password(user["password"]),
                    ],
                )
        conn.commit()

    print(f"Usuarios demo cargados: {len(DEMO_USERS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
