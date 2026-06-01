import argparse
from pathlib import Path

import joblib
import pandas as pd


MODEL_DIR = "models/hidrico_regresion"
OUTPUT_DETAIL = "data/importancia_predictores_hidricos.csv"
OUTPUT_GROUPS = "data/importancia_predictores_hidricos_grupos.csv"
TARGET = "riesgo_hidrico_future"
SPLIT = "temporal"
TARGET_CROPS = ["vid", "olivo"]
HORIZONS = [5, 10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae importancia de features de los predictores hidricos operativos."
    )
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--output-detail", default=OUTPUT_DETAIL)
    parser.add_argument("--output-groups", default=OUTPUT_GROUPS)
    parser.add_argument("--target", default=TARGET)
    parser.add_argument("--split", default=SPLIT)
    parser.add_argument("--top-n", type=int, default=20)
    return parser.parse_args()


def model_path(model_dir: Path, cultivo: str, horizon: int, target: str, split: str) -> Path:
    return model_dir / f"regresor_{cultivo}_{horizon}d_{target}_{split}.pkl"


def feature_group(feature: str) -> str:
    if feature == "horizon_days":
        return "horizonte"
    if feature.endswith("_anomalia_parcela"):
        return "anomalia_parcela"
    if feature.endswith("_rel_fecha"):
        return "contexto_relativo_fecha"
    if "_rolling3_" in feature:
        return "rolling_3_observaciones"
    if feature.endswith("_hist_mean_prev") or feature.endswith("_hist_std_prev"):
        return "historial_parcela"
    if feature.endswith("_delta_5d") or feature.endswith("_delta_10d") or feature.endswith("_delta_15d"):
        return "tendencia_reciente"
    if feature.endswith("_lag1") or feature.endswith("_lag2") or feature.endswith("_lag3"):
        return "lags"
    if feature in {"doy_sin", "doy_cos", "month_sin", "month_cos"}:
        return "estacionalidad"
    if feature == "riesgo_hidrico":
        return "estado_actual"
    if feature.endswith("_mean"):
        return "estado_actual"
    return "otros"


def base_variable(feature: str) -> str:
    suffixes = [
        "_anomalia_parcela",
        "_rel_fecha",
        "_rolling3_mean",
        "_rolling3_std",
        "_hist_mean_prev",
        "_hist_std_prev",
        "_delta_5d",
        "_delta_10d",
        "_delta_15d",
        "_lag1",
        "_lag2",
        "_lag3",
    ]
    for suffix in suffixes:
        if feature.endswith(suffix):
            return feature.removesuffix(suffix)
    return feature


def extraer_importancias(args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    model_dir = Path(args.model_dir)

    for cultivo in TARGET_CROPS:
        for horizon in HORIZONS:
            path = model_path(model_dir, cultivo, horizon, args.target, args.split)
            if not path.exists():
                raise FileNotFoundError(f"No existe el modelo requerido: {path}")

            data = joblib.load(path)
            model = data["model"]
            features = data["features"]
            importances = model.feature_importances_

            total = float(importances.sum())
            if total <= 0:
                total = 1.0

            for rank, (feature, importance) in enumerate(
                sorted(zip(features, importances), key=lambda item: item[1], reverse=True),
                start=1,
            ):
                rows.append(
                    {
                        "cultivo": cultivo,
                        "horizon_days": horizon,
                        "target": args.target,
                        "split": args.split,
                        "rank": rank,
                        "feature": feature,
                        "base_variable": base_variable(feature),
                        "feature_group": feature_group(feature),
                        "importance": float(importance),
                        "importance_pct": float(importance / total),
                        "model_path": str(path),
                    }
                )

    detail = pd.DataFrame(rows)
    groups = (
        detail.groupby(["cultivo", "horizon_days", "feature_group"], as_index=False)
        .agg(
            importance=("importance", "sum"),
            importance_pct=("importance_pct", "sum"),
            top_feature=("feature", "first"),
        )
        .sort_values(["cultivo", "horizon_days", "importance_pct"], ascending=[True, True, False])
    )
    return detail, groups


def main() -> None:
    args = parse_args()
    detail, groups = extraer_importancias(args)

    output_detail = Path(args.output_detail)
    output_groups = Path(args.output_groups)
    output_detail.parent.mkdir(parents=True, exist_ok=True)
    output_groups.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(output_detail, index=False)
    groups.to_csv(output_groups, index=False)

    print("=== Importancia predictores hidricos ===")
    print("Detalle:", output_detail)
    print("Grupos:", output_groups)

    for (cultivo, horizon), subset in detail.groupby(["cultivo", "horizon_days"], sort=True):
        print(f"\n{cultivo} {horizon}d - top {args.top_n}")
        cols = ["rank", "feature", "feature_group", "importance_pct"]
        print(subset.head(args.top_n)[cols].to_string(index=False))

    print("\n=== Importancia por grupo ===")
    print(
        groups.assign(importance_pct=groups["importance_pct"].round(4))
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
