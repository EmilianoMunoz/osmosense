"""
Generación de features fenológicas a partir de series temporales.

A partir de variables tipo:
ndvi_mean_2023_01, ndvi_mean_2023_02, ...

Se generan:

- pico (max)
- valle (min)
- amplitud
- mes de pico
- mes de valle
- pendiente de crecimiento
- pendiente de caída

Estas features capturan comportamiento temporal real del cultivo.
"""

import pandas as pd
import numpy as np
import re


INPUT_PATH = "data/dataset_temporal.csv"
OUTPUT_PATH = "data/dataset_fenologico.csv"


def extraer_series(df, variable):
    """Extrae columnas de una variable ordenadas temporalmente."""
    
    pattern = re.compile(f"{variable}_mean_(\\d{{4}})_(\\d{{2}})")
    
    cols = []
    fechas = []

    for col in df.columns:
        match = pattern.match(col)
        if match:
            year, month = match.groups()
            cols.append(col)
            fechas.append(f"{year}_{month}")

    # ordenar por fecha
    orden = sorted(zip(cols, fechas), key=lambda x: x[1])
    cols_ordenadas = [c for c, _ in orden]

    return df[cols_ordenadas], cols_ordenadas


def calcular_features_fenologicas(df, variable):
    """Calcula features fenológicas para una variable."""
    
    serie_df, cols = extraer_series(df, variable)

    values = serie_df.values

    # manejo NaN
    values = np.nan_to_num(values, nan=0.0)

    # métricas básicas
    max_val = values.max(axis=1)
    min_val = values.min(axis=1)
    amplitude = max_val - min_val

    # índices de tiempo
    idx_max = values.argmax(axis=1)
    idx_min = values.argmin(axis=1)

    # pendiente (aproximada)
    diff = np.diff(values, axis=1)

    growth = diff.max(axis=1)
    senescence = diff.min(axis=1)

    return pd.DataFrame({
        f"{variable}_max": max_val,
        f"{variable}_min": min_val,
        f"{variable}_amplitude": amplitude,
        f"{variable}_peak_idx": idx_max,
        f"{variable}_valley_idx": idx_min,
        f"{variable}_growth": growth,
        f"{variable}_senescence": senescence,
    })


if __name__ == "__main__":

    print("=== Generación de features fenológicas ===\n")

    df = pd.read_csv(INPUT_PATH)
    print(f"Dataset original: {df.shape}")

    # variables clave (no metas todas, esto es importante)
    variables = [
        "ndvi",
        "ndmi",
        "ndwi",
        "savi",
        "ndre"
    ]

    features_list = []

    for var in variables:
        print(f"Procesando {var}...")
        f = calcular_features_fenologicas(df, var)
        features_list.append(f)

    df_feno = pd.concat(features_list, axis=1)

    # unir con metadata
    meta_cols = ["parcela_id", "cultivo"]
    df_meta = df[[c for c in meta_cols if c in df.columns]]

    df_final = pd.concat([df_meta, df_feno], axis=1)

    print(f"Dataset fenológico: {df_final.shape}")

    df_final.to_csv(OUTPUT_PATH, index=False)
    print(f"Guardado en {OUTPUT_PATH}")

    print("\n=== Proceso completado ===")