import json
import ee
import numpy as np
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

# generar períodos mensuales para 2023 y 2024
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
            if mes == 12:
                fecha_fin = f"{anio}-12-31"
            else:
                import calendar
                ultimo_dia = calendar.monthrange(anio, mes)[1]
                fecha_fin = f"{anio}-{mes:02d}-{ultimo_dia}"
            etiqueta = f"{anio}-M{mes:02d}"
            periodos.append((fecha_inicio, fecha_fin, etiqueta, mes, anio))
    return periodos


if __name__ == "__main__":

    inicializar_gee()

    with open("data/parcelas/muestra_entrenamiento.geojson") as f:
        geojson = json.load(f)

    parcelas = geojson["features"]
    print(f"Parcelas cargadas: {len(parcelas)}")

    from collections import Counter
    print(f"Distribución: {Counter(f['properties']['cultivo'] for f in parcelas)}")

    geometria_sr = obtener_geometria_san_rafael()
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
                # agregar mes y año para codificación circular
                resultado["mes"] = mes
                resultado["anio"] = anio
                resultado["mes_sin"] = round(np.sin(2 * np.pi * mes / 12), 4)
                resultado["mes_cos"] = round(np.cos(2 * np.pi * mes / 12), 4)
                resultados_periodo.append(resultado)
            except Exception as e:
                errores.append(props.get("id", ""))

        print(f"  ✓ {len(resultados_periodo)}/{len(parcelas)} procesadas")
        if errores:
            print(f"  Con errores: {len(errores)}")

        todos_resultados.extend(resultados_periodo)

    print(f"\nTotal muestras generadas: {len(todos_resultados)}")
    guardar_resultados(todos_resultados, "data/dataset_vid_olivo.csv")