import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validar_ranking_hidrico import validar


INPUT_TEMPORAL = "data/dataset_temporal_hidrico.csv"
MODEL_DIR = "models/hidrico_regresion"
OUTPUT_DETAIL = "data/validacion_ranking_hidrico_multifecha.csv"
OUTPUT_SUMMARY = "data/validacion_ranking_hidrico_multifecha_resumen.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida el ranking hidrico en multiples fechas historicas."
    )
    parser.add_argument("--input", default=INPUT_TEMPORAL)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-detail", default=OUTPUT_DETAIL)
    parser.add_argument("--output-summary", default=OUTPUT_SUMMARY)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument(
        "--every",
        type=int,
        default=4,
        help="Evalua una de cada N fechas validas para reducir costo.",
    )
    parser.add_argument(
        "--max-fechas",
        type=int,
        default=None,
        help="Limita cantidad de fechas evaluadas.",
    )
    parser.add_argument(
        "--min-n-summary",
        type=int,
        default=50,
        help="Descarta filas de resumen con menos de N parcelas evaluadas.",
    )
    return parser.parse_args()


def fechas_validas(df: pd.DataFrame, start_date: str | None, end_date: str | None) -> list[str]:
    fechas = pd.Series(pd.to_datetime(df["fecha"].unique())).sort_values()
    fecha_set = set(fechas)

    validas = []
    for fecha in fechas:
        if start_date and fecha < pd.Timestamp(start_date):
            continue
        if end_date and fecha > pd.Timestamp(end_date):
            continue
        if fecha + pd.Timedelta(days=5) not in fecha_set:
            continue
        if fecha + pd.Timedelta(days=10) not in fecha_set:
            continue
        validas.append(fecha.strftime("%Y-%m-%d"))

    return validas


def agregar_estacion(summary: pd.DataFrame, fecha: str) -> pd.DataFrame:
    summary = summary.copy()
    ts = pd.Timestamp(fecha)
    month = ts.month
    if month in [12, 1, 2]:
        estacion = "verano"
    elif month in [3, 4, 5]:
        estacion = "otono"
    elif month in [6, 7, 8]:
        estacion = "invierno"
    else:
        estacion = "primavera"

    summary.insert(0, "fecha", fecha)
    summary.insert(1, "month", month)
    summary.insert(2, "estacion", estacion)
    return summary


def main() -> None:
    args = parse_args()
    df_temporal = pd.read_csv(args.input)
    model_dir = Path(args.model_dir)

    fechas = fechas_validas(df_temporal, args.start_date, args.end_date)
    fechas = fechas[:: max(1, args.every)]
    if args.max_fechas:
        fechas = fechas[: args.max_fechas]

    if not fechas:
        raise RuntimeError("No hay fechas validas para evaluar X+5 y X+10.")

    all_detail = []
    all_summary = []

    print("=== Validacion ranking hidrico multifecha ===")
    print(f"Fechas a evaluar: {len(fechas)}")
    print(f"Primera fecha: {fechas[0]}")
    print(f"Ultima fecha: {fechas[-1]}")

    for i, fecha in enumerate(fechas, start=1):
        print(f"[{i}/{len(fechas)}] {fecha}", flush=True)
        detail, summary = validar(df_temporal, model_dir, fecha)
        detail.insert(0, "fecha_validacion", fecha)
        all_detail.append(detail)
        all_summary.append(agregar_estacion(summary, fecha))

    detail_df = pd.concat(all_detail, ignore_index=True)
    summary_df = pd.concat(all_summary, ignore_index=True)
    summary_df = summary_df[summary_df["n"] >= args.min_n_summary].copy()
    if summary_df.empty:
        raise RuntimeError(
            f"No quedaron metricas agregadas con min-n-summary={args.min_n_summary}."
        )

    output_detail = Path(args.output_detail)
    output_summary = Path(args.output_summary)
    output_detail.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    detail_df.to_csv(output_detail, index=False)
    summary_df.to_csv(output_summary, index=False)

    print("\n=== Resumen agregado ===")
    cols = ["cultivo", "horizon_days"]
    agg = (
        summary_df.groupby(cols)
        .agg(
            fechas=("fecha", "nunique"),
            n_promedio=("n", "mean"),
            mae_mean=("mae", "mean"),
            rmse_mean=("rmse", "mean"),
            bias_mean=("bias", "mean"),
            spearman_mean=("spearman", "mean"),
            top10_overlap_mean=("top10_overlap", "mean"),
        )
        .reset_index()
    )
    print(agg.to_string(index=False))
    print("\nDetalle:", output_detail)
    print("Resumen:", output_summary)

    print("\n=== Por estacion ===")
    estacion = (
        summary_df.groupby(["estacion", "cultivo", "horizon_days"])
        .agg(
            fechas=("fecha", "nunique"),
            mae_mean=("mae", "mean"),
            spearman_mean=("spearman", "mean"),
            top10_overlap_mean=("top10_overlap", "mean"),
        )
        .reset_index()
        .sort_values(["estacion", "cultivo", "horizon_days"])
    )
    print(estacion.to_string(index=False))


if __name__ == "__main__":
    main()
