"""
Comparación de modelos de clasificación de cultivos.

Modelos:
- Random Forest
- XGBoost
- SVM

Luego compara ensembles mediante soft voting.
"""

import os
import joblib
import pandas as pd
import numpy as np

from sklearn.ensemble import (
    RandomForestClassifier,
    VotingClassifier
)

from sklearn.svm import SVC

from sklearn.model_selection import (
    train_test_split,
    cross_val_score
)

from sklearn.preprocessing import (
    LabelEncoder,
    StandardScaler
)

from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    classification_report,
    confusion_matrix
)

from xgboost import XGBClassifier


TARGET = "cultivo"


def cargar_dataset(
    ruta: str = "data/dataset_temporal.csv"
) -> tuple:

    df = pd.read_csv(ruta)

    print(f"Dataset: {df.shape[0]} muestras")
    print(f"Distribución: {df[TARGET].value_counts().to_dict()}")

    COLUMNAS_EXCLUIR = [
        "cultivo",
        "parcela_id",
        "nombre"
    ]

    X = df.drop(columns=COLUMNAS_EXCLUIR, errors="ignore")

    y = df[TARGET]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    print(f"Clases: {list(le.classes_)}")

    return X, y_enc, le


def evaluar_modelo(
    nombre: str,
    modelo,
    X_train,
    X_test,
    y_train,
    y_test,
    le
) -> dict:

    print(f"\n{'='*50}")
    print(f"Modelo: {nombre}")
    print(f"{'='*50}")

    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)

    print(classification_report(
        y_test,
        y_pred,
        target_names=le.classes_
    ))

    print("Matriz de confusión:")
    print(confusion_matrix(y_test, y_pred))

    X_total = pd.concat([X_train, X_test])
    y_total = np.concatenate([y_train, y_test])

    cv_scores = cross_val_score(
        modelo,
        X_total,
        y_total,
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

    print("=== Comparación de modelos de clasificación ===\n")

    # -------------------------------------------------
    # cargar dataset
    # -------------------------------------------------

    X, y_enc, le = cargar_dataset()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y_enc,
        test_size=0.2,
        random_state=42,
        stratify=y_enc
    )

    # -------------------------------------------------
    # modelos
    # -------------------------------------------------

    modelos = {

        "Random Forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=15,
            min_samples_split=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        ),

        "XGBoost": XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.03,

            subsample=0.8,
            colsample_bytree=0.8,

            objective="multi:softprob",

            eval_metric="mlogloss",

            random_state=42,

            n_jobs=-1
        ),

        "SVM": Pipeline([
            ("scaler", StandardScaler()),

            ("svm", SVC(
                kernel="rbf",

                C=15,

                gamma="scale",

                probability=True,

                class_weight="balanced",

                random_state=42
            ))
        ]),
    }

    # -------------------------------------------------
    # evaluar modelos
    # -------------------------------------------------

    resultados = {}

    for nombre, modelo in modelos.items():

        resultado = evaluar_modelo(
            nombre,
            modelo,
            X_train,
            X_test,
            y_train,
            y_test,
            le
        )

        resultados[nombre] = resultado

    # -------------------------------------------------
    # resumen
    # -------------------------------------------------

    print(f"\n{'='*50}")
    print("RESUMEN COMPARATIVO")
    print(f"{'='*50}")

    print(f"{'Modelo':<25} {'Accuracy':<12} {'CV Media':<12} {'CV Std'}")
    print("-" * 55)

    for nombre, r in resultados.items():

        print(
            f"{nombre:<25} "
            f"{r['accuracy']:<12} "
            f"{r['cv_media']:<12} "
            f"±{r['cv_std']}"
        )

    # -------------------------------------------------
    # ensemble top 2
    # -------------------------------------------------

    mejores = sorted(
        resultados.values(),
        key=lambda x: x["cv_media"],
        reverse=True
    )[:2]

    nombres_mejores = [m["nombre"] for m in mejores]

    print(f"\n{'='*50}")
    print(
        f"ENSEMBLE — Voting entre los 2 mejores "
        f"({' + '.join(nombres_mejores)})"
    )
    print(f"{'='*50}")

    voting_2 = VotingClassifier(

        estimators=[
            (
                nombre.lower().replace(" ", "_"),
                modelos[nombre]
            )
            for nombre in nombres_mejores
        ],

        voting="soft",

        n_jobs=-1
    )

    r_voting2 = evaluar_modelo(
        f"Voting ({' + '.join(nombres_mejores)})",

        voting_2,

        X_train,
        X_test,

        y_train,
        y_test,

        le
    )

    # -------------------------------------------------
    # resumen final
    # -------------------------------------------------

    print(f"\n{'='*50}")
    print("RESUMEN FINAL")
    print(f"{'='*50}")

    todos = list(resultados.values()) + [r_voting2]

    todos_ordenados = sorted(
        todos,
        key=lambda x: x["cv_media"],
        reverse=True
    )

    print(f"{'Modelo':<35} {'CV Media':<12} {'CV Std'}")
    print("-" * 55)

    for r in todos_ordenados:

        print(
            f"{r['nombre']:<35} "
            f"{r['cv_media']:<12} "
            f"±{r['cv_std']}"
        )

    # -------------------------------------------------
    # guardar mejor modelo
    # -------------------------------------------------

    mejor = todos_ordenados[0]

    print(
        f"\nMejor modelo: "
        f"{mejor['nombre']} "
        f"({mejor['cv_media']*100:.1f}%)"
    )

    os.makedirs("models", exist_ok=True)

    joblib.dump(
        {
            "modelo": mejor["modelo"],
            "label_encoder": le
        },
        "models/clasificador_cultivo.pkl"
    )

    print("Modelo guardado en models/clasificador_cultivo.pkl")

    # -------------------------------------------------
    # feature importance XGBoost
    # -------------------------------------------------

    if "XGBoost" in resultados:

        print(f"\n{'='*50}")
        print("TOP FEATURES — XGBoost")
        print(f"{'='*50}")

        modelo_xgb = resultados["XGBoost"]["modelo"]

        importancias = pd.DataFrame({
            "feature": X.columns,
            "importance": modelo_xgb.feature_importances_
        })

        importancias = importancias.sort_values(
            by="importance",
            ascending=False
        )

        print(importancias.head(25))

    print("\n=== Comparación completada ===")