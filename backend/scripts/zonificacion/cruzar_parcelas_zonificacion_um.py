from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd


DEFAULT_ZONIFICACION = Path("backend/data/zonificacion/regional_dgi_san_rafael.geojson")
DEFAULT_PARCELAS = Path("backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson")
DEFAULT_RANKING = Path("backend/data/rankings/ranking_hidrico_latest.csv")
DEFAULT_OUT_DIR = Path("backend/data/zonificacion")
PROJECTED_CRS = "EPSG:3857"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cruza parcelas oficiales vid/olivo con UM DGI y agrega ranking regional."
    )
    parser.add_argument("--zonificacion", type=Path, default=DEFAULT_ZONIFICACION)
    parser.add_argument("--parcelas", type=Path, default=DEFAULT_PARCELAS)
    parser.add_argument("--ranking", type=Path, default=DEFAULT_RANKING)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-intersection-m2", type=float, default=1.0)
    return parser.parse_args()


def read_inputs(
    zonificacion_path: Path,
    parcelas_path: Path,
    ranking_path: Path,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, pd.DataFrame]:
    zonas = gpd.read_file(zonificacion_path)
    parcelas = gpd.read_file(parcelas_path)
    ranking = pd.read_csv(ranking_path)

    if zonas.crs is None:
        zonas = zonas.set_crs("EPSG:4326")
    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")

    zonas = zonas.to_crs("EPSG:4326")
    parcelas = parcelas.to_crs("EPSG:4326")

    zonas = zonas[zonas["tipo"].astype(str).str.upper() == "UM"].copy()
    if zonas.empty:
        raise ValueError("No se encontraron geometrías tipo UM en la zonificación.")

    zonas = zonas.reset_index(drop=True)
    zonas["um_id"] = zonas.index.astype(int)

    if "fid" not in parcelas.columns:
        raise ValueError("El GeoJSON de parcelas debe tener columna fid.")
    parcelas = parcelas.rename(columns={"fid": "parcela_id"}).copy()
    parcelas["parcela_id"] = pd.to_numeric(parcelas["parcela_id"], errors="raise").astype(int)

    if "cultivo" in parcelas.columns:
        parcelas = parcelas[parcelas["cultivo"].isin(["vid", "olivo"])].copy()
    if parcelas.empty:
        raise ValueError("No hay parcelas vid/olivo para cruzar.")

    ranking["parcela_id"] = pd.to_numeric(ranking["parcela_id"], errors="raise").astype(int)
    return zonas, parcelas, ranking


def assign_parcels_to_um(
    zonas: gpd.GeoDataFrame,
    parcelas: gpd.GeoDataFrame,
    min_intersection_m2: float,
) -> pd.DataFrame:
    zonas_m = zonas[["um_id", "fid", "nombre", "cuenca", "geometry"]].to_crs(PROJECTED_CRS)
    parcelas_m = parcelas[["parcela_id", "cultivo", "area_m2", "geometry"]].to_crs(PROJECTED_CRS)

    intersections = gpd.overlay(
        parcelas_m,
        zonas_m,
        how="intersection",
        keep_geom_type=False,
    )
    if intersections.empty:
        raise ValueError("No hay intersecciones entre parcelas y UM.")

    intersections["intersection_m2"] = intersections.geometry.area
    intersections = intersections[
        intersections["intersection_m2"] >= min_intersection_m2
    ].copy()
    if intersections.empty:
        raise ValueError("No hay intersecciones por encima del mínimo configurado.")

    intersections = intersections.sort_values(
        ["parcela_id", "intersection_m2"],
        ascending=[True, False],
    )
    assigned = intersections.drop_duplicates("parcela_id", keep="first").copy()
    assigned["pct_parcela_en_um"] = (
        assigned["intersection_m2"] / assigned["area_m2"].replace(0, pd.NA) * 100
    )

    return pd.DataFrame(
        assigned[
            [
                "parcela_id",
                "cultivo",
                "area_m2",
                "um_id",
                "fid",
                "nombre",
                "cuenca",
                "intersection_m2",
                "pct_parcela_en_um",
            ]
        ].rename(
            columns={
                "fid": "um_fid",
                "nombre": "um_nombre",
                "cuenca": "um_cuenca",
            }
        )
    )


def weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return None
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def priority_from_score(score: float | None) -> str:
    if score is None or pd.isna(score):
        return "sin ranking"
    if score >= 55:
        return "critica"
    if score >= 47.5:
        return "alta"
    if score >= 35:
        return "media"
    return "baja"


