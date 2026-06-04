from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from frontend.auth import is_authenticated, render_auth_sidebar, render_login
from frontend.data import (
    activar_parcela_disponible,
    create_usuario,
    features_to_frame,
    filtered_geojson,
    load_admin_parcelas_disponibles,
    load_admin_usuarios,
    load_api_health,
    load_clientes,
    load_geojson,
    load_pipeline_state,
    update_usuario,
)
from frontend.logic import add_dynamic_priority, cliente_changed, priority_options, review_priority
from frontend.map import bbox_center_zoom, render_map
from frontend.components.branding import apply_brand_theme, render_fullscreen_loader
from frontend.components.charts import render_distribution, render_prediction_panel
from frontend.components.client_overview import render_client_field_overview, render_client_field_status
from frontend.components.metrics import render_client_metrics, render_metrics
from frontend.components.parcel_detail import render_client_parcel_dialog, render_parcel_dialog
from frontend.components.tables import (
    build_table_dataframe,
    render_cultivo_summary,
    render_review_cases,
    render_top_criticas,
)
from frontend.views.regional import render_regional_view


def select_view_mode() -> tuple[str, bool, bool]:
    st.sidebar.header("Acceso")
    current_view = st.session_state.get("view_mode", "Productor")
    rol = st.session_state.get("auth_rol")
    if rol == "admin":
        options = ["Admin", "Regional", "Productor"]
    elif rol == "regional":
        options = ["Regional"]
    elif rol == "productor":
        options = ["Productor"]
    else:
        options = ["Productor", "Regional", "Admin"]

    view_mode = st.sidebar.radio(
        "Vista",
        options,
        horizontal=True,
        index=options.index(current_view) if current_view in options else 0,
    )
    st.session_state["view_mode"] = view_mode
    return view_mode, view_mode == "Admin", view_mode == "Regional"


def select_cliente(admin_mode: bool) -> tuple[int | None, str | None]:
    if admin_mode or st.session_state.get("view_mode") == "Regional":
        return None, None

    auth_cliente_id = st.session_state.get("auth_cliente_id")
    if st.session_state.get("auth_rol") == "productor" and auth_cliente_id is not None:
        cliente_id = int(auth_cliente_id)
        st.sidebar.caption(f"Productor asignado: {cliente_id}")
        return cliente_id, f"Productor {cliente_id}"

    clientes_data = load_clientes()
    clientes_items = clientes_data.get("items", [])
    if not clientes_items:
        st.info(
            "No hay productores cargados. Crear backend/data/clientes/clientes.csv y "
            "backend/data/clientes/cliente_parcela.csv para habilitar la vista productor."
        )
        st.stop()

    labels = {
        int(item["cliente_id"]): (
            f"{item['nombre']} · {item['tipo']} · "
            f"{int(item.get('parcelas_asignadas', 0))} parcelas"
        )
        for item in clientes_items
    }

    cliente_ids = list(labels)
    cliente_index = (
        cliente_ids.index(int(auth_cliente_id))
        if auth_cliente_id is not None and int(auth_cliente_id) in cliente_ids
        else 0
    )

    selected_cliente_id = st.sidebar.selectbox(
        "Productor",
        cliente_ids,
        index=cliente_index,
        format_func=lambda cid: labels[int(cid)],
    )

    cliente_changed(int(selected_cliente_id))
    selected_cliente_name = labels[int(selected_cliente_id)]
    st.caption(f"Vista productor · {selected_cliente_name}")
    return int(selected_cliente_id), selected_cliente_name


def select_priority_mode(admin_mode: bool) -> str:
    if admin_mode:
        return st.sidebar.radio(
            "Categorización",
            ["Umbrales fijos", "Relativa por percentiles"],
            help=(
                "Umbrales fijos usa las categorías guardadas por el ranking. "
                "Relativa por percentiles reparte las parcelas evaluadas según su posición dentro de la fecha visible."
            ),
        )

    client_priority_mode = st.sidebar.radio(
        "Criterio de prioridad",
        ["General", "Dentro de mi campo"],
        index=1,
        help=(
            "General usa la prioridad del modelo. Dentro de mi campo compara "
            "solo las parcelas visibles del cliente."
        ),
    )

    return "Relativa por percentiles" if client_priority_mode == "Dentro de mi campo" else "Umbrales fijos"


