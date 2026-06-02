from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_DATABASE_URL = "postgresql://estres:estres_dev@127.0.0.1:5433/estres"
PARCELAS_VID_OLIVO = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
PARCELAS_COMPLETO = "data/parcelas/san_rafael_completo_wgs84.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aplica schema y carga datos operativos en PostGIS local."
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-clientes",
        action="store_true",
        help="Omite la carga de clientes demo.",
    )
    parser.add_argument(
        "--all-parcelas",
        action="store_true",
        help="Carga todas las parcelas oficiales, no solo vid/olivo.",
    )
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    return cli_value or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL


def run(command: list[str], dry_run: bool) -> None:
    print("CMD", " ".join(command), flush=True)
    if dry_run:
        return
    subprocess.run(command, check=True)


def main() -> None:
    args = parse_args()
    db_url = database_url(args.database_url)
    common = ["--database-url", db_url]
    if args.dry_run:
        common.append("--dry-run")

    print("=== Setup PostGIS local ===")
    print("Database URL:", db_url)
    print("Dry run:", args.dry_run)

    parcelas_command = [
        sys.executable,
        "scripts/cargar_parcelas_postgis.py",
        *common,
        "--input",
        PARCELAS_COMPLETO if args.all_parcelas else PARCELAS_VID_OLIVO,
    ]
    if args.all_parcelas:
        parcelas_command.append("--all-crops")

    commands = [
        [sys.executable, "scripts/aplicar_schema_postgis.py", *common],
        parcelas_command,
        [sys.executable, "scripts/cargar_ranking_postgis.py", *common],
        [sys.executable, "scripts/cargar_zonificacion_um_postgis.py", *common],
    ]
    if not args.skip_clientes:
        commands.insert(
            3,
            [sys.executable, "scripts/cargar_clientes_parcelas_postgis.py", *common],
        )

    for command in commands:
        run(command, args.dry_run)

    print("Setup PostGIS local finalizado.")


if __name__ == "__main__":
    main()
