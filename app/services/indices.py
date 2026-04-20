import ee
import pandas as pd
from datetime import datetime
import os

def calcular_indices(imagen: ee.Image) -> ee.Image:
    """Calcula índices espectrales sobre una imagen Sentinel-2.

    Calcula NDVI, NDMI, NDWI, MSI y SAVI utilizando las bandas
    espectrales de Sentinel-2. Todos los índices se agregan como
    bandas adicionales a la imagen original.

    Args:
        imagen: Imagen Sentinel-2 con bandas B3, B4, B8 y B11.

    Returns:
        Imagen original con bandas adicionales: NDVI, NDMI, NDWI,
        MSI y SAVI.
    """
    ndvi = imagen.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndmi = imagen.normalizedDifference(["B8", "B11"]).rename("NDMI")
    ndwi = imagen.normalizedDifference(["B3", "B8"]).rename("NDWI")
    msi  = imagen.select("B11").divide(imagen.select("B8")).rename("MSI")
    savi = (
        imagen.expression(
            "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
            {"NIR": imagen.select("B8"), "RED": imagen.select("B4")}
        ).rename("SAVI")
    )
    return imagen.addBands([ndvi, ndmi, ndwi, msi, savi])


def extraer_estadisticas(
    imagen: ee.Image,
    parcela: dict,
    geometria: ee.Geometry,
    fecha: str
) -> dict:
    """Extrae estadísticas de índices espectrales para una parcela.

    Args:
        imagen: Imagen Sentinel-2 con índices ya calculados.
        parcela: Diccionario con propiedades de la parcela.
        geometria: Polígono ee.Geometry de la parcela.
        fecha: Fecha de referencia en formato 'YYYY-MM-DD'.

    Returns:
        Diccionario con id, nombre, cultivo, fecha y valor medio
        de cada índice (NDVI, NDMI, NDWI, MSI, SAVI).
    """
    stats = imagen.select(["NDVI", "NDMI", "NDWI", "MSI", "SAVI"]).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometria,
        scale=10,
        maxPixels=1e9
    ).getInfo()

    return {
        "parcela_id": parcela["id"],
        "nombre":     parcela["nombre"],
        "cultivo":    parcela["cultivo"],
        "fecha":      fecha,
        "ndvi":       round(stats.get("NDVI") or 0, 4),
        "ndmi":       round(stats.get("NDMI") or 0, 4),
        "ndwi":       round(stats.get("NDWI") or 0, 4),
        "msi":        round(stats.get("MSI")  or 0, 4),
        "savi":       round(stats.get("SAVI") or 0, 4),
    }


def guardar_resultados(resultados: list, ruta: str = "data/resultados_indices.csv") -> None:
    """Guarda los resultados de índices espectrales en un archivo CSV.

    Si el archivo ya existe, agrega los nuevos resultados sin
    sobreescribir los anteriores. Si no existe, lo crea.

    Args:
        resultados: Lista de diccionarios con resultados por parcela.
        ruta: Ruta del archivo CSV de salida. Default
            'data/resultados_indices.csv'.

    Returns:
        None
    """
    df_nuevo = pd.DataFrame(resultados)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)

    if os.path.exists(ruta):
        df_existente = pd.read_csv(ruta)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo

    df_final.to_csv(ruta, index=False)
    print(f"Resultados guardados en {ruta} ({len(df_nuevo)} registros nuevos)")