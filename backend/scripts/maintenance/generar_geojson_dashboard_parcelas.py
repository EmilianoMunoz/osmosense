from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd


DEFAULT_INPUT = Path("backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson")
DEFAULT_OUTPUT = Path("backend/data/parcelas/san_rafael_vid_olivo_dashboard.geojson")
PROJECTED_CRS = "EPSG:3857"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un GeoJSON liviano de parcelas para visualización en dashboard."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--simplify-meters",
        type=float,
        default=2.0,
        help="Tolerancia de simplificación en metros. Usar 0 para no simplificar.",
    )
    return parser.parse_args()


def build_dashboard_geojson(
    input_path: Path,
    output_path: Path,
    simplify_meters: float,
) -> tuple[int, int, int]:
    gdf = gpd.read_file(input_path)
    if "fid" not in gdf.columns:
        raise ValueError("El GeoJSON de entrada debe tener columna fid.")

    keep_cols = [col for col in ["fid", "cultivo", "area_m2", "geometry"] if col in gdf.columns]
    light = gdf[keep_cols].copy()
    if light.crs is None:
        light = light.set_crs("EPSG:4326")
    else:
        light = light.to_crs("EPSG:4326")

    before_vertices = int(light.geometry.count_coordinates().sum())
    if simplify_meters > 0:
        projected = light.to_crs(PROJECTED_CRS)
        projected["geometry"] = projected.geometry.simplify(
            tolerance=simplify_meters,
            preserve_topology=True,
        )
        light = projected.to_crs("EPSG:4326")

    light = light[~light.geometry.is_empty & light.geometry.notna()].copy()
    after_vertices = int(light.geometry.count_coordinates().sum())
    output_path.parent.mkdir(parents=True, exist_ok=True)
    light.to_file(output_path, driver="GeoJSON")
    return len(light), before_vertices, after_vertices


def main() -> None:
    args = parse_args()
    rows, before_vertices, after_vertices = build_dashboard_geojson(
        args.input,
        args.output,
        args.simplify_meters,
    )
    input_mb = args.input.stat().st_size / 1024 / 1024
    output_mb = args.output.stat().st_size / 1024 / 1024

    print(f"parcelas: {rows}")
    print(f"vertices antes: {before_vertices}")
    print(f"vertices después: {after_vertices}")
    print(f"entrada: {input_mb:.2f} MB")
    print(f"salida: {output_mb:.2f} MB")
    print(f"reducción archivo: {(1 - output_mb / input_mb) * 100:.1f}%")
    print(f"output: {args.output}")


if __name__ == "__main__":
    main()
