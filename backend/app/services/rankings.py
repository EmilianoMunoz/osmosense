import json
import os
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv


RANKING_CSV = "backend/data/rankings/ranking_hidrico_latest.csv"
RANKINGS_DIR = "backend/data/rankings"
PARCELAS_GEOJSON = "backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson"
PARCELAS_DASHBOARD_GEOJSON = "backend/data/parcelas/san_rafael_vid_olivo_dashboard.geojson"
CLIENTES_CSV = "backend/data/clientes/clientes.csv"
CLIENTE_PARCELA_CSV = "backend/data/clientes/cliente_parcela.csv"
AUDIT_VECINOS_CSV = "backend/data/auditoria_vecinos_ranking_riesgo_actual.csv"
AUDIT_TEMPORAL_CSV = "backend/data/auditoria_outliers_temporales.csv"
AUDIT_RUIDO_CSV = "backend/data/auditoria_ruido_puntual_detalle.csv"
AUDIT_HISTORICAL_METRICS_CSV = "backend/data/auditoria_metricas_historicas.csv"
ZONAS_UM_GEOJSON = "backend/data/zonificacion/um_con_cultivos.geojson"
PARCELAS_UM_CSV = "backend/data/zonificacion/parcelas_um.csv"
RANKING_UM_CSV = "backend/data/zonificacion/ranking_um_latest.csv"
PARCELA_ID_COLUMN = "fid"
RANKING_REQUIRED_COLUMNS = {
    "fecha_actual",
    "parcela_id",
    "cultivo",
    "ranking_global",
    "ranking_por_cultivo",
    "prioridad",
    "prioridad_score",
    "riesgo_actual",
    "riesgo_pred_5d",
    "riesgo_pred_10d",
    "delta_5d",
    "delta_10d",
}
RANKING_NUMERIC_COLUMNS = {
    "parcela_id",
    "dias_desde_lectura",
    "ranking_global",
    "ranking_por_cultivo",
    "prioridad_score",
    "riesgo_actual",
    "riesgo_pred_5d",
    "riesgo_pred_10d",
    "delta_5d",
    "delta_10d",
    "riesgo_operativo_5d",
    "riesgo_operativo_10d",
    "delta_operativo_5d",
    "delta_operativo_10d",
    "tendencia_reciente_5d",
    "pendiente_operativa_5d",
    "factor_estacional",
}
AUDIT_VECINOS_COLUMNS = [
    "parcela_id",
    "neighbor_count",
    "nearest_neighbor_distance_m",
    "neighbor_riesgo_actual_median",
    "riesgo_actual_vs_neighbor_median",
    "abs_riesgo_actual_vs_neighbor_median",
    "neighbor_evaluable",
    "outlier_espacial",
    "tipo_outlier_espacial",
]
AUDIT_TEMPORAL_COLUMNS = [
    "parcela_id",
    "direccion_outlier",
    "riesgo_hidrico_lag1",
    "riesgo_hidrico_lag2",
    "historial_reciente_count",
    "historial_reciente_min_dias",
    "historial_reciente_max_dias",
    "riesgo_reciente_weighted_mean",
    "soporte_indices_count",
    "soporte_indices",
    "min_valid_pixels_hidricos",
    "persistencia_temporal",
    "diagnostico_outlier",
    "riesgo_vs_hist_median",
    "riesgo_vs_reciente_weighted_mean",
]
AUDIT_RUIDO_COLUMNS = [
    "parcela_id",
    "motivo_ruido",
    "severidad_ruido",
    "accion_recomendada",
]
AUDIT_HISTORICAL_METRICS_COLUMNS = [
    "parcela_id",
    "fecha_referencia",
    "ventana_dias",
    "outlier_count_30d",
    "persistente_count_30d",
    "ruido_count_30d",
    "ultima_fecha_outlier",
    "ultima_fecha_persistente",
    "ultima_fecha_ruido",
    "dias_desde_ultimo_outlier",
    "dias_desde_ultimo_persistente",
    "dias_desde_ultimo_ruido",
]
AUDIT_NUMERIC_COLUMNS = {
    "neighbor_count",
    "nearest_neighbor_distance_m",
    "neighbor_riesgo_actual_median",
    "riesgo_actual_vs_neighbor_median",
    "abs_riesgo_actual_vs_neighbor_median",
    "riesgo_hidrico_lag1",
    "riesgo_hidrico_lag2",
    "historial_reciente_count",
    "historial_reciente_min_dias",
    "historial_reciente_max_dias",
    "riesgo_reciente_weighted_mean",
    "soporte_indices_count",
    "min_valid_pixels_hidricos",
    "riesgo_vs_hist_median",
    "riesgo_vs_reciente_weighted_mean",
    "severidad_ruido",
    "ventana_dias",
    "outlier_count_30d",
    "persistente_count_30d",
    "ruido_count_30d",
    "dias_desde_ultimo_outlier",
    "dias_desde_ultimo_persistente",
    "dias_desde_ultimo_ruido",
}
UNRANKED_PRIORITY = "sin ranking"


def database_url() -> str | None:
    load_dotenv()
    return os.getenv("DATABASE_URL")


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _records_from_df(df: pd.DataFrame) -> list[dict[str, Any]]:
    records = []
    for item in df.to_dict(orient="records"):
        records.append({key: _clean_value(value) for key, value in item.items()})
    return records


def _read_csv_existing(path: str | Path, artifact_name: str) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"No existe {artifact_name}: {csv_path}")
    return pd.read_csv(csv_path)


def _ranking_csv_path(path: str | Path = RANKING_CSV) -> Path:
    ranking_path = Path(path)
    if not ranking_path.exists():
        raise FileNotFoundError(f"No existe ranking local: {ranking_path}")
    return ranking_path


