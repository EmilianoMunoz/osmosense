# Modelo Clasificador de Cultivos — Documentación Técnica

> Estado: referencia técnica histórica. El producto operativo actual prioriza
> el flujo hídrico vid/olivo y la visualización por roles; esta documentación
> queda como respaldo del clasificador de cultivos.

## Objetivo
Clasificar automáticamente parcelas agrícolas de San Rafael, Mendoza,
en tres categorías: vid, olivo u otros, a partir de índices espectrales
derivados de imágenes Sentinel-2.

---

## Algoritmo: Random Forest

### ¿Qué es un Random Forest?

Random Forest es un algoritmo de aprendizaje automático supervisado
basado en la construcción de múltiples árboles de decisión durante
el entrenamiento. La predicción final se obtiene por votación mayoritaria
entre todos los árboles.

Muestra de entrada: [NDVI, NDMI, NDWI, MSI, SAVI, B2, B3, B4, B8, B11, mes_sin, mes_cos]
↓
Árbol 1 → "vid"
Árbol 2 → "olivo"
Árbol 3 → "vid"
Árbol 4 → "vid"
Árbol 5 → "olivo"
↓
Votación: vid=3, olivo=2 → predicción final: "vid"

### ¿Cómo funciona un árbol de decisión?

Cada árbol divide recursivamente el espacio de features buscando
el corte que mejor separa las clases. Por ejemplo:

¿NDVI > 0.3?
├── SÍ → ¿mes_cos > 0.5?
│         ├── SÍ → olivo (invierno, mantiene hoja)
│         └── NO → vid (verano, ambos tienen hoja)
└── NO → ¿MSI > 1.2?
├── SÍ → vid (sin hoja, alta reflectancia SWIR)
└── NO → otros (suelo, urbano)

El criterio de división es la **impureza de Gini**, que mide
qué tan mezcladas están las clases en cada nodo:

    Gini = 1 - Σ(pᵢ²)

donde pᵢ es la proporción de muestras de la clase i en el nodo.
Un nodo puro (todas las muestras de la misma clase) tiene Gini = 0.

### ¿Qué es el "Random" en Random Forest?

Cada árbol se entrena con dos fuentes de aleatoriedad:

1. **Bagging**: cada árbol recibe una muestra aleatoria con
   reemplazo del dataset original (bootstrap). Esto hace que
   cada árbol vea datos ligeramente distintos.

2. **Feature sampling**: en cada división, el árbol solo considera
   un subconjunto aleatorio de features (√n_features por defecto).
   Esto reduce la correlación entre árboles y mejora la
   generalización.

---

## Features del modelo

El modelo recibe un vector de 12 features por parcela y mes:

| Feature | Tipo     | Descripción                                |
|---------|----------|--------------------------------------------|
| ndvi    | Índice   | Vigor vegetativo (B8-B4)/(B8+B4)           |
| ndmi    | Índice   | Contenido de agua foliar (B8-B11)/(B8+B11) |
| ndwi    | Índice   | Agua superficial (B3-B8)/(B3+B8)           |
| msi     | Índice   | Estrés hídrico B11/B8                      |
| savi    | Índice   | NDVI corregido por suelo                   |
| b2      | Banda    | Blue (490nm)                               |
| b3      | Banda    | Green (560nm)                              |
| b4      | Banda    | Red (665nm)                                |
| b8      | Banda    | NIR (842nm)                                |
| b11     | Banda    | SWIR-1 (1610nm)                            |
| mes_sin | Temporal | sin(2π × mes / 12)                         |
| mes_cos | Temporal | cos(2π × mes / 12)                         |

### Codificación circular del tiempo

El mes se codifica con seno y coseno para preservar la
continuidad cíclica del año:

    mes_sin = sin(2π × mes / 12)
    mes_cos = cos(2π × mes / 12)

