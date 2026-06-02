import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


SCHEMA_PATH = "backend/sql/schema_postgis.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aplica el schema PostGIS del proyecto.")
    parser.add_argument("--schema", default=SCHEMA_PATH)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    value = cli_value or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Configurar DATABASE_URL o pasar --database-url.")
    return value


def main() -> None:
    args = parse_args()
    schema_path = Path(args.schema)
    sql = schema_path.read_text(encoding="utf-8")

    print("=== Aplicar schema PostGIS ===")
    print("Schema:", schema_path)
    print("Sentencias aprox:", sql.count(";"))
    print("Dry run:", args.dry_run)
    if args.dry_run:
        return

    import psycopg

    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

    print("Schema aplicado.")


if __name__ == "__main__":
    main()