def _ranking_csv_path_for_fecha(fecha: str) -> Path:
    fecha = pd.to_datetime(fecha).strftime("%Y-%m-%d")
    ranking_path = Path(RANKINGS_DIR) / f"ranking_hidrico_{fecha}.csv"
    return _ranking_csv_path(ranking_path)


def _geojson_path(path: str | Path = PARCELAS_GEOJSON) -> Path:
    geojson_path = Path(path)
    if not geojson_path.exists():
        raise FileNotFoundError(f"No existe GeoJSON local de parcelas: {geojson_path}")
    return geojson_path


def _dashboard_geojson_path() -> Path:
    dashboard_path = Path(PARCELAS_DASHBOARD_GEOJSON)
    if dashboard_path.exists():
        return dashboard_path
    return _geojson_path(PARCELAS_GEOJSON)


def _optional_csv_path(path: str | Path) -> Path | None:
    csv_path = Path(path)
    return csv_path if csv_path.exists() else None


def _validate_columns(
    df: pd.DataFrame,
    required_columns: set[str],
    artifact_name: str,
) -> None:
    missing = sorted(required_columns - set(df.columns))
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{artifact_name} no tiene columnas requeridas: {missing_text}")


def _read_ranking_csv(path: str | Path = RANKING_CSV) -> pd.DataFrame:
    df = pd.read_csv(_ranking_csv_path(path))
    _validate_columns(df, RANKING_REQUIRED_COLUMNS, "ranking CSV")

    for column in RANKING_NUMERIC_COLUMNS & set(df.columns):
        df[column] = pd.to_numeric(df[column], errors="raise")

    df["parcela_id"] = df["parcela_id"].astype(int)
    df["fecha_actual"] = pd.to_datetime(df["fecha_actual"]).dt.strftime("%Y-%m-%d")
    if "fecha_lectura" in df.columns:
        df["fecha_lectura"] = pd.to_datetime(df["fecha_lectura"]).dt.strftime("%Y-%m-%d")
    return df


def _read_parcelas_geojson(path: str | Path = PARCELAS_GEOJSON) -> gpd.GeoDataFrame:
    parcelas = gpd.read_file(_geojson_path(path))
    _validate_columns(parcelas, {PARCELA_ID_COLUMN}, "GeoJSON de parcelas")

    if "cultivo" in parcelas.columns:
        parcelas = parcelas[parcelas["cultivo"].isin(["vid", "olivo"])].copy()

    if parcelas.empty:
        raise ValueError("GeoJSON de parcelas no contiene geometrías")

    if parcelas.crs is None:
        parcelas = parcelas.set_crs("EPSG:4326")
    elif parcelas.crs.to_epsg() != 4326:
        parcelas = parcelas.to_crs("EPSG:4326")

    parcelas = parcelas.rename(columns={PARCELA_ID_COLUMN: "parcela_id"})
    parcelas["parcela_id"] = pd.to_numeric(
        parcelas["parcela_id"],
        errors="raise",
    ).astype(int)
    return parcelas


def _read_parcelas_dashboard_geojson() -> gpd.GeoDataFrame:
    return _read_parcelas_geojson(_dashboard_geojson_path())


def _read_parcelas_dashboard_subset(parcela_ids: set[int]) -> gpd.GeoDataFrame:
    parcelas = _read_parcelas_dashboard_geojson()
    return parcelas[parcelas["parcela_id"].isin(parcela_ids)].copy()


