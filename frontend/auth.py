from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests
import streamlit as st
from dotenv import load_dotenv

from frontend.components.branding import render_logo, render_sidebar_logo
from frontend.config import quick_login_enabled


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class QuickLoginUser:
    username: str
    password: str
    label: str
    view_mode: str
    rol: str
    cliente_id: int | None = None


QUICK_LOGIN_USERS = {
    "admin": QuickLoginUser(
        username="admin@osmosense.local",
        password="admin123",
        label="Administrador",
        view_mode="Admin",
        rol="admin",
    ),
    "finca": QuickLoginUser(
        username="productor.vid@osmosense.local",
        password="cliente123",
        label="Finca Demo Norte",
        view_mode="Productor",
        rol="productor",
        cliente_id=1,
    ),
    "olivar": QuickLoginUser(
        username="productor.olivo@osmosense.local",
        password="cliente123",
        label="Olivar Demo Este",
        view_mode="Productor",
        rol="productor",
        cliente_id=2,
    ),
    "regional": QuickLoginUser(
        username="regional@osmosense.local",
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


def login_from_api(username: str, password: str) -> tuple[bool, str | None, bool]:
    login = username.strip().lower()
    if not login or not password:
        return False, "Ingrese email y contraseña.", True
    if not EMAIL_RE.match(login):
        return False, "Ingrese un email válido.", True

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


def login_quick_user(key: str) -> None:
    user = QUICK_LOGIN_USERS[key]
    ok, message, api_available = login_from_api(user.username, user.password)
    if ok:
        st.rerun()

    if not api_available:
        st.error("API/PostGIS no disponible. Los accesos rápidos usan login real.")
    else:
        st.error(message or "No se pudo iniciar sesión con el acceso rápido.")


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

        .quick-title {
            text-align: center;
            font-size: 1rem;
            font-weight: 600;
            margin-top: 1.25rem;
            margin-bottom: 0.25rem;
        }

        .quick-caption {
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

        .role-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.6rem 0 1.0rem 0;
        }

        .role-card {
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 8px;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.03);
        }

        .role-card strong {
            display: block;
            color: #12C2CF;
            margin-bottom: 0.25rem;
        }

        .role-card span {
            display: block;
            opacity: 0.72;
            font-size: 0.82rem;
            line-height: 1.25rem;
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
                    "Email",
                    placeholder="usuario@dominio.com",
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
                    message = "API/PostGIS no disponible. No se inició sesión."

                st.error(message or "Usuario o contraseña inválidos.")

            if quick_login_enabled():
                st.markdown(
                    """
                    <div class="quick-title">Accesos rápidos</div>
                    <div class="quick-caption">
                        Inician sesión contra la API real con usuarios operativos de desarrollo.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                c1, c2 = st.columns(2)

                with c1:
                    if st.button("Productor vid", width="stretch"):
                        login_quick_user("finca")

                    if st.button("Admin", width="stretch"):
                        login_quick_user("admin")

                with c2:
                    if st.button("Productor olivo", width="stretch"):
                        login_quick_user("olivar")

                    if st.button("Regional", width="stretch"):
                        login_quick_user("regional")

                st.markdown(
                    """
                    <div class="credentials-caption">
                        Usuarios PostGIS: admin@osmosense.local/admin123 · productor.vid@osmosense.local/cliente123 · productor.olivo@osmosense.local/cliente123 · regional@osmosense.local/regional123
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
    if source and source != "postgis":
        st.sidebar.info("Sesión local")
    st.sidebar.caption(f"Usuario: {label}")
    if role:
        st.sidebar.caption(f"Rol: {role}")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        logout()
        st.rerun()
