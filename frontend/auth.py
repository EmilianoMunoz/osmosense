from __future__ import annotations

import os
from dataclasses import dataclass

import requests
import streamlit as st
from dotenv import load_dotenv

from frontend.components.branding import render_logo, render_sidebar_logo


@dataclass(frozen=True)
class DemoUser:
    username: str
    password: str
    label: str
    view_mode: str
    rol: str
    cliente_id: int | None = None


DEMO_USERS = {
    "admin": DemoUser(
        username="admin",
        password="admin123",
        label="Administrador",
        view_mode="Admin",
        rol="admin",
    ),
    "finca": DemoUser(
        username="finca",
        password="cliente123",
        label="Finca Demo Norte",
        view_mode="Productor",
        rol="productor",
        cliente_id=1,
    ),
    "olivar": DemoUser(
        username="olivar",
        password="cliente123",
        label="Olivar Demo Este",
        view_mode="Productor",
        rol="productor",
        cliente_id=2,
    ),
    "regional": DemoUser(
        username="regional",
        password="regional123",
        label="Regional DGI",
        view_mode="Regional",
        rol="regional",
    ),
}


def api_base_url() -> str:
    load_dotenv()
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated", False))


def login_as(user: DemoUser) -> None:
    st.session_state["authenticated"] = True
    st.session_state["auth_user"] = user.username
    st.session_state["auth_label"] = user.label
    st.session_state["view_mode"] = user.view_mode
    st.session_state["auth_cliente_id"] = user.cliente_id
    st.session_state["auth_rol"] = user.rol
    st.session_state["auth_source"] = "demo"
    st.session_state.pop("auth_token", None)
    st.session_state.pop("selected_parcela_id", None)


def login_from_api(username: str, password: str) -> tuple[bool, str | None, bool]:
    login = username.strip().lower()
    if not login or not password:
        return False, "Ingrese usuario y contraseña.", True

    try:
        response = requests.post(
            f"{api_base_url()}/auth/login",
            json={"email": login, "password": password},
            timeout=8,
        )
    except requests.RequestException:
        return False, None, False

    if response.status_code == 404:
        return False, None, False
    if response.status_code == 401:
        return False, "Usuario o contraseña inválidos.", True
    if not response.ok:
        return False, f"Error de autenticación HTTP {response.status_code}.", True

    payload = response.json()
    user = payload.get("user", {})
    st.session_state["authenticated"] = True
    st.session_state["auth_user"] = user.get("email", login)
    st.session_state["auth_label"] = user.get("nombre") or user.get("email") or login
    st.session_state["view_mode"] = user.get("view_mode", "Productor")
    st.session_state["auth_cliente_id"] = user.get("cliente_id")
    st.session_state["auth_rol"] = user.get("rol")
    st.session_state["auth_source"] = payload.get("source", "postgis")
    st.session_state["auth_token"] = payload.get("access_token")
    st.session_state.pop("selected_parcela_id", None)
    return True, None, True


def logout() -> None:
    for key in [
        "authenticated",
        "auth_user",
        "auth_label",
        "view_mode",
        "auth_cliente_id",
        "auth_rol",
        "auth_source",
        "auth_token",
        "selected_parcela_id",
        "prev_cliente_id",
    ]:
        st.session_state.pop(key, None)


def render_login() -> None:
    st.markdown(
        """
        <style>
        /* Centra visualmente el bloque principal */
        .block-container {
            padding-top: 3rem;
        }

        /* Mejora visual del contenedor con borde de Streamlit */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 18px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.12);
        }

        .login-title {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .login-subtitle {
            text-align: center;
            opacity: 0.75;
            margin-bottom: 1.5rem;
        }

        .demo-title {
            text-align: center;
            font-size: 1rem;
            font-weight: 600;
            margin-top: 1.25rem;
            margin-bottom: 0.25rem;
        }

        .demo-caption {
            text-align: center;
            opacity: 0.70;
            font-size: 0.85rem;
            margin-bottom: 1rem;
        }

        .credentials-caption {
            text-align: center;
            opacity: 0.65;
            font-size: 0.80rem;
            margin-top: 1rem;
        }

        div[data-testid="stForm"] {
            border: none;
            padding: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.15, 1])

    with center:
        with st.container(border=True):
            
            st.markdown(
                """
                <div style="height: 50px;"></div>
                """,
                unsafe_allow_html=True,
            )

            logo_left, logo_center, logo_right = st.columns([0.5, 2.0, 0.5])
            with logo_center:
                render_logo(width=480)

            st.markdown(
                """
                <div style="height: 50px;"></div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("login_form"):
                username = st.text_input(
                    "Usuario",
                    placeholder="Ingrese su usuario",
                )

                password = st.text_input(
                    "Contraseña",
                    type="password",
                    placeholder="Ingrese su contraseña",
                )

                submitted = st.form_submit_button(
                    "Ingresar",
                    width="stretch",
                    type="primary",
                )

            if submitted:
                ok, message, api_available = login_from_api(username, password)
                if ok:
                    st.rerun()

                if not api_available:
                    user = DEMO_USERS.get(username.strip().lower())
                    if user is not None and password == user.password:
                        login_as(user)
                        st.rerun()
                    message = "API no disponible. Se intentó fallback demo y las credenciales no coinciden."

                st.error(message or "Usuario o contraseña inválidos.")

            st.markdown(
                """
                <div class="demo-title">Accesos rápidos</div>
                <div class="demo-caption">
                    Entorno de desarrollo para probar distintos perfiles del dashboard.
                </div>
                """,
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2)

            with c1:
                if st.button("Productor vid", width="stretch"):
                    login_as(DEMO_USERS["finca"])
                    st.rerun()

                if st.button("Admin", width="stretch"):
                    login_as(DEMO_USERS["admin"])
                    st.rerun()

            with c2:
                if st.button("Productor olivo", width="stretch"):
                    login_as(DEMO_USERS["olivar"])
                    st.rerun()

                if st.button("Regional", width="stretch"):
                    login_as(DEMO_USERS["regional"])
                    st.rerun()

            st.markdown(
                """
                <div class="credentials-caption">
                    Demo: admin/admin123 · finca/cliente123 · olivar/cliente123 · regional/regional123
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_auth_sidebar() -> None:
    label = st.session_state.get("auth_label", "Usuario")
    source = st.session_state.get("auth_source")
    role = st.session_state.get("auth_rol")
    render_sidebar_logo()
    st.sidebar.header("Sesión")
    if source == "postgis":
        st.sidebar.success("Sesión PostGIS")
    elif source == "demo":
        st.sidebar.warning("Sesión demo")
    else:
        st.sidebar.info("Sesión local")
    st.sidebar.caption(f"Usuario: {label}")
    if role:
        st.sidebar.caption(f"Rol: {role}")
    if source == "demo":
        st.sidebar.caption("Modo desarrollo: no usa token ni permisos reales de API.")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        logout()
        st.rerun()
