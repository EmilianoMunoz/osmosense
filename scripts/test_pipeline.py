import json
import ee
from app.core.gee import inicializar_gee
from app.services.images import (
    obtener_geometria_san_rafael,
    obtener_imagenes_sentinel,
    obtener_imagen_compuesta,
)
from app.services.indices import (
    calcular_indices,
    extraer_estadisticas,
    guardar_resultados,
)

if __name__ == "__main__":

    # Paso 1 — inicializar GEE
    inicializar_gee()

    # Paso 2 — cargar parcelas ficticias
    with open("data/parcelas/parcelas_prueba.geojson") as f:
        geojson = json.load(f)

    parcelas = geojson["features"]
    print(f"\nParcelas cargadas: {len(parcelas)}")

    # Paso 3 — obtener zona de interés
    print("\nObteniendo geometría de San Rafael...")
    geometria_sr = obtener_geometria_san_rafael()

    # Paso 4 — traer imágenes filtradas
    print("Buscando imágenes Sentinel-2...")
    coleccion = obtener_imagenes_sentinel(
        geometria=geometria_sr,
        fecha_inicio="2024-01-01",
        fecha_fin="2024-03-31",
        umbral_nubosidad=20.0
    )

    # Paso 5 — generar imagen compuesta
    cantidad = coleccion.size().getInfo()
    print(f"Generando imagen compuesta con {cantidad} imágenes...")
    imagen = obtener_imagen_compuesta(coleccion, geometria_sr)

    # Paso 6 — calcular índices
    imagen_con_indices = calcular_indices(imagen)

    # Paso 7 — extraer estadísticas por parcela
    fecha_referencia = "2024-01-01/2024-03-31"

    print("\nExtrayendo índices por parcela:")
    resultados = []

    for feature in parcelas:
        props = feature["properties"]
        geometria_parcela = ee.Geometry(feature["geometry"])

        resultado = extraer_estadisticas(
            imagen_con_indices,
            props,
            geometria_parcela,
            fecha=fecha_referencia
        )
        resultados.append(resultado)

        print(f"  {props['id']} ({props['cultivo']}) → "
              f"NDVI: {resultado['ndvi']} | "
              f"NDMI: {resultado['ndmi']} | "
              f"MSI: {resultado['msi']}")

    # Paso 8 — guardar resultados
    print("\nGuardando resultados...")
    guardar_resultados(resultados)