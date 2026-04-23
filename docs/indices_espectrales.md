# Índices Espectrales para Clasificación y Detección de Estrés Hídrico

## ¿Qué es un índice espectral?

Un índice espectral es una operación matemática entre dos o más
bandas de una imagen satelital que resalta una característica
específica de la superficie terrestre. Sentinel-2 captura la
reflectancia de la superficie en distintas longitudes de onda.
Cada cultivo refleja la luz de manera diferente según su estado
fisiológico, lo que permite distinguirlos matemáticamente.

---

## Índices utilizados en el sistema

### 1. NDVI — Normalized Difference Vegetation Index
**Fórmula:** (B8 - B4) / (B8 + B4)
**Bandas:** NIR (842nm) y Red (665nm)

Mide el vigor vegetativo general. La vegetación sana absorbe
fuertemente en el rojo (fotosíntesis) y refleja en el infrarrojo
cercano (estructura celular). Valores altos indican vegetación
densa y activa.

| Valor | Interpretación |
|-------|---------------|
| < 0.1 | Suelo desnudo, zonas urbanas |
| 0.1 – 0.3 | Vegetación escasa o estresada |
| 0.3 – 0.5 | Vegetación moderada |
| > 0.5 | Vegetación densa y vigorosa |

**Rol en el sistema:**
- Clasificación: diferencia zonas con vegetación de zonas sin ella.
  La vid en invierno cae a valores bajos (pierde hoja) mientras
  el olivo se mantiene moderado (perennifolio).
- Detección de estrés: valores por debajo del promedio histórico
  de una parcela indican pérdida de vigor, posiblemente por
  déficit hídrico.

---

### 2. NDMI — Normalized Difference Moisture Index
**Fórmula:** (B8 - B11) / (B8 + B11)
**Bandas:** NIR (842nm) y SWIR-1 (1610nm)

**Índice principal de estrés hídrico del sistema.** Mide el
contenido de agua en los tejidos foliares. La banda SWIR es
sensible al agua líquida en las hojas: cuando hay déficit hídrico
las células pierden turgencia y la reflectancia SWIR aumenta,
haciendo caer el NDMI.

| Valor | Interpretación |
|-------|---------------|
| > 0.2 | Sin estrés hídrico |
| 0.0 – 0.2 | Estrés bajo |
| -0.2 – 0.0 | Estrés medio |
| < -0.2 | Estrés alto |

**Rol en el sistema:**
- Es el feature con mayor peso en la detección de estrés hídrico.
- Detecta déficit hídrico 2 a 4 semanas antes de que aparezcan
  síntomas visibles en la planta.
- Diferencia vid de olivo: el olivo mantiene valores más altos
  en verano por su mayor eficiencia en el uso del agua.

---

### 3. NDWI — Normalized Difference Water Index
**Fórmula:** (B3 - B8) / (B3 + B8)
**Bandas:** Green (560nm) y NIR (842nm)

Mide el contenido de agua superficial y en el dosel vegetal.
Originalmente diseñado para detectar cuerpos de agua, en
agricultura indica la disponibilidad hídrica en la superficie
del cultivo.

| Valor | Interpretación |
|-------|---------------|
| > 0.3 | Agua libre o vegetación muy húmeda |
| 0.0 – 0.3 | Vegetación con buen contenido hídrico |
| -0.3 – 0.0 | Vegetación con estrés moderado |
| < -0.3 | Suelo seco o vegetación muy estresada |

**Rol en el sistema:**
- Complementa al NDMI en la detección de estrés hídrico.
- Útil para identificar zonas con riego reciente.

---

### 4. MSI — Moisture Stress Index
**Fórmula:** B11 / B8
**Bandas:** SWIR-1 (1610nm) y NIR (842nm)

Interpretación inversa al NDMI: valores más altos indican
mayor estrés hídrico. Es el índice más discriminativo para
clasificar vid y olivo según los resultados del modelo
(importancia: 27.2%).

