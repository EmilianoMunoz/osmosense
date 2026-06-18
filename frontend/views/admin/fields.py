from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.data import (
    assign_cliente_parcela,
    api_error_message,
    create_cliente,
    delete_cliente_parcela,
    features_to_frame,
    filtered_geojson,
    load_admin_cliente_parcelas,
    load_admin_parcelas,
    load_admin_usuarios,
    load_geojson,
    update_parcela,
    update_usuario,
)
from frontend.map import bbox_center_zoom, feature_center, render_map, selected_parcela_id


ASSIGN_MAP_KEY = "assign_free_parcels_map"
ASSIGN_MAP_FOCUS_ZOOM = 14.5
UNASSIGN_MAP_PREFIX = "unassign_productor_map"
UNASSIGN_MAP_FOCUS_ZOOM = 14.5
PARCELAS_FLASH_KEY = "admin_parcelas_flash"


def _selected_assignment_ids() -> list[int]:
    selected = st.session_state.get("assign_parcela_ids", [])
    return sorted({int(value) for value in selected})


def _toggle_assignment_id(parcela_id: int) -> None:
    selected = set(_selected_assignment_ids())
    if int(parcela_id) in selected:
        selected.remove(int(parcela_id))
    else:
        selected.add(int(parcela_id))
    st.session_state["assign_parcela_ids"] = sorted(selected)


def _handle_assignment_map_selection() -> None:
    clicked_id = selected_parcela_id(st.session_state.get(ASSIGN_MAP_KEY))
    if clicked_id is None:
        return

    st.session_state["assign_last_clicked_id"] = int(clicked_id)
    _toggle_assignment_id(int(clicked_id))


def _clear_assignment_selection() -> None:
    st.session_state["assign_parcela_ids"] = []
    st.session_state.pop("assign_last_clicked_id", None)
    st.session_state.pop("assign_pending_payload", None)


def _parse_parcela_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for chunk in raw.replace("\n", ",").replace(";", ",").split(","):
        value = chunk.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"ID de parcela inválido: {value}")
        ids.append(int(value))
    return sorted(set(ids))


def _add_assignment_ids(parcela_ids: list[int]) -> None:
    selected = set(_selected_assignment_ids())
    selected.update(int(value) for value in parcela_ids)
    st.session_state["assign_parcela_ids"] = sorted(selected)


def _remove_assignment_ids(parcela_ids: list[int]) -> None:
    selected = set(_selected_assignment_ids())
    selected.difference_update(int(value) for value in parcela_ids)
    st.session_state["assign_parcela_ids"] = sorted(selected)


def _unassign_selection_key(cliente_id: int) -> str:
    return f"unassign_parcela_ids_{int(cliente_id)}"


def _unassign_last_clicked_key(cliente_id: int) -> str:
    return f"unassign_last_clicked_id_{int(cliente_id)}"


def _selected_unassign_ids(cliente_id: int) -> list[int]:
    selected = st.session_state.get(_unassign_selection_key(cliente_id), [])
    return sorted({int(value) for value in selected})


def _set_unassign_ids(cliente_id: int, parcela_ids: list[int]) -> None:
    st.session_state[_unassign_selection_key(cliente_id)] = sorted(
        {int(value) for value in parcela_ids}
    )


def _toggle_unassign_id(cliente_id: int, parcela_id: int) -> None:
    selected = set(_selected_unassign_ids(cliente_id))
    if int(parcela_id) in selected:
        selected.remove(int(parcela_id))
    else:
        selected.add(int(parcela_id))
    _set_unassign_ids(cliente_id, list(selected))


def _remove_unassign_ids(cliente_id: int, parcela_ids: list[int]) -> None:
    selected = set(_selected_unassign_ids(cliente_id))
    selected.difference_update(int(value) for value in parcela_ids)
    _set_unassign_ids(cliente_id, list(selected))


def _clear_unassign_selection(cliente_id: int) -> None:
    st.session_state.pop(_unassign_selection_key(cliente_id), None)
    st.session_state.pop(_unassign_last_clicked_key(cliente_id), None)


