# Contexto Para Redaccion De Tesis

Este documento resume el proyecto en formato util para redactar tesis,
especialmente el marco metodologico. No reemplaza a la documentacion tecnica
detallada, sino que sirve como entrada compacta para explicar que se hizo,
por que se decidio hacerlo asi y que resultados respaldan el enfoque.

## Documentos Base Del Proyecto

Para darle contexto a un asistente de redaccion o a un lector tecnico, usar:

```text
README.md
DECISIONS.md
docs/contexto_tesis.md
docs/modelo_predictivo.md
docs/modelo_clasificador.md
docs/indices_espectrales.md
docs/validacion_predictor_hidrico.md
docs/fragmentos_codigo_tesis.md
docs/diagramas.md
docs/arquitectura_cloud_pipeline.md
docs/postgis.md
docs/dashboard.md
docs/seguridad_auth.md
```

Lectura recomendada:

- `README.md`: vision operativa y comandos principales.
- `DECISIONS.md`: decisiones vigentes y bitacora tecnica resumida.
- `docs/contexto_tesis.md`: sintesis metodologica para redactar la tesis.
- `docs/modelo_predictivo.md`: detalle matematico del predictor hidrico.
- `docs/validacion_predictor_hidrico.md`: validacion historica del predictor.
- `docs/modelo_clasificador.md`: respaldo del clasificador de cultivos y
  experimentos neuronales.
- `docs/indices_espectrales.md`: base conceptual de los indices utilizados.
- `docs/fragmentos_codigo_tesis.md`: fragmentos cortos de codigo para citar en
  el marco metodologico.
- `docs/diagramas.md`: diagramas Mermaid de arquitectura, pipeline, PostGIS,
  autenticacion, vistas y modelo predictivo.

`README.md` y `DECISIONS.md` alcanzan para entender el proyecto a nivel
general, pero no son suficientes por si solos para redactar un marco
metodologico academico. El primero es operativo y el segundo mezcla decisiones
vigentes con hitos de desarrollo. Para tesis conviene usar este documento como
puente y luego ampliar con bibliografia.

## Tema Del Proyecto

El proyecto desarrolla una plataforma de monitoreo y prediccion de estres
hidrico satelital para parcelas de vid y olivo ubicadas en San Rafael,
Mendoza. El sistema utiliza imagenes Sentinel-2 procesadas mediante Google
Earth Engine, modelos de aprendizaje automatico y una aplicacion web con roles
diferenciados.

El objetivo no es reemplazar la decision agronomica del productor ni estimar
una medicion fisiologica directa de campo. El sistema genera un indicador
relativo de riesgo hidrico y una priorizacion espacial-temporal para asistir la
lectura de parcelas y zonas.

## Problema Abordado

San Rafael es una zona agricola con alta dependencia del riego. En cultivos
como vid y olivo, la disponibilidad hidrica y la oportunidad de riego afectan
el estado vegetativo y productivo. Sin embargo, el seguimiento parcela por
parcela puede ser costoso, discontinuo o dependiente de recorridas manuales.

La teledeteccion permite observar grandes superficies con revisita frecuente.
Sentinel-2 ofrece informacion multiespectral util para estimar vigor,
contenido de agua foliar, sequedad y cambios temporales en el dosel vegetal.

El problema metodologico central es transformar esas observaciones satelitales
en un indicador operativo, interpretable y actualizable que permita comparar
parcelas dentro de un mismo cultivo y anticipar la evolucion esperada del
riesgo.

## Objetivo General

Construir y validar un sistema basado en imagenes Sentinel-2 y aprendizaje
automatico para estimar, predecir y visualizar el riesgo hidrico relativo en
parcelas de vid y olivo de San Rafael, Mendoza.

## Objetivos Especificos

1. Integrar parcelas oficiales, limite departamental y zonificacion regional en
   un flujo geoespacial reproducible.
2. Extraer indices espectrales Sentinel-2 por parcela mediante Google Earth
   Engine.
3. Construir un score hidrico satelital relativo usando indices vinculados con
   agua, vigor y sequedad.
4. Entrenar modelos de regresion separados para vid y olivo, con horizontes de
   5 y 10 dias.
5. Validar el predictor contra observaciones futuras reales de Sentinel-2.
6. Generar rankings de prioridad por parcela y por unidad regional.
7. Implementar una plataforma web con roles `admin`, `productor` y `regional`.
8. Preparar el flujo para ejecucion automatizada en cloud con PostGIS.

