import pandas as pd
import numpy as np

INPUT = "data/dataset_temporal.csv"
OUTPUT = "data/dataset_hibrido.csv"

# usamos solo señales "mean" (más estables)
INDICES = [
    "ndvi_mean",
    "ndmi_mean",
    "ndwi_mean",
    "savi_mean",
    "ndre_mean",
    "msi_mean"
]

print("Cargando dataset...")
df = pd.read_csv(INPUT)

print(f"Shape original: {df.shape}")

# columnas metadata (robusto)
meta_cols = [c for c in ["parcela_id", "nombre", "cultivo"] if c in df.columns]
df_meta = df[meta_cols]

# resto de features originales
df_original = df.drop(columns=meta_cols, errors="ignore")

# ============================
# FEATURES TEMPORALES AGREGADAS
# ============================

features_temporales = {}

for idx in INDICES:
    cols_idx = [c for c in df.columns if c.startswith(idx)]

    if not cols_idx:
        continue

    print(f"Procesando {idx} ({len(cols_idx)} columnas)")

    valores = df[cols_idx].values

    features_temporales[f"{idx}_max"] = np.max(valores, axis=1)
    features_temporales[f"{idx}_min"] = np.min(valores, axis=1)
    features_temporales[f"{idx}_mean_year"] = np.mean(valores, axis=1)
    features_temporales[f"{idx}_std_year"] = np.std(valores, axis=1)
    features_temporales[f"{idx}_amp"] = (
        features_temporales[f"{idx}_max"] -
        features_temporales[f"{idx}_min"]
    )

    # pendiente simple
    features_temporales[f"{idx}_slope"] = (
        valores[:, -1] - valores[:, 0]
    )

# dataframe de agregadas
df_features = pd.DataFrame(features_temporales)

# ============================
# UNIÓN FINAL (LA CLAVE)
# ============================

df_final = pd.concat([
    df_meta,
    df_original,
    df_features
], axis=1)

print("\nDataset híbrido generado:")
print(df_final.shape)

df_final.to_csv(OUTPUT, index=False)

print(f"\nGuardado en: {OUTPUT}")