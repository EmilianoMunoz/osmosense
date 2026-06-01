import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


INPUT_DETAIL = "data/validacion_ranking_hidrico_multifecha_2024.csv"
OUTPUT_CONFIG = "models/ranking_hidrico_config.json"
OUTPUT_RESULTS = "data/optimizacion_ranking_hidrico.csv"
SCORE_COLUMNS = [
    "riesgo_pred_10d",
    "riesgo_pred_5d",
    "delta_10d_pos",
    "delta_5d_pos",
    "riesgo_actual",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimiza pesos y umbrales del ranking hidrico con validacion historica."
    )
    parser.add_argument("--input-detail", default=INPUT_DETAIL)
    parser.add_argument("--output-config", default=OUTPUT_CONFIG)
    parser.add_argument("--output-results", default=OUTPUT_RESULTS)
    parser.add_argument("--step", type=float, default=0.05)
    parser.add_argument("--min-n", type=int, default=50)
    parser.add_argument("--top-results", type=int, default=20)
    return parser.parse_args()


def top_overlap(y_true: pd.Series, y_score: pd.Series, frac: float) -> float:
    n = max(1, int(np.ceil(len(y_true) * frac)))
    true_top = set(y_true.sort_values(ascending=False).head(n).index)
    pred_top = set(y_score.sort_values(ascending=False).head(n).index)
    return len(true_top & pred_top) / n


def spearman_safe(y_true: pd.Series, y_score: pd.Series) -> float:
    value = spearmanr(y_true, y_score, nan_policy="omit").correlation
    if not np.isfinite(value):
        return 0.0
    return float(value)


def weight_grid(step: float) -> list[dict[str, float]]:
    units = int(round(1 / step))
    weights = []
    for values in itertools.product(range(units + 1), repeat=len(SCORE_COLUMNS)):
        if sum(values) != units:
            continue
        item = {col: value / units for col, value in zip(SCORE_COLUMNS, values)}
        if item["riesgo_pred_10d"] < item["riesgo_pred_5d"]:
            continue
        if item["riesgo_pred_10d"] == 0:
            continue
        weights.append(item)
    return weights


