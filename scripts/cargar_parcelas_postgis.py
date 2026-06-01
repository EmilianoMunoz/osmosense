import argparse
import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from shapely.geometry import MultiPolygon, Polygon
from shapely import wkb


INPUT_GEOJSON = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga parcelas base en PostGIS.")
    parser.add_argument("--input", default=INPUT_GEOJSON)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--id-column", default="fid")
    parser.add_argument("--cultivo-column", default="cultivo")
    parser.add_argument("--area-column", default="shape_Area")
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


def main() -> None:
    args = parse_args()
    gdf = gpd.read_file(args.input)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    required = [args.id_column, args.cultivo_column, args.area_column, "geometry"]
    missing = [col for col in required if col not in gdf.columns]
    if missing:
        raise RuntimeError(f"Columnas faltantes en {args.input}: {missing}")

    gdf = gdf.dropna(subset=[args.id_column, args.cultivo_column, "geometry"]).copy()
    rows = []
    for _, row in gdf.iterrows():
        geom = normalize_geometry(row.geometry)
        rows.append(
            (
                int(row[args.id_column]),
                str(row[args.cultivo_column]).lower(),
                float(row[args.area_column]) if row[args.area_column] is not None else None,
                str(row.get("globalid", "")) or None,
                wkb.dumps(geom, hex=False, srid=4326),
            )
        )

    print("=== Carga parcelas PostGIS ===")
    print("Input:", args.input)
    print("Parcelas:", len(rows))
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
            parcela_id, cultivo_oficial, area_m2, globalid, geom
        )
        VALUES (%s, %s, %s, %s, ST_Multi(ST_SetSRID(ST_GeomFromWKB(%s), 4326)))
        ON CONFLICT (parcela_id) DO UPDATE SET
            cultivo_oficial = EXCLUDED.cultivo_oficial,
            area_m2 = EXCLUDED.area_m2,
            globalid = EXCLUDED.globalid,
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
