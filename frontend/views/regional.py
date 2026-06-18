from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from frontend.components.branding import render_fullscreen_loader
from frontend.config import local_fallback_enabled
from frontend.constants import PRIORIDAD_COLOR, PRIORIDAD_ORDEN_MAPA
from frontend.data import (
    features_to_frame,
    filtered_geojson,
    load_api_health,
    load_regional_um_parcelas_geojson,
    load_zonificacion_regional,
)
from frontend.logic import add_dynamic_priority, add_regional_dynamic_priority
from frontend.map import bbox_center_zoom, render_map, selected_parcela_id


COLOR_OPTIONS = {
    "Prioridad regional": "prioridad_regional_visual",
    "Riesgo promedio": "prioridad_score_prom_pond",
    "% alta/crítica": "pct_alta_critica",
    "Superficie cultivada": "area_cultivada_ha",
}


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def render_regional_metrics(df: pd.DataFrame) -> None:
    parcelas = int(df["parcelas_total"].sum()) if "parcelas_total" in df.columns else 0
    rankeadas = int(df["parcelas_rankeadas"].sum()) if "parcelas_rankeadas" in df.columns else 0
    area_ha = df["area_cultivada_ha"].sum() if "area_cultivada_ha" in df.columns else 0
    cobertura = (rankeadas / parcelas * 100) if parcelas else 0
    fecha = "-"
    if "fecha_actual" in df.columns and not df["fecha_actual"].dropna().empty:
        fecha = str(df["fecha_actual"].dropna().mode().iloc[0])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("UM con cultivos", len(df))
    col2.metric("Parcelas", f"{parcelas:,}".replace(",", "."))
    col3.metric("Cobertura ranking", f"{cobertura:.1f}%")
    col4.metric("Superficie cultivada", f"{area_ha:,.0f} ha".replace(",", "."))
    col5.metric("Fecha ranking", fecha)