def apply_sidebar_filters(
    df: pd.DataFrame,
    admin_mode: bool,
    priority_mode: str = "",
) -> tuple[pd.DataFrame, str]:
    color_options = [
        option
        for option in ["prioridad_visual", "confianza_lectura"]
        if option in df.columns
    ]

    if not admin_mode:
        color_options = [option for option in color_options if option == "prioridad_visual"]

    color_by = st.sidebar.selectbox("Color del mapa", color_options, index=0)

    st.sidebar.header("Filtros operativos" if admin_mode else "Filtros")

    cultivos = st.sidebar.multiselect(
        "Cultivo",
        options=sorted(df["cultivo"].dropna().unique()),
        default=sorted(df["cultivo"].dropna().unique()),
    )

    priority_values = priority_options(df)

    if admin_mode:
        show_all_priorities = st.sidebar.checkbox(
            "Mostrar todas las prioridades",
            value=False,
            help=(
                "Desactivado carga solo alta/crítica por defecto para acelerar "
                "el mapa operativo."
            ),
        )
        default_priorities = (
            priority_values
            if show_all_priorities
            else [p for p in ["critica", "alta"] if p in priority_values]
        )
    else:
        default_priorities = priority_values

    priority_filter_key = (
        f"prioridad_filter_"
        f"{st.session_state.get('view_mode', 'desconocida')}_"
        f"{priority_mode}"
    )

    prioridades = st.sidebar.multiselect(
        "Prioridad",
        options=priority_values,
        default=default_priorities,
        key=priority_filter_key,
    )

    if admin_mode and "confianza_lectura" in df.columns:
        confianza = st.sidebar.multiselect(
            "Confianza",
            options=sorted(df["confianza_lectura"].dropna().unique()),
            default=sorted(df["confianza_lectura"].dropna().unique()),
        )
    else:
        confianza = []

    max_rank_value = df["ranking_global"].max()

    if admin_mode and pd.notna(max_rank_value) and int(max_rank_value) >= 1:
        max_rank = int(max_rank_value)
        rank_range = st.sidebar.slider("Ranking global", 1, max_rank, (1, max_rank))
    else:
        rank_range = (1, 1)

    review_only = False

    if admin_mode:
        st.sidebar.header("Revisión técnica")
        review_only = st.sidebar.checkbox("Solo casos a revisar", value=False)

    filtered = df[df["cultivo"].isin(cultivos)].copy()

    if not review_only:
        filtered = filtered[filtered["prioridad_visual"].isin(prioridades)].copy()

    if admin_mode:
        filtered = filtered[
            filtered["ranking_global"].between(rank_range[0], rank_range[1])
            | filtered["ranking_global"].isna()
        ].copy()

    if "confianza_lectura" in filtered.columns and confianza:
        filtered = filtered[filtered["confianza_lectura"].isin(confianza)].copy()

    if review_only:
        filtered = filtered[filtered.apply(review_priority, axis=1) < 99].copy()

    return filtered, color_by

def sync_geojson_properties_from_df(data: dict, df: pd.DataFrame) -> dict:
    synced = data.copy()
    features = []

    if df.empty or "parcela_id" not in df.columns:
        synced["features"] = []
        return synced

    df_by_id = df.set_index(df["parcela_id"].astype(int))

    for feature in data.get("features", []):
        props = feature.get("properties", {})
        parcela_id = props.get("parcela_id")

        if parcela_id is None:
            continue

        try:
            parcela_id_int = int(parcela_id)
        except (TypeError, ValueError):
            continue

        if parcela_id_int not in df_by_id.index:
            continue

        row = df_by_id.loc[parcela_id_int]

        updated_feature = feature.copy()
        updated_props = props.copy()

        for col in df.columns:
            value = row[col]

            if pd.isna(value):
                updated_props[col] = None
            else:
                updated_props[col] = value

        updated_feature["properties"] = updated_props
        features.append(updated_feature)

    synced["features"] = features
    return synced


