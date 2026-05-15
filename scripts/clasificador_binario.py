"""
Clasificador binario: cultivo vs descarte

Objetivo:
Separar parcelas útiles (vid, frutales, olivo) de descarte.

Se prioriza:
- alto recall de cultivo (no perder parcelas útiles)
- estabilidad del modelo

Modelo:
- XGBoost optimizado
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os


TARGET = "es_cultivo"


def cargar_dataset(ruta: str = "data/dataset_temporal.csv"):
    df = pd.read_csv(ruta)

    # 🔧 evitar fragmentación
    df = df.copy()

    print(f"Dataset: {df.shape[0]} muestras")
    print(f"Distribución original: {df['cultivo'].value_counts().to_dict()}")

    # binarización
    df[TARGET] = df["cultivo"].apply(
        lambda x: 0 if x == "descarte" else 1
    )

    print(f"Distribución binaria: {df[TARGET].value_counts().to_dict()}")

    COLUMNAS_EXCLUIR = [
        "cultivo",
        "parcela_id",
        "nombre"
    ]

    X = df.drop(columns=COLUMNAS_EXCLUIR + [TARGET], errors="ignore")
    y = df[TARGET]

    return X, y


def evaluar_modelo(modelo, X_train, X_test, y_train, y_test, threshold=0.5):
    print(f"\n{'='*50}")
    print("Modelo: XGBoost Binario")
    print(f"{'='*50}")

    modelo.fit(X_train, y_train)

    # 🔥 usamos probabilidades en vez de predict directo
    proba = modelo.predict_proba(X_test)[:, 1]

    # threshold configurable
    y_pred = (proba > threshold).astype(int)

    print(f"\nThreshold usado: {threshold}")

    print(classification_report(y_test, y_pred))
    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

    # métricas clave para tu problema
    from sklearn.metrics import recall_score

    recall_cultivo = recall_score(y_test, y_pred, pos_label=1)
    print(f"\nRecall cultivo (lo más importante): {recall_cultivo:.3f}")

    # cross validation
    cv_scores = cross_val_score(
        modelo,
        pd.concat([X_train, X_test]),
        np.concatenate([y_train, y_test]),
        cv=5,
        scoring="accuracy"
    )

    print(f"\nValidación cruzada (5 folds):")
    print(f"  Accuracy por fold: {[round(s, 3) for s in cv_scores]}")
    print(f"  Media: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    return modelo, cv_scores.mean()


if __name__ == "__main__":

    print("=== Clasificador binario: cultivo vs descarte ===\n")

    X, y = cargar_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    # ⚖️ balanceo dinámico
    scale_pos_weight = len(y_train[y_train == 0]) / len(y_train[y_train == 1])

    print(f"\nScale_pos_weight: {scale_pos_weight:.3f}")

    # 🚀 modelo optimizado
    modelo = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.5,
        reg_lambda=1.5,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1
    )

    # 🔥 podés probar distintos thresholds
    THRESHOLD = 0.35

    modelo, cv = evaluar_modelo(
        modelo,
        X_train, X_test,
        y_train, y_test,
        threshold=THRESHOLD
    )

    print(f"\nCV promedio: {cv:.3f}")

    # guardar modelo
    os.makedirs("models", exist_ok=True)
    joblib.dump(
        {"modelo": modelo, "threshold": THRESHOLD},
        "models/clasificador_binario.pkl"
    )

    print("\nModelo guardado en models/clasificador_binario.pkl")
    print("\n=== Proceso completado ===")