def render_regional_sidebar(df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    st.sidebar.header("Zonificación regional")
    priority_mode = st.sidebar.radio(
        "Categorización",
        ["Umbrales fijos", "Relativa por percentiles"],
        help=(
            "Umbrales fijos usa la prioridad regional calculada por el ranking. "
            "Relativa por percentiles compara solo las UM visibles según su score regional."
        ),
    )
    color_label = st.sidebar.selectbox("Color del mapa", list(COLOR_OPTIONS), index=0)
    color_by = COLOR_OPTIONS[color_label]

    cuencas = st.sidebar.multiselect(
        "Cuenca",
        options=sorted(df["cuenca"].dropna().unique()),
        default=sorted(df["cuenca"].dropna().unique()),
    )
    min_parcelas = st.sidebar.slider(
        "Mínimo de parcelas por UM",
        1,
        int(df["parcelas_total"].max()),
        1,
    )

    base = df[
        df["cuenca"].isin(cuencas)
        & (df["parcelas_total"] >= min_parcelas)
    ].copy()
    base = add_regional_dynamic_priority(base, priority_mode)

    priority_options = [
        p for p in PRIORIDAD_ORDEN_MAPA if p in set(base["prioridad_regional_visual"].dropna())
    ]
    prioridades = st.sidebar.multiselect(
        "Prioridad regional",
        options=priority_options,
        default=priority_options,
        format_func=lambda value: value.capitalize(),
    )

    filtered = base[base["prioridad_regional_visual"].isin(prioridades)].copy()
    return filtered, color_by


def filter_zonificacion_geojson(data: dict[str, Any], ids: set[int]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "source": data.get("source"),
        "features": [
            feature
            for feature in data.get("features", [])
            if int(feature.get("properties", {}).get("zona_id")) in ids
        ],
    }


def regional_hover_data(color_by: str) -> dict[str, Any]:
    hover_data: dict[str, Any] = {
        "ranking_um": True,
        "prioridad_regional_visual_label": True,
        "cuenca": True,
        "parcelas_total": True,
        "parcelas_rankeadas": True,
        "pct_parcelas_rankeadas": ":.1f",
        "area_cultivada_ha": ":.1f",
        "prioridad_score_prom_pond": ":.1f",
        "riesgo_actual_prom_pond": ":.1f",
        "riesgo_10d_prom_pond": ":.1f",
        "delta_10d_prom_pond": ":.1f",
        "pct_alta_critica": ":.1f",
        "zona_id": False,
    }
    if color_by not in hover_data:
        hover_data[color_by] = True
    return hover_data


def render_regional_map(
    data: dict[str, Any],
    df: pd.DataFrame,
    color_by: str,
    selected_id: int | None = None,
) -> int | None:
    if df.empty:
        st.warning("No hay UM para mostrar con los filtros actuales.")
        return None

    center, zoom = bbox_center_zoom(data)
    color_kwargs: dict[str, Any] = {}
    legend_title = next(label for label, col in COLOR_OPTIONS.items() if col == color_by)
    if color_by == "prioridad_regional_visual":
        color_kwargs = {
            "color_discrete_map": PRIORIDAD_COLOR,
            "category_orders": {"prioridad_regional_visual": PRIORIDAD_ORDEN_MAPA},
        }

    fig = px.choropleth_mapbox(
        df,
        geojson=data,
        locations="zona_id",
        featureidkey="properties.zona_id",
        color=color_by,
        hover_name="nombre",
        hover_data=regional_hover_data(color_by),
        custom_data=["zona_id"],
        center=center,
        zoom=zoom,
        opacity=0.62,
        height=700,
        mapbox_style="carto-positron",
        **color_kwargs,
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend_title_text=legend_title,
    )
    if selected_id is not None:
        selected_features = [
            feature
            for feature in data.get("features", [])
            if int(feature.get("properties", {}).get("zona_id")) == int(selected_id)
        ]
        if selected_features:
            fig.add_trace(
                go.Choroplethmapbox(
                    geojson={"type": "FeatureCollection", "features": selected_features},
                    locations=[int(selected_id)],
                    z=[1],
                    featureidkey="properties.zona_id",
                    colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                    marker_line_color="#111827",
                    marker_line_width=4,
                    marker_opacity=0,
                    showscale=False,
                    hoverinfo="skip",
                    name="UM seleccionada",
                )
            )
    selection = st.plotly_chart(
        fig,
        width="stretch",
        key="regional_map",
        on_select="rerun",
        selection_mode="points",
    )
    return selected_parcela_id(selection)


def format_metric(value: Any, suffix: str = "", decimals: int = 1) -> str:
    if pd.isna(value):
        return "-"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer() and decimals == 0):
        return f"{int(value):,}{suffix}".replace(",", ".")
    return f"{float(value):,.{decimals}f}{suffix}".replace(",", ".")


def regional_summary_sentence(row: pd.Series) -> str:
    prioridad = row.get("prioridad_regional_visual_label", row.get("prioridad_regional", "-"))
    score = format_metric(row.get("prioridad_score_prom_pond"))
    alta_critica = format_metric(row.get("pct_alta_critica"), "%")
    delta = row.get("delta_10d_prom_pond")
    tendencia = "estable"
    if pd.notna(delta):
        if delta > 5:
            tendencia = "con aumento proyectado relevante"
        elif delta > 1:
            tendencia = "con aumento proyectado moderado"
        elif delta < -1:
            tendencia = "con baja proyectada"
    return (
        f"Prioridad regional {str(prioridad).lower()} con score {score}. "
        f"{alta_critica} de las parcelas evaluadas están en alta/crítica; tendencia {tendencia}."
    )