def _limit_df(df: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if limit is None:
        return df
    if limit < 1:
        raise ValueError("limit debe ser mayor o igual a 1")
    return df.head(limit)


def _mark_unranked_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["en_ranking_latest"] = df["ranking_global"].notna()
    df["estado_cobertura"] = df["en_ranking_latest"].map(
        {True: "rankeada", False: "sin_ranking_latest"}
    )
    df["prioridad"] = df["prioridad"].fillna(UNRANKED_PRIORITY)
    return df


def _read_optional_audit(path: str | Path, columns: list[str]) -> pd.DataFrame:
    audit_path = Path(path)
    if not audit_path.exists():
        return pd.DataFrame(columns=columns)

    df = pd.read_csv(audit_path)
    present = [column for column in columns if column in df.columns]
    if "parcela_id" not in present:
        return pd.DataFrame(columns=columns)

    df = df[present].copy()
    df["parcela_id"] = pd.to_numeric(df["parcela_id"], errors="raise").astype(int)
    for column in AUDIT_NUMERIC_COLUMNS & set(df.columns):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ["neighbor_evaluable", "outlier_espacial"]:
        if column in df.columns:
            df[column] = df[column].astype(bool)
    return df.drop_duplicates("parcela_id", keep="first")


def _merge_quality_audits(df: pd.DataFrame) -> pd.DataFrame:
    merged = df.copy()

    vecinos = _read_optional_audit(AUDIT_VECINOS_CSV, AUDIT_VECINOS_COLUMNS)
    if not vecinos.empty:
        merged = merged.merge(vecinos, on="parcela_id", how="left")

    temporal = _read_optional_audit(AUDIT_TEMPORAL_CSV, AUDIT_TEMPORAL_COLUMNS)
    if not temporal.empty:
        merged = merged.merge(temporal, on="parcela_id", how="left")

    ruido = _read_optional_audit(AUDIT_RUIDO_CSV, AUDIT_RUIDO_COLUMNS)
    if not ruido.empty:
        merged = merged.merge(ruido, on="parcela_id", how="left")

    historicas = _read_optional_audit(
        AUDIT_HISTORICAL_METRICS_CSV,
        AUDIT_HISTORICAL_METRICS_COLUMNS,
    )
    if not historicas.empty:
        merged = merged.merge(historicas, on="parcela_id", how="left")

    if "outlier_espacial" not in merged.columns:
        merged["outlier_espacial"] = False
    else:
        merged["outlier_espacial"] = merged["outlier_espacial"].fillna(False).astype(bool)

    if "neighbor_evaluable" in merged.columns:
        merged["neighbor_evaluable"] = merged["neighbor_evaluable"].fillna(False).astype(bool)

    merged["confianza_lectura"] = merged.apply(_confidence_label, axis=1)
    merged["confianza_motivo"] = merged.apply(_confidence_reason, axis=1)
    return merged


def _confidence_label(row: pd.Series) -> str:
    if not bool(row.get("en_ranking_latest", False)):
        return "sin_ranking"

    dias_desde_lectura = row.get("dias_desde_lectura")
    if pd.notna(dias_desde_lectura) and int(dias_desde_lectura) > 10:
        return "baja"

    diagnostico = row.get("diagnostico_outlier")
    if diagnostico == "probable_ruido_o_lectura_puntual":
        return "baja"
    if diagnostico == "probable_manejo_real_o_condicion_persistente":
        return "alta"

    if pd.notna(dias_desde_lectura) and int(dias_desde_lectura) > 5:
        return "media"

    if bool(row.get("outlier_espacial", False)):
        return "media"

    neighbor_count = row.get("neighbor_count")
    if pd.notna(neighbor_count) and int(neighbor_count) < 3:
        return "media"

    return "alta"


def _confidence_reason(row: pd.Series) -> str:
    if not bool(row.get("en_ranking_latest", False)):
        return "parcela_sin_ranking_latest"

    dias_desde_lectura = row.get("dias_desde_lectura")
    if pd.notna(dias_desde_lectura) and int(dias_desde_lectura) > 10:
        return "lectura_valida_con_mas_de_10_dias"

    diagnostico = row.get("diagnostico_outlier")
    if diagnostico == "probable_ruido_o_lectura_puntual":
        return "salto_espacial_puntual_o_con_bajo_soporte"
    if diagnostico == "probable_manejo_real_o_condicion_persistente":
        return "salto_espacial_con_persistencia_temporal"

    if pd.notna(dias_desde_lectura) and int(dias_desde_lectura) > 5:
        return "lectura_valida_de_6_a_10_dias"

    if bool(row.get("outlier_espacial", False)):
        return diagnostico or "salto_espacial_sin_confirmacion_temporal"

    neighbor_count = row.get("neighbor_count")
    if pd.notna(neighbor_count) and int(neighbor_count) < 3:
        return "pocos_vecinos_cercanos_para_comparar"

    return "sin_alertas_de_calidad"


def latest_from_csv(limit: int | None = None) -> list[dict[str, Any]]:
    df = _read_ranking_csv()
    df = df.sort_values("ranking_global")
    df = _limit_df(df, limit)
    return _records_from_df(df)


def latest_geojson_from_csv() -> dict[str, Any]:
    ranking = _read_ranking_csv()
    parcelas = _read_parcelas_dashboard_geojson()
    if "cultivo" in parcelas.columns:
        parcelas = parcelas.rename(columns={"cultivo": "cultivo_oficial"})

    merged = parcelas.merge(ranking, on="parcela_id", how="left")
    ranked_count = int(merged["ranking_global"].notna().sum())
    if ranked_count == 0:
        raise ValueError(
            "El merge entre ranking CSV y GeoJSON de parcelas no produjo features. "
            "Revisar que parcela_id del ranking coincida con fid del GeoJSON."
        )

    if "cultivo" not in merged.columns and "cultivo_oficial" in merged.columns:
        merged["cultivo"] = merged["cultivo_oficial"]
    elif "cultivo_oficial" in merged.columns:
        merged["cultivo"] = merged["cultivo"].fillna(merged["cultivo_oficial"])

    merged = _mark_unranked_rows(merged)
    merged = _merge_quality_audits(merged)
    merged = merged.sort_values("ranking_global")
    data = json.loads(merged.to_json())
    data["ranked_count"] = ranked_count
    data["total_count"] = len(merged)
    return data


def latest_geojson_subset_from_csv(parcela_ids: set[int]) -> dict[str, Any]:
    if not parcela_ids:
        return {
            "type": "FeatureCollection",
            "features": [],
            "ranked_count": 0,
            "total_count": 0,
        }

    ranking = _read_ranking_csv()
    ranking = ranking[ranking["parcela_id"].isin(parcela_ids)].copy()
    parcelas = _read_parcelas_dashboard_subset(parcela_ids)
    if "cultivo" in parcelas.columns:
        parcelas = parcelas.rename(columns={"cultivo": "cultivo_oficial"})

    merged = parcelas.merge(ranking, on="parcela_id", how="left")
    if "cultivo" not in merged.columns and "cultivo_oficial" in merged.columns:
        merged["cultivo"] = merged["cultivo_oficial"]
    elif "cultivo_oficial" in merged.columns:
        merged["cultivo"] = merged["cultivo"].fillna(merged["cultivo_oficial"])

    merged = _mark_unranked_rows(merged)
    merged = _merge_quality_audits(merged)
    merged = merged.sort_values("ranking_global", na_position="last")
    data = json.loads(merged.to_json())
    data["ranked_count"] = int(merged["ranking_global"].notna().sum())
    data["total_count"] = len(merged)
    return data


def _read_clientes_csv(path: str | Path | None = None) -> pd.DataFrame:
    source_path = CLIENTES_CSV if path is None else path
    csv_path = _optional_csv_path(source_path)
    if csv_path is None:
        return pd.DataFrame(columns=["cliente_id", "nombre", "tipo", "activo"])

    df = pd.read_csv(csv_path)
    _validate_columns(df, {"cliente_id", "nombre", "tipo"}, "clientes CSV")
    df["cliente_id"] = pd.to_numeric(df["cliente_id"], errors="raise").astype(int)
    if "activo" not in df.columns:
        df["activo"] = True
    return df[df["activo"].astype(bool)].copy()


def _read_cliente_parcela_csv(path: str | Path | None = None) -> pd.DataFrame:
    source_path = CLIENTE_PARCELA_CSV if path is None else path
    csv_path = _optional_csv_path(source_path)
    if csv_path is None:
        return pd.DataFrame(columns=["cliente_id", "parcela_id"])

    df = pd.read_csv(csv_path)
    _validate_columns(df, {"cliente_id", "parcela_id"}, "cliente_parcela CSV")
    df["cliente_id"] = pd.to_numeric(df["cliente_id"], errors="raise").astype(int)
    df["parcela_id"] = pd.to_numeric(df["parcela_id"], errors="raise").astype(int)
    return df.drop_duplicates(["cliente_id", "parcela_id"], keep="first")


def _read_ranking_um_csv(path: str | Path = RANKING_UM_CSV) -> pd.DataFrame:
    df = _read_csv_existing(path, "ranking UM CSV")
    required = {
        "um_id",
        "ranking_um",
        "prioridad_regional",
        "parcelas_total",
        "parcelas_rankeadas",
        "prioridad_score_prom_pond",
    }
    _validate_columns(df, required, "ranking UM CSV")
    numeric_cols = {
        "um_id",
        "ranking_um",
        "parcelas_total",
        "parcelas_rankeadas",
        "parcelas_sin_ranking",
        "pct_parcelas_rankeadas",
        "area_cultivada_m2",
        "area_cultivada_ha",
        "area_rankeada_ha",
        "vid_parcelas",
        "olivo_parcelas",
        "prioridad_score_prom_pond",
        "prioridad_score_mediana",
        "riesgo_actual_prom_pond",
        "riesgo_5d_prom_pond",
        "riesgo_10d_prom_pond",
        "delta_10d_prom_pond",
        "pct_alta_critica",
        "pct_critica",
    }
    for col in numeric_cols & set(df.columns):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("ranking_um")


def _read_parcelas_um_csv(path: str | Path = PARCELAS_UM_CSV) -> pd.DataFrame:
    df = _read_csv_existing(path, "parcelas UM CSV")
    required = {"parcela_id", "um_id"}
    _validate_columns(df, required, "parcelas UM CSV")
    for col in ["parcela_id", "um_id", "um_fid", "area_m2", "intersection_m2", "pct_parcela_en_um"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["parcela_id"] = df["parcela_id"].astype(int)
    df["um_id"] = df["um_id"].astype(int)
    return df


def _read_zonas_um_geojson(path: str | Path = ZONAS_UM_GEOJSON) -> gpd.GeoDataFrame:
    geojson_path = Path(path)
    if not geojson_path.exists():
        raise FileNotFoundError(f"No existe GeoJSON de UM: {geojson_path}")
    zonas = gpd.read_file(geojson_path)
    _validate_columns(zonas, {"um_id"}, "GeoJSON de UM")
    if zonas.crs is None:
        zonas = zonas.set_crs("EPSG:4326")
    elif zonas.crs.to_epsg() != 4326:
        zonas = zonas.to_crs("EPSG:4326")
    zonas["um_id"] = pd.to_numeric(zonas["um_id"], errors="raise").astype(int)
    return zonas


def clientes_from_csv() -> list[dict[str, Any]]:
    clientes = _read_clientes_csv()
    relaciones = _read_cliente_parcela_csv()
    if clientes.empty:
        return []

    counts = relaciones.groupby("cliente_id")["parcela_id"].nunique()
    clientes["parcelas_asignadas"] = clientes["cliente_id"].map(counts).fillna(0).astype(int)
    return _records_from_df(clientes.sort_values(["tipo", "nombre"]))


def latest_geojson_cliente_from_csv(cliente_id: int) -> dict[str, Any]:
    clientes = _read_clientes_csv()
    relaciones = _read_cliente_parcela_csv()
    if clientes.empty:
        raise FileNotFoundError(f"No existe catálogo local de clientes: {CLIENTES_CSV}")
    if relaciones.empty:
        raise FileNotFoundError(
            f"No existe relación local cliente-parcela: {CLIENTE_PARCELA_CSV}"
        )
    if int(cliente_id) not in set(clientes["cliente_id"]):
        raise ValueError(f"Cliente inexistente o inactivo: {cliente_id}")

    parcela_ids = set(
        relaciones.loc[relaciones["cliente_id"] == int(cliente_id), "parcela_id"]
        .astype(int)
        .tolist()
    )
    if not parcela_ids:
        raise ValueError(f"Cliente sin parcelas asociadas: {cliente_id}")

    data = latest_geojson_from_csv()
    filtered_features = [
        feature
        for feature in data["features"]
        if int(feature["properties"]["parcela_id"]) in parcela_ids
    ]
    data["features"] = filtered_features
    data["ranked_count"] = sum(
        1
        for feature in filtered_features
        if feature["properties"].get("ranking_global") is not None
    )
    data["total_count"] = len(filtered_features)
    data["cliente_id"] = int(cliente_id)
    return data


def regional_um_latest_from_csv(limit: int | None = None) -> list[dict[str, Any]]:
    df = _read_ranking_um_csv()
    df = _limit_df(df, limit)
    return _records_from_df(df)


def regional_um_latest_geojson_from_csv() -> dict[str, Any]:
    zonas = _read_zonas_um_geojson()
    ranking_um = _read_ranking_um_csv()

    merged = zonas.merge(ranking_um, on="um_id", how="left", suffixes=("", "_ranking"))
    if merged.empty:
        raise ValueError("No hay UM para devolver en GeoJSON regional.")

    merged = merged.sort_values("ranking_um", na_position="last")
    for col in merged.columns:
        if col != "geometry" and pd.api.types.is_datetime64_any_dtype(merged[col]):
            merged[col] = merged[col].dt.strftime("%Y-%m-%d")
    data = json.loads(merged.to_json())
    data["total_count"] = len(merged)
    data["ranked_count"] = int(merged["ranking_um"].notna().sum())
    return data


def regional_um_parcelas_latest_geojson_from_csv(um_id: int) -> dict[str, Any]:
    relaciones = _read_parcelas_um_csv()
    parcela_ids = set(
        relaciones.loc[relaciones["um_id"] == int(um_id), "parcela_id"].astype(int)
    )
    if not parcela_ids:
        raise ValueError(f"UM inexistente o sin parcelas asociadas: {um_id}")

    data = latest_geojson_subset_from_csv(parcela_ids)
    data["um_id"] = int(um_id)
    return data


def latest_from_postgis(limit: int | None = None) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            fecha_ranking,
            fecha_lectura,
            dias_desde_lectura,
            parcela_id,
            cultivo,
            ranking_global,
            ranking_por_cultivo,
            prioridad,
            prioridad_score,
            riesgo_actual,
            riesgo_pred_5d,
            riesgo_pred_10d,
            delta_5d,
            delta_10d,
            riesgo_operativo_5d,
            riesgo_operativo_10d,
            delta_operativo_5d,
            delta_operativo_10d,
            tendencia_reciente_5d,
            pendiente_operativa_5d,
            factor_estacional,
            ndmi_mean,
            msi_mean,
            ndwi_mean,
            nbr_mean,
            ndvi_mean
        FROM ranking_hidrico_latest
        ORDER BY ranking_global
    """
    params: list[Any] = []
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in row.items()
        }
        for row in rows
    ]


def latest_geojson_from_postgis() -> dict[str, Any]:
    import psycopg

    query = """
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', to_jsonb(t) - 'geom'
                )
                ORDER BY ranking_global
            ), '[]'::jsonb)
        )
        FROM ranking_hidrico_latest_geo t
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()[0]

    return result