## Alcance

Alcance geografico:

```text
San Rafael, Mendoza, Argentina
```

Cultivos operativos:

```text
vid
olivo
```

Fuente principal de parcelas:

```text
dataset oficial IDEMendoza / Gobierno de Mendoza
```

Unidad de analisis:

```text
parcela agricola
```

Horizontes predictivos:

```text
5 dias
10 dias
```

El sistema contempla la posibilidad futura de incorporar parcelas nuevas o
parcelas que cambien de cultivo, pero el flujo operativo actual se concentra en
parcelas oficiales etiquetadas como vid u olivo.

## Fuentes De Datos

### Parcelas

Se utiliza un parcelario oficial con geometria y etiqueta de cultivo. El flujo
filtra las parcelas de interes y conserva un universo operativo de vid y olivo.

Archivos relevantes:

```text
backend/data/parcelas/
backend/data/parcelas/san_rafael_completo_wgs84.geojson
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

### Limite De San Rafael

Se usa un GeoJSON local del limite departamental para evitar depender de
fuentes globales menos precisas.

```text
backend/data/limites/san_rafael.geojson
```

Decision metodologica:

```text
usar un limite local controlado y reproducible para filtrar parcelas y definir
la region de consulta en Google Earth Engine.
```

### Imagenes Sentinel-2

Coleccion usada:

```text
COPERNICUS/S2_SR_HARMONIZED
```

Caracteristicas:

- Sentinel-2 Surface Reflectance;
- procesamiento server-side en Google Earth Engine;
- composicion por ventanas cortas;
- filtro de nubosidad configurable;
- estadisticas por parcela mediante `reduceRegions`.

Parametros operativos vigentes:

```text
cloud_threshold = 35
window_days = 5
step_days = 5
buffer_negativo = 5 m
area_minima = 4000 m2
min_valid_pixels = 8
```

### Zonificacion Regional

Se incorporo zonificacion DGI para vista regional por UM.

```text
backend/data/zonificacion/regional_dgi.csv
backend/data/zonificacion/um_con_cultivos.geojson
backend/data/zonificacion/ranking_um_latest.csv
```

Decision:

```text
la vista regional usa UM con parcelas cultivadas, no cuencas completas como
unidad principal de decision.
```

## Variables E Indices Espectrales

El sistema utiliza bandas Sentinel-2 e indices derivados.

Variables principales:

```text
NDVI, NDMI, NDWI, MSI, SAVI, NDRE,
GNDVI, EVI, BSI, NBR, MTCI, IRECI,
B2, B3, B4, B5, B6, B7, B8, B11, B12
```

Rol conceptual:

| Variable | Uso principal |
|---|---|
| NDVI | vigor vegetativo general |
| NDMI | contenido de agua foliar |
| NDWI | agua superficial/dosel |
| MSI | sequedad/estres hidrico; valor alto implica mayor riesgo |
| SAVI | vigor corregido por suelo |
| NBR | sequedad/biomasa con informacion SWIR |
| Bandas B2-B12 | informacion espectral adicional |

El fundamento conceptual de estos indices esta documentado en:

```text
docs/indices_espectrales.md
```

## Construccion Del Score Hidrico

El proyecto no dispone de mediciones de campo de estres hidrico. Por lo tanto,
se construye un proxy satelital relativo por cultivo y fecha.

Formula vigente:

```text
R = 100 * (
      0.35 * P_bajo(NDMI)
    + 0.30 * P_alto(MSI)
    + 0.15 * P_bajo(NDWI)
    + 0.10 * P_bajo(NBR)
    + 0.10 * P_bajo(NDVI)
)
```

Donde:

```text
R = riesgo_hidrico
P_bajo(x) = percentil inverso dentro del mismo cultivo y fecha
P_alto(x) = percentil directo dentro del mismo cultivo y fecha
```

Interpretacion:

- mayor `R` implica mayor riesgo relativo;
- el valor se interpreta dentro del mismo cultivo y fecha;
- no es una medicion absoluta fisiologica;
- sirve para ordenar parcelas y detectar situaciones comparativamente criticas.

Justificacion de pesos:

| Componente | Peso | Justificacion |
|---|---:|---|
| NDMI | 0.35 | principal indicador de contenido de agua foliar |
| MSI | 0.30 | indicador sensible a sequedad y estres |
| NDWI | 0.15 | complemento hidrico superficial/dosel |
| NBR | 0.10 | sequedad/biomasa |
| NDVI | 0.10 | vigor general, con menor peso por no ser especifico de agua |

Codigo:

```text
backend/scripts/pipeline/generar_targets_hidricos_regresion.py
```

## Modelo Predictivo Hidrico

El predictor actual es un modelo de regresion supervisada.

Algoritmo:

```text
XGBoost Regressor
```

Motivo de eleccion:

- buen rendimiento en datos tabulares;
- capacidad de modelar relaciones no lineales;
- robustez ante interacciones entre indices, fechas, lags y tendencias;
- tiempos de entrenamiento razonables;
- posibilidad de analizar importancia de variables.

Se entrenan modelos separados por cultivo y horizonte:

```text
vid 5 dias
vid 10 dias
olivo 5 dias
olivo 10 dias
```

Motivo de separar vid y olivo:

- la vid es caducifolia y tiene una fenologia estacional marcada;
- el olivo es perenne y mas tolerante a condiciones de sequia;
- sus respuestas espectrales y necesidades hidricas no son equivalentes;
- un modelo unico mezclaria dinamicas agronomicas distintas.

Target principal:

```text
riesgo_hidrico_future
```

Tambien se generan targets auxiliares para interpretacion:

```text
ndmi_mean_future
msi_mean_future
ndwi_mean_future
nbr_mean_future
ndvi_mean_future
```

Variables consideradas:

- indices y bandas actuales;
- lags temporales;
- tendencias recientes;
- diferencias contra el contexto relativo de cultivo-fecha;
- codificacion temporal;
- historial satelital de la parcela.

Archivo de entrenamiento:

```text
backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py
```

Artefactos:

```text
backend/models/hidrico_regresion/
```

## Validacion Del Predictor

La validacion se realiza comparando la prediccion hecha en una fecha `t` contra
la observacion real Sentinel-2 disponible en `t+5` y `t+10`.

Metricas:

| Metrica | Uso |
|---|---|
| MAE | error medio absoluto en puntos de score |
| RMSE | penaliza errores grandes |
| R2 | ajuste global del regresor |
| Spearman | calidad del orden relativo entre parcelas |
| Top10 overlap | coincidencia del 10% mas critico predicho y observado |
| Error <= 5 / 10 puntos | tolerancia operativa |

La metrica mas importante para el producto no es solo el error absoluto, sino
la capacidad de mantener el orden de prioridad entre parcelas. Por eso Spearman
y Top10 overlap son centrales.

Resultado historico actualizado sobre 26 fechas entre `2023-01-11` y
`2026-05-06`:

| Cultivo | Horizonte | MAE | Spearman | Top10 overlap | Error <= 10 pts |
|---|---:|---:|---:|---:|---:|
| global | 5d | 4.08 | 0.958 | 0.835 | 92.1% |
| global | 10d | 4.66 | 0.951 | 0.817 | 88.9% |
| vid | 5d | 4.28 | 0.956 | 0.835 | 91.4% |
| vid | 10d | 5.19 | 0.942 | 0.809 | 86.4% |
| olivo | 5d | 3.66 | 0.965 | 0.864 | 93.7% |
| olivo | 10d | 3.52 | 0.971 | 0.842 | 94.2% |

Lectura:

- el predictor mantiene una alta correlacion ordinal;
- el error medio global esta cerca de 4 a 5 puntos sobre escala 0-100;
- el modelo es adecuado para priorizacion relativa;
- no debe describirse como "90% de accuracy", porque es un problema de
  regresion y ranking, no de clasificacion binaria.

Reporte:

```text
docs/validacion_predictor_hidrico.md
```

## Ranking Hidrico

El ranking operativo combina:

- riesgo actual;
- riesgo predicho a 5 dias;
- riesgo predicho a 10 dias;
- deterioro esperado.

Configuracion vigente:

```text
backend/models/ranking_hidrico_config.json
```

Pesos:

| Componente | Peso |
|---|---:|
| riesgo_actual | 0.30 |
| riesgo_pred_5d | 0.15 |
| riesgo_pred_10d | 0.25 |
| delta_5d_pos | 0.00 |
| delta_10d_pos | 0.30 |

Umbrales fijos:

| Prioridad | Umbral |
|---|---:|
| critica | >= 55.0 |
| alta | >= 47.5 |
| media | >= 35.0 |
| baja | < 35.0 |

Ademas del criterio fijo, el dashboard permite una lectura relativa por
percentiles para evitar que, en contextos extremos, todas las parcelas queden
visualmente en la misma categoria.

## Prediccion ML Cruda Y Proyeccion Operativa

El sistema distingue dos salidas:

### Prediccion ML cruda

Es la salida directa del regresor. Puede subir o bajar porque el historico real
incluye recuperaciones por riego, lluvia, manejo o cambios de condiciones.

Uso:

```text
admin / auditoria tecnica
```

### Proyeccion operativa

Es una capa de comunicacion para productor. Representa un escenario
conservador: que podria pasar si la condicion actual no mejora.

Propiedades:

- no reduce el riesgo respecto del riesgo actual;
- incorpora tendencia reciente;
- considera cultivo y estacion;
- se usa para la visualizacion del productor.

Uso:

```text
productor / interpretacion operativa
```

## Clasificacion De Cultivos

La clasificacion de cultivos fue trabajada durante el desarrollo, pero no forma
parte del flujo operativo actual.

Decision vigente:

```text
el pipeline operativo usa etiquetas oficiales de cultivo y no depende de un
clasificador para determinar vid/olivo.
```

Motivo:

- el producto final esta acotado a San Rafael;
- se cuenta con parcelario oficial etiquetado;
- el objetivo central es deteccion y prediccion hidrica;
- usar el clasificador agregaria incertidumbre innecesaria al flujo operativo.

Modelos historicos trabajados:

- pipeline jerarquico con modelos binarios;
- `cultivo` vs `no_cultivo`;
- `olivo` vs resto;
- `vid` vs frutales;
- calibracion de thresholds;
- clasificador multiclass plano como benchmark;
- filtros vid/olivo.

Los modelos historicos quedan como respaldo metodologico en `legacy/`.

## Experimentos Con Redes Neuronales

Se incorporo una linea experimental con TensorFlow/Keras por recomendacion
academica y para evaluar si una red neuronal podia mejorar la clasificacion.

Experimentos:

1. MLP tabular para `vid` vs `olivo`.
2. MLP multiclase desde parcelario crudo.
3. CNN 1D temporal multiclase por parcela.

Clases evaluadas:

```text
vid, olivo, frutales, incultos, anuales
```

Resultado piloto multiclase:

| Enfoque | Accuracy | Macro F1 |
|---|---:|---:|
| temporal suelto | 0.391 | 0.380 |
| wide all features | 0.450 | 0.451 |
| wide spectral regularizado | 0.460 | 0.449 |
| CNN temporal | 0.556 | 0.553 |

Lectura:

- la CNN temporal fue la variante neuronal mas prometedora;
- todavia no alcanza para reemplazar el flujo operativo;
- persiste confusion entre frutales, olivo y vid;
- se considera una linea futura, no el nucleo actual de la tesis operativa.

Archivos:

```text
backend/scripts/experiments/entrenar_clasificador_tensorflow.py
backend/scripts/experiments/entrenar_cnn_temporal_clasificacion.py
backend/scripts/experiments/generar_dataset_clasificacion_multiclase.py
backend/scripts/experiments/generar_dataset_clasificacion_wide.py
requirements-tensorflow.txt
```

## Auditorias De Calidad

El proyecto incorpora auditorias para revisar la calidad de los rankings.

Auditorias principales:

- cobertura de parcelas;
- parcelas sin ranking;
- outliers espaciales por vecinos cercanos;
- persistencia temporal de outliers;
- ruido puntual;
- historial reciente de outliers.

Decision metodologica importante:

```text
no suavizar automaticamente todos los saltos espaciales.
```

Motivo:

- una parcela vecina puede tener manejo distinto;
- puede haber riego localizado, diferencias de variedad, suelo o conduccion;
- un salto persistente puede ser real;
- solo los casos con evidencia de ruido puntual deben marcarse para revision.

## Arquitectura Del Sistema

El sistema se organiza en:

```text
backend/
frontend/
docs/
sql/
tests/
```

Componentes:

| Componente | Funcion |
|---|---|
| Google Earth Engine | procesamiento satelital server-side |
| Python/Pandas/GeoPandas | procesamiento tabular y geoespacial |
| XGBoost | modelos de regresion hidrica |
| Scikit-learn | metricas, splits y utilidades de ML |
| TensorFlow/Keras | experimentos neuronales |
| FastAPI | API para rankings, usuarios y roles |
| PostGIS | persistencia geoespacial operativa |
| Streamlit | dashboard web |
| Plotly | mapas y graficos interactivos |
| Docker Compose | PostGIS local |
| Pytest | suite de pruebas |

## Roles Del Dashboard

### Admin

Vista tecnica y de gestion:

- estado general del sistema;
- ranking y mapa de parcelas;
- auditorias y casos a revisar;
- gestion de usuarios;
- asignacion de parcelas a productores;
- revision de datos operativos.

### Productor

Vista simplificada:

- solo parcelas asignadas;
- riesgo actual;
- proyeccion operativa;
- explicacion en lenguaje no tecnico;
- sin graficos o campos tecnicos innecesarios.

El productor no recibe una recomendacion automatica de riego. Recibe una
lectura de riesgo para complementar su experiencia.

### Regional

Vista agregada por UM:

- score regional;
- porcentaje de parcelas alta/critica;
- cobertura de ranking;
- composicion vid/olivo;
- parcelas que explican una UM seleccionada.

## Cloud Y Automatizacion

La arquitectura prevista para UM-Cloud contempla:

- VM Ubuntu;
- entorno Python;
- credenciales de Google Earth Engine;
- PostGIS;
- API FastAPI;
- dashboard Streamlit;
- pipeline programado con `cron` o `systemd timer`.

Comando operativo previsto:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py \
  --mode cloud \
  --update-sentinel \
  --parcel-source postgis \
  --skip-if-no-new-date \
  --load-postgis
```

