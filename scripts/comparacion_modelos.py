"""
Comparación de modelos de clasificación de cultivos.

Entrena y evalúa tres modelos:
- Random Forest
- Gradient Boosting (XGBoost)
- SVM

Luego compara combinaciones mediante voting ensemble.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import os


FEATURES = ["ndvi", "ndmi", "ndwi", "msi", "savi", "ndre",
            "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b11",
            "mes_sin", "mes_cos"]
TARGET   = "cultivo"


def cargar_dataset(ruta: str = "data/dataset_vid_olivo.csv") -> tuple:
    """Carga el dataset y prepara features y target.

    Args:
        ruta: Ruta al CSV del dataset.

    Returns:
        Tupla (X, y_enc, le) con features, target codificado y encoder.
    """
    df = pd.read_csv(ruta)
    print(f"Dataset: {df.shape[0]} muestras")
    print(f"Distribución: {df[TARGET].value_counts().to_dict()}")

    X = df[FEATURES]
    y = df[TARGET]
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    print(f"Clases: {list(le.classes_)}")

    return X, y_enc, le


def evaluar_modelo(nombre: str, modelo, X_train, X_test, y_train, y_test, le) -> dict:
    """Entrena y evalúa un modelo, devuelve métricas.

    Args:
        nombre: Nombre del modelo para mostrar.
        modelo: Instancia del modelo sklearn.
        X_train, X_test: Features de entrenamiento y prueba.
        y_train, y_test: Target de entrenamiento y prueba.
        le: LabelEncoder con las clases.

    Returns:
        Diccionario con métricas del modelo.
    """
    print(f"\n{'='*50}")
    print(f"Modelo: {nombre}")
    print(f"{'='*50}")

    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)

    print(classification_report(y_test, y_pred, target_names=le.classes_))
    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

    cv_scores = cross_val_score(modelo, 
                                pd.concat([X_train, X_test]), 
                                np.concatenate([y_train, y_test]),
                                cv=5, scoring="accuracy")
    print(f"\nValidación cruzada (5 folds):")
    print(f"  Accuracy por fold: {[round(s, 3) for s in cv_scores]}")
    print(f"  Media: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

    accuracy = (y_pred == y_test).mean()

    return {
        "nombre":   nombre,
        "modelo":   modelo,
        "accuracy": round(accuracy, 4),
        "cv_media": round(cv_scores.mean(), 4),
        "cv_std":   round(cv_scores.std(), 4),
    }


if __name__ == "__main__":

    print("=== Comparación de modelos de clasificación ===\n")

    # cargar datos
    X, y_enc, le = cargar_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
    )

    # definir modelos
    modelos = {
        "Random Forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=4,
            random_state=42,
            class_weight="balanced"
        ),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
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
        ]),
    }

    # evaluar cada modelo
    resultados = {}
    for nombre, modelo in modelos.items():
        resultado = evaluar_modelo(
            nombre, modelo,
            X_train, X_test,
            y_train, y_test,
            le
        )
        resultados[nombre] = resultado

    # resumen comparativo
    print(f"\n{'='*50}")
    print("RESUMEN COMPARATIVO")
    print(f"{'='*50}")
    print(f"{'Modelo':<25} {'Accuracy':<12} {'CV Media':<12} {'CV Std'}")
    print("-" * 55)
    for nombre, r in resultados.items():
        print(f"{nombre:<25} {r['accuracy']:<12} {r['cv_media']:<12} ±{r['cv_std']}")

    # ensemble voting entre los 3
    print(f"\n{'='*50}")
    print("ENSEMBLE — Voting entre los 3 modelos")
    print(f"{'='*50}")

    voting_3 = VotingClassifier(
        estimators=[
            ("rf",  modelos["Random Forest"]),
            ("gb",  modelos["Gradient Boosting"]),
            ("svm", modelos["SVM"]),
        ],
        voting="soft"
    )
    r_voting3 = evaluar_modelo(
        "Voting (RF + GB + SVM)",
        voting_3,
        X_train, X_test,
        y_train, y_test,
        le
    )

    # ensemble voting entre los 2 mejores
    mejores = sorted(resultados.values(), key=lambda x: x["cv_media"], reverse=True)[:2]
    nombres_mejores = [m["nombre"] for m in mejores]
    print(f"\n{'='*50}")
    print(f"ENSEMBLE — Voting entre los 2 mejores ({' + '.join(nombres_mejores)})")
    print(f"{'='*50}")

    voting_2 = VotingClassifier(
        estimators=[
            (nombre.lower().replace(" ", "_"), modelos[nombre])
            for nombre in nombres_mejores
        ],
        voting="soft"
    )
    r_voting2 = evaluar_modelo(
        f"Voting ({' + '.join(nombres_mejores)})",
        voting_2,
        X_train, X_test,
        y_train, y_test,
        le
    )

    # resumen final
    print(f"\n{'='*50}")
    print("RESUMEN FINAL")
    print(f"{'='*50}")
    todos = list(resultados.values()) + [r_voting3, r_voting2]
    todos_ordenados = sorted(todos, key=lambda x: x["cv_media"], reverse=True)
    print(f"{'Modelo':<35} {'CV Media':<12} {'CV Std'}")
    print("-" * 55)
    for r in todos_ordenados:
        print(f"{r['nombre']:<35} {r['cv_media']:<12} ±{r['cv_std']}")

    # guardar el mejor modelo
    mejor = todos_ordenados[0]
    print(f"\nMejor modelo: {mejor['nombre']} ({mejor['cv_media']*100:.1f}%)")

    os.makedirs("models", exist_ok=True)
    joblib.dump({"modelo": mejor["modelo"], "label_encoder": le},
                "models/clasificador_cultivo.pkl")
    print(f"Modelo guardado en models/clasificador_cultivo.pkl")

    print("\n=== Comparación completada ===")