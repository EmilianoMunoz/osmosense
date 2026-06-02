import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


INPUT_RANKING = "backend/data/rankings/ranking_hidrico_latest.csv"
INPUT_PARCELAS = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
OUTPUT_DETALLE = "backend/data/auditoria_vecinos_ranking.csv"
OUTPUT_RESUMEN = "backend/data/auditoria_vecinos_ranking_resumen.csv"
OUTPUT_GEOJSON = "backend/data/auditoria_vecinos_ranking.geojson"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita outliers espaciales del ranking hidrico por vecinos cercanos."
    )
    parser.add_argument("--ranking", default=INPUT_RANKING)
    parser.add_argument("--parcelas", default=INPUT_PARCELAS)
    parser.add_argument("--output-detalle", default=OUTPUT_DETALLE)
    parser.add_argument("--output-resumen", default=OUTPUT_RESUMEN)
    parser.add_argument("--output-geojson", default=OUTPUT_GEOJSON)
    parser.add_argument(
        "--score-column",
        default="prioridad_score",
        help="Columna numerica a comparar contra vecinos.",
    )
    parser.add_argument("--k", type=int, default=6, help="Vecinos maximos por parcela.")
    parser.add_argument(
        "--max-distance-m",
        type=float,
        default=500.0,
        help="Distancia maxima al centroide para considerar vecinos.",
    )
    parser.add_argument(
        "--min-neighbors",
        type=int,
        default=3,
        help="Minimo de vecinos para evaluar outlier.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=35.0,
        help="Diferencia absoluta contra mediana vecinal para marcar outlier.",
    )
    parser.add_argument(
        "--all-crops",
        action="store_true",
        help="Compara contra todos los cultivos. Por defecto compara dentro del mismo cultivo.",
    )
    return parser.parse_args()


def cargar_datos(ranking_path: str, parcelas_path: str) -> gpd.GeoDataFrame:
    ranking = pd.read_csv(ranking_path)
    ranking["parcela_id"] = ranking["parcela_id"].astype(int)

    parcelas = gpd.read_file(parcelas_path)
    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")
    elif parcelas.crs.to_epsg() != 4326:
        parcelas = parcelas.to_crs("EPSG:4326")

    parcelas = parcelas.rename(columns={"fid": "parcela_id"})
    parcelas["parcela_id"] = parcelas["parcela_id"].astype(int)
    if "cultivo" in parcelas.columns:
        parcelas = parcelas.rename(columns={"cultivo": "cultivo_oficial"})

    merged = parcelas.merge(ranking, on="parcela_id", how="inner")
    if merged.empty:
        raise RuntimeError("No hay interseccion entre ranking y GeoJSON de parcelas.")

    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def auditar_grupo(
    grupo: gpd.GeoDataFrame,
    score_column: str,
    k: int,
    max_distance_m: float,
    min_neighbors: int,
    threshold: float,
) -> pd.DataFrame:
    if len(grupo) <= 1:
        return pd.DataFrame()

    grupo_m = grupo.to_crs("EPSG:3857").copy()
    centroides = grupo_m.geometry.centroid
    coords = np.column_stack([centroides.x.to_numpy(), centroides.y.to_numpy()])
    n_neighbors = min(k + 1, len(grupo_m))

    model = NearestNeighbors(n_neighbors=n_neighbors, metric="euclidean")
    model.fit(coords)
    distances, indices = model.kneighbors(coords)

    rows = []
    scores = grupo_m[score_column].to_numpy(dtype=float)
    parcela_ids = grupo_m["parcela_id"].astype(int).to_numpy()

    for i, parcela_id in enumerate(parcela_ids):
        neighbor_positions = []
        neighbor_distances = []
        for distance, idx in zip(distances[i], indices[i]):
            if idx == i:
                continue
            if distance > max_distance_m:
                continue
            neighbor_positions.append(idx)
            neighbor_distances.append(distance)

        neighbor_scores = scores[neighbor_positions]
        neighbor_ids = parcela_ids[neighbor_positions]
        neighbor_count = len(neighbor_scores)

        if neighbor_count:
            median_score = float(np.median(neighbor_scores))
            mean_score = float(np.mean(neighbor_scores))
            std_score = float(np.std(neighbor_scores))
            min_score = float(np.min(neighbor_scores))
            max_score = float(np.max(neighbor_scores))
            nearest_distance = float(np.min(neighbor_distances))
            diff = float(scores[i] - median_score)
        else:
            median_score = np.nan
            mean_score = np.nan
            std_score = np.nan
            min_score = np.nan
            max_score = np.nan
            nearest_distance = np.nan
            diff = np.nan

        evaluable = neighbor_count >= min_neighbors
        outlier = bool(evaluable and abs(diff) >= threshold)
        rows.append(
            {
                "parcela_id": int(parcela_id),
                "neighbor_count": neighbor_count,
                "neighbor_ids": ",".join(map(str, neighbor_ids.tolist())),
                "nearest_neighbor_distance_m": nearest_distance,
                f"neighbor_{score_column}_median": median_score,
                f"neighbor_{score_column}_mean": mean_score,
                f"neighbor_{score_column}_std": std_score,
                f"neighbor_{score_column}_min": min_score,
                f"neighbor_{score_column}_max": max_score,
                f"{score_column}_vs_neighbor_median": diff,
                f"abs_{score_column}_vs_neighbor_median": (
                    abs(diff) if not np.isnan(diff) else np.nan
                ),
                "neighbor_evaluable": evaluable,
                "outlier_espacial": outlier,
            }
        )

    return pd.DataFrame(rows)


