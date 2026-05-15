"""
Selección de features usando importancia de XGBoost.

Genera un dataset reducido con las N features más importantes.
"""

import pandas as pd
from xgboost import XGBClassifier
from sklearn.preprocessing import LabelEncoder

INPUT_PATH = "data/dataset_temporal_features.csv"
OUTPUT_PATH = "data/dataset_reducido.csv"

TOP_N = 150  # podés probar 100, 150, 200


def main():
    print("Cargando dataset...")
    df = pd.read_csv(INPUT_PATH)
    print("Shape original:", df.shape)

    # filtrar solo cultivos (igual que tu clasificador)
    df = df[df["cultivo"] != "descarte"].copy()

    # separar features y target
    X = df.drop(columns=["cultivo", "parcela_id", "nombre"], errors="ignore")
    y = df["cultivo"]

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    print("\nEntrenando XGBoost para feature importance...")

    modelo = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="mlogloss",
        random_state=42
    )

    modelo.fit(X, y_enc)

    importances = modelo.feature_importances_

    df_importance = pd.DataFrame({
        "feature": X.columns,
        "importance": importances
    })

    df_importance = df_importance.sort_values(
        by="importance",
        ascending=False
    )

    print("\nTop 20 features:")
    print(df_importance.head(20))

    top_features = df_importance.head(TOP_N)["feature"].tolist()

    print(f"\nSeleccionando top {TOP_N} features...")

    # reconstruir dataset reducido
    df_reducido = df[top_features].copy()
    df_reducido["cultivo"] = df["cultivo"]

    print("Shape reducido:", df_reducido.shape)

    df_reducido.to_csv(OUTPUT_PATH, index=False)

    print(f"\nGuardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()