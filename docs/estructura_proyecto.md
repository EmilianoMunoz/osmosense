# Estructura del proyecto

El proyecto queda separado en tres áreas principales:

```text
backend/
frontend/
docs/
```

## Backend

```text
backend/
├── app/                 # FastAPI, servicios y lógica backend
├── data/                # datasets, rankings, auditorías, límites y zonificación
├── models/              # modelos entrenados y configuración de ranking
├── scripts/             # scripts operativos organizados por dominio
├── sql/                 # schema PostGIS
└── boot.sh              # arranque operativo del sistema
```

El `boot.sh` de raíz se conserva como wrapper para no cambiar el comando de uso:

```bash
./boot.sh start
```

Internamente delega en:

```bash
backend/boot.sh
```

## Scripts

```text
backend/scripts/
├── audit/        # auditorías de cobertura, vecinos, outliers y ruido
├── experiments/  # pruebas o scripts fuera del flujo principal
├── maintenance/  # reconstrucción de parcelas y artefactos auxiliares
├── modeling/     # validación, análisis y optimización de modelos
├── pipeline/     # pipeline hídrico y generación de ranking
├── postgis/      # schema, cargas y smoke tests PostGIS
└── zonificacion/ # cruces con unidades de manejo regionales
```

Comandos operativos principales:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis
```

## Frontend

```text
frontend/
streamlit_app.py
```

El dashboard Streamlit queda separado del backend, pero consume la API y usa
fallback local leyendo artefactos desde `backend/data`.

## Docker Compose

`docker-compose.postgis.yml` queda en la raíz por convención: facilita ejecutar
`docker compose` desde el directorio del proyecto y evita acoplar el compose a
una sola parte de la aplicación.
