from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from frontend.auth import is_authenticated, render_auth_sidebar, render_login
from frontend.data import (
    features_to_frame,
    filtered_geojson,
    load_api_health,
    load_clientes,
    load_geojson,
    load_pipeline_state,
)
from frontend.logic import add_dynamic_priority, cliente_changed, priority_options, review_priority
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
from frontend.views.admin_management import render_admin_management_area
from frontend.views.regional import render_regional_view


def select_view_mode() -> tuple[str, bool, bool]:
    st.sidebar.header("Acceso")
    current_view = st.session_state.get("view_mode", "Productor")
    rol = st.session_state.get("auth_rol")
    if rol == "admin":
        options = ["Admin", "Regional", "Productor"]
    elif rol == "regional":
        options = ["Regional"]
    elif rol == "productor":
        options = ["Productor"]
    else:
        options = ["Productor", "Regional", "Admin"]

    view_mode = st.sidebar.radio(
        "Vista",
        options,
        horizontal=True,
        index=options.index(current_view) if current_view in options else 0,
    )
    st.session_state["view_mode"] = view_mode
    return view_mode, view_mode == "Admin", view_mode == "Regional"


def select_cliente(admin_mode: bool) -> tuple[int | None, str | None]:
    if admin_mode or st.session_state.get("view_mode") == "Regional":
        return None, None

    auth_cliente_id = st.session_state.get("auth_cliente_id")
    if st.session_state.get("auth_rol") == "productor" and auth_cliente_id is not None:
        cliente_id = int(auth_cliente_id)
        st.sidebar.caption(f"Productor asignado: {cliente_id}")
        return cliente_id, f"Productor {cliente_id}"

    clientes_data = load_clientes()
    clientes_items = clientes_data.get("items", [])
    if not clientes_items:
        st.info(
            "No hay productores cargados. Crear backend/data/clientes/clientes.csv y "
            "backend/data/clientes/cliente_parcela.csv para habilitar la vista productor."
        )
        st.stop()

    labels = {
        int(item["cliente_id"]): (
            f"{item['nombre']} · {item['tipo']} · "
            f"{int(item.get('parcelas_asignadas', 0))} parcelas"
        )
        for item in clientes_items
    }

    cliente_ids = list(labels)
    cliente_index = (
        cliente_ids.index(int(auth_cliente_id))
        if auth_cliente_id is not None and int(auth_cliente_id) in cliente_ids
        else 0
    )

    selected_cliente_id = st.sidebar.selectbox(
        "Productor",
        cliente_ids,
        index=cliente_index,
        format_func=lambda cid: labels[int(cid)],
    )

    cliente_changed(int(selected_cliente_id))
    selected_cliente_name = labels[int(selected_cliente_id)]
    st.caption(f"Vista productor · {selected_cliente_name}")
    return int(selected_cliente_id), selected_cliente_name


def select_priority_mode(admin_mode: bool) -> str:
    if admin_mode:
        return st.sidebar.radio(
            "Categorización",
            ["Umbrales fijos", "Relativa por percentiles"],
            help=(
                "Umbrales fijos usa las categorías guardadas por el ranking. "
                "Relativa por percentiles reparte las parcelas evaluadas según su posición dentro de la fecha visible."
            ),
        )

    client_priority_mode = st.sidebar.radio(
        "Criterio de prioridad",
        ["General", "Dentro de mi campo"],
        index=1,
        help=(
            "General usa la prioridad del modelo. Dentro de mi campo compara "
            "solo las parcelas visibles del cliente."
        ),
    )

    return "Relativa por percentiles" if client_priority_mode == "Dentro de mi campo" else "Umbrales fijos"