Logica de actualizacion:

- buscar la ultima ventana Sentinel-2 valida;
- no usar "hoy" si no hay imagen valida;
- evitar recalcular ranking si no hay fecha nueva;
- cargar resultados en PostGIS;
- exponer `latest` por API.

## Seguridad Y Acceso

El sistema usa:

- usuarios en PostGIS;
- contraseñas hasheadas;
- login por API;
- token de sesion;
- control de permisos por rol;
- vistas filtradas desde backend.

Roles:

```text
admin
regional
productor
```

La decision de seguridad principal es que el frontend no debe decidir que datos
puede ver un productor. El backend filtra las parcelas segun la relacion
productor-parcela.

## Pruebas Automatizadas

La suite de tests cubre:

- autenticacion y permisos;
- endpoints FastAPI;
- logica de frontend;
- animacion de riesgo;
- servicio de rankings;
- reporte de validacion del predictor;
- smokes PostGIS/productor/regional.

Resultado reciente:

```text
100 tests passed
```

Documento:

```text
docs/tests.md
```

## Limitaciones Metodologicas

1. No hay mediciones de campo directas de estres hidrico.
   El sistema trabaja con un proxy satelital relativo.

2. El score compara parcelas dentro del mismo cultivo y fecha.
   Por lo tanto, no debe interpretarse como una escala fisiologica absoluta.

