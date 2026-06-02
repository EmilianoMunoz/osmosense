import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.pipeline.generar_targets_hidricos_regresion import preparar_observaciones


INPUT_TEMPORAL = "backend/data/dataset_temporal_hidrico.csv"
OUTPUT_RANKING = "backend/data/ranking_hidrico.csv"
MODEL_DIR = "backend/models/hidrico_regresion"
RANKING_CONFIG = "backend/models/ranking_hidrico_config.json"
PARCELAS_GEOJSON = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
TARGET_CROPS = ["vid", "olivo"]
HORIZONS = [5, 10]
DEFAULT_RANKING_CONFIG = {
    "weights": {
        "riesgo_pred_10d": 0.55,
        "riesgo_pred_5d": 0.25,
        "delta_10d_pos": 0.15,
        "delta_5d_pos": 0.00,
        "riesgo_actual": 0.05,
    },
    "thresholds": {
        "critica": 80.0,
        "alta": 65.0,
        "media": 45.0,
    },
}
PRIORITY_MIN_SLOPE_5D = {
    "baja": 0.5,
    "media": 1.5,
    "alta": 3.0,
    "critica": 4.0,
}
CROP_FACTOR = {
    "vid": 1.15,
    "olivo": 0.75,
}
SEASONAL_FACTOR = {
    "vid": {
        12: 1.30,
        1: 1.30,
        2: 1.30,
        9: 1.15,
        10: 1.15,
        11: 1.15,
        3: 0.85,
        4: 0.85,
        5: 0.85,
        6: 0.45,
        7: 0.45,
        8: 0.45,
    },
    "olivo": {
        12: 1.10,
        1: 1.10,
        2: 1.10,
        9: 1.00,
        10: 1.00,
        11: 1.00,
        3: 0.80,
        4: 0.80,
        5: 0.80,
        6: 0.65,
        7: 0.65,
        8: 0.65,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera ranking operativo de riesgo hidrico por parcela."
    )
    parser.add_argument("--input", default=INPUT_TEMPORAL)
    parser.add_argument("--output", default=OUTPUT_RANKING)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument(
        "--ranking-config",
        default=RANKING_CONFIG,
        help="JSON con pesos y umbrales calibrados para prioridad.",
    )
    parser.add_argument(
        "--fecha",
        default=None,
        help="Fecha a rankear en formato YYYY-MM-DD. Si se omite usa la ultima disponible.",
    )
    parser.add_argument(
        "--parcelas",
        default=PARCELAS_GEOJSON,
        help="GeoJSON con el universo oficial de parcelas a rankear.",
    )
    parser.add_argument(
        "--max-reading-age-days",
        type=int,
        default=15,
        help=(
            "Antiguedad maxima permitida para usar la ultima observacion valida "
            "por parcela cuando no existe lectura exacta en la fecha objetivo."
        ),
    )
    return parser.parse_args()


def cargar_config(path: str | Path | None = RANKING_CONFIG) -> dict:
    config = {
        "weights": DEFAULT_RANKING_CONFIG["weights"].copy(),
        "thresholds": DEFAULT_RANKING_CONFIG["thresholds"].copy(),
    }
    if path is None:
        return config

    config_path = Path(path)
    if not config_path.exists():
        return config

    user_config = json.loads(config_path.read_text(encoding="utf-8"))
    config["weights"].update(user_config.get("weights", {}))
    config["thresholds"].update(user_config.get("thresholds", {}))
    return config


def cargar_modelo(model_dir: Path, cultivo: str, horizon: int) -> dict:
    path = model_dir / f"regresor_{cultivo}_{horizon}d_riesgo_hidrico_future_temporal.pkl"
    if not path.exists():
        raise FileNotFoundError(f"No existe el modelo requerido: {path}")
    return joblib.load(path)


def cargar_parcelas_objetivo(path: str | Path | None = PARCELAS_GEOJSON) -> set[int] | None:
    if path is None:
        return None

    parcelas_path = Path(path)
    if not parcelas_path.exists():
        return None

    import geopandas as gpd

    parcelas = gpd.read_file(parcelas_path)
    id_col = "fid" if "fid" in parcelas.columns else "parcela_id"
    if id_col not in parcelas.columns:
        raise ValueError(f"No existe columna fid/parcela_id en {parcelas_path}")

    if "cultivo" in parcelas.columns:
        parcelas = parcelas[parcelas["cultivo"].isin(TARGET_CROPS)].copy()

    return set(parcelas[id_col].astype(int).tolist())


def filtrar_parcelas_objetivo(
    df: pd.DataFrame,
    parcelas_path: str | Path | None = PARCELAS_GEOJSON,
) -> pd.DataFrame:
    ids = cargar_parcelas_objetivo(parcelas_path)
    if ids is None:
        return df

    filtrado = df[df["parcela_id"].astype(int).isin(ids)].copy()
    if filtrado.empty:
        raise ValueError(
            "El filtro de parcelas objetivo dejo el dataset temporal sin filas. "
            f"Revisar {parcelas_path}."
        )
    return filtrado


def seleccionar_fecha(
    df: pd.DataFrame,
    fecha: str | None,
    max_reading_age_days: int = 15,
) -> tuple[pd.DataFrame, str]:
    if fecha is None:
        fecha_objetivo = df["fecha"].max()
    else:
        fecha_objetivo = pd.Timestamp(fecha)

    fecha_minima = fecha_objetivo - pd.Timedelta(days=max_reading_age_days)
    candidates = df[(df["fecha"] <= fecha_objetivo) & (df["fecha"] >= fecha_minima)].copy()
    latest = (
        candidates.sort_values(["parcela_id", "fecha"])
        .drop_duplicates("parcela_id", keep="last")
        .copy()
    )
    if latest.empty:
        disponibles = df["fecha"].dt.strftime("%Y-%m-%d").sort_values().unique()
        raise ValueError(
            f"No hay observaciones entre {fecha_minima.date()} y {fecha_objetivo.date()}. "
            f"Rango disponible: {disponibles[0]} a {disponibles[-1]}"
        )

    latest["fecha_lectura"] = latest["fecha"].dt.strftime("%Y-%m-%d")
    latest["dias_desde_lectura"] = (fecha_objetivo - latest["fecha"]).dt.days.astype(int)
    return latest, fecha_objetivo.strftime("%Y-%m-%d")


def predecir_horizonte(latest: pd.DataFrame, model_dir: Path, horizon: int) -> pd.Series:
    pred = pd.Series(index=latest.index, dtype=float)

    for cultivo in TARGET_CROPS:
        mask = latest["cultivo"] == cultivo
        if not mask.any():
            continue

        data = cargar_modelo(model_dir, cultivo, horizon)
        model = data["model"]
        features = data["features"]

        x = latest.loc[mask].copy()
        x["horizon_days"] = horizon
        x_features = (
            x.select_dtypes(include=[np.number])
            .reindex(columns=features, fill_value=0)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0)
        )
        pred.loc[mask] = model.predict(x_features)

    return pred.clip(lower=0, upper=100)


