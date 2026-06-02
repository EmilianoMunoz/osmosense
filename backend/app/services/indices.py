import ee
import pandas as pd
from datetime import datetime
import os

def calcular_indices(imagen: ee.Image) -> ee.Image:
    """Calcula índices espectrales sobre una imagen Sentinel-2.

    Calcula índices espectrales utilizando las bandas
    espectrales de Sentinel-2. Todos los índices se agregan como
    bandas adicionales a la imagen original.

    Índices calculados:
        - NDVI (B8-B4)/(B8+B4): vigor vegetativo general.
        - NDMI (B8-B11)/(B8+B11): contenido de agua foliar.
        - NDWI (B3-B8)/(B3+B8): contenido de agua superficial.
        - MSI B11/B8: estrés hídrico inverso al NDMI.
        - SAVI 1.5*(B8-B4)/(B8+B4+0.5): NDVI corregido por suelo.
        - NDRE (B8-B5)/(B8+B5): red-edge, sensible a clorofila
          y estructura del dosel. Discrimina tipos de vegetación.
        - GNDVI (B8-B3)/(B8+B3): vigor usando banda verde.
        - EVI: índice de vegetación mejorado, menos saturable que NDVI.
        - BSI: índice de suelo desnudo.
        - NBR (B8-B12)/(B8+B12): sensibilidad a sequedad/biomasa.
        - MTCI (B6-B5)/(B5-B4): gradiente red-edge.
        - IRECI (B7-B4)/(B5/B6): clorofila red-edge.

    Args:
        imagen: Imagen Sentinel-2 con bandas B2, B3, B4, B5,
            B6, B7, B8, B11 y B12.

    Returns:
        Imagen original con bandas adicionales.
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
    ndre = imagen.normalizedDifference(["B8", "B5"]).rename("NDRE")
    gndvi = imagen.normalizedDifference(["B8", "B3"]).rename("GNDVI")
    nbr = imagen.normalizedDifference(["B8", "B12"]).rename("NBR")
    evi = (
        imagen.expression(
            "2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)",
            {
                "NIR": imagen.select("B8"),
                "RED": imagen.select("B4"),
                "BLUE": imagen.select("B2"),
            },
        ).rename("EVI")
    )
    bsi = (
        imagen.expression(
            "((SWIR + RED) - (NIR + BLUE)) / ((SWIR + RED) + (NIR + BLUE) + 1e-6)",
            {
                "SWIR": imagen.select("B11"),
                "RED": imagen.select("B4"),
                "NIR": imagen.select("B8"),
                "BLUE": imagen.select("B2"),
            },
        ).rename("BSI")
    )
    mtci = (
        imagen.expression(
            "(B6 - B5) / (B5 - B4 + 1e-6)",
            {
                "B4": imagen.select("B4"),
                "B5": imagen.select("B5"),
                "B6": imagen.select("B6"),
            },
        ).rename("MTCI")
    )
    ireci = (
        imagen.expression(
            "(B7 - B4) / ((B5 / (B6 + 1e-6)) + 1e-6)",
            {
                "B4": imagen.select("B4"),
                "B5": imagen.select("B5"),
                "B6": imagen.select("B6"),
                "B7": imagen.select("B7"),
            },
        ).rename("IRECI")
    )

    return imagen.addBands([
        ndvi, ndmi, ndwi, msi, savi, ndre,
        gndvi, evi, bsi, nbr, mtci, ireci,
    ])


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
    bandas = [
        "NDVI", "NDMI", "NDWI", "MSI", "SAVI", "NDRE",
        "GNDVI", "EVI", "BSI", "NBR", "MTCI", "IRECI",
        "B2", "B3", "B4", "B5", "B6", "B7", "B8", "B11", "B12",
    ]
    stats = imagen.select(bandas).reduceRegion(
        reducer=(
            ee.Reducer.mean()
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
            .combine(ee.Reducer.minMax(), sharedInputs=True)
            .combine(ee.Reducer.count(), sharedInputs=True)
        ),
        geometry=geometria,
        scale=10,
        maxPixels=1e9
    ).getInfo()

    resultado = {
        "parcela_id": parcela.get("id", ""),
        "nombre":     parcela.get("nombre") or parcela.get("id", ""),
        "cultivo":    parcela.get("cultivo", ""),
        "fecha":      fecha,
    }

    for banda in bandas:
        prefijo = banda.lower()
        for stat in ["mean", "stdDev", "min", "max", "count"]:
            key = f"{banda}_{stat}"
            value = stats.get(key)
            if value is not None:
                resultado[f"{prefijo}_{stat}"] = round(value, 4)
                if stat == "mean":
                    resultado[prefijo] = round(value, 4)

    return resultado


def guardar_resultados(resultados: list, ruta: str = "backend/data/resultados_indices.csv") -> None:
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
