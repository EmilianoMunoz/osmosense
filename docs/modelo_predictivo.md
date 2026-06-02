# Modelo Predictivo Hídrico — Documentación Técnica

## Objetivo

Predecir la evolución futura del estado hídrico satelital de parcelas
de vid y olivo en San Rafael, Mendoza, usando series temporales de
Sentinel-2.

El modelo no predice una medición fisiológica directa de campo. Predice
un **riesgo hídrico satelital** construido a partir de índices
espectrales sensibles a agua, vigor y sequedad.

La unidad de predicción es:

```text
estado de la parcela en fecha X -> valor estimado en X+h
```

donde:

```text
h ∈ {5, 10} días
```

Se entrenan modelos separados por:

```text
cultivo ∈ {vid, olivo}
horizonte ∈ {5 días, 10 días}
target ∈ {riesgo_hidrico, NDMI, MSI, NDWI, NBR, NDVI}
```

El target principal para el producto es:

```text
riesgo_hidrico_future
```

Los demás targets sirven para interpretación agronómica.

---

## Fuente de datos

El dataset base es:

```text
backend/data/dataset_temporal_hidrico.csv
```

Contiene observaciones Sentinel-2 cada 5 días, filtradas por píxeles
válidos, para parcelas de vid y olivo.

El dataset predictivo de regresión es:

```text
backend/data/dataset_predictivo_hidrico_regresion.csv
```

Se genera con:

```bash
venv/bin/python backend/scripts/pipeline/generar_targets_hidricos_regresion.py
```

Código principal:

```text
scripts/generar_targets_hidricos_regresion.py
```

---

## Variables espectrales base

Las variables base están declaradas en:

```text
scripts/generar_targets_hidricos_regresion.py
BASE_FEATURES
líneas 15-20
```

```python
BASE_FEATURES = [
    "ndvi_mean", "ndmi_mean", "ndwi_mean", "msi_mean", "savi_mean", "ndre_mean",
    "gndvi_mean", "evi_mean", "bsi_mean", "nbr_mean", "mtci_mean", "ireci_mean",
    "b2_mean", "b3_mean", "b4_mean", "b5_mean", "b6_mean", "b7_mean",
    "b8_mean", "b11_mean", "b12_mean",
]
```

Interpretación general:

| Variable | Rol                                           |
|----------|-----------------------------------------------|
| NDVI     | vigor vegetativo general                      |
| NDMI     | contenido de agua foliar                      |
| NDWI     | agua superficial/dosel                        |
| MSI      | estrés hídrico; interpretación inversa a NDMI |
| SAVI     | vigor corregido por suelo                     |
| NDRE     | clorofila/red-edge                            |
| GNDVI    | vigor usando banda verde                      |
| EVI      | vigor menos saturable que NDVI                |
| BSI      | suelo desnudo / baja cobertura                |
| NBR      | sequedad/biomasa, incorpora SWIR2             |
| MTCI     | gradiente red-edge                            |
| IRECI    | clorofila red-edge                            |
| B2-B12   | reflectancias Sentinel-2 crudas               |

---

## Score hídrico relativo

El score `riesgo_hidrico` se calcula en:

```text
scripts/generar_targets_hidricos_regresion.py
función: agregar_riesgo_hidrico()
líneas 52-68
```

La fórmula implementada es:

```text
R = 100 * (
      0.35 * P_bajo(NDMI)
    + 0.30 * P_alto(MSI)
    + 0.15 * P_bajo(NDWI)
    + 0.10 * P_bajo(NBR)
    + 0.10 * P_bajo(NDVI)
)
```

donde:

```text
R = riesgo_hidrico
P_bajo(x) = percentil inverso de x dentro del mismo cultivo y fecha
P_alto(x) = percentil directo de x dentro del mismo cultivo y fecha
```

Código:

```python
riesgo = (
    0.35 * robust_percentile(group["ndmi_mean"], high_is_risk=False)
    + 0.30 * robust_percentile(group["msi_mean"], high_is_risk=True)
    + 0.15 * robust_percentile(group["ndwi_mean"], high_is_risk=False)
    + 0.10 * robust_percentile(group["nbr_mean"], high_is_risk=False)
    + 0.10 * robust_percentile(group["ndvi_mean"], high_is_risk=False)
)
item["riesgo_hidrico"] = (100 * riesgo).clip(0, 100)
```

### Pesos del score

