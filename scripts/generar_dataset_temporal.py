import pandas as pd

# ─────────────────────────────────────────────
# configuración
# ─────────────────────────────────────────────

INPUT_CSV = "data/dataset_vid_olivo.csv"
OUTPUT_CSV = "data/dataset_temporal.csv"

FEATURES = [
    "ndvi_mean",
    "ndvi_std",
    "ndvi_min",
    "ndvi_max",

    "ndmi_mean",
    "ndmi_std",

    "ndwi_mean",
    "ndwi_std",

    "msi_mean",
    "msi_std",

    "savi_mean",
    "savi_std",

    "ndre_mean",
    "ndre_std",

    "b2_mean",
    "b3_mean",
    "b4_mean",
    "b5_mean",
    "b6_mean",
    "b7_mean",
    "b8_mean",
    "b11_mean",
]

# ─────────────────────────────────────────────
# cargar dataset
# ─────────────────────────────────────────────

print("Cargando dataset...")
df = pd.read_csv(INPUT_CSV)

print(f"Muestras originales: {len(df)}")

# ordenar para consistencia
df = df.sort_values(["parcela_id", "anio", "mes"])

# ─────────────────────────────────────────────
# pivot temporal
# ─────────────────────────────────────────────

filas = []

parcelas = df["parcela_id"].unique()

print(f"Parcelas únicas: {len(parcelas)}")

for parcela_id in parcelas:

    grupo = df[df["parcela_id"] == parcela_id]

    fila = {
        "parcela_id": parcela_id,
        "cultivo": grupo.iloc[0]["cultivo"]
    }

    # crear features temporales
    for _, row in grupo.iterrows():

        anio = int(row["anio"])
        mes = int(row["mes"])

        periodo = f"{anio}_{mes:02d}"

        for feature in FEATURES:

            columna = f"{feature}_{periodo}"

            fila[columna] = row[feature]

    filas.append(fila)

# ─────────────────────────────────────────────
# dataframe final
# ─────────────────────────────────────────────

df_temporal = pd.DataFrame(filas)

# reemplazar NaN por 0
df_temporal = df_temporal.fillna(0)

print(f"\nDataset temporal generado:")
print(df_temporal.shape)

print("\nDistribución:")
print(df_temporal["cultivo"].value_counts())

# guardar
df_temporal.to_csv(OUTPUT_CSV, index=False)

print(f"\nGuardado en:")
print(OUTPUT_CSV)