| Mes          | mes_sin | mes_cos | Interpretación          |
|--------------|---------|---------|-------------------------|
| Enero (1)    | 0.50    | 0.87    | Verano, vid con follaje |
| Abril (4)    | 1.00    | 0.00    | Otoño, vid cambia color |
| Julio (7)    | 0.50    | -0.87   | Invierno, vid sin hoja  |
| Octubre (10) | -1.00   | 0.00    | Primavera, vid brota    |

Con codificación numérica simple (1-12), diciembre y enero
quedan a distancia 11. Con codificación circular quedan a
distancia ~0.52, reflejando que son meses consecutivos.

---

## Parámetros del modelo

```python
RandomForestClassifier(
    n_estimators=100,     # número de árboles
    max_depth=10,         # profundidad máxima de cada árbol
    min_samples_split=4,  # mínimo de muestras para dividir un nodo
    random_state=42,      # semilla para reproducibilidad
    class_weight="balanced"  # compensa desbalance entre clases
)
```

### Justificación de parámetros:

**n_estimators=100**: compromiso entre rendimiento y tiempo de
cómputo. Con más árboles el modelo es más estable pero tarda más.
100 es el estándar en la literatura para datasets de este tamaño.

**max_depth=10**: limita el crecimiento de cada árbol para evitar
sobreajuste. Sin límite, cada árbol memorizaría el dataset de
entrenamiento.

**min_samples_split=4**: requiere al menos 4 muestras para dividir
un nodo, evitando divisiones sobre ruido en el dataset.

**class_weight="balanced"**: ajusta automáticamente los pesos de
cada clase inversamente proporcional a su frecuencia. Importante
cuando hay desbalance entre clases.

---

## Evaluación del modelo

### Métricas utilizadas

**Accuracy**: proporción de predicciones correctas sobre el total.

    Accuracy = (TP + TN) / (TP + TN + FP + FN)

**Precision**: de las predicciones positivas, cuántas son correctas.

    Precision = TP / (TP + FP)

**Recall**: de los casos positivos reales, cuántos detectó el modelo.

    Recall = TP / (TP + FN)

**F1-score**: media armónica entre precision y recall. Útil cuando
hay desbalance entre clases.

    F1 = 2 × (Precision × Recall) / (Precision + Recall)

### Validación cruzada (k-fold)

Para evaluar el modelo sin depender de una única división
train/test se usa validación cruzada de 5 folds:

Dataset completo (9.600 muestras)
↓
Fold 1: [====][----][----][----][----]  → entrena en 4, evalúa en 1
Fold 2: [----][====][----][----][----]  → entrena en 4, evalúa en 1
Fold 3: [----][----][====][----][----]  → etc.
Fold 4: [----][----][----][====][----]
Fold 5: [----][----][----][----][====]
↓
Accuracy final = promedio de los 5 folds ± desviación estándar

Esto garantiza que cada muestra sea usada tanto para entrenamiento
como para evaluación, dando una estimación más robusta del
rendimiento real.

---

## Experimento: Red Neuronal TensorFlow

Además del clasificador basado en árboles, se agregó un experimento aislado con
TensorFlow/Keras para evaluar si una red neuronal mejora la clasificación de
cultivos.

Archivo:

```text
backend/scripts/experiments/entrenar_clasificador_tensorflow.py
```

Dependencia opcional:

```bash
venv/bin/pip install -r requirements-tensorflow.txt
```

Comando base:

```bash
venv/bin/python backend/scripts/experiments/entrenar_clasificador_tensorflow.py
```

Por defecto usa:

```text
backend/data/dataset_temporal_hidrico.csv
clases: vid, olivo
target: cultivo
split: por parcela_id
```

El split por `parcela_id` es importante: evita que observaciones temporales de
la misma parcela entren simultáneamente en entrenamiento y test. Si se separaran
filas al azar, la métrica podría quedar artificialmente alta por fuga de
información.

### Arquitectura

La red es un perceptrón multicapa:

