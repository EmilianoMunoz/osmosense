import pandas as pd
import numpy as np
import re

INPUT = "data/dataset_hibrido_mejorado.csv"
OUTPUT = "data/dataset_fenologico.csv"

print("Cargando dataset...")
df = pd.read_csv(INPUT)
print("Shape original:", df.shape)

# ================================
# 1. DETECTAR COLUMNAS NDVI
# ================================
ndvi_cols = [
    col for col in df.columns
    if re.match(r"ndvi_mean_\d{4}_\d{2}$", col)
]

print(f"Columnas NDVI detectadas: {len(ndvi_cols)}")

if len(ndvi_cols) < 6:
    raise ValueError("Pocas columnas NDVI detectadas")

# ================================
# 2. ORDENAR CRONOLÓGICAMENTE
# ================================
ndvi_cols = sorted(
    ndvi_cols,
    key=lambda x: (int(x.split("_")[-2]), int(x.split("_")[-1]))
)

ndvi_values = df[ndvi_cols].values
meses = np.array([int(col.split("_")[-1]) for col in ndvi_cols])

# ================================
# 3. FEATURES BASE (vectorizadas)
# ================================
features = {}

features["ndvi_max_year"] = np.max(ndvi_values, axis=1)
features["ndvi_min_year"] = np.min(ndvi_values, axis=1)
features["ndvi_amp_year"] = features["ndvi_max_year"] - features["ndvi_min_year"]
features["ndvi_mean_year"] = np.mean(ndvi_values, axis=1)
features["ndvi_std_year"] = np.std(ndvi_values, axis=1)

# ================================
# 4. PICO
# ================================
features["ndvi_peak_month"] = meses[np.argmax(ndvi_values, axis=1)]
features["ndvi_peak_month_norm"] = features["ndvi_peak_month"] / 12

# ================================
# 5. SLOPE GLOBAL
# ================================
x = np.arange(len(ndvi_cols))
features["ndvi_slope"] = np.apply_along_axis(
    lambda y: np.polyfit(x, y, 1)[0],
    1,
    ndvi_values
)

# ================================
# 6. VARIABILIDAD
# ================================
features["ndvi_coeff_var"] = (
    features["ndvi_std_year"] / (features["ndvi_mean_year"] + 1e-6)
)

# ================================
# 7. DINÁMICA TEMPORAL
# ================================
diffs = np.diff(ndvi_values, axis=1)

features["ndvi_diff_mean"] = np.mean(diffs, axis=1)
features["ndvi_diff_std"] = np.std(diffs, axis=1)
features["ndvi_diff_max"] = np.max(diffs, axis=1)
features["ndvi_diff_min"] = np.min(diffs, axis=1)

features["ndvi_max_growth"] = np.max(diffs, axis=1)
features["ndvi_max_decline"] = np.min(diffs, axis=1)

features["ndvi_growth_total"] = np.sum(diffs.clip(min=0), axis=1)
features["ndvi_decline_total"] = np.sum(diffs.clip(max=0), axis=1)

features["ndvi_growth_balance"] = (
    features["ndvi_growth_total"] /
    (np.abs(features["ndvi_decline_total"]) + 1e-6)
)

features["ndvi_temporal_var"] = np.var(diffs, axis=1)

# ================================
# 8. SHAPE (MUY IMPORTANTES)
# ================================
features["ndvi_peak_sharpness"] = (
    features["ndvi_max_year"] - features["ndvi_mean_year"]
)

features["ndvi_peak_ratio"] = (
    features["ndvi_max_year"] / (features["ndvi_min_year"] + 1e-6)
)

# simetría
mid = len(ndvi_cols) // 2
left = np.mean(ndvi_values[:, :mid], axis=1)
right = np.mean(ndvi_values[:, mid:], axis=1)

features["ndvi_symmetry"] = left - right

# ================================
# 9. ESTACIONALIDAD
# ================================
verano_idx = [i for i, m in enumerate(meses) if m in [12, 1, 2]]
invierno_idx = [i for i, m in enumerate(meses) if m in [6, 7, 8]]
primavera_idx = [i for i, m in enumerate(meses) if m in [9, 10, 11]]

if verano_idx and invierno_idx:
    ndvi_ver = np.mean(ndvi_values[:, verano_idx], axis=1)
    ndvi_inv = np.mean(ndvi_values[:, invierno_idx], axis=1)

    features["ndvi_diff_verano_invierno"] = ndvi_ver - ndvi_inv
    features["ndvi_verano_invierno_ratio"] = ndvi_ver / (ndvi_inv + 1e-6)

if verano_idx and primavera_idx:
    ndvi_ver = np.mean(ndvi_values[:, verano_idx], axis=1)
    ndvi_prim = np.mean(ndvi_values[:, primavera_idx], axis=1)

    features["ndvi_primavera_verano_diff"] = ndvi_ver - ndvi_prim

# ================================
# 10. CONCATENAR TODO (SIN FRAGMENTACIÓN)
# ================================
features_df = pd.DataFrame(features)

df = pd.concat([df, features_df], axis=1)

# ================================
# 11. GUARDAR
# ================================
print("Features avanzadas agregadas")

df.to_csv(OUTPUT, index=False)

print("Guardado en:", OUTPUT)
print("Nuevo shape:", df.shape)

print("\n=== Proceso completado ===")