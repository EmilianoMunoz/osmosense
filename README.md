# Detección y Predicción de Estrés Hídrico en Viñedos y Olivares
### San Rafael, Mendoza — Tesis de Grado

## Descripción
Plataforma web para monitorear y predecir el estrés hídrico de viñedos y olivares
en parcelas agrícolas de San Rafael, Mendoza, mediante el procesamiento de imágenes
satelitales Sentinel-2 y modelos de inteligencia artificial.

## Funcionalidades
- Obtención y filtrado de imágenes Sentinel-2 via Google Earth Engine
- Cálculo de índices espectrales por parcela
- Ranking hídrico satelital relativo para vid y olivo
- Predicción/proyección a 5 y 10 días
- Visualización web para Admin, Cliente y Regional
- Zonificación regional por UM con ranking agregado
- API FastAPI con fallback local o PostGIS
- Pipeline local/cloud preparado para automatización

## Requisitos
- Python 3.10+
- Cuenta en Google Earth Engine (plan Comunidad / Académico)
- Ubuntu 22.04 o superior (desarrollado y probado en este entorno)
- Docker, opcional pero recomendado para PostGIS local

`psycopg[binary]` está declarado para el flujo PostGIS. Si solo se usa el
fallback local CSV/GeoJSON, la API y el dashboard pueden ejecutarse sin conectarse
a PostGIS.

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/tuusuario/estres-hidrico.git
cd estres-hidrico
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
pip install -e .
```

### 4. Configurar variables de entorno
Crear un archivo `.env` en la raíz del proyecto:

```text
GEE_PROJECT_ID=tu-proyecto-gee
API_BASE_URL=http://127.0.0.1:8000
```

Si se usa PostGIS local:

```text
DATABASE_URL=postgresql://estres:estres_dev@127.0.0.1:5433/estres
API_BASE_URL=http://127.0.0.1:8000
```

Ejemplos disponibles:

```text
.env.local.example
.env.cloud.example
.env.postgis.example
```

### 5. Autenticarse con Google Earth Engine
```bash
earthengine authenticate
```

## Uso

Referencias rápidas:

```text
docs/comandos.md
docs/estructura_proyecto.md
docs/FUTURE.md
backend/README.md
frontend/README.md
backend/scripts/README.md
```

### Recalcular dataset temporal Sentinel-2
```bash
venv/bin/python backend/scripts/pipeline/generar_dataset_temporal_hidrico.py --reuse-sample --resume-from-max-date --output backend/data/dataset_temporal_hidrico.csv --start-date 2023-01-01 --end-date 2024-12-31 --step-days 5 --window-days 5 --chunk-size 500
```

### Ampliar cobertura de parcelas faltantes
Extraer fecha latest para el próximo lote de parcelas sin observación:
```bash
venv/bin/python backend/scripts/pipeline/generar_dataset_temporal_hidrico.py --all-target-parcels --missing-date 2024-12-31 --max-parcels 1000 --output backend/data/dataset_temporal_hidrico.csv --output-sample backend/data/parcelas/muestra_temporal_full_vid_olivo.geojson --start-date 2024-12-31 --end-date 2024-12-31 --step-days 5 --window-days 5 --chunk-size 250 --cloud-threshold 35 --resume
```

Luego regenerar ranking:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
```

### Generar targets de regresión hídrica
```bash
venv/bin/python backend/scripts/pipeline/generar_targets_hidricos_regresion.py
```

### Reentrenar modelos de ranking hídrico
```bash
venv/bin/python backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py --split temporal
```

### Analizar importancia de variables del predictor
```bash
venv/bin/python backend/scripts/modeling/analizar_importancia_predictores_hidricos.py --top-n 10
```

### Optimizar fórmula final de ranking
```bash
venv/bin/python backend/scripts/modeling/optimizar_ranking_hidrico.py --step 0.05 --min-n 50
```

La configuración calibrada queda en:

```text
backend/models/ranking_hidrico_config.json
```

### Auditar cobertura de parcelas
```bash
venv/bin/python backend/scripts/audit/auditar_cobertura_parcelas.py
```

