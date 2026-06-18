# Inventario de código

> Estado: histórico. Este inventario fue útil antes de reorganizar el proyecto
> en `backend/`. Para comandos y estructura actuales usar
> `docs/estructura_proyecto.md`, `docs/comandos.md` y `backend/scripts/README.md`.

Este inventario define qué archivos pertenecen al flujo operativo actual y
cuáles quedan como legacy o experimentales. No agrega funcionalidad: solo reduce
ambigüedad para mantenimiento, commits y defensa técnica del proyecto.

## Flujo operativo vigente

### Extracción y dataset temporal

```text
scripts/generar_dataset_temporal_hidrico.py
scripts/recalcular_dataset_desde_ide.py
```

Genera o amplía `data/dataset_temporal_hidrico.csv` desde Sentinel-2/GEE y las
geometrías de parcelas vid/olivo.

`recalcular_dataset_desde_ide.py` queda en `scripts/` porque
`generar_dataset_temporal_hidrico.py` reutiliza funciones auxiliares de ese
archivo. Aunque nació en un flujo anterior, hoy funciona como dependencia
técnica del extractor temporal.

### Targets y entrenamiento predictivo

```text
scripts/generar_targets_hidricos_regresion.py
scripts/experiments/entrenar_predictores_hidricos_regresion.py
```

Construyen el dataset supervisado de regresión y entrenan los cuatro modelos
vigentes:

```text
vid 5d
vid 10d
olivo 5d
olivo 10d
```

### Ranking hídrico

```text
scripts/generar_ranking_hidrico.py
scripts/optimizar_ranking_hidrico.py
scripts/validar_ranking_hidrico_multifecha.py
scripts/run_pipeline_hidrico.py
```

`generar_ranking_hidrico.py` aplica modelos y fórmula de prioridad.

`optimizar_ranking_hidrico.py` calibra pesos y umbrales.

`validar_ranking_hidrico_multifecha.py` evalúa consistencia temporal del
ranking.

`run_pipeline_hidrico.py` es el punto de entrada operativo para ejecución local
o cloud.

### Cobertura

```text
scripts/auditar_cobertura_parcelas.py
```

Mide qué parcelas oficiales vid/olivo tienen ranking latest, cuáles tienen
historial pero no latest, y cuáles todavía no tienen observaciones.

### API

```text
app/main.py
app/services/rankings.py
```

Sirven endpoints de ranking desde PostGIS si existe `DATABASE_URL`. Sin
`DATABASE_URL` pueden usar CSV y GeoJSON locales solo en desarrollo; en
producción (`APP_ENV=production`) la API exige PostGIS.

### Dashboard

```text
streamlit_app.py
```

Visualiza ranking latest, mapa de parcelas, filtros por cultivo/prioridad y
detalle de predicción.

### PostGIS

```text
sql/schema_postgis.sql
scripts/aplicar_schema_postgis.py
scripts/cargar_parcelas_postgis.py
scripts/cargar_ranking_postgis.py
```

Definen y cargan la estructura geoespacial para despliegue con PostGIS.

## Código auxiliar vigente

```text
scripts/analizar_importancia_predictores_hidricos.py
scripts/validar_ranking_hidrico.py
```

No son parte del pipeline diario, pero sirven para análisis técnico,
interpretabilidad y validaciones puntuales.

## Legacy o experimental

Estos archivos fueron movidos a `legacy/` porque dependen de datasets/modelos
descartados o pertenecen a etapas anteriores del proyecto. No deben usarse para
el flujo actual sin revisarlos.

### Clasificadores anteriores

```text
legacy/scripts/clasificador_cultivo.py
legacy/scripts/clasificador_olivo.py
legacy/scripts/clasificador_vid_frutales.py
legacy/scripts/optimizar_thresholds_pipeline.py
legacy/scripts/pipeline_inferencia.py
legacy/scripts/pipeline_inferencia_multiclass.py
legacy/scripts/split_dataset.py
legacy/scripts/experiments/evaluar_filtro_vid_olivo.py
legacy/scripts/experiments/seleccion_features_multiclass.py
```

Motivo: referencian artefactos eliminados o descartados:

```text
data/train.csv
data/validation.csv
data/test_final.csv
models/clasificador_cultivo.pkl
models/clasificador_olivo.pkl
models/clasificador_vid_frutales.pkl
models/clasificador_multiclass.pkl
models/filtro_vid_olivo_config.json
```

### Reconstrucción fenológica anterior

```text
legacy/scripts/generar_dataset_hibrido.py
legacy/scripts/generar_features_fenologicas.py
```

Motivo: pertenecen al flujo previo de clasificación y generación fenológica.
Pueden servir como referencia histórica, pero el flujo actual usa
`dataset_temporal_hidrico.csv`.

### Servicios antiguos

```text
legacy/app/services/clasificador.py
legacy/app/services/estres.py
```

Motivo: contienen lógica previa de clasificación y umbrales directos. La API
actual no los expone; los endpoints vigentes consumen `app/services/rankings.py`.

## Archivos eliminados definitivamente

Estos archivos no se movieron a `legacy/` porque eran pruebas puntuales,
comparaciones intermedias o dependían de datasets/modelos descartados. No forman
parte del flujo vigente ni son necesarios para reproducir el pipeline actual.

```text
scripts/clasificador_binario.py
scripts/clasificador_cultivos.py
scripts/comparacion_modelos.py
scripts/comparar_datasets.py
scripts/entrenar_clasificador.py
scripts/filtrar_meses_utiles.py
scripts/generar_dataset_temporal.py
scripts/generar_features_temporales.py
scripts/preparar_dataset.py
scripts/seleccionar_features.py
scripts/seleccionar_features_top.py
scripts/test_clasificador.py
scripts/test_etiquetados.py
scripts/test_pipeline.py
```

También se eliminan del control de versiones artefactos regenerables o
descartados:

```text
data/parcelas/muestra_entrenamiento.geojson
models/clasificador_cultivo.pkl
```

## Recomendación de mantenimiento

No borrar `legacy/` todavía. Mantenerlo como referencia histórica hasta cerrar
la memoria técnica del proyecto o hasta que el flujo operativo esté congelado.
Antes de ejecutar algo dentro de `legacy/`, revisar paths y artefactos porque
varios modelos/datasets referenciados ya fueron eliminados.
