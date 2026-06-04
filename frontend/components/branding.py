from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st


LOGO_PATH = Path("frontend/assets/logo.png")

BRAND_PRIMARY = "#0c818a"
BRAND_PRIMARY_HOVER = "#096d75"
BRAND_PRIMARY_ACTIVE = "#075b62"
BRAND_AQUA = "#12C2CF"


def logo_exists() -> bool:
    return LOGO_PATH.exists()


def apply_brand_theme() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --primary-color: {BRAND_PRIMARY};
        }}

        /* Botones generales */
        div.stButton > button,
        div[data-testid="stFormSubmitButton"] > button,
        button[kind="primary"],
        button[kind="secondary"] {{
            background: {BRAND_PRIMARY};
            border-color: {BRAND_PRIMARY};
            color: #ffffff;
            box-shadow: none;
        }}

        div.stButton > button:hover,
        div[data-testid="stFormSubmitButton"] > button:hover,
        button[kind="primary"]:hover,
        button[kind="secondary"]:hover {{
            background: {BRAND_PRIMARY_HOVER};
            border-color: {BRAND_PRIMARY_HOVER};
            color: #ffffff;
        }}

        div.stButton > button:active,
        div[data-testid="stFormSubmitButton"] > button:active,
        button[kind="primary"]:active,
        button[kind="secondary"]:active {{
            background: {BRAND_PRIMARY_ACTIVE};
            border-color: {BRAND_PRIMARY_ACTIVE};
            color: #ffffff;
        }}

        div.stButton > button:focus,
        div[data-testid="stFormSubmitButton"] > button:focus,
        button[kind="primary"]:focus,
        button[kind="secondary"]:focus {{
            border-color: {BRAND_PRIMARY_ACTIVE};
            box-shadow: 0 0 0 0.2rem rgba(12, 129, 138, 0.24);
            color: #ffffff;
        }}

        div.stButton > button:disabled,
        div[data-testid="stFormSubmitButton"] > button:disabled {{
            background: rgba(12, 129, 138, 0.34);
            border-color: rgba(12, 129, 138, 0.18);
            color: rgba(255, 255, 255, 0.74);
        }}

        /* Multiselect: tags seleccionados */
        div[data-testid="stMultiSelect"] div[data-baseweb="tag"],
        div[data-testid="stMultiSelect"] span[data-baseweb="tag"],
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] {{
            background: {BRAND_PRIMARY} !important;
            background-color: {BRAND_PRIMARY} !important;
            border-color: {BRAND_PRIMARY} !important;
            color: #ffffff !important;
        }}

        div[data-testid="stMultiSelect"] div[data-baseweb="tag"] *,
        div[data-testid="stMultiSelect"] span[data-baseweb="tag"] *,
        div[data-testid="stMultiSelect"] [data-baseweb="tag"] * {{
            color: #ffffff !important;
            fill: #ffffff !important;
        }}

        div[data-testid="stMultiSelect"] span[aria-label],
        div[data-testid="stMultiSelect"] div[aria-label] {{
            background-color: {BRAND_PRIMARY} !important;
            border-color: {BRAND_PRIMARY} !important;
            color: #ffffff !important;
        }}

        div[data-testid="stMultiSelect"] span[aria-label] *,
        div[data-testid="stMultiSelect"] div[aria-label] * {{
            color: #ffffff !important;
            fill: #ffffff !important;
        }}

        div[data-testid="stMultiSelect"] [data-baseweb="tag"] button {{
            background-color: transparent !important;
            color: #ffffff !important;
        }}

        div[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {{
            color: #ffffff !important;
            fill: #ffffff !important;
        }}

        /* Radio buttons: solo cambia el circulito */
        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:first-child {{
            background-color: {BRAND_PRIMARY} !important;
            border-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:first-child div {{
            background-color: #ffffff !important;
        }}

        div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{
            border-color: rgba(255, 255, 255, 0.45) !important;
        }}

        div[data-testid="stRadio"] label[data-baseweb="radio"]:hover > div:first-child {{
            border-color: {BRAND_PRIMARY} !important;
        }}

        /* Checkboxes seleccionados */
        div[data-testid="stCheckbox"] label:has(input:checked) span {{
            background-color: {BRAND_PRIMARY} !important;
            border-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stCheckbox"] label:has(input:checked) svg {{
            fill: #ffffff !important;
            color: #ffffff !important;
        }}

        /* Tabs: texto y línea inferior seleccionada */
        div[data-testid="stTabs"] button[aria-selected="true"] {{
            color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stTabs"] button[aria-selected="true"] p {{
            color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
            background-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stTabs"] [data-baseweb="tab-border"] {{
            background-color: rgba(255, 255, 255, 0.16) !important;
        }}

        div[data-testid="stTabs"] button:hover {{
            color: {BRAND_AQUA} !important;
        }}

        div[data-testid="stTabs"] button:hover p {{
            color: {BRAND_AQUA} !important;
        }}

        /* Selectbox / input focus */
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="input"] > div:focus-within {{
            border-color: {BRAND_PRIMARY} !important;
            box-shadow: 0 0 0 0.2rem rgba(12, 129, 138, 0.18) !important;
        }}

        /* Slider: línea activa en celeste y manijas blancas */
        div[data-testid="stSlider"] [data-baseweb="slider"] div {{
            border-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {{
            background-color: #ffffff !important;
            border-color: #ffffff !important;
            box-shadow: 0 0 0 2px {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"]:focus {{
            box-shadow: 0 0 0 3px rgba(12, 129, 138, 0.35) !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] div[style*="background"] {{
            background-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] div[style*="background-color"] {{
            background-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] div[style*="rgb(255, 75, 75)"] {{
            background-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] div[style*="#ff4b4b"] {{
            background-color: {BRAND_PRIMARY} !important;
        }}

        div[data-testid="stSlider"] [data-baseweb="slider"] span {{
            color: {BRAND_PRIMARY} !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_logo(width: int = 260) -> None:
    if logo_exists():
        st.image(str(LOGO_PATH), width=width)


def render_sidebar_logo() -> None:
    if logo_exists():
        st.sidebar.image(str(LOGO_PATH), width=210)


def render_loading_logo(message: str):
    placeholder = st.empty()
    with placeholder.container():
        left, center, right = st.columns([1, 1.1, 1])
        with center:
            render_logo(width=240)
            st.caption(message)
    return placeholder


@st.cache_data(show_spinner=False)
def _logo_data_uri() -> str | None:
    if not logo_exists():
        return None

    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_fullscreen_loader(message: str):
    placeholder = st.empty()
    logo_uri = _logo_data_uri()

    logo_html = (
        f'<img class="app-loader-logo" src="{logo_uri}" alt="OSMOSENSE" />'
        if logo_uri
        else '<div class="app-loader-title">OSMOSENSE</div>'
    )

    placeholder.markdown(
        f"""
        <style>
        .app-loader-overlay {{
            position: fixed;
            inset: 0;
            z-index: 999999;
            display: flex;
            align-items: center;
            justify-content: center;
            background:
                radial-gradient(circle at 50% 42%, rgba(12, 129, 138, 0.24), transparent 34%),
                rgba(7, 15, 20, 0.96);
        }}

        .app-loader-content {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
            text-align: center;
        }}

        .app-loader-logo {{
            width: min(420px, 72vw);
            height: auto;
            border-radius: 10px;
            box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
        }}

        .app-loader-title {{
            color: white;
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: 0;
        }}

        .app-loader-message {{
            color: rgba(255, 255, 255, 0.82);
            font-size: 0.95rem;
        }}

        .app-loader-bar {{
            width: min(300px, 64vw);
            height: 3px;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.16);
        }}

        .app-loader-bar::after {{
            content: "";
            display: block;
            width: 42%;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, {BRAND_PRIMARY}, {BRAND_AQUA});
            animation: app-loader-slide 1.05s ease-in-out infinite;
        }}

        @keyframes app-loader-slide {{
            0% {{ transform: translateX(-110%); }}
            100% {{ transform: translateX(250%); }}
        }}
        </style>

        <div class="app-loader-overlay">
            <div class="app-loader-content">
                {logo_html}
                <div class="app-loader-message">{message}</div>
                <div class="app-loader-bar"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return placeholder