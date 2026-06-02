import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.pipeline.generar_targets_hidricos_regresion import preparar_observaciones


INPUT_TEMPORAL = "backend/data/dataset_temporal_hidrico.csv"
INPUT_OUTLIERS = "backend/data/auditoria_vecinos_ranking_riesgo_actual.csv"
OUTPUT_DETALLE = "backend/data/auditoria_outliers_temporales.csv"
OUTPUT_RESUMEN = "backend/data/auditoria_outliers_temporales_resumen.csv"

HYDRIC_REL_FEATURES = [
    ("ndmi_mean_rel_fecha", "low_is_risk"),
    ("msi_mean_rel_fecha", "high_is_risk"),
    ("ndwi_mean_rel_fecha", "low_is_risk"),
    ("nbr_mean_rel_fecha", "low_is_risk"),
    ("ndvi_mean_rel_fecha", "low_is_risk"),
]
COUNT_COLUMNS = ["ndmi_count", "msi_count", "ndwi_count", "nbr_count", "ndvi_count"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita persistencia temporal de outliers espaciales."
    )
    parser.add_argument("--temporal", default=INPUT_TEMPORAL)
    parser.add_argument("--outliers", default=INPUT_OUTLIERS)
    parser.add_argument("--output-detalle", default=OUTPUT_DETALLE)
    parser.add_argument("--output-resumen", default=OUTPUT_RESUMEN)
    parser.add_argument(
        "--neighbor-threshold",
        type=float,
        default=35.0,
        help="Diferencia minima contra vecinos para tomar outliers.",
    )
    parser.add_argument(
        "--risk-high-threshold",
        type=float,
        default=55.0,
        help="Riesgo considerado alto para evaluar persistencia.",
    )
    parser.add_argument(
        "--risk-low-threshold",
        type=float,
        default=35.0,
        help="Riesgo considerado bajo para evaluar persistencia.",
    )
    parser.add_argument(
        "--min-valid-pixels-strong",
        type=int,
        default=20,
        help="Minimo de pixeles validos para considerar fuerte la lectura.",
    )
    parser.add_argument(
        "--support-rel-threshold",
        type=float,
        default=0.5,
        help="Umbral relativo por fecha para contar soporte espectral.",
    )
    parser.add_argument(
        "--recent-window-days",
        type=int,
        default=45,
        help="Ventana historica hacia atras usada para soporte temporal ponderado.",
    )
    parser.add_argument(
        "--weight-step-days",
        type=float,
        default=5.0,
        help="Escala de ponderacion: t-5 pesa mas que t-10, t-15, etc.",
    )
    return parser.parse_args()


def cargar_outliers(path: str, neighbor_threshold: float) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "parcela_id",
        "outlier_espacial",
        "riesgo_actual",
        "riesgo_actual_vs_neighbor_median",
        "abs_riesgo_actual_vs_neighbor_median",
        "neighbor_count",
        "fecha_actual",
        "cultivo",
        "prioridad",
        "prioridad_score",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    outliers = df[
        (df["outlier_espacial"].astype(bool))
        & (df["abs_riesgo_actual_vs_neighbor_median"] >= neighbor_threshold)
    ].copy()
    outliers["parcela_id"] = outliers["parcela_id"].astype(int)
    outliers["fecha_actual"] = pd.to_datetime(outliers["fecha_actual"])
    return outliers


def soporte_espectral(row: pd.Series, direction: str, threshold: float) -> tuple[int, str]:
    soportes = []
    for col, risk_direction in HYDRIC_REL_FEATURES:
        value = row.get(col, np.nan)
        if pd.isna(value):
            continue

        if direction == "alto":
            supported = value >= threshold if risk_direction == "high_is_risk" else value <= -threshold
        else:
            supported = value <= -threshold if risk_direction == "high_is_risk" else value >= threshold

        if supported:
            soportes.append(col.replace("_mean_rel_fecha", ""))

    return len(soportes), ",".join(soportes)


