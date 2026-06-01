import argparse
import calendar
from pathlib import Path

import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import mapping

from app.core.gee import inicializar_gee
from app.core.region import SAN_RAFAEL_BOUNDS, filtrar_gdf_san_rafael
from app.services.images import obtener_imagenes_sentinel, obtener_imagen_compuesta
from app.services.indices import calcular_indices


INPUT_GEOJSON = "data/parcelas/parcelas_ide.geojson"
OUTPUT_SAMPLE = "data/parcelas/muestra_recalculada.geojson"
OUTPUT_MONTHLY = "data/dataset_mensual_recalculado.csv"
OUTPUT_WIDE = "data/dataset_fenologico_recalculado.csv"

RANDOM_STATE = 42
AREA_MINIMA_M2 = 4000
BUFFER_NEGATIVO_M = 5
MIN_VALID_PIXELS = 8

INDICES_FENOLOGICOS = [
    "ndvi",
    "ndmi",
    "ndwi",
    "msi",
    "savi",
    "ndre",
    "gndvi",
    "evi",
    "bsi",
    "nbr",
    "mtci",
    "ireci",
]

STAT_COLUMNS = ["mean", "stdDev", "min", "max", "count"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recalcula dataset Sentinel-2 desde parcelas IDEMendoza."
    )
    parser.add_argument("--input", default=INPUT_GEOJSON)
    parser.add_argument("--output-sample", default=OUTPUT_SAMPLE)
    parser.add_argument("--output-monthly", default=OUTPUT_MONTHLY)
    parser.add_argument("--output-wide", default=OUTPUT_WIDE)
    parser.add_argument("--start-year", type=int, default=2023)
    parser.add_argument("--end-year", type=int, default=2024)
    parser.add_argument("--cloud-threshold", type=float, default=30.0)
    parser.add_argument("--chunk-size", type=int, default=250)
    parser.add_argument("--muestras-vid", type=int, default=1000)
    parser.add_argument("--muestras-frutales", type=int, default=1000)
    parser.add_argument("--muestras-descarte", type=int, default=1000)
    parser.add_argument("--muestras-olivo", type=int, default=711)
    parser.add_argument("--min-valid-pixels", type=int, default=MIN_VALID_PIXELS)
    parser.add_argument("--max-months", type=int, default=None)
    parser.add_argument(
        "--reuse-sample",
        action="store_true",
        help="Usa output-sample existente y solo recalcula índices.",
    )
    return parser.parse_args()


def normalizar_cultivo(valor: str) -> str:
    valor = str(valor).strip().upper()

    if valor == "VID":
        return "vid"
    if valor == "OLIVOS":
        return "olivo"
    if valor == "FRUTALES":
        return "frutales"
    return "descarte"


def preparar_muestra(args: argparse.Namespace) -> gpd.GeoDataFrame:
    sample_path = Path(args.output_sample)

    if args.reuse_sample and sample_path.exists():
        print(f"Usando muestra existente: {sample_path}")
        return gpd.read_file(sample_path)

    print("Cargando parcelas IDE...")
    gdf = gpd.read_file(args.input)
    gdf = gdf.to_crs("EPSG:4326")

    gdf = filtrar_gdf_san_rafael(gdf)
    gdf["cultivo"] = gdf["tipo_culti"].apply(normalizar_cultivo)

    gdf_area = gdf.to_crs("EPSG:3857")
    gdf["area_m2"] = gdf_area.geometry.area
    gdf = gdf[gdf["area_m2"] >= AREA_MINIMA_M2].copy()

    muestras = {
        "vid": args.muestras_vid,
        "frutales": args.muestras_frutales,
        "descarte": args.muestras_descarte,
        "olivo": args.muestras_olivo,
    }

    partes = []
    for cultivo, n in muestras.items():
        subset = gdf[gdf["cultivo"] == cultivo].copy()
        n_final = min(n, len(subset))

        if n_final == 0:
            continue

        partes.append(subset.sample(n=n_final, random_state=RANDOM_STATE))
        print(f"{cultivo}: {n_final} muestras")

    muestra = pd.concat(partes, ignore_index=True)
    muestra["id"] = muestra["fid"].astype(str)
    muestra = gpd.GeoDataFrame(muestra, geometry="geometry", crs="EPSG:4326")

    sample_path.parent.mkdir(parents=True, exist_ok=True)
    muestra.to_file(sample_path, driver="GeoJSON")
    print(f"Muestra guardada en {sample_path}: {muestra.shape}")
    print("Distribución:", muestra["cultivo"].value_counts().to_dict())

    return muestra


