from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv


DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida conteos básicos en PostGIS.")
    parser.add_argument("--database-url", default=None)
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    return cli_value or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def main() -> None:
    args = parse_args()
    import psycopg

    checks = [
        ("parcelas", "SELECT count(*) FROM parcelas"),
        ("ranking_hidrico_latest", "SELECT count(*) FROM ranking_hidrico_latest"),
        ("clientes", "SELECT count(*) FROM clientes"),
        ("cliente_parcela", "SELECT count(*) FROM cliente_parcela"),
        ("zonas_um", "SELECT count(*) FROM zonas_um"),
        ("parcela_um", "SELECT count(*) FROM parcela_um"),
        ("ranking_um_latest", "SELECT count(*) FROM ranking_um_latest"),
        ("postgis_version", "SELECT postgis_version()"),
    ]

    print("=== Validación PostGIS ===")
    print("Database URL:", database_url(args.database_url))
    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            for label, query in checks:
                cur.execute(query)
                value = cur.fetchone()[0]
                print(f"{label}: {value}")


if __name__ == "__main__":
    main()
