from __future__ import annotations

import os
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from shapely.geometry import shape


MIN_TARGET_AREA_M2 = 4000


def require_database_url(cli_value: str | None = None) -> str:
    load_dotenv()
    value = cli_value or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Configurar DATABASE_URL o pasar --database-url.")
    return value


def load_target_parcels_from_postgis(
    database_url: str,
    min_area_m2: float = MIN_TARGET_AREA_M2,
) -> gpd.GeoDataFrame:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            parcela_id,
            cultivo_oficial AS cultivo,
            area_m2,
            ST_AsGeoJSON(geom)::json AS geometry
        FROM parcelas
        WHERE activo = true
          AND cultivo_oficial IN ('vid', 'olivo')
          AND COALESCE(area_m2, 0) >= %s
        ORDER BY parcela_id
    """
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [min_area_m2])
            rows = cur.fetchall()

    if not rows:
        raise RuntimeError("PostGIS no devolvio parcelas objetivo activas vid/olivo.")

    records = []
    geometries = []
    for row in rows:
        item = dict(row)
        geometries.append(shape(item.pop("geometry")))
        item["parcela_id"] = int(item["parcela_id"])
        item["id"] = str(item["parcela_id"])
        records.append(item)

    return gpd.GeoDataFrame(records, geometry=geometries, crs="EPSG:4326")


def write_target_snapshot(gdf: gpd.GeoDataFrame, output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(
        f".{output_path.stem}.{os.getpid()}{output_path.suffix or '.geojson'}"
    )
    try:
        gdf.to_file(temporary, driver="GeoJSON")
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return output_path