def meses(start_year: int, end_year: int) -> list[tuple[int, int]]:
    return [
        (year, month)
        for year in range(start_year, end_year + 1)
        for month in range(1, 13)
    ]


def geojson_to_ee_feature(row: pd.Series) -> ee.Feature:
    geom = row.geometry
    if BUFFER_NEGATIVO_M:
        geom = (
            gpd.GeoSeries([geom], crs="EPSG:4326")
            .to_crs("EPSG:3857")
            .buffer(-BUFFER_NEGATIVO_M)
            .to_crs("EPSG:4326")
            .iloc[0]
        )

        if geom.is_empty:
            geom = row.geometry

    properties = {
        "parcela_id": str(row["id"]),
        "cultivo": row["cultivo"],
        "area_m2": float(row["area_m2"]),
    }
    return ee.Feature(ee.Geometry(mapping(geom)), properties)


def feature_collection_from_gdf(gdf: gpd.GeoDataFrame) -> ee.FeatureCollection:
    features = [geojson_to_ee_feature(row) for _, row in gdf.iterrows()]
    return ee.FeatureCollection(features)


def reducer_estadisticas() -> ee.Reducer:
    return (
        ee.Reducer.mean()
        .combine(ee.Reducer.stdDev(), sharedInputs=True)
        .combine(ee.Reducer.minMax(), sharedInputs=True)
        .combine(ee.Reducer.count(), sharedInputs=True)
    )


def extraer_mes(
    muestra: gpd.GeoDataFrame,
    year: int,
    month: int,
    cloud_threshold: float,
    chunk_size: int,
) -> list[dict]:
    fecha_inicio = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    fecha_fin = f"{year}-{month:02d}-{last_day:02d}"
    month_label = f"{year}_{month:02d}"

    minx, miny, maxx, maxy = muestra.total_bounds
    region = ee.Geometry.Rectangle([float(minx), float(miny), float(maxx), float(maxy)])

    coleccion = obtener_imagenes_sentinel(
        region,
        fecha_inicio,
        fecha_fin,
        umbral_nubosidad=cloud_threshold,
    )

    cantidad = coleccion.size().getInfo()
    print(f"{month_label}: {cantidad} imágenes")

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
                "year": year,
                "month": month,
                "fecha": f"{year}-{month:02d}-01",
            }

            for key, value in props.items():
                if key in row or key in ["system:index"]:
                    continue
                if isinstance(value, (int, float)):
                    row[key.lower()] = value

            resultados.append(row)

        print(f"  chunk {start}-{end}: {len(features)} parcelas")

    return resultados


def filtrar_observaciones_validas(df: pd.DataFrame, min_valid_pixels: int) -> pd.DataFrame:
    count_cols = [c for c in df.columns if c.endswith("_count")]

    if not count_cols:
        return df

    valid_count = df[count_cols].max(axis=1)
    before = len(df)
    df = df[valid_count >= min_valid_pixels].copy()
    print(f"Observaciones válidas: {len(df)}/{before}")
    return df


def generar_wide(df_mensual: pd.DataFrame) -> pd.DataFrame:
    meta = (
        df_mensual[["parcela_id", "cultivo", "area_m2"]]
        .drop_duplicates(subset=["parcela_id"])
        .set_index("parcela_id")
    )

    feature_cols = [
        c
        for c in df_mensual.select_dtypes(include=[np.number]).columns
        if c not in ["year", "month", "area_m2"]
    ]

    df = df_mensual.copy()
    df["periodo"] = df["year"].astype(str) + "_" + df["month"].astype(str).str.zfill(2)

    wide_parts = []
    for col in feature_cols:
        pivot = df.pivot_table(index="parcela_id", columns="periodo", values=col, aggfunc="mean")
        pivot.columns = [f"{col}_{periodo}" for periodo in pivot.columns]
        wide_parts.append(pivot)

    wide = pd.concat([meta] + wide_parts, axis=1).reset_index()
    wide = wide.fillna(0)

    return agregar_features_fenologicas(wide)


