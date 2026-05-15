"""
Comparación de datasets:
- dataset original
- dataset fenológico
- dataset híbrido

Evalúa usando SVM (que ya viste que rinde bien).
"""

import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.metrics import classification_report


TARGET = "cultivo"


def cargar_dataset(path):
    df = pd.read_csv(path)

    # filtrar solo cultivos
    df = df[df[TARGET] != "descarte"].copy()

    X = df.drop(columns=[c for c in ["cultivo", "parcela_id", "nombre"] if c in df.columns])
    y = df[TARGET]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    return X, y_enc, le


def evaluar(nombre, X, y, le):
    print(f"\n{'='*60}")
    print(f"DATASET: {nombre}")
    print(f"{'='*60}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    modelo = Pipeline([
        ("scaler", StandardScaler()),
        ("svm", SVC(
            kernel="rbf",
            C=10,
            gamma="scale",
            class_weight="balanced",
            probability=True,
            random_state=42
        ))
    ])

    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)

    print("\nClassification report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    cv = cross_val_score(modelo, X, y, cv=5, scoring="accuracy")

    print("CV:", [round(x, 3) for x in cv])
    print(f"Media: {cv.mean():.3f} ± {cv.std():.3f}")

    return cv.mean()


if __name__ == "__main__":

    datasets = {
        "Original": "data/dataset_temporal.csv",
        "Fenologico": "data/dataset_fenologico.csv",
        "Hibrido": "data/dataset_hibrido.csv"
    }

    resultados = {}

    for nombre, path in datasets.items():
        try:
            X, y, le = cargar_dataset(path)
            score = evaluar(nombre, X, y, le)
            resultados[nombre] = score
        except Exception as e:
            print(f"\nError con {nombre}: {e}")

    print(f"\n{'='*60}")
    print("RESUMEN FINAL")
    print(f"{'='*60}")

    for k, v in sorted(resultados.items(), key=lambda x: x[1], reverse=True):
        print(f"{k:<15} → {v:.4f}")