| Componente | Peso | Criterio                                                                                  |
|------------|------|-------------------------------------------------------------------------------------------|
| NDMI       | 0.35 | Señal principal de contenido de agua foliar. Menor NDMI implica mayor riesgo.             |
| MSI        | 0.30 | Señal directa de estrés/sequedad. Mayor MSI implica mayor riesgo.                         |
| NDWI       | 0.15 | Complementa información hídrica superficial/dosel. Menor NDWI implica mayor riesgo.       |
| NBR        | 0.10 | Aporta información de sequedad/biomasa. Menor NBR implica mayor riesgo.                   |
| NDVI       | 0.10 | Aporta vigor general, pero con menor peso porque puede reflejar fenología y no solo agua. |

El score está acotado a:

```text
0 <= riesgo_hidrico <= 100
```

Valores altos indican mayor prioridad relativa de atención/riego.

### Naturaleza relativa del score

El score se calcula comparando parcelas dentro de:

```text
mismo cultivo + misma fecha
```

Por lo tanto, no es una medición absoluta de estrés hídrico. Es una
medida relativa para ranking operativo.

---

## Construcción del problema predictivo

Los pares predictivos se construyen en:

```text
scripts/generar_targets_hidricos_regresion.py
función: crear_pares()
líneas 142-169
```

Para cada horizonte `h`, se desplaza la fecha futura hacia atrás:

```python
future["fecha"] = future["fecha"] - pd.to_timedelta(horizon, unit="D")
future = future.rename(columns={col: f"{col}_future" for col in future_cols})
merged = df.merge(future, on=["parcela_id", "fecha"], how="inner")
merged["horizon_days"] = horizon
```

Matemáticamente:

```text
X_t = variables observadas en fecha t
y_t,h = valor observado en fecha t + h
```

El modelo aprende:

```text
f_c,h(X_t) ≈ y_t,h
```

donde:

```text
c = cultivo
h = horizonte
```

---

## Features temporales

El modelo incorpora estacionalidad mediante codificación circular:

```text
scripts/generar_targets_hidricos_regresion.py
función: agregar_features_temporales()
líneas 71-78
```

Fórmulas:

```text
doy_sin = sin(2π * day_of_year / 365.25)
doy_cos = cos(2π * day_of_year / 365.25)
month_sin = sin(2π * month / 12)
month_cos = cos(2π * month / 12)
```

Esto evita que diciembre y enero queden artificialmente separados.

---

## Historial propio de la parcela

Como el producto se limita a San Rafael y las parcelas de producción
son conocidas, el historial propio de cada parcela es una fuente de
información válida.

Se calcula en:

```text
scripts/generar_targets_hidricos_regresion.py
función: agregar_historial_parcela()
líneas 81-115
```

Para cada variable `x` y parcela `p`:

```text
lag1 = x_p,t-1
lag2 = x_p,t-2
lag3 = x_p,t-3
delta_5d = x_p,t - x_p,t-1
delta_10d = x_p,t - x_p,t-2
delta_15d = x_p,t - x_p,t-3
rolling3_mean = promedio de últimas 3 observaciones
rolling3_std = desvío de últimas 3 observaciones
```

También se calcula una anomalía contra el historial previo de la misma
parcela:

```text
anomalia_parcela = (x_p,t - media_histórica_previa_p) /
                   (std_histórica_previa_p + ε)
```

Código:

```python
df[f"{col}_lag1"] = grouped[col].shift(1)
df[f"{col}_lag2"] = grouped[col].shift(2)
df[f"{col}_lag3"] = grouped[col].shift(3)
df[f"{col}_delta_5d"] = df[col] - df[f"{col}_lag1"]
df[f"{col}_delta_10d"] = df[col] - df[f"{col}_lag2"]
df[f"{col}_delta_15d"] = df[col] - df[f"{col}_lag3"]
df[f"{col}_rolling3_mean"] = grouped[col].rolling(3, min_periods=1).mean()
df[f"{col}_rolling3_std"] = grouped[col].rolling(3, min_periods=2).std()
df[f"{col}_anomalia_parcela"] = (
    (df[col] - df[f"{col}_hist_mean_prev"])
    / (df[f"{col}_hist_std_prev"].abs() + 1e-6)
)
```

Esta parte permite capturar patrones como:

```text
NDMI viene bajando sostenidamente
MSI viene subiendo
la parcela está peor que su propio promedio histórico
el cambio reciente es más rápido que lo habitual
```

---

