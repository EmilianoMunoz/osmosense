import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import ee
import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.gee import inicializar_gee
from app.core.region import filtrar_gdf_san_rafael
from app.services.images import obtener_imagenes_sentinel, obtener_imagen_compuesta
from app.services.indices import calcular_indices
from scripts.recalcular_dataset_desde_ide import (
    AREA_MINIMA_M2,
    BUFFER_NEGATIVO_M,
    MIN_VALID_PIXELS,
    RANDOM_STATE,
    SAN_RAFAEL_BOUNDS,
    feature_collection_from_gdf,
    filtrar_observaciones_validas,
    normalizar_cultivo,
    preparar_muestra,
    reducer_estadisticas,
)


OUTPUT_TEMPORAL = "data/dataset_temporal_hidrico.csv"
TARGET_CROPS = ["vid", "olivo"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrae observaciones Sentinel-2 por ventanas cortas para entrenar "
            "predictores hidricos X -> X+5/X+10."
        )
    )
    parser.add_argument("--input", default="data/parcelas/parcelas_ide.geojson")
    parser.add_argument("--output-sample", default="data/parcelas/muestra_recalculada.geojson")
    parser.add_argument("--output", default=OUTPUT_TEMPORAL)
    parser.add_argument("--start-date", default="2023-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--step-days", type=int, default=5)
    parser.add_argument("--window-days", type=int, default=5)
    parser.add_argument("--cloud-threshold", type=float, default=35.0)
    parser.add_argument("--chunk-size", type=int, default=250)
    parser.add_argument("--min-valid-pixels", type=int, default=MIN_VALID_PIXELS)
    parser.add_argument(
        "--reuse-sample",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Usa la muestra existente de parcelas si esta disponible.",
    )
    parser.add_argument("--max-windows", type=int, default=None)
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continua desde el CSV de salida si ya contiene fechas extraidas.",
    )
    parser.add_argument(
        "--resume-from-max-date",
        action="store_true",
        help=(
            "Al reanudar, omite todas las ventanas anteriores o iguales a la "
            "fecha maxima ya presente en el CSV. Util para continuar por bloques "
            "sin repetir ventanas que quedaron sin pixeles validos."
        ),
    )
    parser.add_argument("--muestras-vid", type=int, default=1000)
    parser.add_argument("--muestras-olivo", type=int, default=711)
    parser.add_argument("--muestras-frutales", type=int, default=0)
    parser.add_argument("--muestras-descarte", type=int, default=0)
    parser.add_argument(
        "--all-target-parcels",
        action="store_true",
        help="Usa todas las parcelas vid/olivo que pasan filtros, sin muestreo.",
    )
    parser.add_argument(
        "--missing-only-from-output",
        action="store_true",
        help="Al expandir, procesa solo parcelas que no existen en el CSV de salida.",
    )
    parser.add_argument(
        "--missing-date",
        default=None,
        help="Procesa parcelas que no tienen observacion para esta fecha en el CSV de salida.",
    )
    parser.add_argument(
        "--target-ids-csv",
        default=None,
        help="CSV con IDs de parcelas a procesar. Debe incluir la columna indicada por --target-id-column.",
    )
    parser.add_argument(
        "--target-id-column",
        default="parcela_id",
        help="Columna del CSV --target-ids-csv que contiene los IDs de parcelas.",
    )
    parser.add_argument(
        "--max-parcels",
        type=int,
        default=None,
        help="Limita la cantidad de parcelas objetivo a procesar en esta corrida.",
    )
    return parser.parse_args()


def fechas_ventanas(start_date: str, end_date: str, step_days: int) -> list[date]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    fechas = []
    actual = start

    while actual <= end:
        fechas.append(actual)
        actual += timedelta(days=step_days)

    return fechas


def filtrar_vid_olivo(muestra: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    muestra = muestra[muestra["cultivo"].isin(TARGET_CROPS)].copy()
    muestra["id"] = muestra["id"].astype(str)
    return muestra


def preparar_todas_objetivo(args: argparse.Namespace) -> gpd.GeoDataFrame:
    print("Cargando todas las parcelas objetivo vid/olivo...")
    gdf = gpd.read_file(args.input)
    gdf = gdf.to_crs("EPSG:4326")

    gdf = filtrar_gdf_san_rafael(gdf)
    gdf["cultivo"] = gdf["tipo_culti"].apply(normalizar_cultivo)
    gdf = gdf[gdf["cultivo"].isin(TARGET_CROPS)].copy()

    gdf_area = gdf.to_crs("EPSG:3857")
    gdf["area_m2"] = gdf_area.geometry.area
    gdf = gdf[gdf["area_m2"] >= AREA_MINIMA_M2].copy()
    gdf["id"] = gdf["fid"].astype(str)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs="EPSG:4326")
    gdf = gdf.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)

    output_sample = Path(args.output_sample)
    output_sample.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_sample, driver="GeoJSON")
    print(f"Muestra completa guardada en {output_sample}: {gdf.shape}")
    print("Distribucion:", gdf["cultivo"].value_counts().to_dict())
    return gdf


