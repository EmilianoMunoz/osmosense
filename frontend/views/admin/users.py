from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from frontend.data import (
    api_error_message,
    create_usuario,
    delete_usuario,
    load_admin_cliente_parcelas,
    load_admin_usuarios,
    load_clientes,
    update_usuario,
)


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DNI_RE = re.compile(r"^\d{7,9}$")


def _clean_dni(value: str) -> str:
    return value.strip().replace(".", "").replace(" ", "").replace("-", "")


def _format_datetime_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


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


def _assigned_parcels_count(cliente_id: object) -> int:
    if cliente_id is None or pd.isna(cliente_id):
        return 0
    data = load_admin_cliente_parcelas(int(cliente_id))
    if data.get("source") == "api_unavailable":
        return 0
    return int(data.get("count") or len(data.get("items", [])))


def _render_users_summary(users: pd.DataFrame) -> None:
    if users.empty:
        return

    activo = users.get("activo", pd.Series(True, index=users.index)).fillna(False).astype(bool)
    productores = users.get("rol", pd.Series("", index=users.index)).astype(str) == "productor"
    sin_perfil = productores & users.get("cliente_id", pd.Series(index=users.index)).isna()

    cols = st.columns(4)
    cols[0].metric("Usuarios activos", int(activo.sum()))
    cols[1].metric("Productores", int(productores.sum()))
    cols[2].metric("Productores sin parcelas", int(sin_perfil.sum()))
    cols[3].metric("Inactivos", int((~activo).sum()))


def _build_usuario_payload(
    email: str,
    nombre: str,
    apellido: str,
    dni: str,
    rol: str,
    cliente_id: int | None,
    activo: bool,
    password: str | None = None,
    password_confirm: str | None = None,
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
    if password and password_confirm is not None and password != password_confirm:
        raise ValueError("Las contraseñas no coinciden.")
    if password is not None and not password:
        password = None

    apellido_clean = apellido.strip()
    dni_clean = _clean_dni(dni)

    if rol == "productor":
        if not apellido_clean:
            raise ValueError("El apellido es obligatorio para usuarios productores.")
        if not dni_clean:
            raise ValueError("El DNI es obligatorio para usuarios productores.")

    if dni_clean and not DNI_RE.match(dni_clean):
        raise ValueError("El DNI debe contener entre 7 y 9 dígitos.")

    payload = {
        "email": email_clean,
        "nombre": nombre_clean,
        "apellido": apellido_clean or None,
        "dni": dni_clean or None,
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
                "Perfil de parcelas asociado (opcional)",
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
        password_confirm = st.text_input(
            "Confirmar nueva contraseña",
            type="password",
            help="Completar solo si se indicó nueva contraseña.",
            key=f"edit_user_password_confirm_{usuario_id}",
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
                password_confirm,
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
    assigned_count = _assigned_parcels_count(selected.get("cliente_id"))

    st.warning(
        "Esta acción desactiva el acceso del usuario. No borra el registro físico "
        "para conservar trazabilidad."
    )
    st.write(f"Usuario: **{email}**")
    if assigned_count:
        st.info(
            f"Este productor tiene {assigned_count} parcelas asociadas. Al desactivar "
            "el usuario, esas parcelas no se borran ni pierden ranking, pero el productor "
            "ya no podrá verlas hasta reactivar el acceso."
        )
    confirm = st.text_input(
        "Escribí DESACTIVAR para confirmar",
        key=f"delete_user_confirm_{usuario_id}",
    )

    col_cancel, col_delete = st.columns(2)
    with col_cancel:
        if st.button("Cancelar", width="stretch"):
            st.rerun()
    with col_delete:
        if st.button(
            "Desactivar acceso",
            type="primary",
            width="stretch",
            disabled=confirm.strip().upper() != "DESACTIVAR",
        ):
            try:
                delete_usuario(int(usuario_id))
            except Exception as exc:
                st.error(f"No se pudo desactivar el usuario: {api_error_message(exc)}")
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
    productor_label = str(productor) if pd.notna(productor) and productor else "Sin parcelas asociadas"
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
        detail_cols[0].caption(f"Parcelas: {productor_label}")
        detail_cols[1].caption(f"Último ingreso: {last_login}")
        detail_cols[2].caption(f"DNI: {dni} · ID: {usuario_id}")

        action_cols = st.columns([1, 1, 3])
        with action_cols[0]:
            if st.button("Editar", key=f"edit_usuario_{usuario_id}", width="stretch"):
                render_edit_usuario_dialog(usuario_id)
        with action_cols[1]:
            if activo:
                if st.button("Desactivar", key=f"delete_usuario_{usuario_id}", width="stretch"):
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
    _render_users_summary(users)

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
                    "Perfil de parcelas asociado (opcional)",
                    productor_options,
                    format_func=lambda value: productor_labels.get(value, str(value)),
                    key="new_user_cliente_id",
                )

            password_cols = st.columns(2)
            with password_cols[0]:
                password = st.text_input(
                    "Contraseña inicial",
                    type="password",
                    key="new_user_password",
                )
            with password_cols[1]:
                password_confirm = st.text_input(
                    "Confirmar contraseña",
                    type="password",
                    key="new_user_password_confirm",
                )
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
                    password_confirm,
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
        search = st.text_input("Buscar", placeholder="email, nombre o DNI", key="usuarios_search")

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
