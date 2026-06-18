from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.data import load_clientes
from frontend.logic import cliente_changed, priority_options, review_priority


def select_view_mode() -> tuple[str, bool, bool]:
    st.sidebar.header("Acceso")
    current_view = st.session_state.get("view_mode", "Productor")
    rol = st.session_state.get("auth_rol")
    if rol == "admin":
        options = ["Admin", "Regional", "Productor"]
    elif rol == "regional":
        options = ["Regional"]
    elif rol == "productor":
        options = ["Productor"]
    else:
        options = ["Productor", "Regional", "Admin"]

    view_mode = st.sidebar.radio(
        "Vista",
        options,
        horizontal=True,
        index=options.index(current_view) if current_view in options else 0,
    )
    st.session_state["view_mode"] = view_mode
    return view_mode, view_mode == "Admin", view_mode == "Regional"


def select_cliente(admin_mode: bool) -> tuple[int | None, str | None]:
    if admin_mode or st.session_state.get("view_mode") == "Regional":
        return None, None

    auth_cliente_id = st.session_state.get("auth_cliente_id")
    if st.session_state.get("auth_rol") == "productor":
        cliente_changed(None)
        st.sidebar.caption("Productor autenticado")
        return None, st.session_state.get("auth_label", "Productor")

    clientes_data = load_clientes()
    clientes_items = clientes_data.get("items", [])
    if not clientes_items:
        st.info(
            "No hay productores cargados. Crear backend/data/clientes/clientes.csv y "
            "backend/data/clientes/cliente_parcela.csv para habilitar la vista productor."
        )
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
        return st.sidebar.radio(
            "Categorización",
            ["Umbrales fijos", "Relativa por percentiles"],
            help=(
                "Umbrales fijos usa las categorías guardadas por el ranking. "
                "Relativa por percentiles reparte las parcelas evaluadas según su posición dentro de la fecha visible."
            ),
        )

    client_priority_mode = st.sidebar.radio(
        "Criterio de prioridad",
        ["General", "Mis parcelas"],
        index=1,
        help=(
            "General usa la prioridad del modelo. Mis parcelas compara solo "
            "las parcelas visibles del productor."
        ),
    )

    return "Relativa por percentiles" if client_priority_mode == "Mis parcelas" else "Umbrales fijos"


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
        color_options = [option for option in color_options if option == "prioridad_visual"]

    color_by = st.sidebar.selectbox("Color del mapa", color_options, index=0)

    st.sidebar.header("Filtros operativos" if admin_mode else "Filtros")

    cultivos = st.sidebar.multiselect(
        "Cultivo",
        options=sorted(df["cultivo"].dropna().unique()),
        default=sorted(df["cultivo"].dropna().unique()),
    )

    priority_values = priority_options(df)

    if admin_mode:
        show_all_priorities = st.sidebar.checkbox(
            "Mostrar todas las prioridades",
            value=False,
            help=(
                "Desactivado carga solo alta/crítica por defecto para acelerar "
                "el mapa operativo."
            ),
        )
        default_priorities = (
            priority_values
            if show_all_priorities
            else [p for p in ["critica", "alta"] if p in priority_values]
        )
        priority_scope = "all" if show_all_priorities else "focus"
    else:
        default_priorities = priority_values
        priority_scope = "all"

    priority_filter_key = (
        f"prioridad_filter_"
        f"{st.session_state.get('view_mode', 'desconocida')}_"
        f"{priority_mode}_"
        f"{priority_scope}"
    )

    prioridades = st.sidebar.multiselect(
        "Prioridad",
        options=priority_values,
        default=default_priorities,
        key=priority_filter_key,
    )

    if admin_mode and "confianza_lectura" in df.columns:
        confianza = st.sidebar.multiselect(
            "Confianza",
            options=sorted(df["confianza_lectura"].dropna().unique()),
            default=sorted(df["confianza_lectura"].dropna().unique()),
        )
    else:
        confianza = []

    max_rank_value = df["ranking_global"].max()

    if admin_mode and pd.notna(max_rank_value) and int(max_rank_value) >= 1:
        max_rank = int(max_rank_value)
        rank_range = st.sidebar.slider("Ranking global", 1, max_rank, (1, max_rank))
    else:
        rank_range = (1, 1)

    review_only = False

    if admin_mode:
        st.sidebar.header("Revisión técnica")
        review_only = st.sidebar.checkbox("Solo casos a revisar", value=False)

    filtered = df[df["cultivo"].isin(cultivos)].copy()

    if not review_only:
        filtered = filtered[filtered["prioridad_visual"].isin(prioridades)].copy()

    if admin_mode:
        filtered = filtered[
            filtered["ranking_global"].between(rank_range[0], rank_range[1])
            | filtered["ranking_global"].isna()
        ].copy()

    if "confianza_lectura" in filtered.columns and confianza:
        filtered = filtered[filtered["confianza_lectura"].isin(confianza)].copy()

    if review_only:
        filtered = filtered[filtered.apply(review_priority, axis=1) < 99].copy()

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
