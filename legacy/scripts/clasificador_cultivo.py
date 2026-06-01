import pandas as pd
import numpy as np
import joblib
import os

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix, roc_curve
from xgboost import XGBClassifier

# ================================
# CONFIG
# ================================
DATA_PATH = "data/train.csv"
TARGET = "target"
TEST_SIZE = 0.2
RANDOM_STATE = 42

print("=== Clasificador: CULTIVO vs NO CULTIVO ===\n")

# ================================
# CARGA DATASET
# ================================
df = pd.read_csv(DATA_PATH)

print(f"Dataset original: {len(df)} muestras")
print("Distribución:", df["cultivo"].value_counts().to_dict())

# ================================
# TARGET BINARIO
# ================================
df[TARGET] = df["cultivo"].apply(
    lambda x: 1 if x in ["vid", "frutales", "olivo"] else 0
)

print("Distribución binaria:", df[TARGET].value_counts().to_dict())

# ================================
# FEATURES
# ================================
X = df.drop(columns=["cultivo", TARGET], errors="ignore")
X = X.select_dtypes(include=[np.number])
y = df[TARGET]

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
# BALANCEO
# ================================
neg = (y_train == 0).sum()
pos = (y_train == 1).sum()
scale_pos_weight = neg / pos

print(f"\nScale_pos_weight: {scale_pos_weight:.3f}")

# ================================
# MODELO
# ================================
model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    eval_metric="logloss",
    scale_pos_weight=scale_pos_weight,
    random_state=RANDOM_STATE,
    n_jobs=-1
)

# ================================
# ENTRENAMIENTO
# ================================
print("\nEntrenando modelo...")
model.fit(X_train, y_train)

# ================================
# THRESHOLD ÓPTIMO
# ================================
probs = model.predict_proba(X_test)[:, 1]

fpr, tpr, thresholds = roc_curve(y_test, probs)
optimal_idx = np.argmax(tpr - fpr)
THRESHOLD = thresholds[optimal_idx]

print(f"\nThreshold óptimo: {THRESHOLD:.3f}")

# ================================
# PREDICCIÓN FINAL
# ================================
y_pred = (probs >= THRESHOLD).astype(int)

# ================================
# RESULTADOS
# ================================
print("\n=== RESULTADOS ===\n")

print(classification_report(y_test, y_pred))
print("Matriz de confusión:")
print(confusion_matrix(y_test, y_pred))

# ================================
# MÉTRICA CLAVE
# ================================
recall_cultivo = classification_report(
    y_test, y_pred, output_dict=True
)["1"]["recall"]

print(f"\nRecall CULTIVO (clave): {recall_cultivo:.3f}")

# ================================
# CROSS VALIDATION
# ================================
print("\nValidación cruzada (5 folds):")

cv = cross_val_score(
    model,
    X,
    y,
    cv=5,
    scoring="accuracy",
    n_jobs=-1
)

print(f"  Media: {cv.mean():.3f} ± {cv.std():.3f}")

# ================================
# GUARDAR MODELO + THRESHOLD + FEATURES
# ================================
os.makedirs("models", exist_ok=True)

joblib.dump(
    {
        "model": model,
        "threshold": THRESHOLD,
        "features": list(X.columns)
    },
    "models/clasificador_cultivo.pkl"
)

print("\nModelo guardado en models/clasificador_cultivo.pkl")
print("\n=== Proceso completado ===")
