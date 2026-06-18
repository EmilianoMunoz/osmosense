# Decisiones Técnicas — Estrés Hídrico San Rafael


## Objetivo Del Producto

Construir un sistema para San Rafael, Mendoza, que permita:

- monitorear parcelas oficiales de vid y olivo;
- estimar riesgo hídrico satelital relativo;
- predecir evolución a 5 y 10 días;
- generar un ranking de prioridad de riesgo/atención;
- visualizar resultados en dashboard;
- preparar despliegue posterior en UM-Cloud con PostGIS.

El sistema no usa mediciones de campo de estrés hídrico. El riesgo es un proxy
satelital relativo construido con Sentinel-2.

## Alcance Geográfico Y Agronómico

El alcance operativo queda limitado a:

```text
San Rafael, Mendoza
cultivos: vid y olivo
fuente de parcelas: IDEMendoza
```

Decisión vigente:

- para producción sobre parcelas conocidas se usan las etiquetas oficiales del
  dataset de gobierno;
- el clasificador de cultivo queda como soporte/experimento para escenarios de
  expansión o cambio de uso, pero no es el centro del pipeline operativo actual;
- frutales y no_cultivo no forman parte del producto final.

## Fuente Satelital

Se usa Google Earth Engine con Sentinel-2:

```text
COPERNICUS/S2_SR_HARMONIZED
```

Decisiones vigentes:

- imágenes Sentinel-2 Surface Reflectance;
- composición por ventana corta;
- filtro de nubosidad configurable, actualmente `--cloud-threshold 35`;
- estadísticas por parcela vía `reduceRegions`;
- geometrías en EPSG:4326 para GEE;
- área calculada en EPSG:3857 para filtros métricos;
- buffer negativo de `5 m` para reducir contaminación de borde.

Constantes operativas:

```text
AREA_MINIMA_M2 = 4000
BUFFER_NEGATIVO_M = 5
MIN_VALID_PIXELS = 8
SAN_RAFAEL_BOUNDS = (-69.61384291, -35.52309910, -67.41312966, -34.47910163)
```

Archivo relevante:

```text
scripts/recalcular_dataset_desde_ide.py
```

## Límite Geográfico Local

Decisión vigente:

```text
No depender de FAO/GAUL para el límite fino de San Rafael.
```

Se agregó soporte para un GeoJSON local:

```text
data/limites/san_rafael.geojson
```

Si ese archivo existe, el sistema lo usa para:

- filtrar parcelas oficiales;
- construir la región de consulta en GEE;
- trabajar con un polígono controlado y reproducible.

Si el archivo no existe, se mantiene el fallback por bounding box:

```text
(-69.61384291, -35.52309910, -67.41312966, -34.47910163)
```

Archivos modificados:

```text
app/core/region.py
app/services/images.py
scripts/recalcular_dataset_desde_ide.py
scripts/generar_dataset_temporal_hidrico.py
docs/limite_san_rafael.md
```

Estado actual:

```text
data/limites/san_rafael.geojson existe
el sistema usa el límite local exacto
```

El fallback por bounding box queda disponible solo si falta el GeoJSON local.

## Zonificación DGI

Se incorporó la zonificación DGI entregada como:

```text
data/zonificacion/regional_dgi.csv
```

Nota técnica:

```text
El archivo tiene extensión .csv, pero su contenido es un GeoJSON FeatureCollection.
```

Decisión:

```text
No usar la zonificación provincial completa directamente.
Primero recortarla contra data/limites/san_rafael.geojson.
```

Script reproducible:

```text
scripts/filtrar_zonificacion_san_rafael.py
```

Salidas:

```text
data/zonificacion/regional_dgi_san_rafael.geojson
data/zonificacion/regional_dgi_san_rafael_resumen.csv
```

Resultado actual:

```text
zonas originales: 406
zonas intersectadas con San Rafael: 97
Cuenca: 59
UM: 38
geometrías fuera del límite > 1 m2: 0
```

El script también corrige texto con mojibake (`RÃ­o` -> `Río`) y agrega:

```text
sup_ha_original_calc
sup_ha_san_rafael
pct_sup_en_san_rafael
```

Esta capa queda lista para cruzar posteriormente parcelas/rankings por zona.

Cruce operativo con parcelas:

```text
scripts/cruzar_parcelas_zonificacion_um.py
```

Decisión:

```text
La vista regional operativa usa solo UM con parcelas oficiales vid/olivo.
No muestra Cuencas como unidad de decisión principal.
```

Método:

- toma solo geometrías `tipo = UM`;
- asigna cada parcela a la UM con mayor área de intersección;
- agrega métricas regionales ponderadas por superficie de parcela;
- conserva solo UM que tienen cultivos.

Salidas:

```text
data/zonificacion/parcelas_um.csv
data/zonificacion/um_con_cultivos.geojson
data/zonificacion/ranking_um_latest.csv
```

Resultado actual:

```text
UM originales: 38
parcelas oficiales: 10689
parcelas asignadas a UM: 10667
UM con cultivos: 34
parcelas rankeadas en UM: 9660
```

## Índices Y Variables Satelitales

El dataset temporal usa índices espectrales y bandas Sentinel-2. Variables
principales:

```text
NDVI, NDMI, NDWI, MSI, SAVI, NDRE,
GNDVI, EVI, BSI, NBR, MTCI, IRECI,
B2, B3, B4, B5, B6, B7, B8, B11, B12
```

Roles principales:

| Variable      | Uso                                            |
|---------------|------------------------------------------------|
| NDMI          | contenido de agua foliar                       |
| MSI           | estrés/sequedad; valor alto implica más riesgo |
| NDWI          | agua superficial/dosel                         |
| NBR           | sequedad/biomasa                               |
| NDVI          | vigor vegetativo                               |
| bandas crudas | señal espectral adicional                      |

## Dataset Temporal Operativo

Dataset principal:

```text
data/dataset_temporal_hidrico.csv
```

Estado actual:

```text
filas: 157820
columnas: 119
parcelas con historial: 13175
rango fechas: 2023-01-01 a 2024-12-31
vid filas: 114192
olivo filas: 43628
```

Nota:
el dataset temporal conserva observaciones históricas generadas antes de adoptar
el polígono exacto. El ranking operativo filtra esas observaciones contra
`data/parcelas/san_rafael_vid_olivo_wgs84.geojson`, reconstruido con el límite
local exacto.

Script principal:

```text
scripts/generar_dataset_temporal_hidrico.py
```

Comando base para regenerar/ampliar:

```bash
venv/bin/python scripts/generar_dataset_temporal_hidrico.py \
  --reuse-sample \
  --resume-from-max-date \
  --output data/dataset_temporal_hidrico.csv \
  --start-date 2023-01-01 \
  --end-date 2024-12-31 \
  --step-days 5 \
  --window-days 5 \
  --chunk-size 500
```

## Clasificación De Cultivos

La clasificación tuvo varias iteraciones, pero el estado vigente se resume así:

1. **Clasificador multiclass plano**
   - objetivo: clasificar `frutales`, `no_cultivo`, `olivo`, `vid`;
   - sirvió como benchmark frente al pipeline jerárquico;
   - quedó movido a `legacy/`;
   - no forma parte del pipeline operativo actual.

2. **Filtro vid/olivo**
   - objetivo: quedarse con parcelas compatibles con el dominio final;
   - fue útil metodológicamente para aislar vid/olivo;
   - en el flujo actual se reemplaza por etiquetas oficiales IDEMendoza;
   - queda como referencia histórica en `legacy/`.