def render_regional_detail(row: pd.Series) -> None:
    st.subheader(str(row.get("nombre", "UM")))
    st.caption(f"Cuenca: {row.get('cuenca', '-')}")
    st.info(regional_summary_sentence(row))

    cols = st.columns(4)
    cols[0].metric("Ranking UM", format_metric(row.get("ranking_um"), decimals=0))
    cols[1].metric("Score regional", format_metric(row.get("prioridad_score_prom_pond")))
    cols[2].metric("Riesgo actual", format_metric(row.get("riesgo_actual_prom_pond")))
    cols[3].metric("Riesgo 10 días", format_metric(row.get("riesgo_10d_prom_pond")))

    cols = st.columns(4)
    cols[0].metric("Parcelas", format_metric(row.get("parcelas_total"), decimals=0))
    cols[1].metric("Rankeadas", format_metric(row.get("parcelas_rankeadas"), decimals=0))
    cols[2].metric("Alta/crítica", format_metric(row.get("pct_alta_critica"), "%"))
    cols[3].metric("Superficie cultivada", format_metric(row.get("area_cultivada_ha"), " ha"))

    fecha = row.get("fecha_actual")
    if pd.notna(fecha):
        st.caption(
            f"Fecha del ranking: {fecha}. Los valores son agregados ponderados de "
            "las parcelas evaluadas dentro de la UM."
        )

    st.markdown("**Composición**")
    st.markdown(f"- Vid: {format_metric(row.get('vid_parcelas'), decimals=0)} parcelas.")
    st.markdown(f"- Olivo: {format_metric(row.get('olivo_parcelas'), decimals=0)} parcelas.")
    st.markdown(
        f"- Cobertura de ranking: {format_metric(row.get('pct_parcelas_rankeadas'), '%')}."
    )


def render_regional_side_panel(df: pd.DataFrame) -> None:
    st.subheader("Detalle de UM")
    selected_id = st.session_state.get("selected_um_id")
    if selected_id is None:
        st.info("Seleccioná una UM en el mapa para ver el detalle.")
        return
    row = df[df["zona_id"] == int(selected_id)]
    if row.empty:
        st.info("La UM seleccionada no está visible con los filtros actuales.")
        return
    render_regional_detail(row.iloc[0])


def parcelas_de_um_df(um_id: int) -> tuple[dict[str, Any], pd.DataFrame]:
    data = load_regional_um_parcelas_geojson(int(um_id))
    df = features_to_frame(data)
    if not df.empty:
        df = add_dynamic_priority(df, "Umbrales fijos")
    if df.empty:
        return data, pd.DataFrame()
    return data, df


def render_um_parcelas_summary(parcelas: pd.DataFrame) -> None:
    if parcelas.empty:
        st.info("No hay parcelas asociadas a esta UM.")
        return

    ranked = parcelas[parcelas["ranking_global"].notna()].copy()
    priority_col = "prioridad_visual" if "prioridad_visual" in parcelas.columns else "prioridad"
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Parcelas UM", f"{len(parcelas):,}".replace(",", "."))
    col2.metric("Evaluadas", f"{len(ranked):,}".replace(",", "."))
    col3.metric("Alta/crítica", int(parcelas[priority_col].isin(["alta", "critica"]).sum()))
    col4.metric(
        "Score promedio",
        f"{ranked['prioridad_score'].mean():.1f}" if not ranked.empty else "-",
    )

    if {"cultivo", "prioridad_score", "riesgo_actual"}.issubset(ranked.columns):
        crop_summary = (
            ranked.groupby("cultivo", dropna=False)
            .agg(
                parcelas=("parcela_id", "count"),
                riesgo_promedio=("riesgo_actual", "mean"),
                score_promedio=("prioridad_score", "mean"),
                alta_critica=(
                    "prioridad_visual"
                    if "prioridad_visual" in ranked.columns
                    else "prioridad",
                    lambda s: int(s.isin(["alta", "critica"]).sum()),
                ),
            )
            .reset_index()
        )
        for col in ["riesgo_promedio", "score_promedio"]:
            crop_summary[col] = crop_summary[col].round(1)
        st.markdown("**Comparación por cultivo en la UM**")
        st.dataframe(
            crop_summary.rename(
                columns={
                    "cultivo": "Cultivo",
                    "parcelas": "Parcelas",
                    "riesgo_promedio": "Riesgo promedio",
                    "score_promedio": "Score promedio",
                    "alta_critica": "Alta/crítica",
                }
            ),
            hide_index=True,
            width="stretch",
        )