def asignar_prioridad(row: pd.Series, thresholds: dict) -> str:
    score = row["prioridad_score"]

    if score >= thresholds["critica"]:
        return "critica"
    if score >= thresholds["alta"]:
        return "alta"
    if score >= thresholds["media"]:
        return "media"
    return "baja"


def score_prioridad(df: pd.DataFrame, weights: dict) -> pd.Series:
    return (
        weights["riesgo_pred_10d"] * df["riesgo_pred_10d"]
        + weights["riesgo_pred_5d"] * df["riesgo_pred_5d"]
        + weights["delta_10d_pos"] * df["delta_10d"].clip(lower=0)
        + weights["delta_5d_pos"] * df["delta_5d"].clip(lower=0)
        + weights["riesgo_actual"] * df["riesgo_hidrico"]
    )


def seasonal_factor(cultivo: str, month: int) -> float:
    return SEASONAL_FACTOR.get(cultivo, {}).get(int(month), 1.0)


def agregar_proyeccion_operativa(ranking: pd.DataFrame) -> pd.DataFrame:
    ranking = ranking.copy()
    lag1 = ranking["riesgo_hidrico_lag1"]
    lag2 = ranking["riesgo_hidrico_lag2"]
    actual = ranking["riesgo_actual"]

    tendencia_5d = actual - lag1
    tendencia_10d_prom = (actual - lag2) / 2
    tendencia = (0.7 * tendencia_5d + 0.3 * tendencia_10d_prom).fillna(tendencia_5d)
    tendencia = tendencia.fillna(0).clip(lower=0)

    min_slope = ranking["prioridad"].map(PRIORITY_MIN_SLOPE_5D).fillna(1.0)
    crop_factor = ranking["cultivo"].map(CROP_FACTOR).fillna(1.0)
    seasonal = ranking.apply(
        lambda row: seasonal_factor(row["cultivo"], row["fecha"].month),
        axis=1,
    )
    pendiente = np.maximum(tendencia, min_slope) * crop_factor * seasonal

    ranking["tendencia_reciente_5d"] = tendencia
    ranking["factor_estacional"] = seasonal
    ranking["pendiente_operativa_5d"] = pendiente.clip(lower=0)
    ranking["riesgo_operativo_5d"] = np.maximum.reduce(
        [
            actual,
            ranking["riesgo_pred_5d"],
            actual + ranking["pendiente_operativa_5d"],
        ]
    ).clip(0, 100)
    ranking["riesgo_operativo_10d"] = np.maximum.reduce(
        [
            ranking["riesgo_operativo_5d"],
            ranking["riesgo_pred_10d"],
            ranking["riesgo_operativo_5d"] + ranking["pendiente_operativa_5d"],
        ]
    ).clip(0, 100)
    ranking["delta_operativo_5d"] = ranking["riesgo_operativo_5d"] - actual
    ranking["delta_operativo_10d"] = ranking["riesgo_operativo_10d"] - actual
    return ranking


