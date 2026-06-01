import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix


VALIDATION_PATH = "data/validation.csv"
TEST_PATH = "data/test_final.csv"
MODEL_PATH = "models/clasificador_multiclass.pkl"
OUTPUT_CONFIG = "models/filtro_vid_olivo_config.json"

TARGET_CLASSES = ["vid", "olivo"]
NON_TARGET_CLASS = "no_objetivo"


def mapear_clase(clase: str) -> str:
    if clase in TARGET_CLASSES:
        return clase
    return NON_TARGET_CLASS


def cargar_dataset(path: str) -> tuple[pd.DataFrame, np.ndarray]:
    df = pd.read_csv(path)
    y_true = np.array([mapear_clase(c) for c in df["cultivo"].values])
    return df, y_true


def predecir_filtro(
    probabilities: np.ndarray,
    classes: list[str],
    threshold_vid: float,
    threshold_olivo: float,
    margin: float,
) -> np.ndarray:
    idx_vid = classes.index("vid")
    idx_olivo = classes.index("olivo")

    prob_vid = probabilities[:, idx_vid]
    prob_olivo = probabilities[:, idx_olivo]

    max_other_for_vid = np.max(np.delete(probabilities, idx_vid, axis=1), axis=1)
    max_other_for_olivo = np.max(np.delete(probabilities, idx_olivo, axis=1), axis=1)

    pred = np.full(len(probabilities), NON_TARGET_CLASS, dtype=object)

    es_vid = (
        (prob_vid >= threshold_vid)
        & (prob_vid >= prob_olivo)
        & ((prob_vid - max_other_for_vid) >= margin)
    )
    pred[es_vid] = "vid"

    es_olivo = (
        ~es_vid
        & (prob_olivo >= threshold_olivo)
        & (prob_olivo >= prob_vid)
        & ((prob_olivo - max_other_for_olivo) >= margin)
    )
    pred[es_olivo] = "olivo"

    return pred


def metricas_objetivo(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    metrics = {}

    for clase in TARGET_CLASSES:
        tp = int(((y_true == clase) & (y_pred == clase)).sum())
        fp = int(((y_true != clase) & (y_pred == clase)).sum())
        fn = int(((y_true == clase) & (y_pred != clase)).sum())

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0

        metrics[f"precision_{clase}"] = precision
        metrics[f"recall_{clase}"] = recall
        metrics[f"predichas_{clase}"] = int((y_pred == clase).sum())

    metrics["coverage_objetivo"] = float(np.isin(y_pred, TARGET_CLASSES).mean())
    metrics["retenidas_objetivo_real"] = float(
        np.isin(y_pred[y_true != NON_TARGET_CLASS], TARGET_CLASSES).mean()
    )
    metrics["contaminacion_no_objetivo"] = float(
        (np.isin(y_pred, TARGET_CLASSES) & (y_true == NON_TARGET_CLASS)).sum()
        / max(1, np.isin(y_pred, TARGET_CLASSES).sum())
    )

    metrics["score"] = (
        metrics["precision_vid"]
        + metrics["precision_olivo"]
        + 0.35 * metrics["recall_vid"]
        + 0.35 * metrics["recall_olivo"]
        - 0.75 * metrics["contaminacion_no_objetivo"]
    )

    return metrics


def imprimir_resultado(titulo: str, y_true: np.ndarray, y_pred: np.ndarray, metrics: dict) -> None:
    print(f"\n=== {titulo} ===")
    print(f"precision_vid={metrics['precision_vid']:.3f}")
    print(f"recall_vid={metrics['recall_vid']:.3f}")
    print(f"precision_olivo={metrics['precision_olivo']:.3f}")
    print(f"recall_olivo={metrics['recall_olivo']:.3f}")
    print(f"coverage_objetivo={metrics['coverage_objetivo']:.3f}")
    print(f"contaminacion_no_objetivo={metrics['contaminacion_no_objetivo']:.3f}")
    print("\nReporte:")
    print(classification_report(y_true, y_pred, labels=[NON_TARGET_CLASS, "olivo", "vid"]))
    print("Matriz de confusion:")
    print(confusion_matrix(y_true, y_pred, labels=[NON_TARGET_CLASS, "olivo", "vid"]))
    print("Labels matriz:", [NON_TARGET_CLASS, "olivo", "vid"])


def main() -> None:
    data = joblib.load(MODEL_PATH)
    model = data["model"]
    features = data["features"]
    classes = list(data["classes"])

    validation_df, y_validation = cargar_dataset(VALIDATION_PATH)
    test_df, y_test = cargar_dataset(TEST_PATH)

    X_validation = validation_df.select_dtypes(include=[np.number]).reindex(
        columns=features,
        fill_value=0,
    )
    X_test = test_df.select_dtypes(include=[np.number]).reindex(columns=features, fill_value=0)

    probabilities_validation = model.predict_proba(X_validation)
    probabilities_test = model.predict_proba(X_test)

    best = None

    for threshold_vid in np.arange(0.25, 0.86, 0.02):
        for threshold_olivo in np.arange(0.25, 0.86, 0.02):
            for margin in np.arange(0.00, 0.31, 0.02):
                y_pred = predecir_filtro(
                    probabilities_validation,
                    classes,
                    threshold_vid,
                    threshold_olivo,
                    margin,
                )
                metrics = metricas_objetivo(y_validation, y_pred)

                # Evita configuraciones demasiado conservadoras para operar el producto.
                if metrics["recall_vid"] < 0.35 or metrics["recall_olivo"] < 0.35:
                    continue

                if best is None or metrics["score"] > best["metrics"]["score"]:
                    best = {
                        "threshold_vid": float(threshold_vid),
                        "threshold_olivo": float(threshold_olivo),
                        "margin": float(margin),
                        "metrics": metrics,
                        "pred_validation": y_pred,
                    }

    if best is None:
        raise RuntimeError("No se encontro una configuracion valida para el filtro")

    y_test_pred = predecir_filtro(
        probabilities_test,
        classes,
        best["threshold_vid"],
        best["threshold_olivo"],
        best["margin"],
    )
    test_metrics = metricas_objetivo(y_test, y_test_pred)

    print("=== Filtro operativo VID/OLIVO ===")
    print(f"threshold_vid={best['threshold_vid']:.2f}")
    print(f"threshold_olivo={best['threshold_olivo']:.2f}")
    print(f"margin={best['margin']:.2f}")

    imprimir_resultado("VALIDATION", y_validation, best["pred_validation"], best["metrics"])
    imprimir_resultado("TEST FINAL", y_test, y_test_pred, test_metrics)

    output = {
        "model_path": MODEL_PATH,
        "classes": classes,
        "target_classes": TARGET_CLASSES,
        "non_target_class": NON_TARGET_CLASS,
        "threshold_vid": best["threshold_vid"],
        "threshold_olivo": best["threshold_olivo"],
        "margin": best["margin"],
        "validation_metrics": best["metrics"],
        "test_metrics": test_metrics,
    }

    Path(OUTPUT_CONFIG).write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nConfiguracion guardada en {OUTPUT_CONFIG}")


if __name__ == "__main__":
    main()