def render_um_parcelas_table(parcelas: pd.DataFrame) -> None:
    if parcelas.empty:
        return
    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "riesgo_operativo_10d",
        "delta_operativo_10d",
        "confianza_lectura",
    ]
    cols = [col for col in cols if col in parcelas.columns]
    table = parcelas.sort_values("ranking_global", na_position="last")[cols].copy()
    for col in [
        "prioridad_score",
        "riesgo_actual",
        "riesgo_operativo_10d",
        "delta_operativo_10d",
    ]:
        if col in table.columns:
            table[col] = table[col].round(2)
    labels = {
        "ranking_global": "Ranking",
        "parcela_id": "Parcela",
        "cultivo": "Cultivo",
        "prioridad": "Prioridad",
        "prioridad_score": "Score",
        "riesgo_actual": "Riesgo actual",
        "riesgo_operativo_10d": "Riesgo 10 días",
        "delta_operativo_10d": "Delta 10 días",
        "confianza_lectura": "Confianza",
    }
    st.dataframe(table.rename(columns=labels).head(100), hide_index=True, width="stretch")
    if len(table) > 100:
        st.caption(f"Mostrando 100 de {len(table):,} parcelas de la UM.".replace(",", "."))


def render_regional_focus_tab(df: pd.DataFrame) -> None:
    st.subheader("Foco regional")
    st.caption("UM que requieren mayor seguimiento por aumento proyectado, concentración alta/crítica o baja cobertura.")
    if df.empty:
        st.info("No hay UM visibles con los filtros actuales.")
        return

    ranked = df[df["ranking_um"].notna()].copy() if "ranking_um" in df.columns else df.copy()
    if ranked.empty:
        st.info("No hay UM rankeadas para resumir.")
        return

    cols = [
        "ranking_um",
        "nombre",
        "cuenca",
        "parcelas_total",
        "parcelas_rankeadas",
        "pct_parcelas_rankeadas",
        "prioridad_score_prom_pond",
        "riesgo_actual_prom_pond",
        "riesgo_10d_prom_pond",
        "delta_10d_prom_pond",
        "pct_alta_critica",
    ]
    cols = [col for col in cols if col in ranked.columns]
    labels = {
        "ranking_um": "Ranking",
        "nombre": "UM",
        "cuenca": "Cuenca",
        "parcelas_total": "Parcelas",
        "parcelas_rankeadas": "Rankeadas",
        "pct_parcelas_rankeadas": "% cobertura",
        "prioridad_score_prom_pond": "Score",
        "riesgo_actual_prom_pond": "Riesgo actual",
        "riesgo_10d_prom_pond": "Riesgo 10 días",
        "delta_10d_prom_pond": "Delta 10 días",
        "pct_alta_critica": "% alta/crítica",
    }

    left, right = st.columns(2)
    with left:
        st.markdown("**Mayor aumento proyectado**")
        if "delta_10d_prom_pond" in ranked.columns:
            table = ranked.sort_values("delta_10d_prom_pond", ascending=False)[cols].head(10)
            st.dataframe(table.rename(columns=labels), hide_index=True, width="stretch")
        else:
            st.info("No hay columna de delta regional.")

    with right:
        st.markdown("**Mayor concentración alta/crítica**")
        if "pct_alta_critica" in ranked.columns:
            table = ranked.sort_values("pct_alta_critica", ascending=False)[cols].head(10)
            st.dataframe(table.rename(columns=labels), hide_index=True, width="stretch")
        else:
            st.info("No hay columna de alta/crítica regional.")

    export_cols = [col for col in cols if col in ranked.columns]
    export_df = ranked.sort_values("ranking_um", na_position="last")[export_cols].copy()
    st.download_button(
        "Descargar foco regional CSV",
        data=dataframe_to_csv_bytes(export_df),
        file_name="foco_regional_um.csv",
        mime="text/csv",
    )

    if {"riesgo_actual_prom_pond", "delta_10d_prom_pond"}.issubset(ranked.columns):
        st.markdown("**Riesgo actual vs. aumento proyectado**")
        chart = ranked.copy()
        chart["nombre_mapa"] = chart.get("nombre", chart.get("um_id", "UM")).astype(str)
        hover_data = {"ranking_um": True} if "ranking_um" in chart.columns else {}
        if "pct_alta_critica" in chart.columns:
            hover_data["pct_alta_critica"] = ":.1f"
        if "pct_parcelas_rankeadas" in chart.columns:
            hover_data["pct_parcelas_rankeadas"] = ":.1f"
        fig = px.scatter(
            chart,
            x="riesgo_actual_prom_pond",
            y="delta_10d_prom_pond",
            size="parcelas_total" if "parcelas_total" in chart.columns else None,
            color="prioridad_regional_visual"
            if "prioridad_regional_visual" in chart.columns
            else None,
            color_discrete_map=PRIORIDAD_COLOR,
            hover_name="nombre_mapa",
            hover_data=hover_data,
        )
        fig.update_layout(
            height=360,
            xaxis_title="Riesgo actual promedio",
            yaxis_title="Aumento proyectado a 10 días",
            margin={"r": 10, "t": 10, "l": 10, "b": 10},
        )
        st.plotly_chart(fig, width="stretch")

    if {"vid_parcelas", "olivo_parcelas", "nombre"}.issubset(ranked.columns):
        st.markdown("**Composición vid/olivo por UM**")
        composition_cols = [
            "nombre",
            "vid_parcelas",
            "olivo_parcelas",
            "parcelas_total",
            "prioridad_score_prom_pond",
        ]
        composition_cols = [col for col in composition_cols if col in ranked.columns]
        composition = (
            ranked.sort_values("parcelas_total", ascending=False)
            .head(15)[composition_cols]
            .copy()
        )
        chart = composition.melt(
            id_vars=["nombre"],
            value_vars=[col for col in ["vid_parcelas", "olivo_parcelas"] if col in composition.columns],
            var_name="cultivo",
            value_name="parcelas",
        )
        chart["cultivo"] = chart["cultivo"].map(
            {"vid_parcelas": "Vid", "olivo_parcelas": "Olivo"}
        )
        fig = px.bar(
            chart,
            x="nombre",
            y="parcelas",
            color="cultivo",
            barmode="stack",
            color_discrete_map={"Vid": "#0c818a", "Olivo": "#7a9a01"},
        )
        fig.update_layout(
            height=340,
            margin={"r": 10, "t": 10, "l": 10, "b": 80},
            xaxis_title="UM",
            yaxis_title="Parcelas",
            legend_title_text="Cultivo",
        )
        st.plotly_chart(fig, width="stretch")

    if "pct_parcelas_rankeadas" in ranked.columns:
        low_coverage = ranked[ranked["pct_parcelas_rankeadas"] < 80].copy()
        if not low_coverage.empty:
            st.markdown("**UM con baja cobertura de ranking**")
            table = low_coverage.sort_values("pct_parcelas_rankeadas")[cols].head(10)
            st.dataframe(table.rename(columns=labels), hide_index=True, width="stretch")


