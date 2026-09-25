from __future__ import annotations

from collections.abc import Collection

import pandas as pd
import streamlit as st

from frontend.data import load_clientes
from frontend.logic import (
    add_dynamic_priority,
    cliente_changed,
    priority_options,
    review_priority,
)

ROLE_VIEW_MODE = {
    "admin": "Admin",
    "regional": "Regional",
    "productor": "Productor",
}
ADMIN_COLOR_OPTIONS = {
    "Prioridad": "prioridad_visual",
    "Confianza de lectura": "confianza_lectura",
}
ADMIN_FILTER_KEYS = (
    "admin_review_mode",
    "admin_color_label",
    "admin_priority_mode",
    "admin_rank_preset",
    "admin_rank_range",
    "admin_cultivos",
    "admin_priority_scope",
    "admin_custom_priorities",
    "admin_confianza",
)


def view_mode_for_role(role: str | None) -> str | None:
    return ROLE_VIEW_MODE.get(str(role or "").strip().lower())


def select_view_mode() -> tuple[str, bool, bool]:
    view_mode = view_mode_for_role(st.session_state.get("auth_rol"))
    if view_mode is None:
        st.error("El rol de la sesión no tiene una vista habilitada.")
        st.stop()

    st.session_state["view_mode"] = view_mode
    return view_mode, view_mode == "Admin", view_mode == "Regional"


def select_cliente(admin_mode: bool) -> tuple[int | None, str | None]:
    if admin_mode or st.session_state.get("view_mode") == "Regional":
        return None, None

    auth_cliente_id = st.session_state.get("auth_cliente_id")
    if st.session_state.get("auth_rol") == "productor":
        cliente_changed(None)
        return None, st.session_state.get("auth_label", "Productor")

    clientes_data = load_clientes()
    clientes_items = clientes_data.get("items", [])
    if not clientes_items:
        st.info("No hay productores disponibles para mostrar.")
        st.stop()

    labels = {
        int(item["cliente_id"]): (
            f"{item['nombre']} · {item['tipo']} · "
            f"{int(item.get('parcelas_asignadas', 0))} parcelas"
        )
        for item in clientes_items
    }
    cliente_ids = list(labels)
    cliente_index = (
        cliente_ids.index(int(auth_cliente_id))
        if auth_cliente_id is not None and int(auth_cliente_id) in cliente_ids
        else 0
    )
    selected_cliente_id = st.sidebar.selectbox(
        "Productor",
        cliente_ids,
        index=cliente_index,
        format_func=lambda cid: labels[int(cid)],
    )

    cliente_changed(int(selected_cliente_id))
    selected_cliente_name = labels[int(selected_cliente_id)]
    st.caption(f"Vista productor · {selected_cliente_name}")
    return int(selected_cliente_id), selected_cliente_name


def select_priority_mode(admin_mode: bool) -> str:
    if admin_mode:
        return "Umbrales fijos"

    client_priority_mode = st.sidebar.radio(
        "Criterio de prioridad",
        ["General", "Mis parcelas"],
        index=1,
        help=(
            "General usa la prioridad del modelo. Mis parcelas compara solo "
            "las parcelas visibles del productor."
        ),
    )
    return (
        "Relativa por percentiles"
        if client_priority_mode == "Mis parcelas"
        else "Umbrales fijos"
    )


def _reset_admin_filters() -> None:
    for key in ADMIN_FILTER_KEYS:
        st.session_state.pop(key, None)


def _format_count(value: int) -> str:
    return f"{int(value):,}".replace(",", ".")


def filter_admin_dataframe(
    df: pd.DataFrame,
    *,
    cultivos: Collection[str],
    prioridades: Collection[str],
    confianza: Collection[str],
    rank_range: tuple[int, int],
    review_only: bool,
) -> pd.DataFrame:
    filtered = df[df["cultivo"].isin(cultivos)].copy()

    if not review_only:
        filtered = filtered[
            filtered["prioridad_visual"].isin(prioridades)
        ].copy()

    if "ranking_global" in filtered.columns:
        filtered = filtered[
            filtered["ranking_global"].between(rank_range[0], rank_range[1])
            | filtered["ranking_global"].isna()
        ].copy()

    if "confianza_lectura" in filtered.columns and confianza:
        filtered = filtered[
            filtered["confianza_lectura"].isin(confianza)
        ].copy()

    if review_only:
        filtered = filtered[
            filtered.apply(review_priority, axis=1) < 99
        ].copy()

    return filtered


