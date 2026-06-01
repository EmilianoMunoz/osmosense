import argparse
import sys
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.region import filtrar_gdf_san_rafael, limite_san_rafael_existe
from scripts.recalcular_dataset_desde_ide import normalizar_cultivo


INPUT_PARCELAS = "data/parcelas/parcelas_ide.geojson"
OUTPUT_COMPLETO = "data/parcelas/san_rafael_completo_wgs84.geojson"
OUTPUT_VID_OLIVO = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstruye capas de parcelas de San Rafael desde IDEMendoza."
    )
    parser.add_argument("--input", default=INPUT_PARCELAS)
    parser.add_argument("--output-completo", default=OUTPUT_COMPLETO)
    parser.add_argument("--output-vid-olivo", default=OUTPUT_VID_OLIVO)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gdf = gpd.read_file(args.input)
    if gdf.crs is None:
        raise RuntimeError(f"El archivo no tiene CRS definido: {args.input}")
    gdf = gdf.to_crs("EPSG:4326")

    filtrado = filtrar_gdf_san_rafael(gdf)
    if "tipo_culti" not in filtrado.columns:
        raise RuntimeError("No existe la columna tipo_culti en el parcelario.")

    filtrado["cultivo"] = filtrado["tipo_culti"].apply(normalizar_cultivo)
    area = filtrado.to_crs("EPSG:3857").geometry.area
    filtrado["area_m2"] = area

    vid_olivo = filtrado[filtrado["cultivo"].isin(["vid", "olivo"])].copy()

    output_completo = Path(args.output_completo)
    output_vid_olivo = Path(args.output_vid_olivo)
    output_completo.parent.mkdir(parents=True, exist_ok=True)
    output_vid_olivo.parent.mkdir(parents=True, exist_ok=True)

    filtrado.to_file(output_completo, driver="GeoJSON")
    vid_olivo.to_file(output_vid_olivo, driver="GeoJSON")

    print("=== Reconstruccion parcelas San Rafael ===")
    print("Input:", args.input)
    print("Limite local exacto:", limite_san_rafael_existe())
    print("Salida completa:", output_completo)
    print("Salida vid/olivo:", output_vid_olivo)
    print("Parcelas completas:", len(filtrado))
    print("Distribucion completa:", filtrado["cultivo"].value_counts().to_dict())
    print("Parcelas vid/olivo:", len(vid_olivo))
    print("Distribucion vid/olivo:", vid_olivo["cultivo"].value_counts().to_dict())
    print("Bounds:", [round(value, 6) for value in vid_olivo.total_bounds])


if __name__ == "__main__":
    main()