| Valor | Interpretación |
|-------|---------------|
| < 0.6 | Sin estrés |
| 0.6 – 1.0 | Estrés bajo |
| 1.0 – 1.5 | Estrés medio |
| > 1.5 | Estrés alto |

**Rol en el sistema:**
- Feature más importante del clasificador de cultivos (27.2%).
- En invierno la vid sin hoja tiene MSI muy alto, el olivo
  con hoja lo mantiene bajo. Esta diferencia es la señal
  más clara para distinguir ambos cultivos.

---

### 5. SAVI — Soil Adjusted Vegetation Index
**Fórmula:** 1.5 × (B8 - B4) / (B8 + B4 + 0.5)
**Bandas:** NIR (842nm) y Red (665nm)

Variante del NDVI que incorpora un factor de corrección (L=0.5)
para reducir el efecto del suelo desnudo en la señal de
vegetación. Especialmente relevante en zonas áridas y semiáridas
como San Rafael, donde el suelo desnudo entre hileras de vid
puede contaminar la lectura del NDVI puro.

**Rol en el sistema:**
- Complementa al NDVI en parcelas con baja densidad de cobertura.
- Más estable que el NDVI en períodos de baja actividad vegetativa
  (invierno en viñedos).

---

## Cómo se usan los índices en el clasificador

El modelo Random Forest recibe un vector de 5 features por
parcela y fecha:
[NDVI, NDMI, NDWI, MSI, SAVI] → Random Forest → vid / olivo / otros

La importancia relativa de cada feature según el modelo entrenado:

| Feature | Importancia |
|---------|------------|
| MSI | 27.2% |
| NDVI | 19.5% |
| NDMI | 18.4% |
| NDWI | 17.8% |
| SAVI | 17.1% |

El MSI es el más discriminativo porque captura la diferencia
fenológica más marcada entre vid y olivo: en invierno la vid
pierde completamente la hoja (MSI alto) mientras el olivo la
mantiene (MSI bajo).

---

## Cómo se usan los índices en la detección de estrés

La clasificación de estrés por reglas combina tres índices
mediante un promedio ponderado:

Estrés = NDMI (50%) + MSI (30%) + NDVI (20%)

Los pesos fueron definidos como decisión de diseño del sistema
basándose en el rol de cada índice según la literatura:
- NDMI recibe el mayor peso (50%) por ser el índice más directo
  del contenido de agua foliar, detectando déficit hídrico antes
  de que aparezcan síntomas visibles (Gao, 1996).
- MSI recibe peso intermedio (30%) por su sensibilidad al estrés
  hídrico en la banda SWIR, siendo especialmente discriminativo
  entre vid y olivo según los resultados del modelo entrenado.
- NDVI recibe menor peso (20%) por ser un indicador indirecto
  del estado hídrico, más relacionado con el vigor general
  que con el contenido de agua foliar.

Nota: estos pesos corresponden a la clasificación por reglas
(HU-006). El modelo ML (HU-008) aprenderá los pesos óptimos
automáticamente a partir de los datos de entrenamiento.

## Referencias

- Gao, B.C. (1996). NDWI — A normalized difference water index
  for remote sensing of vegetation liquid water from space.
  Remote Sensing of Environment, 58(3), 257-266.
  https://doi.org/10.1016/S0034-4257(96)00067-3

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

- Bchir, A., & Masmoudi-Charfi, C. (2024). Estimating and mapping
  NDVI and NDMI indexes by remote sensing of olive orchards in
  different Tunisian regions. In Recent Advances in Environmental
  Science from the Euro-Mediterranean and Surrounding Regions.
  Springer, Cham.
  https://doi.org/10.1007/978-3-031-43922-3_116

- García Lima, E.E. (2024). Detección multiescala de estrés hídrico
  en choperas empleando modelos de transferencia radiativa a partir
  de imágenes Sentinel-2 y sensores ecofisiológicos en tiempo casi
  real. Trabajo Fin de Máster, Universidad de León.

- Huete, A.R. (1988). A soil-adjusted vegetation index (SAVI).
  Remote Sensing of Environment, 25(3), 295-309.
  https://doi.org/10.1016/0034-4257(88)90106-X