from __future__ import annotations

import os
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv


def api_base_url() -> str:
    load_dotenv()
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@st.cache_data(show_spinner=False)
def fetch_geojson_from_api(base_url: str) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{base_url}/rankings/latest/geojson", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False)
def fetch_clientes_from_api(base_url: str) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{base_url}/clientes", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False)
def fetch_cliente_geojson_from_api(base_url: str, cliente_id: int) -> dict[str, Any] | None:
    try:
        response = requests.get(
            f"{base_url}/clientes/{cliente_id}/rankings/latest/geojson",
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False)
def fetch_admin_parcelas_disponibles_from_api(
    base_url: str,
    limit: int | None = None,
) -> dict[str, Any] | None:
    try:
        params = {"limit": limit} if limit else None
        response = requests.get(
            f"{base_url}/admin/parcelas/disponibles",
            params=params,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def activar_parcela_disponible(
    parcela_id: int,
    cultivo_oficial: str,
    cliente_id: int | None = None,
    etiqueta: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"cultivo_oficial": cultivo_oficial}
    if cliente_id is not None:
        payload["cliente_id"] = int(cliente_id)
    if etiqueta:
        payload["etiqueta"] = etiqueta

    response = requests.post(
        f"{api_base_url()}/admin/parcelas/{int(parcela_id)}/activar-disponible",
        json=payload,
        timeout=10,
    )
    response.raise_for_status()
    fetch_admin_parcelas_disponibles_from_api.clear()
    fetch_geojson_from_api.clear()
    fetch_clientes_from_api.clear()
    fetch_cliente_geojson_from_api.clear()
    return response.json()


@st.cache_data(show_spinner=False)
def fetch_regional_um_geojson_from_api(base_url: str) -> dict[str, Any] | None:
    try:
        response = requests.get(f"{base_url}/regional/um/latest/geojson", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False)
def fetch_regional_um_parcelas_geojson_from_api(
    base_url: str,
    um_id: int,
) -> dict[str, Any] | None:
    try:
        response = requests.get(
            f"{base_url}/regional/um/{um_id}/parcelas/latest/geojson",
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


@st.cache_data(show_spinner=False)
def load_geojson_local() -> dict[str, Any]:
    from app.services.rankings import latest_geojson_from_csv

    data = latest_geojson_from_csv()
    data["source"] = "local"
    return data


@st.cache_data(show_spinner=False)
def load_clientes_local() -> dict[str, Any]:
    from app.services.rankings import clientes

    return clientes()


@st.cache_data(show_spinner=False)
def load_cliente_geojson_local(cliente_id: int) -> dict[str, Any]:
    from app.services.rankings import latest_geojson_cliente_from_csv

    data = latest_geojson_cliente_from_csv(cliente_id)
    data["source"] = "local"
    return data


def load_clientes() -> dict[str, Any]:
    base_url = api_base_url()
    data = fetch_clientes_from_api(base_url)
    if data is not None:
        return data
    return load_clientes_local()


def load_geojson(cliente_id: int | None = None) -> dict[str, Any]:
    base_url = api_base_url()
    if cliente_id is not None:
        data = fetch_cliente_geojson_from_api(base_url, cliente_id)
        if data is not None:
            return data
        return load_cliente_geojson_local(cliente_id)

    data = fetch_geojson_from_api(base_url)
    if data is not None:
        return data
    return load_geojson_local()


def admin_disponibles_to_geojson(data: dict[str, Any]) -> dict[str, Any]:
    features = []
    for item in data.get("items", []):
        geometry = item.get("geometry")
        if not geometry:
            continue
        properties = {key: value for key, value in item.items() if key != "geometry"}
        features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": properties,
            }
        )
    return {
        "type": "FeatureCollection",
        "source": data.get("source"),
        "features": features,
        "count": data.get("count", len(features)),
    }


def load_admin_parcelas_disponibles(limit: int | None = 3000) -> dict[str, Any]:
    data = fetch_admin_parcelas_disponibles_from_api(api_base_url(), limit=limit)
    if data is None:
        return {"source": "api_unavailable", "count": 0, "items": []}
    return admin_disponibles_to_geojson(data)