```text
features normalizadas
↓
Dense(128, relu) + BatchNorm + Dropout
↓
Dense(64, relu) + BatchNorm + Dropout
↓
Dense(n_clases, softmax)
```

Parámetros principales:

| Parámetro | Valor inicial |
|-----------|---------------|
| epochs | 80 |
| batch_size | 256 |
| early stopping | val_loss, patience 10 |
| learning_rate | 0.001 |
| dropout | 0.25 |
| regularización L2 | 0.0001 |
| class_weight | balanced |

### Features iniciales

El experimento no usa `parcela_id` como feature. Por defecto toma:

- índices y bandas agregadas con sufijo `_mean`;
- dispersión espectral con sufijo `_stddev`;
- codificación temporal circular:
  - `month_sin`;
  - `month_cos`;
  - `doy_sin`;
  - `doy_cos`.

No incluye `area_m2` salvo que se ejecute con:

```bash
--include-area
```

La superficie puede mejorar métricas, pero no es estrictamente una señal
espectral y podría introducir sesgos catastrales.

### Salidas

El entrenamiento guarda artefactos en:

```text
backend/models/clasificador_tensorflow/
```

Archivos principales:

| Archivo | Contenido |
|---------|-----------|
| `clasificador_tensorflow.keras` | modelo Keras entrenado |
| `preprocesamiento.joblib` | imputador, scaler, label encoder y features |
| `metricas_clasificador_tensorflow.json` | resumen del experimento |
| `classification_report.csv` | precision, recall y F1 por clase |
| `confusion_matrix.csv` | matriz de confusión |
| `history.csv` | curva de entrenamiento |

Estos artefactos están ignorados por Git porque son regenerables y pueden ser
pesados.

### Dataset multiclase desde parcelario completo

Para probar la clasificación pedida sobre el dataset crudo de parcelas se usó:

```text
backend/data/parcelas/san_rafael_completo_wgs84.geojson
```

Ese archivo contiene geometría y etiqueta oficial, pero no contiene índices
Sentinel-2. Por eso se agregó un generador específico:

```text
backend/scripts/experiments/generar_dataset_clasificacion_multiclase.py
```

Clases usadas:

| `tipo_culti` oficial | Clase del modelo |
|----------------------|------------------|
| `VID` | `vid` |
| `OLIVOS` | `olivo` |
| `FRUTALES` | `frutales` |
| `INCULTOS` | `incultos` |
| `ANUALES` | `anuales` |

Conteo disponible con área mínima de 4000 m²:

| Clase | Parcelas |
|-------|----------|
| anuales | 15196 |
| incultos | 10089 |
| vid | 9273 |
| frutales | 4883 |
| olivo | 406 |

Como `olivo` limita el balance de clases, la prueba piloto usó 100 parcelas por
clase y 4 ventanas Sentinel-2 durante 2024:

```bash
venv/bin/python backend/scripts/experiments/generar_dataset_clasificacion_multiclase.py \
  --samples-per-class 100 \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --step-days 90 \
  --window-days 15 \
  --max-windows 4 \
  --chunk-size 100 \
  --cloud-threshold 35
```

Resultado del dataset temporal:

```text
filas válidas: 1741
parcelas únicas: 500
fechas: 2024-01-01, 2024-03-31, 2024-06-29, 2024-09-27
distribución: anuales 363, incultos 355, vid 345, frutales 340, olivo 338
```

También se probó una representación ancha, una fila por parcela:

```bash
venv/bin/python backend/scripts/experiments/generar_dataset_clasificacion_wide.py
```

Resultado:

```text
filas: 500
columnas: 451
distribución: 100 parcelas por clase
```

### Resultado inicial binario vid/olivo

Corrida completa sobre `backend/data/dataset_temporal_hidrico.csv`:

```bash
venv/bin/python backend/scripts/experiments/entrenar_clasificador_tensorflow.py \
  --epochs 60 \
  --patience 8 \
  --batch-size 1024
```

