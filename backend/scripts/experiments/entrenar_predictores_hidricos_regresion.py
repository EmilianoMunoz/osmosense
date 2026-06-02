import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor


INPUT_PATH = "backend/data/dataset_predictivo_hidrico_regresion.csv"
OUTPUT_DIR = Path("backend/models/hidrico_regresion")
RANDOM_STATE = 42
TARGET_CROPS = ["vid", "olivo"]
TARGETS = [
    "riesgo_hidrico_future",
    "ndmi_mean_future",
    "msi_mean_future",
    "ndwi_mean_future",
    "nbr_mean_future",
    "ndvi_mean_future",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Entrena predictores hidricos de regresion por cultivo y horizonte."
    )
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--targets", nargs="+", default=TARGETS)
    parser.add_argument("--split", choices=["temporal", "group"], default="temporal")
    parser.add_argument("--test-size", type=float, default=0.25)
    return parser.parse_args()


def feature_columns(df: pd.DataFrame, targets: list[str]) -> list[str]:
    excluded = {
        "parcela_id", "cultivo", "fecha", "fecha_fin",
        "year", "month", "day_of_year",
    }
    excluded.update(targets)
    excluded_prefixes = ("delta_", "scl_")
    excluded_suffixes = ("_future",)

    features = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if col in excluded:
            continue
        if col.startswith(excluded_prefixes) or col.endswith(excluded_suffixes):
            continue
        features.append(col)

    return features


def crear_modelo() -> XGBRegressor:
    return XGBRegressor(
        objective="reg:squarederror",
        n_estimators=450,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.9,
        colsample_bytree=0.85,
        gamma=0.05,
        min_child_weight=2,
        reg_lambda=1.5,
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )


def split_por_parcela(df: pd.DataFrame, test_size: float) -> tuple[np.ndarray, np.ndarray]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=RANDOM_STATE)
    groups = df["parcela_id"].astype(str).values
    return next(splitter.split(df, groups=groups))


def split_temporal(df: pd.DataFrame, test_size: float) -> tuple[np.ndarray, np.ndarray]:
    fechas = np.array(sorted(pd.to_datetime(df["fecha"]).unique()))
    cutoff_idx = max(1, int(len(fechas) * (1 - test_size)))
    cutoff = fechas[cutoff_idx]
    fechas_df = pd.to_datetime(df["fecha"]).values
    train_idx = np.flatnonzero(fechas_df < cutoff)
    test_idx = np.flatnonzero(fechas_df >= cutoff)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError("Split temporal vacio; revisar rango de fechas.")

    return train_idx, test_idx


def top_decile_overlap(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = max(1, int(np.ceil(len(y_true) * 0.10)))
    true_top = set(np.argsort(y_true)[-n:])
    pred_top = set(np.argsort(y_pred)[-n:])
    return len(true_top & pred_top) / n


def evaluar(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    spearman = spearmanr(y_true, y_pred, nan_policy="omit").correlation
    if not np.isfinite(spearman):
        spearman = 0.0

    return {
        "mae": mean_absolute_error(y_true, y_pred),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": r2_score(y_true, y_pred),
        "spearman": float(spearman),
        "top10_overlap": top_decile_overlap(y_true, y_pred),
    }


def entrenar_un_target(
    subset: pd.DataFrame,
    features: list[str],
    target: str,
    cultivo: str,
    horizon: int,
    split: str,
    test_size: float,
    output_dir: Path,
    source_dataset: str,
) -> dict:
    if split == "group":
        train_idx, test_idx = split_por_parcela(subset, test_size)
    else:
        train_idx, test_idx = split_temporal(subset, test_size)

    train = subset.iloc[train_idx].copy()
    test = subset.iloc[test_idx].copy()

    model = crear_modelo()
    model.fit(train[features], train[target])
    pred = model.predict(test[features])
    metrics = evaluar(test[target].to_numpy(), pred)

    model_path = output_dir / f"regresor_{cultivo}_{int(horizon)}d_{target}_{split}.pkl"
    joblib.dump(
        {
            "model": model,
            "features": features,
            "cultivo": cultivo,
            "horizon_days": int(horizon),
            "target": target,
            "split": split,
            "source_dataset": source_dataset,
            "notes": (
                "Regresion X -> X+h para predecir valor futuro continuo. "
                "El ranking operativo debe priorizar riesgo_hidrico_future "
                "y el deterioro esperado."
            ),
        },
        model_path,
    )

    return {
        "cultivo": cultivo,
        "horizon_days": int(horizon),
        "target": target,
        "split": split,
        "n_train": len(train),
        "n_test": len(test),
        "train_fecha_min": str(train["fecha"].min()),
        "train_fecha_max": str(train["fecha"].max()),
        "test_fecha_min": str(test["fecha"].min()),
        "test_fecha_max": str(test["fecha"].max()),
        "model_path": str(model_path),
        **metrics,
    }


def entrenar(
    df: pd.DataFrame,
    targets: list[str],
    split: str,
    test_size: float,
    output_dir: Path,
    source_dataset: str,
) -> pd.DataFrame:
    results = []

    for cultivo in TARGET_CROPS:
        for horizon in sorted(df["horizon_days"].unique()):
            subset = df[(df["cultivo"] == cultivo) & (df["horizon_days"] == horizon)].copy()
            features = feature_columns(subset, targets)
            subset[features] = subset[features].replace([np.inf, -np.inf], np.nan).fillna(0)

            for target in targets:
                if target not in subset.columns:
                    continue

                result = entrenar_un_target(
                    subset,
                    features,
                    target,
                    cultivo,
                    int(horizon),
                    split,
                    test_size,
                    output_dir,
                    source_dataset,
                )
                results.append(result)
                print(
                    f"{cultivo:5s} h={int(horizon):2d}d {target:22s} "
                    f"mae={result['mae']:.4f} rmse={result['rmse']:.4f} "
                    f"r2={result['r2']:.3f} rho={result['spearman']:.3f} "
                    f"top10={result['top10_overlap']:.3f}"
                )

    return pd.DataFrame(results)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.input)
    print("=== Entrenamiento predictores hidricos regresion ===\n")
    print(f"Input: {args.input}")
    print(f"Split: {args.split}")
    print(f"Targets: {args.targets}\n")

    summary = entrenar(df, args.targets, args.split, args.test_size, output_dir, args.input)
    summary_path = output_dir / f"metricas_regresion_{args.split}.csv"
    summary.to_csv(summary_path, index=False)
    print(f"\nMetricas guardadas en {summary_path}")


if __name__ == "__main__":
    main()