def clientes_from_postgis() -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            c.cliente_id,
            c.nombre,
            c.tipo,
            c.descripcion,
            count(cp.parcela_id)::integer AS parcelas_asignadas
        FROM clientes c
        LEFT JOIN cliente_parcela cp
            ON cp.cliente_id = c.cliente_id
        WHERE c.activo = true
        GROUP BY c.cliente_id, c.nombre, c.tipo, c.descripcion
        ORDER BY c.tipo, c.nombre
    """
    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def latest_geojson_cliente_from_postgis(cliente_id: int) -> dict[str, Any]:
    import psycopg

    query = """
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', to_jsonb(t) - 'geom'
                )
                ORDER BY ranking_global NULLS LAST
            ), '[]'::jsonb),
            'cliente_id', %s,
            'ranked_count', count(ranking_global),
            'total_count', count(*)
        )
        FROM cliente_ranking_hidrico_latest_geo t
        WHERE cliente_id = %s
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [cliente_id, cliente_id])
            result = cur.fetchone()[0]

    if result["total_count"] == 0:
        raise ValueError(f"Cliente inexistente, inactivo o sin parcelas: {cliente_id}")
    return result


def regional_um_latest_from_postgis(limit: int | None = None) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            fecha_ranking,
            um_id,
            ranking_um,
            prioridad_regional,
            parcelas_total,
            parcelas_rankeadas,
            parcelas_sin_ranking,
            pct_parcelas_rankeadas,
            area_cultivada_ha,
            area_rankeada_ha,
            vid_parcelas,
            olivo_parcelas,
            prioridad_score_prom_pond,
            prioridad_score_mediana,
            riesgo_actual_prom_pond,
            riesgo_5d_prom_pond,
            riesgo_10d_prom_pond,
            delta_10d_prom_pond,
            pct_alta_critica,
            pct_critica
        FROM ranking_um_latest
        ORDER BY ranking_um
    """
    params: list[Any] = []
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in row.items()
        }
        for row in rows
    ]


def regional_um_latest_geojson_from_postgis() -> dict[str, Any]:
    import psycopg

    query = """
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', to_jsonb(t) - 'geom'
                )
                ORDER BY ranking_um
            ), '[]'::jsonb),
            'ranked_count', count(ranking_um),
            'total_count', count(*)
        )
        FROM ranking_um_latest_geo t
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            result = cur.fetchone()[0]

    return result


