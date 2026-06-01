from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from frontend.constants import ACTION_LABELS, DIAGNOSTIC_LABELS, PRIORIDAD_LABELS
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

    if bool(row.get("outlier_espacial", False)):
        diff = row.get("riesgo_actual_vs_neighbor_median")
        neighbor = row.get("neighbor_riesgo_actual_median")
        if pd.notna(diff) and pd.notna(neighbor):
            items.append(
                f"Difiere de sus vecinos: mediana vecinal {neighbor:.1f}, diferencia {diff:.1f} puntos."
            )
        else:
            items.append("Fue detectada como outlier espacial frente a parcelas cercanas.")

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


def render_parcel_summary(row: pd.Series) -> None:
    st.subheader(f"Parcela {int(row['parcela_id'])}")
    st.write(risk_sentence(row))

    cols = st.columns(4)
    cols[0].metric("Riesgo actual", f"{row['riesgo_actual']:.1f}" if pd.notna(row.get("riesgo_actual")) else "-")
    riesgo_5d = display_risk(row, 5, admin_mode=True)
    riesgo_10d = display_risk(row, 10, admin_mode=True)
    cols[1].metric("Predicción 5 días", f"{riesgo_5d:.1f}" if pd.notna(riesgo_5d) else "-")
    cols[2].metric("Predicción 10 días", f"{riesgo_10d:.1f}" if pd.notna(riesgo_10d) else "-")
    cols[3].metric("Ranking", int(row["ranking_global"]) if pd.notna(row.get("ranking_global")) else "-")

    st.markdown("**Lectura**")
    for item in explanation_items(row):
        st.markdown(f"- {item}")


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
        st.write(f"Tendencia reciente estimada: {tendencia:.1f} puntos por imagen.")

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
