"""
Script de preparación del dataset de entrenamiento.

Toma el archivo original de IDEMendoza (parcelas_ide.geojson),
filtra las parcelas de San Rafael con cultivos vid, olivo y otros,
reproyecta las coordenadas y genera la muestra de entrenamiento.

Requisitos:
    - data/parcelas/parcelas_ide.geojson (descargado de IDEMendoza)
    - pip install pyproj

Outputs:
    - data/parcelas/san_rafael_vid_olivo_wgs84.geojson
    - data/parcelas/muestra_entrenamiento.geojson
"""

import json
import random
from collections import Counter
from pyproj import Transformer


# ── configuración ──────────────────────────────────────────────
RUTA_IDE     = "data/parcelas/parcelas_ide.geojson"
RUTA_WGS84   = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
RUTA_MUESTRA = "data/parcelas/muestra_entrenamiento.geojson"

MUESTRAS_POR_CLASE = 200
AREA_MINIMA        = 5000
RANDOM_SEED        = 42
CULTIVOS_OTROS     = ("ANUALES", "INCULTOS", "FRUTALES")

MIN_X, MAX_X = -7809842, -7430799
MIN_Y, MAX_Y = -4300897, -4038340


# ── funciones ──────────────────────────────────────────────────
def filtrar_san_rafael_completo(features: list) -> dict:
    """Filtra todas las parcelas de San Rafael por tipo de cultivo.

    Args:
        features: Lista de features del GeoJSON de IDEMendoza.

    Returns:
        Diccionario con listas de features por clase:
        'vid', 'olivo', 'otros'.
    """
    resultado = {"vid": [], "olivo": [], "otros": []}

    for f in features:
        cultivo = f["properties"]["tipo_culti"].strip()
        try:
            coords = f["geometry"]["coordinates"][0]
            en_sr = any(
                MIN_X <= x <= MAX_X and MIN_Y <= y <= MAX_Y
                for x, y in coords
            )
            if not en_sr:
                continue

            if cultivo == "VID":
                f["properties"]["cultivo"] = "vid"
                resultado["vid"].append(f)
            elif cultivo == "OLIVOS":
                f["properties"]["cultivo"] = "olivo"
                resultado["olivo"].append(f)
            elif cultivo in CULTIVOS_OTROS:
                f["properties"]["cultivo"] = "otros"
                resultado["otros"].append(f)
        except Exception:
            continue

    return resultado


def reproyectar_wgs84(features: list) -> list:
    """Reproyecta coordenadas de EPSG:3857 a EPSG:4326.

    Args:
        features: Lista de features en EPSG:3857.

    Returns:
        Lista de features con coordenadas en WGS84.
    """
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

    def convertir_anillo(anillo):
        return [list(transformer.transform(x, y)) for x, y in anillo]

    def convertir_geometria(geom):
        if geom["type"] == "Polygon":
            return {
                "type": "Polygon",
                "coordinates": [convertir_anillo(a) for a in geom["coordinates"]]
            }
        elif geom["type"] == "MultiPolygon":
            return {
                "type": "MultiPolygon",
                "coordinates": [
                    [convertir_anillo(a) for a in poligono]
                    for poligono in geom["coordinates"]
                ]
            }
        return geom

    convertidas = []
    for f in features:
        try:
            f["geometry"] = convertir_geometria(f["geometry"])
            convertidas.append(f)
        except Exception:
            continue
    return convertidas


def generar_muestra_tres_clases(clases: dict) -> list:
    """Genera muestra balanceada de tres clases filtrando parcelas pequeñas.

    Args:
        clases: Diccionario con listas de features por clase.

    Returns:
        Lista de features con muestra balanceada y IDs normalizados.
    """
    muestra_final = []
    prefijos = {"vid": "V", "olivo": "O", "otros": "X"}

    for clase, features in clases.items():
        validas = [
            f for f in features
            if f["properties"].get("shape_Area", 0) >= AREA_MINIMA
        ]
        print(f"{clase}: {len(features)} totales → {len(validas)} >= {AREA_MINIMA}m²")

        random.seed(RANDOM_SEED)
        muestra = random.sample(validas, min(MUESTRAS_POR_CLASE, len(validas)))

        prefijo = prefijos[clase]
        for i, f in enumerate(muestra):
            f["properties"]["id"] = f"{prefijo}{i+1:03d}"

        muestra_final.extend(muestra)
        print(f"  → {len(muestra)} seleccionadas")

    return muestra_final


def guardar_geojson(features: list, ruta: str) -> None:
    """Guarda una lista de features como GeoJSON.

    Args:
        features: Lista de features a guardar.
        ruta: Ruta del archivo de salida.
    """
    resultado = {"type": "FeatureCollection", "features": features}
    with open(ruta, "w") as f:
        json.dump(resultado, f)
    print(f"Guardado: {ruta} ({len(features)} features)")


# ── main ───────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=== Preparación del dataset de entrenamiento ===\n")

    print(f"Cargando {RUTA_IDE}...")
    with open(RUTA_IDE) as f:
        data = json.load(f)
    print(f"Total features IDE: {len(data['features'])}")

    print("\nFiltrando San Rafael...")
    clases = filtrar_san_rafael_completo(data["features"])
    for clase, features in clases.items():
        print(f"  {clase}: {len(features)} parcelas")

    todas = clases["vid"] + clases["olivo"] + clases["otros"]
    print(f"\nTotal a reproyectar: {len(todas)}")

    print("Reproyectando a WGS84...")
    en_wgs84 = reproyectar_wgs84(todas)

    clases_wgs84 = {
        "vid":   [f for f in en_wgs84 if f["properties"]["cultivo"] == "vid"],
        "olivo": [f for f in en_wgs84 if f["properties"]["cultivo"] == "olivo"],
        "otros": [f for f in en_wgs84 if f["properties"]["cultivo"] == "otros"],
    }

    guardar_geojson(en_wgs84, RUTA_WGS84)

    print("\nGenerando muestra de entrenamiento...")
    muestra = generar_muestra_tres_clases(clases_wgs84)
    guardar_geojson(muestra, RUTA_MUESTRA)

    print(f"\nDistribución final:")
    print(Counter(f["properties"]["cultivo"] for f in muestra))
    print("\n=== Dataset preparado ===")