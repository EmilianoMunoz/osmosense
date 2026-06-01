import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import classification_report, confusion_matrix

# ================================
# CONFIG
# ================================
DATA_PATH = "data/test_final.csv"

# ================================
# CARGAR MODELOS
# ================================
print("Cargando modelos...")

# --- Modelo 1: cultivo vs no cultivo ---
data_cultivo = joblib.load("models/clasificador_cultivo.pkl")
modelo_cultivo = data_cultivo["model"]
THRESHOLD_CULTIVO = data_cultivo["threshold"]
FEATURES_CULTIVO = data_cultivo["features"]

# --- Modelo 2: olivo vs resto ---
data_olivo = joblib.load("models/clasificador_olivo.pkl")
modelo_olivo = data_olivo["model"]
THRESHOLD_OLIVO = data_olivo["threshold"]
FEATURES_OLIVO = data_olivo["features"]

# --- Modelo 3: vid vs frutales ---
data_vid = joblib.load("models/clasificador_vid_frutales.pkl")
modelo_vid = data_vid["model"]
THRESHOLD_VID = data_vid["threshold"]
FEATURES_VID = data_vid["features"]

print("Modelos cargados correctamente\n")

# ================================
# CARGAR DATASET
# ================================
df = pd.read_csv(DATA_PATH)

print(f"Dataset: {len(df)} muestras")
print("Distribución real:", df["cultivo"].value_counts().to_dict())

# ================================
# FEATURES BASE
# ================================
X = df.drop(columns=["cultivo"], errors="ignore")
X = X.select_dtypes(include=[np.number])

y_true = df["cultivo"].values

# ================================
# PIPELINE DE PREDICCIÓN
# ================================
predicciones = []

for i in range(len(X)):
    x = X.iloc[[i]]

    # =========================
    # 1. CULTIVO vs NO CULTIVO
    # =========================
    x_cultivo = x.reindex(columns=FEATURES_CULTIVO, fill_value=0)

    prob_cultivo = modelo_cultivo.predict_proba(x_cultivo)[0][1]

    if prob_cultivo < THRESHOLD_CULTIVO:
        predicciones.append("no_cultivo")
        continue

    # =========================
    # 2. OLIVO vs RESTO
    # =========================
    x_olivo = x.reindex(columns=FEATURES_OLIVO, fill_value=0)

    prob_olivo = modelo_olivo.predict_proba(x_olivo)[0][1]

    if prob_olivo >= THRESHOLD_OLIVO:
        predicciones.append("olivo")
        continue

    # =========================
    # 3. VID vs FRUTALES
    # =========================
    x_vid = x.reindex(columns=FEATURES_VID, fill_value=0)

    prob_vid = modelo_vid.predict_proba(x_vid)[0][1]

    if prob_vid >= THRESHOLD_VID:
        predicciones.append("vid")
    else:
        predicciones.append("frutales")

# ================================
# NORMALIZAR CLASES REALES
# ================================
def mapear_clase_real(x):
    if x in ["vid", "frutales", "olivo"]:
        return x
    else:
        return "no_cultivo"

y_true_mapped = [mapear_clase_real(x) for x in y_true]

# ================================
# RESULTADOS
# ================================
print("\n=== RESULTADOS PIPELINE COMPLETO ===\n")

print(classification_report(y_true_mapped, predicciones))

print("Matriz de confusión:")
print(confusion_matrix(y_true_mapped, predicciones))

# ================================
# ACCURACY GLOBAL
# ================================
accuracy = np.mean(np.array(predicciones) == np.array(y_true_mapped))
print(f"\nAccuracy global pipeline: {accuracy:.4f}")

# ================================
# ANÁLISIS DE ERRORES
# ================================
df_resultados = df.copy()
df_resultados["real"] = y_true_mapped
df_resultados["pred"] = predicciones

errores = df_resultados[df_resultados["real"] != df_resultados["pred"]]

print(f"\nTotal errores: {len(errores)}")

print("\nErrores por clase real:")
print(errores["real"].value_counts())

print("\nErrores por predicción:")
print(errores["pred"].value_counts())