Configuración:

```text
split: group por parcela_id
filas train: 121891
filas validation: 29192
filas test: 37826
features: 46
clases: olivo, vid
epochs entrenadas: 32
```

Resultado con argmax estándar:

| Métrica | Valor |
|---------|-------|
| accuracy | 0.811 |
| macro F1 | 0.750 |
| weighted F1 | 0.818 |

Resultado con threshold binario optimizado en validación:

| Métrica | Valor |
|---------|-------|
| threshold clase `vid` | 0.38 |
| accuracy | 0.838 |
| macro F1 | 0.767 |
| weighted F1 | 0.837 |

Reporte por clase con threshold optimizado:

| Clase | Precision | Recall | F1 | Soporte |
|-------|-----------|--------|----|---------|
| olivo | 0.650 | 0.625 | 0.637 | 8585 |
| vid | 0.891 | 0.901 | 0.896 | 29241 |

Conclusión inicial:

```text
La red neuronal es viable como experimento, pero todavía no justifica reemplazar
el flujo operativo. El desempeño en vid es bueno; olivo sigue siendo la clase
más débil y debe mejorar antes de adoptar TensorFlow en producción.
```

### Resultado inicial multiclase

Se probaron tres variantes sobre el dataset piloto de `vid`, `olivo`,
`frutales`, `incultos` y `anuales`.

1. Observaciones temporales sueltas:

```bash
venv/bin/python backend/scripts/experiments/entrenar_clasificador_tensorflow.py \
  --input backend/data/dataset_clasificacion_multiclase_temporal.csv \
  --output-dir backend/models/clasificador_tensorflow/multiclase_crudo_piloto \
  --classes vid olivo frutales incultos anuales \
  --epochs 100 \
  --patience 12 \
  --batch-size 128
```

Resultado:

| Métrica | Valor |
|---------|-------|
| accuracy | 0.391 |
| macro F1 | 0.380 |

2. Dataset ancho, todas las features numéricas:

```bash
venv/bin/python backend/scripts/experiments/entrenar_clasificador_tensorflow.py \
  --input backend/data/dataset_clasificacion_multiclase_wide.csv \
  --output-dir backend/models/clasificador_tensorflow/multiclase_crudo_wide_piloto \
  --classes vid olivo frutales incultos anuales \
  --feature-set all \
  --epochs 150 \
  --patience 20 \
  --batch-size 64
```

Resultado:

| Métrica | Valor |
|---------|-------|
| accuracy | 0.450 |
| macro F1 | 0.451 |

3. Dataset ancho, solo features espectrales limpias y red más regularizada:

```bash
venv/bin/python backend/scripts/experiments/entrenar_clasificador_tensorflow.py \
  --input backend/data/dataset_clasificacion_multiclase_wide.csv \
  --output-dir backend/models/clasificador_tensorflow/multiclase_crudo_wide_regularizado_piloto \
  --classes vid olivo frutales incultos anuales \
  --feature-set wide-spectral \
  --hidden-units 64 \
  --dropout 0.45 \
  --l2 0.01 \
  --learning-rate 0.0007 \
  --epochs 180 \
  --patience 25 \
  --batch-size 64
```

Resultado:

| Métrica | Valor |
|---------|-------|
| accuracy | 0.460 |
| macro F1 | 0.449 |

4. CNN 1D temporal, una secuencia por parcela:

```bash
venv/bin/python backend/scripts/experiments/entrenar_cnn_temporal_clasificacion.py \
  --input backend/data/dataset_clasificacion_multiclase_temporal.csv \
  --output-dir backend/models/clasificador_tensorflow/cnn_temporal_multiclase_piloto \
  --classes vid olivo frutales incultos anuales \
  --min-timesteps 3 \
  --epochs 180 \
  --patience 25 \
  --batch-size 64 \
  --filters 64 128 \
  --dropout 0.35 \
  --l2 0.001
```

Arquitectura:

