from __future__ import annotations

import pandas as pd
import streamlit as st


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
