# Artefactos operativos

Este documento separa los archivos que forman parte del flujo actual de los
artefactos experimentales o regenerables que no conviene versionar en Git.

## Criterio de limpieza

Se conserva solo lo necesario para:

1. reconstruir o ampliar el dataset temporal desde parcelas oficiales;
2. reentrenar los modelos predictivos vigentes;
3. generar rankings hídricos;
4. servir la API y el dashboard;
5. cargar resultados en PostGIS cuando corresponda.

Los datasets grandes, rankings, logs, salidas de auditoría y modelos binarios
quedan fuera de Git por `.gitignore`.

## Datos conservados localmente

### Fuente original

```text
backend/data/parcelas/parcelas_ide.geojson
```

Dataset oficial original con geometrías y etiquetas de cultivo. Es la base de
referencia para reconstruir muestras, auditar cobertura y cargar parcelas en
PostGIS.

### Geometrías operativas

```text
backend/data/limites/san_rafael.geojson
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
backend/data/parcelas/muestra_temporal_full_vid_olivo.geojson
```

`san_rafael.geojson` es opcional pero recomendado. Si existe, reemplaza el
fallback por bounding box para filtrar parcelas y definir la región GEE.

`san_rafael_vid_olivo_wgs84.geojson` contiene las parcelas oficiales filtradas
para el dominio actual del producto: vid y olivo en San Rafael.

`muestra_temporal_full_vid_olivo.geojson` es la muestra usada para extracción
temporal Sentinel-2 y expansión por lotes.

### Dataset temporal principal

```text
backend/data/dataset_temporal_hidrico.csv
```

Es el dataset operativo actual. Contiene observaciones Sentinel-2 por parcela y
fecha, con índices espectrales y variables temporales usadas para generar
targets, validar predicciones y producir ranking.

Este archivo no se versiona por tamaño. Si se borra o se quiere ampliar, se
regenera con:

```bash
venv/bin/python backend/scripts/pipeline/generar_dataset_temporal_hidrico.py --reuse-sample --resume-from-max-date --output backend/data/dataset_temporal_hidrico.csv --start-date 2023-01-01 --end-date 2024-12-31 --step-days 5 --window-days 5 --chunk-size 500
```

Para ampliar cobertura latest de parcelas faltantes:

```bash
venv/bin/python backend/scripts/pipeline/generar_dataset_temporal_hidrico.py --all-target-parcels --missing-date 2024-12-31 --max-parcels 1000 --output backend/data/dataset_temporal_hidrico.csv --output-sample backend/data/parcelas/muestra_temporal_full_vid_olivo.geojson --start-date 2024-12-31 --end-date 2024-12-31 --step-days 5 --window-days 5 --chunk-size 250 --cloud-threshold 35 --resume
```

### Ranking operativo

```text
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/rankings/ranking_hidrico_YYYY-MM-DD.csv
```

Son salidas del pipeline. La API y el dashboard los usan como fallback local
cuando no hay PostGIS disponible.

Se regeneran con:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
```

### Auditoría y validación

```text
backend/data/auditoria_cobertura_parcelas.csv
backend/data/auditoria_cobertura_parcelas.geojson
backend/data/validacion_ranking_hidrico_multifecha_2024.csv
backend/data/validacion_ranking_hidrico_multifecha_2024_resumen.csv
```

No son necesarios para servir el producto, pero sirven para medir cobertura,
calibrar ranking y justificar resultados. Son regenerables y no se versionan.

## Modelos conservados

Los modelos vigentes son regresores separados por cultivo y horizonte:

```text
backend/models/hidrico_regresion/regresor_vid_5d_riesgo_hidrico_future_temporal.pkl
backend/models/hidrico_regresion/regresor_vid_10d_riesgo_hidrico_future_temporal.pkl
backend/models/hidrico_regresion/regresor_olivo_5d_riesgo_hidrico_future_temporal.pkl
backend/models/hidrico_regresion/regresor_olivo_10d_riesgo_hidrico_future_temporal.pkl
```

La configuración versionable de ranking es:

```text
backend/models/ranking_hidrico_config.json
```

Los `.pkl` no se versionan por `.gitignore`. Si se necesita distribuirlos, usar
Git LFS, release artifacts o almacenamiento externo.

## Artefactos eliminados

Se eliminaron datasets y modelos de etapas descartadas:

- clasificadores binarios antiguos de estrés hídrico;
- modelos multiclass y filtros auxiliares que no forman parte del flujo actual;
- splits `train/validation/test_final` usados por experimentos previos;
- datasets fenológicos e híbridos reemplazados por el dataset temporal;
- targets de regresión materializados, porque se regeneran desde el temporal.

El target intermedio de regresión se recrea con:

```bash
venv/bin/python backend/scripts/pipeline/generar_targets_hidricos_regresion.py
```

Luego se reentrenan los cuatro modelos vigentes con:

```bash
venv/bin/python backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py --split temporal
```

## Verificación mínima después de limpiar

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local --dry-run
venv/bin/python -c "from app.services.rankings import latest_ranking, latest_geojson; print(len(latest_ranking(limit=1)), len(latest_geojson()['features']))"
```

La primera prueba verifica que el pipeline puede generar ranking con los
artefactos restantes. La segunda verifica que la API puede leer el ranking local
y devolver GeoJSON para el dashboard.
