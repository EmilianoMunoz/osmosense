from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from frontend.constants import PRIORIDAD_COLOR, PRIORIDAD_LABELS, PRIORIDAD_ORDEN_MAPA


def client_status_summary(df: pd.DataFrame) -> dict[str, float | int | str]:
    priority_col = "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"
    ranked = df[df["ranking_global"].notna()].copy()
    total = int(len(ranked))
    high_or_critical = int(ranked[priority_col].isin(["alta", "critica"]).sum()) if total else 0
    critical = int((ranked[priority_col] == "critica").sum()) if total else 0
    pct_high = high_or_critical / total if total else 0.0
    current_mean = float(ranked["riesgo_actual"].mean()) if total and "riesgo_actual" in ranked.columns else 0.0

    if {"riesgo_actual", "riesgo_operativo_10d"}.issubset(ranked.columns):
        projected_change = float((ranked["riesgo_operativo_10d"] - ranked["riesgo_actual"]).mean())
        projected_mean = float(ranked["riesgo_operativo_10d"].mean())
    else:
        projected_change = 0.0
        projected_mean = current_mean

    if pct_high >= 0.5 or critical >= 3:
        status = "Atención alta"
    elif pct_high >= 0.25 or critical > 0:
        status = "Atención media"
    else:
        status = "Atención baja"

    return {
        "status": status,
        "total": total,
        "high_or_critical": high_or_critical,
        "critical": critical,
        "pct_high": pct_high,
        "current_mean": current_mean,
        "projected_mean": projected_mean,
        "projected_change": projected_change,
    }


def render_client_field_status(df: pd.DataFrame) -> None:
    summary = client_status_summary(df)
    status = str(summary["status"])

    if status == "Atención alta":
        box = st.warning
    elif status == "Atención media":
        box = st.info
    else:
        box = st.success

    box(
        " · ".join(
            [
                status,
                f"{summary['high_or_critical']} de {summary['total']} parcelas en prioridad alta o crítica",
                f"riesgo medio actual {summary['current_mean']:.1f}",
                f"proyección media 10 días {summary['projected_mean']:.1f}",
            ]
        )
    )


def _priority_column(df: pd.DataFrame) -> str:
    return "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"


def render_client_field_overview(df: pd.DataFrame) -> None:
    st.subheader("Lectura del campo")

    if df.empty:
        st.info("No hay parcelas visibles para resumir.")
        return

    priority_col = _priority_column(df)
    ranked = df[df["ranking_global"].notna()].copy()

    left, right = st.columns([1.05, 1.0])

    with left:
        if ranked.empty:
            st.info("Todavía no hay parcelas evaluadas en esta vista.")
        else:
            top_cols = [
                "parcela_id",
                "cultivo",
                priority_col,
                "riesgo_actual",
                "riesgo_operativo_10d",
                "delta_operativo_10d",
                "tendencia_reciente_5d",
            ]
            top_cols = [col for col in top_cols if col in ranked.columns]
            top = ranked.sort_values("riesgo_actual", ascending=False)[top_cols].head(8).copy()
            for col in ["riesgo_actual", "riesgo_operativo_10d", "delta_operativo_10d", "tendencia_reciente_5d"]:
                if col in top.columns:
                    top[col] = top[col].round(1)
            labels = {
                "parcela_id": "Parcela",
                "cultivo": "Cultivo",
                priority_col: "Prioridad",
                "riesgo_actual": "Riesgo actual",
                "riesgo_operativo_10d": "Riesgo 10 días",
                "delta_operativo_10d": "Cambio 10 días",
                "tendencia_reciente_5d": "Tendencia",
            }
            st.markdown("**Parcelas con mayor riesgo actual**")
            st.dataframe(top.rename(columns=labels), hide_index=True, width="stretch")

    with right:
        dist = (
            df[priority_col]
            .value_counts()
            .reindex(PRIORIDAD_ORDEN_MAPA)
            .dropna()
            .reset_index()
        )
        dist.columns = ["prioridad", "parcelas"]
        dist["prioridad_label"] = dist["prioridad"].map(PRIORIDAD_LABELS).fillna(dist["prioridad"])
        if dist.empty:
            st.info("No hay prioridades para graficar.")
        else:
            fig = px.bar(
                dist,
                x="prioridad_label",
                y="parcelas",
                color="prioridad",
                color_discrete_map=PRIORIDAD_COLOR,
                category_orders={"prioridad": PRIORIDAD_ORDEN_MAPA},
            )
            fig.update_layout(
                showlegend=False,
                height=280,
                margin={"r": 10, "t": 10, "l": 10, "b": 10},
                xaxis_title="Prioridad",
                yaxis_title="Parcelas",
            )
            st.markdown("**Distribución de prioridad**")
            st.plotly_chart(fig, width="stretch")

    if {"cultivo", "riesgo_actual"}.issubset(ranked.columns) and not ranked.empty:
        st.markdown("**Resumen por cultivo**")
        aggregations = {
            "parcelas": ("parcela_id", "count"),
            "riesgo_promedio": ("riesgo_actual", "mean"),
            "riesgo_maximo": ("riesgo_actual", "max"),
        }
        if "delta_operativo_10d" in ranked.columns:
            aggregations["cambio_10d"] = ("delta_operativo_10d", "mean")
        summary = (
            ranked.groupby("cultivo", dropna=False)
            .agg(**aggregations)
            .reset_index()
        )
        for col in ["riesgo_promedio", "riesgo_maximo", "cambio_10d"]:
            if col in summary.columns:
                summary[col] = summary[col].round(1)
        st.dataframe(
            summary.rename(
                columns={
                    "cultivo": "Cultivo",
                    "parcelas": "Parcelas",
                    "riesgo_promedio": "Riesgo promedio",
                    "riesgo_maximo": "Riesgo máximo",
                    "cambio_10d": "Cambio medio 10 días",
                }
            ),
            hide_index=True,
            width="stretch",
        )
