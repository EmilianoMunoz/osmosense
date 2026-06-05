from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from frontend.data import (
    activar_parcela_disponible,
    api_error_message,
    create_cliente,
    create_usuario,
    features_to_frame,
    load_admin_clientes,
    load_admin_parcelas_disponibles,
    load_admin_usuarios,
    load_clientes,
    update_cliente,
    update_usuario,
)
from frontend.map import render_map
from frontend.components.branding import render_fullscreen_loader


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _format_datetime_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def _clientes_frame() -> tuple[dict, pd.DataFrame]:
    data = load_admin_clientes(limit=5000)
    if data.get("source") == "api_unavailable":
        data = load_clientes()
    clientes = pd.DataFrame(data.get("items", []))
    if not clientes.empty:
        if "activo" not in clientes.columns:
            clientes["activo"] = True
        if "descripcion" not in clientes.columns:
            clientes["descripcion"] = None
        if "parcelas_asignadas" not in clientes.columns:
            clientes["parcelas_asignadas"] = 0
        if "updated_at" not in clientes.columns:
            clientes["updated_at"] = None
    return data, clientes


def _find_cliente(cliente_id: int) -> pd.Series | None:
    _, clientes = _clientes_frame()
    if clientes.empty or "cliente_id" not in clientes.columns:
        return None
    matches = clientes[clientes["cliente_id"].astype(int) == int(cliente_id)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _build_cliente_payload(
    nombre: str,
    tipo: str,
    descripcion: str,
    activo: bool,
) -> dict:
    nombre_clean = nombre.strip()
    if not nombre_clean:
        raise ValueError("El nombre del productor/campo es obligatorio.")
    return {
        "nombre": nombre_clean,
        "tipo": tipo,
        "descripcion": descripcion.strip() or None,
        "activo": activo,
    }


@st.dialog("Editar productor/campo")
def render_edit_cliente_dialog(cliente_id: int) -> None:
    selected = _find_cliente(cliente_id)
    if selected is None:
        st.error("No se encontró el productor/campo seleccionado.")
        return

    tipos = ["particular", "empresa", "regional", "demo"]
    current_tipo = str(selected.get("tipo") or "particular")
    if current_tipo not in tipos:
        tipos.append(current_tipo)

    with st.form(f"edit_cliente_form_{cliente_id}"):
        nombre = st.text_input(
            "Nombre",
            value=str(selected.get("nombre") or ""),
            key=f"edit_cliente_nombre_{cliente_id}",
        )
        tipo = st.selectbox(
            "Tipo",
            tipos,
            index=tipos.index(current_tipo),
            key=f"edit_cliente_tipo_{cliente_id}",
        )
        descripcion = st.text_area(
            "Descripción",
            value=str(selected.get("descripcion") or ""),
            key=f"edit_cliente_descripcion_{cliente_id}",
        )
        activo = st.checkbox(
            "Activo",
            value=bool(selected.get("activo", True)),
            key=f"edit_cliente_activo_{cliente_id}",
        )
        submitted = st.form_submit_button("Guardar cambios")

    if submitted:
        try:
            payload = _build_cliente_payload(nombre, tipo, descripcion, activo)
            update_cliente(int(cliente_id), payload)
        except Exception as exc:
            st.error(f"No se pudo actualizar el productor/campo: {api_error_message(exc)}")
        else:
            st.success("Productor/campo actualizado.")
            st.rerun()


@st.dialog("Eliminar productor/campo")
def render_delete_cliente_dialog(cliente_id: int) -> None:
    selected = _find_cliente(cliente_id)
    if selected is None:
        st.error("No se encontró el productor/campo seleccionado.")
        return

    nombre = str(selected.get("nombre") or f"Productor {cliente_id}")
    parcelas = int(selected.get("parcelas_asignadas", 0) or 0)
    st.warning(
        "Esta acción desactiva el productor/campo. No borra las parcelas asignadas ni el historial."
    )
    st.write(f"Productor/campo: **{nombre}**")
    st.write(f"Parcelas asignadas: **{parcelas}**")

    col_cancel, col_delete = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.rerun()
    with col_delete:
        if st.button("Eliminar acceso", type="primary", width="stretch"):
            try:
                update_cliente(int(cliente_id), {"activo": False})
            except Exception as exc:
                st.error(f"No se pudo eliminar el productor/campo: {api_error_message(exc)}")
            else:
                st.success("Productor/campo desactivado.")
                st.rerun()


def render_cliente_card(cliente: pd.Series) -> None:
    cliente_id = int(cliente["cliente_id"])
    activo = bool(cliente.get("activo", True))
    nombre = str(cliente.get("nombre") or "Sin nombre")
    tipo = str(cliente.get("tipo") or "-")
    descripcion = str(cliente.get("descripcion") or "Sin descripción")
    parcelas = int(cliente.get("parcelas_asignadas", 0) or 0)

    with st.container(border=True):
        header_cols = st.columns([2.3, 0.8, 0.8])
        with header_cols[0]:
            st.markdown(f"**{nombre}**")
            st.caption(descripcion)
        with header_cols[1]:
            st.metric("Tipo", tipo)
        with header_cols[2]:
            st.metric("Estado", "Activo" if activo else "Inactivo")

        detail_cols = st.columns(3)
        detail_cols[0].caption(f"Parcelas asignadas: {parcelas}")
        detail_cols[1].caption(f"ID: {cliente_id}")
        detail_cols[2].caption(f"Actualizado: {_format_datetime_value(cliente.get('updated_at'))}")

        action_cols = st.columns([1, 1, 3])
        with action_cols[0]:
            if st.button("Editar", key=f"edit_cliente_{cliente_id}", width="stretch"):
                render_edit_cliente_dialog(cliente_id)
        with action_cols[1]:
            if activo:
                if st.button("Eliminar", key=f"delete_cliente_{cliente_id}", width="stretch"):
                    render_delete_cliente_dialog(cliente_id)
            else:
                if st.button("Reactivar", key=f"reactivar_cliente_{cliente_id}", width="stretch"):
                    try:
                        update_cliente(cliente_id, {"activo": True})
                    except Exception as exc:
                        st.error(f"No se pudo reactivar el productor/campo: {api_error_message(exc)}")
                    else:
                        st.success("Productor/campo reactivado.")
                        st.rerun()


def render_clientes_tab() -> None:
    st.subheader("Productores/campos")
    st.caption("Gestión de productores o unidades privadas que tendrán parcelas asignadas.")

    data, clientes = _clientes_frame()
    st.caption(f"Fuente: {data.get('source', 'desconocida')} · {len(clientes)} productores/campos")

    with st.expander("Crear nuevo productor/campo", expanded=clientes.empty):
        with st.form("create_cliente_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                nombre = st.text_input("Nombre", key="new_cliente_nombre")
                tipo = st.selectbox(
                    "Tipo",
                    ["particular", "empresa", "regional", "demo"],
                    key="new_cliente_tipo",
                )
            with col_b:
                activo = st.checkbox("Activo", value=True, key="new_cliente_activo")
            descripcion = st.text_area("Descripción", key="new_cliente_descripcion")
            submitted = st.form_submit_button("Crear productor/campo")

        if submitted:
            try:
                payload = _build_cliente_payload(nombre, tipo, descripcion, activo)
                create_cliente(payload)
            except Exception as exc:
                st.error(f"No se pudo crear el productor/campo: {api_error_message(exc)}")
            else:
                st.success("Productor/campo creado.")
                st.rerun()

    if clientes.empty:
        st.info("No hay productores/campos cargados o la API no está disponible.")
        return

    st.divider()
    st.subheader("Productores/campos cargados")

    filter_cols = st.columns([1, 1, 2])
    with filter_cols[0]:
        estado = st.radio(
            "Estado",
            ["Activos", "Todos", "Inactivos"],
            horizontal=True,
            key="clientes_estado_filter",
        )
    with filter_cols[1]:
        tipos = sorted(clientes["tipo"].dropna().astype(str).unique().tolist())
        tipo_filter = st.multiselect("Tipos", tipos, default=tipos, key="clientes_tipo_filter")
    with filter_cols[2]:
        search = st.text_input("Buscar", placeholder="nombre o descripción", key="clientes_search")

    visible = clientes.copy()
    if estado == "Activos":
        visible = visible[visible["activo"].fillna(False).astype(bool)]
    elif estado == "Inactivos":
        visible = visible[~visible["activo"].fillna(False).astype(bool)]
    if tipo_filter:
        visible = visible[visible["tipo"].astype(str).isin(tipo_filter)]
    if search.strip():
        text = search.strip().lower()
        haystack = (
            visible.get("nombre", pd.Series("", index=visible.index)).fillna("").astype(str)
            + " "
            + visible.get("descripcion", pd.Series("", index=visible.index)).fillna("").astype(str)
        ).str.lower()
        visible = visible[haystack.str.contains(text, regex=False)]

    st.caption(f"{len(visible)} productores/campos visibles")
    for _, cliente in visible.iterrows():
        render_cliente_card(cliente)


@st.dialog("Confirmar activación de parcela")
def render_activate_parcela_dialog(
    parcela_id: int,
    cultivo_destino: str,
    cliente_id: int | None,
    etiqueta: str | None,
) -> None:
    st.write(f"Parcela: **{parcela_id}**")
    st.write(f"Nuevo cultivo operativo: **{cultivo_destino}**")
    st.write(
        "Productor asignado: "
        + (f"**{cliente_id}**" if cliente_id is not None else "**Sin asignar**")
    )
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

        clientes_data = load_clientes()
        clientes_items = clientes_data.get("items", [])

        cliente_options = [None] + [int(cliente["cliente_id"]) for cliente in clientes_items]

        cliente_labels = {None: "Sin asignar"}
        cliente_labels.update(
            {
                int(cliente["cliente_id"]): f"{cliente['nombre']} · {cliente['tipo']}"
                for cliente in clientes_items
            }
        )

        st.subheader("Activar para análisis")

        with st.form("preparar_activar_parcela_disponible"):
            cultivo_destino = st.radio("Nuevo cultivo operativo", ["vid", "olivo"], horizontal=True)

            cliente_id = st.selectbox(
                "Asignar productor/campo",
                cliente_options,
                format_func=lambda value: cliente_labels.get(value, str(value)),
            )

            etiqueta = st.text_input("Etiqueta interna", value="")
            submitted = st.form_submit_button("Revisar y confirmar")

        if submitted:
            render_activate_parcela_dialog(
                parcela_id=int(item["parcela_id"]),
                cultivo_destino=cultivo_destino,
                cliente_id=cliente_id,
                etiqueta=etiqueta or None,
            )


def _productor_options() -> tuple[list[int | None], dict[int | None, str]]:
    clientes_data = load_clientes()
    clientes_items = clientes_data.get("items", [])

    options: list[int | None] = [None]
    labels: dict[int | None, str] = {None: "Sin asignar"}

    for cliente in clientes_items:
        cliente_id = int(cliente["cliente_id"])
        options.append(cliente_id)
        labels[cliente_id] = (
            f"{cliente['nombre']} · {cliente['tipo']} · "
            f"{int(cliente.get('parcelas_asignadas', 0))} parcelas"
        )

    return options, labels


def _usuarios_frame() -> tuple[dict, pd.DataFrame]:
    data = load_admin_usuarios(limit=5000)
    users = pd.DataFrame(data.get("items", []))
    if not users.empty:
        for col in ["apellido", "dni", "productor_nombre", "last_login_at"]:
            if col not in users.columns:
                users[col] = None
        if "activo" not in users.columns:
            users["activo"] = True
    return data, users


def _find_usuario(usuario_id: int) -> pd.Series | None:
    _, users = _usuarios_frame()
    if users.empty or "usuario_id" not in users.columns:
        return None
    matches = users[users["usuario_id"].astype(int) == int(usuario_id)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _build_usuario_payload(
    email: str,
    nombre: str,
    apellido: str,
    dni: str,
    rol: str,
    cliente_id: int | None,
    activo: bool,
    password: str | None = None,
) -> dict:
    email_clean = email.strip().lower()
    if not email_clean:
        raise ValueError("El email es obligatorio.")
    if not EMAIL_RE.match(email_clean):
        raise ValueError("El email no tiene un formato válido.")
    nombre_clean = nombre.strip()
    if not nombre_clean:
        raise ValueError("El nombre es obligatorio.")
    if password is not None and password and len(password) < 6:
        raise ValueError("La contraseña debe tener al menos 6 caracteres.")
    if password is not None and not password:
        password = None

    payload = {
        "email": email_clean,
        "nombre": nombre_clean,
        "apellido": apellido.strip() or None,
        "dni": dni.strip() or None,
        "rol": rol,
        "activo": activo,
    }
    if rol == "productor" and cliente_id is not None:
        payload["cliente_id"] = int(cliente_id)
    elif rol in {"admin", "regional"}:
        payload["cliente_id"] = None
    if password:
        payload["password"] = password
    return payload


@st.dialog("Editar usuario")
def render_edit_usuario_dialog(usuario_id: int) -> None:
    selected = _find_usuario(usuario_id)
    if selected is None:
        st.error("No se encontró el usuario seleccionado.")
        return

    productor_options, productor_labels = _productor_options()
    current_rol = (
        selected.get("rol")
        if selected.get("rol") in ["productor", "regional", "admin"]
        else "productor"
    )

    with st.form(f"edit_usuario_form_{usuario_id}"):
        email = st.text_input(
            "Email",
            value=str(selected.get("email") or ""),
            key=f"edit_user_email_{usuario_id}",
        )
        nombre = st.text_input(
            "Nombre",
            value=str(selected.get("nombre") or ""),
            key=f"edit_user_nombre_{usuario_id}",
        )
        apellido = st.text_input(
            "Apellido",
            value=str(selected.get("apellido") or ""),
            key=f"edit_user_apellido_{usuario_id}",
        )
        dni = st.text_input(
            "DNI",
            value=str(selected.get("dni") or ""),
            key=f"edit_user_dni_{usuario_id}",
        )
        rol = st.selectbox(
            "Rol",
            ["productor", "regional", "admin"],
            index=["productor", "regional", "admin"].index(current_rol),
            key=f"edit_user_rol_{usuario_id}",
        )

        cliente_id = None
        if rol == "productor":
            current_cliente = selected.get("cliente_id")
            current_cliente = int(current_cliente) if pd.notna(current_cliente) else None
            index = (
                productor_options.index(current_cliente)
                if current_cliente in productor_options
                else 0
            )
            cliente_id = st.selectbox(
                "Productor/campo asociado (opcional)",
                productor_options,
                index=index,
                format_func=lambda value: productor_labels.get(value, str(value)),
                key=f"edit_user_cliente_id_{usuario_id}",
            )

        password = st.text_input(
            "Nueva contraseña",
            type="password",
            help="Dejar vacío para conservar la actual.",
            key=f"edit_user_password_{usuario_id}",
        )
        activo = st.checkbox(
            "Activo",
            value=bool(selected.get("activo", True)),
            key=f"edit_user_activo_{usuario_id}",
        )
        submitted = st.form_submit_button("Guardar cambios")

    if submitted:
        try:
            payload = _build_usuario_payload(
                email,
                nombre,
                apellido,
                dni,
                rol,
                cliente_id,
                activo,
                password,
            )
            update_usuario(int(usuario_id), payload)
        except Exception as exc:
            st.error(f"No se pudo actualizar el usuario: {api_error_message(exc)}")
        else:
            st.success("Usuario actualizado.")
            st.rerun()


@st.dialog("Eliminar usuario")
def render_delete_usuario_dialog(usuario_id: int) -> None:
    selected = _find_usuario(usuario_id)
    if selected is None:
        st.error("No se encontró el usuario seleccionado.")
        return

    email = str(selected.get("email") or f"Usuario {usuario_id}")
    st.warning(
        "Esta acción desactiva el acceso del usuario. No borra el registro físico "
        "para conservar trazabilidad."
    )
    st.write(f"Usuario: **{email}**")

    col_cancel, col_delete = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.rerun()
    with col_delete:
        if st.button("Eliminar acceso", type="primary", width="stretch"):
            try:
                update_usuario(int(usuario_id), {"activo": False})
            except Exception as exc:
                st.error(f"No se pudo eliminar el usuario: {api_error_message(exc)}")
            else:
                st.success("Usuario desactivado.")
                st.rerun()


def render_usuario_card(user: pd.Series) -> None:
    usuario_id = int(user["usuario_id"])
    activo = bool(user.get("activo", True))
    rol = str(user.get("rol") or "-")
    nombre = str(user.get("nombre") or "Sin nombre")
    apellido = str(user.get("apellido") or "")
    dni = str(user.get("dni") or "-")
    nombre_completo = f"{nombre} {apellido}".strip()
    email = str(user.get("email") or "-")
    productor = user.get("productor_nombre")
    productor_label = str(productor) if pd.notna(productor) and productor else "Sin campo asociado"
    last_login = _format_datetime_value(user.get("last_login_at"))

    with st.container(border=True):
        header_cols = st.columns([2.4, 0.8, 0.8])
        with header_cols[0]:
            st.markdown(f"**{nombre_completo}**")
            st.caption(email)
        with header_cols[1]:
            st.metric("Rol", rol)
        with header_cols[2]:
            st.metric("Estado", "Activo" if activo else "Inactivo")

        detail_cols = st.columns(3)
        detail_cols[0].caption(f"Campo: {productor_label}")
        detail_cols[1].caption(f"Último ingreso: {last_login}")
        detail_cols[2].caption(f"DNI: {dni} · ID: {usuario_id}")

        action_cols = st.columns([1, 1, 3])
        with action_cols[0]:
            if st.button("Editar", key=f"edit_usuario_{usuario_id}", width="stretch"):
                render_edit_usuario_dialog(usuario_id)
        with action_cols[1]:
            if activo:
                if st.button("Eliminar", key=f"delete_usuario_{usuario_id}", width="stretch"):
                    render_delete_usuario_dialog(usuario_id)
            else:
                if st.button("Reactivar", key=f"reactivar_usuario_{usuario_id}", width="stretch"):
                    try:
                        update_usuario(usuario_id, {"activo": True})
                    except Exception as exc:
                        st.error(f"No se pudo reactivar el usuario: {api_error_message(exc)}")
                    else:
                        st.success("Usuario reactivado.")
                        st.rerun()


def render_users_tab() -> None:
    st.subheader("Usuarios")
    st.caption("Alta y mantenimiento de accesos. Roles operativos: admin, regional y productor.")

    data, users = _usuarios_frame()

    st.caption(f"Fuente: {data.get('source', 'desconocida')} · {len(users)} usuarios")

    productor_options, productor_labels = _productor_options()

    with st.expander("Crear nuevo usuario", expanded=users.empty):
        with st.form("create_usuario_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                email = st.text_input("Email", key="new_user_email")
                nombre = st.text_input("Nombre", key="new_user_nombre")
                apellido = st.text_input("Apellido", key="new_user_apellido")
                dni = st.text_input("DNI", key="new_user_dni")
            with col_b:
                rol = st.selectbox("Rol", ["productor", "regional", "admin"], key="new_user_rol")
                activo = st.checkbox("Activo", value=True, key="new_user_activo")

            cliente_id = None
            if rol == "productor":
                cliente_id = st.selectbox(
                    "Productor/campo asociado (opcional)",
                    productor_options,
                    format_func=lambda value: productor_labels.get(value, str(value)),
                    key="new_user_cliente_id",
                )

            password = st.text_input("Contraseña inicial", type="password", key="new_user_password")
            submitted = st.form_submit_button("Crear usuario")

        if submitted:
            try:
                if len(password) < 6:
                    raise ValueError("La contraseña inicial debe tener al menos 6 caracteres.")
                payload = _build_usuario_payload(
                    email,
                    nombre,
                    apellido,
                    dni,
                    rol,
                    cliente_id,
                    activo,
                    password,
                )
                create_usuario(payload)
            except Exception as exc:
                st.error(f"No se pudo crear el usuario: {api_error_message(exc)}")
            else:
                st.success("Usuario creado.")
                st.rerun()

    if users.empty:
        st.info("No hay usuarios cargados o la API no está disponible.")
        return

    st.divider()
    st.subheader("Usuarios cargados")

    filter_cols = st.columns([1, 1, 2])
    with filter_cols[0]:
        estado = st.radio(
            "Estado",
            ["Activos", "Todos", "Inactivos"],
            horizontal=True,
            key="usuarios_estado_filter",
        )
    with filter_cols[1]:
        rol_filter = st.multiselect(
            "Roles",
            ["admin", "regional", "productor"],
            default=["admin", "regional", "productor"],
            key="usuarios_rol_filter",
        )
    with filter_cols[2]:
        search = st.text_input("Buscar", placeholder="email, nombre o campo", key="usuarios_search")

    visible = users.copy()
    if estado == "Activos":
        visible = visible[visible["activo"].fillna(False).astype(bool)]
    elif estado == "Inactivos":
        visible = visible[~visible["activo"].fillna(False).astype(bool)]
    if rol_filter:
        visible = visible[visible["rol"].isin(rol_filter)]
    if search.strip():
        text = search.strip().lower()
        haystack = (
            visible.get("email", pd.Series("", index=visible.index)).fillna("").astype(str)
            + " "
            + visible.get("nombre", pd.Series("", index=visible.index)).fillna("").astype(str)
            + " "
            + visible.get("apellido", pd.Series("", index=visible.index)).fillna("").astype(str)
            + " "
            + visible.get("dni", pd.Series("", index=visible.index)).fillna("").astype(str)
            + " "
            + visible.get("productor_nombre", pd.Series("", index=visible.index)).fillna("").astype(str)
        ).str.lower()
        visible = visible[haystack.str.contains(text, regex=False)]

    st.caption(f"{len(visible)} usuarios visibles")
    for _, user in visible.iterrows():
        render_usuario_card(user)


def render_admin_management_area() -> None:
    tab_productores, tab_usuarios, tab_parcelas = st.tabs(
        ["Productores/campos", "Usuarios", "Parcelas disponibles"]
    )

    with tab_productores:
        render_clientes_tab()

    with tab_usuarios:
        render_users_tab()

    with tab_parcelas:
        render_available_parcels_tab()
