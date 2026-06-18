from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


INPUT_DETAIL = "backend/data/validacion_predictor_hidrico_detalle.csv"
INPUT_SUMMARY = "backend/data/validacion_predictor_hidrico_resumen.csv"
OUTPUT_REPORT = "docs/validacion_predictor_hidrico.md"
OUTPUT_AGGREGATE = "backend/data/validacion_predictor_hidrico_agregado.csv"
OUTPUT_WORST_DATES = "backend/data/validacion_predictor_hidrico_peores_fechas.csv"
HORIZONS = [5, 10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera reporte legible de validacion historica del predictor hidrico."
    )
    parser.add_argument("--detail", default=INPUT_DETAIL)
    parser.add_argument("--summary", default=INPUT_SUMMARY)
    parser.add_argument("--output-report", default=OUTPUT_REPORT)
    parser.add_argument("--output-aggregate", default=OUTPUT_AGGREGATE)
    parser.add_argument("--output-worst-dates", default=OUTPUT_WORST_DATES)
    parser.add_argument("--top-worst", type=int, default=8)
    return parser.parse_args()


def weighted_average(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return float("nan")
    return float(np.average(values[valid], weights=weights[valid]))


def aggregate_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["cultivo", "horizon_days"]
    for keys, group in summary.groupby(group_cols, dropna=False):
        cultivo, horizon = keys
        weights = group["n"]
        rows.append(
            {
                "cultivo": cultivo,
                "horizon_days": int(horizon),
                "fechas": int(group["fecha"].nunique()),
                "n_promedio": float(group["n"].mean()),
                "mae": weighted_average(group["mae"], weights),
                "rmse": weighted_average(group["rmse"], weights),
                "bias": weighted_average(group["bias"], weights),
                "spearman": weighted_average(group["spearman"], weights),
                "top10_overlap": weighted_average(group["top10_overlap"], weights),
            }
        )
    return pd.DataFrame(rows).sort_values(["cultivo", "horizon_days"]).reset_index(drop=True)


def aggregate_by_season(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["estacion", "cultivo", "horizon_days"]
    for keys, group in summary.groupby(group_cols, dropna=False):
        estacion, cultivo, horizon = keys
        weights = group["n"]
        rows.append(
            {
                "estacion": estacion,
                "cultivo": cultivo,
                "horizon_days": int(horizon),
                "fechas": int(group["fecha"].nunique()),
                "n_promedio": float(group["n"].mean()),
                "mae": weighted_average(group["mae"], weights),
                "spearman": weighted_average(group["spearman"], weights),
                "top10_overlap": weighted_average(group["top10_overlap"], weights),
            }
        )
    return pd.DataFrame(rows).sort_values(["estacion", "cultivo", "horizon_days"]).reset_index(drop=True)


def detail_metrics(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon in HORIZONS:
        pred_col = f"riesgo_pred_{horizon}d"
        obs_col = f"riesgo_obs_{horizon}d"
        delta_col = f"delta_{horizon}d"
        delta_obs_col = f"delta_obs_{horizon}d"
        error_col = f"error_{horizon}d"
        required = [pred_col, obs_col, delta_col, delta_obs_col, error_col]
        if not set(required).issubset(detail.columns):
            continue

        data = detail.dropna(subset=required).copy()
        for cultivo, group in data.groupby("cultivo", dropna=False):
            error_abs = group[error_col].abs()
            pred_direction = np.sign(group[delta_col])
            obs_direction = np.sign(group[delta_obs_col])
            direction_match = pred_direction == obs_direction
            rows.append(
                {
                    "cultivo": cultivo,
                    "horizon_days": horizon,
                    "n": int(len(group)),
                    "pct_error_le_5": float((error_abs <= 5).mean()),
                    "pct_error_le_10": float((error_abs <= 10).mean()),
                    "direction_accuracy": float(direction_match.mean()),
                    "obs_delta_mean": float(group[delta_obs_col].mean()),
                    "pred_delta_mean": float(group[delta_col].mean()),
                }
            )
        if not data.empty:
            error_abs = data[error_col].abs()
            pred_direction = np.sign(data[delta_col])
            obs_direction = np.sign(data[delta_obs_col])
            rows.append(
                {
                    "cultivo": "global",
                    "horizon_days": horizon,
                    "n": int(len(data)),
                    "pct_error_le_5": float((error_abs <= 5).mean()),
                    "pct_error_le_10": float((error_abs <= 10).mean()),
                    "direction_accuracy": float((pred_direction == obs_direction).mean()),
                    "obs_delta_mean": float(data[delta_obs_col].mean()),
                    "pred_delta_mean": float(data[delta_col].mean()),
                }
            )

    return pd.DataFrame(rows).sort_values(["cultivo", "horizon_days"]).reset_index(drop=True)


def worst_dates(summary: pd.DataFrame, top: int) -> pd.DataFrame:
    global_rows = summary[summary["cultivo"] == "global"].copy()
    if global_rows.empty:
        return pd.DataFrame()

    worst_mae = global_rows.sort_values("mae", ascending=False).head(top).copy()
    worst_mae["criterio"] = "mayor_mae"
    worst_spearman = global_rows.sort_values("spearman", ascending=True).head(top).copy()
    worst_spearman["criterio"] = "menor_spearman"
    return pd.concat([worst_mae, worst_spearman], ignore_index=True)


def fmt(value: float | int | str, digits: int = 3) -> str:
    if isinstance(value, str):
        return value
    if pd.isna(value):
        return "-"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    return f"{float(value):.{digits}f}"


def markdown_table(df: pd.DataFrame, columns: list[str], digits: int = 3) -> str:
    if df.empty:
        return "_Sin datos._"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    lines = [header, sep]
    for _, row in df[columns].iterrows():
        lines.append("| " + " | ".join(fmt(row[col], digits) for col in columns) + " |")
    return "\n".join(lines)


def build_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    by_season: pd.DataFrame,
    detail_agg: pd.DataFrame,
    worst: pd.DataFrame,
) -> str:
    fechas = sorted(summary["fecha"].astype(str).unique())
    lines = [
        "# Validacion del Predictor Hidrico",
        "",
        "Reporte generado desde validacion historica contra observaciones Sentinel-2 futuras.",
        "",
        "## Cobertura",
        "",
        f"- Fechas evaluadas: {len(fechas)}",
        f"- Rango: {fechas[0]} a {fechas[-1]}",
        "",
        "## Resumen Global Por Cultivo Y Horizonte",
        "",
        markdown_table(
            aggregate,
            [
                "cultivo",
                "horizon_days",
                "fechas",
                "n_promedio",
                "mae",
                "rmse",
                "bias",
                "spearman",
                "top10_overlap",
            ],
        ),
        "",
        "## Error Operativo",
        "",
        "Porcentaje de predicciones dentro de 5 y 10 puntos de error absoluto.",
        "",
        markdown_table(
            detail_agg,
            [
                "cultivo",
                "horizon_days",
                "n",
                "pct_error_le_5",
                "pct_error_le_10",
                "direction_accuracy",
                "obs_delta_mean",
                "pred_delta_mean",
            ],
        ),
        "",
        "## Resumen Por Estacion",
        "",
        markdown_table(
            by_season,
            [
                "estacion",
                "cultivo",
                "horizon_days",
                "fechas",
                "mae",
                "spearman",
                "top10_overlap",
            ],
        ),
        "",
        "## Fechas A Revisar",
        "",
        markdown_table(
            worst,
            [
                "criterio",
                "fecha",
                "estacion",
                "horizon_days",
                "n",
                "mae",
                "rmse",
                "bias",
                "spearman",
                "top10_overlap",
            ],
        ),
        "",
        "## Lectura",
        "",
        "- `MAE` indica error promedio en puntos de score hidrico sobre escala 0-100.",
        "- `Spearman` mide si el modelo mantiene bien el orden relativo de parcelas.",
        "- `top10_overlap` mide coincidencia entre el 10% de parcelas mas criticas predichas y observadas.",
        "- `direction_accuracy` mide si el modelo acierta el signo de la evolucion respecto del riesgo actual.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    detail = pd.read_csv(args.detail)
    summary = pd.read_csv(args.summary)

    aggregate = aggregate_summary(summary)
    by_season = aggregate_by_season(summary)
    detail_agg = detail_metrics(detail)
    worst = worst_dates(summary, args.top_worst)

    aggregate_out = aggregate.copy()
    if not by_season.empty:
        by_season_out = by_season.copy()
        by_season_out.insert(0, "tipo_agregado", "estacion")
        aggregate_out.insert(0, "tipo_agregado", "global")
        aggregate_out = pd.concat([aggregate_out, by_season_out], ignore_index=True, sort=False)
    output_aggregate = Path(args.output_aggregate)
    output_aggregate.parent.mkdir(parents=True, exist_ok=True)
    aggregate_out.to_csv(output_aggregate, index=False)

    output_worst = Path(args.output_worst_dates)
    worst.to_csv(output_worst, index=False)

    report = build_report(summary, aggregate, by_season, detail_agg, worst)
    output_report = Path(args.output_report)
    output_report.write_text(report, encoding="utf-8")

    print("=== Reporte validacion predictor hidrico ===")
    print("Detalle:", args.detail)
    print("Resumen:", args.summary)
    print("Agregado:", output_aggregate)
    print("Peores fechas:", output_worst)
    print("Reporte:", output_report)
    print()
    print(markdown_table(aggregate, ["cultivo", "horizon_days", "mae", "spearman", "top10_overlap"]))


if __name__ == "__main__":
    main()
