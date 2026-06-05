from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.constants import ACTION_LABELS, DIAGNOSTIC_LABELS, PRIORIDAD_LABELS
from frontend.data import load_parcela_history
from frontend.logic import display_delta, display_risk, format_label


def risk_sentence(row: pd.Series) -> str:
    priority = format_label(row.get("prioridad_visual", row.get("prioridad")), PRIORIDAD_LABELS)
    confidence = row.get("confianza_lectura", "-")
    score = row.get("prioridad_score")
    score_text = f"{score:.1f}" if pd.notna(score) else "-"
    return f"Prioridad {priority.lower()} con score {score_text}. Confianza de lectura: {confidence}."


def client_risk_sentence(row: pd.Series) -> str:
    priority = format_label(row.get("prioridad_visual", row.get("prioridad")), PRIORIDAD_LABELS)
    riesgo = row.get("riesgo_actual")
    pred_5d = display_risk(row, 5, admin_mode=False)
    pred_10d = display_risk(row, 10, admin_mode=False)
    if pd.isna(riesgo):
        estado = row.get("estado_evaluacion")
        if pd.notna(estado):
            return f"{estado}. La parcela entrará al análisis cuando exista una lectura satelital válida."
        return "La parcela no tiene lectura suficiente para calcular estrés hídrico en esta fecha."

    text = f"Prioridad {priority.lower()}. Riesgo actual estimado: {riesgo:.1f}."
    if pd.notna(pred_5d) and pd.notna(pred_10d):
        text += f" Proyección operativa: {pred_5d:.1f} a 5 días y {pred_10d:.1f} a 10 días."
    return text


def explanation_items(row: pd.Series) -> list[str]:
    items = []
    fecha_lectura = row.get("fecha_lectura")
    dias_desde_lectura = row.get("dias_desde_lectura")
    if pd.notna(fecha_lectura):
        if pd.notna(dias_desde_lectura):
            items.append(
                f"Lectura satelital usada: {fecha_lectura} ({int(dias_desde_lectura)} días respecto de la fecha objetivo)."
            )
        else:
            items.append(f"Lectura satelital usada: {fecha_lectura}.")

    outlier_value = row.get("outlier_especial", row.get("outlier_espacial", False))
    outlier_visible = pd.notna(outlier_value) and bool(outlier_value)
    if outlier_visible:
        diff = row.get("riesgo_actual_vs_neighbor_median")
        neighbor = row.get("neighbor_riesgo_actual_median")
        if pd.notna(diff) and pd.notna(neighbor):
            items.append(
                f"Difiere de sus vecinos: mediana vecinal {neighbor:.1f}, diferencia {diff:.1f} puntos."
            )
        else:
            items.append("Fue detectada como outlier espacial frente a parcelas cercanas.")

    score_suavizado = row.get("score_suavizado", False)
    if pd.notna(score_suavizado) and bool(score_suavizado):
        risk_smoothed = row.get("riesgo_actual_suavizado")
        score_smoothed = row.get("prioridad_score_suavizado")
        parts = []
        if pd.notna(risk_smoothed):
            parts.append(f"riesgo operativo suavizado {risk_smoothed:.1f}")
        if pd.notna(score_smoothed):
            parts.append(f"score operativo suavizado {score_smoothed:.1f}")
        if parts:
            items.append("Conflicto suavizado: " + ", ".join(parts) + ".")

    diagnostico = row.get("diagnostico_outlier")
    if pd.notna(diagnostico):
        items.append(f"Diagnóstico: {format_label(diagnostico, DIAGNOSTIC_LABELS)}.")

    action = row.get("accion_recomendada")
    if pd.notna(action):
        items.append(f"Acción sugerida: {format_label(action, ACTION_LABELS)}.")

    recent = row.get("riesgo_reciente_weighted_mean")
    if pd.notna(recent):
        items.append(f"Promedio reciente ponderado: {recent:.1f}; las fechas más cercanas pesan más.")

    outlier_count = row.get("outlier_count_30d")
    if pd.notna(outlier_count):
        items.append(f"Apariciones como outlier en 30 días: {int(outlier_count)}.")

    if not items:
        items.append("No hay alertas de calidad relevantes para esta parcela.")
    return items