## Contexto relativo por fecha y cultivo

Además del historial propio, se calcula la posición relativa de cada
parcela contra otras parcelas del mismo cultivo en la misma fecha.

Código:

```text
scripts/generar_targets_hidricos_regresion.py
función: agregar_contexto_relativo_fecha()
líneas 118-129
```

Fórmula:

```text
rel_fecha = (x_i,t - mediana_c,t) / (IQR_c,t + ε)
```

donde:

```text
c = cultivo
t = fecha
IQR = Q75 - Q25
```

Código:

```python
grouped = df.groupby(["cultivo", "fecha"], sort=False)[col]
median = grouped.transform("median")
q75 = grouped.transform(lambda s: s.quantile(0.75))
q25 = grouped.transform(lambda s: s.quantile(0.25))
df[f"{col}_rel_fecha"] = (df[col] - median) / ((q75 - q25).abs() + 1e-6)
```

Esto permite que el modelo aprenda no solo el estado absoluto de una
parcela, sino si está relativamente peor o mejor que parcelas similares.

---

## Modelo de aprendizaje automático

El modelo usado es:

```text
XGBRegressor
```

Está definido en:

```text
scripts/experiments/entrenar_predictores_hidricos_regresion.py
función: crear_modelo()
líneas 59-73
```

Parámetros:

```python
XGBRegressor(
    objective="reg:squarederror",
    n_estimators=450,
    max_depth=4,
    learning_rate=0.035,
    subsample=0.9,
    colsample_bytree=0.85,
    gamma=0.05,
    min_child_weight=2,
    reg_lambda=1.5,
    tree_method="hist",
    random_state=42,
    n_jobs=-1,
)
```

### Interpretación de parámetros

| Parámetro        | Valor            | Función                                                 |
|------------------|------------------|---------------------------------------------------------|
| objective        | reg:squarederror | Regresión continua minimizando error cuadrático.        |
| n_estimators     | 450              | Cantidad de árboles.                                    |
| max_depth        | 4                | Profundidad máxima de cada árbol. Controla complejidad. |
| learning_rate    | 0.035            | Paso de aprendizaje. Valores bajos reducen sobreajuste. |
| subsample        | 0.9              | Usa 90% de filas por árbol.                             |
| colsample_bytree | 0.85             | Usa 85% de columnas por árbol.                          |
| gamma            | 0.05             | Ganancia mínima para dividir un nodo.                   |
| min_child_weight | 2                | Evita divisiones con poca evidencia.                    |
| reg_lambda       | 1.5              | Regularización L2.                                      |
| tree_method      | hist             | Entrenamiento eficiente para datasets grandes.          |

---

## Prevención de leakage

Para evitar que el modelo vea información futura, se excluyen columnas
que no deberían estar disponibles en producción.

Código:

```text
scripts/experiments/entrenar_predictores_hidricos_regresion.py
función: feature_columns()
líneas 39-56
```

Se excluyen:

```text
parcela_id
cultivo
fecha
fecha_fin
year
month
day_of_year
targets futuros
columnas que comienzan con delta_
columnas que terminan con _future
```

La exclusión de `_future` es crítica porque esas columnas contienen los
valores observados en X+5 o X+10, es decir, lo que el modelo intenta
predecir.

---

## Validación

La métrica principal usa split temporal:

```text
scripts/experiments/entrenar_predictores_hidricos_regresion.py
función: split_temporal()
líneas 82-93
```

Este esquema entrena con fechas antiguas y evalúa con fechas futuras:

```text
train = fechas anteriores al corte
test = fechas posteriores al corte
```

Esto es más estricto que separar parcelas al azar porque simula el uso
real del producto:

```text
predecir futuro a partir del pasado
```

---

## Métricas

Las métricas se calculan en:

```text
scripts/experiments/entrenar_predictores_hidricos_regresion.py
funciones: evaluar() y top_decile_overlap()
líneas 96-114
```

### MAE

Error absoluto medio:

```text
MAE = (1/n) * Σ |y_i - ŷ_i|
```

Indica el error promedio en la misma escala del target.

### RMSE

Raíz del error cuadrático medio:

```text
RMSE = sqrt((1/n) * Σ (y_i - ŷ_i)^2)
```

Penaliza más los errores grandes.

### R2

Proporción de varianza explicada:

```text
R2 = 1 - Σ(y_i - ŷ_i)^2 / Σ(y_i - mean(y))^2
```

