from app.core.gee import inicializar_gee
from app.services.images import (
    obtener_geometria_san_rafael,
    obtener_imagenes_sentinel,
    resumen_coleccion
)

if __name__ == "__main__":

    inicializar_gee()

    print("\nObteniendo geometría de San Rafael...")
    geometria = obtener_geometria_san_rafael()
    print("Geometría obtenida correctamente")

    print("\nBuscando imágenes Sentinel-2...")
    coleccion = obtener_imagenes_sentinel(
        geometria=geometria,
        fecha_inicio="2024-01-01",
        fecha_fin="2024-03-31",
        umbral_nubosidad=20.0
    )

    print("\nResumen de la colección:")
    resumen_coleccion(coleccion)