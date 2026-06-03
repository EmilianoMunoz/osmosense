# Dashboard Streamlit

El dashboard muestra el ranking hídrico en un mapa interactivo con filtros,
métricas y predicción por parcela.

## Ejecutar

Instalar dependencias si todavía no están en el entorno:

```bash
venv/bin/pip install -r requirements.txt
```

Levantar el dashboard:

```bash
venv/bin/streamlit run streamlit_app.py
```

Levantar API, PostGIS y dashboard juntos:

```bash
./boot.sh start
```

Primera carga completa:

```bash
./boot.sh start --setup --all-parcelas --smoke
```

## Acceso

El dashboard abre primero una pantalla de login. Si la API está disponible, las
credenciales se validan contra la tabla `usuarios` de PostGIS vía
`POST /auth/login`. Si la API no está disponible, se conserva fallback demo para
desarrollo.

Usuarios demo:

| Usuario    | Contraseña    | Vista         |
|------------|---------------|---------------|
| `admin`    | `admin123`    | Admin         |
| `finca`    | `cliente123`  | Productor vid |
| `olivar`   | `cliente123`  | Productor olivo |
| `regional` | `regional123` | Regional      |

La pantalla conserva accesos rápidos para desarrollo:

```text
Productor vid
Productor olivo
Admin
Regional
```

## Organización del frontend

El entrypoint sigue siendo:

```text
streamlit_app.py
```

Se inició la separación del frontend en:

```text
frontend/
frontend/auth.py
frontend/constants.py
frontend/data.py
frontend/logic.py
frontend/map.py
frontend/panels.py
frontend/table_config.py
frontend/components/charts.py
frontend/components/client_overview.py
frontend/components/metrics.py
frontend/components/parcel_detail.py
frontend/components/tables.py
frontend/views/dashboard.py
frontend/views/regional.py
```

Responsabilidades:

| Archivo                                  | Responsabilidad                                   |
|------------------------------------------|---------------------------------------------------|
| `streamlit_app.py`                       | Entrypoint mínimo.                                |
| `frontend/auth.py`                       | Login, logout y sesión demo.                      |
| `frontend/data.py`                       | Carga desde API/local y normalización a DataFrame.|
| `frontend/logic.py`                      | Prioridad dinámica, selección de valores visibles y reglas puras. |
| `frontend/map.py`                        | Mapa, zoom, hover y selección de parcela.         |
| `frontend/table_config.py`               | Columnas visibles, labels y restricciones por rol.|
| `frontend/components/client_overview.py` | Estado general del campo en vista cliente.        |
| `frontend/components/metrics.py`         | Métricas resumen.                                 |
| `frontend/components/parcel_detail.py`   | Detalle y pop-up de parcela.                      |
| `frontend/components/tables.py`          | Tablas y resúmenes tabulares.                     |
| `frontend/components/charts.py`          | Gráficos de proyección y distribución.            |
| `frontend/panels.py`                     | Fachada de compatibilidad para componentes.       |
| `frontend/views/dashboard.py`            | Orquestación de la vista Streamlit.               |
| `frontend/views/regional.py`             | Vista de zonificación DGI recortada a San Rafael. |

El objetivo es mantener separada la lógica testeable de la composición visual.

## Fuente de datos

El dashboard intenta consumir la API:

```text
API_BASE_URL=http://127.0.0.1:8000
```

Endpoints usados:

```text
GET /rankings/latest/geojson
GET /clientes
GET /clientes/{cliente_id}/rankings/latest/geojson
GET /admin/parcelas/disponibles
POST /admin/parcelas/{parcela_id}/activar-disponible
```

Si la API no responde, usa fallback local:

