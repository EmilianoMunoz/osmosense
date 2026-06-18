from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.constants import PRIORIDAD_COLOR, PRIORIDAD_LABELS, PRIORIDAD_ORDEN_MAPA
from frontend.components.client_feedback import (
    priority_label,
    producer_comparison_lines,
    producer_comparison_summary,
    risk_change_indicator,
    risk_level_label,
    risk_level_color,
)
from frontend.logic import display_delta, display_risk


AVERAGE_REFERENCE_COLOR = "#12C2CF"


def parcela_label(row: pd.Series, admin_mode: bool = True) -> str:
    if not admin_mode:
        priority = row.get("prioridad_visual", row.get("prioridad", "-"))
        priority_label = PRIORIDAD_LABELS.get(str(priority), str(priority))
        return f"Parcela {int(row['parcela_id'])} · {row['cultivo']} · Prioridad {priority_label.lower()}"

    return (
        f"#{int(row['ranking_global'])} · {int(row['parcela_id'])} · "
        f"{row['cultivo']} · {row['prioridad']} · score {row['prioridad_score']:.1f}"
    )


def render_prediction_panel(
    df: pd.DataFrame,
    selected_id: int | None = None,
    admin_mode: bool = True,
) -> None:
    ranked = df[df["ranking_global"].notna()].sort_values("ranking_global").copy()
    parcela_options = ranked["parcela_id"].astype(int).tolist()
    if not parcela_options:
        st.info("No hay parcelas rankeadas con los filtros actuales.")
        return

    labels = {
        int(row["parcela_id"]): parcela_label(row, admin_mode=admin_mode)
        for _, row in ranked.iterrows()
    }
    default_index = 0
    if selected_id in parcela_options:
        default_index = parcela_options.index(selected_id)

    selected = st.selectbox(
        "Parcela",
        parcela_options,
        index=default_index,
        format_func=lambda parcela_id: labels.get(int(parcela_id), str(parcela_id)),
    )
    row = df[df["parcela_id"] == selected].iloc[0]

    if not admin_mode:
        render_client_context_panel(row, ranked)
        return

    render_admin_prediction_chart(row)
    render_admin_prediction_details(row)


def render_admin_prediction_chart(row: pd.Series) -> None:
    pred_df = pd.DataFrame(
        {
            "horizonte": ["Actual", "5 días", "10 días"],
            "riesgo": [
                row["riesgo_actual"],
                display_risk(row, 5, admin_mode=True),
                display_risk(row, 10, admin_mode=True),
            ],
        }
    )
    fig = px.line(pred_df, x="horizonte", y="riesgo", markers=True, range_y=[0, 100])
    fig.update_traces(line={"width": 3}, marker={"size": 9})
    fig.add_hline(y=35, line_dash="dot", line_color="#fee08b")
    fig.add_hline(y=47.5, line_dash="dot", line_color="#fc8d59")
    fig.add_hline(y=55, line_dash="dot", line_color="#d73027")
    fig.update_layout(height=260, margin={"r": 10, "t": 10, "l": 10, "b": 10})
    st.plotly_chart(fig, width="stretch")