def auditar(args: argparse.Namespace) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    gdf = cargar_datos(args.ranking, args.parcelas)
    if args.score_column not in gdf.columns:
        raise RuntimeError(f"No existe la columna {args.score_column} en el ranking.")

    if args.all_crops:
        frames = [
            auditar_grupo(
                gdf,
                args.score_column,
                args.k,
                args.max_distance_m,
                args.min_neighbors,
                args.threshold,
            )
        ]
    else:
        frames = [
            auditar_grupo(
                grupo,
                args.score_column,
                args.k,
                args.max_distance_m,
                args.min_neighbors,
                args.threshold,
            )
            for _, grupo in gdf.groupby("cultivo")
        ]

    vecinos = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
    detalle = gdf.merge(vecinos, on="parcela_id", how="left")
    detalle["neighbor_count"] = detalle["neighbor_count"].fillna(0).astype(int)
    detalle["neighbor_evaluable"] = detalle["neighbor_evaluable"].fillna(False)
    detalle["outlier_espacial"] = detalle["outlier_espacial"].fillna(False)
    detalle["tipo_outlier_espacial"] = np.select(
        [
            detalle["outlier_espacial"]
            & (detalle[f"{args.score_column}_vs_neighbor_median"] > 0),
            detalle["outlier_espacial"]
            & (detalle[f"{args.score_column}_vs_neighbor_median"] < 0),
        ],
        ["score_mucho_mas_alto_que_vecinos", "score_mucho_mas_bajo_que_vecinos"],
        default="normal_o_no_evaluable",
    )

    resumen = (
        detalle.groupby(["cultivo", "prioridad", "tipo_outlier_espacial"])
        .size()
        .reset_index(name="parcelas")
        .sort_values(["cultivo", "prioridad", "parcelas"], ascending=[True, True, False])
    )
    return detalle, resumen


def main() -> None:
    args = parse_args()
    detalle, resumen = auditar(args)

    output_detalle = Path(args.output_detalle)
    output_resumen = Path(args.output_resumen)
    output_geojson = Path(args.output_geojson)
    output_detalle.parent.mkdir(parents=True, exist_ok=True)
    output_resumen.parent.mkdir(parents=True, exist_ok=True)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    detalle.drop(columns="geometry").to_csv(output_detalle, index=False)
    resumen.to_csv(output_resumen, index=False)
    detalle.to_file(output_geojson, driver="GeoJSON")

    evaluables = int(detalle["neighbor_evaluable"].sum())
    outliers = int(detalle["outlier_espacial"].sum())
    print("=== Auditoria vecinos ranking ===")
    print("Ranking:", args.ranking)
    print("Parcelas:", args.parcelas)
    print("Comparacion:", "todos_los_cultivos" if args.all_crops else "mismo_cultivo")
    print("k:", args.k)
    print("max_distance_m:", args.max_distance_m)
    print("min_neighbors:", args.min_neighbors)
    print("threshold:", args.threshold)
    print("score_column:", args.score_column)
    print("Parcelas rankeadas:", len(detalle))
    print("Evaluables:", evaluables)
    print("Outliers espaciales:", outliers)
    if evaluables:
        print("Outliers sobre evaluables:", f"{100 * outliers / evaluables:.2f}%")
    print("\nPor tipo:")
    print(detalle["tipo_outlier_espacial"].value_counts().to_string())
    print("\nTop 15 diferencias:")
    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        args.score_column,
        "neighbor_count",
        f"neighbor_{args.score_column}_median",
        f"{args.score_column}_vs_neighbor_median",
        "nearest_neighbor_distance_m",
        "tipo_outlier_espacial",
    ]
    print(
        detalle.sort_values(
            f"abs_{args.score_column}_vs_neighbor_median",
            ascending=False,
        )[cols]
        .head(15)
        .to_string(index=False)
    )
    print("\nDetalle:", output_detalle)
    print("Resumen:", output_resumen)
    print("GeoJSON:", output_geojson)


if __name__ == "__main__":
    main()
