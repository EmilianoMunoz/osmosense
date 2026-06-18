from __future__ import annotations

import streamlit as st

from frontend.views.admin.available_parcels import render_available_parcels_tab
from frontend.views.admin.fields import render_parcelas_tab
from frontend.views.admin.users import render_users_tab


def render_admin_management_area() -> None:
    st.subheader("Gestión")
    st.caption("Mantenimiento operativo separado por usuarios y parcelas.")

    tab_usuarios, tab_parcelas = st.tabs(["Usuarios", "Parcelas"])

    with tab_usuarios:
        render_users_tab()

    with tab_parcelas:
        tab_asignacion, tab_nuevas = st.tabs(
            ["Asignar y desasignar", "Agregar al análisis"]
        )
        with tab_asignacion:
            render_parcelas_tab()
        with tab_nuevas:
            render_available_parcels_tab()