No debe interpretarse como accuracy. Un R2 de 0.90 significa que el
modelo explica aproximadamente el 90% de la variabilidad observada en
el target.

### Spearman

Correlación de rangos:

```text
Spearman = corr(rank(y), rank(ŷ))
```

Es clave para este producto porque el objetivo final es rankear parcelas.

### Top10 overlap

Mide cuánto coincide el 10% de parcelas más críticas predichas con el
10% más crítico observado:

```text
top10_overlap = |Top10_real ∩ Top10_predicho| / |Top10_real|
```

---

## Resultados actuales

Resultados con split temporal para el target operativo
`riesgo_hidrico_future`:

| Cultivo | Horizonte | MAE   | RMSE  | R2    | Spearman | Top10 overlap |
|---------|-----------|-------|-------|-------|----------|---------------|
| vid     | 5 días    | 4.271 | 6.531 | 0.900 | 0.949    | 0.830         |
| vid     | 10 días   | 5.681 | 8.341 | 0.835 | 0.914    | 0.782         |
| olivo   | 5 días    | 3.716 | 5.531 | 0.927 | 0.964    | 0.806         |
| olivo   | 10 días   | 4.748 | 6.977 | 0.883 | 0.940    | 0.766         |

Interpretación:

- El error medio del score futuro está entre 3.7 y 5.7 puntos en escala
  0-100.
- La correlación de ranking es alta: Spearman entre 0.914 y 0.964.
- El modelo identifica entre 76.6% y 83.0% del top 10% más crítico,
  según cultivo y horizonte.

Validación operativa multifecha sobre 2024, simulando ranking en fecha X y
comparación contra observación empírica en X+5 y X+10. Se descartan filas de
resumen con menos de 50 parcelas evaluadas para evitar métricas inestables:

| Cultivo | Horizonte | Fechas | MAE   | RMSE  | Bias   | Spearman | Top10 overlap |
|---------|-----------|--------|-------|-------|--------|----------|---------------|
| global  | 5 días    | 12     | 3.882 | 5.824 | -0.896 | 0.960    | 0.835         |
| global  | 10 días   | 12     | 4.711 | 6.891 | -1.110 | 0.943    | 0.808         |
| vid     | 5 días    | 12     | 4.121 | 6.102 | -0.916 | 0.959    | 0.837         |
| vid     | 10 días   | 12     | 5.235 | 7.517 | -1.385 | 0.933    | 0.806         |
| olivo   | 5 días    | 12     | 3.350 | 5.032 | -0.854 | 0.965    | 0.823         |
| olivo   | 10 días   | 12     | 3.597 | 5.218 | -0.545 | 0.965    | 0.785         |

Por estación, el ranking se mantiene estable. La validación anterior incluía
una fecha con una sola parcela evaluada, lo que distorsionaba el promedio de
verano. Con `min-n-summary=50`, verano queda en un rango consistente:

| Estación | Horizonte | MAE global | Spearman global | Top10 overlap global |
|----------|-----------|------------|-----------------|----------------------|
| verano   | 5 días    | 3.958      | 0.966           | 0.873                |
| verano   | 10 días   | 4.375      | 0.953           | 0.866                |

---

## Importancia de variables

Se agregó un reporte reproducible:

```bash
venv/bin/python backend/scripts/modeling/analizar_importancia_predictores_hidricos.py --top-n 10
```

Archivos generados:

```text
backend/data/importancia_predictores_hidricos.csv
backend/data/importancia_predictores_hidricos_grupos.csv
```

Los modelos operativos fueron reentrenados excluyendo features `scl_*`.
`SCL` es una clasificación de escena/calidad de Sentinel-2 y no una señal
agronómica directa. La exclusión evita que el modelo aprenda artefactos de
calidad de imagen. El desempeño quedó prácticamente igual.

Importancia agregada por grupo para `riesgo_hidrico_future`:

| Cultivo | Horizonte | Contexto relativo | Estado actual | Tendencia reciente | Lags  | Historial |
|---------|-----------|-------------------|---------------|--------------------|-------|-----------|
| olivo   | 5 días    | 0.599             | 0.185         | 0.055              | 0.047 | 0.023     |
| olivo   | 10 días   | 0.718             | 0.075         | 0.059              | 0.042 | 0.033     |
| vid     | 5 días    | 0.615             | 0.176         | 0.054              | 0.059 | 0.025     |
| vid     | 10 días   | 0.647             | 0.088         | 0.072              | 0.051 | 0.042     |

