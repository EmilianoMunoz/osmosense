# Frontend

Frontend Streamlit del sistema. La entrada se mantiene en la raíz:

```text
streamlit_app.py
```

Los módulos de UI viven en:

```text
frontend/
├── components/  # paneles, tablas, gráficos y detalle de parcela
├── views/       # vistas Admin, Cliente y Regional
├── auth.py      # login y sesión Streamlit
├── data.py      # consumo API y fallback local
├── logic.py     # reglas de presentación
└── map.py       # mapa Plotly
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

Si la API no está disponible, usa fallback local leyendo artefactos desde
`backend/data/`.

## Sesión

El login manual usa `POST /auth/login` cuando la API está disponible. Los
botones rápidos usan sesión demo y deben considerarse solo desarrollo.
