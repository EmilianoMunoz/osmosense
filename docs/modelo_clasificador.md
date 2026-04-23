# Modelo Clasificador de Cultivos — Documentación Técnica

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