def generar_ranking(
    df_temporal: pd.DataFrame,
    model_dir: Path,
    fecha: str | None,
    ranking_config: str | Path | None = RANKING_CONFIG,
    parcelas_path: str | Path | None = PARCELAS_GEOJSON,
    max_reading_age_days: int = 15,
) -> pd.DataFrame:
    config = cargar_config(ranking_config)
    df_temporal = filtrar_parcelas_objetivo(df_temporal, parcelas_path)
    df = preparar_observaciones(df_temporal)
    latest, fecha_usada = seleccionar_fecha(df, fecha, max_reading_age_days)

    ranking = latest[
        [
            "parcela_id",
            "cultivo",
            "area_m2",
            "fecha",
            "fecha_lectura",
            "dias_desde_lectura",
            "riesgo_hidrico",
            "riesgo_hidrico_lag1",
            "riesgo_hidrico_lag2",
            "ndmi_mean",
            "msi_mean",
            "ndwi_mean",
            "nbr_mean",
            "ndvi_mean",
        ]
    ].copy()

    ranking["fecha_actual"] = fecha_usada
    ranking["riesgo_actual"] = ranking["riesgo_hidrico"]

    for horizon in HORIZONS:
        ranking[f"riesgo_pred_{horizon}d"] = predecir_horizonte(latest, model_dir, horizon)
        ranking[f"delta_{horizon}d"] = (
            ranking[f"riesgo_pred_{horizon}d"] - ranking["riesgo_actual"]
        )

    ranking["prioridad_score"] = score_prioridad(ranking, config["weights"])
    ranking["prioridad"] = ranking.apply(
        lambda row: asignar_prioridad(row, config["thresholds"]),
        axis=1,
    )
    ranking = agregar_proyeccion_operativa(ranking)
    ranking["ranking_global"] = (
        ranking["prioridad_score"].rank(method="first", ascending=False).astype(int)
    )
    ranking["ranking_por_cultivo"] = (
        ranking.groupby("cultivo")["prioridad_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    output_cols = [
        "ranking_global",
        "ranking_por_cultivo",
        "parcela_id",
        "cultivo",
        "fecha_actual",
        "fecha_lectura",
        "dias_desde_lectura",
        "area_m2",
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
    ranking = ranking[output_cols].sort_values("ranking_global").reset_index(drop=True)
    return ranking


def main() -> None:
    args = parse_args()
    df_temporal = pd.read_csv(args.input)
    model_dir = Path(args.model_dir)
    ranking = generar_ranking(
        df_temporal,
        model_dir,
        args.fecha,
        args.ranking_config,
        args.parcelas,
        args.max_reading_age_days,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(output, index=False)

    print("=== Ranking hidrico ===")
    print("Entrada:", args.input)
    print("Salida:", output)
    print("Fecha:", ranking["fecha_actual"].iloc[0])
    print("Lecturas por antiguedad:", ranking["dias_desde_lectura"].value_counts().sort_index().to_dict())
    print("Parcelas:", len(ranking))
    print("Distribucion cultivo:", ranking["cultivo"].value_counts().to_dict())
    print("Distribucion prioridad:", ranking["prioridad"].value_counts().to_dict())
    print("\nTop 10:")
    print(
        ranking[
            [
                "ranking_global",
                "parcela_id",
                "cultivo",
                "prioridad",
                "riesgo_actual",
                "riesgo_pred_5d",
                "riesgo_pred_10d",
                "riesgo_operativo_5d",
                "riesgo_operativo_10d",
                "delta_10d",
            ]
        ].head(10).to_string(index=False)
    )


if __name__ == "__main__":
    main()
