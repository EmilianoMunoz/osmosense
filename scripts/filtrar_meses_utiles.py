import pandas as pd

# dataset original
RUTA_INPUT = "data/dataset_vid_olivo.csv"

# nuevo dataset filtrado
RUTA_OUTPUT = "data/dataset_vid_olivo_verano.csv"

# meses útiles
MESES_VALIDOS = [10, 11, 12, 1, 2, 3]

print("Cargando dataset...")
df = pd.read_csv(RUTA_INPUT)

print(f"Muestras originales: {len(df)}")

# filtrar meses
df_filtrado = df[df["mes"].isin(MESES_VALIDOS)]

print(f"Muestras filtradas: {len(df_filtrado)}")

print("\nDistribución por mes:")
print(df_filtrado["mes"].value_counts().sort_index())

print("\nDistribución por cultivo:")
print(df_filtrado["cultivo"].value_counts())

# guardar
df_filtrado.to_csv(RUTA_OUTPUT, index=False)

print(f"\nDataset guardado en:")
print(RUTA_OUTPUT)