def filtrar_faltantes_output(muestra: gpd.GeoDataFrame, output_path: Path) -> gpd.GeoDataFrame:
    if not output_path.exists():
        print("No existe output previo; no se filtran faltantes.")
        return muestra

    df_existente = pd.read_csv(output_path, usecols=["parcela_id"])
    existentes = set(df_existente["parcela_id"].astype(str).unique())
    before = len(muestra)
    muestra = muestra[~muestra["id"].astype(str).isin(existentes)].copy()
    print(
        "Parcelas faltantes respecto del output: "
        f"{len(muestra)}/{before}"
    )
    print("Distribucion faltantes:", muestra["cultivo"].value_counts().to_dict())
    return muestra


def filtrar_faltantes_fecha(
    muestra: gpd.GeoDataFrame,
    output_path: Path,
    fecha: str,
) -> gpd.GeoDataFrame:
    if not output_path.exists():
        print("No existe output previo; no se filtran faltantes por fecha.")
        return muestra

    df_existente = pd.read_csv(output_path, usecols=["parcela_id", "fecha"])
    con_fecha = set(
        df_existente.loc[df_existente["fecha"].astype(str) == fecha, "parcela_id"]
        .astype(str)
        .unique()
    )
    before = len(muestra)
    muestra = muestra[~muestra["id"].astype(str).isin(con_fecha)].copy()
    print(
        f"Parcelas sin observacion para {fecha}: "
        f"{len(muestra)}/{before}"
    )
    print("Distribucion faltantes fecha:", muestra["cultivo"].value_counts().to_dict())
    return muestra


def filtrar_target_ids(
    muestra: gpd.GeoDataFrame,
    target_ids_csv: str | None,
    target_id_column: str,
) -> gpd.GeoDataFrame:
    if not target_ids_csv:
        return muestra

    ids_path = Path(target_ids_csv)
    if not ids_path.exists():
        raise FileNotFoundError(f"No existe CSV de IDs objetivo: {ids_path}")

    ids_df = pd.read_csv(ids_path)
    if target_id_column not in ids_df.columns:
        raise RuntimeError(
            f"El CSV {ids_path} no tiene la columna {target_id_column}."
        )

    target_ids = set(ids_df[target_id_column].dropna().astype(str).unique())
    before = len(muestra)
    muestra = muestra[muestra["id"].astype(str).isin(target_ids)].copy()
    print(f"Parcelas filtradas por IDs objetivo: {len(muestra)}/{before}")
    print("Distribucion IDs objetivo:", muestra["cultivo"].value_counts().to_dict())
    return muestra


def filtrar_observaciones_faltantes_por_fecha(
    muestra: gpd.GeoDataFrame,
    output_path: Path,
    fecha: str,
) -> gpd.GeoDataFrame:
    if not output_path.exists():
        return muestra

    df_existente = pd.read_csv(output_path, usecols=["parcela_id", "fecha"])
    con_fecha = set(
        df_existente.loc[df_existente["fecha"].astype(str) == fecha, "parcela_id"]
        .astype(str)
        .unique()
    )
    return muestra[~muestra["id"].astype(str).isin(con_fecha)].copy()


def extraer_ventana(
    muestra: gpd.GeoDataFrame,
    fecha_inicio: date,
    window_days: int,
    cloud_threshold: float,
    chunk_size: int,
) -> list[dict]:
    fecha_fin = fecha_inicio + timedelta(days=window_days)
    fecha_inicio_str = fecha_inicio.isoformat()
    fecha_fin_str = fecha_fin.isoformat()

    minx, miny, maxx, maxy = muestra.total_bounds
    region = ee.Geometry.Rectangle([float(minx), float(miny), float(maxx), float(maxy)])

    coleccion = obtener_imagenes_sentinel(
        region,
        fecha_inicio_str,
        fecha_fin_str,
        umbral_nubosidad=cloud_threshold,
    )

    cantidad = coleccion.size().getInfo()
    print(f"{fecha_inicio_str} -> {fecha_fin_str}: {cantidad} imagenes", flush=True)

    if cantidad == 0:
        return []

    imagen = calcular_indices(obtener_imagen_compuesta(coleccion, region))
    bandas = imagen.bandNames().getInfo()
    resultados = []

    for start in range(0, len(muestra), chunk_size):
        end = min(start + chunk_size, len(muestra))
        chunk = muestra.iloc[start:end]
        fc = feature_collection_from_gdf(chunk)

        reducido = imagen.select(bandas).reduceRegions(
            collection=fc,
            reducer=reducer_estadisticas(),
            scale=10,
            tileScale=4,
        )

        features = reducido.getInfo()["features"]

        for feature in features:
            props = feature["properties"]
            row = {
                "parcela_id": props["parcela_id"],
                "cultivo": props["cultivo"],
                "area_m2": props["area_m2"],
                "fecha": fecha_inicio_str,
                "fecha_fin": fecha_fin_str,
                "year": fecha_inicio.year,
                "month": fecha_inicio.month,
                "day_of_year": fecha_inicio.timetuple().tm_yday,
                "window_days": window_days,
            }

            for key, value in props.items():
                if key in row or key == "system:index":
                    continue
                if isinstance(value, (int, float)):
                    row[key.lower()] = value

            resultados.append(row)

        print(f"  chunk {start}-{end}: {len(features)} parcelas", flush=True)

    return resultados