def render_parcela_history(row: pd.Series, admin_mode: bool = False) -> None:
    parcela_id = row.get("parcela_id")
    if pd.isna(parcela_id):
        return

    history = load_parcela_history(int(parcela_id))
    if history.empty:
        st.info("No hay historial satelital disponible para esta parcela.")
        return

    index_cols = [
        col
        for col in ["ndvi_mean", "ndmi_mean", "msi_mean", "nbr_mean"]
        if col in history.columns and history[col].notna().any()
    ]
    if not index_cols:
        st.info("El historial existe, pero no tiene índices suficientes para graficar.")
        return

    labels = {
        "ndvi_mean": "NDVI",
        "ndmi_mean": "NDMI",
        "msi_mean": "MSI",
        "nbr_mean": "NBR",
    }
    chart_df = history.melt(
        id_vars=["fecha"],
        value_vars=index_cols,
        var_name="indice",
        value_name="valor",
    )
    chart_df["indice"] = chart_df["indice"].map(labels).fillna(chart_df["indice"])

    fig = px.line(
        chart_df,
        x="fecha",
        y="valor",
        color="indice",
        markers=True,
    )
    fig.update_layout(
        height=260,
        margin={"r": 10, "t": 10, "l": 10, "b": 10},
        legend_title_text="Índice",
    )
    st.plotly_chart(fig, width="stretch")

    if len(history) >= 2 and "ndvi_mean" in history.columns:
        first = history["ndvi_mean"].dropna().iloc[0] if history["ndvi_mean"].notna().any() else None
        last = history["ndvi_mean"].dropna().iloc[-1] if history["ndvi_mean"].notna().any() else None
        if first is not None and last is not None:
            delta = float(last - first)
            st.caption(f"Variación NDVI en la ventana visible: {delta:+.3f}.")

    if admin_mode:
        cols = ["fecha"] + index_cols
        table = history[cols].copy()
        for col in index_cols:
            table[col] = table[col].round(3)
        st.dataframe(table.rename(columns=labels), hide_index=True, width="stretch")


def render_parcel_summary(row: pd.Series) -> None:
    st.subheader(f"Parcela {int(row['parcela_id'])}")
    st.write(risk_sentence(row))

    cols = st.columns(4)
    cols[0].metric("Riesgo actual", f"{row['riesgo_actual']:.1f}" if pd.notna(row.get("riesgo_actual")) else "-")
    riesgo_5d = display_risk(row, 5, admin_mode=True)
    riesgo_10d = display_risk(row, 10, admin_mode=True)
    cols[1].metric("Proyección 5 días", f"{riesgo_5d:.1f}" if pd.notna(riesgo_5d) else "-")
    cols[2].metric("Proyección 10 días", f"{riesgo_10d:.1f}" if pd.notna(riesgo_10d) else "-")
    cols[3].metric("Ranking", int(row["ranking_global"]) if pd.notna(row.get("ranking_global")) else "-")

    st.markdown("**Lectura**")
    for item in explanation_items(row):
        st.markdown(f"- {item}")

    st.markdown("**Historial satelital reciente**")
    render_parcela_history(row, admin_mode=True)


def render_client_parcel_summary(row: pd.Series) -> None:
    st.subheader(f"Parcela {int(row['parcela_id'])}")
    st.write(client_risk_sentence(row))

    cols = st.columns(3)
    riesgo_5d = display_risk(row, 5, admin_mode=False)
    riesgo_10d = display_risk(row, 10, admin_mode=False)
    cols[0].metric("Riesgo actual", f"{row['riesgo_actual']:.1f}" if pd.notna(row.get("riesgo_actual")) else "-")
    cols[1].metric("Proyección 5 días", f"{riesgo_5d:.1f}" if pd.notna(riesgo_5d) else "-")
    cols[2].metric("Proyección 10 días", f"{riesgo_10d:.1f}" if pd.notna(riesgo_10d) else "-")

    fecha_lectura = row.get("fecha_lectura")
    dias = row.get("dias_desde_lectura")
    if pd.notna(fecha_lectura):
        if pd.notna(dias):
            st.info(f"Lectura satelital usada: {fecha_lectura} ({int(dias)} días respecto de la fecha objetivo).")
        else:
            st.info(f"Lectura satelital usada: {fecha_lectura}.")

    tendencia = row.get("tendencia_reciente_5d")
    if pd.notna(tendencia):
        tendencia = float(tendencia)
        if tendencia > 2:
            st.write("El riesgo viene aumentando en las últimas imágenes.")
        elif tendencia < -2:
            st.write("El riesgo viene bajando en las últimas imágenes.")
        else:
            st.write("El riesgo reciente se mantiene estable.")

    delta_10d = display_delta(row, 10, admin_mode=False)
    if pd.notna(delta_10d):
        if delta_10d > 5:
            st.write("La serie proyectada indica aumento del estrés hídrico en los próximos 10 días.")
        elif delta_10d < -5:
            st.write("La serie proyectada indica una posible reducción del estrés hídrico en los próximos 10 días.")
        else:
            st.write("La serie proyectada se mantiene relativamente estable en los próximos 10 días.")


if hasattr(st, "dialog"):
    @st.dialog("Detalle de parcela")
    def render_parcel_dialog(row_dict: dict[str, Any]) -> None:
        render_parcel_summary(pd.Series(row_dict))


if hasattr(st, "dialog"):
    @st.dialog("Detalle de parcela")
    def render_client_parcel_dialog(row_dict: dict[str, Any]) -> None:
        render_client_parcel_summary(pd.Series(row_dict))
