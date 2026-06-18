from __future__ import annotations

import pandas as pd
import streamlit as st


def _format_date(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return pd.to_datetime(value).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value)


def render_metrics(df: pd.DataFrame, admin_mode: bool = True) -> None:
    priority_col = "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"
    criticas = int((df[priority_col] == "critica").sum())
    alta = int((df[priority_col] == "alta").sum())
    riesgo_prom = float(df["prioridad_score"].mean()) if not df.empty else 0.0
    if "fecha_ranking" in df.columns and df["fecha_ranking"].notna().any():
        fecha = _format_date(df["fecha_ranking"].dropna().iloc[0])
    elif "fecha_actual" in df.columns and df["fecha_actual"].notna().any():
        fecha = _format_date(df["fecha_actual"].dropna().iloc[0])
    else:
        fecha = "-"
    rankeadas = int(df["ranking_global"].notna().sum()) if "ranking_global" in df.columns else 0
    sin_ranking = int((df[priority_col] == "sin ranking").sum())
    top_score = df["prioridad_score"].max() if "prioridad_score" in df.columns else pd.NA

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ranking operativo", fecha)
    col2.metric("Parcelas", f"{len(df):,}".replace(",", "."))
    col3.metric("Prioridad crítica", criticas)
    col4.metric("Score promedio", f"{riesgo_prom:.1f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Prioridad alta", alta)
    col6.metric("Vid", int((df["cultivo"] == "vid").sum()))
    col7.metric("Olivo", int((df["cultivo"] == "olivo").sum()))
    col8.metric("Evaluadas", f"{rankeadas:,}".replace(",", "."))

    outlier_col = "outlier_especial" if "outlier_especial" in df.columns else "outlier_espacial"
    outliers = int(df.get(outlier_col, pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    baja_confianza = int((df.get("confianza_lectura", pd.Series(dtype=str)) == "baja").sum())

    col9, col10, col11, col12 = st.columns(4)
    col9.metric("Sin ranking", f"{sin_ranking:,}".replace(",", "."))
    col10.metric("Score máximo", f"{top_score:.1f}" if pd.notna(top_score) else "-")
    if admin_mode:
        col11.metric("Outliers especiales", outliers)
        col12.metric("Conf. baja", baja_confianza)
    else:
        crit_alta = int((df[priority_col].isin(["critica", "alta"])).sum())
        col11.metric("Alta o crítica", crit_alta)
        col12.metric("Conf. baja", baja_confianza)


def render_client_metrics(df: pd.DataFrame) -> None:
    priority_col = "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"
    ranked = df[df["ranking_global"].notna()].copy()
    if "fecha_ranking" in df.columns and df["fecha_ranking"].notna().any():
        fecha = _format_date(df["fecha_ranking"].dropna().iloc[0])
    elif "fecha_actual" in df.columns and df["fecha_actual"].notna().any():
        fecha = _format_date(df["fecha_actual"].dropna().iloc[0])
    else:
        fecha = "-"
    latest_reading = (
        _format_date(df["fecha_lectura"].dropna().max())
        if "fecha_lectura" in df.columns and df["fecha_lectura"].notna().any()
        else "-"
    )
    riesgo_prom = float(ranked["riesgo_actual"].mean()) if not ranked.empty else 0.0
    riesgo_max = ranked["riesgo_actual"].max() if not ranked.empty else pd.NA

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Ranking operativo", fecha)
    col2.metric("Parcelas evaluadas", f"{len(ranked):,}".replace(",", "."))
    col3.metric("Atención crítica", int((df[priority_col] == "critica").sum()))
    col4.metric("Atención alta", int((df[priority_col] == "alta").sum()))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Señal promedio", f"{riesgo_prom:.1f}")
    col6.metric("Señal más alta", f"{riesgo_max:.1f}" if pd.notna(riesgo_max) else "-")
    col7.metric("Lectura satelital", latest_reading)
    col8.metric("Sin ranking", int((df[priority_col] == "sin ranking").sum()))
