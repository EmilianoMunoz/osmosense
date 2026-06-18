from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.auth import is_authenticated, render_auth_sidebar, render_login
from frontend.data import (
    features_to_frame,
    filtered_geojson,
    load_geojson,
    load_my_geojson,
)
from frontend.logic import add_dynamic_priority
from frontend.map import bbox_center_zoom, render_map
from frontend.components.branding import apply_brand_theme, render_fullscreen_loader
from frontend.components.charts import render_distribution, render_prediction_panel
from frontend.components.client_overview import render_client_field_overview, render_client_field_status
from frontend.components.metrics import render_client_metrics
from frontend.components.parcel_detail import render_client_parcel_dialog, render_parcel_dialog
from frontend.components.tables import (
    build_table_dataframe,
    render_cultivo_summary,
    render_review_cases,
    render_top_criticas,
)
from frontend.views.admin import render_admin_management_area
from frontend.views.admin.status import (
    _human_source,
    render_admin_status_tab,
    render_runtime_notices,
)
from frontend.views.dashboard_filters import (
    apply_sidebar_filters,
    select_cliente,
    select_priority_mode,
    select_view_mode,
    sync_geojson_properties_from_df,
)
from frontend.views.regional import render_regional_view


ADMIN_ANALYSIS_SECTIONS = [
    "Estado",
    "Mapa operativo",
    "Datos",
    "Cobertura",
    "Revisión técnica",
]


