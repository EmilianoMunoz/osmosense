# Comandos Operativos

Hoja rápida de comandos actuales después de mover el backend a `backend/`.

## Stack Local

Levantar todo:

```bash
./boot.sh start
```

Primera carga completa con PostGIS:

```bash
./boot.sh start --setup --all-parcelas --smoke
```

Ver estado:

```bash
./boot.sh status
```

Detener API y dashboard:

```bash
./boot.sh stop
```

## API

```bash
venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Dashboard

```bash
venv/bin/streamlit run streamlit_app.py
```

## PostGIS

Levantar PostGIS:

```bash
docker compose -f docker-compose.postgis.yml up -d
```

Aplicar schema y cargar datos:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
```

Validar PostGIS:

```bash
venv/bin/python backend/scripts/postgis/validar_postgis_local.py
```

Smoke test:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```

## Pipeline

Pipeline local:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
```

Pipeline cloud con actualización Sentinel y carga PostGIS:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Arranque de servicios con actualización previa de ranking solo si hay fecha nueva:

```bash
./boot.sh start --update-ranking
```

Dry-run:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local --dry-run
```

## Tests

```bash
venv/bin/python -m pytest -q
```
