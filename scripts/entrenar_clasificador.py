from app.core.gee import inicializar_gee
from app.services.clasificador import (
    cargar_dataset,
    entrenar_clasificador,
    guardar_modelo,
)

if __name__ == "__main__":

    print("=== Entrenamiento del clasificador de cultivos ===\n")

    # cargar dataset
    df = cargar_dataset("data/dataset_vid_olivo.csv")

    # entrenar
    modelo, le, reporte = entrenar_clasificador(df)

    # guardar
    guardar_modelo(modelo, le)

    print("\n=== Entrenamiento completado ===")
