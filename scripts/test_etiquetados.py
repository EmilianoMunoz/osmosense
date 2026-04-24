import json
import ee
import numpy as np
import calendar
from app.core.gee import inicializar_gee
from app.services.images import (
    obtener_geometria_san_rafael,
    obtener_imagenes_sentinel,
    obtener_imagen_compuesta,
)
from app.services.indices import (
    calcular_indices,
    guardar_resultados,
)


def generar_periodos_mensuales(anios: list) -> list:
    """Genera lista de períodos mensuales para los años indicados.

    Args:
        anios: Lista de años a procesar.

    Returns:
        Lista de tuplas (fecha_inicio, fecha_fin, etiqueta, mes, anio).
    """
    periodos = []
    for anio in anios:
        for mes in range(1, 13):
            fecha_inicio = f"{anio}-{mes:02d}-01"
            ultimo_dia   = calendar.monthrange(anio, mes)[1]
            fecha_fin    = f"{anio}-{mes:02d}-{ultimo_dia}"
            etiqueta     = f"{anio}-M{mes:02d}"
            periodos.append((fecha_inicio, fecha_fin, etiqueta, mes, anio))
    return periodos


def extraer_estadisticas_batch(
    imagen: ee.Image,
    parcelas_fc: ee.FeatureCollection,
    fecha: str,
    mes: int,
    anio: int
) -> list:
    """Extrae estadísticas para todas las parcelas en una sola llamada a GEE.

    Usa reduceRegions para procesar todas las parcelas del lado del
    servidor en lugar de una llamada por parcela, reduciendo
    drásticamente el tiempo de procesamiento.

    Args:
        imagen: Imagen Sentinel-2 con índices calculados.
        parcelas_fc: FeatureCollection de GEE con todas las parcelas.
        fecha: Etiqueta del período (ej: '2023-M01').
        mes: Número de mes (1-12).
        anio: Año (ej: 2023).

    Returns:
        Lista de diccionarios con índices y metadatos por parcela.
    """
    stats = imagen.select([
        "NDVI", "NDMI", "NDWI", "MSI", "SAVI",
        "B2", "B3", "B4", "B8", "B11"
    ]).reduceRegions(
        collection=parcelas_fc,
        reducer=ee.Reducer.mean(),
        scale=10
    )

    resultados_gee = stats.getInfo()

    lista = []
    for feature in resultados_gee["features"]:
        props = feature["properties"]
        lista.append({
            "parcela_id": props.get("id", ""),
            "nombre":     props.get("id", ""),
            "cultivo":    props.get("cultivo", ""),
            "fecha":      fecha,
            "ndvi":       round(props.get("NDVI") or 0, 4),
            "ndmi":       round(props.get("NDMI") or 0, 4),
            "ndwi":       round(props.get("NDWI") or 0, 4),
            "msi":        round(props.get("MSI")  or 0, 4),
            "savi":       round(props.get("SAVI") or 0, 4),
            "b2":         round(props.get("B2")   or 0, 4),
            "b3":         round(props.get("B3")   or 0, 4),
            "b4":         round(props.get("B4")   or 0, 4),
            "b8":         round(props.get("B8")   or 0, 4),
            "b11":        round(props.get("B11")  or 0, 4),
            "mes":        mes,
            "anio":       anio,
            "mes_sin":    round(np.sin(2 * np.pi * mes / 12), 4),
            "mes_cos":    round(np.cos(2 * np.pi * mes / 12), 4),
        })
    return lista


if __name__ == "__main__":

    inicializar_gee()

    # cargar parcelas
    with open("data/parcelas/muestra_entrenamiento.geojson") as f:
        geojson = json.load(f)

    parcelas = geojson["features"]
    print(f"Parcelas cargadas: {len(parcelas)}")

    from collections import Counter
    print(f"Distribución: {Counter(f['properties']['cultivo'] for f in parcelas)}")

    # convertir a FeatureCollection de GEE
    parcelas_fc = ee.FeatureCollection([
        ee.Feature(
            ee.Geometry(f["geometry"]),
            f["properties"]
        ) for f in parcelas
    ])
    print(f"FeatureCollection creada con {parcelas_fc.size().getInfo()} features")

    geometria_sr  = obtener_geometria_san_rafael()
    todos_resultados = []
    periodos = generar_periodos_mensuales([2023, 2024])
    print(f"\nPeríodos a procesar: {len(periodos)} meses")

    for fecha_inicio, fecha_fin, etiqueta, mes, anio in periodos:
        print(f"\nProcesando {etiqueta} ({fecha_inicio} → {fecha_fin})...")

        coleccion = obtener_imagenes_sentinel(
            geometria=geometria_sr,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            umbral_nubosidad=20.0
        )

        cantidad = coleccion.size().getInfo()
        if cantidad == 0:
            print(f"  Sin imágenes disponibles, saltando...")
            continue

        print(f"  {cantidad} imágenes disponibles")
        imagen = obtener_imagen_compuesta(coleccion, geometria_sr)
        imagen_con_indices = calcular_indices(imagen)

        try:
            resultados_periodo = extraer_estadisticas_batch(
                imagen_con_indices,
                parcelas_fc,
                etiqueta,
                mes,
                anio
            )
            print(f"  ✓ {len(resultados_periodo)}/{len(parcelas)} procesadas")
            todos_resultados.extend(resultados_periodo)
        except Exception as e:
            print(f"  ✗ Error en {etiqueta}: {e}")

    print(f"\nTotal muestras generadas: {len(todos_resultados)}")
    guardar_resultados(todos_resultados, "data/dataset_vid_olivo.csv")