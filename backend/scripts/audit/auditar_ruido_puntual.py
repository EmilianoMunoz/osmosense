import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


INPUT_TEMPORAL_AUDIT = "backend/data/auditoria_outliers_temporales.csv"
INPUT_PARCELAS = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
OUTPUT_DETALLE = "backend/data/auditoria_ruido_puntual_detalle.csv"
OUTPUT_RESUMEN = "backend/data/auditoria_ruido_puntual_resumen.csv"
OUTPUT_GEOJSON = "backend/data/auditoria_ruido_puntual_detalle.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita casos diagnosticados como probable ruido o lectura puntual."
    )
    parser.add_argument("--input", default=INPUT_TEMPORAL_AUDIT)
    parser.add_argument("--parcelas", default=INPUT_PARCELAS)
    parser.add_argument("--output-detalle", default=OUTPUT_DETALLE)
    parser.add_argument("--output-resumen", default=OUTPUT_RESUMEN)
    parser.add_argument("--output-geojson", default=OUTPUT_GEOJSON)
    parser.add_argument(
        "--diagnostico",
        default="probable_ruido_o_lectura_puntual",
        help="Diagnostico a auditar desde la auditoria temporal.",
    )
    return parser.parse_args()


def cargar_ruido(path: str, diagnostico: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "parcela_id",
        "cultivo",
        "ranking_global",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "abs_riesgo_actual_vs_neighbor_median",
        "neighbor_count",
        "nearest_neighbor_distance_m",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "historial_reciente_count",
        "min_valid_pixels_hidricos",
        "soporte_indices_count",
        "persistencia_temporal",
        "diagnostico_outlier",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise RuntimeError(f"Columnas faltantes en {path}: {missing}")

    ruido = df[df["diagnostico_outlier"] == diagnostico].copy()
    ruido["parcela_id"] = ruido["parcela_id"].astype(int)
    return ruido


def cargar_geometrias(path: str) -> gpd.GeoDataFrame:
    parcelas = gpd.read_file(path)
    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")
    elif parcelas.crs.to_epsg() != 4326:
        parcelas = parcelas.to_crs("EPSG:4326")

    parcelas = parcelas.rename(columns={"fid": "parcela_id"})
    parcelas["parcela_id"] = parcelas["parcela_id"].astype(int)
    keep = ["parcela_id", "geometry"]
    if "tipo_culti" in parcelas.columns:
        keep.insert(1, "tipo_culti")
    return parcelas[keep].copy()


def clasificar_motivo(row: pd.Series) -> str:
    soporte = row["soporte_indices_count"]
    pixels = row["min_valid_pixels_hidricos"]
    delta_hist = abs(row["riesgo_vs_reciente_weighted_mean"])
    delta_vecinos = row["abs_riesgo_actual_vs_neighbor_median"]

    if soporte == 0 and delta_hist < 8:
        return "sin_soporte_espectral_y_sin_salto_temporal"
    if soporte <= 1 and pixels < 100:
        return "bajo_soporte_y_pocos_pixeles"
    if soporte <= 1 and delta_vecinos >= 35 and delta_hist < 10:
        return "salto_vecinal_sin_confirmacion_temporal"
    if delta_hist >= 15:
        return "salto_temporal_puntual_relevante"
    return "lectura_puntual_indeterminada"


def calcular_severidad(row: pd.Series) -> float:
    vecino = min(row["abs_riesgo_actual_vs_neighbor_median"] / 60, 1.0)
    temporal = min(abs(row["riesgo_vs_reciente_weighted_mean"]) / 35, 1.0)
    pixels_penalty = 1.0 - min(row["min_valid_pixels_hidricos"] / 200, 1.0)
    soporte_penalty = 1.0 - min(row["soporte_indices_count"] / 3, 1.0)

    score = (
        0.35 * vecino
        + 0.30 * temporal
        + 0.20 * soporte_penalty
        + 0.15 * pixels_penalty
    )
    return float(round(100 * score, 2))


def recomendar_accion(row: pd.Series) -> str:
    if row["motivo_ruido"] in {
        "sin_soporte_espectral_y_sin_salto_temporal",
        "salto_vecinal_sin_confirmacion_temporal",
    }:
        return "bajar_confianza_no_suavizar_score"
    if row["motivo_ruido"] == "bajo_soporte_y_pocos_pixeles":
        return "bajar_confianza_y_revisar_geometria"
    if row["motivo_ruido"] == "salto_temporal_puntual_relevante":
        return "revisar_visual_antes_de_suavizar"
    return "mantener_alerta"


def auditar(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, gpd.GeoDataFrame]:
    ruido = cargar_ruido(args.input, args.diagnostico)
    if ruido.empty:
        raise RuntimeError(f"No hay casos con diagnostico {args.diagnostico}.")

    ruido["motivo_ruido"] = ruido.apply(clasificar_motivo, axis=1)
    ruido["severidad_ruido"] = ruido.apply(calcular_severidad, axis=1)
    ruido["accion_recomendada"] = ruido.apply(recomendar_accion, axis=1)

    columns = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "abs_riesgo_actual_vs_neighbor_median",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "historial_reciente_count",
        "neighbor_count",
        "nearest_neighbor_distance_m",
        "min_valid_pixels_hidricos",
        "soporte_indices_count",
        "soporte_indices",
        "persistencia_temporal",
        "diagnostico_outlier",
        "motivo_ruido",
        "severidad_ruido",
        "accion_recomendada",
    ]
    columns = [col for col in columns if col in ruido.columns]
    detalle = ruido[columns].sort_values("severidad_ruido", ascending=False).copy()

    resumen = (
        detalle.groupby(["motivo_ruido", "accion_recomendada"])
        .agg(
            parcelas=("parcela_id", "count"),
            severidad_media=("severidad_ruido", "mean"),
            delta_vecinal_media=("abs_riesgo_actual_vs_neighbor_median", "mean"),
            delta_temporal_media=("riesgo_vs_reciente_weighted_mean", "mean"),
            pixeles_min_mediana=("min_valid_pixels_hidricos", "median"),
            soporte_indices_media=("soporte_indices_count", "mean"),
        )
        .reset_index()
        .sort_values("parcelas", ascending=False)
    )

    for col in [
        "severidad_media",
        "delta_vecinal_media",
        "delta_temporal_media",
        "pixeles_min_mediana",
        "soporte_indices_media",
    ]:
        resumen[col] = resumen[col].round(2)

    geoms = cargar_geometrias(args.parcelas)
    geo = geoms.merge(detalle, on="parcela_id", how="inner")
    geo = gpd.GeoDataFrame(geo, geometry="geometry", crs="EPSG:4326")
    return detalle, resumen, geo