def regional_um_parcelas_latest_geojson_from_postgis(um_id: int) -> dict[str, Any]:
    import psycopg

    query = """
        SELECT jsonb_build_object(
            'type', 'FeatureCollection',
            'features', COALESCE(jsonb_agg(
                jsonb_build_object(
                    'type', 'Feature',
                    'geometry', ST_AsGeoJSON(q.geom)::jsonb,
                    'properties', to_jsonb(q) - 'geom'
                )
                ORDER BY q.ranking_global NULLS LAST
            ), '[]'::jsonb),
            'um_id', %s,
            'ranked_count', count(q.ranking_global),
            'total_count', count(*)
        )
        FROM (
            SELECT
                pu.um_id,
                p.parcela_id,
                p.cultivo_oficial,
                p.area_m2,
                r.fecha_ranking,
                r.fecha_lectura,
                r.dias_desde_lectura,
                COALESCE(r.cultivo, p.cultivo_oficial) AS cultivo,
                r.ranking_global,
                r.ranking_por_cultivo,
                CASE
                    WHEN r.ranking_global IS NULL THEN 'sin_ranking_latest'
                    ELSE 'rankeada'
                END AS estado_cobertura,
                COALESCE(r.prioridad, 'sin ranking') AS prioridad,
                r.prioridad_score,
                r.riesgo_actual,
                r.riesgo_pred_5d,
                r.riesgo_pred_10d,
                r.delta_5d,
                r.delta_10d,
                r.riesgo_operativo_5d,
                r.riesgo_operativo_10d,
                r.delta_operativo_5d,
                r.delta_operativo_10d,
                r.tendencia_reciente_5d,
                r.pendiente_operativa_5d,
                r.factor_estacional,
                r.ndmi_mean,
                r.msi_mean,
                r.ndwi_mean,
                r.nbr_mean,
                r.ndvi_mean,
                p.geom
            FROM parcela_um pu
            JOIN parcelas p
                ON p.parcela_id = pu.parcela_id
            LEFT JOIN ranking_hidrico_latest r
                ON r.parcela_id = pu.parcela_id
            WHERE pu.um_id = %s
        ) q
    """
    with psycopg.connect(database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [um_id, um_id])
            result = cur.fetchone()[0]

    if result["total_count"] == 0:
        raise ValueError(f"UM inexistente o sin parcelas asociadas: {um_id}")
    return result


