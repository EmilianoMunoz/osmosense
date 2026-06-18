from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.components.client_feedback import (
    producer_dashboard_headline,
    risk_change_indicator,
    risk_level_label,
)
from frontend.constants import PRIORIDAD_LABELS


def client_top_projected_changes(df: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    ranked = df[df["ranking_global"].notna()].copy()
    required = {"delta_operativo_10d", "riesgo_actual", "riesgo_operativo_10d"}
    if ranked.empty or not required.issubset(ranked.columns):
        return pd.DataFrame()

    ranked["delta_operativo_10d"] = pd.to_numeric(
        ranked["delta_operativo_10d"],
        errors="coerce",
    )
    ranked = ranked[ranked["delta_operativo_10d"].notna()].copy()
    if ranked.empty:
        return pd.DataFrame()

    cols = [
        "parcela_id",
        "cultivo",
        "riesgo_actual",
        "riesgo_operativo_10d",
        "delta_operativo_10d",
    ]
    cols = [col for col in cols if col in ranked.columns]
    return (
        ranked.sort_values(
            ["delta_operativo_10d", "riesgo_actual"],
            ascending=[False, False],
        )[cols]
        .head(limit)
        .copy()
    )


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

    box(producer_dashboard_headline(summary))


def _priority_column(df: pd.DataFrame) -> str:
    return "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"


def _render_expected_change(container, value: float | None) -> None:
    indicator = risk_change_indicator(value)
    suffix = "" if indicator["text"] == "-" else " puntos"
    container.markdown(
        f"""
        <div style="padding:0.2rem 0;">
            <div style="font-size:0.78rem; opacity:0.75;">Evolución esperada</div>
            <div style="font-size:1.55rem; font-weight:700; color:{indicator['color']}; line-height:1.2;">
                {indicator['text']}{suffix}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_client_field_overview(df: pd.DataFrame) -> None:
    st.subheader("Resumen de situación")

    if df.empty:
        st.info("No hay parcelas visibles para resumir.")
        return

    priority_col = _priority_column(df)
    ranked = df[df["ranking_global"].notna()].copy()

    if ranked.empty:
        st.info("Todavía no hay parcelas evaluadas en esta vista.")
        return

    summary = client_status_summary(df)
    high_or_critical = int(summary["high_or_critical"])
    total = int(summary["total"])
    projected_change = float(summary["projected_change"])
    max_risk = ranked["riesgo_actual"].max() if "riesgo_actual" in ranked.columns else pd.NA

    col1, col2, col3 = st.columns(3)
    col1.metric("Parcelas en atención", f"{high_or_critical} de {total}")
    _render_expected_change(col2, projected_change)
    col3.metric("Señal más alta", f"{max_risk:.1f}" if pd.notna(max_risk) else "-")

    if high_or_critical:
        st.warning(
            "Hay parcelas con señal alta o crítica. Conviene mirarlas primero "
            "con conocimiento del campo y del manejo reciente."
        )
    else:
        st.success("No hay parcelas con señal alta o crítica bajo los filtros actuales.")

    st.caption(
        "El color resume el nivel de atención: verde bajo, amarillo medio, "
        "naranja alto y rojo crítico. En modo Mis parcelas, la comparación se hace "
        "solo con tus parcelas visibles. La proyección muestra un escenario de "
        "continuidad de la condición actual, no una recomendación de riego."
    )

    top_cols = [
        "parcela_id",
        "cultivo",
        priority_col,
        "riesgo_actual",
        "riesgo_operativo_10d",
        "delta_operativo_10d",
    ]
    top_cols = [col for col in top_cols if col in ranked.columns]
    top = ranked.sort_values("riesgo_actual", ascending=False)[top_cols].head(8).copy()
    if "riesgo_actual" in top.columns:
        top["lectura"] = top["riesgo_actual"].apply(risk_level_label)
    for col in ["riesgo_actual", "riesgo_operativo_10d", "delta_operativo_10d"]:
        if col in top.columns:
            top[col] = top[col].round(1)
    if priority_col in top.columns:
        top[priority_col] = top[priority_col].map(PRIORIDAD_LABELS).fillna(top[priority_col])
    labels = {
        "parcela_id": "Parcela",
        "cultivo": "Cultivo",
        priority_col: "Prioridad",
        "riesgo_actual": "Riesgo actual",
        "riesgo_operativo_10d": "Riesgo 10 días",
        "delta_operativo_10d": "Cambio 10 días",
        "lectura": "Lectura",
    }
    st.markdown("**Parcelas para revisar primero**")
    st.dataframe(top.rename(columns=labels), hide_index=True, width="stretch")

    change = client_top_projected_changes(ranked, limit=5)
    if not change.empty:
        for col in ["riesgo_actual", "riesgo_operativo_10d", "delta_operativo_10d"]:
            if col in change.columns:
                change[col] = change[col].round(1)
        st.markdown("**Mayor aumento esperado**")
        st.caption(
            "Estas parcelas no necesariamente son las de mayor riesgo actual; "
            "son las que más podrían cambiar en el escenario a 10 días."
        )
        st.dataframe(
            change.rename(
                columns={
                    "parcela_id": "Parcela",
                    "cultivo": "Cultivo",
                    "riesgo_actual": "Riesgo actual",
                    "riesgo_operativo_10d": "Riesgo 10 días",
                    "delta_operativo_10d": "Cambio esperado",
                }
            ),
            hide_index=True,
            width="stretch",
        )

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