Salidas:

```text
backend/data/auditoria_cobertura_parcelas.csv
backend/data/auditoria_cobertura_parcelas.geojson
```

### Auditar parcelas sin ranking
```bash
venv/bin/python backend/scripts/audit/auditar_sin_ranking.py
```

Salidas:

```text
backend/data/auditoria_sin_ranking_detalle.csv
backend/data/auditoria_sin_ranking_resumen.csv
backend/data/auditoria_sin_ranking_detalle.geojson
```

### Auditar outliers espaciales por vecinos
```bash
venv/bin/python backend/scripts/audit/auditar_vecinos_ranking.py --score-column prioridad_score
venv/bin/python backend/scripts/audit/auditar_vecinos_ranking.py --score-column riesgo_actual --output-detalle backend/data/auditoria_vecinos_ranking_riesgo_actual.csv --output-resumen backend/data/auditoria_vecinos_ranking_riesgo_actual_resumen.csv --output-geojson backend/data/auditoria_vecinos_ranking_riesgo_actual.geojson
```

Por defecto compara cada parcela rankeada contra vecinos del mismo cultivo,
hasta 500 m, usando 6 vecinos máximos y marcando outlier si difiere 35 puntos o
más de la mediana vecinal.

### Auditar persistencia temporal de outliers
```bash
venv/bin/python backend/scripts/audit/auditar_outliers_temporales.py
```

Usa los outliers espaciales de `riesgo_actual` y revisa si el salto es
persistente, puntual o indeterminado según el historial de la misma parcela.

### Ejecutar pipeline operativo local/cloud
Sin consultar GEE, usando el dataset temporal existente:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
```

Actualizando Sentinel-2/GEE antes de rankear:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --skip-if-no-new-date
```

Actualizando Sentinel-2/GEE usando parcelas activas desde PostGIS:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date
```

Actualizando solo una ventana reciente para análisis latest/t-5/t-10:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --update-recent-window --recent-days 10 --extract-chunk-size 250 --skip-if-no-new-date
```

En ejecución real, este modo primero busca hacia atrás la última ventana
Sentinel válida y usa esa fecha como `t`. Se puede controlar con:

```text
--resolve-latest-valid-date / --no-resolve-latest-valid-date
--latest-lookback-days 30
--latest-min-images 1
```

Con `--recent-days 10`, `--extract-step-days 5` y `--extract-window-days 5`,
el modo reciente consulta ventanas cerradas hacia atrás. Si la última fecha
válida resuelta es 2026-05-31, consulta:

```text
2026-05-16 -> 2026-05-21
2026-05-21 -> 2026-05-26
2026-05-26 -> 2026-05-31
```

Actualizando Sentinel-2/GEE y cargando el ranking en PostGIS:
```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Salidas:
```text
backend/data/rankings/ranking_hidrico_YYYY-MM-DD.csv
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/state/pipeline_hidrico_state.json
backend/data/logs/pipeline_hidrico_YYYYMMDD_HHMMSS.log
```

Los datasets y modelos generados son artefactos locales pesados y quedan
excluidos de Git por `.gitignore`.

La lista actual de artefactos operativos y regenerables está documentada en
`docs/artefactos_operativos.md`.

El inventario de código vigente, auxiliar y legacy está en
`docs/inventario_codigo.md`.

## Despliegue cloud

El despliegue objetivo es UM-Cloud. La guía de acceso/provisionamiento está en
`docs/UM_Cloud_Setup_Guide.md` y la arquitectura operativa del pipeline está en
`docs/arquitectura_cloud_pipeline.md`.

## Límite geográfico

El límite local de San Rafael se documenta en `docs/limite_san_rafael.md`.
Si existe `backend/data/limites/san_rafael.geojson`, el pipeline lo usa para filtrar
parcelas y construir la región de consulta GEE. Si no existe, usa el bounding
box operativo como fallback.

## PostGIS

La estructura operativa de base de datos está en `backend/sql/schema_postgis.sql`.
El flujo de carga está documentado en `docs/postgis.md`.

Levantar PostGIS local:

```bash
docker compose -f docker-compose.postgis.yml up -d
```

Aplicar schema y cargar datos operativos:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py
```

