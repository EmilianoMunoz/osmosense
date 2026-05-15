"""
Generación de features temporales diferenciales.

Crea diferencias entre meses consecutivos para cada índice espectral.
"""

import pandas as pd
import re

INPUT_PATH = "data/dataset_temporal.csv"
OUTPUT_PATH = "data/dataset_temporal_features.csv"


def extraer_info_columna(col):
    """
    Extrae:
    (feature_base, año, mes)

    Ej: ndvi_mean_2023_07 -> ("ndvi_mean", 2023, 7)
    """
    match = re.match(r"(.*)_(\d{4})_(\d{2})$", col)
    if match:
        base = match.group(1)
        anio = int(match.group(2))
        mes = int(match.group(3))
        return base, anio, mes
    return None


def main():
    print("Cargando dataset...")
    df = pd.read_csv(INPUT_PATH)
    print("Shape original:", df.shape)

    columnas = df.columns

    # agrupar columnas por tipo de feature
    features_dict = {}

    for col in columnas:
        info = extraer_info_columna(col)
        if info:
            base, anio, mes = info
            if base not in features_dict:
                features_dict[base] = []
            features_dict[base].append((col, anio, mes))

    nuevas_features = []

    print("\nGenerando diferencias temporales...")

    for base, cols in features_dict.items():
        # ordenar por fecha
        cols_sorted = sorted(cols, key=lambda x: (x[1], x[2]))

        for i in range(1, len(cols_sorted)):
            col_actual, a1, m1 = cols_sorted[i]
            col_prev, a0, m0 = cols_sorted[i - 1]

            nueva_col = f"{base}_diff_{a1}_{m1:02d}_{a0}_{m0:02d}"

            df[nueva_col] = df[col_actual] - df[col_prev]
            nuevas_features.append(nueva_col)

    print(f"Features nuevas creadas: {len(nuevas_features)}")

    print("\nShape final:", df.shape)

    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nGuardado en: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()