def main() -> None:
    args = parse_args()
    detalle, resumen, geo = auditar(args)

    output_detalle = Path(args.output_detalle)
    output_resumen = Path(args.output_resumen)
    output_geojson = Path(args.output_geojson)
    output_detalle.parent.mkdir(parents=True, exist_ok=True)
    output_resumen.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    detalle.to_csv(output_detalle, index=False)
    resumen.to_csv(output_resumen, index=False)
    geo.to_file(output_geojson, driver="GeoJSON")

    print("=== Auditoria ruido puntual ===")
    print("Entrada:", args.input)
    print("Casos:", len(detalle))
    print("\nPor motivo:")
    print(detalle["motivo_ruido"].value_counts().to_string())
    print("\nAcciones:")
    print(detalle["accion_recomendada"].value_counts().to_string())
    print("\nResumen:")
    print(resumen.to_string(index=False))
    print("\nTop 15 severidad:")
    top_cols = [
        "ranking_global",
        "parcela_id",
        "prioridad",
        "riesgo_actual",
        "neighbor_riesgo_actual_median",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "min_valid_pixels_hidricos",
        "soporte_indices_count",
        "motivo_ruido",
        "severidad_ruido",
        "accion_recomendada",
    ]
    print(detalle[top_cols].head(15).to_string(index=False))
    print("\nDetalle:", output_detalle)
    print("Resumen:", output_resumen)
    print("GeoJSON:", output_geojson)


if __name__ == "__main__":
    main()