def apply_sidebar_filters(
    df: pd.DataFrame,
    admin_mode: bool,
    priority_mode: str = "",
) -> tuple[pd.DataFrame, str]:
    color_options = [
        option
        for option in ["prioridad_visual", "confianza_lectura"]
        if option in df.columns
    ]

    if not admin_mode:
        color_options = [option for option in color_options if option == "prioridad_visual"]

    color_by = st.sidebar.selectbox("Color del mapa", color_options, index=0)

    st.sidebar.header("Filtros operativos" if admin_mode else "Filtros")

    cultivos = st.sidebar.multiselect(
        "Cultivo",
        options=sorted(df["cultivo"].dropna().unique()),
        default=sorted(df["cultivo"].dropna().unique()),
    )

    priority_values = priority_options(df)

    if admin_mode:
        show_all_priorities = st.sidebar.checkbox(
            "Mostrar todas las prioridades",
            value=False,
            help=(
                "Desactivado carga solo alta/crítica por defecto para acelerar "
                "el mapa operativo."
            ),
        )
        default_priorities = (
            priority_values
            if show_all_priorities
            else [p for p in ["critica", "alta"] if p in priority_values]
        )
        priority_scope = "all" if show_all_priorities else "focus"
    else:
        default_priorities = priority_values
        priority_scope = "all"

    priority_filter_key = (
        f"prioridad_filter_"
        f"{st.session_state.get('view_mode', 'desconocida')}_"
        f"{priority_mode}_"
        f"{priority_scope}"
    )

    prioridades = st.sidebar.multiselect(
        "Prioridad",
        options=priority_values,
        default=default_priorities,
        key=priority_filter_key,
    )

    if admin_mode and "confianza_lectura" in df.columns:
        confianza = st.sidebar.multiselect(
            "Confianza",
            options=sorted(df["confianza_lectura"].dropna().unique()),
            default=sorted(df["confianza_lectura"].dropna().unique()),
        )
    else:
        confianza = []

    max_rank_value = df["ranking_global"].max()

    if admin_mode and pd.notna(max_rank_value) and int(max_rank_value) >= 1:
        max_rank = int(max_rank_value)
        rank_range = st.sidebar.slider("Ranking global", 1, max_rank, (1, max_rank))
    else:
        rank_range = (1, 1)

    review_only = False

    if admin_mode:
        st.sidebar.header("Revisión técnica")
        review_only = st.sidebar.checkbox("Solo casos a revisar", value=False)

    filtered = df[df["cultivo"].isin(cultivos)].copy()

    if not review_only:
        filtered = filtered[filtered["prioridad_visual"].isin(prioridades)].copy()

    if admin_mode:
        filtered = filtered[
            filtered["ranking_global"].between(rank_range[0], rank_range[1])
            | filtered["ranking_global"].isna()
        ].copy()

    if "confianza_lectura" in filtered.columns and confianza:
        filtered = filtered[filtered["confianza_lectura"].isin(confianza)].copy()

    if review_only:
        filtered = filtered[filtered.apply(review_priority, axis=1) < 99].copy()

    return filtered, color_by

def sync_geojson_properties_from_df(data: dict, df: pd.DataFrame) -> dict:
    synced = data.copy()
    features = []

    if df.empty or "parcela_id" not in df.columns:
        synced["features"] = []
        return synced

    df_by_id = df.set_index(df["parcela_id"].astype(int))

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        parcela_id = props.get("parcela_id")

        if parcela_id is None:
            continue

        try:
            parcela_id_int = int(parcela_id)
        except (TypeError, ValueError):
            continue

        if parcela_id_int not in df_by_id.index:
            continue

        row = df_by_id.loc[parcela_id_int]

        updated_feature = feature.copy()
        updated_props = props.copy()

        for col in df.columns:
            value = row[col]

            if pd.isna(value):
                updated_props[col] = None
            else:
                updated_props[col] = value

        updated_feature["properties"] = updated_props
        features.append(updated_feature)

    synced["features"] = features
    return synced


def _format_state_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "sí" if value else "no"
    return str(value)


def _format_datetime_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def _human_pipeline_reason(reason: object) -> str:
    reasons = {
        "sin_fecha_nueva": "Sin imagen Sentinel nueva",
        "error": "Error de ejecución",
        None: "Sin observaciones",
        "": "Sin observaciones",
    }
    return reasons.get(reason, str(reason))


def _human_source(source: object) -> str:
    sources = {
        "postgis": "PostGIS",
        "csv": "CSV vía API",
        "local": "Fallback local",
        "api_unavailable": "API no disponible",
    }
    return sources.get(source, str(source or "desconocida"))