```text
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

## Vistas incluidas

### Admin

- mapa operativo filtrado por defecto a prioridades `alta` y `crítica`;
- opción `Mostrar todas las prioridades` para cargar el universo completo;
- filtros por cultivo, prioridad, confianza y rango de ranking;
- pestaña de estado general con métricas del universo completo y de la vista
  activa;
- panel de proyección actual, 5 días y 10 días;
- pestaña de revisión técnica de outliers/calidad;
- pestaña de parcelas disponibles para activar no vid/no olivo como `vid` u
  `olivo` y asignarlas opcionalmente a un cliente;
- pestaña de cobertura con evaluadas, sin ranking y confianza de lectura;
- top de parcelas críticas;
- resumen por cultivo;
- tabla completa de ranking y auditoría.

La vista Admin muestra proyecciones operativas:

```text
riesgo_operativo_5d
riesgo_operativo_10d
delta_operativo_10d
```

Si una corrida antigua no tiene esas columnas, el frontend hace fallback a las
predicciones crudas `riesgo_pred_*`.

### Cliente

- selector local de cliente;
- estado general del campo antes del mapa;
- mapa limitado a parcelas asociadas al cliente;
- slider bajo el mapa para visualizar riesgo actual, proyección 5 días y
  proyección 10 días con categorías relativas al campo visible;
- métricas operativas orientadas a detección de estrés hídrico;
- panel de proyección por parcela a 5 y 10 días;
- tabla simplificada de sus parcelas con nombres legibles;
- sin pestaña de revisión técnica.
- sin recomendación directa de riego: el usuario interpreta la información con
  su experiencia de manejo.
- la parcela seleccionada se resalta en el mapa.

La vista cliente muestra la proyección operativa:

```text
riesgo_operativo_5d
riesgo_operativo_10d
```

Estas columnas representan un escenario conservador de continuidad de la
condición actual. La proyección sube o se mantiene con el paso de los días, toma
en cuenta tendencia reciente, cultivo y estación, y evita mostrar mejoras que
en el histórico pudieron deberse a riego o lluvia entre imágenes.

En el mapa cliente, el slider temporal colorea de verde a rojo según la posición
relativa de cada parcela dentro del campo visible para cada día interpolado. Esto
mantiene consistencia con el criterio `Dentro de mi campo` de la tabla.

La vista admin puede conservar columnas de predicción ML cruda en tablas
técnicas:

```text
riesgo_pred_5d
riesgo_pred_10d
```

pero la visualización principal de mapa, popup y panel usa la proyección
operativa.

Para habilitar clientes en fallback local:

```text
backend/data/clientes/clientes.csv
backend/data/clientes/cliente_parcela.csv
```

Clientes demo actuales:

```text
Finca Demo Norte: parcelas vecinas de vid
Olivar Demo Este: parcelas vecinas de olivo
```

### Regional

- mapa de UM DGI con parcelas oficiales de vid/olivo;
- filtros por cuenca, prioridad regional y mínimo de parcelas;
- categorización por umbrales fijos o relativa por percentiles dentro de las
  UM visibles;
- color por prioridad regional, score promedio, porcentaje alta/crítica o
  superficie cultivada;
- métricas de UM, parcelas, cobertura de ranking y superficie cultivada;
- tabla de ranking regional por UM.
- al seleccionar una UM en el mapa se muestra un detalle con fecha de ranking,
  score regional, riesgo actual, riesgo proyectado a 10 días, composición
  vid/olivo y cobertura de parcelas rankeadas.
- la pestaña `Parcelas de la UM` muestra las parcelas que explican la UM
  seleccionada, su ranking, riesgo, prioridad y un mapa filtrado a esa zona.

Fuente local:

```text
backend/data/zonificacion/um_con_cultivos.geojson
backend/data/zonificacion/ranking_um_latest.csv
backend/data/zonificacion/parcelas_um.csv
```

Esta vista omite UM sin cultivos porque la decisión regional se quiere hacer
sobre zonas efectivamente productivas.

## Cobertura actual

El dashboard admin muestra todas las parcelas oficiales vid/olivo. Las parcelas
sin ranking se mantienen visibles en gris.

Para acelerar el mapa se usa un GeoJSON liviano de visualización:

```text
backend/data/parcelas/san_rafael_vid_olivo_dashboard.geojson
```

Se genera desde el parcelario operativo con:

```bash
venv/bin/python backend/scripts/maintenance/generar_geojson_dashboard_parcelas.py
```

Este archivo conserva `fid`, `cultivo`, `area_m2` y geometría simplificada. El
ranking y los datos del hover siguen viniendo del DataFrame, por eso el GeoJSON
que se envía a Plotly se reduce a geometría + `parcela_id`.

Para auditar faltantes:

```bash
venv/bin/python backend/scripts/audit/auditar_cobertura_parcelas.py
```

Salidas:

```text
backend/data/auditoria_cobertura_parcelas.csv
backend/data/auditoria_cobertura_parcelas.geojson
```

Estados posibles:

| Estado                             | Significado                                              |
|------------------------------------|----------------------------------------------------------|
| `rankeada` | Tiene historial y aparece en el ranking latest.                                  |
| `con_historial_sin_ranking_latest` | Tiene historial, pero no observación válida/ranking en la fecha latest. |
| `sin_historial`                    | No fue incluida en el dataset temporal actual.           |

Estado actual:

```text
parcelas oficiales vid/olivo: 10689
rankeadas: 9679
sin ranking: 1010
```

## Variables de entorno

Opcional en `.env`:

```text
API_BASE_URL=http://127.0.0.1:8000
```

En cloud se debe apuntar al host/puerto donde corra FastAPI.