def features_to_frame(data: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for feature in data.get("features", []):
        rows.append(feature.get("properties", {}).copy())
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if "cultivo" not in df.columns and "cultivo_oficial" in df.columns:
        df["cultivo"] = df["cultivo_oficial"]
    elif "cultivo_oficial" in df.columns:
        df["cultivo"] = df["cultivo"].fillna(df["cultivo_oficial"])

    numeric_cols = [
        "ranking_global",
        "ranking_por_cultivo",
        "parcela_id",
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
        "area_m2",
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
        "dias_desde_lectura",
        "zona_id",
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
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "accion_recomendada" in df.columns:
        df["accion_visual"] = df["accion_recomendada"].fillna("sin_accion")
    if "ranking_global" in df.columns:
        return df.sort_values("ranking_global", na_position="last")
    if "ranking_um" in df.columns:
        return df.sort_values("ranking_um", na_position="last")
    return df


def filtered_geojson(data: dict[str, Any], ids: set[int]) -> dict[str, Any]:
    features = []
    for feature in data.get("features", []):
        parcela_id = feature.get("properties", {}).get("parcela_id")
        if parcela_id is None or int(parcela_id) not in ids:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": {"parcela_id": int(parcela_id)},
            }
        )
    return {
        "type": "FeatureCollection",
        "source": data.get("source"),
        "features": features,
    }


@st.cache_data(show_spinner=False)
def load_zonificacion_san_rafael(
    path: str = "data/zonificacion/um_con_cultivos.geojson",
) -> tuple[dict[str, Any], pd.DataFrame]:
    gdf = gpd.read_file(path).to_crs("EPSG:4326")
    gdf = gdf.reset_index(drop=True).copy()
    gdf["zona_id"] = gdf.index.astype(int)
    for col in gdf.columns:
        if col != "geometry" and pd.api.types.is_datetime64_any_dtype(gdf[col]):
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%d")

    data = gdf.to_json()
    import json

    geojson = json.loads(data)
    geojson["source"] = "local"

    df = pd.DataFrame(gdf.drop(columns="geometry"))
    numeric_cols = [
        "zona_id",
        "fid",
        "sup_ha",
        "sup_ha_original_calc",
        "sup_ha_san_rafael",
        "pct_sup_en_san_rafael",
        "alt_media",
        "pp_med_a",
        "um_id",
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
        "ranking_um",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return geojson, df


def normalize_regional_um_geojson(data: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    for feature in data.get("features", []):
        props = feature.setdefault("properties", {})
        if "zona_id" not in props and "um_id" in props:
            props["zona_id"] = props["um_id"]
    df = features_to_frame(data)
    if "zona_id" not in df.columns and "um_id" in df.columns:
        df["zona_id"] = df["um_id"]
    return data, df


def load_zonificacion_regional() -> tuple[dict[str, Any], pd.DataFrame]:
    base_url = api_base_url()
    data = fetch_regional_um_geojson_from_api(base_url)
    if data is not None:
        return normalize_regional_um_geojson(data)
    return load_zonificacion_san_rafael()


def load_regional_um_parcelas_geojson(um_id: int) -> dict[str, Any]:
    base_url = api_base_url()
    data = fetch_regional_um_parcelas_geojson_from_api(base_url, um_id)
    if data is not None:
        return data

    mapping = load_parcelas_um()
    parcela_ids = set(
        mapping.loc[mapping["um_id"] == int(um_id), "parcela_id"]
        .dropna()
        .astype(int)
        .tolist()
    )
    data = load_geojson(None)
    filtered_features = [
        feature
        for feature in data.get("features", [])
        if int(feature.get("properties", {}).get("parcela_id")) in parcela_ids
    ]
    result = {
        "type": "FeatureCollection",
        "source": data.get("source", "local"),
        "features": filtered_features,
        "um_id": int(um_id),
        "total_count": len(filtered_features),
        "ranked_count": sum(
            1
            for feature in filtered_features
            if feature.get("properties", {}).get("ranking_global") is not None
        ),
    }
    return result


@st.cache_data(show_spinner=False)
def load_parcelas_um(path: str = "data/zonificacion/parcelas_um.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    numeric_cols = [
        "parcela_id",
        "area_m2",
        "um_id",
        "um_fid",
        "intersection_m2",
        "pct_parcela_en_um",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