def _format_state_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "sí" if value else "no"
    return str(value)


def _format_datetime_value(value: object) -> str:
    if value is None or value == "":
        return "-"
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is not None:
            dt = dt.astimezone()
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(value)


def _human_pipeline_reason(reason: object) -> str:
    reasons = {
        "sin_fecha_nueva": "Sin imagen Sentinel nueva",
        "error": "Error de ejecución",
        None: "Sin observaciones",
        "": "Sin observaciones",
    }
    return reasons.get(reason, str(reason))


def _human_source(source: object) -> str:
    sources = {
        "postgis": "PostGIS",
        "csv": "CSV vía API",
        "local": "Fallback local",
        "api_unavailable": "API no disponible",
    }
    return sources.get(source, str(source or "desconocida"))


def render_runtime_notices(data: dict) -> None:
    health = load_api_health()
    source = data.get("source")

    if not health.get("available"):
        st.sidebar.error("API no disponible. Se está usando fallback local si existe.")
        return

    st.sidebar.success("API disponible")

    if source == "postgis":
        st.sidebar.success("Datos operativos desde PostGIS")
    elif source == "csv":
        st.sidebar.warning("API disponible, pero el ranking viene de CSV.")
    elif source == "local":
        st.sidebar.warning("Usando fallback local; revisar API/autenticación.")
    elif source == "api_unavailable":
        st.sidebar.error("No se pudo obtener datos desde la API.")


def render_pipeline_status() -> None:
    data = load_pipeline_state()
    state = data.get("state", {}) if isinstance(data, dict) else {}
    summary = data.get("ranking_summary", {}) if isinstance(data, dict) else {}

    st.subheader("Estado operativo del pipeline")

    if not data.get("exists"):
        if data.get("source") == "api_unavailable":
            st.error("No se pudo consultar el estado del pipeline porque la API no respondió.")
        else:
            st.info("Todavía no hay estado persistido del pipeline.")
        return

    skipped = bool(state.get("skipped", False))
    failed = bool(state.get("failed", False))
    if failed:
        status_label = "Error"
        st.error("La última ejecución del pipeline terminó con error.")
    elif skipped:
        status_label = "Sin actualización"
        st.info("La última ejecución no recalculó ranking porque no encontró una imagen válida nueva.")
    else:
        status_label = "Actualizado"
        st.success("La última ejecución generó o cargó ranking operativo.")

    reason = state.get("reason")

    cols = st.columns(5)
    cols[0].metric("Estado última corrida", status_label)
    cols[1].metric("Última ejecución", _format_datetime_value(state.get("last_run_utc")))
    cols[2].metric(
        "Última imagen válida",
        _format_state_value(
            state.get("fecha_dataset")
            or state.get("fecha_rankeada")
            or summary.get("fecha_ranking")
        ),
    )
    cols[3].metric(
        "PostGIS cargado",
        _format_state_value(state.get("postgis_loaded")),
    )
    cols[4].metric("Resultado", _human_pipeline_reason(reason))

    detail_cols = st.columns(4)
    detail_cols[0].metric(
        "Parcelas ranking",
        f"{int(summary.get('rows', state.get('parcelas', 0))):,}".replace(",", "."),
    )
    detail_cols[1].metric(
        "Fecha antes",
        _format_state_value(state.get("fecha_dataset_antes")),
    )
    detail_cols[2].metric(
        "Fecha después",
        _format_state_value(state.get("fecha_dataset_despues")),
    )
    detail_cols[3].metric("Modo", _format_state_value(state.get("mode")))

    if summary.get("exists"):
        st.caption(
            "Ranking latest: "
            f"{int(summary.get('rows', 0)):,} filas · ".replace(",", ".")
            + f"{int(summary.get('evaluadas', 0)):,} evaluadas · ".replace(",", ".")
            + f"{int(summary.get('sin_ranking', 0)):,} sin ranking".replace(",", ".")
        )

    if state.get("log_path"):
        st.caption(f"Log: {state['log_path']}")