def render_um_parcelas_tab() -> None:
    selected_id = st.session_state.get("selected_um_id")
    if selected_id is None:
        st.info("Seleccioná una UM en el mapa regional para ver sus parcelas.")
        return

    data, parcelas = parcelas_de_um_df(int(selected_id))
    render_um_parcelas_summary(parcelas)
    if parcelas.empty:
        return

    st.subheader("Parcelas dentro de la UM")
    st.download_button(
        "Descargar parcelas de la UM CSV",
        data=dataframe_to_csv_bytes(parcelas),
        file_name=f"parcelas_um_{int(selected_id)}.csv",
        mime="text/csv",
    )
    render_um_parcelas_table(parcelas)

    st.subheader("Mapa de parcelas de la UM")
    parcela_data = filtered_geojson(data, set(parcelas["parcela_id"].astype(int)))
    center, zoom = bbox_center_zoom(parcela_data)
    render_map(
        parcela_data,
        parcelas,
        color_by="prioridad_visual" if "prioridad_visual" in parcelas.columns else "prioridad",
        center=center,
        zoom=zoom,
        selected_id=st.session_state.get("selected_parcela_id"),
        admin_mode=True,
    )


def render_regional_table(df: pd.DataFrame) -> None:
    cols = [
        "ranking_um",
        "nombre",
        "cuenca",
        "prioridad_regional_visual_label",
        "parcelas_total",
        "parcelas_rankeadas",
        "pct_parcelas_rankeadas",
        "area_cultivada_ha",
        "vid_parcelas",
        "olivo_parcelas",
        "prioridad_score_prom_pond",
        "riesgo_actual_prom_pond",
        "riesgo_10d_prom_pond",
        "delta_10d_prom_pond",
        "pct_alta_critica",
        "pct_critica",
    ]
    cols = [col for col in cols if col in df.columns]
    labels = {
        "ranking_um": "Ranking UM",
        "nombre": "UM",
        "cuenca": "Cuenca",
        "prioridad_regional_visual_label": "Prioridad regional",
        "parcelas_total": "Parcelas",
        "parcelas_rankeadas": "Rankeadas",
        "pct_parcelas_rankeadas": "% rankeadas",
        "area_cultivada_ha": "Sup. cultivada (ha)",
        "vid_parcelas": "Vid",
        "olivo_parcelas": "Olivo",
        "prioridad_score_prom_pond": "Score regional",
        "riesgo_actual_prom_pond": "Riesgo actual",
        "riesgo_10d_prom_pond": "Riesgo 10 días",
        "delta_10d_prom_pond": "Delta 10 días",
        "pct_alta_critica": "% alta/crítica",
        "pct_critica": "% crítica",
    }
    table = df.sort_values("ranking_um")[cols].rename(columns=labels)
    st.download_button(
        "Descargar ranking UM CSV",
        data=dataframe_to_csv_bytes(table),
        file_name="ranking_um.csv",
        mime="text/csv",
    )
    st.dataframe(table, hide_index=True, width="stretch")