def apply_admin_sidebar_filters(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str]:
    available_colors = {"Prioridad": "prioridad_visual"}
    if "confianza_lectura" in df.columns:
        available_colors["Confianza de lectura"] = "confianza_lectura"
    max_rank_value = df.get("ranking_global", pd.Series(dtype=float)).max()
    max_rank = (
        int(max_rank_value)
        if pd.notna(max_rank_value) and int(max_rank_value) >= 1
        else 1
    )
    rank_presets = ["Todos"]
    rank_presets.extend(
        f"Top {limit}" for limit in (100, 500, 1000) if limit < max_rank
    )
    rank_presets.append("Rango personalizado")

    with st.sidebar.form("admin_analysis_filters", border=False):
        st.markdown("### Análisis")
        review_mode = st.segmented_control(
            "Modo",
            ["Operación", "Revisión técnica"],
            default="Operación",
            key="admin_review_mode",
            width="stretch",
        )
        color_label = st.selectbox(
            "Color del mapa",
            list(available_colors),
            key="admin_color_label",
        )

        with st.expander("Filtros avanzados", expanded=False):
            priority_mode = st.radio(
                "Criterio de prioridad",
                ["Umbrales fijos", "Relativa por percentiles"],
                key="admin_priority_mode",
                help=(
                    "Los umbrales fijos conservan la escala operativa. "
                    "Los percentiles comparan la fecha visible."
                ),
            )
            rank_preset = st.selectbox(
                "Posición en el ranking",
                rank_presets,
                key="admin_rank_preset",
            )
            if rank_preset == "Rango personalizado":
                rank_range = st.slider(
                    "Rango",
                    1,
                    max_rank,
                    (1, max_rank),
                    key="admin_rank_range",
                )
            elif rank_preset.startswith("Top "):
                rank_range = (1, min(int(rank_preset.split()[1]), max_rank))
            else:
                rank_range = (1, max_rank)

        ranked_df = add_dynamic_priority(df, priority_mode)
        priority_values = priority_options(ranked_df)
        review_only = review_mode == "Revisión técnica"

        st.markdown("### Filtros")
        cultivos = st.multiselect(
            "Cultivo",
            options=sorted(ranked_df["cultivo"].dropna().unique()),
            default=sorted(ranked_df["cultivo"].dropna().unique()),
            key="admin_cultivos",
        )
        priority_scope = st.selectbox(
            "Alcance del mapa",
            ["Foco operativo", "Todas", "Personalizado"],
            key="admin_priority_scope",
            disabled=review_only,
        )
        if priority_scope == "Foco operativo":
            prioridades = [
                value
                for value in ("critica", "alta")
                if value in priority_values
            ]
        elif priority_scope == "Todas":
            prioridades = priority_values
        else:
            prioridades = st.multiselect(
                "Prioridad",
                options=priority_values,
                default=priority_values,
                key="admin_custom_priorities",
                format_func=lambda value: str(value).capitalize(),
                disabled=review_only,
            )

        if "confianza_lectura" in ranked_df.columns:
            confidence_values = sorted(
                ranked_df["confianza_lectura"].dropna().unique()
            )
            confianza = st.multiselect(
                "Confianza",
                options=confidence_values,
                default=confidence_values,
                key="admin_confianza",
            )
        else:
            confianza = []

        apply_col, reset_col = st.columns([1.2, 1])
        with apply_col:
            st.form_submit_button(
                "Aplicar",
                type="primary",
                icon=":material/filter_alt:",
                width="stretch",
            )
        with reset_col:
            st.form_submit_button(
                "Reiniciar",
                type="tertiary",
                icon=":material/restart_alt:",
                help="Restablecer filtros",
                width="stretch",
                on_click=_reset_admin_filters,
            )

    filtered = filter_admin_dataframe(
        ranked_df,
        cultivos=cultivos,
        prioridades=prioridades,
        confianza=confianza,
        rank_range=rank_range,
        review_only=review_only,
    )
    st.sidebar.caption(
        f"{_format_count(len(filtered))} de "
        f"{_format_count(len(ranked_df))} parcelas visibles"
    )
    color_by = available_colors[color_label]
    return ranked_df, filtered, color_by, priority_mode


def apply_sidebar_filters(
    df: pd.DataFrame,
    admin_mode: bool,
    priority_mode: str = "",
) -> tuple[pd.DataFrame, str]:
    color_options = [
        option
        for option in ["prioridad_visual", "confianza_lectura"]
        if option in df.columns
    ]
    if not admin_mode:
        color_options = [
            option for option in color_options if option == "prioridad_visual"
        ]

    color_by = st.sidebar.selectbox(
        "Color del mapa",
        color_options,
        index=0,
        format_func=lambda value: {
            "prioridad_visual": "Prioridad",
            "confianza_lectura": "Confianza de lectura",
        }.get(value, value),
    )
    st.sidebar.header("Filtros")
    cultivos = st.sidebar.multiselect(
        "Cultivo",
        options=sorted(df["cultivo"].dropna().unique()),
        default=sorted(df["cultivo"].dropna().unique()),
    )
    prioridades = st.sidebar.multiselect(
        "Prioridad",
        options=priority_options(df),
        default=priority_options(df),
        format_func=lambda value: str(value).capitalize(),
    )
    filtered = df[
        df["cultivo"].isin(cultivos)
        & df["prioridad_visual"].isin(prioridades)
    ].copy()
    return filtered, color_by


def sync_geojson_properties_from_df(data: dict, df: pd.DataFrame) -> dict:
    synced = data.copy()
    features = []

    if df.empty or "parcela_id" not in df.columns:
        synced["features"] = []
        return synced

    df_by_id = df.set_index(df["parcela_id"].astype(int))

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        parcela_id = props.get("parcela_id")

        if parcela_id is None:
            continue

        try:
            parcela_id_int = int(parcela_id)
        except (TypeError, ValueError):
            continue

        if parcela_id_int not in df_by_id.index:
            continue

        row = df_by_id.loc[parcela_id_int]

        updated_feature = feature.copy()
        updated_props = props.copy()

        for col in df.columns:
            value = row[col]

            if pd.isna(value):
                updated_props[col] = None
            else:
                updated_props[col] = value

        updated_feature["properties"] = updated_props
        features.append(updated_feature)

    synced["features"] = features
    return synced
