from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core.gee import inicializar_gee
from backend.scripts.experiments.recalcular_dataset_desde_ide import (
    AREA_MINIMA_M2,
    BUFFER_NEGATIVO_M,
    MIN_VALID_PIXELS,
    RANDOM_STATE,
    filtrar_observaciones_validas,
)
from backend.scripts.pipeline.generar_dataset_temporal_hidrico import (
    extraer_ventana,
    fechas_ventanas,
)


INPUT_GEOJSON = "backend/data/parcelas/san_rafael_completo_wgs84.geojson"
OUTPUT_DATASET = "backend/data/dataset_clasificacion_multiclase_temporal.csv"
OUTPUT_SAMPLE = "backend/data/parcelas/muestra_clasificacion_multiclase.geojson"
TARGET_CLASSES = ["vid", "olivo", "frutales", "incultos", "anuales"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un dataset Sentinel-2 multiclase desde el parcelario completo "
            "de San Rafael para entrenar clasificadores de cultivo."
        )
    )
    parser.add_argument("--input", default=INPUT_GEOJSON)
    parser.add_argument("--output", default=OUTPUT_DATASET)
    parser.add_argument("--output-sample", default=OUTPUT_SAMPLE)
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--step-days", type=int, default=60)
    parser.add_argument("--window-days", type=int, default=10)
    parser.add_argument("--max-windows", type=int, default=6)
    parser.add_argument("--cloud-threshold", type=float, default=35.0)
    parser.add_argument("--chunk-size", type=int, default=150)
    parser.add_argument("--min-valid-pixels", type=int, default=MIN_VALID_PIXELS)
    parser.add_argument("--area-minima-m2", type=float, default=AREA_MINIMA_M2)
    parser.add_argument("--samples-per-class", type=int, default=350)
    parser.add_argument("--classes", nargs="+", default=TARGET_CLASSES)
    parser.add_argument(
        "--reuse-sample",
        action="store_true",
        help="Usa output-sample existente y solo recalcula observaciones.",
    )
    return parser.parse_args()


def normalizar_cultivo_multiclase(value: object) -> str | None:
    text = str(value or "").strip().upper()
    mapping = {
        "VID": "vid",
        "OLIVOS": "olivo",
        "FRUTALES": "frutales",
        "INCULTOS": "incultos",
        "ANUALES": "anuales",
    }
    return mapping.get(text)


def preparar_muestra_multiclase(args: argparse.Namespace) -> gpd.GeoDataFrame:
    sample_path = Path(args.output_sample)
    if args.reuse_sample and sample_path.exists():
        print(f"Usando muestra existente: {sample_path}")
        muestra = gpd.read_file(sample_path)
        muestra["id"] = muestra["id"].astype(str)
        return muestra

    print(f"Cargando parcelario completo: {args.input}")
    gdf = gpd.read_file(args.input)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs("EPSG:4326")

    gdf["cultivo"] = gdf["tipo_culti"].apply(normalizar_cultivo_multiclase)
    classes = [item.lower() for item in args.classes]
    gdf = gdf[gdf["cultivo"].isin(classes)].copy()

    if "area_m2" not in gdf.columns:
        gdf["area_m2"] = gdf.to_crs("EPSG:3857").geometry.area
    gdf = gdf[pd.to_numeric(gdf["area_m2"], errors="coerce") >= args.area_minima_m2].copy()

    parts = []
    for cultivo in classes:
        subset = gdf[gdf["cultivo"] == cultivo].copy()
        n = min(args.samples_per_class, len(subset))
        if n == 0:
            print(f"{cultivo}: sin parcelas disponibles")
            continue
        parts.append(subset.sample(n=n, random_state=RANDOM_STATE))
        print(f"{cultivo}: {n}/{len(subset)} parcelas")

    if not parts:
        raise RuntimeError("No se pudo construir muestra multiclase.")

    muestra = pd.concat(parts, ignore_index=True)
    muestra["id"] = muestra["fid"].astype(str)
    muestra = gpd.GeoDataFrame(muestra, geometry="geometry", crs="EPSG:4326")
    muestra = muestra.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    muestra.to_file(sample_path, driver="GeoJSON")
    print(f"Muestra guardada en {sample_path}: {muestra.shape}")
    print("Distribucion:", muestra["cultivo"].value_counts().to_dict())
    print(f"Buffer negativo usado en geometria: {BUFFER_NEGATIVO_M} m")
    return muestra


def generar_dataset(args: argparse.Namespace) -> pd.DataFrame:
    inicializar_gee()
    muestra = preparar_muestra_multiclase(args)

    fechas = fechas_ventanas(args.start_date, args.end_date, args.step_days)
    if args.max_windows:
        fechas = fechas[: args.max_windows]

    all_rows = []
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for fecha_inicio in fechas:
        rows = extraer_ventana(
            muestra,
            fecha_inicio,
            args.window_days,
            args.cloud_threshold,
            args.chunk_size,
        )
        all_rows.extend(rows)
        if all_rows:
            pd.DataFrame(all_rows).to_csv(output_path, index=False)
            print(f"Parcial guardado: {output_path} ({len(all_rows)} filas)", flush=True)

    if not all_rows:
        raise RuntimeError("No se extrajeron observaciones desde GEE.")

    df = pd.DataFrame(all_rows)
    df = filtrar_observaciones_validas(df, args.min_valid_pixels)
    df.to_csv(output_path, index=False)

    print("\n=== Dataset clasificacion multiclase ===")
    print("Salida:", output_path)
    print("Shape:", df.shape)
    print("Distribucion:", df["cultivo"].value_counts().to_dict())
    print("Rango fechas:", df["fecha"].min(), df["fecha"].max())
    return df


def main() -> None:
    args = parse_args()
    generar_dataset(args)


if __name__ == "__main__":
    main()
