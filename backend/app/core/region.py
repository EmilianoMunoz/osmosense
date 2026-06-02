from pathlib import Path
from typing import Any

import ee
import geopandas as gpd
from shapely.geometry import mapping


SAN_RAFAEL_BOUNDS = (-69.61384291, -35.52309910, -67.41312966, -34.47910163)
SAN_RAFAEL_LIMIT_GEOJSON = Path("backend/data/limites/san_rafael.geojson")


def limite_san_rafael_existe(path: str | Path = SAN_RAFAEL_LIMIT_GEOJSON) -> bool:
    return Path(path).exists()


def cargar_limite_san_rafael(
    path: str | Path = SAN_RAFAEL_LIMIT_GEOJSON,
) -> gpd.GeoDataFrame | None:
    limite_path = Path(path)
    if not limite_path.exists():
        return None

    limite = gpd.read_file(limite_path)
    if limite.empty:
        raise ValueError(f"El límite de San Rafael está vacío: {limite_path}")

    if limite.crs is None:
        limite = limite.set_crs("EPSG:4326")
    elif limite.crs.to_epsg() != 4326:
        limite = limite.to_crs("EPSG:4326")

    geometria = limite.geometry.union_all()
    return gpd.GeoDataFrame({"nombre": ["San Rafael"]}, geometry=[geometria], crs="EPSG:4326")


def filtrar_gdf_san_rafael(
    gdf: gpd.GeoDataFrame,
    limite_path: str | Path = SAN_RAFAEL_LIMIT_GEOJSON,
) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    limite = cargar_limite_san_rafael(limite_path)
    if limite is None:
        minx, miny, maxx, maxy = SAN_RAFAEL_BOUNDS
        return gdf.cx[minx:maxx, miny:maxy].copy()

    geom = limite.geometry.iloc[0]
    return gdf[gdf.geometry.intersects(geom)].copy()


def region_san_rafael_ee(
    limite_path: str | Path = SAN_RAFAEL_LIMIT_GEOJSON,
) -> ee.Geometry:
    limite = cargar_limite_san_rafael(limite_path)
    if limite is None:
        return ee.Geometry.Rectangle(list(SAN_RAFAEL_BOUNDS))

    geom_geojson: dict[str, Any] = mapping(limite.geometry.iloc[0])
    return ee.Geometry(geom_geojson)