def _handle_unassign_map_selection(cliente_id: int, map_key: str) -> None:
    clicked_id = selected_parcela_id(st.session_state.get(map_key))
    if clicked_id is None:
        return
    st.session_state[_unassign_last_clicked_key(cliente_id)] = int(clicked_id)
    _toggle_unassign_id(cliente_id, int(clicked_id))


def _productor_parcel_count(cliente_id: int) -> int:
    data = load_admin_cliente_parcelas(int(cliente_id))
    if data.get("source") == "api_unavailable":
        return 0
    return int(data.get("count") or len(data.get("items", [])))


def _set_parcelas_flash(
    action: str,
    productor_label: str,
    parcela_ids: list[int],
    before_count: int | None = None,
    after_count: int | None = None,
) -> None:
    st.session_state[PARCELAS_FLASH_KEY] = {
        "action": action,
        "productor_label": productor_label,
        "parcela_ids": sorted({int(value) for value in parcela_ids}),
        "before_count": before_count,
        "after_count": after_count,
    }


@st.dialog("Operación completada")
def _show_parcelas_flash_dialog() -> None:
    flash = st.session_state.get(PARCELAS_FLASH_KEY)
    parcela_ids = [int(value) for value in flash.get("parcela_ids", [])]
    action = str(flash.get("action") or "Operación completada")
    productor_label = str(flash.get("productor_label") or "Productor")
    before_count = flash.get("before_count")
    after_count = flash.get("after_count")

    st.success(f"{action}: {len(parcela_ids)} parcela(s).")
    st.caption(f"Productor: {productor_label}")

    if before_count is not None or after_count is not None:
        cols = st.columns(2)
        cols[0].metric("Antes", "-" if before_count is None else int(before_count))
        cols[1].metric("Después", "-" if after_count is None else int(after_count))

    if parcela_ids:
        st.caption("IDs afectados: " + ", ".join(str(value) for value in parcela_ids[:40]))
        if len(parcela_ids) > 40:
            st.caption(f"+ {len(parcela_ids) - 40} parcelas más")

    if st.button("Aceptar", type="primary", width="stretch", key="hide_parcelas_flash"):
        st.session_state.pop(PARCELAS_FLASH_KEY, None)
        st.rerun()


def _render_parcelas_flash() -> None:
    if st.session_state.get(PARCELAS_FLASH_KEY):
        _show_parcelas_flash_dialog()


def _productores_frame() -> pd.DataFrame:
    data = load_admin_usuarios(limit=5000, activo=True)
    users = pd.DataFrame(data.get("items", []))
    if users.empty:
        return users
    if "rol" not in users.columns:
        return pd.DataFrame()
    productores = users[users["rol"].astype(str) == "productor"].copy()
    for col in ["apellido", "dni", "cliente_id", "email", "nombre"]:
        if col not in productores.columns:
            productores[col] = None
    return productores


def _productor_label(row: pd.Series) -> str:
    nombre = f"{row.get('nombre') or ''} {row.get('apellido') or ''}".strip()
    email = str(row.get("email") or "")
    dni = str(row.get("dni") or "").strip()
    base = nombre or email or f"Productor {int(row['usuario_id'])}"
    extra = f" · DNI {dni}" if dni and dni != "None" else ""
    return f"{base}{extra} · {email}"


def _filter_productores(productores: pd.DataFrame, search: str) -> pd.DataFrame:
    text = search.strip().lower()
    if not text:
        return productores
    haystack = (
        productores.get("email", pd.Series("", index=productores.index)).fillna("").astype(str)
        + " "
        + productores.get("nombre", pd.Series("", index=productores.index)).fillna("").astype(str)
        + " "
        + productores.get("apellido", pd.Series("", index=productores.index)).fillna("").astype(str)
        + " "
        + productores.get("dni", pd.Series("", index=productores.index)).fillna("").astype(str)
    ).str.lower()
    return productores[haystack.str.contains(text, regex=False)]