def _format_int(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{int(value):,}".replace(",", ".")


def _format_float(value: object, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{decimals}f}"


def render_runtime_notices(data: dict) -> None:
    health = load_api_health()
    source = data.get("source")

    if not health.get("available"):
        st.sidebar.error("API no disponible. Se está usando fallback local si existe.")
        return

    if source == "csv":
        st.sidebar.warning("API disponible, pero el ranking viene de CSV.")
    elif source == "local":
        st.sidebar.warning("Usando fallback local; revisar API/autenticación.")
    elif source == "api_unavailable":
        st.sidebar.error("No se pudo obtener datos desde la API.")


def render_pipeline_status() -> None:
    data = load_pipeline_state()
    state = data.get("state", {}) if isinstance(data, dict) else {}
    summary = data.get("ranking_summary", {}) if isinstance(data, dict) else {}

    st.subheader("Pipeline")

    if not data.get("exists"):
        if data.get("source") == "api_unavailable":
            st.error("No se pudo consultar el estado del pipeline porque la API no respondió.")
        else:
            st.info("Todavía no hay estado persistido del pipeline.")
        return

    skipped = bool(state.get("skipped", False))
    failed = bool(state.get("failed", False))
    if failed:
        status_label = "Error"
        status_message = "La última ejecución del pipeline terminó con error."
        st.error(status_message)
    elif skipped:
        status_label = "Sin actualización"
        status_message = "Sin imagen Sentinel nueva; no se recalculó ranking."
        st.info(status_message)
    else:
        status_label = "Actualizado"
        status_message = "La última ejecución generó o cargó ranking operativo."
        st.success(status_message)

    reason = state.get("reason")
    latest_date = (
        state.get("fecha_dataset")
        or state.get("fecha_rankeada")
        or summary.get("fecha_ranking")
    )

    cols = st.columns(4)
    cols[0].metric("Estado", status_label)
    cols[1].metric("Última ejecución", _format_datetime_value(state.get("last_run_utc")))
    cols[2].metric("Última imagen válida", _format_state_value(latest_date))
    cols[3].metric("Modo", _format_state_value(state.get("mode")))

    details = pd.DataFrame(
        [
            {
                "Resultado": _human_pipeline_reason(reason),
                "PostGIS cargado": _format_state_value(state.get("postgis_loaded")),
                "Fecha antes": _format_state_value(state.get("fecha_dataset_antes")),
                "Fecha después": _format_state_value(state.get("fecha_dataset_despues")),
                "Filas ranking": _format_int(summary.get("rows", state.get("parcelas", 0))),
                "Evaluadas": _format_int(summary.get("evaluadas")),
                "Sin ranking": _format_int(summary.get("sin_ranking")),
            }
        ]
    )
    st.dataframe(details, hide_index=True, width="stretch")

    if summary.get("exists"):
        st.caption(
            "Ranking latest: "
            f"{int(summary.get('rows', 0)):,} filas · ".replace(",", ".")
            + f"{int(summary.get('evaluadas', 0)):,} evaluadas · ".replace(",", ".")
            + f"{int(summary.get('sin_ranking', 0)):,} sin ranking".replace(",", ".")
        )

    if state.get("log_path"):
        st.caption(f"Log: {state['log_path']}")


def render_admin_overview(df: pd.DataFrame) -> None:
    priority_col = "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"
    ranked = df[df["ranking_global"].notna()].copy()
    total = len(df)
    evaluated = len(ranked)
    critical = int((df[priority_col] == "critica").sum())
    high = int((df[priority_col] == "alta").sum())
    high_critical = critical + high
    coverage = evaluated / total * 100 if total else 0
    score_mean = df["prioridad_score"].mean() if "prioridad_score" in df.columns else pd.NA
    fecha = "-"
    if "fecha_actual" in df.columns and df["fecha_actual"].notna().any():
        fecha = str(df["fecha_actual"].dropna().iloc[0])

    cols = st.columns(4)
    cols[0].metric("Fecha imagen", fecha)
    cols[1].metric("Parcelas evaluadas", f"{_format_int(evaluated)} / {_format_int(total)}")
    cols[2].metric("Alta/crítica", _format_int(high_critical))
    cols[3].metric("Score promedio", _format_float(score_mean))

    detail_cols = st.columns(4)
    detail_cols[0].metric("Cobertura", f"{coverage:.1f}%")
    detail_cols[1].metric("Críticas", _format_int(critical))
    detail_cols[2].metric("Altas", _format_int(high))
    detail_cols[3].metric(
        "Sin ranking",
        _format_int(int((df[priority_col] == "sin ranking").sum())),
    )


def render_admin_quality_summary(df: pd.DataFrame) -> None:
    outlier_col = "outlier_especial" if "outlier_especial" in df.columns else "outlier_espacial"
    outliers = int(df.get(outlier_col, pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    baja_confianza = int((df.get("confianza_lectura", pd.Series(dtype=str)) == "baja").sum())
    score_smoothed = int(df.get("score_suavizado", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())

    cols = st.columns(3)
    cols[0].metric("Casos a revisar", _format_int(outliers))
    cols[1].metric("Confianza baja", _format_int(baja_confianza))
    cols[2].metric("Scores suavizados", _format_int(score_smoothed))


def render_admin_status_tab(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    st.subheader("Estado general")
    render_admin_overview(df)

    st.divider()
    render_pipeline_status()

    st.divider()
    st.subheader("Calidad de lectura")
    render_admin_quality_summary(df)

    st.divider()
    st.subheader("Vista activa filtrada")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Parcelas visibles", f"{len(filtered):,}".replace(",", "."))

    col2.metric(
        "Evaluadas visibles",
        f"{int(filtered['ranking_global'].notna().sum()):,}".replace(",", "."),
    )

    col3.metric(
        "Alta/crítica visibles",
        int(filtered["prioridad_visual"].isin(["alta", "critica"]).sum()),
    )

    col4.metric(
        "Sin ranking visibles",
        int((filtered["prioridad_visual"] == "sin ranking").sum()),
    )

    left, right = st.columns([1.1, 1.0])

    with left:
        st.subheader("Distribución por prioridad")
        priority_summary = (
            df.groupby("prioridad_visual", dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
            .rename(columns={"prioridad_visual": "Prioridad", "parcelas": "Parcelas"})
        )
        st.dataframe(priority_summary, hide_index=True, width="stretch")

    with right:
        st.subheader("Resumen por cultivo")
        render_cultivo_summary(df)


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
        elif selected_cliente_id is not None:
            map_center, map_zoom = bbox_center_zoom(filtered_data)
        else:
            map_center, map_zoom = None, 8.3

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
            relative_animation_categories=priority_mode == "Relativa por percentiles",
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
        st.subheader("Parcela")
        selected_id = st.session_state.get("selected_parcela_id")
        render_prediction_panel(filtered, selected_id=selected_id, admin_mode=admin_mode)

        st.subheader("Distribución")
        render_distribution(filtered)

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
    st.subheader("Tabla de ranking" if admin_mode else "Mis parcelas")

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
    tab_estado, tab_mapa, tab_revision, tab_cobertura, tab_datos = st.tabs(
        ["Estado", "Mapa operativo", "Revisión técnica", "Cobertura", "Datos"]
    )

    with tab_estado:
        render_admin_status_tab(df, filtered)

    with tab_mapa:
        render_map_tab(
            data=data,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            admin_mode=True,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )

    with tab_revision:
        render_review_tab(filtered)

    with tab_cobertura:
        render_coverage_tab(df)

    with tab_datos:
        render_data_tab(filtered, admin_mode=True)


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
            st.title("Ranking hídrico de parcelas")
            st.caption("San Rafael, Mendoza · Vid y olivo")
        with header_right:
            st.caption("Área admin")
            admin_area = st.radio(
                "Área admin",
                ["Análisis", "Gestión"],
                horizontal=True,
                label_visibility="collapsed",
                key="admin_area",
            )
            if st.button("Actualizar datos", width="stretch"):
                refresh_dashboard_data()
    else:
        st.title("Ranking hídrico de parcelas")
        st.caption("San Rafael, Mendoza · Vid y olivo")

    if admin_mode and admin_area == "Gestión":
        render_admin_management_area()
        return

    selected_cliente_id, _ = select_cliente(admin_mode)

    loading_message = (
        "Cargando ranking operativo..."
        if admin_mode
        else "Cargando parcelas del productor..."
    )
    loading = render_fullscreen_loader(loading_message)
    with st.spinner(loading_message):
        data = load_geojson(selected_cliente_id)
        df = features_to_frame(data)
    loading.empty()

    if df.empty:
        st.error("No se pudo cargar el ranking.")
        return

    st.sidebar.header("Vista")
    st.sidebar.caption(f"Fuente: {_human_source(data.get('source'))}")
    render_runtime_notices(data)

    priority_mode = select_priority_mode(admin_mode)

    priority_context = f"{view_mode}:{selected_cliente_id}:{priority_mode}"
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
    tab_resumen, tab_mapa, tab_datos = st.tabs(["Resumen", "Campo", "Parcelas"])
    with tab_resumen:
        render_client_field_overview(filtered)

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

    with tab_datos:
        render_data_tab(filtered, admin_mode)