```text
Input: (parcelas, fechas, features espectrales)
↓
Conv1D(64, kernel=3) + BatchNorm + Dropout
↓
Conv1D(128, kernel=3) + BatchNorm + Dropout
↓
GlobalAveragePooling1D
↓
Dense(64)
↓
Dense(5, softmax)
```

Resultado:

| Métrica | Valor |
|---------|-------|
| accuracy | 0.556 |
| macro F1 | 0.553 |
| weighted F1 | 0.553 |

Configuración:

```text
parcelas: 492
fechas: 4
features por fecha: 42
train: 319
validation: 74
test: 99
```

Reporte por clase de la CNN temporal:

| Clase | Precision | Recall | F1 |
|-------|-----------|--------|----|
| anuales | 0.591 | 0.650 | 0.619 |
| frutales | 0.464 | 0.650 | 0.542 |
| incultos | 0.800 | 0.600 | 0.686 |
| olivo | 0.550 | 0.579 | 0.564 |
| vid | 0.429 | 0.300 | 0.353 |

Conclusión multiclase:

```text
La CNN temporal es la variante neuronal más prometedora: mejora claramente a la
MLP sobre observaciones sueltas y a la MLP sobre dataset ancho. Aun así, el
resultado piloto no es suficiente para adopción operativa. La principal
confusión sigue entre frutales, olivo y vid. Para una evaluación seria hace
falta ampliar el dataset a más parcelas por clase y 12 o más ventanas
fenológicas.
```

### Criterio de adopción

La red neuronal solo debería reemplazar o complementar al clasificador actual si
cumple al menos estas condiciones:

- mejora macro F1 en validación por parcela;
- mantiene buen recall en `olivo`, clase minoritaria;
- no depende de `area_m2` para explicar la mejora;
- no degrada la interpretabilidad necesaria para auditar errores;
- mantiene tiempos razonables para reentrenamiento en el entorno cloud.

### Importancia de features

Random Forest calcula la importancia de cada feature midiendo
cuánto reduce la impureza de Gini en promedio a lo largo de
todos los árboles y todas las divisiones donde aparece ese feature:

    Importancia(f) = Σ (reducción de Gini por divisiones en f) / total

Un feature con alta importancia aparece frecuentemente en los
primeros nodos de los árboles, donde las divisiones tienen
mayor impacto en la clasificación final.

---

## Interpretación agronómica del clasificador

El modelo aprovecha dos tipos de diferencias entre vid y olivo:

**Diferencias espectrales permanentes:**
- El olivo tiene hoja perenne con estructura cerosa que refleja
  más en SWIR, resultando en MSI sistemáticamente más bajo.
- La vid tiene hoja caduca con mayor contenido de clorofila
  activa en verano, resultando en NDVI más alto en enero-marzo.

**Diferencias fenológicas estacionales:**
- Julio-agosto: vid sin hoja (NDVI < 0.1, MSI > 1.5) vs
  olivo con hoja (NDVI ~0.3, MSI ~0.8). Esta es la señal
  más discriminativa capturada por mes_sin y mes_cos.
- Octubre-noviembre: brotación de la vid genera un aumento
  rápido de NDVI que el olivo no presenta.

---

## Referencias

- Breiman, L. (2001). Random forests. Machine Learning, 45(1), 5-32.
  https://doi.org/10.1023/A:1010933404324

- Navrozidis, I., Alexandridis, T., Moshou, D., Haugommard, A.,
  & Lagopodi, A. (2022). Implementing Sentinel-2 data and machine
  learning to detect plant stress in olive groves.
  Remote Sensing, 14(23), 5947.
  https://doi.org/10.3390/rs14235947

- Mustapha, M., & Zineddine, M. (2024). An evaluative technique
  for drought impact on variation in agricultural LULC using
  remote sensing and machine learning.
  Environmental Monitoring and Assessment, 96(515).
  https://doi.org/10.1007/s10661-024-12677-0