3. El historico Sentinel-2 incluye efectos no observados directamente:
   riego, lluvia, manejo, suelo, variedad, poda y cambios de cultivo.

4. Las predicciones a 5 y 10 dias se validan contra observaciones satelitales
   futuras, no contra sensores de humedad de suelo o mediciones de potencial
   hidrico.

5. La clasificacion neuronal multiclase aun es experimental.

6. La disponibilidad de imagenes Sentinel-2 depende de nubosidad y calidad de
   pixeles validos.

7. El sistema esta acotado a San Rafael; la generalizacion a otras regiones
   requiere recalibracion y validacion.

## Decisiones Metodologicas Clave

- Usar etiquetas oficiales de cultivo para el flujo operativo.
- Separar modelos de vid y olivo.
- Usar XGBoost para regresion tabular.
- Validar con split temporal y validacion historica multifecha.
- Medir ranking con Spearman y Top10 overlap, no solo MAE.
- Mantener la clasificacion como linea secundaria/experimental.
- Usar PostGIS como almacenamiento geoespacial operativo.
- Mantener procesamiento satelital pesado en Google Earth Engine.
- Mostrar al productor una proyeccion operativa conservadora.
- No emitir recomendaciones automaticas de riego.

## Autores Y Referencias Ya Citadas En La Documentacion