def latest_ranking(limit: int | None = None) -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    rows = latest_from_postgis(limit) if source == "postgis" else latest_from_csv(limit)
    return {
        "source": source,
        "count": len(rows),
        "items": rows,
    }


def latest_geojson() -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    data = latest_geojson_from_postgis() if source == "postgis" else latest_geojson_from_csv()
    data["source"] = source
    return data


def clientes() -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    rows = clientes_from_postgis() if source == "postgis" else clientes_from_csv()
    return {"source": source, "count": len(rows), "items": rows}


def latest_geojson_cliente(cliente_id: int) -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    data = (
        latest_geojson_cliente_from_postgis(cliente_id)
        if source == "postgis"
        else latest_geojson_cliente_from_csv(cliente_id)
    )
    data["source"] = source
    return data


def regional_um_latest(limit: int | None = None) -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    rows = (
        regional_um_latest_from_postgis(limit)
        if source == "postgis"
        else regional_um_latest_from_csv(limit)
    )
    return {"source": source, "count": len(rows), "items": rows}


def regional_um_latest_geojson() -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    data = (
        regional_um_latest_geojson_from_postgis()
        if source == "postgis"
        else regional_um_latest_geojson_from_csv()
    )
    data["source"] = source
    return data


def regional_um_parcelas_latest_geojson(um_id: int) -> dict[str, Any]:
    source = "postgis" if database_url() else "csv"
    data = (
        regional_um_parcelas_latest_geojson_from_postgis(um_id)
        if source == "postgis"
        else regional_um_parcelas_latest_geojson_from_csv(um_id)
    )
    data["source"] = source
    return data


def _require_database_url() -> str:
    db_url = database_url()
    if not db_url:
        raise RuntimeError("Los endpoints admin requieren DATABASE_URL/PostGIS.")
    return db_url


def _clean_postgis_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in row.items()
    }


def admin_parcelas(
    limit: int | None = None,
    cultivo: str | None = None,
    activo: bool | None = True,
) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    where = []
    params: list[Any] = []
    if cultivo:
        where.append("p.cultivo_oficial = %s")
        params.append(cultivo)
    if activo is not None:
        where.append("p.activo = %s")
        params.append(activo)

    query = """
        SELECT
            p.parcela_id,
            p.cultivo_oficial,
            p.cultivo_original,
            p.area_m2,
            p.fuente,
            p.globalid,
            p.activo,
            p.updated_at,
            r.fecha_ranking,
            r.ranking_global,
            r.prioridad,
            r.riesgo_actual
        FROM parcelas p
        LEFT JOIN ranking_hidrico_latest r
            ON r.parcela_id = p.parcela_id
    """
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY p.parcela_id"
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = [_clean_postgis_row(dict(row)) for row in cur.fetchall()]

    return {"source": "postgis", "count": len(rows), "items": rows}


def admin_parcelas_disponibles(limit: int | None = None) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            p.parcela_id,
            p.cultivo_oficial,
            p.cultivo_original,
            p.area_m2,
            p.fuente,
            p.globalid,
            p.activo,
            p.updated_at,
            ST_AsGeoJSON(p.geom)::json AS geometry
        FROM parcelas p
        WHERE p.activo = true
          AND p.cultivo_oficial NOT IN ('vid', 'olivo')
        ORDER BY p.parcela_id
    """
    params: list[Any] = []
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = [_clean_postgis_row(dict(row)) for row in cur.fetchall()]

    return {"source": "postgis", "count": len(rows), "items": rows}


def admin_parcela(parcela_id: int) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            p.parcela_id,
            p.cultivo_oficial,
            p.cultivo_original,
            p.area_m2,
            p.fuente,
            p.globalid,
            p.activo,
            p.updated_at,
            ST_AsGeoJSON(p.geom)::json AS geometry,
            r.fecha_ranking,
            r.ranking_global,
            r.prioridad,
            r.riesgo_actual,
            r.riesgo_operativo_5d,
            r.riesgo_operativo_10d
        FROM parcelas p
        LEFT JOIN ranking_hidrico_latest r
            ON r.parcela_id = p.parcela_id
        WHERE p.parcela_id = %s
    """
    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, [parcela_id])
            row = cur.fetchone()

    if row is None:
        raise ValueError(f"Parcela inexistente: {parcela_id}")
    return {"source": "postgis", "item": _clean_postgis_row(dict(row))}