Decisión vigente:

```text
El pipeline operativo no depende de modelos de clasificación.
Usa parcelas oficiales vid/olivo como universo de análisis.
```

Motivo:

- el producto final se limita a San Rafael;
- las parcelas de producción son conocidas;
- existe dataset oficial con tipo de cultivo;
- el foco actual es ranking y predicción hídrica, no clasificación general.

Código clasificador histórico:

```text
legacy/scripts/
legacy/app/services/
```

Los modelos `.pkl` de clasificación fueron eliminados del flujo operativo.

### Experimento TensorFlow

Se agregó una prueba aislada con red neuronal TensorFlow/Keras para evaluar si
conviene reabrir la línea de clasificación.

Archivo:

```text
backend/scripts/experiments/entrenar_clasificador_tensorflow.py
backend/scripts/experiments/entrenar_cnn_temporal_clasificacion.py
backend/scripts/experiments/generar_dataset_clasificacion_multiclase.py
backend/scripts/experiments/generar_dataset_clasificacion_wide.py
```

Decisiones:

- no reemplaza el pipeline operativo;
- usa `backend/data/dataset_temporal_hidrico.csv` por defecto;
- clasifica `vid` vs `olivo` en la primera prueba;
- valida con split por `parcela_id` para evitar fuga entre train/test;
- guarda artefactos regenerables en `backend/models/clasificador_tensorflow/`;
- TensorFlow queda como dependencia opcional en `requirements-tensorflow.txt`.

Resultado inicial con dataset completo:

```text
split: por parcela_id
features: 46
accuracy argmax: 0.811
macro F1 argmax: 0.750
threshold optimizado: 0.38
accuracy threshold: 0.838
macro F1 threshold: 0.767
olivo F1: 0.637
vid F1: 0.896
```

Lectura:

```text
TensorFlow es viable como experimento, pero no reemplaza todavía al flujo
operativo. Olivo sigue siendo la clase crítica a mejorar.
```

Prueba multiclase desde parcelario completo:

```text
fuente: backend/data/parcelas/san_rafael_completo_wgs84.geojson
clases: vid, olivo, frutales, incultos, anuales
muestra piloto: 100 parcelas por clase
fechas Sentinel-2: 2024-01-01, 2024-03-31, 2024-06-29, 2024-09-27
dataset temporal válido: 1741 filas
dataset wide: 500 parcelas
```

Resultados piloto:

```text
temporal suelto: accuracy 0.391, macro F1 0.380
wide all features: accuracy 0.450, macro F1 0.451
wide spectral regularizado: accuracy 0.460, macro F1 0.449
cnn temporal: accuracy 0.556, macro F1 0.553
```

Lectura:

```text
El flujo TensorFlow + GEE funciona sobre el parcelario crudo completo. La CNN
temporal es la arquitectura neuronal más prometedora, pero la métrica piloto
todavía no alcanza para usarla como clasificador multiclase operativo. La
confusión principal queda entre frutales, olivo y vid.
```

## Predictor Hídrico De Regresión

Decisión vigente:

```text
Se usan modelos de regresión separados por cultivo y horizonte.
```

Modelos operativos:

```text
models/hidrico_regresion/regresor_vid_5d_riesgo_hidrico_future_temporal.pkl
models/hidrico_regresion/regresor_vid_10d_riesgo_hidrico_future_temporal.pkl
models/hidrico_regresion/regresor_olivo_5d_riesgo_hidrico_future_temporal.pkl
models/hidrico_regresion/regresor_olivo_10d_riesgo_hidrico_future_temporal.pkl
```

Script de entrenamiento:

```text
scripts/experiments/entrenar_predictores_hidricos_regresion.py
```

Target principal:

```text
riesgo_hidrico_future
```

Horizontes:

```text
5 días
10 días
```

Motivo de separar por cultivo:

- vid y olivo tienen fenología diferente;
- la vid es más estacional y tiene mayor sensibilidad hídrica en verano;
- el olivo es perenne y más tolerante a sequía;
- un único modelo mezclaría dinámicas agronómicas distintas.

## Score Hídrico Satelital

El score `riesgo_hidrico` se construye como proxy relativo por cultivo y fecha.

Fórmula:

```text
R = 100 * (
      0.35 * P_bajo(NDMI)
    + 0.30 * P_alto(MSI)
    + 0.15 * P_bajo(NDWI)
    + 0.10 * P_bajo(NBR)
    + 0.10 * P_bajo(NDVI)
)
```

Interpretación:

- valores altos implican mayor prioridad relativa;
- compara parcelas dentro del mismo cultivo y fecha.

Archivo:

```text
scripts/generar_targets_hidricos_regresion.py
```

## Métricas Actuales De Regresión

Validación temporal:

| Cultivo | Horizonte | MAE  | RMSE | R2    | Spearman | Top10 overlap |
|---------|-----------|------|------|-------|----------|---------------|
| vid     | 5d        | 4.27 | 6.53 | 0.900 | 0.949    | 0.830         |
| vid     | 10d       | 5.68 | 8.34 | 0.835 | 0.914    | 0.782         |
| olivo   | 5d        | 3.72 | 5.53 | 0.927 | 0.964    | 0.806         |
| olivo   | 10d       | 4.75 | 6.98 | 0.883 | 0.940    | 0.766         |

Archivo:

```text
models/hidrico_regresion/metricas_regresion_temporal.csv
```

Lectura:

- el error medio está en torno a 3.7-5.7 puntos de score;
- la correlación ordinal es alta;
- el modelo sirve mejor para ranking relativo que para prometer exactitud
  absoluta parcela por parcela.

Validación histórica actualizada:

```text
backend/scripts/modeling/validar_ranking_hidrico_multifecha.py
backend/scripts/modeling/generar_reporte_validacion_predictor_hidrico.py
docs/validacion_predictor_hidrico.md
```

Resultado sobre 26 fechas entre `2023-01-11` y `2026-05-06`:

| Cultivo | Horizonte | MAE  | Spearman | Top10 overlap | Error <= 10 pts |
|---------|-----------|------|----------|---------------|-----------------|
| global  | 5d        | 4.08 | 0.958    | 0.835         | 92.1%           |
| global  | 10d       | 4.66 | 0.951    | 0.817         | 88.9%           |
| vid     | 5d        | 4.28 | 0.956    | 0.835         | 91.4%           |
| vid     | 10d       | 5.19 | 0.942    | 0.809         | 86.4%           |
| olivo   | 5d        | 3.66 | 0.965    | 0.864         | 93.7%           |
| olivo   | 10d       | 3.52 | 0.971    | 0.842         | 94.2%           |

Lectura vigente:

- el predictor mantiene muy bien el orden relativo de parcelas;
- el error absoluto es razonable para una herramienta de priorización;
- otoño concentra las fechas con mayor MAE;
- no debe comunicarse como "90% de accuracy", sino como error medio,
  correlación de ranking y porcentaje dentro de tolerancia.

## Ranking Hídrico

El ranking combina:

- riesgo actual;
- riesgo predicho a 5 días;
- riesgo predicho a 10 días;
- empeoramiento esperado.

Configuración vigente:

```text
models/ranking_hidrico_config.json
```

Pesos:

