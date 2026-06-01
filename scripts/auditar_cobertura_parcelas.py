import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


INPUT_PARCELAS = "data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
INPUT_TEMPORAL = "data/dataset_temporal_hidrico.csv"
INPUT_RANKING = "data/rankings/ranking_hidrico_latest.csv"
OUTPUT_CSV = "data/auditoria_cobertura_parcelas.csv"
OUTPUT_GEOJSON = "data/auditoria_cobertura_parcelas.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita cobertura de parcelas oficiales vs dataset temporal/ranking."
    )
    parser.add_argument("--parcelas", default=INPUT_PARCELAS)
    parser.add_argument("--temporal", default=INPUT_TEMPORAL)
    parser.add_argument("--ranking", default=INPUT_RANKING)
    parser.add_argument("--output-csv", default=OUTPUT_CSV)
    parser.add_argument("--output-geojson", default=OUTPUT_GEOJSON)
    parser.add_argument("--id-column", default="fid")
    return parser.parse_args()


def estado_cobertura(row: pd.Series) -> str:
    if row["en_ranking_latest"]:
        return "rankeada"
    if row["en_dataset_temporal"]:
        return "con_historial_sin_ranking_latest"
    return "sin_historial"


def motivo_probable(row: pd.Series) -> str:
    if row["estado_cobertura"] == "rankeada":
        return "parcela incluida en ranking latest"
    if row["estado_cobertura"] == "con_historial_sin_ranking_latest":
        return "sin observacion valida en fecha latest o filtrada por features"
    return "no incluida en muestra temporal actual"


def main() -> None:
    args = parse_args()
    parcelas = gpd.read_file(args.parcelas)
    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")
    elif parcelas.crs.to_epsg() != 4326:
        parcelas = parcelas.to_crs("EPSG:4326")

    if args.id_column not in parcelas.columns:
        raise RuntimeError(f"No existe columna id {args.id_column} en {args.parcelas}")

    parcelas = parcelas.rename(columns={args.id_column: "parcela_id"})
    parcelas["parcela_id"] = parcelas["parcela_id"].astype(int)
    parcelas = parcelas[parcelas["cultivo"].isin(["vid", "olivo"])].copy()

    temporal = pd.read_csv(args.temporal, usecols=["parcela_id", "cultivo", "fecha"])
    temporal["parcela_id"] = temporal["parcela_id"].astype(int)
    temporal_stats = (
        temporal.groupby("parcela_id")
        .agg(
            temporal_cultivo=("cultivo", "last"),
            observaciones_temporales=("fecha", "count"),
            primera_fecha=("fecha", "min"),
            ultima_fecha=("fecha", "max"),
        )
        .reset_index()
    )

    ranking = pd.read_csv(args.ranking, usecols=["parcela_id", "cultivo", "fecha_actual", "prioridad", "ranking_global"])
    ranking["parcela_id"] = ranking["parcela_id"].astype(int)
    ranking = ranking.rename(
        columns={
            "cultivo": "ranking_cultivo",
            "fecha_actual": "fecha_ranking_latest",
        }
    )

    audit = parcelas.merge(temporal_stats, on="parcela_id", how="left")
    audit = audit.merge(ranking, on="parcela_id", how="left")
    audit["en_dataset_temporal"] = audit["observaciones_temporales"].notna()
    audit["en_ranking_latest"] = audit["ranking_global"].notna()
    audit["observaciones_temporales"] = audit["observaciones_temporales"].fillna(0).astype(int)
    audit["estado_cobertura"] = audit.apply(estado_cobertura, axis=1)
    audit["motivo_probable"] = audit.apply(motivo_probable, axis=1)

    output_csv = Path(args.output_csv)
    output_geojson = Path(args.output_geojson)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    audit.drop(columns="geometry").to_csv(output_csv, index=False)
    audit.to_file(output_geojson, driver="GeoJSON")

    print("=== Auditoria cobertura parcelas ===")
    print("Parcelas oficiales vid/olivo:", len(audit))
    print("\nPor estado:")
    print(audit["estado_cobertura"].value_counts().to_string())
    print("\nPor cultivo y estado:")
    print(
        audit.groupby(["cultivo", "estado_cobertura"])
        .size()
        .unstack(fill_value=0)
        .to_string()
    )
    print("\nCobertura dataset temporal:")
    print(
        audit.groupby("cultivo")["en_dataset_temporal"]
        .mean()
        .mul(100)
        .round(2)
        .astype(str)
        .add("%")
        .to_string()
    )
    print("\nCobertura ranking latest:")
    print(
        audit.groupby("cultivo")["en_ranking_latest"]
        .mean()
        .mul(100)
        .round(2)
        .astype(str)
        .add("%")
        .to_string()
    )
    print("\nCSV:", output_csv)
    print("GeoJSON:", output_geojson)


if __name__ == "__main__":
    main()
