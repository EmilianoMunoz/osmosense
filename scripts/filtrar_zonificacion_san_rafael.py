import argparse
import json
from pathlib import Path

import geopandas as gpd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/zonificacion/regional_dgi.csv"
DEFAULT_LIMIT = ROOT / "data/limites/san_rafael.geojson"
DEFAULT_OUTPUT = ROOT / "data/zonificacion/regional_dgi_san_rafael.geojson"
DEFAULT_SUMMARY = ROOT / "data/zonificacion/regional_dgi_san_rafael_resumen.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recorta la zonificacion DGI contra el limite local de San Rafael."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--limit", default=DEFAULT_LIMIT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    return parser.parse_args()


def fix_mojibake(value):
    if not isinstance(value, str):
        return value
    try:
        fixed = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value
    return fixed if fixed != value else value


def make_valid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except AttributeError:
        gdf["geometry"] = gdf.geometry.buffer(0)
    return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()


def read_geojson_with_csv_extension(path: Path) -> gpd.GeoDataFrame:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    gdf = gpd.GeoDataFrame.from_features(data["features"], crs="EPSG:4326")
    for column in gdf.columns:
        dtype_name = str(gdf[column].dtype)
        if column == "geometry" or not (
            gdf[column].dtype == object or dtype_name in {"str", "string"}
        ):
            continue
        gdf[column] = gdf[column].map(fix_mojibake)
    return gdf


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    limit_path = Path(args.limit)
    output_path = Path(args.output)
    summary_path = Path(args.summary)

    zonificacion = read_geojson_with_csv_extension(input_path)
    limite = gpd.read_file(limit_path).to_crs("EPSG:4326")

    zonificacion = make_valid(zonificacion)
    limite = make_valid(limite)
    limite = limite[["geometry"]].dissolve()

    zonificacion_metric = zonificacion.to_crs("EPSG:5347")
    zonificacion["sup_ha_original_calc"] = zonificacion_metric.geometry.area / 10_000

    clipped = gpd.overlay(zonificacion, limite, how="intersection", keep_geom_type=True)
    clipped = make_valid(clipped)
    clipped = clipped.reset_index(drop=True)

    clipped_metric = clipped.to_crs("EPSG:5347")
    clipped["sup_ha_san_rafael"] = clipped_metric.geometry.area / 10_000
    if "sup_ha_original_calc" in clipped.columns:
        clipped["pct_sup_en_san_rafael"] = (
            clipped["sup_ha_san_rafael"]
            / clipped["sup_ha_original_calc"].replace(0, float("nan"))
            * 100
        ).round(2)
        clipped["pct_sup_en_san_rafael"] = clipped["pct_sup_en_san_rafael"].clip(upper=100)
    clipped["sup_ha_san_rafael"] = clipped["sup_ha_san_rafael"].round(4)
    clipped["sup_ha_original_calc"] = clipped["sup_ha_original_calc"].round(4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clipped.to_file(output_path, driver="GeoJSON")

    summary_cols = [
        col
        for col in [
            "fid",
            "nombre",
            "tipo",
            "cuenca",
            "sup_ha",
            "sup_ha_original_calc",
            "sup_ha_san_rafael",
            "pct_sup_en_san_rafael",
        ]
        if col in clipped.columns
    ]
    clipped[summary_cols].sort_values(["tipo", "nombre"]).to_csv(summary_path, index=False)

    print("=== Zonificacion San Rafael ===")
    print(f"Input: {input_path}")
    print(f"Limite: {limit_path}")
    print(f"Zonas originales: {len(zonificacion)}")
    print(f"Zonas intersectadas: {len(clipped)}")
    print(f"Tipos: {clipped['tipo'].value_counts().to_dict() if 'tipo' in clipped.columns else {}}")
    print(f"Output GeoJSON: {output_path}")
    print(f"Output resumen: {summary_path}")


if __name__ == "__main__":
    main()
