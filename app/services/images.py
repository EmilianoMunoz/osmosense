import ee

def obtener_geometria_san_rafael() -> ee.Geometry:
    coleccion = (
        ee.FeatureCollection("FAO/GAUL/2015/level2")
        .filter(ee.Filter.And(
            ee.Filter.eq("ADM1_NAME", "Mendoza"),
            ee.Filter.eq("ADM2_NAME", "San Rafael")
        ))
    )
    if coleccion.size().getInfo() == 0:
        raise Exception("No se encontró San Rafael en la capa GAUL.")
    return coleccion.first().geometry()


def obtener_imagenes_sentinel(
    geometria: ee.Geometry,
    fecha_inicio: str,
    fecha_fin: str,
    umbral_nubosidad: float = 20.0
) -> ee.ImageCollection:
    coleccion = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(geometria)
        .filterDate(fecha_inicio, fecha_fin)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", umbral_nubosidad))
        .select(["B2", "B3", "B4", "B8", "B11", "B12"])
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )
    return coleccion


def resumen_coleccion(coleccion: ee.ImageCollection) -> None:
    cantidad = coleccion.size().getInfo()
    print(f"Imágenes disponibles: {cantidad}")

    if cantidad == 0:
        print("No hay imágenes para el rango y filtros indicados.")
        return

    mejor = coleccion.first()
    fecha = mejor.date().format("YYYY-MM-dd").getInfo()
    nubes = mejor.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
    bandas = mejor.bandNames().getInfo()

    print(f"Mejor imagen  → fecha: {fecha} | nubosidad: {nubes:.1f}%")
    print(f"Bandas seleccionadas: {bandas}")