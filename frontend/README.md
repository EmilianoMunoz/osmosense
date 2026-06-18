# Frontend

Frontend Streamlit del sistema. La entrada se mantiene en la raíz:

```text
streamlit_app.py
```

Los módulos de UI viven en:

```text
frontend/
├── components/  # paneles, tablas, gráficos y detalle de parcela
├── views/       # vistas Admin, Productor y Regional
├── auth.py      # login y sesión Streamlit
├── data.py      # consumo API y fallback local
├── logic.py     # reglas de presentación
└── map.py       # mapa Plotly
```

La vista principal se organiza así:

```text
frontend/views/
├── dashboard.py          # orquestador de dashboard y análisis
├── dashboard_filters.py  # selección de rol/vista y filtros laterales
├── regional.py           # vista regional por UM
└── admin/
    ├── __init__.py           # pestañas de gestión admin
    ├── fields.py             # fincas/productores
    ├── users.py              # usuarios y accesos
    ├── available_parcels.py  # parcelas disponibles para activar
    └── status.py             # estado general y pipeline
```

## Ejecutar

Desde la raíz:

```bash
venv/bin/streamlit run streamlit_app.py
```

O con todo el stack:

```bash
./boot.sh start
```

## Datos

El frontend intenta consumir la API configurada en `API_BASE_URL`.

En desarrollo puede usar fallback local leyendo artefactos desde
`backend/data/` si `ENABLE_LOCAL_FALLBACK=true`.

En producción (`APP_ENV=production`) no usa fallback local: si la API/PostGIS no
responde, la vista muestra error.

## Sesión

El login manual usa `POST /auth/login` cuando la API está disponible. Los
botones rápidos también usan la API/PostGIS real, pero quedan disponibles solo
en desarrollo (`ENABLE_QUICK_LOGIN=true` y `APP_ENV` distinto de `production`).
