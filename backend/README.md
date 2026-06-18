# Backend

Backend operativo del sistema de estrés hídrico. Contiene API, pipeline,
modelos, datos operativos, schema PostGIS y scripts de mantenimiento.

## Estructura

```text
backend/
├── app/       # FastAPI y servicios backend
├── data/      # datos operativos, rankings, auditorías y zonificación
├── models/    # modelos entrenados y configuración del ranking
├── scripts/   # scripts organizados por dominio
├── sql/       # schema PostGIS
└── boot.sh    # arranque operativo, invocado por ./boot.sh
```

## Comandos principales

Levantar API, PostGIS y dashboard desde la raíz:

```bash
./boot.sh start
```

Primera carga completa local:

```bash
./boot.sh start --setup --all-parcelas --smoke
```

Arranque con actualización operativa de ranking si hay imagen Sentinel nueva:

```bash
./boot.sh start --update-ranking
```

Ejecutar pipeline local:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
```

Ejecutar pipeline cloud/PostGIS:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --update-recent-window --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Aplicar schema y cargar PostGIS local:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
```

Smoke test operativo:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```

## API

Entrada FastAPI:

```text
backend.app.main:app
```

Arranque manual:

```bash
venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Datos y modelos

Los artefactos regenerables viven en `backend/data/` y los modelos en
`backend/models/`. En general no deben versionarse salvo configuraciones livianas
como `backend/models/ranking_hidrico_config.json`.
