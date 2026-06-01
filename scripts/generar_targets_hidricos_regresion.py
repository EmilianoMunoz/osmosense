import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning


INPUT_TEMPORAL = "data/dataset_temporal_hidrico.csv"
OUTPUT_TARGETS = "data/dataset_predictivo_hidrico_regresion.csv"
HORIZONS = [5, 10]
TARGET_CROPS = ["vid", "olivo"]

BASE_FEATURES = [
    "ndvi_mean", "ndmi_mean", "ndwi_mean", "msi_mean", "savi_mean", "ndre_mean",
    "gndvi_mean", "evi_mean", "bsi_mean", "nbr_mean", "mtci_mean", "ireci_mean",
    "b2_mean", "b3_mean", "b4_mean", "b5_mean", "b6_mean", "b7_mean",
    "b8_mean", "b11_mean", "b12_mean",
]

HYDRIC_FEATURES = ["ndmi_mean", "msi_mean", "ndwi_mean", "nbr_mean", "ndvi_mean"]
TARGETS = [
    "riesgo_hidrico_future",
    "ndmi_mean_future",
    "msi_mean_future",
    "ndwi_mean_future",
    "nbr_mean_future",
    "ndvi_mean_future",
]

warnings.filterwarnings("ignore", category=PerformanceWarning)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera pares X -> X+h para prediccion hidrica por regresion."
    )
    parser.add_argument("--input", default=INPUT_TEMPORAL)
    parser.add_argument("--output", default=OUTPUT_TARGETS)
    parser.add_argument("--horizons", nargs="+", type=int, default=HORIZONS)
    return parser.parse_args()


def robust_percentile(series: pd.Series, high_is_risk: bool) -> pd.Series:
    ranks = series.rank(pct=True, method="average")
    if high_is_risk:
        return ranks
    return 1.0 - ranks


def agregar_riesgo_hidrico(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    parts = []

    for _, group in df.groupby(["cultivo", "fecha"], sort=False):
        riesgo = (
            0.35 * robust_percentile(group["ndmi_mean"], high_is_risk=False)
            + 0.30 * robust_percentile(group["msi_mean"], high_is_risk=True)
            + 0.15 * robust_percentile(group["ndwi_mean"], high_is_risk=False)
            + 0.10 * robust_percentile(group["nbr_mean"], high_is_risk=False)
            + 0.10 * robust_percentile(group["ndvi_mean"], high_is_risk=False)
        )
        item = group.copy()
        item["riesgo_hidrico"] = (100 * riesgo).clip(0, 100)
        parts.append(item)

    return pd.concat(parts, ignore_index=True)


def agregar_features_temporales(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    day = df["day_of_year"].astype(float)
    df["doy_sin"] = np.sin(2 * np.pi * day / 365.25)
    df["doy_cos"] = np.cos(2 * np.pi * day / 365.25)
    df["month_sin"] = np.sin(2 * np.pi * df["month"].astype(float) / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"].astype(float) / 12)
    return df


def agregar_historial_parcela(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["parcela_id", "fecha"]).copy()
    cols = [c for c in BASE_FEATURES + ["riesgo_hidrico"] if c in df.columns]
    grouped = df.groupby("parcela_id", sort=False)

    for col in cols:
        df[f"{col}_lag1"] = grouped[col].shift(1)
        df[f"{col}_lag2"] = grouped[col].shift(2)
        df[f"{col}_lag3"] = grouped[col].shift(3)
        df[f"{col}_delta_5d"] = df[col] - df[f"{col}_lag1"]
        df[f"{col}_delta_10d"] = df[col] - df[f"{col}_lag2"]
        df[f"{col}_delta_15d"] = df[col] - df[f"{col}_lag3"]
        df[f"{col}_rolling3_mean"] = (
            grouped[col]
            .rolling(3, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        df[f"{col}_rolling3_std"] = (
            grouped[col]
            .rolling(3, min_periods=2)
            .std()
            .reset_index(level=0, drop=True)
        )

        expanding_mean = grouped[col].expanding(min_periods=2).mean().reset_index(level=0, drop=True)
        expanding_std = grouped[col].expanding(min_periods=3).std().reset_index(level=0, drop=True)
        df[f"{col}_hist_mean_prev"] = expanding_mean.groupby(df["parcela_id"]).shift(1)
        df[f"{col}_hist_std_prev"] = expanding_std.groupby(df["parcela_id"]).shift(1)
        df[f"{col}_anomalia_parcela"] = (
            (df[col] - df[f"{col}_hist_mean_prev"])
            / (df[f"{col}_hist_std_prev"].abs() + 1e-6)
        )

    return df


def agregar_contexto_relativo_fecha(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols = [c for c in HYDRIC_FEATURES + ["riesgo_hidrico"] if c in df.columns]

    for col in cols:
        grouped = df.groupby(["cultivo", "fecha"], sort=False)[col]
        median = grouped.transform("median")
        q75 = grouped.transform(lambda s: s.quantile(0.75))
        q25 = grouped.transform(lambda s: s.quantile(0.25))
        df[f"{col}_rel_fecha"] = (df[col] - median) / ((q75 - q25).abs() + 1e-6)

    return df


def preparar_observaciones(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["cultivo"].isin(TARGET_CROPS)].copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = agregar_riesgo_hidrico(df)
    df = agregar_features_temporales(df)
    df = agregar_historial_parcela(df)
    df = agregar_contexto_relativo_fecha(df)
    return df


def crear_pares(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    df = preparar_observaciones(df)
    future_cols = [
        "riesgo_hidrico",
        "ndmi_mean", "msi_mean", "ndwi_mean", "nbr_mean", "ndvi_mean",
    ]

    pairs = []
    for horizon in horizons:
        future = df[["parcela_id", "fecha"] + future_cols].copy()
        future["fecha"] = future["fecha"] - pd.to_timedelta(horizon, unit="D")
        future = future.rename(columns={col: f"{col}_future" for col in future_cols})

        merged = df.merge(future, on=["parcela_id", "fecha"], how="inner")
        merged["horizon_days"] = horizon
        pairs.append(merged)

    if not pairs:
        return pd.DataFrame()

    pairs = pd.concat(pairs, ignore_index=True)
    pairs["delta_riesgo_hidrico"] = pairs["riesgo_hidrico_future"] - pairs["riesgo_hidrico"]
    pairs["delta_ndmi"] = pairs["ndmi_mean_future"] - pairs["ndmi_mean"]
    pairs["delta_msi"] = pairs["msi_mean_future"] - pairs["msi_mean"]
    pairs["delta_ndwi"] = pairs["ndwi_mean_future"] - pairs["ndwi_mean"]
    pairs["delta_nbr"] = pairs["nbr_mean_future"] - pairs["nbr_mean"]
    pairs["delta_ndvi"] = pairs["ndvi_mean_future"] - pairs["ndvi_mean"]
    return pairs


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input)
    pairs = crear_pares(df, args.horizons)

    if pairs.empty:
        raise RuntimeError("No se generaron pares predictivos de regresion.")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.output, index=False)

    print("=== Dataset predictivo hidrico regresion ===")
    print("Entrada:", args.input)
    print("Salida:", args.output)
    print("Shape:", pairs.shape)
    print("Distribucion cultivo:", pairs["cultivo"].value_counts().to_dict())
    print("Distribucion horizonte:", pairs["horizon_days"].value_counts().to_dict())
    print("Targets:", TARGETS)
    print("Riesgo futuro:")
    print(pairs.groupby(["cultivo", "horizon_days"])["riesgo_hidrico_future"].describe())


if __name__ == "__main__":
    main()