def admin_create_parcela(payload: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    geometry = payload.get("geometry")
    if not geometry:
        raise ValueError("geometry es requerido.")

    area_m2 = payload.get("area_m2")
    query = """
        INSERT INTO parcelas (
            parcela_id,
            cultivo_oficial,
            cultivo_original,
            area_m2,
            fuente,
            globalid,
            activo,
            geom
        )
        VALUES (
            %s,
            %s,
            %s,
            COALESCE(%s, ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography)),
            %s,
            %s,
            %s,
            ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
        )
        RETURNING
            parcela_id,
            cultivo_oficial,
            cultivo_original,
            area_m2,
            fuente,
            globalid,
            activo,
            updated_at,
            ST_AsGeoJSON(geom)::json AS geometry
    """
    geometry_text = json.dumps(geometry)
    params = [
        payload["parcela_id"],
        payload["cultivo_oficial"],
        payload.get("cultivo_original"),
        area_m2,
        geometry_text,
        payload.get("fuente", "manual"),
        payload.get("globalid"),
        payload.get("activo", True),
        geometry_text,
    ]

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            item = _clean_postgis_row(dict(cur.fetchone()))
        conn.commit()

    return {"source": "postgis", "item": item}


def admin_update_parcela(parcela_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    assignments = []
    params: list[Any] = []
    if "cultivo_oficial" in payload:
        assignments.append("cultivo_oficial = %s")
        params.append(payload["cultivo_oficial"])
    if "area_m2" in payload:
        assignments.append("area_m2 = %s")
        params.append(payload["area_m2"])
    if "cultivo_original" in payload:
        assignments.append("cultivo_original = %s")
        params.append(payload["cultivo_original"])
    if "fuente" in payload:
        assignments.append("fuente = %s")
        params.append(payload["fuente"])
    if "globalid" in payload:
        assignments.append("globalid = %s")
        params.append(payload["globalid"])
    if "activo" in payload:
        assignments.append("activo = %s")
        params.append(payload["activo"])
    if "geometry" in payload:
        geometry_text = json.dumps(payload["geometry"])
        assignments.append("geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))")
        params.append(geometry_text)
        if "area_m2" not in payload:
            assignments.append(
                "area_m2 = ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography)"
            )
            params.append(geometry_text)

    if not assignments:
        raise ValueError("No hay campos para actualizar.")

    query = f"""
        UPDATE parcelas
        SET {", ".join(assignments)}, updated_at = now()
        WHERE parcela_id = %s
        RETURNING
            parcela_id,
            cultivo_oficial,
            cultivo_original,
            area_m2,
            fuente,
            globalid,
            activo,
            updated_at,
            ST_AsGeoJSON(geom)::json AS geometry
    """
    params.append(parcela_id)

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Parcela inexistente: {parcela_id}")
            item = _clean_postgis_row(dict(row))
        conn.commit()

    return {"source": "postgis", "item": item}


def admin_activar_parcela_disponible(
    parcela_id: int,
    cultivo_oficial: str,
    cliente_id: int | None = None,
    etiqueta: str | None = None,
) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE parcelas
                SET cultivo_oficial = %s,
                    activo = true,
                    fuente = CASE
                        WHEN fuente = 'idemendoza' THEN 'idemendoza_admin'
                        ELSE fuente
                    END,
                    updated_at = now()
                WHERE parcela_id = %s
                RETURNING
                    parcela_id,
                    cultivo_oficial,
                    cultivo_original,
                    area_m2,
                    fuente,
                    activo,
                    updated_at
                """,
                [cultivo_oficial, parcela_id],
            )
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Parcela inexistente: {parcela_id}")
            item = _clean_postgis_row(dict(row))

            assigned = None
            if cliente_id is not None:
                cur.execute("SELECT 1 FROM clientes WHERE cliente_id = %s", [cliente_id])
                if cur.fetchone() is None:
                    raise ValueError(f"Cliente inexistente: {cliente_id}")
                cur.execute(
                    """
                    INSERT INTO cliente_parcela (cliente_id, parcela_id, etiqueta)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (cliente_id, parcela_id) DO UPDATE SET
                        etiqueta = EXCLUDED.etiqueta
                    RETURNING cliente_id, parcela_id, etiqueta, created_at
                    """,
                    [cliente_id, parcela_id, etiqueta],
                )
                assigned = _clean_postgis_row(dict(cur.fetchone()))
        conn.commit()

    return {"source": "postgis", "item": item, "cliente_parcela": assigned}


def admin_deactivate_parcela(parcela_id: int) -> dict[str, Any]:
    import psycopg

    with psycopg.connect(_require_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE parcelas
                SET activo = false,
                    updated_at = now()
                WHERE parcela_id = %s
                  AND activo = true
                """,
                [parcela_id],
            )
            updated = cur.rowcount
        conn.commit()

    if updated == 0:
        raise ValueError(f"Parcela inexistente o ya inactiva: {parcela_id}")
    return {"source": "postgis", "deleted": True, "parcela_id": int(parcela_id)}


def admin_clientes(limit: int | None = None) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            c.cliente_id,
            c.nombre,
            c.tipo,
            c.descripcion,
            c.activo,
            c.created_at,
            c.updated_at,
            count(cp.parcela_id)::integer AS parcelas_asignadas
        FROM clientes c
        LEFT JOIN cliente_parcela cp
            ON cp.cliente_id = c.cliente_id
        GROUP BY c.cliente_id
        ORDER BY c.activo DESC, c.tipo, c.nombre
    """
    params: list[Any] = []
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = [_clean_postgis_row(dict(row)) for row in cur.fetchall()]

    return {"source": "postgis", "count": len(rows), "items": rows}


def admin_cliente_parcelas(cliente_id: int) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    query_cliente = """
        SELECT cliente_id, nombre, tipo, descripcion, activo
        FROM clientes
        WHERE cliente_id = %s
    """
    query_parcelas = """
        SELECT
            cp.cliente_id,
            cp.parcela_id,
            cp.etiqueta,
            p.cultivo_oficial,
            p.area_m2,
            r.ranking_global,
            r.prioridad,
            r.riesgo_actual,
            r.fecha_ranking
        FROM cliente_parcela cp
        JOIN parcelas p
            ON p.parcela_id = cp.parcela_id
        LEFT JOIN ranking_hidrico_latest r
            ON r.parcela_id = cp.parcela_id
        WHERE cp.cliente_id = %s
        ORDER BY cp.etiqueta NULLS LAST, cp.parcela_id
    """
    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query_cliente, [cliente_id])
            cliente = cur.fetchone()
            if cliente is None:
                raise ValueError(f"Cliente inexistente: {cliente_id}")

            cur.execute(query_parcelas, [cliente_id])
            parcelas = [_clean_postgis_row(dict(row)) for row in cur.fetchall()]

    return {
        "source": "postgis",
        "cliente": _clean_postgis_row(dict(cliente)),
        "count": len(parcelas),
        "items": parcelas,
    }


def admin_create_cliente(payload: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    cliente_id = payload.get("cliente_id")
    nombre = payload.get("nombre")
    tipo = payload.get("tipo")
    descripcion = payload.get("descripcion")
    activo = payload.get("activo", True)

    if cliente_id is None:
        query = """
            INSERT INTO clientes (nombre, tipo, descripcion, activo)
            VALUES (%s, %s, %s, %s)
            RETURNING cliente_id, nombre, tipo, descripcion, activo, created_at, updated_at
        """
        params = [nombre, tipo, descripcion, activo]
    else:
        query = """
            INSERT INTO clientes (cliente_id, nombre, tipo, descripcion, activo)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING cliente_id, nombre, tipo, descripcion, activo, created_at, updated_at
        """
        params = [cliente_id, nombre, tipo, descripcion, activo]

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = _clean_postgis_row(dict(cur.fetchone()))
        conn.commit()

    return {"source": "postgis", "item": row}


def admin_update_cliente(cliente_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    allowed = ["nombre", "tipo", "descripcion", "activo"]
    updates = [field for field in allowed if field in payload]
    if not updates:
        raise ValueError("No hay campos para actualizar.")

    assignments = ", ".join(f"{field} = %s" for field in updates)
    query = f"""
        UPDATE clientes
        SET {assignments}, updated_at = now()
        WHERE cliente_id = %s
        RETURNING cliente_id, nombre, tipo, descripcion, activo, created_at, updated_at
    """
    params = [payload[field] for field in updates] + [cliente_id]

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            if row is None:
                raise ValueError(f"Cliente inexistente: {cliente_id}")
            item = _clean_postgis_row(dict(row))
        conn.commit()

    return {"source": "postgis", "item": item}


def admin_assign_cliente_parcela(
    cliente_id: int,
    parcela_id: int,
    etiqueta: str | None = None,
) -> dict[str, Any]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(_require_database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM clientes WHERE cliente_id = %s", [cliente_id])
            if cur.fetchone() is None:
                raise ValueError(f"Cliente inexistente: {cliente_id}")

            cur.execute("SELECT 1 FROM parcelas WHERE parcela_id = %s", [parcela_id])
            if cur.fetchone() is None:
                raise ValueError(f"Parcela inexistente: {parcela_id}")

            cur.execute(
                """
                INSERT INTO cliente_parcela (cliente_id, parcela_id, etiqueta)
                VALUES (%s, %s, %s)
                ON CONFLICT (cliente_id, parcela_id) DO UPDATE SET
                    etiqueta = EXCLUDED.etiqueta
                RETURNING cliente_id, parcela_id, etiqueta, created_at
                """,
                [cliente_id, parcela_id, etiqueta],
            )
            item = _clean_postgis_row(dict(cur.fetchone()))
        conn.commit()

    return {"source": "postgis", "item": item}


def admin_delete_cliente_parcela(cliente_id: int, parcela_id: int) -> dict[str, Any]:
    import psycopg

    with psycopg.connect(_require_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM cliente_parcela
                WHERE cliente_id = %s
                  AND parcela_id = %s
                """,
                [cliente_id, parcela_id],
            )
            deleted = cur.rowcount
        conn.commit()

    if deleted == 0:
        raise ValueError(
            f"No existe relación cliente-parcela: cliente_id={cliente_id}, parcela_id={parcela_id}"
        )
    return {
        "source": "postgis",
        "deleted": True,
        "cliente_id": int(cliente_id),
        "parcela_id": int(parcela_id),
    }


