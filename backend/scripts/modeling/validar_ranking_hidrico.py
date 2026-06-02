import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.pipeline.generar_ranking_hidrico import generar_ranking
from backend.scripts.pipeline.generar_targets_hidricos_regresion import preparar_observaciones


INPUT_TEMPORAL = "backend/data/dataset_temporal_hidrico.csv"
MODEL_DIR = "backend/models/hidrico_regresion"
OUTPUT_DETAIL = "backend/data/validacion_ranking_hidrico.csv"
OUTPUT_SUMMARY = "backend/data/validacion_ranking_hidrico_resumen.csv"
HORIZONS = [5, 10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valida historicamente el ranking hidrico contra Sentinel observado."
    )
    parser.add_argument("--input", default=INPUT_TEMPORAL)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--fecha", required=True, help="Fecha historica YYYY-MM-DD")
    parser.add_argument("--output-detail", default=OUTPUT_DETAIL)
    parser.add_argument("--output-summary", default=OUTPUT_SUMMARY)
    return parser.parse_args()


def cargar_observado_futuro(df_preparado: pd.DataFrame, fecha: str, horizon: int) -> pd.DataFrame:
    fecha_futura = pd.Timestamp(fecha) + pd.Timedelta(days=horizon)
    observed = df_preparado[df_preparado["fecha"] == fecha_futura][
        ["parcela_id", "cultivo", "riesgo_hidrico"]
    ].copy()
    observed = observed.rename(
        columns={
            "riesgo_hidrico": f"riesgo_obs_{horizon}d",
        }
    )
    return observed


def top_decile_overlap(y_true: pd.Series, y_pred: pd.Series) -> float:
    n = max(1, int(np.ceil(len(y_true) * 0.10)))
    true_top = set(y_true.sort_values(ascending=False).head(n).index)
    pred_top = set(y_pred.sort_values(ascending=False).head(n).index)
    return len(true_top & pred_top) / n


def metricas(df: pd.DataFrame, horizon: int, cultivo: str | None = None) -> dict:
    data = df.copy()
    if cultivo is not None:
        data = data[data["cultivo"] == cultivo].copy()

    pred_col = f"riesgo_pred_{horizon}d"
    obs_col = f"riesgo_obs_{horizon}d"
    data = data.dropna(subset=[pred_col, obs_col])

    if data.empty:
        return {}

    error = data[pred_col] - data[obs_col]
    spearman = spearmanr(data[obs_col], data[pred_col], nan_policy="omit").correlation
    if not np.isfinite(spearman):
        spearman = 0.0

    return {
        "cultivo": cultivo or "global",
        "horizon_days": horizon,
        "n": len(data),
        "mae": float(error.abs().mean()),
        "rmse": float(np.sqrt((error ** 2).mean())),
        "bias": float(error.mean()),
        "spearman": float(spearman),
        "top10_overlap": top_decile_overlap(data[obs_col], data[pred_col]),
        "obs_mean": float(data[obs_col].mean()),
        "pred_mean": float(data[pred_col].mean()),
    }


def validar(df_temporal: pd.DataFrame, model_dir: Path, fecha: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranking = generar_ranking(df_temporal, model_dir, fecha)
    df_preparado = preparar_observaciones(df_temporal)

    detail = ranking.copy()
    for horizon in HORIZONS:
        observed = cargar_observado_futuro(df_preparado, fecha, horizon)
        detail = detail.merge(observed, on=["parcela_id", "cultivo"], how="left")
        detail[f"error_{horizon}d"] = (
            detail[f"riesgo_pred_{horizon}d"] - detail[f"riesgo_obs_{horizon}d"]
        )
        detail[f"delta_obs_{horizon}d"] = (
            detail[f"riesgo_obs_{horizon}d"] - detail["riesgo_actual"]
        )

    rows = []
    for horizon in HORIZONS:
        rows.append(metricas(detail, horizon))
        for cultivo in sorted(detail["cultivo"].unique()):
            rows.append(metricas(detail, horizon, cultivo))

    summary = pd.DataFrame([row for row in rows if row])
    return detail, summary


def main() -> None:
    args = parse_args()
    df_temporal = pd.read_csv(args.input)
    model_dir = Path(args.model_dir)
    detail, summary = validar(df_temporal, model_dir, args.fecha)

    detail_path = Path(args.output_detail)
    summary_path = Path(args.output_summary)
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)

    print("=== Validacion historica ranking hidrico ===")
    print("Fecha base:", args.fecha)
    print("Detalle:", detail_path)
    print("Resumen:", summary_path)
    print("\nResumen:")
    print(summary.to_string(index=False))
    print("\nTop 10 predicho vs observado:")
    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "riesgo_actual",
        "riesgo_pred_5d",
        "riesgo_obs_5d",
        "riesgo_pred_10d",
        "riesgo_obs_10d",
    ]
    print(detail[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