def _cliente_id_from_productor(productor: pd.Series) -> int | None:
    cliente_id = productor.get("cliente_id")
    if cliente_id is None or pd.isna(cliente_id):
        return None
    return int(cliente_id)


def _ensure_productor_assignment_profile(productor: pd.Series) -> int:
    cliente_id = _cliente_id_from_productor(productor)
    if cliente_id is not None:
        return cliente_id

    nombre = f"{productor.get('nombre') or ''} {productor.get('apellido') or ''}".strip()
    email = str(productor.get("email") or "")
    created = create_cliente(
        {
            "nombre": nombre or email or f"Productor {int(productor['usuario_id'])}",
            "tipo": "particular",
            "descripcion": f"Perfil interno de asignación de parcelas para {email}".strip(),
            "activo": True,
        }
    )
    cliente_id = int(created["item"]["cliente_id"])
    update_usuario(int(productor["usuario_id"]), {"cliente_id": cliente_id})
    return cliente_id


@st.dialog("Desasignar parcelas")
def render_bulk_unassign_parcelas_dialog(
    cliente_id: int,
    parcela_ids: list[int],
    productor_label: str,
) -> None:
    selected_ids = sorted({int(value) for value in parcela_ids})
    st.write(f"Productor: **{productor_label}**")
    st.write(f"Parcelas a desasignar: **{len(selected_ids)}**")
    st.caption(", ".join(str(value) for value in selected_ids[:40]))
    if len(selected_ids) > 40:
        st.caption(f"+ {len(selected_ids) - 40} parcelas más")
    st.warning(
        "Las parcelas dejarán de aparecer en la vista del productor. No se borran "
        "las parcelas ni su historial de ranking."
    )
    confirm = st.text_input("Escribí DESASIGNAR para confirmar", key="bulk_unassign_confirm")

    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.rerun()
    with col_confirm:
        if st.button(
            "Desasignar parcelas",
            type="primary",
            width="stretch",
            disabled=confirm.strip().upper() != "DESASIGNAR",
        ):
            try:
                before_count = _productor_parcel_count(cliente_id)
                for parcela_id in selected_ids:
                    delete_cliente_parcela(cliente_id, int(parcela_id))
                after_count = _productor_parcel_count(cliente_id)
            except Exception as exc:
                st.error(f"No se pudieron desasignar las parcelas: {api_error_message(exc)}")
            else:
                _set_parcelas_flash(
                    "Desasignación completada",
                    productor_label,
                    selected_ids,
                    before_count,
                    after_count,
                )
                _clear_unassign_selection(cliente_id)
                st.rerun()


@st.dialog("Confirmar asignación de parcelas")
def render_assignment_confirmation_dialog() -> None:
    payload = st.session_state.get("assign_pending_payload")
    if not payload:
        st.error("No hay una asignación pendiente para confirmar.")
        return

    selected_ids = [int(value) for value in payload["selected_ids"]]
    productor = payload["productor"]
    productor_label = str(payload["productor_label"])
    cultivo_destino = str(payload["cultivo_destino"])
    etiqueta = str(payload.get("etiqueta") or "").strip() or None

    st.write(f"Productor: **{productor_label}**")
    st.write(f"Cultivo operativo: **{cultivo_destino}**")
    st.write(f"Parcelas a asignar: **{len(selected_ids)}**")
    st.caption(", ".join(str(value) for value in selected_ids[:40]))
    if len(selected_ids) > 40:
        st.caption(f"+ {len(selected_ids) - 40} parcelas más")
    if etiqueta:
        st.write(f"Etiqueta: **{etiqueta}**")

    st.warning(
        "Al confirmar, estas parcelas quedarán vinculadas al productor y saldrán del listado "
        "de parcelas libres."
    )

    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.session_state.pop("assign_pending_payload", None)
            st.rerun()
    with col_confirm:
        if st.button("Confirmar asignación", type="primary", width="stretch"):
            try:
                productor_series = pd.Series(productor)
                cliente_id = _ensure_productor_assignment_profile(productor_series)
                before_count = _productor_parcel_count(cliente_id)
                for parcela_id in selected_ids:
                    update_parcela(int(parcela_id), {"cultivo_oficial": cultivo_destino})
                    assign_cliente_parcela(
                        cliente_id=cliente_id,
                        parcela_id=int(parcela_id),
                        etiqueta=etiqueta,
                    )
                after_count = _productor_parcel_count(cliente_id)
            except Exception as exc:
                st.error(f"No se pudieron asignar las parcelas: {api_error_message(exc)}")
            else:
                _set_parcelas_flash(
                    "Asignación completada",
                    productor_label,
                    selected_ids,
                    before_count,
                    after_count,
                )
                _clear_assignment_selection()
                st.rerun()


