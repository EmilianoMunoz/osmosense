import itertools
import argparse

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score


DEFAULT_DATA_PATH = "data/validation.csv"

MODEL_CULTIVO_PATH = "models/clasificador_cultivo.pkl"
MODEL_OLIVO_PATH = "models/clasificador_olivo.pkl"
MODEL_VID_PATH = "models/clasificador_vid_frutales.pkl"


def mapear_clase_real(clase: str) -> str:
    if clase in ["vid", "frutales", "olivo"]:
        return clase
    return "no_cultivo"


def cargar_modelo(path: str) -> dict:
    data = joblib.load(path)
    required_keys = {"model", "threshold", "features"}
    missing_keys = required_keys - set(data.keys())

    if missing_keys:
        raise KeyError(f"El modelo {path} no tiene las claves requeridas: {missing_keys}")

    return data


def predecir_pipeline(
    prob_cultivo: np.ndarray,
    prob_olivo: np.ndarray,
    prob_vid: np.ndarray,
    threshold_cultivo: float,
    threshold_olivo: float,
    threshold_vid: float,
) -> np.ndarray:
    predicciones = np.full(len(prob_cultivo), "frutales", dtype=object)

    es_no_cultivo = prob_cultivo < threshold_cultivo
    predicciones[es_no_cultivo] = "no_cultivo"

    candidatos_cultivo = ~es_no_cultivo
    es_olivo = candidatos_cultivo & (prob_olivo >= threshold_olivo)
    predicciones[es_olivo] = "olivo"

    candidatos_vid_frutales = candidatos_cultivo & ~es_olivo
    es_vid = candidatos_vid_frutales & (prob_vid >= threshold_vid)
    predicciones[es_vid] = "vid"

    return predicciones


def evaluar(y_true: np.ndarray, predicciones: np.ndarray) -> dict:
    return {
        "accuracy": accuracy_score(y_true, predicciones),
        "macro_f1": f1_score(y_true, predicciones, average="macro"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Optimiza thresholds del pipeline jerarquico sobre un dataset de validacion."
    )
    parser.add_argument(
        "--data-path",
        default=DEFAULT_DATA_PATH,
        help=f"CSV usado para calibrar thresholds. Default: {DEFAULT_DATA_PATH}",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Cargando modelos...")
    data_cultivo = cargar_modelo(MODEL_CULTIVO_PATH)
    data_olivo = cargar_modelo(MODEL_OLIVO_PATH)
    data_vid = cargar_modelo(MODEL_VID_PATH)

    print("Cargando dataset...")
    print(f"Dataset de calibracion: {args.data_path}")
    df = pd.read_csv(args.data_path)

    X = df.drop(columns=["cultivo"], errors="ignore")
    X = X.select_dtypes(include=[np.number])
    y_true = np.array([mapear_clase_real(c) for c in df["cultivo"].values])

    print("Calculando probabilidades...")
    X_cultivo = X.reindex(columns=data_cultivo["features"], fill_value=0)
    X_olivo = X.reindex(columns=data_olivo["features"], fill_value=0)
    X_vid = X.reindex(columns=data_vid["features"], fill_value=0)

    prob_cultivo = data_cultivo["model"].predict_proba(X_cultivo)[:, 1]
    prob_olivo = data_olivo["model"].predict_proba(X_olivo)[:, 1]
    prob_vid = data_vid["model"].predict_proba(X_vid)[:, 1]

    thresholds_actuales = (
        data_cultivo["threshold"],
        data_olivo["threshold"],
        data_vid["threshold"],
    )

    pred_actual = predecir_pipeline(
        prob_cultivo,
        prob_olivo,
        prob_vid,
        *thresholds_actuales,
    )
    score_actual = evaluar(y_true, pred_actual)

    print("\n=== THRESHOLDS ACTUALES ===")
    print(f"cultivo={thresholds_actuales[0]:.3f}")
    print(f"olivo={thresholds_actuales[1]:.3f}")
    print(f"vid={thresholds_actuales[2]:.3f}")
    print(f"accuracy={score_actual['accuracy']:.4f}")
    print(f"macro_f1={score_actual['macro_f1']:.4f}")

    grilla_cultivo = np.arange(0.30, 0.91, 0.02)
    grilla_olivo = np.arange(0.02, 0.51, 0.02)
    grilla_vid = np.arange(0.30, 0.81, 0.02)

    best_accuracy = {
        "score": -1,
        "macro_f1": -1,
        "thresholds": None,
        "predicciones": None,
    }
    best_macro_f1 = {
        "score": -1,
        "accuracy": -1,
        "thresholds": None,
        "predicciones": None,
    }

    total = len(grilla_cultivo) * len(grilla_olivo) * len(grilla_vid)
    print(f"\nProbando {total:,} combinaciones...")

    for threshold_cultivo, threshold_olivo, threshold_vid in itertools.product(
        grilla_cultivo,
        grilla_olivo,
        grilla_vid,
    ):
        predicciones = predecir_pipeline(
            prob_cultivo,
            prob_olivo,
            prob_vid,
            threshold_cultivo,
            threshold_olivo,
            threshold_vid,
        )
        score = evaluar(y_true, predicciones)

        if score["accuracy"] > best_accuracy["score"]:
            best_accuracy = {
                "score": score["accuracy"],
                "macro_f1": score["macro_f1"],
                "thresholds": (threshold_cultivo, threshold_olivo, threshold_vid),
                "predicciones": predicciones,
            }

        if score["macro_f1"] > best_macro_f1["score"]:
            best_macro_f1 = {
                "score": score["macro_f1"],
                "accuracy": score["accuracy"],
                "thresholds": (threshold_cultivo, threshold_olivo, threshold_vid),
                "predicciones": predicciones,
            }

    print("\n=== MEJOR POR ACCURACY ===")
    tc, to, tv = best_accuracy["thresholds"]
    print(f"cultivo={tc:.3f}")
    print(f"olivo={to:.3f}")
    print(f"vid={tv:.3f}")
    print(f"accuracy={best_accuracy['score']:.4f}")
    print(f"macro_f1={best_accuracy['macro_f1']:.4f}")
    print("\nReporte:")
    print(classification_report(y_true, best_accuracy["predicciones"]))
    print("Matriz de confusión:")
    print(confusion_matrix(y_true, best_accuracy["predicciones"]))

    print("\n=== MEJOR POR MACRO-F1 ===")
    tc, to, tv = best_macro_f1["thresholds"]
    print(f"cultivo={tc:.3f}")
    print(f"olivo={to:.3f}")
    print(f"vid={tv:.3f}")
    print(f"accuracy={best_macro_f1['accuracy']:.4f}")
    print(f"macro_f1={best_macro_f1['score']:.4f}")

    print("\nNota: este script no modifica los .pkl; solo informa los thresholds candidatos.")


if __name__ == "__main__":
    main()