| Componente      | Peso |
|-----------------|------|
| riesgo_pred_10d | 0.25 |
| riesgo_pred_5d  | 0.15 |
| delta_10d_pos   | 0.30 |
| delta_5d_pos    | 0.00 |
| riesgo_actual   | 0.30 |

Umbrales:

| Prioridad | Umbral  |
|-----------|---------|
| critica   | >= 55.0 |
| alta      | >= 47.5 |
| media     | >= 35.0 |
| baja      | < 35.0  |

Validación multifecha usada para calibración:

```text
data/validacion_ranking_hidrico_multifecha_2024.csv
```

Métricas de calibración:

```text
spearman_5d: 0.964
spearman_10d: 0.939
top10_5d: 0.852
top10_10d: 0.814
```

Scripts:

```text
scripts/generar_ranking_hidrico.py
scripts/optimizar_ranking_hidrico.py
scripts/validar_ranking_hidrico_multifecha.py
```

## Proyección Operativa Para Cliente

Decisión vigente:

```text
Mantener separadas la predicción ML cruda y la proyección operativa.
```

Motivo:

- los modelos `riesgo_pred_5d` y `riesgo_pred_10d` aprenden del histórico real;
- en el histórico puede haber mejoras por riego, lluvia o recuperación entre
  imágenes;
- para el cliente se quiere comunicar el escenario conservador de continuidad:
  si la condición no mejora, el riesgo proyectado debe subir o mantenerse.

Columnas nuevas:

```text
riesgo_operativo_5d
riesgo_operativo_10d
delta_operativo_5d
delta_operativo_10d
tendencia_reciente_5d
pendiente_operativa_5d
factor_estacional
```

Reglas:

```text
riesgo_operativo_5d >= riesgo_actual
riesgo_operativo_10d >= riesgo_operativo_5d
riesgo_operativo_5d >= riesgo_pred_5d
riesgo_operativo_10d >= riesgo_pred_10d
```

La pendiente operativa toma en cuenta:

- tendencia reciente de la parcela, con más peso en la ventana de 5 días que en
  la de 10 días;
- prioridad actual;
- cultivo (`vid` más sensible que `olivo`);
- estación del año.

Factores vigentes:

| Factor | Vid | Olivo |
|--------|-----|-------|
| cultivo | 1.15 | 0.75 |
| verano | 1.30 | 1.10 |
| primavera | 1.15 | 1.00 |
| otoño | 0.85 | 0.80 |
| invierno | 0.45 | 0.65 |

Pendiente mínima cada 5 días:

| Prioridad | Puntos |
|-----------|--------|
| baja      | 0.5    |
| media     | 1.5    |
| alta      | 3.0    |
| critica   | 4.0    |

Implementación:

```text
scripts/generar_ranking_hidrico.py
función: agregar_proyeccion_operativa()
```

Uso en dashboard:

- admin: muestra predicción ML cruda y campos técnicos;
- cliente: muestra proyección operativa;
- no se agrega recomendación automática de riego.

## Estado Actual Del Ranking

Ranking latest:

```text
data/rankings/ranking_hidrico_latest.csv
fecha objetivo: 2026-05-26
parcelas rankeadas: 9679
vid: 9273
olivo: 406
criterio: última observación válida por parcela hasta 15 días hacia atrás
```

Antigüedad real de lectura:

```text
0 días: 5148
5 días: 4528
10 días: 3
```

Distribución de prioridad:

| Prioridad | Parcelas |
|-----------|----------|
| baja      | 4841     |
| media     | 2592     |
| alta      | 1350     |
| critica   | 896      |

## Cobertura De Parcelas

Universo oficial vid/olivo:

```text
parcelas oficiales: 10689
vid: 10126
olivo: 563
```

Estado actual:

| Estado                           | Parcelas |
|----------------------------------|----------|
| rankeada                         | 9679     |
| sin_historial                    | 1010     |

Por cultivo:

| Cultivo | Rankeada | Con historial sin latest | Sin historial |
|---------|----------|--------------------------|---------------|
| vid     | 9273     | 0                        | 853           |
| olivo   | 406      | 0                        | 157           |

Cobertura latest:

| Cultivo | Cobertura |
|---------|-----------|
| vid     | 91.58%    |
| olivo   | 72.11%    |

Scripts:

```text
scripts/auditar_cobertura_parcelas.py
scripts/auditar_sin_ranking.py
```

## Auditoría De Parcelas Sin Ranking

Total sin ranking:

```text
1010
```

Causas probables:

| Causa                                      | Parcelas |
|--------------------------------------------|----------|
| excluida_por_area_menor_4000m2             | 1010     |

Interpretación:

- las 4531 parcelas que antes quedaban afuera por no tener observación exacta
  en `2026-05-26` ahora se rankean usando su última lectura válida reciente;
- las 1010 restantes no entran por diseño porque tienen área menor a `4000 m2`.

Evaluación del cambio `5000 -> 4000 m2`:

```text
parcelas oficiales entre 4000 y 5000 m2: 273
vid: 235
olivo: 38
observaciones latest válidas extraídas: 244
rankeadas nuevas: 244
```

Distribución de las 244 nuevas rankeadas:

| Cultivo | Parcelas |
|---------|----------|
| vid     | 212      |
| olivo   | 32       |

| Prioridad | Parcelas |
|-----------|----------|
| baja      | 136      |
| media     | 70       |
| alta      | 28       |
| critica   | 10       |

Salidas:

```text
data/auditoria_sin_ranking_detalle.csv
data/auditoria_sin_ranking_resumen.csv
data/auditoria_sin_ranking_detalle.geojson
```

## Auditoría Espacial Por Vecinos

Se agregó:

```text
scripts/auditar_vecinos_ranking.py
```

Objetivo:
detectar parcelas rankeadas cuyo score difiere demasiado de parcelas vecinas.
Esto no modifica el ranking; solo marca posibles outliers para revisión.

Parámetros usados:

```text
vecinos: mismo cultivo
k: 6
distancia máxima: 500 m
mínimo de vecinos para evaluar: 3
umbral de outlier: 35 puntos contra mediana vecinal
```

Auditoría sobre `prioridad_score`:

```text
parcelas rankeadas: 8711
parcelas evaluables: 7345
outliers espaciales: 42
outliers sobre evaluables: 0.57%
```

Tipos:

```text
score_mucho_mas_alto_que_vecinos: 29
score_mucho_mas_bajo_que_vecinos: 13
```

Auditoría sobre `riesgo_actual`:

```text
parcelas rankeadas: 8711
parcelas evaluables: 7345
outliers espaciales: 482
outliers sobre evaluables: 6.56%
```

Tipos:

```text
score_mucho_mas_alto_que_vecinos: 257
score_mucho_mas_bajo_que_vecinos: 225
```

Interpretación:

- el score final calibrado es espacialmente más estable que el riesgo actual;
- los saltos fuertes que se observan visualmente existen sobre todo en
  `riesgo_actual`;
- antes de suavizar conviene usar estos flags como `outlier_espacial` o
  componente de confianza;
- no se debe reemplazar el score original sin revisar si el outlier responde a
  ruido, geometría, sombra/nube o manejo real diferente.

Salidas principales:

```text
data/auditoria_vecinos_ranking_prioridad_score.csv
data/auditoria_vecinos_ranking_prioridad_score_resumen.csv
data/auditoria_vecinos_ranking_prioridad_score.geojson
data/auditoria_vecinos_ranking_riesgo_actual.csv
data/auditoria_vecinos_ranking_riesgo_actual_resumen.csv
data/auditoria_vecinos_ranking_riesgo_actual.geojson
```

