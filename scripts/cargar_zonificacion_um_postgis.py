import argparse
import json
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv


ZONAS_GEOJSON = "data/zonificacion/um_con_cultivos.geojson"
PARCELAS_UM_CSV = "data/zonificacion/parcelas_um.csv"
RANKING_UM_CSV = "data/zonificacion/ranking_um_latest.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga zonificacion UM y ranking regional en PostGIS.")
    parser.add_argument("--zonas", default=ZONAS_GEOJSON)
    parser.add_argument("--parcelas-um", default=PARCELAS_UM_CSV)
    parser.add_argument("--ranking-um", default=RANKING_UM_CSV)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--pipeline-run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def database_url(cli_value: str | None) -> str:
    load_dotenv()
    value = cli_value or os.getenv("DATABASE_URL")
    if not value:
        raise RuntimeError("Configurar DATABASE_URL o pasar --database-url.")
    return value


def clean_float(value):
    if pd.isna(value):
        return None
    return float(value)


def clean_int(value):
    if pd.isna(value):
        return None
    return int(value)


def read_zonas(path: str | Path) -> list[tuple]:
    gdf = gpd.read_file(path).to_crs("EPSG:4326")
    required = {"um_id", "fid", "nombre", "geometry"}
    missing = sorted(required - set(gdf.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    rows = []
    for _, row in gdf.iterrows():
        rows.append(
            (
                int(row["um_id"]),
                clean_int(row["fid"]),
                str(row["nombre"]),
                None if pd.isna(row.get("cuenca")) else str(row.get("cuenca")),
                clean_float(row.get("sup_ha_san_rafael")),
                clean_float(row.get("pct_sup_en_san_rafael")),
                json.dumps(row.geometry.__geo_interface__),
            )
        )
    return rows


def read_parcelas_um(path: str | Path) -> list[tuple]:
    df = pd.read_csv(path)
    required = {"parcela_id", "um_id", "intersection_m2", "pct_parcela_en_um"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    return [
        (
            int(row["parcela_id"]),
            int(row["um_id"]),
            clean_float(row["intersection_m2"]),
            clean_float(row["pct_parcela_en_um"]),
        )
        for _, row in df.iterrows()
    ]


def read_ranking_um(path: str | Path, pipeline_run_id: str | None) -> list[tuple]:
    df = pd.read_csv(path)
    required = {
        "fecha_actual",
        "um_id",
        "ranking_um",
        "prioridad_regional",
        "parcelas_total",
        "parcelas_rankeadas",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    rows = []
    for _, row in df.iterrows():
        rows.append(
            (
                pd.Timestamp(row["fecha_actual"]).date(),
                int(row["um_id"]),
                int(row["ranking_um"]),
                str(row["prioridad_regional"]),
                clean_int(row.get("parcelas_total")),
                clean_int(row.get("parcelas_rankeadas")),
                clean_int(row.get("parcelas_sin_ranking")),
                clean_float(row.get("pct_parcelas_rankeadas")),
                clean_float(row.get("area_cultivada_ha")),
                clean_float(row.get("area_rankeada_ha")),
                clean_int(row.get("vid_parcelas")),
                clean_int(row.get("olivo_parcelas")),
                clean_float(row.get("prioridad_score_prom_pond")),
                clean_float(row.get("prioridad_score_mediana")),
                clean_float(row.get("riesgo_actual_prom_pond")),
                clean_float(row.get("riesgo_5d_prom_pond")),
                clean_float(row.get("riesgo_10d_prom_pond")),
                clean_float(row.get("delta_10d_prom_pond")),
                clean_float(row.get("pct_alta_critica")),
                clean_float(row.get("pct_critica")),
                pipeline_run_id,
            )
        )
    return rows


def main() -> None:
    args = parse_args()
    zonas = read_zonas(args.zonas)
    parcelas_um = read_parcelas_um(args.parcelas_um)
    ranking_um = read_ranking_um(args.ranking_um, args.pipeline_run_id)

    print("=== Carga zonificacion UM PostGIS ===")
    print("Zonas:", len(zonas))
    print("Relaciones parcela-UM:", len(parcelas_um))
    print("Ranking UM:", len(ranking_um))
    print("Dry run:", args.dry_run)
    if args.dry_run:
        return

    import psycopg

    sql_zonas = """
        INSERT INTO zonas_um (
            um_id, um_fid, nombre, cuenca, sup_ha_san_rafael,
            pct_sup_en_san_rafael, geom
        )
        VALUES (%s, %s, %s, %s, %s, %s, ST_Multi(ST_GeomFromGeoJSON(%s)))
        ON CONFLICT (um_id) DO UPDATE SET
            um_fid = EXCLUDED.um_fid,
            nombre = EXCLUDED.nombre,
            cuenca = EXCLUDED.cuenca,
            sup_ha_san_rafael = EXCLUDED.sup_ha_san_rafael,
            pct_sup_en_san_rafael = EXCLUDED.pct_sup_en_san_rafael,
            geom = EXCLUDED.geom,
            updated_at = now()
    """
    sql_parcelas_um = """
        INSERT INTO parcela_um (
            parcela_id, um_id, intersection_m2, pct_parcela_en_um
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (parcela_id) DO UPDATE SET
            um_id = EXCLUDED.um_id,
            intersection_m2 = EXCLUDED.intersection_m2,
            pct_parcela_en_um = EXCLUDED.pct_parcela_en_um,
            updated_at = now()
    """
    sql_ranking_um = """
        INSERT INTO ranking_um (
            fecha_ranking, um_id, ranking_um, prioridad_regional,
            parcelas_total, parcelas_rankeadas, parcelas_sin_ranking,
            pct_parcelas_rankeadas, area_cultivada_ha, area_rankeada_ha,
            vid_parcelas, olivo_parcelas, prioridad_score_prom_pond,
            prioridad_score_mediana, riesgo_actual_prom_pond, riesgo_5d_prom_pond,
            riesgo_10d_prom_pond, delta_10d_prom_pond, pct_alta_critica,
            pct_critica, pipeline_run_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (fecha_ranking, um_id) DO UPDATE SET
            ranking_um = EXCLUDED.ranking_um,
            prioridad_regional = EXCLUDED.prioridad_regional,
            parcelas_total = EXCLUDED.parcelas_total,
            parcelas_rankeadas = EXCLUDED.parcelas_rankeadas,
            parcelas_sin_ranking = EXCLUDED.parcelas_sin_ranking,
            pct_parcelas_rankeadas = EXCLUDED.pct_parcelas_rankeadas,
            area_cultivada_ha = EXCLUDED.area_cultivada_ha,
            area_rankeada_ha = EXCLUDED.area_rankeada_ha,
            vid_parcelas = EXCLUDED.vid_parcelas,
            olivo_parcelas = EXCLUDED.olivo_parcelas,
            prioridad_score_prom_pond = EXCLUDED.prioridad_score_prom_pond,
            prioridad_score_mediana = EXCLUDED.prioridad_score_mediana,
            riesgo_actual_prom_pond = EXCLUDED.riesgo_actual_prom_pond,
            riesgo_5d_prom_pond = EXCLUDED.riesgo_5d_prom_pond,
            riesgo_10d_prom_pond = EXCLUDED.riesgo_10d_prom_pond,
            delta_10d_prom_pond = EXCLUDED.delta_10d_prom_pond,
            pct_alta_critica = EXCLUDED.pct_alta_critica,
            pct_critica = EXCLUDED.pct_critica,
            pipeline_run_id = EXCLUDED.pipeline_run_id,
            created_at = now()
    """

    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql_zonas, zonas)
            cur.executemany(sql_parcelas_um, parcelas_um)
            cur.executemany(sql_ranking_um, ranking_um)
        conn.commit()

    print("Carga finalizada.")


if __name__ == "__main__":
    main()
