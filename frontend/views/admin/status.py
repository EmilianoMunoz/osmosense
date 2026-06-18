from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from frontend.data import load_api_health, load_pipeline_state
from frontend.config import local_fallback_enabled
from frontend.components.tables import render_cultivo_summary


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
        if local_fallback_enabled():
            st.sidebar.error("API no disponible. Se está usando fallback local si existe.")
        else:
            st.sidebar.error("API/PostGIS no disponible. En producción no hay fallback local.")
        return

    if source == "csv":
        st.sidebar.warning("API disponible, pero el ranking viene de CSV.")
    elif source == "local":
        st.sidebar.warning("Usando fallback local; revisar API/autenticación.")
    elif source == "api_unavailable":
        st.sidebar.error("No se pudo obtener datos desde la API/PostGIS.")


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