## Auditoría Temporal De Outliers

Se agregó:

```text
scripts/auditar_outliers_temporales.py
```

Objetivo:
tomar los outliers espaciales de `riesgo_actual` y revisar si el salto es
persistente en el historial de la misma parcela o si parece un evento puntual.

Entradas:

```text
data/auditoria_vecinos_ranking_riesgo_actual.csv
data/dataset_temporal_hidrico.csv
```

Salidas:

```text
data/auditoria_outliers_temporales.csv
data/auditoria_outliers_temporales_resumen.csv
```

Resultado:

```text
outliers auditados: 482
persistente: 388
puntual: 68
sin_historial_reciente: 26
```

Diagnóstico:

| Diagnóstico                                  | Parcelas |
|----------------------------------------------|----------|
| probable_manejo_real_o_condicion_persistente | 346      |
| indeterminado                                | 65       |
| probable_ruido_o_lectura_puntual             | 45       |
| indeterminado_sin_historial_reciente         | 26       |

La auditoría temporal usa historial reciente ponderado:

```text
t-5 pesa más que t-10
t-10 pesa más que t-15
t-15 pesa más que t-20
```

Implementación:

```text
peso_temporal = 5 / max(dias_previos, 5)
ventana reciente por defecto: 45 días
```

Campos incorporados:

```text
historial_reciente_count
historial_reciente_min_dias
historial_reciente_max_dias
riesgo_reciente_weighted_mean
riesgo_vs_reciente_weighted_mean
```

Interpretación:

- Se ejecutó backfill inicial sobre outliers previos. Tras incorporar parcelas
  de 4000-5000 m2 aparecieron 26 outliers nuevos sin historial reciente.
- Hay 346 outliers persistentes con soporte espectral suficiente; no conviene
  suavizarlos automáticamente porque podrían representar manejo real o una
  condición sostenida.
- 45 casos aparecen como probable ruido o lectura puntual bajo las reglas
  actuales.
- La mejora prioritaria sigue siendo exponer confianza/diagnóstico y no
  reemplazar el score automáticamente.

## Pipeline Operativo

Entrada principal:

```text
scripts/run_pipeline_hidrico.py
```

Uso local:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py --mode local
```

Uso cloud previsto:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py \
  --mode cloud \
  --update-sentinel \
  --skip-if-no-new-date \
  --load-postgis
```

El pipeline:

1. opcionalmente actualiza Sentinel/GEE;
2. genera ranking latest;
3. guarda CSV local;
4. opcionalmente ejecuta auditorías de calidad;
5. guarda snapshot local de auditorías por fecha;
6. opcionalmente carga PostGIS.

### Snapshots Históricos De Auditorías

Además de mantener archivos `latest`, el pipeline guarda una copia por fecha en:

```text
data/auditorias/<fecha_rankeada>/
```

Para `2024-12-31` quedó:

```text
data/auditorias/2024-12-31/auditoria_vecinos_ranking_riesgo_actual.csv
data/auditorias/2024-12-31/auditoria_vecinos_ranking_riesgo_actual_resumen.csv
data/auditorias/2024-12-31/auditoria_vecinos_ranking_riesgo_actual.geojson
data/auditorias/2024-12-31/auditoria_outliers_temporales.csv
data/auditorias/2024-12-31/auditoria_outliers_temporales_resumen.csv
data/auditorias/2024-12-31/auditoria_ruido_puntual_detalle.csv
data/auditorias/2024-12-31/auditoria_ruido_puntual_resumen.csv
data/auditorias/2024-12-31/auditoria_ruido_puntual_detalle.geojson
data/auditorias/2024-12-31/metadata.json
```

Motivo:

- los outliers son dinámicos y pueden cambiar en cada fecha Sentinel;
- `latest` sirve para dashboard operativo;
- el snapshot por fecha permite comparar recurrencia, desaparición y aparición
  de outliers a lo largo del tiempo.

Parámetro:

```text
--audit-history-dir data/auditorias
```

### Métricas Históricas Por Parcela

Se agregó:

```text
scripts/generar_metricas_historicas_auditorias.py
```

Entrada:

```text
data/auditorias/*/
```

Salida:

```text
data/auditoria_metricas_historicas.csv
```

Campos:

```text
outlier_count_30d
persistente_count_30d
ruido_count_30d
ultima_fecha_outlier
ultima_fecha_persistente
ultima_fecha_ruido
dias_desde_ultimo_outlier
dias_desde_ultimo_persistente
dias_desde_ultimo_ruido
```

Resultado actual con referencia `2026-05-26` y ventana de 30 días:

```text
filas: 590
parcelas con outlier: 590
parcelas con persistencia: 517
parcelas con ruido: 59
```

Interpretación:

- hoy los conteos todavía son simples porque hay pocos snapshots operativos;
- cuando el pipeline corra sobre nuevas fechas Sentinel, estos campos van a
  permitir distinguir outliers nuevos de recurrentes;
- la API local y el dashboard incorporan estas columnas al GeoJSON.

### Modo Ventana Reciente

Se agregó al orquestador:

```text
--update-recent-window
--recent-days
--extract-window-days
--extract-step-days
--extract-cloud-threshold
--extract-output-sample
--resolve-latest-valid-date / --no-resolve-latest-valid-date
--latest-lookback-days
--latest-min-images
```

Objetivo:
preparar el pipeline para trabajar con ventanas recientes tipo:

```text
latest
latest - 5 días
latest - 10 días
```

Uso previsto:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py \
  --mode cloud \
  --update-sentinel \
  --update-recent-window \
  --recent-days 10 \
  --extract-chunk-size 250 \
  --skip-if-no-new-date
```

Con `--update-recent-window`, el orquestador llama a:

```text
scripts/generar_dataset_temporal_hidrico.py
```

con:

```text
--all-target-parcels
--start-date = extract_end_date - recent_days
--end-date = extract_end_date o fecha actual
--step-days = 5 por defecto
--window-days = 5 por defecto
```

Esto permite asegurar observaciones recientes para auditar saltos temporales,
sin reextraer todo el histórico.

Resolución de última fecha válida:

```text
En ejecución real, el pipeline no usa "hoy" directamente.
Primero consulta GEE hacia atrás hasta encontrar una ventana Sentinel válida.
Esa fecha se usa como t.
```

La búsqueda usa:

```text
lookback: 30 días por defecto
min_images: 1 por defecto
cloud_threshold: 35 por defecto
window_days: 5 por defecto
```

Si no encuentra una ventana válida, falla explícitamente en vez de generar un
ranking con una fecha sin imágenes.

Verificación dry-run:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py \
  --mode local \
  --update-sentinel \
  --update-recent-window \
  --recent-days 10 \
  --extract-end-date 2026-05-31 \
  --extract-chunk-size 250 \
  --dry-run
```

Comando GEE generado:

```text
scripts/generar_dataset_temporal_hidrico.py
--start-date 2026-05-16
--end-date 2026-05-26
--step-days 5
--window-days 5
--chunk-size 250
--cloud-threshold 35.0
--resume
--all-target-parcels
```

Ese rango genera ventanas cerradas hacia atrás:

```text
2026-05-16 -> 2026-05-21
2026-05-21 -> 2026-05-26
2026-05-26 -> 2026-05-31
```

