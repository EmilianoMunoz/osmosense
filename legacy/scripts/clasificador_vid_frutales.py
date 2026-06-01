import pandas as pd
import numpy as np
import joblib
import os

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from xgboost import XGBClassifier

# ================================
# CONFIG
# ================================
DATA_PATH = "data/train.csv"
TARGET = "target"
TEST_SIZE = 0.2
RANDOM_STATE = 42

print("=== Clasificador: VID vs FRUTALES (XGBoost PRO) ===\n")

# ================================
# CARGA DATASET
# ================================
df = pd.read_csv(DATA_PATH)

df = df[df["cultivo"].isin(["vid", "frutales"])].copy()

print("Distribución:", df["cultivo"].value_counts().to_dict())

# ================================
# TARGET
# ================================
df[TARGET] = df["cultivo"].apply(lambda x: 1 if x == "vid" else 0)

print("Distribución binaria:", df[TARGET].value_counts().to_dict())

# ================================
# FEATURES
# ================================
indices_temporales = ("ndvi_", "ndmi_", "ndwi_", "msi_", "savi_", "ndre_")

features_clave = [
    col
    for col in df.select_dtypes(include=[np.number]).columns
    if col.startswith(indices_temporales) and "_mean_" in col
]

X = df[features_clave].copy()
y = df[TARGET]

print(f"\nFeatures usadas: {len(features_clave)}")

# ================================
# SPLIT
# ================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=TEST_SIZE,
    stratify=y,
    random_state=RANDOM_STATE
)

# ================================
# MODELO XGBOOST (🔥 TUNING EFECTIVO)
# ================================
model = XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.03,
    subsample=0.9,
    colsample_bytree=0.9,
    gamma=0.2,
    min_child_weight=2,
    eval_metric="logloss",
    random_state=RANDOM_STATE,
    n_jobs=-1
)

# ================================
# ENTRENAMIENTO
# ================================
print("\nEntrenando modelo...")
model.fit(X_train, y_train)

# ================================
# OPTIMIZACIÓN DE THRESHOLD (🔥 CLAVE)
# ================================
probs = model.predict_proba(X_test)[:, 1]

best_threshold = 0.5
best_f1 = 0

for t in np.arange(0.3, 0.71, 0.05):
    preds = (probs >= t).astype(int)
    f1 = f1_score(y_test, preds)

    if f1 > best_f1:
        best_f1 = f1
        best_threshold = t

print(f"\nMejor threshold encontrado: {best_threshold:.2f}")
print(f"Mejor F1: {best_f1:.3f}")

# ================================
# PRED FINAL
# ================================
y_pred = (probs >= best_threshold).astype(int)

# ================================
# RESULTADOS
# ================================
print("\n=== RESULTADOS ===\n")

print(classification_report(y_test, y_pred))
print(confusion_matrix(y_test, y_pred))

# ================================
# CROSS VALIDATION
# ================================
print("\nValidación cruzada (5 folds):")

cv_scores = cross_val_score(
    model,
    X,
    y,
    cv=5,
    scoring="accuracy",
    n_jobs=-1
)

print(f"  Accuracy por fold: {[round(s, 3) for s in cv_scores]}")
print(f"  Media: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

# ================================
# GUARDAR MODELO + THRESHOLD + FEATURES
# ================================
os.makedirs("models", exist_ok=True)

joblib.dump(
    {
        "model": model,
        "threshold": best_threshold,
        "features": list(X.columns)  # 🔥 usar las reales
    },
    "models/clasificador_vid_frutales.pkl"
)

print("\nModelo guardado en models/clasificador_vid_frutales.pkl")