def render_admin_status_tab(df: pd.DataFrame, filtered: pd.DataFrame) -> None:
    st.subheader("Estado general")
    render_metrics(df, admin_mode=True)

    st.divider()
    render_pipeline_status()

    st.divider()
    st.subheader("Vista activa")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Parcelas visibles", f"{len(filtered):,}".replace(",", "."))

    col2.metric(
        "Evaluadas visibles",
        f"{int(filtered['ranking_global'].notna().sum()):,}".replace(",", "."),
    )

    col3.metric(
        "Alta/crítica visibles",
        int(filtered["prioridad_visual"].isin(["alta", "critica"]).sum()),
    )

    col4.metric(
        "Sin ranking visibles",
        int((filtered["prioridad_visual"] == "sin ranking").sum()),
    )

    left, right = st.columns([1.1, 1.0])

    with left:
        st.subheader("Distribución por prioridad")
        priority_summary = (
            df.groupby("prioridad_visual", dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
            .rename(columns={"prioridad_visual": "Prioridad", "parcelas": "Parcelas"})
        )
        st.dataframe(priority_summary, hide_index=True, width="stretch")

    with right:
        st.subheader("Resumen por cultivo")
        render_cultivo_summary(df)


def render_coverage_tab(df: pd.DataFrame) -> None:
    st.subheader("Cobertura")

    if df.empty:
        st.info("No hay datos para mostrar.")
        return

    coverage = (
        df.groupby("cultivo", dropna=False)
        .agg(
            parcelas=("parcela_id", "count"),
            evaluadas=("ranking_global", lambda s: int(s.notna().sum())),
            sin_ranking=("ranking_global", lambda s: int(s.isna().sum())),
        )
        .reset_index()
    )

    coverage["cobertura_%"] = (coverage["evaluadas"] / coverage["parcelas"] * 100).round(2)

    st.dataframe(coverage, hide_index=True, width="stretch")

    if "confianza_lectura" in df.columns:
        st.subheader("Confianza de lectura")
        confidence = (
            df.groupby(["cultivo", "confianza_lectura"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        st.dataframe(confidence, hide_index=True, width="stretch")

    if "estado_evaluacion" in df.columns:
        st.subheader("Estado de evaluación")
        estado = (
            df.groupby(["cultivo", "estado_evaluacion"], dropna=False)
            .agg(parcelas=("parcela_id", "count"))
            .reset_index()
        )
        st.dataframe(estado, hide_index=True, width="stretch")

    missing = df[df["ranking_global"].isna()].copy()

    if not missing.empty:
        st.subheader("Parcelas sin ranking")
        cols = [
            "parcela_id",
            "cultivo",
            "estado_evaluacion",
            "estado_cobertura",
            "area_m2",
            "confianza_lectura",
        ]
        cols = [col for col in cols if col in missing.columns]

        st.dataframe(
            missing.sort_values(["cultivo", "parcela_id"])[cols].head(200),
            hide_index=True,
            width="stretch",
        )

        if len(missing) > 200:
            st.caption(f"Mostrando 200 de {len(missing):,} parcelas sin ranking.".replace(",", "."))


def render_map_tab(
    data: dict,
    filtered: pd.DataFrame,
    filtered_data: dict,
    color_by: str,
    admin_mode: bool,
    selected_cliente_id: int | None,
    priority_mode: str = "",
) -> None:
    left, right = st.columns([2.2, 1.0])

    with left:
        if not admin_mode and selected_cliente_id is not None:
            map_center, map_zoom = bbox_center_zoom(filtered_data)
        else:
            map_center, map_zoom = None, 8.3

        selected_id = st.session_state.get("selected_parcela_id")

        clicked_id = render_map(
            filtered_data,
            filtered,
            color_by=color_by,
            center=map_center,
            zoom=map_zoom,
            selected_id=selected_id,
            admin_mode=admin_mode,
            risk_animation=not admin_mode,
            relative_animation_categories=priority_mode == "Relativa por percentiles",
        )

        if clicked_id is not None:
            st.session_state["selected_parcela_id"] = clicked_id
            row = filtered[filtered["parcela_id"] == clicked_id]

            if not row.empty and hasattr(st, "dialog"):
                if admin_mode:
                    render_parcel_dialog(row.iloc[0].to_dict())
                else:
                    render_client_parcel_dialog(row.iloc[0].to_dict())

    with right:
        st.subheader("Parcela")
        selected_id = st.session_state.get("selected_parcela_id")
        render_prediction_panel(filtered, selected_id=selected_id, admin_mode=admin_mode)

        st.subheader("Distribución")
        render_distribution(filtered)

def render_review_tab(filtered: pd.DataFrame) -> None:
    st.subheader("Casos a revisar")
    render_review_cases(filtered)

    lower_left, lower_right = st.columns([1.15, 1.0])

    with lower_left:
        st.subheader("Top prioridad")
        render_top_criticas(filtered, limit=15)

    with lower_right:
        st.subheader("Resumen por cultivo")
        render_cultivo_summary(filtered)


def render_data_tab(filtered: pd.DataFrame, admin_mode: bool) -> None:
    st.subheader("Tabla de ranking" if admin_mode else "Mis parcelas")

    table_df = build_table_dataframe(filtered, admin_mode)

    if table_df.empty:
        st.info("No hay columnas disponibles para mostrar.")
        return

    st.dataframe(table_df, hide_index=True, width="stretch")


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
        st.subheader("Activación")

        selected_id = st.session_state.get("selected_disponible_id")

        if selected_id is None:
            selected_id = int(df.iloc[0]["parcela_id"])
            st.session_state["selected_disponible_id"] = selected_id

        row = df[df["parcela_id"].astype(int) == int(selected_id)]

        if row.empty:
            st.info("Seleccioná una parcela disponible en el mapa.")
            return

        item = row.iloc[0]

        st.write(f"Parcela {int(item['parcela_id'])}")
        st.write(f"Cultivo original: {item.get('cultivo_original', '-')}")
        st.write(f"Área: {item.get('area_m2', 0):.0f} m²" if pd.notna(item.get("area_m2")) else "Área: -")

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

        with st.form("activar_parcela_disponible"):
            cultivo_destino = st.radio("Nuevo cultivo operativo", ["vid", "olivo"], horizontal=True)

            cliente_id = st.selectbox(
                "Asignar productor",
                cliente_options,
                format_func=lambda value: cliente_labels.get(value, str(value)),
            )

            etiqueta = st.text_input("Etiqueta interna", value="")
            submitted = st.form_submit_button("Activar parcela")

        if submitted:
            try:
                activar_parcela_disponible(
                    parcela_id=int(item["parcela_id"]),
                    cultivo_oficial=cultivo_destino,
                    cliente_id=cliente_id,
                    etiqueta=etiqueta or None,
                )
            except Exception as exc:
                st.error(f"No se pudo activar la parcela: {exc}")
            else:
                st.success("Parcela activada. Entrará al universo objetivo PostGIS.")
                st.session_state.pop("selected_disponible_id", None)
                st.rerun()


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


def render_users_tab() -> None:
    st.subheader("Usuarios")
    st.caption("Alta y mantenimiento de accesos. Roles operativos: admin, regional y productor.")

    data = load_admin_usuarios(limit=5000)
    users = pd.DataFrame(data.get("items", []))

    st.caption(f"Fuente: {data.get('source', 'desconocida')} · {len(users)} usuarios")

    if not users.empty:
        visible_cols = [
            "usuario_id",
            "email",
            "nombre",
            "rol",
            "productor_nombre",
            "cliente_id",
            "activo",
            "last_login_at",
        ]
        visible_cols = [col for col in visible_cols if col in users.columns]
        st.dataframe(users[visible_cols], hide_index=True, width="stretch")
    else:
        st.info("No hay usuarios cargados o la API no está disponible.")

    productor_options, productor_labels = _productor_options()

    col_create, col_edit = st.columns(2)

    with col_create:
        st.subheader("Nuevo usuario")

        with st.form("create_usuario_form"):
            email = st.text_input("Usuario/email", key="new_user_email")
            nombre = st.text_input("Nombre", key="new_user_nombre")
            rol = st.selectbox("Rol", ["productor", "regional", "admin"], key="new_user_rol")

            cliente_id = None
            if rol == "productor":
                cliente_id = st.selectbox(
                    "Productor/campo asociado",
                    productor_options,
                    format_func=lambda value: productor_labels.get(value, str(value)),
                    key="new_user_cliente_id",
                )

            password = st.text_input("Contraseña inicial", type="password", key="new_user_password")
            activo = st.checkbox("Activo", value=True, key="new_user_activo")

            submitted = st.form_submit_button("Crear usuario")

        if submitted:
            try:
                payload = {
                    "email": email,
                    "nombre": nombre or None,
                    "rol": rol,
                    "cliente_id": cliente_id,
                    "password": password,
                    "activo": activo,
                }
                create_usuario(payload)
            except Exception as exc:
                st.error(f"No se pudo crear el usuario: {exc}")
            else:
                st.success("Usuario creado.")
                st.rerun()

    with col_edit:
        st.subheader("Editar usuario")

        if users.empty:
            st.info("No hay usuarios para editar.")
            return

        user_ids = [int(value) for value in users["usuario_id"].dropna().tolist()]

        selected_user_id = st.selectbox(
            "Usuario",
            user_ids,
            format_func=lambda uid: str(
                users.loc[users["usuario_id"].astype(int) == int(uid), "email"].iloc[0]
            ),
            key="edit_user_id",
        )

        selected = users[users["usuario_id"].astype(int) == int(selected_user_id)].iloc[0]

        current_rol = (
            selected.get("rol")
            if selected.get("rol") in ["productor", "regional", "admin"]
            else "productor"
        )

        with st.form("edit_usuario_form"):
            email = st.text_input(
                "Usuario/email",
                value=str(selected.get("email") or ""),
                key="edit_user_email",
            )

            nombre = st.text_input(
                "Nombre",
                value=str(selected.get("nombre") or ""),
                key="edit_user_nombre",
            )

            rol = st.selectbox(
                "Rol",
                ["productor", "regional", "admin"],
                index=["productor", "regional", "admin"].index(current_rol),
                key="edit_user_rol",
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
                    "Productor/campo asociado",
                    productor_options,
                    index=index,
                    format_func=lambda value: productor_labels.get(value, str(value)),
                    key="edit_user_cliente_id",
                )

            password = st.text_input(
                "Nueva contraseña",
                type="password",
                help="Dejar vacío para conservar la actual.",
                key="edit_user_password",
            )

            activo = st.checkbox(
                "Activo",
                value=bool(selected.get("activo", True)),
                key="edit_user_activo",
            )

            submitted = st.form_submit_button("Guardar cambios")

        if submitted:
            try:
                payload = {
                    "email": email,
                    "nombre": nombre or None,
                    "rol": rol,
                    "cliente_id": cliente_id,
                    "activo": activo,
                }

                if password:
                    payload["password"] = password

                update_usuario(int(selected_user_id), payload)
            except Exception as exc:
                st.error(f"No se pudo actualizar el usuario: {exc}")
            else:
                st.success("Usuario actualizado.")
                st.rerun()


def render_admin_management_area() -> None:
    tab_usuarios, tab_parcelas = st.tabs(["Usuarios", "Parcelas y asignación"])

    with tab_usuarios:
        render_users_tab()

    with tab_parcelas:
        render_available_parcels_tab()


def render_admin_analysis_area(
    data: dict,
    df: pd.DataFrame,
    filtered: pd.DataFrame,
    filtered_data: dict,
    color_by: str,
    selected_cliente_id: int | None,
    priority_mode: str,
) -> None:
    tab_estado, tab_mapa, tab_revision, tab_cobertura, tab_datos = st.tabs(
        ["Estado", "Mapa operativo", "Revisión técnica", "Cobertura", "Datos"]
    )

    with tab_estado:
        render_admin_status_tab(df, filtered)

    with tab_mapa:
        render_map_tab(
            data=data,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            admin_mode=True,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )

    with tab_revision:
        render_review_tab(filtered)

    with tab_cobertura:
        render_coverage_tab(df)

    with tab_datos:
        render_data_tab(filtered, admin_mode=True)


def render_dashboard() -> None:
    st.set_page_config(
        page_title="Ranking hídrico San Rafael",
        page_icon=None,
        layout="wide",
    )
    apply_brand_theme()

    if not is_authenticated():
        render_login()
        st.stop()

    render_auth_sidebar()

    view_mode, admin_mode, regional_mode = select_view_mode()

    if regional_mode:
        render_regional_view()
        return

    admin_area = "Análisis"
    if admin_mode:
        header_left, header_right = st.columns([0.68, 0.32])
        with header_left:
            st.title("Ranking hídrico de parcelas")
            st.caption("San Rafael, Mendoza · Vid y olivo")
        with header_right:
            st.caption("Área admin")
            admin_area = st.radio(
                "Área admin",
                ["Análisis", "Gestión"],
                horizontal=True,
                label_visibility="collapsed",
                key="admin_area",
            )
    else:
        st.title("Ranking hídrico de parcelas")
        st.caption("San Rafael, Mendoza · Vid y olivo")

    if admin_mode and admin_area == "Gestión":
        render_admin_management_area()
        return

    selected_cliente_id, _ = select_cliente(admin_mode)

    loading_message = (
        "Cargando ranking operativo..."
        if admin_mode
        else "Cargando parcelas del productor..."
    )
    loading = render_fullscreen_loader(loading_message)
    with st.spinner(loading_message):
        data = load_geojson(selected_cliente_id)
        df = features_to_frame(data)
    loading.empty()

    if df.empty:
        st.error("No se pudo cargar el ranking.")
        return

    st.sidebar.header("Vista")
    st.sidebar.caption(f"Fuente: {_human_source(data.get('source'))}")
    render_runtime_notices(data)

    priority_mode = select_priority_mode(admin_mode)

    priority_context = f"{view_mode}:{selected_cliente_id}:{priority_mode}"
    if st.session_state.get("prev_priority_context") != priority_context:
        st.session_state.pop("selected_parcela_id", None)
    st.session_state["prev_priority_context"] = priority_context

    df = add_dynamic_priority(df, priority_mode)

    filtered, color_by = apply_sidebar_filters(
        df=df,
        admin_mode=admin_mode,
        priority_mode=priority_mode,
    )

    filtered_data = sync_geojson_properties_from_df(data, filtered)
    if admin_mode:
        render_admin_analysis_area(
            data=data,
            df=df,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )
        return

    render_client_metrics(filtered)
    render_client_field_status(filtered)
    tab_resumen, tab_mapa, tab_datos = st.tabs(["Resumen", "Campo", "Parcelas"])
    with tab_resumen:
        render_client_field_overview(filtered)

    with tab_mapa:
        render_map_tab(
            data=data,
            filtered=filtered,
            filtered_data=filtered_data,
            color_by=color_by,
            admin_mode=admin_mode,
            selected_cliente_id=selected_cliente_id,
            priority_mode=priority_mode,
        )

    with tab_datos:
        render_data_tab(filtered, admin_mode)