Resultado:
dry-run OK. No se consultó GEE ni se modificó el dataset. En dry-run se informa
que no se resuelve `latest` contra GEE y se usa la fecha objetivo provista.

Verificación real con GEE sobre la última fecha disponible:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py \
  --mode local \
  --update-sentinel \
  --update-recent-window \
  --recent-days 10 \
  --backfill-outlier-history \
  --skip-if-no-new-date
```

Resultado operativo:

```text
fecha objetivo consultada: 2026-05-31
última ventana Sentinel válida: 2026-05-26 -> 2026-05-31
imágenes Sentinel válidas: 11
fecha rankeada: 2026-05-26
```

Se incorporaron las ventanas recientes:

```text
2026-05-16 -> 2026-05-21
2026-05-21 -> 2026-05-26
2026-05-26 -> 2026-05-31
```

El `ranking_hidrico_latest.csv` quedó apuntando a `2026-05-26`.

## API

API mínima:

```text
app/main.py
app/services/rankings.py
```

Endpoints:

```text
GET /health
GET /rankings/latest
GET /rankings/latest/geojson
GET /rankings/{fecha}
GET /clientes
GET /clientes/{cliente_id}/rankings/latest/geojson
GET /regional/um/latest
GET /regional/um/latest/geojson
GET /regional/um/{um_id}/parcelas/latest/geojson
```

Decisión vigente:

- si existe `DATABASE_URL`, usa PostGIS;
- si no existe, usa fallback local CSV/GeoJSON;
- `/rankings/latest/geojson` devuelve las 10689 parcelas oficiales vid/olivo
  dentro del límite exacto;
- parcelas no rankeadas salen como:

```text
estado_cobertura = sin_ranking_latest
prioridad = sin ranking
```

Esto permite visualización completa del universo oficial sin inventar scores.

### Roles Y Productores

Decisión:

```text
El dashboard se separa en vistas Admin, Productor y Regional.
Las vistas productor deben filtrar parcelas desde backend/PostGIS.
```

Roles previstos:

```text
admin
productor
regional
```

Modelo agregado:

```text
clientes
usuarios
cliente_parcela
```

Lectura vigente:

```text
clientes/cliente_id se mantiene solo como compatibilidad interna.
La entidad de producto es productor -> parcelas asignadas.
No se modelan campos como entidad funcional del sistema.
```

Endpoint operativo para cliente:

```text
GET /clientes/{cliente_id}/rankings/latest/geojson
```

Comportamiento:

- devuelve solo parcelas asociadas al productor;
- conserva parcelas sin ranking latest;
- en PostGIS filtra por `cliente_parcela`;
- en fallback local usa `data/clientes/clientes.csv` y
  `data/clientes/cliente_parcela.csv`.

Documentación:

```text
docs/roles_clientes.md
```

Endpoints regionales:

- usan PostGIS si existe `DATABASE_URL`;
- usan fallback local si no existe `DATABASE_URL`;
- alimentan la vista Regional del dashboard;
- permiten listar UM, mapear UM y abrir drill-down de parcelas por UM.

Validación API local:

```text
servidor: uvicorn app.main:app --host 127.0.0.1 --port 8011
fecha de prueba: 2026-06-01
```

Resultados:

| Endpoint                                 | Tiempo | Tamaño   | Count |
|------------------------------------------|--------|----------|-------|
| `/health`                                | 0.028s | 0.00 MB  | -     |
| `/rankings/latest?limit=5`               | 0.047s | 0.00 MB  | 5     |
| `/rankings/latest/geojson`               | 2.307s | 25.15 MB | 10689 |
| `/regional/um/latest`                    | 0.008s | 0.02 MB  | 34    |
| `/regional/um/latest/geojson`            | 0.031s | 0.12 MB  | 34    |
| `/regional/um/0/parcelas/latest/geojson` | 2.118s | 0.14 MB  | 59    |
| `/clientes`                              | 0.018s | 0.00 MB  | 2     |

Observación:

```text
El endpoint de parcelas por UM pesa poco, pero tarda porque el fallback local
arma primero el GeoJSON completo de parcelas y luego filtra.
```

Mejora pendiente:

```text
Optimizar /regional/um/{um_id}/parcelas/latest/geojson para leer y cruzar
solo las parcelas de la UM solicitada.
```

Mejora aplicada:

```text
regional_um_parcelas_latest_geojson_from_csv ahora usa
latest_geojson_subset_from_csv(parcelas_de_la_um)
```

Ya no construye `/rankings/latest/geojson` completo antes de filtrar.

Medición posterior:

| Endpoint                                  | Tiempo | Tamaño | Parcelas |
|-------------------------------------------|--------|--------|----------|
| `/regional/um/0/parcelas/latest/geojson`  | 0.367s | 0.14 MB | 59      |
| `/regional/um/2/parcelas/latest/geojson`  | 0.427s | 1.32 MB | 565     |
| `/regional/um/10/parcelas/latest/geojson` | 0.497s | 2.46 MB | 1046    |

## Dashboard

Dashboard:

```text
streamlit_app.py
frontend/auth.py
frontend/constants.py
frontend/data.py
frontend/logic.py
frontend/map.py
frontend/panels.py
frontend/views/dashboard.py
frontend/views/regional.py
```

Stack:

```text
Streamlit 1.57.0
Plotly
```

Decisiones vigentes:

- mapa interactivo con todas las parcelas oficiales vid/olivo;
- rankeadas coloreadas por prioridad;
- no rankeadas en gris;
- panel de predicción solo para parcelas rankeadas;
- métricas visibles de evaluadas y sin ranking.
- login local de desarrollo antes de cargar datos pesados;
- selector de vista `Admin` / `Productor` / `Regional` dentro de la sesión;
- vista productor filtrada por backend usando relación `cliente_parcela`;
- vista productor sin pestaña de revisión técnica.
- vista regional operativa por UM DGI recortada a San Rafael;
- vista regional con foco en UM, cobertura, composición vid/olivo, aumento
  proyectado y concentración alta/crítica;
- vista admin separa análisis de datos y gestión de usuarios/productores/parcelas;
- la pestaña Productores permite asignar parcelas analizables sin productor,
  verificar la vista resultante y desasignar parcelas;
- la primera pantalla mantiene accesos rápidos `Productor vid`, `Productor olivo`,
  `Admin` y `Regional` para desarrollo;
- la vista productor no recomienda riego; muestra detección/proyección de estrés
  para que el productor tome la decisión con su propio criterio.
- al cambiar de productor se limpia la parcela seleccionada y el mapa se centra
  en sus parcelas visibles.

Usuarios demo:

| Email | Contraseña | Vista |
|---|---|---|
| admin@osmosense.local | admin123 | Admin |
| productor.vid@osmosense.local | cliente123 | Productor vid |
| productor.olivo@osmosense.local | cliente123 | Productor olivo |
| regional@osmosense.local | regional123 | Regional |

Refactor iniciado:

```text
frontend/
```

Separación vigente:

- `streamlit_app.py`: entrypoint mínimo;
- `frontend/auth.py`: login, logout y sesión PostGIS;
- `frontend/data.py`: carga API/local y normalización;
- `frontend/logic.py`: reglas testeables;
- `frontend/map.py`: mapa y hover;
- `frontend/table_config.py`: columnas visibles, labels y restricciones por rol;
- `frontend/components/client_overview.py`: estado general de parcelas en vista productor;
- `frontend/components/metrics.py`: métricas resumen;
- `frontend/components/parcel_detail.py`: detalle y pop-up de parcela;
- `frontend/components/tables.py`: tablas y resúmenes tabulares;
- `frontend/components/charts.py`: gráficos;
- `frontend/panels.py`: fachada de compatibilidad para componentes;
- `frontend/views/dashboard.py`: composición de la vista;
- `frontend/views/dashboard_filters.py`: filtros y selección de vista;
- `frontend/views/admin/`: gestión admin de usuarios, productores y parcelas;
- `frontend/views/regional.py`: mapa, foco regional y drill-down de UM.

Vista regional:

- consume `data/zonificacion/um_con_cultivos.geojson`;
- muestra solo UM con parcelas oficiales de vid/olivo;
- permite filtrar por cuenca, prioridad regional y mínimo de parcelas;
- permite categorizar por umbrales fijos o por percentiles relativos dentro de
  las UM visibles;
- permite colorear por prioridad regional, score promedio, `% alta/crítica` o
  superficie cultivada;
- muestra métricas de UM, parcelas, cobertura de ranking y superficie cultivada;
- muestra tabla `ranking_um` con score regional, riesgo actual, riesgo a 10 días,
  delta esperado y composición vid/olivo.
- al seleccionar una UM en el mapa, abre detalle con fecha de ranking, score
  regional, riesgos agregados, tendencia, composición vid/olivo y cobertura.
- agrega drill-down `Parcelas de la UM` para ver las parcelas que explican la UM
  seleccionada, tabla de ranking y mapa filtrado.

Integración pipeline:

```text
scripts/run_pipeline_hidrico.py --update-zonificacion-um
```

`--update-zonificacion-um` queda activo por defecto y ejecuta:

```text
scripts/cruzar_parcelas_zonificacion_um.py
```

después de generar `ranking_hidrico_latest.csv`.

Para omitirlo:

```text
--no-update-zonificacion-um
```

PostGIS regional:

```text
sql/schema_postgis.sql
scripts/cargar_zonificacion_um_postgis.py
```

Tablas:

```text
zonas_um
parcela_um
ranking_um
```

Vistas:

```text
ranking_um_latest
ranking_um_latest_geo
```

## PostGIS Local

Se agregó entorno local reproducible:

```text
docker-compose.postgis.yml
.env.postgis.example
```

Imagen:

```text
postgis/postgis:17-3.6-alpine
```

Nota:

```text
PostGIS vigente en esta imagen es 3.6; no 1.0.4.
```

Comandos:

```bash
docker compose -f docker-compose.postgis.yml up -d
venv/bin/python scripts/setup_postgis_local.py
venv/bin/python scripts/validar_postgis_local.py
```

Scripts agregados:

```text
scripts/setup_postgis_local.py
scripts/validar_postgis_local.py
```

Validación local:

```text
parcelas: 10689
ranking_hidrico_latest: 9679
clientes: 2
cliente_parcela: 28
zonas_um: 34
parcela_um: 10667
ranking_um_latest: 34
postgis_version: 3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1
```

Observación:

```text
Se omitió 1 relación demo cliente-parcela porque la parcela 43241 no existe
en el universo oficial actual cargado en PostGIS.
```

Validación API con `DATABASE_URL`:

| Endpoint | Source | Tiempo | Tamaño | Count |
|----------|--------|--------|--------|-------|
| `/rankings/latest?limit=5` | postgis | 0.076s | 0.00 MB | 5 |
| `/regional/um/latest` | postgis | 0.013s | 0.02 MB | 34 |
| `/regional/um/latest/geojson` | postgis | 0.076s | 0.07 MB | 34 |
| `/regional/um/0/parcelas/latest/geojson` | postgis | 0.036s | 0.07 MB | 59 |
| `/clientes` | postgis | 0.012s | 0.00 MB | 2 |

Optimización del mapa admin:

```text
data/parcelas/san_rafael_vid_olivo_dashboard.geojson
scripts/generar_geojson_dashboard_parcelas.py
```

Decisión:

- mantener `data/parcelas/san_rafael_vid_olivo_wgs84.geojson` como geometría
  operativa/catastral;
- usar el GeoJSON `dashboard` como geometría preferida para visualización;
- simplificar geometrías con tolerancia de 2 m;
- conservar solo `fid`, `cultivo`, `area_m2` y geometría en ese archivo;
- enviar a Plotly solo geometría + `parcela_id`; el hover usa el DataFrame.

Resultado:

```text
GeoJSON parcelas original: 7.52 MB
GeoJSON dashboard: 4.42 MB
GeoJSON usado por Plotly: 3.45 MB
reducción efectiva frente al payload completo del mapa: 86.3%
```

Tests frontend agregados:

```text
tests/test_frontend_logic.py
```

Validan:

- cliente usa `riesgo_operativo_*`;
- admin usa `riesgo_pred_*`;
- la prioridad relativa no modifica `prioridad_score`;
- el hover del cliente usa proyección operativa;
- cliente no expone columnas técnicas en tabla;
- admin conserva columnas técnicas y predicciones crudas;
- las columnas visibles usan labels legibles;
- el estado general del campo usa la proyección operativa;
- la vista productor separa parcelas con mayor riesgo actual de parcelas con
  mayor aumento esperado a 10 días;
- el selector de parcela del cliente no muestra ranking ni score;
- el hover del mapa cliente no muestra ranking, score ni campos técnicos.

Ejecución:

```bash
venv/bin/streamlit run streamlit_app.py
```

## PostGIS Y Cloud

Decisión:

```text
PostGIS será el storage geoespacial operativo.
```

Archivos:

```text
sql/schema_postgis.sql
scripts/aplicar_schema_postgis.py
scripts/cargar_parcelas_postgis.py
scripts/cargar_ranking_postgis.py
scripts/cargar_clientes_parcelas_postgis.py
docs/postgis.md
```

UM-Cloud:

```text
docs/UM_Cloud_Setup_Guide.md
docs/arquitectura_cloud_pipeline.md
```

Estado:

- schema y scripts preparados;
- carga integrada al orquestador;
- despliegue completo queda para cuando el flujo local esté estable.

## Artefactos Operativos

Mantener:

```text
data/parcelas/parcelas_ide.geojson
data/parcelas/san_rafael_vid_olivo_wgs84.geojson
data/parcelas/muestra_temporal_full_vid_olivo.geojson
data/dataset_temporal_hidrico.csv
data/rankings/ranking_hidrico_latest.csv
models/ranking_hidrico_config.json
models/hidrico_regresion/*.pkl
models/hidrico_regresion/metricas_regresion_temporal.csv
```

No versionar en Git:

- CSV grandes;
- GeoJSON derivados;
- modelos `.pkl`;
- rankings;
- logs;
- state local.

Esto está cubierto por `.gitignore`.

## Código Legacy

Se creó:

```text
legacy/
```

Objetivo:

- conservar historia técnica;
- evitar confusión en `scripts/`;
- no borrar código que puede servir para la memoria o comparación.

No usar `legacy/` en el flujo operativo actual sin revisar paths y artefactos.

Inventario:

```text
docs/inventario_codigo.md
```

## Tests Y Verificación

Suite vigente:

```text
tests/test_auth.py
tests/test_api_handlers.py
tests/test_frontend_logic.py
tests/test_map_animation.py
tests/test_rankings_service.py
```

Comando:

```bash
venv/bin/python -m pytest -q
```

Último resultado:

```text
76 passed
```

Smokes operativos no destructivos:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
venv/bin/python backend/scripts/postgis/smoke_test_productor.py
venv/bin/python backend/scripts/postgis/smoke_test_regional.py
```

Últimos resultados de smoke contra API local:

```text
smoke productor: OK
smoke regional: OK
```

Decisión corregida:

```text
La animación de riesgo del productor usa categorías absolutas por defecto.
No debe recolorear por posición relativa entre parcelas.
El escenario sin riego no muestra mejoras artificiales.
```

## Auditoría De Calidad Del Ranking

El pipeline puede ejecutar auditorías posteriores al ranking con:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py --mode local --run-quality-audits
```

Esto agrega dos controles sobre la lectura actual:

- auditoría espacial por vecinos cercanos usando `riesgo_actual`;
- auditoría temporal de los outliers espaciales contra el historial disponible.

Archivos generados:

```text
data/auditoria_vecinos_ranking_riesgo_actual.csv
data/auditoria_vecinos_ranking_riesgo_actual_resumen.csv
data/auditoria_vecinos_ranking_riesgo_actual.geojson
data/auditoria_outliers_temporales.csv
data/auditoria_outliers_temporales_resumen.csv
```

Última ejecución local:

```text
ranking latest: 2026-05-26
parcelas oficiales vid/olivo: 10689
rankeadas: 9679
sin ranking: 1010
outliers espaciales sobre riesgo_actual: 590
outliers evaluables: 8237
outliers/evaluables: 7.16%
```

Distribución de ranking:

```text
baja: 4841
media: 2592
alta: 1350
critica: 896
```

Diagnóstico temporal de los 590 outliers:

```text
persistente: 517
puntual: 73

indeterminado: 350
probable_manejo_real_o_condicion_persistente: 181
probable_ruido_o_lectura_puntual: 59
```

Backfill inicial:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py \
  --mode local \
  --backfill-outlier-history
```

Con `fecha_rankeada = 2026-05-26`, el pipeline arma:

```text
outliers objetivo: 590
start: 2026-04-11
end: 2026-05-21
step: 5 días
window: 5 días
```

Resultado del backfill ejecutado:

```text
filas antes: 187225
filas después del guardado parcial: 189481
observaciones válidas finales: 188909
outliers con historial ponderado: 590
```

Esto rellena historia reciente previa a `latest` para poder distinguir:

```text
salto puntual
condición persistente
probable ruido de lectura
```

Regla de ponderación temporal:

```text
peso_temporal = 5 / max(dias_previos, 5)
```

Ejemplos:

```text
t-5  -> peso 1.00
t-10 -> peso 0.50
t-15 -> peso 0.33
t-20 -> peso 0.25
```

La API local (`app/services/rankings.py`) incorpora estos campos al GeoJSON cuando los CSV existen:

```text
outlier_espacial
tipo_outlier_espacial
neighbor_count
neighbor_riesgo_actual_median
riesgo_actual_vs_neighbor_median
persistencia_temporal
diagnostico_outlier
historial_reciente_count
riesgo_reciente_weighted_mean
riesgo_vs_reciente_weighted_mean
motivo_ruido
severidad_ruido
accion_recomendada
confianza_lectura
confianza_motivo
fecha_lectura
dias_desde_lectura
```

Criterio de `confianza_lectura`:

```text
alta: lectura normal reciente o outlier persistente con soporte temporal
media: lectura de 6 a 10 días, outlier espacial indeterminado o pocos vecinos
baja: lectura de más de 10 días o probable ruido/lectura puntual
sin_ranking: parcela oficial sin ranking latest
```

Distribución actual:

```text
alta: 7827
media: 1793
baja: 59
sin_ranking: 1010
```

El dashboard muestra estos campos en métricas, hover del mapa, filtro de confianza, panel de parcela y tabla de ranking.

Mejora de revisión incorporada:

```text
filtros operativos por cultivo, prioridad, confianza y ranking
selector de color del mapa: prioridad / confianza
switch técnico "Solo casos a revisar"
panel "Casos a revisar"
```

Decisión UX:

```text
diagnostico_outlier, motivo_ruido y accion_recomendada no son filtros
principales del usuario final.
```

Motivo:

- son señales técnicas para explicar la decisión y auditar calidad;
- el usuario operativo debe ver prioridad, confianza y recomendación resumida;
- los campos técnicos quedan disponibles en detalle de parcela, revisión y datos.

Mejora de usabilidad:

```text
dashboard organizado en pestañas:
- Estado
- Mapa operativo
- Revisión técnica
- Cobertura
- Datos
```

Decisión de performance para admin:

```text
La vista admin no carga todas las prioridades por defecto.
El mapa operativo inicia con prioridad alta + crítica.
```

Resultado actual:

```text
parcelas totales: 10689
parcelas visibles por defecto en admin: 2242
alta: 1348
critica: 894
```

El usuario puede activar `Mostrar todas las prioridades` para cargar el universo
completo cuando lo necesite.

El mapa permite seleccionar una parcela. Al seleccionar una parcela se abre un
detalle con:

```text
riesgo actual
proyección 5 días
proyección 10 días
ranking
confianza de lectura
diagnóstico
motivo de la lectura
criterio técnico de auditoría
historial de outliers 30d
```

Categorización visual:

```text
Umbrales fijos:
  usa la prioridad guardada por el ranking.

Relativa por percentiles:
  crítica = top 10% por score dentro de la fecha
  alta    = siguiente 20%
  media   = siguiente 30%
  baja    = resto evaluado
```

La categorización relativa es solo visual en el dashboard; no modifica:

```text
prioridad_score
ranking_global
ranking_por_cultivo
prioridad guardada
```

El panel "Casos a revisar" prioriza:

```text
1. revisar_visual_antes_de_suavizar
2. bajar_confianza_y_revisar_geometria
3. bajar_confianza_no_suavizar_score
4. mantener_alerta
5. otros outliers espaciales
```

Cantidad actual de casos de revisión visibles con todos los filtros abiertos:

```text
464
```

### Auditoría Específica De Ruido Puntual

Se agregó:

```text
scripts/auditar_ruido_puntual.py
```

Objetivo:
analizar únicamente los casos `probable_ruido_o_lectura_puntual` para decidir
si conviene suavizar, bajar confianza o revisar geometría.

Salidas:

```text
data/auditoria_ruido_puntual_detalle.csv
data/auditoria_ruido_puntual_resumen.csv
data/auditoria_ruido_puntual_detalle.geojson
```

Resultado actual:

```text
casos: 59
```

Por motivo:

| Motivo                                     | Parcelas |
|--------------------------------------------|----------|
| sin_soporte_espectral_y_sin_salto_temporal | 38       |
| salto_vecinal_sin_confirmacion_temporal    | 9        |
| salto_temporal_puntual_relevante           | 5        |
| lectura_puntual_indeterminada              | 5        |
| bajo_soporte_y_pocos_pixeles               | 2        |

Acción recomendada:

| Acción                              | Parcelas |
|-------------------------------------|----------|
| bajar_confianza_no_suavizar_score   | 47       |
| revisar_visual_antes_de_suavizar    | 5        |
| mantener_alerta                     | 5        |
| bajar_confianza_y_revisar_geometria | 2        |

Decisión:

```text
No suavizar automáticamente el score todavía.
```

Motivo:

- 47 casos parecen problemas de confirmación/confianza, no de valor a corregir;
- 5 casos tienen salto temporal puntual relevante y requieren revisión visual;
- 2 casos apuntan a pocos píxeles o posible geometría problemática;
- el score observado debe conservarse y la acción operativa debe apoyarse en
  `confianza_lectura`, `motivo_ruido` y `accion_recomendada`.

## Dependencias

Dependencias directas actuales:

```text
requirements.txt
```

Decisiones:

- `geemap` y `rasterio` fueron removidos porque no se usan en el flujo actual;
- `scipy` se agregó porque se usa para `spearmanr`;
- `psycopg[binary]` queda declarado para PostGIS;
- el fallback local puede correr sin PostGIS.

## Roles Y Usuarios

Roles operativos vigentes:

```text
admin
regional
productor
```

Decisiones:

- se reemplazó la nomenclatura de roles `cliente_particular` y
  `cliente_regional` por `productor` y `regional`;
- la tabla `clientes` y el campo `cliente_id` se mantienen por ahora como
  estructura interna de asociación productor/campo-parcela;
- el schema PostGIS migra roles antiguos a los nuevos al reaplicarse;
- el dashboard Admin incorpora una pestaña `Usuarios`;
- el API expone `GET/POST/PUT/DELETE /admin/usuarios`;
- `DELETE /admin/usuarios/{id}` es baja lógica: desactiva el acceso y conserva
  trazabilidad;
- el backend impide desactivar o cambiar de rol al último admin activo;
- los productores activos requieren `email`, `nombre`, `apellido`, `DNI` y
  contraseña; se pueden crear sin parcelas y asignarlas después;
- la pestaña `Productores` permite asignar parcelas por mapa o por IDs y
  desasignar relaciones en lote;
- el área Admin `Análisis` usa navegación lazy por sección, no `st.tabs`, para
  evitar renderizar mapa y tablas pesadas cuando no están visibles;
- el mapa Admin usa geometría optimizada por defecto; en PostGIS se solicita
  `simplify_meters=2` sobre el endpoint GeoJSON y en fallback local se usa
  `san_rafael_vid_olivo_dashboard.geojson`;
- los usuarios demo quedan como `admin`, `finca`, `olivar` y `regional`.

Verificación local:

```text
87 tests passed
usuarios demo PostGIS: admin, productor, productor, regional
```

## Ensayo Productivo Local Para Cloud

Fecha:

```text
2026-06-18
```

Objetivo:

```text
Simular lo más posible el despliegue productivo de OSMOSENSE antes de pasar a
UM-Cloud.
```

Configuración ensayada:

- `APP_ENV=production`;
- `ENABLE_LOCAL_FALLBACK=false`;
- `ENABLE_QUICK_LOGIN=false`;
- `AUTH_SECRET` fuerte para ensayo local;
- `DATABASE_URL` apuntando a PostGIS local;
- `API_BASE_URL=http://127.0.0.1:8000`;
- API y dashboard levantados contra PostGIS, no contra fallback CSV.

Cambios de preparación:

- se corrigió la nomenclatura del despliegue a `OSMOSENSE`/`osmosense`;
- los servicios `systemd` quedan como `osmosense-*`;
- la ruta recomendada de VM queda en `/opt/osmosense`;
- se reemplazó la variable de entorno legacy por `OSMOSENSE_ENV`;
- los usuarios de la base local fueron migrados desde el dominio legacy a
  `@osmosense.local`;
- las contraseñas demo conocidas fueron rotadas para que no queden activas en
  el ensayo productivo.

Credenciales locales de ensayo:

```text
admin@osmosense.local / OsmosenseAdminDemo2026!
productor.vid@osmosense.local / OsmosenseVidDemo2026!
productor.olivo@osmosense.local / OsmosenseOlivoDemo2026!
regional@osmosense.local / OsmosenseRegionalDemo2026!
```

Scripts agregados para preparación cloud:

```text
backend/scripts/maintenance/run_preflight_cloud.py
backend/scripts/maintenance/preflight_cloud.py
backend/scripts/maintenance/rotar_credenciales_cloud.py
deployment/systemd/osmosense-api.service
deployment/systemd/osmosense-dashboard.service
deployment/systemd/osmosense-pipeline.service
deployment/systemd/osmosense-pipeline.timer
deployment/systemd/osmosense-postgis-backup.service
deployment/systemd/osmosense-postgis-backup.timer
deployment/scripts/bootstrap_vm.sh
deployment/scripts/install_systemd.sh
docs/despliegue_um_cloud.md
```

Uso previsto:

- `deployment/scripts/bootstrap_vm.sh` prepara una VM Ubuntu luego de clonar el
  repositorio: paquetes base, `venv`, dependencias, `.env` y usuario de
  servicio;
- `deployment/scripts/install_systemd.sh` instala las units `systemd` y permite
  habilitar/arrancar API, dashboard, pipeline y backup de forma repetible.

Decisiones de seguridad mínimas:

- `AUTH_SECRET` es obligatorio en producción;
- `AUTH_SECRET` debe tener al menos 32 caracteres;
- se rechazan secretos de ejemplo;
- `preflight_cloud` falla si detecta contraseñas demo conocidas;
- `.env` debe tener permisos restringidos;
- en producción no se permite fallback local ni login rápido.

Resultado del preflight:

```text
0 fallas, 2 advertencias
```

Advertencias esperadas en entorno local:

- `DATABASE_URL` usa credencial local/dev `estres_dev`;
- `API_BASE_URL` apunta a `localhost`.

Validaciones realizadas:

```text
SMOKE PRODUCTOR OK
SMOKE REGIONAL OK
SMOKE CRUD PRODUCTOR OK
Streamlit respondió HTTP 200
API respondió /health
```

El smoke CRUD asignó temporalmente una parcela libre al productor y luego la
desasignó. Resultado:

```text
la parcela dejó de verse en /me/parcelas y /me/rankings/latest/geojson
```

Comando principal de preflight para cloud:

```bash
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py --check-db
```

Comando principal de rotación de credenciales:

```bash
venv/bin/python backend/scripts/maintenance/rotar_credenciales_cloud.py --confirm
```

Validación automatizada posterior:

```text
98 tests passed
```

Conclusión:

```text
El sistema queda listo para repetir el mismo flujo dentro de la VM UM-Cloud.
```

Corrección durante despliegue UM-Cloud:

- el servicio `osmosense-pipeline.service` debe ejecutar el pipeline con
  `--update-recent-window` cuando usa `--parcel-source postgis`;
- motivo: en cloud no se debe reconstruir todo el histórico desde
  `parcelas_ide.geojson`; el flujo operativo consulta PostGIS y solo busca la
  última ventana Sentinel válida;
- el backup PostGIS pasó a ejecutarse mediante
  `deployment/scripts/backup_postgis.sh` para fallar correctamente si `pg_dump`
  falla y evitar archivos `.sql.gz` vacíos.

## Decisiones Descartadas O Resumidas

Se eliminaron de este documento los detalles extensos de:

- múltiples versiones intermedias del clasificador;
- tuning de thresholds descartados;
- particiones de entrenamiento/evaluación del flujo viejo;
- modelos binarios jerárquicos;
- datasets fenológicos/híbridos reemplazados;
- clasificador multiclass como pipeline principal;
- predictor binario de estrés hídrico.

Motivo:

```text
No forman parte del flujo operativo vigente.
```

La historia técnica queda preservada parcialmente en:

```text
legacy/
docs/
```