def estado_persistencia(row: pd.Series, direction: str, high: float, low: float) -> str:
    weighted_mean = row.get("riesgo_reciente_weighted_mean", np.nan)
    if pd.notna(weighted_mean):
        if direction == "alto":
            return "persistente" if weighted_mean >= high else "puntual"
        return "persistente" if weighted_mean <= low else "puntual"

    lag_values = [
        row.get("riesgo_hidrico_lag1", np.nan),
        row.get("riesgo_hidrico_lag2", np.nan),
    ]
    available = [value for value in lag_values if pd.notna(value)]
    if not available:
        return "sin_historial_reciente"

    if direction == "alto":
        persistent = any(value >= high for value in available)
    else:
        persistent = any(value <= low for value in available)

    return "persistente" if persistent else "puntual"


def calcular_historial_reciente(
    obs_ids: pd.DataFrame,
    outliers: pd.DataFrame,
    recent_window_days: int,
    weight_step_days: float,
) -> pd.DataFrame:
    latest_by_id = outliers.set_index("parcela_id")["fecha_actual"].to_dict()
    prev = obs_ids.copy()
    prev["fecha_actual_outlier"] = prev["parcela_id"].map(latest_by_id)
    prev["dias_previos"] = (
        prev["fecha_actual_outlier"] - prev["fecha"]
    ).dt.days.astype(float)
    prev = prev[
        (prev["dias_previos"] > 0)
        & (prev["dias_previos"] <= recent_window_days)
    ].copy()

    if prev.empty:
        return pd.DataFrame(
            columns=[
                "parcela_id",
                "historial_reciente_count",
                "historial_reciente_min_dias",
                "historial_reciente_max_dias",
                "riesgo_reciente_weighted_mean",
            ]
        )

    prev["peso_temporal"] = weight_step_days / prev["dias_previos"].clip(lower=weight_step_days)
    prev["riesgo_x_peso"] = prev["riesgo_hidrico"] * prev["peso_temporal"]

    grouped = prev.groupby("parcela_id", sort=False)
    weighted = (
        grouped["riesgo_x_peso"].sum() / grouped["peso_temporal"].sum()
    ).rename("riesgo_reciente_weighted_mean")
    stats = grouped["dias_previos"].agg(
        historial_reciente_count="count",
        historial_reciente_min_dias="min",
        historial_reciente_max_dias="max",
    )
    return stats.join(weighted).reset_index()


def diagnosticar(row: pd.Series, min_pixels: int) -> str:
    if row["persistencia_temporal"] == "persistente" and row["soporte_indices_count"] >= 3:
        if row["min_valid_pixels_hidricos"] >= min_pixels:
            return "probable_manejo_real_o_condicion_persistente"
        return "indeterminado_por_pocos_pixeles"

    if row["persistencia_temporal"] == "puntual":
        if row["soporte_indices_count"] <= 2 or row["min_valid_pixels_hidricos"] < min_pixels:
            return "probable_ruido_o_lectura_puntual"

    if row["persistencia_temporal"] == "sin_historial_reciente":
        return "indeterminado_sin_historial_reciente"

    return "indeterminado"


