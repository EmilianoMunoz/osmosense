from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.constants import (
    ACCION_COLOR,
    CONFIANZA_COLOR,
    PRIORIDAD_COLOR,
    PRIORIDAD_ORDEN_MAPA,
)

RISK_ANIMATION_ORDER = ["baja", "media", "alta", "critica"]


def risk_category(value: Any) -> str:
    if pd.isna(value):
        return "sin ranking"
    value = float(value)
    if value < 35:
        return "baja"
    if value < 47.5:
        return "media"
    if value < 55:
        return "alta"
    return "critica"


def map_color_config(color_by: str) -> tuple[dict[str, str] | None, dict[str, list[str]] | None, str]:
    if color_by == "prioridad_visual":
        return PRIORIDAD_COLOR, {"prioridad_visual": PRIORIDAD_ORDEN_MAPA}, "Prioridad"
    if color_by == "confianza_lectura":
        return CONFIANZA_COLOR, {"confianza_lectura": ["alta", "media", "baja", "sin_ranking"]}, "Confianza"
    if color_by == "accion_visual":
        return ACCION_COLOR, {"accion_visual": list(ACCION_COLOR)}, "Acción"
    if color_by == "cultivo_original":
        return None, None, "Cultivo original"
    if color_by == "cultivo_oficial":
        return None, None, "Cultivo operativo"
    if color_by == "fuente":
        return None, None, "Fuente"
    return PRIORIDAD_COLOR, {"prioridad": PRIORIDAD_ORDEN_MAPA}, "Prioridad"


def selected_parcela_id(selection: Any) -> int | None:
    try:
        points = selection["selection"]["points"]
    except (TypeError, KeyError):
        return None
    if not points:
        return None
    point = points[0]
    value = point.get("location")
    if value is None and point.get("customdata"):
        value = point["customdata"][0]
    if value is None:
        return None
    return int(value)


def bbox_center_zoom(data: dict[str, Any]) -> tuple[dict[str, float], float]:
    lats: list[float] = []
    lons: list[float] = []

    def extract_coords(coords: Any) -> None:
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            lons.append(coords[0])
            lats.append(coords[1])
        else:
            for sub in coords:
                extract_coords(sub)

    for feature in data.get("features", []):
        geom = feature.get("geometry")
        if geom is None:
            continue
        extract_coords(geom.get("coordinates", []))

    if not lats or not lons:
        return {"lat": -34.6, "lon": -68.35}, 8.3

    lat_min, lat_max = min(lats), max(lats)
    lon_min, lon_max = min(lons), max(lons)
    center = {"lat": (lat_min + lat_max) / 2, "lon": (lon_min + lon_max) / 2}

    span = max(lat_max - lat_min, lon_max - lon_min)
    if span < 0.02:
        zoom = 14.0
    elif span < 0.05:
        zoom = 13.0
    elif span < 0.1:
        zoom = 12.0
    elif span < 0.3:
        zoom = 11.0
    elif span < 0.6:
        zoom = 10.0
    elif span < 1.2:
        zoom = 9.0
    else:
        zoom = 8.3

    return center, zoom


def enrich_map_hover(df: pd.DataFrame, admin_mode: bool) -> pd.DataFrame:
    df_map = df.copy()
    df_map["riesgo_5_dias"] = (
        df_map["riesgo_operativo_5d"].fillna(df_map["riesgo_pred_5d"])
        if {"riesgo_operativo_5d", "riesgo_pred_5d"}.issubset(df_map.columns)
        else df_map.get("riesgo_pred_5d")
    )
    df_map["riesgo_10_dias"] = (
        df_map["riesgo_operativo_10d"].fillna(df_map["riesgo_pred_10d"])
        if {"riesgo_operativo_10d", "riesgo_pred_10d"}.issubset(df_map.columns)
        else df_map.get("riesgo_pred_10d")
    )
    df_map["delta_10_dias"] = (
        df_map["delta_operativo_10d"].fillna(df_map["delta_10d"])
        if {"delta_operativo_10d", "delta_10d"}.issubset(df_map.columns)
        else df_map.get("delta_10d")
    )
    return df_map