def _render_client_status_metric(container, label: str, value: float | None) -> None:
    color = risk_level_color(value)
    container.markdown(
        f"""
        <div style="padding:0.2rem 0;">
            <div style="font-size:0.78rem; opacity:0.75;">{label}</div>
            <div style="font-size:1.55rem; font-weight:700; color:{color}; line-height:1.2;">
                {risk_level_label(value)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_client_change_metric(
    container,
    label: str,
    value: float | None,
    help_text: str = "puntos",
) -> None:
    indicator = risk_change_indicator(value)
    suffix = "" if indicator["text"] == "-" else f" {help_text}"
    container.markdown(
        f"""
        <div style="padding:0.2rem 0;">
            <div style="font-size:0.78rem; opacity:0.75;">{label}</div>
            <div style="font-size:1.55rem; font-weight:700; color:{indicator['color']}; line-height:1.2;">
                {indicator['text']}{suffix}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def render_client_context_panel(row: pd.Series, ranked: pd.DataFrame) -> None:
    summary = producer_comparison_summary(row, ranked)
    current = summary["current"]
    projected = summary["projected"]
    avg_current = summary["avg_current"]
    avg_projected = summary["avg_projected"]
    diff = summary["diff_current"]
    delta = summary["delta"]

    st.markdown("**Comparación dentro de mis parcelas**")
    cols = st.columns(3)
    _render_client_status_metric(cols[0], "Lectura", current)
    _render_client_change_metric(cols[1], "Vs promedio", diff)
    _render_client_change_metric(cols[2], "Cambio 10 días", delta)

    render_client_comparison_chart(
        title="Riesgo actual",
        value=current,
        average=avg_current,
    )
    render_client_comparison_chart(
        title="Escenario a 10 días",
        value=projected,
        average=avg_projected,
    )

    st.markdown(f"**Prioridad {priority_label(row).lower()}**")
    for line in producer_comparison_lines(summary):
        st.write(line)
    st.caption(
        "Este panel compara la parcela seleccionada contra tus parcelas visibles. "
        "El popup mantiene el detalle puntual de la parcela."
    )


def render_client_comparison_chart(
    title: str,
    value: float | None,
    average: float | None,
) -> None:
    if value is None:
        st.info(f"{title}: sin lectura suficiente.")
        return

    st.markdown(f"**{title}**")
    chart_df = pd.DataFrame(
        {
            "referencia": ["Esta parcela"],
            "riesgo": [float(value)],
        }
    )
    fig = px.bar(
        chart_df,
        x="riesgo",
        y="referencia",
        orientation="h",
        text=chart_df["riesgo"].round(1),
        range_x=[0, 100],
    )
    if average is not None:
        avg = max(0.0, min(100.0, float(average)))
        fig.add_vrect(
            x0=avg,
            x1=100,
            fillcolor="#d73027",
            opacity=0.07,
            line_width=0,
        )
        fig.add_vline(
            x=avg,
            line_dash="dash",
            line_color=AVERAGE_REFERENCE_COLOR,
            line_width=3,
            annotation_text="Promedio",
            annotation_position="top",
            annotation_font_color=AVERAGE_REFERENCE_COLOR,
        )
    fig.update_traces(
        marker_color=risk_level_color(value),
        textposition="inside",
        cliponaxis=False,
    )
    fig.update_layout(
        showlegend=False,
        height=120,
        margin={"r": 8, "t": 4, "l": 8, "b": 12},
        xaxis_title=None,
        yaxis_title=None,
        yaxis={"showticklabels": False},
    )
    st.plotly_chart(fig, width="stretch")
    if average is not None:
        st.caption(
            f"Promedio de tus parcelas: {average:.1f}. "
            "Si la barra queda a la derecha de la línea celeste, está por encima del promedio visible."
        )


def render_admin_prediction_details(row: pd.Series) -> None:
    details = {
        "parcela_id": int(row["parcela_id"]),
        "cultivo": row["cultivo"],
        "prioridad": row["prioridad"],
        "score": round(row["prioridad_score"], 2),
        "ranking_global": int(row["ranking_global"]),
        "ranking_cultivo": int(row["ranking_por_cultivo"]),
        "riesgo_actual": round(row["riesgo_actual"], 2),
        "riesgo_5d": round(display_risk(row, 5, admin_mode=True), 2),
        "riesgo_10d": round(display_risk(row, 10, admin_mode=True), 2),
        "delta_5d": round(display_delta(row, 5, admin_mode=True), 2),
        "delta_10d": round(display_delta(row, 10, admin_mode=True), 2),
    }
    detail_cols = [
        "fecha_lectura",
        "dias_desde_lectura",
        "confianza_lectura",
        "tendencia_reciente_5d",
        "pendiente_operativa_5d",
        "factor_estacional",
        "confianza_motivo",
        "outlier_espacial",
        "tipo_outlier_espacial",
        "persistencia_temporal",
        "diagnostico_outlier",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "historial_reciente_count",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "motivo_ruido",
        "severidad_ruido",
        "accion_recomendada",
        "outlier_count_30d",
        "persistente_count_30d",
        "ruido_count_30d",
        "ultima_fecha_outlier",
        "ultima_fecha_persistente",
        "ultima_fecha_ruido",
    ]
    for column in detail_cols:
        if column in row.index and pd.notna(row[column]):
            details[column] = row[column]

    st.dataframe(pd.DataFrame([details]), hide_index=True, width="stretch")


def render_distribution(filtered: pd.DataFrame) -> None:
    priority_col = "prioridad_visual"
    dist = (
        filtered[priority_col]
        .value_counts()
        .reindex(PRIORIDAD_ORDEN_MAPA)
        .dropna()
        .reset_index()
    )
    dist.columns = ["prioridad", "parcelas"]
    dist["prioridad_label"] = dist["prioridad"].map(PRIORIDAD_LABELS).fillna(dist["prioridad"])
    fig = px.bar(
        dist,
        x="prioridad_label",
        y="parcelas",
        color="prioridad",
        color_discrete_map=PRIORIDAD_COLOR,
        category_orders={"prioridad": PRIORIDAD_ORDEN_MAPA},
    )
    fig.update_layout(showlegend=False, height=260, margin={"r": 10, "t": 10, "l": 10, "b": 10})
    st.plotly_chart(fig, width="stretch")