def render_productor_current_parcels(productor: pd.Series) -> None:
    productor_label = _productor_label(productor)
    cliente_id = _cliente_id_from_productor(productor)

    st.subheader("Parcelas actuales")
    if cliente_id is None:
        st.info("Este productor todavía no tiene parcelas asignadas.")
        return

    data = load_admin_cliente_parcelas(cliente_id)
    if data.get("source") == "api_unavailable":
        st.error("No se pudo consultar la API para cargar las parcelas del productor.")
        return

    parcelas = pd.DataFrame(data.get("items", []))
    if parcelas.empty:
        st.info("Este productor no tiene parcelas asignadas.")
        return

    metric_cols = st.columns(4)
    metric_cols[0].metric("Asignadas", len(parcelas))
    cultivo_series = parcelas.get(
        "cultivo_oficial",
        pd.Series("", index=parcelas.index, dtype="object"),
    ).astype(str)
    metric_cols[1].metric(
        "Vid",
        int((cultivo_series == "vid").sum()),
    )
    metric_cols[2].metric(
        "Olivo",
        int((cultivo_series == "olivo").sum()),
    )
    ranking_series = parcelas.get(
        "ranking_global",
        pd.Series(index=parcelas.index, dtype="float64"),
    )
    ranked_count = int(ranking_series.notna().sum())
    metric_cols[3].metric("Con ranking", ranked_count)

    if st.button("Verificar vista del productor", key="verify_productor_view", width="stretch"):
        geojson = load_geojson(cliente_id)
        if geojson.get("source") == "api_unavailable":
            st.error("No se pudo verificar la vista del productor desde la API.")
        else:
            st.success(
                f"La vista del productor devuelve {len(geojson.get('features', []))} parcelas."
            )

    filter_cols = st.columns([1, 1])
    with filter_cols[0]:
        search = st.text_input(
            "Buscar parcela asignada",
            placeholder="ID o etiqueta",
            key=f"assigned_search_{cliente_id}",
        )
    with filter_cols[1]:
        cultivo_filter = st.selectbox(
            "Cultivo",
            ["Todos", "vid", "olivo"],
            key=f"assigned_cultivo_{cliente_id}",
        )

    parcelas_visible = parcelas.copy()
    if cultivo_filter != "Todos" and "cultivo_oficial" in parcelas_visible.columns:
        parcelas_visible = parcelas_visible[
            parcelas_visible["cultivo_oficial"].astype(str) == cultivo_filter
        ]
    if search.strip():
        text = search.strip().lower()
        haystack = (
            parcelas_visible.get("parcela_id", pd.Series("", index=parcelas_visible.index)).fillna("").astype(str)
            + " "
            + parcelas_visible.get("etiqueta", pd.Series("", index=parcelas_visible.index)).fillna("").astype(str)
        ).str.lower()
        parcelas_visible = parcelas_visible[haystack.str.contains(text, regex=False)]

    visible_cols = [
        col
        for col in [
            "parcela_id",
            "cultivo_oficial",
            "prioridad",
            "riesgo_actual",
            "ranking_global",
            "fecha_ranking",
            "etiqueta",
        ]
        if col in parcelas_visible.columns
    ]
    st.dataframe(
        parcelas_visible[visible_cols].sort_values("parcela_id"),
        width="stretch",
        hide_index=True,
    )

    parcela_options = [int(value) for value in parcelas_visible["parcela_id"].dropna().tolist()]
    if not parcela_options:
        st.info("No hay parcelas asignadas bajo los filtros actuales.")
        return

    assigned_ids = {int(value) for value in parcelas["parcela_id"].dropna().tolist()}
    selected_parcelas = [
        parcela_id
        for parcela_id in _selected_unassign_ids(cliente_id)
        if parcela_id in assigned_ids
    ]
    _set_unassign_ids(cliente_id, selected_parcelas)

    st.markdown("**Seleccionar parcelas para desasignar**")
    st.caption(
        "El mapa muestra únicamente las parcelas vinculadas a este productor. "
        "Hacé clic sobre una parcela para agregarla o quitarla de la selección."
    )

    geojson = load_geojson(cliente_id)
    geo_df = features_to_frame(geojson)
    if geojson.get("source") == "api_unavailable" or geo_df.empty:
        st.warning("No se pudo cargar el mapa de parcelas del productor desde la API.")
    else:
        visible_ids = set(parcela_options)
        geo_visible = geo_df[geo_df["parcela_id"].astype(int).isin(visible_ids)].copy()
        geo_visible["seleccionada"] = geo_visible["parcela_id"].astype(int).isin(selected_parcelas)
        map_data = filtered_geojson(geojson, visible_ids)
        map_center, map_zoom = bbox_center_zoom(map_data)
        last_clicked_id = st.session_state.get(_unassign_last_clicked_key(cliente_id))
        if last_clicked_id is not None and int(last_clicked_id) in visible_ids:
            clicked_center = feature_center(map_data, int(last_clicked_id))
            if clicked_center is not None:
                map_center = clicked_center
                map_zoom = max(map_zoom, UNASSIGN_MAP_FOCUS_ZOOM)
        map_key = f"{UNASSIGN_MAP_PREFIX}_{cliente_id}"

        map_col, selection_col = st.columns([2.1, 1.0])
        with map_col:
            clicked_id = render_map(
                map_data,
                geo_visible,
                color_by="seleccionada",
                center=map_center,
                zoom=map_zoom,
                selected_id=None,
                admin_mode=True,
                map_key=map_key,
                on_select=lambda: _handle_unassign_map_selection(cliente_id, map_key),
                highlight_selected=False,
            )
            if clicked_id is not None:
                st.caption(f"Última parcela marcada: {int(clicked_id)}")

        with selection_col:
            st.metric("Seleccionadas", len(selected_parcelas))
            selected_text = ", ".join(str(value) for value in selected_parcelas)
            st.text_area(
                "IDs a desasignar",
                value=selected_text,
                height=110,
                disabled=True,
                placeholder="Seleccioná parcelas desde el mapa",
            )

            if selected_parcelas:
                remove_ids = st.multiselect(
                    "Quitar de la selección",
                    selected_parcelas,
                    key=f"unassign_remove_ids_{cliente_id}",
                )
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button(
                        "Quitar",
                        width="stretch",
                        disabled=not remove_ids,
                        key=f"unassign_remove_button_{cliente_id}",
                    ):
                        _remove_unassign_ids(cliente_id, remove_ids)
                        st.rerun()
                with action_cols[1]:
                    if st.button(
                        "Limpiar",
                        width="stretch",
                        key=f"unassign_clear_button_{cliente_id}",
                    ):
                        _clear_unassign_selection(cliente_id)
                        st.rerun()

    if st.button(
        "Desasignar seleccionadas",
        width="stretch",
        disabled=not selected_parcelas,
        key=f"unassign_confirm_button_{cliente_id}",
    ):
        render_bulk_unassign_parcelas_dialog(cliente_id, selected_parcelas, productor_label)


