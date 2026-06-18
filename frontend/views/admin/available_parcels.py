from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.data import (
    activar_parcela_disponible,
    api_error_message,
    create_cliente,
    features_to_frame,
    load_admin_usuarios,
    load_admin_parcelas_disponibles,
    update_usuario,
)
from frontend.components.branding import render_fullscreen_loader
from frontend.map import render_map


@st.dialog("Confirmar activación de parcela")
def render_activate_parcela_dialog(
    parcela_id: int,
    cultivo_destino: str,
    productor: dict | None,
    etiqueta: str | None,
) -> None:
    st.write(f"Parcela: **{parcela_id}**")
    st.write(f"Nuevo cultivo operativo: **{cultivo_destino}**")
    productor_label = _productor_label(productor) if productor else "Sin asignar"
    st.write(f"Productor asignado: **{productor_label}**")
    if etiqueta:
        st.write(f"Etiqueta interna: **{etiqueta}**")

    st.warning("La parcela entrará al universo evaluable vid/olivo en las próximas corridas.")

    col_cancel, col_ok = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.rerun()
    with col_ok:
        if st.button("Confirmar activación", type="primary", width="stretch"):
            try:
                cliente_id = (
                    _ensure_productor_assignment_profile(productor)
                    if productor is not None
                    else None
                )
                activar_parcela_disponible(
                    parcela_id=int(parcela_id),
                    cultivo_oficial=cultivo_destino,
                    cliente_id=cliente_id,
                    etiqueta=etiqueta or None,
                )
            except Exception as exc:
                st.error(f"No se pudo activar la parcela: {api_error_message(exc)}")
            else:
                st.success("Parcela activada. Entrará al universo objetivo PostGIS.")
                st.session_state.pop("selected_disponible_id", None)
                st.rerun()


def _productores_disponibles() -> list[dict]:
    data = load_admin_usuarios(limit=5000, activo=True)
    users = pd.DataFrame(data.get("items", []))
    if users.empty or "rol" not in users.columns:
        return []
    productores = users[users["rol"].astype(str) == "productor"].copy()
    return productores.to_dict("records")


def _productor_label(productor: dict | None) -> str:
    if not productor:
        return "Sin asignar"
    nombre = f"{productor.get('nombre') or ''} {productor.get('apellido') or ''}".strip()
    email = str(productor.get("email") or "")
    dni = str(productor.get("dni") or "").strip()
    base = nombre or email or f"Productor {int(productor['usuario_id'])}"
    extra = f" · DNI {dni}" if dni and dni != "None" else ""
    return f"{base}{extra} · {email}"


def _ensure_productor_assignment_profile(productor: dict) -> int:
    cliente_id = productor.get("cliente_id")
    if cliente_id is not None and pd.notna(cliente_id):
        return int(cliente_id)

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


def render_available_parcels_tab() -> None:
    st.subheader("Parcelas disponibles")
    st.caption("Parcelas activas cuyo cultivo operativo todavía no es vid ni olivo.")

    limit = st.number_input(
        "Cantidad máxima a cargar en el mapa",
        min_value=100,
        max_value=20000,
        value=3000,
        step=500,
    )

    loading = render_fullscreen_loader("Cargando parcelas disponibles...")
    with st.spinner("Cargando parcelas disponibles..."):
        data = load_admin_parcelas_disponibles(limit=int(limit))
    loading.empty()
    df = features_to_frame(data)

    if df.empty:
        st.info("No hay parcelas disponibles o la API no está disponible.")
        return

    st.caption(
        f"Fuente: {data.get('source', 'desconocida')} · "
        f"Mostrando {len(df):,} parcelas".replace(",", ".")
    )

    col_map, col_detail = st.columns([2.2, 1.0])

    with col_map:
        color_by = st.selectbox(
            "Color",
            ["cultivo_original", "cultivo_oficial", "fuente"],
            index=0,
            key="available_color_by",
        )

        selected_id = st.session_state.get("selected_disponible_id")

        clicked_id = render_map(
            data,
            df,
            color_by=color_by,
            center=None,
            zoom=8.3,
            selected_id=selected_id,
            admin_mode=True,
            map_key="available_parcels_map",
        )

        if clicked_id is not None:
            st.session_state["selected_disponible_id"] = clicked_id

    with col_detail:
        st.subheader("Parcela seleccionada")

        selected_id = st.session_state.get("selected_disponible_id")

        if selected_id is None:
            selected_id = int(df.iloc[0]["parcela_id"])
            st.session_state["selected_disponible_id"] = selected_id

        row = df[df["parcela_id"].astype(int) == int(selected_id)]

        if row.empty:
            st.info("Seleccioná una parcela disponible en el mapa.")
            return

        item = row.iloc[0]

        area = f"{item.get('area_m2', 0):.0f} m²" if pd.notna(item.get("area_m2")) else "-"
        with st.container(border=True):
            st.markdown(f"**Parcela {int(item['parcela_id'])}**")
            st.caption(f"Cultivo original: {item.get('cultivo_original', '-')}")
            st.caption(f"Cultivo oficial: {item.get('cultivo_oficial', '-')}")
            st.caption(f"Área: {area}")
            st.caption(f"Fuente: {item.get('fuente', '-')}")

        productores = _productores_disponibles()
        productor_options = [None] + [int(productor["usuario_id"]) for productor in productores]
        productor_by_id = {
            int(productor["usuario_id"]): productor
            for productor in productores
        }
        productor_labels = {None: "Sin asignar"}
        productor_labels.update(
            {
                usuario_id: _productor_label(productor)
                for usuario_id, productor in productor_by_id.items()
            }
        )

        st.subheader("Activar para análisis")

        with st.form("preparar_activar_parcela_disponible"):
            cultivo_destino = st.radio("Nuevo cultivo operativo", ["vid", "olivo"], horizontal=True)

            productor_id = st.selectbox(
                "Asignar productor",
                productor_options,
                format_func=lambda value: productor_labels.get(value, str(value)),
            )

            etiqueta = st.text_input("Etiqueta interna", value="")
            submitted = st.form_submit_button("Revisar y confirmar")

        if submitted:
            render_activate_parcela_dialog(
                parcela_id=int(item["parcela_id"]),
                cultivo_destino=cultivo_destino,
                productor=productor_by_id.get(int(productor_id)) if productor_id else None,
                etiqueta=etiqueta or None,
            )
