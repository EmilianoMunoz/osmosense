import argparse
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


INPUT_RANKING = "backend/data/rankings/ranking_hidrico_latest.csv"
RANKING_CONFIG = "backend/models/ranking_hidrico_config.json"
MODEL_DIR = "backend/models/hidrico_regresion"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Carga ranking hidrico en PostGIS.")
    parser.add_argument("--input", default=INPUT_RANKING)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--ranking-config", default=RANKING_CONFIG)
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


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    required = [
        "fecha_actual",
        "fecha_lectura",
        "dias_desde_lectura",
        "parcela_id",
        "cultivo",
        "ranking_global",
        "ranking_por_cultivo",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "riesgo_pred_5d",
        "riesgo_pred_10d",
        "delta_5d",
        "delta_10d",
        "riesgo_operativo_5d",
        "riesgo_operativo_10d",
        "delta_operativo_5d",
        "delta_operativo_10d",
        "tendencia_reciente_5d",
        "pendiente_operativa_5d",
        "factor_estacional",
        "ndmi_mean",
        "msi_mean",
        "ndwi_mean",
        "nbr_mean",
        "ndvi_mean",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Columnas faltantes en {args.input}: {missing}")

    rows = []
    for _, row in df.iterrows():
        rows.append(
            (
                pd.Timestamp(row["fecha_actual"]).date(),
                pd.Timestamp(row["fecha_lectura"]).date(),
                int(row["dias_desde_lectura"]),
                int(row["parcela_id"]),
                str(row["cultivo"]),
                int(row["ranking_global"]),
                int(row["ranking_por_cultivo"]),
                str(row["prioridad"]),
                clean_float(row["prioridad_score"]),
                clean_float(row["riesgo_actual"]),
                clean_float(row["riesgo_pred_5d"]),
                clean_float(row["riesgo_pred_10d"]),
                clean_float(row["delta_5d"]),
                clean_float(row["delta_10d"]),
                clean_float(row["riesgo_operativo_5d"]),
                clean_float(row["riesgo_operativo_10d"]),
                clean_float(row["delta_operativo_5d"]),
                clean_float(row["delta_operativo_10d"]),
                clean_float(row["tendencia_reciente_5d"]),
                clean_float(row["pendiente_operativa_5d"]),
                clean_float(row["factor_estacional"]),
                clean_float(row["ndmi_mean"]),
                clean_float(row["msi_mean"]),
                clean_float(row["ndwi_mean"]),
                clean_float(row["nbr_mean"]),
                clean_float(row["ndvi_mean"]),
                args.model_dir,
                args.ranking_config,
                args.pipeline_run_id,
            )
        )

    print("=== Carga ranking PostGIS ===")
    print("Input:", args.input)
    print("Filas:", len(rows))
    print("Fecha:", df["fecha_actual"].iloc[0] if not df.empty else None)
    print("Dry run:", args.dry_run)
    if args.dry_run:
        return

    import psycopg

    sql = """
        INSERT INTO ranking_hidrico (
            fecha_ranking,
            fecha_lectura,
            dias_desde_lectura,
            parcela_id,
            cultivo,
            ranking_global,
            ranking_por_cultivo,
            prioridad,
            prioridad_score,
            riesgo_actual,
            riesgo_pred_5d,
            riesgo_pred_10d,
            delta_5d,
            delta_10d,
            riesgo_operativo_5d,
            riesgo_operativo_10d,
            delta_operativo_5d,
            delta_operativo_10d,
            tendencia_reciente_5d,
            pendiente_operativa_5d,
            factor_estacional,
            ndmi_mean,
            msi_mean,
            ndwi_mean,
            nbr_mean,
            ndvi_mean,
            model_dir,
            ranking_config,
            pipeline_run_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (fecha_ranking, parcela_id) DO UPDATE SET
            fecha_lectura = EXCLUDED.fecha_lectura,
            dias_desde_lectura = EXCLUDED.dias_desde_lectura,
            cultivo = EXCLUDED.cultivo,
            ranking_global = EXCLUDED.ranking_global,
            ranking_por_cultivo = EXCLUDED.ranking_por_cultivo,
            prioridad = EXCLUDED.prioridad,
            prioridad_score = EXCLUDED.prioridad_score,
            riesgo_actual = EXCLUDED.riesgo_actual,
            riesgo_pred_5d = EXCLUDED.riesgo_pred_5d,
            riesgo_pred_10d = EXCLUDED.riesgo_pred_10d,
            delta_5d = EXCLUDED.delta_5d,
            delta_10d = EXCLUDED.delta_10d,
            riesgo_operativo_5d = EXCLUDED.riesgo_operativo_5d,
            riesgo_operativo_10d = EXCLUDED.riesgo_operativo_10d,
            delta_operativo_5d = EXCLUDED.delta_operativo_5d,
            delta_operativo_10d = EXCLUDED.delta_operativo_10d,
            tendencia_reciente_5d = EXCLUDED.tendencia_reciente_5d,
            pendiente_operativa_5d = EXCLUDED.pendiente_operativa_5d,
            factor_estacional = EXCLUDED.factor_estacional,
            ndmi_mean = EXCLUDED.ndmi_mean,
            msi_mean = EXCLUDED.msi_mean,
            ndwi_mean = EXCLUDED.ndwi_mean,
            nbr_mean = EXCLUDED.nbr_mean,
            ndvi_mean = EXCLUDED.ndvi_mean,
            model_dir = EXCLUDED.model_dir,
            ranking_config = EXCLUDED.ranking_config,
            pipeline_run_id = EXCLUDED.pipeline_run_id,
            created_at = now()
    """

    with psycopg.connect(database_url(args.database_url)) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, rows)
        conn.commit()

    print("Carga finalizada.")


if __name__ == "__main__":
    main()
