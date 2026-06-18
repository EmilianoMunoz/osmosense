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
`POST /auth/login`. Los accesos rápidos también usan ese login real; no generan
sesión demo ni evitan los permisos de la API.

Usuarios disponibles para desarrollo local:

| Email | Contraseña | Vista |
|---|---|---|
| `admin@osmosense.local` | `admin123` | Admin |
| `productor.vid@osmosense.local` | `cliente123` | Productor vid |
| `productor.olivo@osmosense.local` | `cliente123` | Productor olivo |
| `regional@osmosense.local` | `regional123` | Regional |

La pantalla conserva accesos rápidos PostGIS:

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
frontend/components/branding.py
frontend/components/charts.py
frontend/components/client_feedback.py
frontend/components/client_overview.py
frontend/components/metrics.py
frontend/components/parcel_detail.py
frontend/components/tables.py
frontend/views/admin/
frontend/views/dashboard_filters.py
frontend/views/dashboard.py
frontend/views/regional.py
```

Responsabilidades:

| Archivo                                  | Responsabilidad                                   |
|------------------------------------------|---------------------------------------------------|
| `streamlit_app.py`                       | Entrypoint mínimo.                                |
| `frontend/auth.py`                       | Login, logout y sesión PostGIS.                   |
| `frontend/data.py`                       | Carga desde API/local y normalización a DataFrame.|
| `frontend/logic.py`                      | Prioridad dinámica, selección de valores visibles y reglas puras. |
| `frontend/map.py`                        | Mapa, zoom, hover y selección de parcela.         |
| `frontend/table_config.py`               | Columnas visibles, labels y restricciones por rol.|
| `frontend/components/branding.py`        | Logo, estilos de marca y pantalla de carga.       |
| `frontend/components/client_feedback.py` | Mensajes claros para productor.                   |
| `frontend/components/client_overview.py` | Estado general de parcelas en vista productor.    |
| `frontend/components/metrics.py`         | Métricas resumen.                                 |
| `frontend/components/parcel_detail.py`   | Detalle y pop-up de parcela.                      |
| `frontend/components/tables.py`          | Tablas y resúmenes tabulares.                     |
| `frontend/components/charts.py`          | Gráficos de proyección y distribución.            |
| `frontend/panels.py`                     | Fachada de compatibilidad para componentes.       |
| `frontend/views/dashboard_filters.py`    | Filtros, navegación y selección de vista.         |
| `frontend/views/dashboard.py`            | Orquestación de la vista Streamlit.               |
| `frontend/views/admin/`                  | Gestión admin de usuarios, productores y parcelas.|
| `frontend/views/regional.py`             | Vista regional por UM DGI recortada a San Rafael. |

El objetivo es mantener separada la lógica testeable de la composición visual.

## Fuente de datos

El dashboard intenta consumir la API:

```text
API_BASE_URL=http://127.0.0.1:8000
```

Endpoints usados:

```text
GET /rankings/latest/geojson
GET /me
GET /me/rankings/latest/geojson
GET /me/parcelas
GET /clientes
GET /clientes/{cliente_id}/rankings/latest/geojson
GET /admin/usuarios
POST /admin/usuarios
PUT /admin/usuarios/{usuario_id}
DELETE /admin/usuarios/{usuario_id}
GET /admin/clientes
GET /admin/clientes/{cliente_id}/parcelas
POST /admin/clientes/{cliente_id}/parcelas
DELETE /admin/clientes/{cliente_id}/parcelas/{parcela_id}
GET /admin/parcelas/disponibles
POST /admin/parcelas/{parcela_id}/activar-disponible
```

La vista `Productor` usa `/me/rankings/latest/geojson`: el backend toma el
productor desde el token y el frontend no construye la consulta con
`cliente_id`. Las rutas `/clientes/{cliente_id}/...` quedan para compatibilidad
interna y para vistas admin/debug.

En desarrollo, si la API no responde, puede usar fallback local:

```text
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

En producción (`APP_ENV=production`) ese fallback queda deshabilitado. Si la
API/PostGIS no responde, la vista muestra error y no renderiza datos locales.
Además, las vistas autenticadas de productor y las verificaciones admin por
productor no usan fallback CSV cuando existe token de sesión: esto evita que el
CRUD de asignación/desasignación quede inconsistente por relaciones locales
viejas.

## Vistas incluidas

### Admin

- entrada al área `Análisis` o `Gestión`;
- en `Análisis`, selector lazy de secciones: `Estado`, `Mapa operativo`,
  `Datos`, `Cobertura`, `Revisión técnica`. Solo se renderiza la sección activa
  para evitar construir mapa y tablas pesadas en cada rerun;
- en `Estado`, separa `Ranking operativo` de `Última corrida`: si la corrida
  Sentinel más reciente no alcanza cobertura suficiente, se informa que fue
  descartada para uso operativo y se conserva la última fecha confiable;
- en `Gestión`, dos secciones principales: `Usuarios` y `Parcelas`;
- en `Usuarios`, alta, edición, reactivación y desactivación trazable de
  accesos. Los productores requieren apellido y DNI válido;
- en `Parcelas`, subsecciones `Asignar y desasignar` y `Agregar al análisis`;
- mapa operativo filtrado por defecto a prioridades `alta` y `crítica`;
- opción `Mostrar todas las prioridades` para cargar el universo completo;
- filtros por cultivo, prioridad, confianza y rango de ranking;
- pestaña de estado general con métricas del universo completo y de la vista
  activa;