def score_with_weights(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    for col, weight in weights.items():
        score = score + weight * df[col]
    return score


def evaluar_pesos(df: pd.DataFrame, weights: dict[str, float], min_n: int) -> dict:
    metrics = []
    for fecha, group in df.groupby("fecha_validacion"):
        data = group.dropna(subset=["riesgo_obs_5d", "riesgo_obs_10d"]).copy()
        if len(data) < min_n:
            continue
        score = score_with_weights(data, weights)
        metrics.append(
            {
                "fecha": fecha,
                "n": len(data),
                "spearman_5d": spearman_safe(data["riesgo_obs_5d"], score),
                "spearman_10d": spearman_safe(data["riesgo_obs_10d"], score),
                "top10_5d": top_overlap(data["riesgo_obs_5d"], score, 0.10),
                "top10_10d": top_overlap(data["riesgo_obs_10d"], score, 0.10),
            }
        )

    if not metrics:
        raise RuntimeError(f"No hay fechas con al menos {min_n} observaciones validas.")

    metric_df = pd.DataFrame(metrics)
    result = {
        "fechas": int(metric_df["fecha"].nunique()),
        "n_promedio": float(metric_df["n"].mean()),
        "spearman_5d": float(metric_df["spearman_5d"].mean()),
        "spearman_10d": float(metric_df["spearman_10d"].mean()),
        "top10_5d": float(metric_df["top10_5d"].mean()),
        "top10_10d": float(metric_df["top10_10d"].mean()),
    }
    result["objective"] = (
        0.50 * result["top10_10d"]
        + 0.25 * result["spearman_10d"]
        + 0.15 * result["top10_5d"]
        + 0.10 * result["spearman_5d"]
    )
    result.update(weights)
    return result


def f1_score(y_true: pd.Series, y_pred: pd.Series) -> float:
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def observado_top_por_fecha(df: pd.DataFrame, obs_col: str, frac: float) -> pd.Series:
    labels = pd.Series(False, index=df.index)
    for _, group in df.groupby("fecha_validacion"):
        data = group.dropna(subset=[obs_col])
        n = max(1, int(np.ceil(len(data) * frac)))
        labels.loc[data[obs_col].sort_values(ascending=False).head(n).index] = True
    return labels


def calibrar_umbrales(df: pd.DataFrame, score: pd.Series) -> dict:
    data = df.dropna(subset=["riesgo_obs_10d"]).copy()
    score = score.loc[data.index]

    targets = {
        "critica": observado_top_por_fecha(data, "riesgo_obs_10d", 0.10),
        "alta": observado_top_por_fecha(data, "riesgo_obs_10d", 0.25),
        "media": observado_top_por_fecha(data, "riesgo_obs_10d", 0.50),
    }

    candidates = np.arange(30, 91, 2.5)
    best = None
    for critica in candidates:
        for alta in candidates:
            if alta >= critica:
                continue
            for media in candidates:
                if media >= alta:
                    continue
                pred = {
                    "critica": score >= critica,
                    "alta": score >= alta,
                    "media": score >= media,
                }
                f1_critica = f1_score(targets["critica"], pred["critica"])
                f1_alta = f1_score(targets["alta"], pred["alta"])
                f1_media = f1_score(targets["media"], pred["media"])
                objective = 0.55 * f1_critica + 0.30 * f1_alta + 0.15 * f1_media
                item = {
                    "critica": float(critica),
                    "alta": float(alta),
                    "media": float(media),
                    "f1_critica": float(f1_critica),
                    "f1_alta": float(f1_alta),
                    "f1_media": float(f1_media),
                    "threshold_objective": float(objective),
                }
                if best is None or item["threshold_objective"] > best["threshold_objective"]:
                    best = item

    if best is None:
        raise RuntimeError("No se pudieron calibrar umbrales.")
    return best


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input_detail)
    df["delta_10d_pos"] = df["delta_10d"].clip(lower=0)
    df["delta_5d_pos"] = df["delta_5d"].clip(lower=0)

    results = []
    for weights in weight_grid(args.step):
        results.append(evaluar_pesos(df, weights, args.min_n))

    result_df = pd.DataFrame(results).sort_values("objective", ascending=False)
    best = result_df.iloc[0].to_dict()
    best_weights = {col: float(best[col]) for col in SCORE_COLUMNS}
    best_score = score_with_weights(df, best_weights)
    thresholds = calibrar_umbrales(df, best_score)

    config = {
        "version": 1,
        "source_validation": args.input_detail,
        "objective": {
            "description": (
                "0.50*top10_10d + 0.25*spearman_10d + "
                "0.15*top10_5d + 0.10*spearman_5d"
            ),
            "value": float(best["objective"]),
        },
        "weights": best_weights,
        "thresholds": {
            "critica": thresholds["critica"],
            "alta": thresholds["alta"],
            "media": thresholds["media"],
        },
        "validation_metrics": {
            "fechas": int(best["fechas"]),
            "n_promedio": float(best["n_promedio"]),
            "spearman_5d": float(best["spearman_5d"]),
            "spearman_10d": float(best["spearman_10d"]),
            "top10_5d": float(best["top10_5d"]),
            "top10_10d": float(best["top10_10d"]),
        },
        "threshold_metrics": {
            "f1_critica": thresholds["f1_critica"],
            "f1_alta": thresholds["f1_alta"],
            "f1_media": thresholds["f1_media"],
            "objective": thresholds["threshold_objective"],
        },
    }

    output_config = Path(args.output_config)
    output_results = Path(args.output_results)
    output_config.parent.mkdir(parents=True, exist_ok=True)
    output_results.parent.mkdir(parents=True, exist_ok=True)
    output_config.write_text(json.dumps(config, indent=2), encoding="utf-8")
    result_df.to_csv(output_results, index=False)

    print("=== Optimizacion ranking hidrico ===")
    print("Input:", args.input_detail)
    print("Config:", output_config)
    print("Resultados:", output_results)
    print("\nMejores pesos:")
    for key, value in best_weights.items():
        print(f"  {key}: {value:.3f}")
    print("\nMetricas ranking:")
    for key, value in config["validation_metrics"].items():
        print(f"  {key}: {value}")
    print("\nUmbrales:")
    for key, value in config["thresholds"].items():
        print(f"  {key}: {value:.1f}")
    print("\nTop resultados:")
    print(result_df.head(args.top_results).to_string(index=False))


if __name__ == "__main__":
    main()
