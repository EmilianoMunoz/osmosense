"""
Clasificador multiclase de cultivos (vid, frutales, olivo)

Modelos:
- XGBoost
- SVM
- Stacking (XGBoost + SVM)

Se entrena SOLO con parcelas que NO son descarte.
"""

import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix

from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import StackingClassifier

from xgboost import XGBClassifier

import joblib
import os


TARGET = "cultivo"


def cargar_dataset(ruta = "data/dataset_hibrido.csv"):
    df = pd.read_csv(ruta)

    print(f"Dataset original: {df.shape[0]} muestras")

    # filtrar solo cultivos
    df = df[df["cultivo"] != "descarte"].copy()

    print(f"Dataset filtrado (solo cultivos): {df.shape[0]} muestras")
    print(f"Distribución: {df[TARGET].value_counts().to_dict()}")

    # eliminar columnas no útiles
    X = df.drop(columns=["cultivo", "parcela_id", "nombre"], errors="ignore")
    y = df[TARGET]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    print(f"Clases: {list(le.classes_)}")

    return X, y_enc, le


def evaluar_modelo(nombre, modelo, X_train, X_test, y_train, y_test, le):
    print(f"\n{'='*50}")
    print(f"Modelo: {nombre}")
    print(f"{'='*50}")

    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)

    print(classification_report(y_test, y_pred, target_names=le.classes_))
    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

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

    accuracy = (y_pred == y_test).mean()

    return {
        "nombre": nombre,
        "modelo": modelo,
        "accuracy": round(accuracy, 4),
        "cv_media": round(cv_scores.mean(), 4),
        "cv_std": round(cv_scores.std(), 4),
    }


if __name__ == "__main__":

    print("=== Clasificador multiclase: cultivos ===\n")

    X, y_enc, le = cargar_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc,
        test_size=0.2,
        random_state=42,
        stratify=y_enc
    )

    # =========================
    # MODELOS BASE
    # =========================

    modelos = {

        "XGBoost": XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="mlogloss",
            random_state=42
        ),

        "SVM": Pipeline([
            ("scaler", StandardScaler()),
            ("svm", SVC(
                kernel="rbf",
                C=10,
                gamma="scale",
                probability=True,
                class_weight="balanced",
                random_state=42
            ))
        ])
    }

    resultados = {}

    # =========================
    # EVALUACIÓN MODELOS BASE
    # =========================

    for nombre, modelo in modelos.items():
        resultado = evaluar_modelo(
            nombre, modelo,
            X_train, X_test,
            y_train, y_test,
            le
        )
        resultados[nombre] = resultado

    # =========================
    # STACKING
    # =========================

    print(f"\n{'='*50}")
    print("STACKING — SVM + XGBoost")
    print(f"{'='*50}")

    stacking_model = StackingClassifier(
        estimators=[
            ("xgb", modelos["XGBoost"]),
            ("svm", modelos["SVM"]),
        ],
        final_estimator=LogisticRegression(),
        passthrough=False
    )

    r_stacking = evaluar_modelo(
        "Stacking (SVM + XGBoost)",
        stacking_model,
        X_train, X_test,
        y_train, y_test,
        le
    )

    # =========================
    # RESUMEN FINAL
    # =========================

    print(f"\n{'='*50}")
    print("RESUMEN FINAL")
    print(f"{'='*50}")

    todos = list(resultados.values()) + [r_stacking]
    todos_ordenados = sorted(todos, key=lambda x: x["cv_media"], reverse=True)

    print(f"{'Modelo':<35} {'CV Media':<12} {'CV Std'}")
    print("-" * 55)

    for r in todos_ordenados:
        print(f"{r['nombre']:<35} {r['cv_media']:<12} ±{r['cv_std']}")

    # =========================
    # GUARDAR MEJOR MODELO
    # =========================

    mejor = todos_ordenados[0]

    print(f"\nMejor modelo: {mejor['nombre']} ({mejor['cv_media']*100:.1f}%)")

    os.makedirs("models", exist_ok=True)

    joblib.dump(
        {
            "modelo": mejor["modelo"],
            "label_encoder": le
        },
        "models/clasificador_cultivos.pkl"
    )

    print("Modelo guardado en models/clasificador_cultivos.pkl")
    print("\n=== Proceso completado ===")