Lectura:

- El factor dominante es el contexto relativo por cultivo y fecha:
  `riesgo_hidrico_rel_fecha`, `ndmi_mean_rel_fecha`, `msi_mean_rel_fecha`.
- El estado actual (`riesgo_hidrico`) pesa más en 5 días que en 10 días.
- A 10 días gana peso la posición relativa de NDMI/MSI y el historial.
- La estacionalidad explícita pesa poco porque gran parte de la señal
  fenológica ya está contenida en los índices y en el contexto por fecha.

---

## Calibración del ranking final

El ranking operativo no usa directamente una sola predicción. Combina:

- riesgo predicho a 10 días;
- riesgo predicho a 5 días;
- deterioro positivo esperado a 10 días;
- deterioro positivo esperado a 5 días;
- riesgo actual.

Se creó:

```text
scripts/optimizar_ranking_hidrico.py
```

Comando:

```bash
venv/bin/python backend/scripts/modeling/optimizar_ranking_hidrico.py --step 0.05 --min-n 50
```

Este script usa:

```text
backend/data/validacion_ranking_hidrico_multifecha_2024.csv
```

y busca pesos que maximicen:

```text
0.50 * top10_10d
+ 0.25 * spearman_10d
+ 0.15 * top10_5d
+ 0.10 * spearman_5d
```

La prioridad se calcula ahora con la configuración:

```text
backend/models/ranking_hidrico_config.json
```

Pesos calibrados:

| Variable           | Peso |
|--------------------|------|
| riesgo_pred_10d    | 0.25 |
| riesgo_pred_5d     | 0.15 |
| delta_10d positivo | 0.30 |
| delta_5d positivo  | 0.00 |
| riesgo_actual      | 0.30 |

Fórmula:

```text
prioridad_score =
    0.25 * riesgo_pred_10d
  + 0.15 * riesgo_pred_5d
  + 0.30 * max(delta_10d, 0)
  + 0.00 * max(delta_5d, 0)
  + 0.30 * riesgo_actual
```

Umbrales calibrados:

| Prioridad | Umbral de score |
|-----------|-----------------|
| crítica   | >= 55.0         |
| alta      | >= 47.5         |
| media     | >= 35.0         |
| baja      | < 35.0          |

Métricas de la fórmula calibrada:

| Métrica           | Valor |
|-------------------|-------|
| fechas evaluadas  | 12    |
| Spearman 5d       | 0.964 |
| Spearman 10d      | 0.939 |
| Top10 overlap 5d  | 0.852 |
| Top10 overlap 10d | 0.814 |

Interpretación:
la fórmula calibrada prioriza parcelas que ya están mal y que además muestran
deterioro esperado a 10 días. Esto es más útil operativamente que ordenar solo
por riesgo futuro absoluto, porque destaca parcelas donde la intervención puede
ser más urgente.

---

## Proyección operativa sin mejora

Los modelos de regresión (`riesgo_pred_5d` y `riesgo_pred_10d`) se entrenan con
histórico real. Por eso pueden predecir una baja del riesgo si en casos
similares del pasado hubo recuperación, riego, lluvia o mejora de señal
satelital entre imágenes.

Para el dashboard de cliente se agrega una segunda lectura:

```text
riesgo_operativo_5d
riesgo_operativo_10d
```

Esta proyección representa un escenario conservador de continuidad de la
condición actual: "si la situación no mejora, cómo podría evolucionar el
riesgo". No reemplaza al modelo ML crudo; lo envuelve con reglas operativas.

Se calcula en:

```text
scripts/generar_ranking_hidrico.py
función: agregar_proyeccion_operativa()
```

La tendencia reciente se estima con el historial inmediato de la parcela:

```text
tendencia_5d = riesgo_actual - riesgo_hidrico_lag1
tendencia_10d_prom = (riesgo_actual - riesgo_hidrico_lag2) / 2
tendencia = max(0, 0.7 * tendencia_5d + 0.3 * tendencia_10d_prom)
```

Esto hace que pese más la ventana más cercana. Si la parcela viene empeorando,
esa pendiente se conserva. Si viene mejorando, la pendiente negativa no reduce
la proyección operativa, porque el escenario mostrado al cliente es de no
mejora.

Además se aplica una pendiente mínima según prioridad:

| Prioridad | Pendiente mínima cada 5 días |
|-----------|------------------------------|
| baja      | 0.5 puntos                   |
| media     | 1.5 puntos                   |
| alta      | 3.0 puntos                   |
| critica   | 4.0 puntos                   |

La pendiente se ajusta por cultivo:

| Cultivo | Factor |
|---------|--------|
| vid     | 1.15   |
| olivo   | 0.75   |

y por estación:

| Cultivo | Verano | Primavera | Otoño | Invierno |
|---------|--------|-----------|-------|----------|
| vid     | 1.30   | 1.15      | 0.85  | 0.45     |
| olivo   | 1.10   | 1.00      | 0.80  | 0.65     |

La pendiente final es:

```text
pendiente_operativa_5d =
    max(tendencia, pendiente_minima)
  * factor_cultivo
  * factor_estacional
```

Las proyecciones quedan forzadas a ser monótonas y conservadoras respecto de
la predicción histórica:

```text
riesgo_operativo_5d =
    max(riesgo_actual, riesgo_pred_5d, riesgo_actual + pendiente_operativa_5d)

riesgo_operativo_10d =
    max(riesgo_operativo_5d,
        riesgo_pred_10d,
        riesgo_operativo_5d + pendiente_operativa_5d)
```

Por construcción:

```text
riesgo_operativo_5d >= riesgo_actual
riesgo_operativo_10d >= riesgo_operativo_5d
riesgo_operativo_5d >= riesgo_pred_5d
riesgo_operativo_10d >= riesgo_pred_10d
```

Uso en producto:

- vista admin: conserva predicción ML cruda para auditoría técnica;
- vista cliente: muestra la proyección operativa, porque comunica mejor el
  escenario de deterioro si la condición no mejora;
- el ranking actual no cambia por esta capa; sigue usando la fórmula calibrada
  de `prioridad_score`.

---

## Ejemplo interpretativo

Supongamos una parcela de vid:

```text
riesgo actual = 18
riesgo observado 5 días después = 87
```

Para el modelo:

```text
regresor_vid_5d_riesgo_hidrico_future_temporal.pkl
```

el margen observado es:

```text
MAE = 4.262
RMSE = 6.523
```

Si la parcela ya mostraba señales previas de deterioro:

```text
NDMI bajando
MSI subiendo
riesgo_hidrico_delta_5d positivo
anomalía contra historial propio
posición relativa peor que otras parcelas
```

una predicción razonable esperada sería:

```text
87 ± 4 a 7 puntos
```

Si el salto ocurre sin señal previa en la serie Sentinel-2, el modelo
puede subestimar el valor futuro. Esto es esperable: el modelo predice
a partir de patrones observables en la serie satelital, no de eventos
externos no registrados todavía.

---

## Consideración sobre cambio histórico de cultivo

El producto final está limitado a San Rafael y usará parcelas conocidas.
Eso permite aprovechar el historial propio de cada parcela.

Sin embargo, una parcela puede haber tenido otro cultivo en parte del
histórico. En ese caso, las observaciones antiguas pueden introducir
ruido porque el historial ya no representa el cultivo actual.

Mitigación propuesta para versiones posteriores:

1. Detectar parcelas con señales espectrales incompatibles con su cultivo
   oficial durante períodos largos.
2. Marcar esas parcelas como `cultivo_inestable`.
3. Excluirlas del entrenamiento o usar solo el tramo temporal posterior
   al cambio detectado.

---

## Archivos generados

Dataset predictivo:

```text
backend/data/dataset_predictivo_hidrico_regresion.csv
```

Modelos:

```text
backend/models/hidrico_regresion/
```

Modelos principales para ranking:

```text
regresor_vid_5d_riesgo_hidrico_future_temporal.pkl
regresor_vid_10d_riesgo_hidrico_future_temporal.pkl
regresor_olivo_5d_riesgo_hidrico_future_temporal.pkl
regresor_olivo_10d_riesgo_hidrico_future_temporal.pkl
```

Métricas:

```text
backend/models/hidrico_regresion/metricas_regresion_temporal.csv
backend/models/hidrico_regresion/metricas_regresion_group.csv
```

---

## Comandos de reproducción

Generar dataset predictivo:

```bash
venv/bin/python backend/scripts/pipeline/generar_targets_hidricos_regresion.py
```

Entrenar modelos principales:

```bash
venv/bin/python backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py --split temporal
```

Evaluación secundaria por parcela:

```bash
venv/bin/python backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py --split group
```