def ranking_by_fecha(fecha: str, limit: int | None = None) -> dict[str, Any]:
    fecha = pd.to_datetime(fecha).strftime("%Y-%m-%d")
    if not database_url():
        df = _read_ranking_csv(_ranking_csv_path_for_fecha(fecha))
        df = df[df["fecha_actual"] == fecha].sort_values("ranking_global")
        df = _limit_df(df, limit)
        rows = _records_from_df(df)
        return {"source": "csv", "fecha": fecha, "count": len(rows), "items": rows}

    import psycopg
    from psycopg.rows import dict_row

    query = """
        SELECT
            fecha_ranking,
            fecha_lectura,
            dias_desde_lectura,
            parcela_id,
            cultivo,
            ranking_global,
            ranking_por_cultivo,
            prioridad,
            prioridad_score,
            riesgo_actual,
            riesgo_pred_5d,
            riesgo_pred_10d,
            delta_5d,
            delta_10d,
            riesgo_operativo_5d,
            riesgo_operativo_10d,
            delta_operativo_5d,
            delta_operativo_10d,
            tendencia_reciente_5d,
            pendiente_operativa_5d,
            factor_estacional,
            ndmi_mean,
            msi_mean,
            ndwi_mean,
            nbr_mean,
            ndvi_mean
        FROM ranking_hidrico
        WHERE fecha_ranking = %s
        ORDER BY ranking_global
    """
    params: list[Any] = [fecha]
    if limit:
        query += " LIMIT %s"
        params.append(limit)

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    clean_rows = [
        {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in row.items()
        }
        for row in rows
    ]
    return {"source": "postgis", "fecha": fecha, "count": len(clean_rows), "items": clean_rows}