Estas fuentes aparecen en la documentacion tecnica del proyecto. Antes de
entregar la tesis conviene revisar formato APA/IEEE final y verificar que cada
cita este efectivamente usada en el texto.

- Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5-32.
  https://doi.org/10.1023/A:1010933404324

- Gao, B.C. (1996). NDWI: A normalized difference water index for remote
  sensing of vegetation liquid water from space. Remote Sensing of Environment,
  58(3), 257-266.
  https://doi.org/10.1016/S0034-4257(96)00067-3

- Huete, A.R. (1988). A soil-adjusted vegetation index (SAVI). Remote Sensing
  of Environment, 25(3), 295-309.
  https://doi.org/10.1016/0034-4257(88)90106-X

- Navrozidis, I., Alexandridis, T., Moshou, D., Haugommard, A., & Lagopodi, A.
  (2022). Implementing Sentinel-2 data and machine learning to detect plant
  stress in olive groves. Remote Sensing, 14(23), 5947.
  https://doi.org/10.3390/rs14235947

- Mustapha, M., & Zineddine, M. (2024). An evaluative technique for drought
  impact on variation in agricultural LULC using remote sensing and machine
  learning. Environmental Monitoring and Assessment.
  https://doi.org/10.1007/s10661-024-12677-0

- Bchir, A., & Masmoudi-Charfi, C. (2024). Estimating and mapping NDVI and
  NDMI indexes by remote sensing of olive orchards in different Tunisian
  regions. In Recent Advances in Environmental Science from the
  Euro-Mediterranean and Surrounding Regions. Springer, Cham.
  https://doi.org/10.1007/978-3-031-43922-3_116

