from __future__ import annotations

from datetime import datetime

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
    render_review_cases,
)
from frontend.views.admin import render_admin_management_area
from frontend.views.admin.status import (
    render_admin_status_tab,
    render_runtime_notices,
)
from frontend.views.dashboard_filters import (
    apply_admin_sidebar_filters,
    apply_sidebar_filters,
    select_cliente,
    select_priority_mode,
    select_view_mode,
    sync_geojson_properties_from_df,
)
from frontend.views.regional import render_regional_view


ADMIN_ANALYSIS_SECTIONS = [
    "Estado",
    "Mapa",
    "Ranking",
    "Calidad",
    "Revisión",
]
LEGACY_ADMIN_SECTIONS = {
    "Mapa operativo": "Mapa",
    "Datos": "Ranking",
    "Cobertura": "Calidad",
    "Revisión técnica": "Revisión",
}


def _format_dashboard_date(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


def render_operational_ranking_notice(df: pd.DataFrame) -> None:
    if df.empty or "fecha_ranking" not in df.columns or not df["fecha_ranking"].notna().any():
        return

    fecha = _format_dashboard_date(df["fecha_ranking"].dropna().iloc[0])
    st.caption(
        "Ranking operativo usado: "
        f"{fecha}. La vista utiliza el último ranking con cobertura suficiente."
    )


def render_coverage_tab(df: pd.DataFrame) -> None:
    st.subheader("Calidad de datos")

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
    total = len(df)
    evaluated = int(df["ranking_global"].notna().sum())
    missing_count = total - evaluated
    coverage_percent = evaluated / total * 100 if total else 0.0
    confidence_high = 0
    confidence_total = 0
    if "confianza_lectura" in df.columns:
        confidence_total = int(df["confianza_lectura"].notna().sum())
        confidence_high = int((df["confianza_lectura"] == "alta").sum())
    confidence_percent = (
        confidence_high / confidence_total * 100 if confidence_total else None
    )

    metrics = st.columns(4)
    metrics[0].metric("Cobertura", f"{coverage_percent:.1f}%")
    metrics[1].metric("Evaluadas", f"{evaluated:,}".replace(",", "."))
    metrics[2].metric("Sin ranking", f"{missing_count:,}".replace(",", "."))
    metrics[3].metric(
        "Confianza alta",
        f"{confidence_percent:.1f}%" if confidence_percent is not None else "-",
    )

    all_readings_high_confidence = confidence_total == total and confidence_high == total
    if missing_count == 0 and all_readings_high_confidence:
        st.success("Cobertura completa y confianza alta en todas las lecturas.")
    elif missing_count == 0:
        st.success("Todas las parcelas cuentan con evaluación operativa.")
    else:
        st.warning(
            f"Hay {missing_count:,} parcelas pendientes de ranking.".replace(",", ".")
        )

    coverage_display = coverage.rename(
        columns={
            "cultivo": "Cultivo",
            "parcelas": "Parcelas",
            "evaluadas": "Evaluadas",
            "sin_ranking": "Sin ranking",
            "cobertura_%": "Cobertura (%)",
        }
    )

    st.dataframe(coverage_display, hide_index=True, width="stretch")

    if "confianza_lectura" in df.columns:
        confidence = (
            df.groupby(["cultivo", "confianza_lectura"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        confidence_values = set(df["confianza_lectura"].dropna().astype(str))
        if confidence_values != {"alta"}:
            confidence_display = confidence.rename(
                columns={
                    "cultivo": "Cultivo",
                    "confianza_lectura": "Confianza",
                    "parcelas": "Parcelas",
                }
            )
            with st.expander("Detalle de confianza"):
                st.dataframe(
                    confidence_display,
                    hide_index=True,
                    width="stretch",
                )

    if "estado_evaluacion" in df.columns:
        estado = (
            df.groupby(["cultivo", "estado_evaluacion"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        evaluation_values = set(df["estado_evaluacion"].dropna().astype(str))
        if evaluation_values != {"Evaluada"}:
            estado_display = estado.rename(
                columns={
                    "cultivo": "Cultivo",
                    "estado_evaluacion": "Estado",
                    "parcelas": "Parcelas",
                }
            )
            with st.expander("Detalle de evaluación"):
                st.dataframe(
                    estado_display,
                    hide_index=True,
                    width="stretch",
                )

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
    st.subheader("Revisión técnica")
    render_review_cases(filtered)


def render_data_tab(filtered: pd.DataFrame, admin_mode: bool) -> None:
    technical = False
    if admin_mode:
        title_col, mode_col = st.columns([0.72, 0.28], vertical_alignment="bottom")
        with title_col:
            st.subheader("Ranking de parcelas")
            st.caption(
                "Vista operativa ordenada por prioridad. Activá el detalle "
                "técnico para auditar variables del modelo."
            )
        with mode_col:
            technical = st.toggle(
                "Mostrar columnas técnicas",
                value=False,
                key="admin_show_technical_columns",
            )
    else:
        st.subheader("Listado de parcelas")

    table_df = build_table_dataframe(
        filtered,
        admin_mode,
        technical=technical,
    )

    if table_df.empty:
        st.info("No hay columnas disponibles para mostrar.")
        return

    st.caption(f"{len(table_df):,} parcelas visibles.".replace(",", "."))
    st.dataframe(table_df, hide_index=True, width="stretch", height=540)


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
    current_section = st.session_state.get("admin_analysis_section")
    if current_section in LEGACY_ADMIN_SECTIONS:
        st.session_state["admin_analysis_section"] = LEGACY_ADMIN_SECTIONS[
            current_section
        ]

    ranking_date = "-"
    if "fecha_ranking" in df.columns and df["fecha_ranking"].notna().any():
        ranking_date = _format_dashboard_date(df["fecha_ranking"].dropna().iloc[0])

    st.caption(
        f"Ranking operativo: {ranking_date} · "
        f"{len(df):,} parcelas totales · ".replace(",", ".")
        + f"{len(filtered):,} visibles con los filtros actuales".replace(",", ".")
    )
    active_section = st.segmented_control(
        "Sección de análisis",
        ADMIN_ANALYSIS_SECTIONS,
        default="Estado",
        label_visibility="collapsed",
        key="admin_analysis_section",
        width="stretch",
    )
    active_section = active_section or "Estado"

    if active_section == "Estado":
        render_admin_status_tab(df, filtered)
        return

    if active_section == "Mapa":
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

    if active_section == "Ranking":
        render_data_tab(filtered, admin_mode=True)
        return

    if active_section == "Calidad":
        render_coverage_tab(df)
        return

    if active_section == "Revisión":
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
        header_title, header_mode, header_refresh = st.columns(
            [0.56, 0.30, 0.14],
            vertical_alignment="bottom",
        )
        with header_title:
            st.title("Panel admin")
            st.caption(
                "Ranking hídrico, calidad de datos y gestión operativa · San Rafael"
            )
        with header_mode:
            admin_area = st.segmented_control(
                "Área",
                ["Análisis", "Gestión"],
                default="Análisis",
                label_visibility="collapsed",
                key="admin_area",
                width="stretch",
            )
            admin_area = admin_area or "Análisis"
        with header_refresh:
            if st.button(
                "Recargar",
                icon=":material/refresh:",
                type="tertiary",
                help="Volver a consultar los datos sin ejecutar el pipeline",
                width="stretch",
            ):
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

    render_runtime_notices(data)

    if admin_mode:
        df, filtered, color_by, priority_mode = apply_admin_sidebar_filters(df)
    else:
        priority_mode = select_priority_mode(admin_mode)
        df = add_dynamic_priority(df, priority_mode)
        filtered, color_by = apply_sidebar_filters(
            df=df,
            admin_mode=admin_mode,
            priority_mode=priority_mode,
        )

    producer_context = "me" if producer_self_mode else selected_cliente_id
    priority_context = f"{view_mode}:{producer_context}:{priority_mode}"
    if st.session_state.get("prev_priority_context") != priority_context:
        st.session_state.pop("selected_parcela_id", None)
    st.session_state["prev_priority_context"] = priority_context

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

    render_operational_ranking_notice(filtered)
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