def aggregate_um(
    zonas: gpd.GeoDataFrame,
    mapping: pd.DataFrame,
    ranking: pd.DataFrame,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    ranking_cols = [
        "parcela_id",
        "ranking_global",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "riesgo_operativo_5d",
        "riesgo_operativo_10d",
        "delta_operativo_5d",
        "delta_operativo_10d",
        "fecha_actual",
        "fecha_lectura",
        "dias_desde_lectura",
    ]
    ranking_cols = [col for col in ranking_cols if col in ranking.columns]
    joined = mapping.merge(ranking[ranking_cols], on="parcela_id", how="left")
    joined["en_ranking_latest"] = joined["ranking_global"].notna()

    rows = []
    for um_id, group in joined.groupby("um_id", dropna=False):
        ranked = group[group["en_ranking_latest"]].copy()
        area_total = group["area_m2"].sum()
        area_ranked = ranked["area_m2"].sum()
        score_weighted = weighted_mean(ranked["prioridad_score"], ranked["area_m2"])
        riesgo_actual_weighted = weighted_mean(ranked["riesgo_actual"], ranked["area_m2"])
        riesgo_5d_weighted = weighted_mean(ranked["riesgo_operativo_5d"], ranked["area_m2"])
        riesgo_10d_weighted = weighted_mean(ranked["riesgo_operativo_10d"], ranked["area_m2"])

        rows.append(
            {
                "um_id": int(um_id),
                "parcelas_total": int(len(group)),
                "parcelas_rankeadas": int(len(ranked)),
                "parcelas_sin_ranking": int(len(group) - len(ranked)),
                "pct_parcelas_rankeadas": float(len(ranked) / len(group) * 100),
                "area_cultivada_m2": float(area_total),
                "area_cultivada_ha": float(area_total / 10000),
                "area_rankeada_ha": float(area_ranked / 10000),
                "vid_parcelas": int((group["cultivo"] == "vid").sum()),
                "olivo_parcelas": int((group["cultivo"] == "olivo").sum()),
                "prioridad_score_prom_pond": score_weighted,
                "prioridad_score_mediana": ranked["prioridad_score"].median()
                if not ranked.empty
                else None,
                "riesgo_actual_prom_pond": riesgo_actual_weighted,
                "riesgo_5d_prom_pond": riesgo_5d_weighted,
                "riesgo_10d_prom_pond": riesgo_10d_weighted,
                "delta_10d_prom_pond": None
                if riesgo_actual_weighted is None or riesgo_10d_weighted is None
                else riesgo_10d_weighted - riesgo_actual_weighted,
                "pct_alta_critica": float(
                    ranked["prioridad"].isin(["alta", "critica"]).mean() * 100
                )
                if not ranked.empty
                else None,
                "pct_critica": float((ranked["prioridad"] == "critica").mean() * 100)
                if not ranked.empty
                else None,
                "fecha_actual": ranked["fecha_actual"].mode().iloc[0]
                if "fecha_actual" in ranked.columns and not ranked.empty
                else None,
                "prioridad_regional": priority_from_score(score_weighted),
            }
        )

    summary = pd.DataFrame(rows)
    summary["ranking_um"] = (
        summary["prioridad_score_prom_pond"]
        .rank(method="first", ascending=False, na_option="bottom")
        .astype(int)
    )
    summary = summary.sort_values("ranking_um").reset_index(drop=True)

    zonas_um = zonas.merge(summary, on="um_id", how="inner")
    return zonas_um, summary


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    zonas, parcelas, ranking = read_inputs(args.zonificacion, args.parcelas, args.ranking)
    mapping = assign_parcels_to_um(zonas, parcelas, args.min_intersection_m2)
    zonas_um, summary = aggregate_um(zonas, mapping, ranking)

    mapping_path = args.out_dir / "parcelas_um.csv"
    geojson_path = args.out_dir / "um_con_cultivos.geojson"
    ranking_path = args.out_dir / "ranking_um_latest.csv"

    mapping.sort_values(["um_id", "parcela_id"]).to_csv(mapping_path, index=False)
    summary.to_csv(ranking_path, index=False)
    zonas_um.to_crs("EPSG:4326").to_file(geojson_path, driver="GeoJSON")

    print(f"UM originales: {len(zonas)}")
    print(f"Parcelas oficiales: {len(parcelas)}")
    print(f"Parcelas asignadas a UM: {mapping['parcela_id'].nunique()}")
    print(f"UM con cultivos: {len(zonas_um)}")
    print(f"Parcelas rankeadas en UM: {int(summary['parcelas_rankeadas'].sum())}")
    print(f"Salidas:")
    print(f"  {mapping_path}")
    print(f"  {geojson_path}")
    print(f"  {ranking_path}")


if __name__ == "__main__":
    main()