def render_regional_view() -> None:
    st.title("Seguimiento regional por UM")
    st.caption(
        "Unidades de manejo DGI con cultivos objetivo dentro de San Rafael. "
        "La vista compara zonas para seguimiento regional, no parcelas individuales."
    )

    loading = render_fullscreen_loader("Cargando zonificación regional...")
    with st.spinner("Cargando zonificación regional..."):
        data, df = load_zonificacion_regional()
    loading.empty()

    health = load_api_health()
    source = data.get("source", "desconocida")
    st.sidebar.caption(f"Fuente regional: {source}")
    if not health.get("available"):
        if local_fallback_enabled():
            st.sidebar.error("API no disponible. Se usa fallback local si existe.")
        else:
            st.sidebar.error("API/PostGIS no disponible. En producción no hay fallback local.")
    elif source in {"csv", "local"}:
        st.sidebar.warning("Datos regionales desde fallback local/CSV.")

    if df.empty:
        st.error("No se pudo cargar la zonificación regional desde la API/PostGIS.")
        return

    filtered, color_by = render_regional_sidebar(df)
    filtered_data = filter_zonificacion_geojson(data, set(filtered["zona_id"].astype(int)))

    render_regional_metrics(filtered)
    tab_mapa, tab_foco, tab_datos, tab_parcelas = st.tabs(
        ["Mapa regional", "Foco regional", "Ranking UM", "Parcelas de la UM"]
    )
    with tab_mapa:
        left, right = st.columns([2.2, 1.0])
        with left:
            clicked_id = render_regional_map(
                filtered_data,
                filtered,
                color_by,
                selected_id=st.session_state.get("selected_um_id"),
            )
            if clicked_id is not None:
                st.session_state["selected_um_id"] = clicked_id
        with right:
            render_regional_side_panel(filtered)
    with tab_datos:
        render_regional_table(filtered)
    with tab_foco:
        render_regional_focus_tab(filtered)
    with tab_parcelas:
        render_um_parcelas_tab()
