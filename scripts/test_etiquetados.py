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

PERIODOS = [
    ("2024-01-01", "2024-03-31", "2024-T1"),
    ("2024-04-01", "2024-06-30", "2024-T2"),
    ("2024-07-01", "2024-09-30", "2024-T3"),
    ("2024-10-01", "2024-12-31", "2024-T4"),
]

if __name__ == "__main__":

    inicializar_gee()

    with open("data/parcelas/parcelas_etiquetadas.geojson") as f:
        geojson = json.load(f)

    parcelas = geojson["features"]
    print(f"Parcelas cargadas: {len(parcelas)}")

    geometria_sr = obtener_geometria_san_rafael()
    todos_resultados = []

    for fecha_inicio, fecha_fin, etiqueta in PERIODOS:
        print(f"\nProcesando período {etiqueta} ({fecha_inicio} → {fecha_fin})...")

        coleccion = obtener_imagenes_sentinel(
            geometria=geometria_sr,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            umbral_nubosidad=20.0
        )

        cantidad = coleccion.size().getInfo()
        if cantidad == 0:
            print(f"  Sin imágenes disponibles para {etiqueta}, saltando...")
            continue

        print(f"  {cantidad} imágenes disponibles")
        imagen = obtener_imagen_compuesta(coleccion, geometria_sr)
        imagen_con_indices = calcular_indices(imagen)

        resultados_periodo = []
        errores = []

        for feature in parcelas:
            props = feature["properties"]
            try:
                geometria_parcela = ee.Geometry(feature["geometry"])
                resultado = extraer_estadisticas(
                    imagen_con_indices,
                    props,
                    geometria_parcela,
                    fecha=etiqueta
                )
                resultados_periodo.append(resultado)
            except Exception as e:
                errores.append(props.get("id", ""))
                print(f"  ✗ {props.get('id')} → Error: {e}")

        print(f"  ✓ {len(resultados_periodo)}/{len(parcelas)} parcelas procesadas")
        if errores:
            print(f"  Con errores: {errores}")

        todos_resultados.extend(resultados_periodo)

    print(f"\nTotal de muestras generadas: {len(todos_resultados)}")
    guardar_resultados(todos_resultados, "data/dataset_vid_olivo.csv")