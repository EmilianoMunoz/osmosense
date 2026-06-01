from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.constants import PRIORIDAD_COLOR, PRIORIDAD_LABELS, PRIORIDAD_ORDEN_MAPA
from frontend.logic import display_delta, display_risk
from frontend.table_config import column_labels


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

    pred_df = pd.DataFrame(
        {
            "horizonte": ["Actual", "5 días", "10 días"],
            "riesgo": [
                row["riesgo_actual"],
                display_risk(row, 5, admin_mode=admin_mode),
                display_risk(row, 10, admin_mode=admin_mode),
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

    if admin_mode:
        render_admin_prediction_details(row)
    else:
        render_client_prediction_details(row)


def render_client_prediction_details(row: pd.Series) -> None:
    details = {
        "parcela_id": int(row["parcela_id"]),
        "cultivo": row["cultivo"],
        "prioridad_visual": row.get("prioridad_visual", row.get("prioridad")),
        "riesgo_actual": round(row["riesgo_actual"], 2),
        "riesgo_operativo_5d": round(display_risk(row, 5, admin_mode=False), 2),
        "riesgo_operativo_10d": round(display_risk(row, 10, admin_mode=False), 2),
        "delta_operativo_10d": round(display_delta(row, 10, admin_mode=False), 2),
    }
    optional_cols = ["fecha_lectura", "dias_desde_lectura", "confianza_lectura", "tendencia_reciente_5d"]
    for column in optional_cols:
        if column in row.index and pd.notna(row[column]):
            details[column] = row[column]

    cols = list(details)
    st.dataframe(
        pd.DataFrame([details]).rename(columns=column_labels(cols)),
        hide_index=True,
        width="stretch",
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
