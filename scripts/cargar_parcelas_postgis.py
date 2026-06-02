import argparse
import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from shapely.geometry import MultiPolygon, Polygon
from shapely import wkb


INPUT_GEOJSON = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
TARGET_CROPS = {"vid", "olivo"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga parcelas base en PostGIS.")
    parser.add_argument("--input", default=INPUT_GEOJSON)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--id-column", default="fid")
    parser.add_argument("--cultivo-column", default=None)
    parser.add_argument("--cultivo-original-column", default="tipo_culti")
    parser.add_argument("--area-column", default="shape_Area")
    parser.add_argument(
        "--all-crops",
        action="store_true",
        help="Carga todas las parcelas. Sin este flag solo carga vid/olivo.",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    value = cli_value or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Configurar DATABASE_URL o pasar --database-url.")
    return value


def normalize_geometry(geom):
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    return geom


def normalize_crop(value: object) -> str:
    raw = str(value or "").strip().upper()
    if raw == "VID":
        return "vid"
    if raw == "OLIVOS":
        return "olivo"
    if raw == "FRUTALES":
        return "frutales"
    if raw == "ANUALES":
        return "anuales"
    if raw == "INCULTOS":
        return "incultos"
    if not raw:
        return "sin_dato"
    return raw.lower()


def crop_from_row(row, cultivo_column: str | None, cultivo_original_column: str) -> str:
    if cultivo_column and cultivo_column in row and row[cultivo_column] is not None:
        return normalize_crop(row[cultivo_column])
    return normalize_crop(row.get(cultivo_original_column))


def main() -> None:
    args = parse_args()
    gdf = gpd.read_file(args.input)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    required = [args.id_column, args.cultivo_original_column, args.area_column, "geometry"]
    missing = [col for col in required if col not in gdf.columns]
    if missing:
        raise RuntimeError(f"Columnas faltantes en {args.input}: {missing}")

    gdf = gdf.dropna(subset=[args.id_column, "geometry"]).copy()
    rows = []
    for _, row in gdf.iterrows():
        geom = normalize_geometry(row.geometry)
        cultivo_oficial = crop_from_row(
            row,
            args.cultivo_column,
            args.cultivo_original_column,
        )
        if not args.all_crops and cultivo_oficial not in TARGET_CROPS:
            continue
        cultivo_original = (
            None
            if row.get(args.cultivo_original_column) is None
            else str(row.get(args.cultivo_original_column)).strip()
        )
        rows.append(
            (
                int(row[args.id_column]),
                cultivo_oficial,
                cultivo_original,
                float(row[args.area_column]) if row[args.area_column] is not None else None,
                str(row.get("globalid", "")) or None,
                wkb.dumps(geom, hex=False, srid=4326),
            )
        )

    print("=== Carga parcelas PostGIS ===")
    print("Input:", args.input)
    print("Parcelas:", len(rows))
    print("Todas las categorias:", args.all_crops)
    print("Dry run:", args.dry_run)
    if args.dry_run:
        return

    import psycopg

    rows = [
        (*row[:-1], psycopg.Binary(row[-1]))
        for row in rows
    ]

    sql = """
        INSERT INTO parcelas (
            parcela_id, cultivo_oficial, cultivo_original, area_m2, globalid, activo, geom
        )
        VALUES (%s, %s, %s, %s, %s, true, ST_Multi(ST_SetSRID(ST_GeomFromWKB(%s), 4326)))
        ON CONFLICT (parcela_id) DO UPDATE SET
            cultivo_oficial = EXCLUDED.cultivo_oficial,
            cultivo_original = EXCLUDED.cultivo_original,
            area_m2 = EXCLUDED.area_m2,
            globalid = EXCLUDED.globalid,
            activo = true,
            geom = EXCLUDED.geom,
            updated_at = now()
    """

    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()

    print("Carga finalizada.")


if __name__ == "__main__":
    main()