- Garcia Lima, E.E. (2024). Deteccion multiescala de estres hidrico en
  choperas empleando modelos de transferencia radiativa a partir de imagenes
  Sentinel-2 y sensores ecofisiologicos en tiempo casi real. Trabajo Fin de
  Master, Universidad de Leon.

## Bibliografia Que Conviene Agregar

Para robustecer la tesis, falta agregar bibliografia especifica sobre:

- mision Sentinel-2 y bandas MSI;
- uso de Google Earth Engine en procesamiento geoespacial;
- XGBoost;
- evaluacion de modelos de ranking;
- estres hidrico en vid;
- estres hidrico y tolerancia a sequia en olivo;
- necesidades hidricas, evapotranspiracion y riego en cultivos permanentes;
- PostGIS o sistemas de informacion geografica aplicados a agricultura.

Posibles lineas:

- documentacion oficial ESA/Copernicus para Sentinel-2;
- articulo original de XGBoost;
- FAO-56 para evapotranspiracion y requerimientos hidricos;
- literatura local/regional sobre vid y olivo en Mendoza.

## Como Convertir Esto En Marco Metodologico

Una estructura posible para el capitulo metodologico:

1. Area de estudio.
   San Rafael, Mendoza; cultivos seleccionados; justificacion agronomica.

2. Fuentes de datos.
   Parcelario oficial, limite departamental, Sentinel-2, zonificacion DGI.

3. Preprocesamiento geoespacial.
   CRS, filtro por limite, area minima, buffer negativo, ventanas temporales,
   calidad de pixeles.

4. Calculo de indices espectrales.
   Formulas y rol de NDVI, NDMI, NDWI, MSI, SAVI, NBR.

5. Construccion del score hidrico.
   Formula ponderada y naturaleza relativa del indicador.

6. Construccion del dataset predictivo.
   Pares `X_t -> y_t+h`, horizontes de 5 y 10 dias, separacion por cultivo.

7. Modelado.
   XGBoost Regressor, features, entrenamiento, split temporal, artefactos.

8. Validacion.
   MAE, RMSE, Spearman, Top10 overlap, tolerancias, validacion historica.

9. Ranking operativo.
   Combinacion de riesgo actual, riesgo futuro y deterioro esperado.

10. Implementacion del sistema.
    FastAPI, PostGIS, Streamlit, roles y automatizacion cloud.

11. Limitaciones.
    Ausencia de datos de campo, naturaleza relativa del score, dependencia de
    calidad Sentinel-2, alcance geografico.

## Frase De Sintesis Para La Tesis

El sistema propuesto implementa una metodologia de monitoreo satelital basada
en Sentinel-2 para estimar un riesgo hidrico relativo por parcela, entrenar
modelos de regresion separados para vid y olivo, validar la prediccion contra
observaciones futuras y publicar rankings operativos para productores y
autoridades regionales mediante una plataforma web geoespacial.
