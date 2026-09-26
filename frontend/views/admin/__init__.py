from __future__ import annotations

import streamlit as st

from frontend.views.admin.available_parcels import render_available_parcels_tab
from frontend.views.admin.fields import render_parcelas_tab
from frontend.views.admin.users import render_users_tab


MANAGEMENT_SECTIONS = ["Usuarios", "Asignaciones", "Incorporar al análisis"]


def render_admin_management_area() -> None:
    st.subheader("Gestión")
    st.caption("Usuarios, relaciones productor-parcela e incorporación al análisis.")

    active_section = st.segmented_control(
        "Sección de gestión",
        MANAGEMENT_SECTIONS,
        default="Usuarios",
        label_visibility="collapsed",
        key="admin_management_section",
        width="stretch",
    )
    active_section = active_section or "Usuarios"

    if active_section == "Usuarios":
        render_users_tab()
        return

    if active_section == "Asignaciones":
        render_parcelas_tab()
        return

    render_available_parcels_tab()
