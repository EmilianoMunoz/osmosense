import argparse
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.scripts.experiments.recalcular_dataset_desde_ide import AREA_MINIMA_M2


AUDITORIA_COBERTURA = "backend/data/auditoria_cobertura_parcelas.csv"
PARCELAS_OFICIALES = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
MUESTRA_TEMPORAL = "backend/data/parcelas/muestra_temporal_full_vid_olivo.geojson"
DATASET_TEMPORAL = "backend/data/dataset_temporal_hidrico.csv"
OUTPUT_DETALLE = "backend/data/auditoria_sin_ranking_detalle.csv"
OUTPUT_RESUMEN = "backend/data/auditoria_sin_ranking_resumen.csv"
OUTPUT_GEOJSON = "backend/data/auditoria_sin_ranking_detalle.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita parcelas oficiales vid/olivo que no entraron al ranking latest."
    )
    parser.add_argument("--auditoria", default=AUDITORIA_COBERTURA)
    parser.add_argument("--parcelas", default=PARCELAS_OFICIALES)
    parser.add_argument("--muestra-temporal", default=MUESTRA_TEMPORAL)
    parser.add_argument("--temporal", default=DATASET_TEMPORAL)
    parser.add_argument("--output-detalle", default=OUTPUT_DETALLE)
    parser.add_argument("--output-resumen", default=OUTPUT_RESUMEN)
    parser.add_argument("--output-geojson", default=OUTPUT_GEOJSON)
    parser.add_argument("--latest-date", default=None)
    return parser.parse_args()


def cargar_parcelas(path: str) -> gpd.GeoDataFrame:
    parcelas = gpd.read_file(path)
    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")
    elif parcelas.crs.to_epsg() != 4326:
        parcelas = parcelas.to_crs("EPSG:4326")

    parcelas = parcelas.rename(columns={"fid": "parcela_id"})
    parcelas["parcela_id"] = parcelas["parcela_id"].astype(int)
    area = parcelas.to_crs("EPSG:3857").geometry.area
    parcelas["area_m2_calculada"] = area
    return parcelas[["parcela_id", "area_m2_calculada", "geometry"]]


def cargar_ids_muestra(path: str) -> set[int]:
    muestra = gpd.read_file(path)
    id_col = "id" if "id" in muestra.columns else "fid"
    return set(muestra[id_col].astype(int).tolist())


def cargar_temporal(path: str) -> tuple[pd.DataFrame, str]:
    temporal = pd.read_csv(path, usecols=["parcela_id", "fecha"])
    temporal["parcela_id"] = temporal["parcela_id"].astype(int)
    temporal["fecha"] = temporal["fecha"].astype(str)
    latest_date = temporal["fecha"].max()
    latest_ids = set(
        temporal.loc[temporal["fecha"] == latest_date, "parcela_id"].astype(int)
    )
    stats = (
        temporal.groupby("parcela_id")
        .agg(
            observaciones_temporal_reales=("fecha", "count"),
            primera_fecha_real=("fecha", "min"),
            ultima_fecha_real=("fecha", "max"),
            fechas_unicas=("fecha", "nunique"),
        )
        .reset_index()
    )
    stats["tiene_observacion_latest_temporal"] = stats["parcela_id"].isin(latest_ids)
    return stats, latest_date


def clasificar_causa(row: pd.Series) -> str:
    if row["estado_cobertura"] == "con_historial_sin_ranking_latest":
        if not row["tiene_observacion_latest_temporal"]:
            return "sin_observacion_valida_en_fecha_latest"
        return "observacion_latest_no_usable_para_ranking"

    if row["area_m2_calculada"] < AREA_MINIMA_M2:
        return f"excluida_por_area_menor_{AREA_MINIMA_M2}m2"

    if not row["en_muestra_temporal_full"]:
        return "no_presente_en_muestra_temporal_full"

    if row["en_muestra_temporal_full"] and not row["en_dataset_temporal"]:
        return "sin_pixeles_validos_en_extraccion_temporal"

    return "sin_historial_causa_no_determinada"


def main() -> None:
    args = parse_args()

    auditoria = pd.read_csv(args.auditoria)
    no_rankeadas = auditoria[auditoria["estado_cobertura"] != "rankeada"].copy()
    no_rankeadas["parcela_id"] = no_rankeadas["parcela_id"].astype(int)

    parcelas = cargar_parcelas(args.parcelas)
    muestra_ids = cargar_ids_muestra(args.muestra_temporal)
    temporal_stats, latest_date = cargar_temporal(args.temporal)
    if args.latest_date:
        latest_date = args.latest_date

    detalle = no_rankeadas.merge(parcelas, on="parcela_id", how="left")
    detalle = detalle.merge(temporal_stats, on="parcela_id", how="left")
    detalle["en_muestra_temporal_full"] = detalle["parcela_id"].isin(muestra_ids)
    detalle[f"area_menor_{AREA_MINIMA_M2}m2"] = (
        detalle["area_m2_calculada"] < AREA_MINIMA_M2
    )
    detalle["tiene_observacion_latest_temporal"] = detalle[
        "tiene_observacion_latest_temporal"
    ].fillna(False)
    detalle["observaciones_temporal_reales"] = detalle[
        "observaciones_temporal_reales"
    ].fillna(0).astype(int)
    detalle["fechas_unicas"] = detalle["fechas_unicas"].fillna(0).astype(int)
    detalle["latest_date_auditada"] = latest_date
    detalle["causa_probable_detallada"] = detalle.apply(clasificar_causa, axis=1)

    resumen = (
        detalle.groupby(["cultivo", "estado_cobertura", "causa_probable_detallada"])
        .size()
        .reset_index(name="parcelas")
        .sort_values(["cultivo", "estado_cobertura", "parcelas"], ascending=[True, True, False])
    )

    output_detalle = Path(args.output_detalle)
    output_resumen = Path(args.output_resumen)
    output_geojson = Path(args.output_geojson)
    output_detalle.parent.mkdir(parents=True, exist_ok=True)
    output_resumen.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    detalle.drop(columns="geometry").to_csv(output_detalle, index=False)
    resumen.to_csv(output_resumen, index=False)
    gpd.GeoDataFrame(detalle, geometry="geometry", crs="EPSG:4326").to_file(
        output_geojson,
        driver="GeoJSON",
    )

    print("=== Auditoria parcelas sin ranking ===")
    print("Latest auditada:", latest_date)
    print("Parcelas sin ranking:", len(detalle))
    print("\nPor estado:")
    print(detalle["estado_cobertura"].value_counts().to_string())
    print("\nPor causa probable:")
    print(detalle["causa_probable_detallada"].value_counts().to_string())
    print("\nPor cultivo, estado y causa:")
    print(resumen.to_string(index=False))
    print("\nDetalle:", output_detalle)
    print("Resumen:", output_resumen)
    print("GeoJSON:", output_geojson)


if __name__ == "__main__":
    main()
