from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class DemoUser:
    username: str
    password: str
    label: str
    view_mode: str
    cliente_id: int | None = None


DEMO_USERS = {
    "admin": DemoUser(
        username="admin",
        password="admin123",
        label="Administrador",
        view_mode="Admin",
    ),
    "finca": DemoUser(
        username="finca",
        password="cliente123",
        label="Finca Demo Norte",
        view_mode="Cliente",
        cliente_id=1,
    ),
    "olivar": DemoUser(
        username="olivar",
        password="cliente123",
        label="Olivar Demo Este",
        view_mode="Cliente",
        cliente_id=2,
    ),
    "regional": DemoUser(
        username="regional",
        password="regional123",
        label="Regional DGI",
        view_mode="Regional",
    ),
}


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated", False))


def login_as(user: DemoUser) -> None:
    st.session_state["authenticated"] = True
    st.session_state["auth_user"] = user.username
    st.session_state["auth_label"] = user.label
    st.session_state["view_mode"] = user.view_mode
    st.session_state["auth_cliente_id"] = user.cliente_id
    st.session_state.pop("selected_parcela_id", None)


def logout() -> None:
    for key in [
        "authenticated",
        "auth_user",
        "auth_label",
        "view_mode",
        "auth_cliente_id",
        "selected_parcela_id",
        "prev_cliente_id",
    ]:
        st.session_state.pop(key, None)


def render_login() -> None:
    st.title("Estrés hídrico San Rafael")
    st.caption("Acceso al dashboard de parcelas de vid y olivo")

    left, right = st.columns([1.0, 1.1])
    with left:
        st.subheader("Ingresar")
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", width="stretch", type="primary")

        if submitted:
            user = DEMO_USERS.get(username.strip().lower())
            if user is not None and password == user.password:
                login_as(user)
                st.rerun()
            st.error("Usuario o contraseña inválidos.")

    with right:
        st.subheader("Entorno de desarrollo")
        st.write(
            "Los accesos rápidos se mantienen para probar el dashboard sin pasar "
            "por autenticación real mientras el producto sigue en desarrollo."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Cliente vid", width="stretch"):
                login_as(DEMO_USERS["finca"])
                st.rerun()
            if st.button("Cliente olivo", width="stretch"):
                login_as(DEMO_USERS["olivar"])
                st.rerun()
        with c2:
            if st.button("Admin", width="stretch"):
                login_as(DEMO_USERS["admin"])
                st.rerun()
            if st.button("Regional", width="stretch"):
                login_as(DEMO_USERS["regional"])
                st.rerun()

        st.caption(
            "Demo: admin/admin123 · finca/cliente123 · "
            "olivar/cliente123 · regional/regional123"
        )


def render_auth_sidebar() -> None:
    label = st.session_state.get("auth_label", "Usuario")
    st.sidebar.header("Sesión")
    st.sidebar.caption(f"Conectado como: {label}")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        logout()
        st.rerun()