- panel de proyección actual, 5 días y 10 días;
- pestaña de revisión técnica de outliers/calidad;
- asignación de parcelas analizadas sin productor mediante mapa o carga manual
  de IDs;
- desasignación de parcelas mediante mapa filtrado al productor seleccionado:
  el clic sobre una parcela agrega o quita su ID de la selección a desasignar;
- confirmación en popup luego de asignar o desasignar, con productor,
  cantidad de parcelas, IDs afectados y conteo antes/después;
- pestaña de parcelas disponibles para activar no vid/no olivo como `vid` u
  `olivo` y asignarlas opcionalmente a un productor;
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

### Productor

- pestañas en orden: `Mapa`, `Resumen`, `Parcelas`;
- aviso superior con la fecha de `Ranking operativo usado`, para aclarar que la
  vista usa el último ranking con cobertura suficiente;
- métricas separadas para `Ranking operativo` y `Lectura satelital`: la primera
  es la fecha objetivo del ranking, la segunda es la imagen/observación efectiva
  usada para calcular las parcelas;
- mapa limitado a parcelas asociadas al productor como primera vista;
- slider bajo el mapa para visualizar riesgo actual, proyección 5 días y
  proyección 10 días;
- mensaje superior en lenguaje simple con cantidad de parcelas en atención y
  evolución general esperada;
- resumen operativo de sus parcelas;
- métricas operativas con etiquetas no técnicas (`Atención crítica`,
  `Atención alta`, `Señal promedio`, `Señal más alta`);
- panel lateral de comparación de la parcela seleccionada contra el promedio de
  las parcelas visibles del productor;
- dos gráficos horizontales simples: uno para riesgo actual y otro para
  escenario a 10 días, cada uno con una línea celeste de promedio del conjunto;
- indicadores de evolución con flecha roja hacia arriba cuando aumenta el
  riesgo, flecha verde hacia abajo cuando disminuye y flecha gris cuando se
  mantiene estable. Se evita el signo `+` porque puede leerse como algo
  positivo;
- barras de comparación coloreadas con la misma escala semántica del mapa:
  verde bajo, amarillo medio, naranja alto y rojo crítico;
- bloque de `Mayor aumento esperado`, que separa las parcelas con mayor cambio
  proyectado de las parcelas que ya tienen mayor riesgo actual;
- lectura simple por parcela: estado actual, evolución esperada, tendencia y
  fecha de lectura;
- listado de parcelas para revisar primero, sin exponer columnas técnicas;
- tabla simplificada de sus parcelas con nombres legibles;
- sin pestaña de revisión técnica.
- sin gráfico de distribución de prioridades, porque no aporta una acción clara
  para el productor;
- sin recomendación directa de riego: el usuario interpreta la información con
  su experiencia de manejo.
- la parcela seleccionada se resalta en el mapa.

La vista productor muestra la proyección operativa:

```text
riesgo_operativo_5d
riesgo_operativo_10d
```

Estas columnas representan un escenario conservador de continuidad de la
condición actual. La proyección sube o se mantiene con el paso de los días, toma
en cuenta tendencia reciente, cultivo y estación, y evita mostrar mejoras que
en el histórico pudieron deberse a riego o lluvia entre imágenes.

En el mapa productor, el slider temporal colorea de verde a rojo según la
evolución operativa de cada parcela visible. La categoría de la animación usa
umbrales absolutos por defecto, no posición relativa entre parcelas.

La vista admin puede conservar columnas de predicción ML cruda en tablas
técnicas:

```text
riesgo_pred_5d
riesgo_pred_10d
```

pero la visualización principal de mapa, popup y panel usa la proyección
operativa.

Compatibilidad local heredada para relaciones productor-parcela:

```text
backend/data/clientes/clientes.csv
backend/data/clientes/cliente_parcela.csv
```

En producto, la entidad visible es `productor`. Los nombres `clientes` y
`cliente_parcela` quedan como compatibilidad interna hasta migrar a
`usuario_id -> parcela`.

### Regional

- pestañas en orden: `Mapa regional`, `Foco regional`, `Ranking UM`,
  `Parcelas de la UM`;
- mapa de UM DGI con parcelas oficiales de vid/olivo;
- filtros por cuenca, prioridad regional y mínimo de parcelas;
- categorización por umbrales fijos o relativa por percentiles dentro de las
  UM visibles;
- color por prioridad regional, score promedio, porcentaje alta/crítica o
  superficie cultivada;
- métricas de UM, parcelas, cobertura de ranking y superficie cultivada;
- foco regional con UM de mayor aumento proyectado, concentración alta/crítica
  y baja cobertura;
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

Para acelerar el mapa se usa geometría optimizada solo para visualización:

- con PostGIS, el frontend puede pedir
  `/rankings/latest/geojson?simplify_meters=2`;
- en fallback local, se usa un GeoJSON liviano:

```text
backend/data/parcelas/san_rafael_vid_olivo_dashboard.geojson
```

Se genera desde el parcelario operativo con:

```bash
venv/bin/python backend/scripts/maintenance/generar_geojson_dashboard_parcelas.py
```

El dashboard Admin usa la geometría optimizada por defecto. La optimización no
modifica la geometría persistida ni los modelos; solo cambia la geometría
enviada al navegador para dibujar el mapa.

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
