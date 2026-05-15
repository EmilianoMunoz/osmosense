"""
Selección automática de features usando XGBoost.

- Entrena XGBoost
- Calcula importancia
- Selecciona top N features
- Genera nuevo dataset limpio

Salida:
data/dataset_top_features.csv
"""

import pandas as pd
import numpy as np
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder

INPUT_PATH = "data/dataset_hibrido.csv"
OUTPUT_PATH = "data/dataset_top_features.csv"

TOP_N = 50  # podés probar 50, 80, 100


def cargar_datos():
    df = pd.read_csv(INPUT_PATH)

    # solo cultivos
    df = df[df["cultivo"] != "descarte"].copy()

    X = df.drop(columns=[c for c in ["cultivo", "parcela_id", "nombre"] if c in df.columns])
    y = df["cultivo"]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    return df, X, y_enc, le


def seleccionar_features(X, y):
    print("Entrenando XGBoost para obtener importancia...")

    modelo = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mlogloss"
    )

    modelo.fit(X, y)

    importancias = modelo.feature_importances_

    df_importance = pd.DataFrame({
        "feature": X.columns,
        "importance": importancias
    }).sort_values(by="importance", ascending=False)

    print("\nTOP 20 FEATURES:")
    print(df_importance.head(20))

    top_features = df_importance.head(TOP_N)["feature"].tolist()

    return top_features, df_importance


if __name__ == "__main__":

    print("=== Selección de features ===\n")

    df, X, y, le = cargar_datos()

    print(f"Dataset original: {X.shape}")

    top_features, df_importance = seleccionar_features(X, y)

    print(f"\nSeleccionando top {TOP_N} features...")

    df_final = df[["parcela_id", "cultivo"] + top_features]

    print(f"Dataset reducido: {df_final.shape}")

    df_final.to_csv(OUTPUT_PATH, index=False)

    print(f"\nGuardado en: {OUTPUT_PATH}")
    print("\n=== Proceso completado ===")