def main() -> None:
    args = parse_args()
    inicializar_gee()

    if args.all_target_parcels:
        muestra = preparar_todas_objetivo(args)
    else:
        muestra = preparar_muestra(args)
    muestra = filtrar_vid_olivo(muestra)
    if args.missing_only_from_output:
        muestra = filtrar_faltantes_output(muestra, Path(args.output))
    if args.missing_date:
        muestra = filtrar_faltantes_fecha(muestra, Path(args.output), args.missing_date)
    muestra = filtrar_target_ids(muestra, args.target_ids_csv, args.target_id_column)

    if args.max_parcels:
        before = len(muestra)
        muestra = muestra.head(args.max_parcels).copy()
        print(f"Limite max-parcels aplicado: {len(muestra)}/{before}")
        print("Distribucion lote:", muestra["cultivo"].value_counts().to_dict())

    if muestra.empty:
        print("No hay parcelas faltantes para procesar.")
        return

    minx, miny, maxx, maxy = muestra.total_bounds
    sr_minx, sr_miny, sr_maxx, sr_maxy = SAN_RAFAEL_BOUNDS
    if not (sr_minx <= minx <= sr_maxx and sr_minx <= maxx <= sr_maxx):
        print("Aviso: la muestra excede el bounding box esperado de San Rafael.")
    if not (sr_miny <= miny <= sr_maxy and sr_miny <= maxy <= sr_maxy):
        print("Aviso: la muestra excede el bounding box esperado de San Rafael.")

    print(f"Parcelas objetivo: {len(muestra)}")
    print("Distribucion:", muestra["cultivo"].value_counts().to_dict())
    print(f"Buffer negativo usado en geometria: {BUFFER_NEGATIVO_M} m")

    fechas = fechas_ventanas(args.start_date, args.end_date, args.step_days)
    if args.max_windows:
        fechas = fechas[: args.max_windows]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows = []
    fechas_extraidas = set()
    max_fecha_extraida = None

    expanding_missing = (
        args.all_target_parcels
        and (args.missing_only_from_output or args.missing_date or args.target_ids_csv)
    )

    if args.resume and output_path.exists():
        df_existente = pd.read_csv(output_path)
        if not df_existente.empty and "fecha" in df_existente.columns:
            all_rows = df_existente.to_dict("records")
            fechas_extraidas = set(df_existente["fecha"].astype(str).unique())
            max_fecha_extraida = max(fechas_extraidas)
            print(
                f"Reanudando desde {output_path}: "
                f"{len(all_rows)} filas, {len(fechas_extraidas)} fechas ya extraidas"
            )

    for fecha_inicio in fechas:
        if (
            args.resume_from_max_date
            and max_fecha_extraida is not None
            and fecha_inicio.isoformat() <= max_fecha_extraida
        ):
            print(f"{fecha_inicio.isoformat()}: anterior a max fecha, se omite", flush=True)
            continue

        if fecha_inicio.isoformat() in fechas_extraidas:
            if expanding_missing:
                print(
                    f"{fecha_inicio.isoformat()}: ya extraida, "
                    "se agregan parcelas faltantes",
                    flush=True,
                )
                muestra_fecha = filtrar_observaciones_faltantes_por_fecha(
                    muestra,
                    output_path,
                    fecha_inicio.isoformat(),
                )
                if muestra_fecha.empty:
                    print(
                        f"{fecha_inicio.isoformat()}: no hay parcelas faltantes",
                        flush=True,
                    )
                    continue
            else:
                print(f"{fecha_inicio.isoformat()}: ya extraida, se omite", flush=True)
                continue
        else:
            muestra_fecha = muestra

        rows = extraer_ventana(
            muestra_fecha,
            fecha_inicio,
            args.window_days,
            args.cloud_threshold,
            args.chunk_size,
        )
        all_rows.extend(rows)

        if all_rows:
            pd.DataFrame(all_rows).to_csv(output_path, index=False)
            print(f"Parcial guardado: {output_path} ({len(all_rows)} filas)", flush=True)

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError("No se extrajeron observaciones temporales.")

    df = filtrar_observaciones_validas(df, args.min_valid_pixels)
    df.to_csv(output_path, index=False)

    print("\n=== Dataset temporal hidrico ===")
    print("Salida:", output_path)
    print("Shape:", df.shape)
    print("Distribucion:", df["cultivo"].value_counts().to_dict())
    print("Rango fechas:", df["fecha"].min(), df["fecha"].max())


if __name__ == "__main__":
    main()