def render_coverage_tab(df: pd.DataFrame) -> None:
    st.subheader("Cobertura")

    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    coverage = (
        df.groupby("cultivo", dropna=False)
        .agg(
            parcelas=("parcela_id", "count"),
            evaluadas=("ranking_global", lambda s: int(s.notna().sum())),
            sin_ranking=("ranking_global", lambda s: int(s.isna().sum())),
        )
        .reset_index()
    )

    coverage["cobertura_%"] = (coverage["evaluadas"] / coverage["parcelas"] * 100).round(2)

    st.dataframe(coverage, hide_index=True, width="stretch")

    if "confianza_lectura" in df.columns:
        st.subheader("Confianza de lectura")
        confidence = (
            df.groupby(["cultivo", "confianza_lectura"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        st.dataframe(confidence, hide_index=True, width="stretch")

    if "estado_evaluacion" in df.columns:
        st.subheader("Estado de evaluación")
        estado = (
            df.groupby(["cultivo", "estado_evaluacion"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        st.dataframe(estado, hide_index=True, width="stretch")

    missing = df[df["ranking_global"].isna()].copy()

    if not missing.empty:
        st.subheader("Parcelas sin ranking")
        cols = [
            "parcela_id",
            "cultivo",
            "estado_evaluacion",
            "estado_cobertura",
            "area_m2",
            "confianza_lectura",
        ]
        cols = [col for col in cols if col in missing.columns]

        st.dataframe(
            missing.sort_values(["cultivo", "parcela_id"])[cols].head(200),
            hide_index=True,
            width="stretch",
        )

        if len(missing) > 200:
            st.caption(f"Mostrando 200 de {len(missing):,} parcelas sin ranking.".replace(",", "."))


def render_map_tab(
    data: dict,
    filtered: pd.DataFrame,
    filtered_data: dict,
    color_by: str,
    admin_mode: bool,
    selected_cliente_id: int | None,
    priority_mode: str = "",
) -> None:
    left, right = st.columns([2.2, 1.0])

    with left:
        if admin_mode:
            map_center, map_zoom = bbox_center_zoom(filtered_data)
            map_zoom = min(map_zoom + 0.45, 10.0)
        else:
            map_center, map_zoom = bbox_center_zoom(filtered_data)

        selected_id = st.session_state.get("selected_parcela_id")

        clicked_id = render_map(
            filtered_data,
            filtered,
            color_by=color_by,
            center=map_center,
            zoom=map_zoom,
            selected_id=selected_id,
            admin_mode=admin_mode,
            risk_animation=not admin_mode,
            relative_animation_categories=False,
        )

        if clicked_id is not None:
            st.session_state["selected_parcela_id"] = clicked_id
            row = filtered[filtered["parcela_id"] == clicked_id]

            if not row.empty and hasattr(st, "dialog"):
                if admin_mode:
                    render_parcel_dialog(row.iloc[0].to_dict())
                else:
                    render_client_parcel_dialog(row.iloc[0].to_dict())

    with right:
        st.subheader("Detalle de parcela" if not admin_mode else "Parcela")
        selected_id = st.session_state.get("selected_parcela_id")
        render_prediction_panel(filtered, selected_id=selected_id, admin_mode=admin_mode)

        if admin_mode:
            st.subheader("Distribución")
            render_distribution(filtered)
        else:
            st.caption(
                "Seleccioná una parcela en el mapa o en el selector para ver una "
                "lectura simple del estado actual y su evolución esperada."
            )

def render_review_tab(filtered: pd.DataFrame) -> None:
    st.subheader("Casos a revisar")
    render_review_cases(filtered)

    lower_left, lower_right = st.columns([1.15, 1.0])

    with lower_left:
        st.subheader("Top prioridad")
        render_top_criticas(filtered, limit=15)

    with lower_right:
        st.subheader("Resumen por cultivo")
        render_cultivo_summary(filtered)


def render_data_tab(filtered: pd.DataFrame, admin_mode: bool) -> None:
    st.subheader("Ranking y auditoría" if admin_mode else "Listado de parcelas")

    table_df = build_table_dataframe(filtered, admin_mode)

    if table_df.empty:
        st.info("No hay columnas disponibles para mostrar.")
        return

    st.dataframe(table_df, hide_index=True, width="stretch")


def refresh_dashboard_data() -> None:
    st.cache_data.clear()
    for key in [
        "selected_parcela_id",
        "selected_disponible_id",
        "prev_priority_context",
    ]:
        st.session_state.pop(key, None)
    st.rerun()


def render_admin_analysis_area(
    data: dict,
    df: pd.DataFrame,
    filtered: pd.DataFrame,
    filtered_data: dict,
    color_by: str,
    selected_cliente_id: int | None,
    priority_mode: str,
) -> None:
    active_section = st.radio(
        "Sección de análisis",
        ADMIN_ANALYSIS_SECTIONS,
        horizontal=True,
        label_visibility="collapsed",
        key="admin_analysis_section",
    )

    if active_section == "Estado":
        render_admin_status_tab(df, filtered)
        return

    if active_section == "Mapa operativo":
        render_map_tab(
            data=data,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            admin_mode=True,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )
        return

    if active_section == "Datos":
        render_data_tab(filtered, admin_mode=True)
        return

    if active_section == "Cobertura":
        render_coverage_tab(df)
        return

    if active_section == "Revisión técnica":
        render_review_tab(filtered)
        return


def render_dashboard() -> None:
    st.set_page_config(
        page_title="Ranking hídrico San Rafael",
        page_icon=None,
        layout="wide",
    )
    apply_brand_theme()

    if not is_authenticated():
        render_login()
        st.stop()

    render_auth_sidebar()

    view_mode, admin_mode, regional_mode = select_view_mode()

    if regional_mode:
        render_regional_view()
        return

    admin_area = "Análisis"
    if admin_mode:
        header_left, header_right = st.columns([0.68, 0.32])
        with header_left:
            st.title("Panel admin")
            st.caption("Ranking hídrico, calidad de datos y gestión operativa · San Rafael")
        with header_right:
            st.caption("Sección")
            admin_area = st.radio(
                "Sección",
                ["Análisis", "Gestión"],
                horizontal=True,
                label_visibility="collapsed",
                key="admin_area",
            )
            if st.button("Actualizar datos", width="stretch"):
                refresh_dashboard_data()
    else:
        st.title("Mis parcelas")
        st.caption("Lectura de atención hídrica y evolución esperada · San Rafael")

    if admin_mode and admin_area == "Gestión":
        render_admin_management_area()
        return

    producer_self_mode = st.session_state.get("auth_rol") == "productor" and not admin_mode
    selected_cliente_id, _ = select_cliente(admin_mode)
    simplify_meters = 2.0 if admin_mode and selected_cliente_id is None else None

    loading_message = (
        "Cargando ranking operativo..."
        if admin_mode
        else "Cargando parcelas del productor..."
    )
    loading = render_fullscreen_loader(loading_message)
    with st.spinner(loading_message):
        if producer_self_mode:
            data = load_my_geojson()
        else:
            data = load_geojson(selected_cliente_id, simplify_meters=simplify_meters)
        df = features_to_frame(data)
    loading.empty()

    if df.empty:
        st.error("No se pudo cargar el ranking.")
        return

    st.sidebar.header("Vista")
    st.sidebar.caption(f"Fuente: {_human_source(data.get('source'))}")
    render_runtime_notices(data)

    priority_mode = select_priority_mode(admin_mode)

    producer_context = "me" if producer_self_mode else selected_cliente_id
    priority_context = f"{view_mode}:{producer_context}:{priority_mode}"
    if st.session_state.get("prev_priority_context") != priority_context:
        st.session_state.pop("selected_parcela_id", None)
    st.session_state["prev_priority_context"] = priority_context

    df = add_dynamic_priority(df, priority_mode)

    filtered, color_by = apply_sidebar_filters(
        df=df,
        admin_mode=admin_mode,
        priority_mode=priority_mode,
    )

    filtered_data = sync_geojson_properties_from_df(data, filtered)
    if admin_mode:
        render_admin_analysis_area(
            data=data,
            df=df,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )
        return

    render_client_metrics(filtered)
    render_client_field_status(filtered)
    tab_mapa, tab_resumen, tab_datos = st.tabs(["Mapa", "Resumen", "Parcelas"])
    with tab_mapa:
        render_map_tab(
            data=data,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            admin_mode=admin_mode,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )

    with tab_resumen:
        render_client_field_overview(filtered)

    with tab_datos:
        render_data_tab(filtered, admin_mode)