def map_hover_data(admin_mode: bool, df: pd.DataFrame) -> dict[str, Any]:
    if not admin_mode:
        hover_data = {
            "cultivo": True,
            "prioridad_visual_label": True,
            "riesgo_actual": ":.1f",
            "riesgo_5_dias": ":.1f",
            "riesgo_10_dias": ":.1f",
            "delta_10_dias": ":.1f",
            "parcela_id": False,
        }
        if "riesgo_mapa" in df.columns:
            hover_data["riesgo_mapa"] = ":.1f"
        if "dia_proyeccion" in df.columns:
            hover_data["dia_proyeccion"] = True
        if "confianza_lectura" in df.columns:
            hover_data["confianza_lectura"] = True
        return hover_data

    hover_data = {
        "cultivo": True,
        "prioridad_visual_label": True,
        "prioridad_score": ":.1f",
        "riesgo_actual": ":.1f",
        "riesgo_5_dias": ":.1f",
        "riesgo_10_dias": ":.1f",
        "delta_10_dias": ":.1f",
        "ranking_global": True,
        "parcela_id": False,
    }
    if "estado_cobertura" in df.columns:
        hover_data["estado_cobertura"] = True
    optional_hover = {
        "confianza_lectura": True,
        "outlier_espacial": True,
        "tipo_outlier_espacial": True,
        "persistencia_temporal": True,
        "diagnostico_outlier": True,
        "neighbor_riesgo_actual_median": ":.1f",
        "riesgo_actual_vs_neighbor_median": ":.1f",
        "historial_reciente_count": True,
        "riesgo_reciente_weighted_mean": ":.1f",
        "motivo_ruido": True,
        "severidad_ruido": ":.1f",
        "accion_recomendada": True,
        "outlier_count_30d": True,
        "persistente_count_30d": True,
        "ruido_count_30d": True,
    }
    for column, value in optional_hover.items():
        if column in df.columns:
            hover_data[column] = value
    return {column: value for column, value in hover_data.items() if column in df.columns}