def agregar_features_fenologicas(df: pd.DataFrame) -> pd.DataFrame:
    features = {}

    for indice in INDICES_FENOLOGICOS:
        cols = [
            c
            for c in df.columns
            if c.startswith(f"{indice}_mean_")
            and c.rsplit("_", 2)[-2].isdigit()
            and c.rsplit("_", 1)[-1].isdigit()
        ]

        if len(cols) < 6:
            continue

        cols = sorted(cols, key=lambda c: (int(c.split("_")[-2]), int(c.split("_")[-1])))
        values = df[cols].to_numpy()
        months = np.array([int(c.split("_")[-1]) for c in cols])
        diffs = np.diff(values, axis=1)

        features[f"{indice}_max_year"] = np.max(values, axis=1)
        features[f"{indice}_min_year"] = np.min(values, axis=1)
        features[f"{indice}_amp_year"] = features[f"{indice}_max_year"] - features[f"{indice}_min_year"]
        features[f"{indice}_mean_year"] = np.mean(values, axis=1)
        features[f"{indice}_std_year"] = np.std(values, axis=1)
        features[f"{indice}_coeff_var"] = features[f"{indice}_std_year"] / (
            np.abs(features[f"{indice}_mean_year"]) + 1e-6
        )
        features[f"{indice}_slope"] = values[:, -1] - values[:, 0]
        features[f"{indice}_diff_mean"] = np.mean(diffs, axis=1)
        features[f"{indice}_diff_std"] = np.std(diffs, axis=1)
        features[f"{indice}_growth_total"] = np.sum(diffs.clip(min=0), axis=1)
        features[f"{indice}_decline_total"] = np.sum(diffs.clip(max=0), axis=1)
        features[f"{indice}_peak_month"] = months[np.argmax(values, axis=1)]

        verano_idx = [i for i, month in enumerate(months) if month in [12, 1, 2]]
        invierno_idx = [i for i, month in enumerate(months) if month in [6, 7, 8]]

        if verano_idx and invierno_idx:
            verano = np.mean(values[:, verano_idx], axis=1)
            invierno = np.mean(values[:, invierno_idx], axis=1)
            features[f"{indice}_diff_verano_invierno"] = verano - invierno

    features_df = pd.DataFrame(features)
    return pd.concat([df, features_df], axis=1)


def main() -> None:
    args = parse_args()
    inicializar_gee()

    muestra = preparar_muestra(args)
    month_list = meses(args.start_year, args.end_year)

    if args.max_months:
        month_list = month_list[: args.max_months]

    all_rows = []
    for year, month in month_list:
        rows = extraer_mes(
            muestra,
            year,
            month,
            args.cloud_threshold,
            args.chunk_size,
        )
        all_rows.extend(rows)

        df_partial = pd.DataFrame(all_rows)
        Path(args.output_monthly).parent.mkdir(parents=True, exist_ok=True)
        df_partial.to_csv(args.output_monthly, index=False)
        print(f"Parcial guardado: {args.output_monthly} ({len(df_partial)} filas)")

    df_mensual = pd.DataFrame(all_rows)
    df_mensual = filtrar_observaciones_validas(df_mensual, args.min_valid_pixels)
    df_mensual.to_csv(args.output_monthly, index=False)

    df_wide = generar_wide(df_mensual)
    df_wide.to_csv(args.output_wide, index=False)

    print("\n=== Dataset recalculado ===")
    print("Mensual:", df_mensual.shape, args.output_monthly)
    print("Wide:", df_wide.shape, args.output_wide)
    print("Distribución:", df_wide["cultivo"].value_counts().to_dict())


if __name__ == "__main__":
    main()
