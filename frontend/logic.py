from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from frontend.constants import PRIORIDAD_LABELS, PRIORIDAD_ORDEN_MAPA


def add_dynamic_priority(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    df = df.copy()

    if mode == "Relativa por percentiles" and "prioridad_score" in df.columns:
        ranked = df["ranking_global"].notna() & df["prioridad_score"].notna()
        pct = df.loc[ranked, "prioridad_score"].rank(pct=True, ascending=False)

        df["prioridad_visual"] = "sin ranking"

        df.loc[ranked & (pct <= 0.10), "prioridad_visual"] = "critica"
        df.loc[ranked & (pct > 0.10) & (pct <= 0.30), "prioridad_visual"] = "alta"
        df.loc[ranked & (pct > 0.30) & (pct <= 0.60), "prioridad_visual"] = "media"
        df.loc[ranked & (pct > 0.60), "prioridad_visual"] = "baja"
    else:
        df["prioridad_visual"] = df["prioridad"]

    df["prioridad_visual_label"] = (
        df["prioridad_visual"].map(PRIORIDAD_LABELS).fillna(df["prioridad_visual"])
    )

    return df


def add_regional_dynamic_priority(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    df = df.copy()

    score_col = "prioridad_score_prom_pond"
    visual_col = "prioridad_regional_visual"

    if mode == "Relativa por percentiles" and score_col in df.columns:
        ranked = df[score_col].notna()
        pct = df.loc[ranked, score_col].rank(pct=True, ascending=False)

        df[visual_col] = "sin ranking"

        df.loc[ranked & (pct <= 0.10), visual_col] = "critica"
        df.loc[ranked & (pct > 0.10) & (pct <= 0.30), visual_col] = "alta"
        df.loc[ranked & (pct > 0.30) & (pct <= 0.60), visual_col] = "media"
        df.loc[ranked & (pct > 0.60), visual_col] = "baja"
    else:
        df[visual_col] = df["prioridad_regional"]

    df["prioridad_regional_visual_label"] = (
        df[visual_col].map(PRIORIDAD_LABELS).fillna(df[visual_col])
    )

    return df


def priority_options(df: pd.DataFrame) -> list[str]:
    priority_col = "prioridad_visual" if "prioridad_visual" in df.columns else "prioridad"
    present = set(df[priority_col].dropna().astype(str))
    return [p for p in PRIORIDAD_ORDEN_MAPA if p in present]


def format_label(value: Any, labels: dict[str, str]) -> str:
    if pd.isna(value):
        return "-"

    return labels.get(str(value), str(value))


def display_value(row: pd.Series, primary: str, fallback: str | None = None) -> Any:
    value = row.get(primary)

    if pd.notna(value):
        return value

    if fallback is None:
        return value

    return row.get(fallback)


def display_risk(row: pd.Series, horizon: int, admin_mode: bool = True) -> Any:
    raw_col = f"riesgo_pred_{horizon}d"
    op_col = f"riesgo_operativo_{horizon}d"
    return display_value(row, op_col, raw_col)


def display_delta(row: pd.Series, horizon: int, admin_mode: bool = True) -> Any:
    raw_col = f"delta_{horizon}d"
    op_col = f"delta_operativo_{horizon}d"
    return display_value(row, op_col, raw_col)


def review_priority(row: pd.Series) -> int:
    action = row.get("accion_recomendada")

    if action == "revisar_visual_antes_de_suavizar":
        return 1

    if action == "bajar_confianza_y_revisar_geometria":
        return 2

    if action == "bajar_confianza_no_suavizar_score":
        return 3

    if pd.notna(action):
        return 4

    if row.get("confianza_lectura") == "baja":
        return 5

    if bool(row.get("outlier_espacial", False)):
        return 6

    return 99


def cliente_changed(cliente_id: int | None) -> bool:
    prev = st.session_state.get("prev_cliente_id", -1)
    changed = prev != cliente_id

    st.session_state["prev_cliente_id"] = cliente_id

    if changed:
        st.session_state.pop("selected_parcela_id", None)

    return changed