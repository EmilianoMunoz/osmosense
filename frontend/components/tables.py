from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.logic import display_delta, display_risk, review_priority
from frontend.table_config import column_labels, table_columns


def review_cases_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    required = {"parcela_id", "ranking_global"}
    if df.empty or not required <= set(df.columns):
        return pd.DataFrame()

    review = df[df.apply(review_priority, axis=1) < 99].copy()
    if review.empty:
        return pd.DataFrame()

    review["orden_revision"] = review.apply(review_priority, axis=1)
    sort_candidates = [
        ("orden_revision", True),
        ("severidad_ruido", False),
        ("ranking_global", True),
    ]
    sort_columns = [column for column, _ in sort_candidates if column in review.columns]
    sort_ascending = [
        ascending
        for column, ascending in sort_candidates
        if column in review.columns
    ]
    review = review.sort_values(
        sort_columns,
        ascending=sort_ascending,
        na_position="last",
    )

    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "prioridad_visual",
        "confianza_lectura",
        "outlier_especial",
        "score_suavizado",
        "accion_recomendada",
        "motivo_ruido",
        "severidad_ruido",
        "riesgo_actual",
        "riesgo_actual_suavizado",
        "prioridad_score_suavizado",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
        "historial_reciente_count",
        "min_valid_pixels_hidricos",
        "soporte_indices_count",
        "outlier_count_30d",
        "persistente_count_30d",
        "ruido_count_30d",
        "dias_desde_ultimo_outlier",
    ]
    cols = [col for col in cols if col in review.columns]
    numeric = [
        "severidad_ruido",
        "riesgo_actual",
        "riesgo_actual_suavizado",
        "prioridad_score_suavizado",
        "neighbor_riesgo_actual_median",
        "riesgo_actual_vs_neighbor_median",
        "riesgo_reciente_weighted_mean",
        "riesgo_vs_reciente_weighted_mean",
    ]
    for col in numeric:
        if col in review.columns:
            review[col] = review[col].round(2)

    return review[cols].head(80).rename(columns=column_labels(cols))


def render_review_cases(df: pd.DataFrame) -> int:
    review = review_cases_dataframe(df)
    if review.empty:
        st.success("No se detectaron casos técnicos para revisar con los filtros actuales.")
        return 0

    st.caption(
        f"{len(review):,} casos ordenados por prioridad de revisión.".replace(",", ".")
    )
    st.dataframe(review, hide_index=True, width="stretch")
    return len(review)


def render_cultivo_summary(df: pd.DataFrame) -> None:
    if df.empty:
        return

    ranked = df[df["ranking_global"].notna()].copy()
    if ranked.empty:
        return
    ranked["riesgo_10d_display"] = ranked.apply(
        lambda row: display_risk(row, 10, admin_mode=True),
        axis=1,
    )
    ranked["delta_10d_display"] = ranked.apply(
        lambda row: display_delta(row, 10, admin_mode=True),
        axis=1,
    )

    summary = (
        ranked.groupby("cultivo")
        .agg(
            parcelas=("parcela_id", "count"),
            criticas=("prioridad", lambda s: int((s == "critica").sum())),
            altas=("prioridad", lambda s: int((s == "alta").sum())),
            score_promedio=("prioridad_score", "mean"),
            riesgo_10d_promedio=("riesgo_10d_display", "mean"),
            delta_10d_promedio=("delta_10d_display", "mean"),
        )
        .reset_index()
    )
    for col in ["score_promedio", "riesgo_10d_promedio", "delta_10d_promedio"]:
        summary[col] = summary[col].round(2)

    st.dataframe(summary, hide_index=True, width="stretch")


def render_top_criticas(df: pd.DataFrame, limit: int = 15) -> None:
    if df.empty:
        return

    ranked = df[df["ranking_global"].notna()].copy()
    if ranked.empty:
        return

    top = ranked.sort_values("ranking_global").head(limit).copy()
    top["riesgo_10d_display"] = top.apply(
        lambda row: display_risk(row, 10, admin_mode=True),
        axis=1,
    )
    top["delta_10d_display"] = top.apply(
        lambda row: display_delta(row, 10, admin_mode=True),
        axis=1,
    )
    cols = [
        "ranking_global",
        "parcela_id",
        "cultivo",
        "prioridad",
        "prioridad_score",
        "riesgo_actual",
        "riesgo_10d_display",
        "delta_10d_display",
    ]
    for col in ["prioridad_score", "riesgo_actual", "riesgo_10d_display", "delta_10d_display"]:
        top[col] = top[col].round(2)
    labels = column_labels(cols)
    labels["riesgo_10d_display"] = "Proyección 10 días"
    labels["delta_10d_display"] = "Cambio proyectado 10 días"
    st.dataframe(top[cols].rename(columns=labels), hide_index=True, width="stretch")


def build_table_dataframe(
    filtered: pd.DataFrame,
    admin_mode: bool,
    *,
    technical: bool = False,
) -> pd.DataFrame:
    cols = table_columns(
        admin_mode,
        set(filtered.columns),
        technical=technical,
    )
    if not cols:
        return pd.DataFrame()
    sort_col = "ranking_global" if "ranking_global" in filtered.columns else cols[0]
    table_df = filtered.sort_values(sort_col, na_position="last")[cols].copy()

    if admin_mode:
        integer_columns = {"ranking_global", "ranking_por_cultivo", "parcela_id"}
        for column in integer_columns & set(table_df.columns):
            table_df[column] = pd.to_numeric(
                table_df[column],
                errors="coerce",
            ).astype("Int64")

        decimals = 2 if technical else 1
        numeric_columns = table_df.select_dtypes(include="number").columns
        rounded = [column for column in numeric_columns if column not in integer_columns]
        table_df[rounded] = table_df[rounded].round(decimals)

    return table_df.rename(columns=column_labels(cols))