Validar conteos:

```bash
venv/bin/python backend/scripts/postgis/validar_postgis_local.py
```

Pruebas sin conectarse a una base:

```bash
venv/bin/python backend/scripts/postgis/aplicar_schema_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_parcelas_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_ranking_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --dry-run
```

## API

La API mínima está en `app/main.py` y se documenta en `docs/api.md`.

Ejecutar local:

```bash
venv/bin/uvicorn backend.app.main:app --reload
```

Ejecutar local leyendo desde PostGIS:

```bash
export DATABASE_URL=postgresql://estres:estres_dev@127.0.0.1:5433/estres
venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Endpoints principales:

```text
GET /health
POST /auth/login
GET /rankings/latest
GET /rankings/latest/geojson
GET /rankings/{fecha}
GET /clientes
GET /clientes/{cliente_id}/rankings/latest/geojson
GET /admin/parcelas
GET /admin/parcelas/disponibles
GET /admin/parcelas/{parcela_id}
POST /admin/parcelas
POST /admin/parcelas/{parcela_id}/activar-disponible
PUT /admin/parcelas/{parcela_id}
DELETE /admin/parcelas/{parcela_id}
GET /admin/clientes
POST /admin/clientes
PUT /admin/clientes/{cliente_id}
GET /admin/clientes/{cliente_id}/parcelas
POST /admin/clientes/{cliente_id}/parcelas
DELETE /admin/clientes/{cliente_id}/parcelas/{parcela_id}
GET /admin/usuarios
POST /admin/usuarios
PUT /admin/usuarios/{usuario_id}
GET /regional/um/latest
GET /regional/um/latest/geojson
GET /regional/um/{um_id}/parcelas/latest/geojson
```

## Dashboard

El dashboard Streamlit está en `streamlit_app.py` y se documenta en
`docs/dashboard.md`.

Levantar entorno local completo:

```bash
./boot.sh start
```

Primera carga o recarga completa de PostGIS:

```bash
./boot.sh start --setup --all-parcelas --smoke
```

Consultar estado:

```bash
./boot.sh status
```

Detener API y dashboard:

```bash
./boot.sh stop
```

Consume `/rankings/latest/geojson` si la API está levantada. Si no, usa CSV y
GeoJSON locales.

Flujo manual equivalente con PostGIS:

```bash
docker compose -f docker-compose.postgis.yml up -d
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
venv/bin/streamlit run streamlit_app.py
```

En el dashboard, la barra lateral debe indicar:

```text
Fuente: postgis
```

El login del dashboard usa `POST /auth/login` contra PostGIS cuando la API está
activa. Los accesos rápidos de desarrollo siguen disponibles en la pantalla de
login.

## Verificación mínima

Ejecutar tests rápidos de ranking/API:

```bash
venv/bin/python -m pytest -q
```

Ejecutar smoke test operativo contra la API levantada:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis
```

Validar PostGIS directo:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --skip-api --check-postgis
```

Validar fallback local CSV/GeoJSON:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --skip-api --check-local-fallback
```

Validación completa local, con API y PostGIS:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis --check-local-fallback
```

## Artefactos y Git

Versionar:

```text
backend/app/
backend/scripts/
backend/sql/
backend/models/ranking_hidrico_config.json
frontend/
docs/
tests/
docker-compose.postgis.yml
.env.local.example
.env.cloud.example
.env.postgis.example
```

No versionar:

```text
.env
venv/
backend/data/**/*.csv
backend/data/**/*.geojson
backend/data/logs/
backend/data/state/
backend/data/rankings/
backend/data/auditorias/
backend/data/parcelas/*.geojson
backend/models/**/*.pkl
backend/models/hidrico_regresion/
```

Los CSV/GeoJSON grandes o derivados se regeneran con el pipeline y están
cubiertos por `.gitignore`.