def render_parcel_assignment_panel() -> None:
    st.subheader("Asignar parcelas a productor")
    st.caption(
        "Mostramos solo parcelas activas que todavía no están asignadas a ningún productor."
    )
    _render_parcelas_flash()

    productores = _productores_frame()
    if productores.empty:
        st.info("Primero cargá al menos un usuario con rol productor.")
        return

    limit = st.number_input(
        "Cantidad máxima de parcelas libres a cargar",
        min_value=100,
        max_value=5000,
        value=1500,
        step=100,
        key="assign_parcelas_limit",
    )

    with st.spinner("Cargando parcelas libres..."):
        data = load_admin_parcelas(limit=int(limit), activo=True, sin_asignar=True)
    df = features_to_frame(data)

    if df.empty:
        if data.get("source") == "api_unavailable":
            st.error("No se pudo consultar la API para cargar parcelas analizables.")
        else:
            st.info("No hay parcelas analizadas sin productor bajo los filtros actuales.")
        return

    selected_ids = _selected_assignment_ids()
    df["seleccionada"] = df["parcela_id"].astype(int).isin(selected_ids)

    filter_cols = st.columns([1, 1, 1])
    with filter_cols[0]:
        cultivo_filter = st.selectbox(
            "Filtrar cultivo",
            ["Todos", "vid", "olivo"],
            key="assign_cultivo_filter",
        )
    with filter_cols[1]:
        parcela_search = st.text_input(
            "Buscar parcela libre",
            placeholder="ID de parcela",
            key="assign_parcela_search",
        )
    with filter_cols[2]:
        only_selected = st.checkbox(
            "Ver solo seleccionadas",
            value=False,
            key="assign_only_selected",
        )

    df_visible = df.copy()
    if cultivo_filter != "Todos" and "cultivo_oficial" in df_visible.columns:
        df_visible = df_visible[df_visible["cultivo_oficial"].astype(str) == cultivo_filter]
    if parcela_search.strip():
        text = parcela_search.strip()
        df_visible = df_visible[
            df_visible["parcela_id"].fillna("").astype(str).str.contains(text, regex=False)
        ]
    if only_selected:
        df_visible = df_visible[df_visible["seleccionada"]]

    map_col, form_col = st.columns([2.2, 1.0])

    with map_col:
        count_cols = st.columns(3)
        count_cols[0].metric("Parcelas visibles", f"{len(df_visible):,}".replace(",", "."))
        vid_count = int((df_visible["cultivo_oficial"].astype(str) == "vid").sum())
        olivo_count = int((df_visible["cultivo_oficial"].astype(str) == "olivo").sum())
        count_cols[1].metric("Vid", f"{vid_count:,}".replace(",", "."))
        count_cols[2].metric("Olivo", f"{olivo_count:,}".replace(",", "."))

        color_by = st.selectbox(
            "Color del mapa de asignación",
            ["seleccionada", "cultivo_oficial", "cultivo_original", "fuente"],
            index=0,
            key="assign_color_by",
        )
        if df_visible.empty:
            st.info("No hay parcelas libres bajo los filtros actuales.")
        else:
            map_center = None
            map_zoom = 8.3
            last_clicked_id = st.session_state.get("assign_last_clicked_id")
            visible_ids = set(df_visible["parcela_id"].dropna().astype(int).tolist())
            if last_clicked_id is not None and int(last_clicked_id) in visible_ids:
                map_center = feature_center(data, int(last_clicked_id))
                if map_center is not None:
                    map_zoom = ASSIGN_MAP_FOCUS_ZOOM

            clicked_id = render_map(
                data,
                df_visible,
                color_by=color_by,
                center=map_center,
                zoom=map_zoom,
                selected_id=None,
                admin_mode=True,
                map_key=ASSIGN_MAP_KEY,
                on_select=_handle_assignment_map_selection,
                highlight_selected=False,
            )
            if clicked_id is not None:
                st.caption(f"Última parcela seleccionada: {int(clicked_id)}")

    with form_col:
        st.metric("Parcelas seleccionadas", len(selected_ids))
        if selected_ids:
            st.caption(", ".join(str(value) for value in selected_ids[:20]))
            if len(selected_ids) > 20:
                st.caption(f"+ {len(selected_ids) - 20} parcelas más")

        raw_ids = st.text_area(
            "Agregar parcelas por ID",
            placeholder="Ej. 43070, 43071, 43072",
            key="assign_manual_ids",
            height=80,
        )
        add_cols = st.columns(2)
        with add_cols[0]:
            if st.button("Agregar IDs", width="stretch", disabled=not raw_ids.strip()):
                try:
                    parsed_ids = _parse_parcela_ids(raw_ids)
                    available_ids = set(df["parcela_id"].dropna().astype(int).tolist())
                    valid_ids = [value for value in parsed_ids if value in available_ids]
                    missing_ids = [value for value in parsed_ids if value not in available_ids]
                    if valid_ids:
                        _add_assignment_ids(valid_ids)
                    if missing_ids:
                        st.warning(
                            "No se agregaron IDs que no están cargados como libres: "
                            + ", ".join(str(value) for value in missing_ids[:20])
                        )
                    if valid_ids:
                        st.success(f"Se agregaron {len(valid_ids)} parcelas a la selección.")
                        st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with add_cols[1]:
            if st.button("Limpiar selección", width="stretch", disabled=not selected_ids):
                _clear_assignment_selection()
                st.rerun()

        if selected_ids:
            remove_ids = st.multiselect(
                "Quitar de la selección",
                selected_ids,
                key="assign_remove_ids",
            )
            if st.button("Quitar seleccionadas", width="stretch", disabled=not remove_ids):
                _remove_assignment_ids(remove_ids)
                st.rerun()

        productor_search = st.text_input(
            "Buscar productor",
            placeholder="nombre, email o DNI",
            key="assign_productor_search",
        )
        productores_visibles = _filter_productores(productores, productor_search)
        if productores_visibles.empty:
            st.info("No hay productores que coincidan con la búsqueda.")
            return

        productor_ids = [
            int(value) for value in productores_visibles["usuario_id"].dropna().tolist()
        ]
        productor_by_id = {
            int(row["usuario_id"]): row
            for _, row in productores_visibles.iterrows()
        }
        target_usuario_id = st.selectbox(
            "Productor destino",
            productor_ids,
            format_func=lambda value: _productor_label(productor_by_id[int(value)]),
            key="assign_productor_target",
        )

        cultivo_destino = st.radio(
            "Cultivo operativo",
            ["vid", "olivo"],
            horizontal=True,
            key="assign_cultivo_destino",
        )
        etiqueta = st.text_input(
            "Etiqueta para la relación",
            placeholder="Ej. Cuadro norte, lote nuevo",
            key="assign_etiqueta",
        )

        productor = productor_by_id[int(target_usuario_id)]
        productor_cliente_id = _cliente_id_from_productor(productor)
        st.caption(
            "Estado del productor: "
            + (
                "ya tiene parcelas vinculadas."
                if productor_cliente_id is not None
                else "sin parcelas vinculadas todavía."
            )
        )

        if selected_ids:
            with st.container(border=True):
                st.markdown("**Resumen previo**")
                st.caption(f"Productor: {_productor_label(productor)}")
                st.caption(f"Cultivo operativo: {cultivo_destino}")
                st.caption(f"Parcelas: {len(selected_ids)}")
                st.caption(", ".join(str(value) for value in selected_ids[:15]))
                if len(selected_ids) > 15:
                    st.caption(f"+ {len(selected_ids) - 15} parcelas más")

        if st.button(
            "Revisar y confirmar",
            type="primary",
            width="stretch",
            disabled=not selected_ids,
        ):
            st.session_state["assign_pending_payload"] = {
                "selected_ids": selected_ids,
                "productor": productor.to_dict(),
                "productor_label": _productor_label(productor),
                "cultivo_destino": cultivo_destino,
                "etiqueta": etiqueta.strip() or None,
            }
            render_assignment_confirmation_dialog()

    st.divider()
    render_productor_current_parcels(productor)


def render_parcelas_tab() -> None:
    st.subheader("Parcelas")
    st.caption("Asignación directa de parcelas a productores y desasignación desde mapa.")
    render_parcel_assignment_panel()


def render_clientes_tab() -> None:
    render_parcelas_tab()
