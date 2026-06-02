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
                <div class="login-title">Estrés hídrico San Rafael</div>
                <div class="login-subtitle">
                    Acceso al dashboard de parcelas de vid y olivo
                </div>
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
                user = DEMO_USERS.get(username.strip().lower())
                if user is not None and password == user.password:
                    login_as(user)
                    st.rerun()

                st.error("Usuario o contraseña inválidos.")

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
                if st.button("Cliente vid", width="stretch"):
                    login_as(DEMO_USERS["finca"])
                    st.rerun()

                if st.button("Admin", width="stretch"):
                    login_as(DEMO_USERS["admin"])
                    st.rerun()

            with c2:
                if st.button("Cliente olivo", width="stretch"):
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
    st.sidebar.header("Sesión")
    st.sidebar.caption(f"Conectado como: {label}")
    if st.sidebar.button("Cerrar sesión", width="stretch"):
        logout()
        st.rerun()