def auditar(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    outliers = cargar_outliers(args.outliers, args.neighbor_threshold)
    if outliers.empty:
        raise RuntimeError("No hay outliers espaciales para auditar.")

    temporal = pd.read_csv(args.temporal)
    observaciones = preparar_observaciones(temporal)
    observaciones["parcela_id"] = observaciones["parcela_id"].astype(int)
    observaciones["fecha"] = pd.to_datetime(observaciones["fecha"])

    ids = set(outliers["parcela_id"].tolist())
    obs_ids = observaciones[observaciones["parcela_id"].isin(ids)].copy()

    # Estadística histórica previa a la fecha latest auditada.
    latest_by_id = outliers.set_index("parcela_id")["fecha_actual"].to_dict()
    obs_ids["fecha_actual_outlier"] = obs_ids["parcela_id"].map(latest_by_id)
    prev = obs_ids[obs_ids["fecha"] < obs_ids["fecha_actual_outlier"]].copy()
    hist = (
        prev.groupby("parcela_id")["riesgo_hidrico"]
        .agg(
            riesgo_hist_count="count",
            riesgo_hist_median_prev="median",
            riesgo_hist_mean_prev="mean",
            riesgo_hist_std_prev="std",
            riesgo_hist_min_prev="min",
            riesgo_hist_max_prev="max",
        )
        .reset_index()
    )
    recent_hist = calcular_historial_reciente(
        obs_ids,
        outliers,
        args.recent_window_days,
        args.weight_step_days,
    )

    current_cols = [
        "parcela_id",
        "fecha",
        "riesgo_hidrico",
        "riesgo_hidrico_lag1",
        "riesgo_hidrico_lag2",
        "riesgo_hidrico_delta_5d",
        "riesgo_hidrico_delta_10d",
        "ndmi_mean",
        "msi_mean",
        "ndwi_mean",
        "nbr_mean",
        "ndvi_mean",
        "ndmi_mean_rel_fecha",
        "msi_mean_rel_fecha",
        "ndwi_mean_rel_fecha",
        "nbr_mean_rel_fecha",
        "ndvi_mean_rel_fecha",
    ] + [col for col in COUNT_COLUMNS if col in obs_ids.columns]
    current_cols = [col for col in current_cols if col in obs_ids.columns]

    current = obs_ids[current_cols].copy()
    merged = outliers.merge(
        current,
        left_on=["parcela_id", "fecha_actual"],
        right_on=["parcela_id", "fecha"],
        how="left",
    ).merge(hist, on="parcela_id", how="left").merge(
        recent_hist,
        on="parcela_id",
        how="left",
    )

    count_cols_present = [col for col in COUNT_COLUMNS if col in merged.columns]
    if count_cols_present:
        merged["min_valid_pixels_hidricos"] = merged[count_cols_present].min(axis=1)
    else:
        merged["min_valid_pixels_hidricos"] = np.nan

    merged["direccion_outlier"] = np.where(
        merged["riesgo_actual_vs_neighbor_median"] > 0,
        "alto",
        "bajo",
    )

    soporte = merged.apply(
        lambda row: soporte_espectral(
            row,
            row["direccion_outlier"],
            args.support_rel_threshold,
        ),
        axis=1,
    )
    merged["soporte_indices_count"] = [item[0] for item in soporte]
    merged["soporte_indices"] = [item[1] for item in soporte]
    merged["persistencia_temporal"] = merged.apply(
        lambda row: estado_persistencia(
            row,
            row["direccion_outlier"],
            args.risk_high_threshold,
            args.risk_low_threshold,
        ),
        axis=1,
    )
    merged["diagnostico_outlier"] = merged.apply(
        lambda row: diagnosticar(row, args.min_valid_pixels_strong),
        axis=1,
    )
    merged["riesgo_vs_hist_median"] = (
        merged["riesgo_actual"] - merged["riesgo_hist_median_prev"]
    )
    merged["riesgo_vs_reciente_weighted_mean"] = (
        merged["riesgo_actual"] - merged["riesgo_reciente_weighted_mean"]
    )

    resumen = (
        merged.groupby(["cultivo", "direccion_outlier", "persistencia_temporal", "diagnostico_outlier"])
        .size()
        .reset_index(name="parcelas")
        .sort_values(["cultivo", "direccion_outlier", "parcelas"], ascending=[True, True, False])
    )
    return merged, resumen


def main() -> None:
    args = parse_args()
    detalle, resumen = auditar(args)

    output_detalle = Path(args.output_detalle)
    output_resumen = Path(args.output_resumen)
    output_detalle.parent.mkdir(parents=True, exist_ok=True)
    output_resumen.parent.mkdir(parents=True, exist_ok=True)
    detalle.to_csv(output_detalle, index=False)
    resumen.to_csv(output_resumen, index=False)

    print("=== Auditoria temporal de outliers espaciales ===")
    print("Outliers auditados:", len(detalle))
    print("\nPersistencia:")
    print(detalle["persistencia_temporal"].value_counts().to_string())
    print("\nDiagnostico:")
    print(detalle["diagnostico_outlier"].value_counts().to_string())
    print("\nPor cultivo/direccion/persistencia/diagnostico:")
    print(resumen.to_string(index=False))
    print("\nTop 15 outliers auditados:")
    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "direccion_outlier",
        "riesgo_actual",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "riesgo_hidrico_lag1",
        "riesgo_hidrico_lag2",
        "historial_reciente_count",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "soporte_indices_count",
        "min_valid_pixels_hidricos",
        "persistencia_temporal",
        "diagnostico_outlier",
    ]
    print(
        detalle.sort_values("abs_riesgo_actual_vs_neighbor_median", ascending=False)[cols]
        .head(15)
        .to_string(index=False)
    )
    print("\nDetalle:", output_detalle)
    print("Resumen:", output_resumen)


if __name__ == "__main__":
    main()