def risk_animation_frame(df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for day in range(0, 11):
        frame = df.copy()
        if day <= 5:
            ratio = day / 5 if day else 0
            frame["riesgo_mapa"] = (
                frame["riesgo_actual"]
                + (frame["riesgo_5_dias"] - frame["riesgo_actual"]) * ratio
            )
        else:
            ratio = (day - 5) / 5
            frame["riesgo_mapa"] = (
                frame["riesgo_5_dias"]
                + (frame["riesgo_10_dias"] - frame["riesgo_5_dias"]) * ratio
            )
        frame["dia_proyeccion"] = day
        frame["riesgo_categoria"] = "sin ranking"
        ranked = frame["riesgo_mapa"].notna()
        pct = frame.loc[ranked, "riesgo_mapa"].rank(pct=True, ascending=False)
        frame.loc[ranked & (pct <= 0.10), "riesgo_categoria"] = "critica"
        frame.loc[ranked & (pct > 0.10) & (pct <= 0.30), "riesgo_categoria"] = "alta"
        frame.loc[ranked & (pct > 0.30) & (pct <= 0.60), "riesgo_categoria"] = "media"
        frame.loc[ranked & (pct > 0.60), "riesgo_categoria"] = "baja"
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def render_map(
    data: dict[str, Any],
    df: pd.DataFrame,
    color_by: str = "prioridad_visual",
    center: dict[str, float] | None = None,
    zoom: float = 8.3,
    selected_id: int | None = None,
    admin_mode: bool = True,
    map_key: str = "ranking_map",
    numeric_color: str | None = None,
    numeric_color_title: str = "Riesgo",
    risk_animation: bool = False,
) -> int | None:
    if df.empty:
        st.warning("No hay parcelas para mostrar con los filtros actuales.")
        return None

    df_map = enrich_map_hover(df, admin_mode)
    center_lat = center["lat"] if center else -34.6
    center_lon = center["lon"] if center else -68.35
    hover_data = map_hover_data(admin_mode, df_map)

    color_map, category_orders, legend_title = map_color_config(color_by)
    if numeric_color is None and color_by not in df.columns:
        color_by = "prioridad"
        color_map, category_orders, legend_title = map_color_config(color_by)

    if risk_animation and not admin_mode:
        df_anim = risk_animation_frame(df_map)
        hover_data = map_hover_data(admin_mode, df_anim)
        fig = px.choropleth_mapbox(
            df_anim,
            geojson=data,
            locations="parcela_id",
            featureidkey="properties.parcela_id",
            color="riesgo_categoria",
            color_discrete_map=PRIORIDAD_COLOR,
            category_orders={"riesgo_categoria": RISK_ANIMATION_ORDER},
            animation_frame="dia_proyeccion",
            hover_name="parcela_id",
            hover_data=hover_data,
            custom_data=["parcela_id"],
            center={"lat": center_lat, "lon": center_lon},
            zoom=zoom,
            opacity=0.72,
            height=650,
            mapbox_style="carto-positron",
        )
        legend_title = "Estrés hídrico"
        if fig.layout.sliders:
            slider = fig.layout.sliders[0].to_plotly_json()
            slider["currentvalue"] = {"prefix": "Proyección: ", "suffix": " días"}
            slider["pad"] = {"t": 24}
            fig.update_layout(sliders=[slider])
    elif numeric_color is not None and numeric_color in df_map.columns:
        fig = px.choropleth_mapbox(
            df_map,
            geojson=data,
            locations="parcela_id",
            featureidkey="properties.parcela_id",
            color=numeric_color,
            color_continuous_scale=[
                [0.0, "#1a9850"],
                [0.35, "#91cf60"],
                [0.55, "#ffffbf"],
                [0.75, "#fdae61"],
                [1.0, "#d7191c"],
            ],
            range_color=[0, 100],
            hover_name="parcela_id",
            hover_data=hover_data,
            custom_data=["parcela_id"],
            center={"lat": center_lat, "lon": center_lon},
            zoom=zoom,
            opacity=0.72,
            height=650,
            mapbox_style="carto-positron",
        )
        fig.update_layout(coloraxis_colorbar={"title": numeric_color_title})
        legend_title = numeric_color_title
    else:
        fig = px.choropleth_mapbox(
            df_map,
            geojson=data,
            locations="parcela_id",
            featureidkey="properties.parcela_id",
            color=color_by,
            color_discrete_map=color_map,
            category_orders=category_orders,
            hover_name="parcela_id",
            hover_data=hover_data,
            custom_data=["parcela_id"],
            center={"lat": center_lat, "lon": center_lon},
            zoom=zoom,
            opacity=0.68,
            height=650,
            mapbox_style="carto-positron",
        )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text=legend_title,
        uirevision=map_key,
    )
    fig.update_mapboxes(uirevision=map_key)
    if selected_id is not None:
        selected_features = [
            feature
            for feature in data.get("features", [])
            if int(feature.get("properties", {}).get("parcela_id")) == int(selected_id)
        ]
        if selected_features:
            fig.add_trace(
                go.Choroplethmapbox(
                    geojson={"type": "FeatureCollection", "features": selected_features},
                    locations=[int(selected_id)],
                    z=[1],
                    featureidkey="properties.parcela_id",
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                    marker_line_color="#111827",
                    marker_line_width=4,
                    marker_opacity=0,
                    showscale=False,
                    hoverinfo="skip",
                    name="Seleccionada",
                )
            )
    selection = st.plotly_chart(
        fig,
        width="stretch",
        key=map_key,
        on_select="rerun",
        selection_mode="points",
    )
    return selected_parcela_id(selection)
