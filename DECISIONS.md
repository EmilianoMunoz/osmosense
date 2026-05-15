# Decisiones Técnicas — Estrés Hídrico San Rafael

## 20/04/2026
### Fuente de imágenes satelitales: Google Earth Engine (GEE)
Se evaluaron tres alternativas para acceder a imágenes Sentinel-2:
- Google Earth Engine (GEE)
- Copernicus Data Space (CDSE)
- AWS Open Data (S3)

Se eligió GEE porque el procesamiento ocurre en sus servidores,
evitando la descarga de imágenes crudas de decenas de GB. El catálogo
COPERNICUS/S2_SR_HARMONIZED provee reflectancia superficial ya corregida
atmosféricamente (Level-2A), lista para calcular índices espectrales sin
preprocesamiento adicional.

## 20/04/2026
### Tipo de cuenta GEE: Comunidad (no comercial / académica)
Se eligió el plan Comunidad (150 EECU/mes) por ser suficiente para el
volumen de datos de la tesis (estimado en 40-55 EECU totales) y no
requerir cuenta de facturación. El procesamiento principal ocurre
server-side en GEE, por lo que el consumo local de recursos es mínimo.

## 20/04/2026
### Colección Sentinel-2: S2_SR_HARMONIZED
Se eligió COPERNICUS/S2_SR_HARMONIZED sobre S2_SR por incluir
corrección de inconsistencias radiométricas entre distintas versiones
del procesador de ESA, garantizando consistencia en series temporales
largas (2022-2024).

## 20/04/2026
### Umbral de nubosidad: 20%
Se definió 20% como umbral inicial de nubosidad basado en práctica
estándar en teledetección agrícola. San Rafael, Mendoza, es una zona
árida con baja cobertura nubosa, por lo que este umbral no representa
una restricción significativa en la disponibilidad de imágenes.
Puede ajustarse en iteraciones posteriores según necesidad.

## 20/04/2026
### Bandas seleccionadas de Sentinel-2
Se seleccionaron 6 de las 13 bandas disponibles:
- B2 (Blue): clasificación de tipo de cultivo
- B3 (Green): cálculo de NDWI
- B4 (Red): cálculo de NDVI
- B8 (NIR): cálculo de NDVI y NDWI
- B11 (SWIR-1): detección de estrés hídrico
- B12 (SWIR-2): detección de estrés hídrico

Las bandas restantes (B1, B5, B6, B7, B8A, B9, B10) fueron descartadas
por no aportar información relevante para los objetivos del proyecto.

## 20/04/2026
### Zona geográfica: capa FAO/GAUL/2015/level2
El polígono del departamento San Rafael se obtiene directamente desde
la capa administrativa FAO/GAUL incorporada en GEE, filtrando por
ADM1_NAME = "Mendoza" y ADM2_NAME = "San Rafael". Esto evita la
necesidad de mantener archivos shapefile externos para la zona base.
Las parcelas individuales se definirán como GeoJSON propios.

## 20/04/2026
### Stack tecnológico
- Lenguaje: Python 3
- Procesamiento satelital: earthengine-api, geemap
- Datos geoespaciales: geopandas, shapely, rasterio
- Backend (fase siguiente): FastAPI, uvicorn
- Variables de entorno: python-dotenv
- Análisis de datos: numpy, pandas

Se eligió Python por ser el estándar en proyectos de teledetección,
machine learning y análisis geoespacial, con amplia disponibilidad
de librerías especializadas.

## 20/04/2026
### Estrategia de imagen: mosaico mediano en lugar de imagen individual
Se reemplazó la selección de imagen individual (coleccion.first()) por
un mosaico mediano (coleccion.median()) generado a partir de todas las
imágenes disponibles en el período. Esto garantiza cobertura completa
del área de interés aunque ninguna imagen individual cubra todas las
parcelas. La fecha se maneja como rango de referencia del período
analizado.

## 20/04/2026
### Índices espectrales seleccionados
Se definieron 5 índices espectrales basados en revisión de literatura
reciente (2023-2025) sobre viñedos y olivares con Sentinel-2:
- NDMI (B8-B11)/(B8+B11): índice principal de estrés hídrico.
  Detecta cambios en contenido de agua foliar 2-4 semanas antes
  de síntomas visibles.
- NDVI (B8-B4)/(B8+B4): vigor general del cultivo. Útil para
  series temporales y diferenciación entre cultivos.
- NDWI (B3-B8)/(B3+B8): contenido de agua superficial.
- MSI B11/B8: estrés hídrico con interpretación inversa al NDMI.
  Valores más altos indican mayor estrés.
- SAVI 1.5*(B8-B4)/(B8+B4+0.5): variante del NDVI que corrige
  el efecto del suelo desnudo, relevante para zonas áridas
  como San Rafael.

## 20/04/2026
### Extracción de estadísticas: reduceRegion con escala 10m
Se utiliza ee.Reducer.mean() con escala de 10 metros (resolución
nativa de Sentinel-2 para bandas B3, B4, B8) para extraer el valor
medio de cada índice dentro del polígono de cada parcela. Esto
produce un vector de features por parcela y fecha, que es la unidad
de entrada para los modelos ML.

## 20/04/2026
### Persistencia inicial: CSV
Los resultados de índices se persisten en CSV como solución inicial
para desarrollo y pruebas. Se migrará a PostgreSQL + PostGIS cuando
se integre el backend FastAPI (HU-005 completa con BD en fase
siguiente).

## 22/04/2026
### Dataset de clasificación de cultivos
Se construyó un dataset de 140 muestras para entrenar el clasificador
de cultivos (vid / olivo) con las siguientes características:
- 19 parcelas de vid y 16 parcelas de olivo etiquetadas manualmente
  mediante geojson.io sobre imágenes de Google Earth.
- 4 períodos temporales (T1-T4 2024) para capturar variabilidad
  estacional de cada cultivo.
- Features: NDVI, NDMI, NDWI, MSI, SAVI.
- Distribución: 76 muestras vid / 64 muestras olivo.

### Etiquetado manual de parcelas
Las parcelas fueron identificadas visualmente en Google Earth y
digitalizadas con geojson.io. La distinción entre vid y olivo se
realizó por patrón visual: hileras rectas y regulares para vid,
copas redondeadas individuales para olivo. Se etiquetaron cuadros
individuales dentro de establecimientos, permitiendo que un mismo
predio tenga múltiples etiquetas de cultivo distintas.

## 22/04/2026
### Fuente oficial de parcelas: IDEMendoza
Se reemplazaron las parcelas etiquetadas manualmente por datos
oficiales obtenidos del portal IDEMendoza (Infraestructura de
Datos Espaciales de Mendoza):
https://ide.mendoza.gov.ar
El dataset provee el parcelario catastral con tipo de cultivo
por parcela para todo el territorio de Mendoza. Se filtraron
las parcelas correspondientes al departamento de San Rafael
con cultivos de vid y olivo.

### Justificación del modelo clasificador vs catastro estático
El parcelario de IDEMendoza provee etiquetas de cultivo por parcela
pero con fecha de actualización incierta. El modelo clasificador
permite detectar discrepancias entre el catastro y el estado
espectral actual de la parcela, identificando posibles cambios
de uso de suelo (por ejemplo, reconversión de viñedo a olivar).
Esto agrega valor al sistema más allá de la clasificación pura,
habilitando un caso de uso de monitoreo de cambios de cultivo
a lo largo del tiempo.

Perfecto, exactamente lo esperado (400 parcelas × 4 períodos).
Antes de seguir con el modelo de estrés, hacemos el commit con todo lo que trabajamos hoy. Primero actualizamos la documentación y después commiteamos.

## 23/04/2026
### Fuente oficial de parcelas: IDEMendoza
Se reemplazaron las parcelas etiquetadas manualmente por datos
oficiales del portal IDEMendoza (Infraestructura de Datos
Espaciales de Mendoza):
https://ide.mendoza.gov.ar
El dataset provee el parcelario catastral con tipo de cultivo
por parcela para todo Mendoza (216.721 parcelas). Se filtraron
las correspondientes a San Rafael con cultivos vid y olivo,
obteniendo 16.158 parcelas (15.447 vid, 711 olivo).

### Sistema de coordenadas: reproyección EPSG:3857 → EPSG:4326
El GeoJSON de IDEMendoza estaba en proyección Web Mercator
(EPSG:3857, coordenadas en metros). Se reproyectó a WGS84
(EPSG:4326, grados decimales) usando pyproj para compatibilidad
con Google Earth Engine.

### Muestra de entrenamiento: 400 parcelas balanceadas
Se tomó una muestra aleatoria balanceada de 200 vid y 200 olivo
con random.seed(42) para reproducibilidad. Esta muestra se usó
para extraer índices espectrales en 4 períodos de 2024,
generando 1.600 muestras de entrenamiento.

### Enfoque de etiquetado de estrés hídrico: clasificación relativa
Para el modelo ML de estrés hídrico se adoptó un enfoque de
clasificación relativa (ranking) en lugar de umbrales absolutos.
Las parcelas se clasifican comparando sus índices contra el resto
de parcelas del mismo cultivo en el mismo período. Esto evita
la necesidad de datos de campo externos y es metodológicamente
válido para zonas con heterogeneidad en prácticas de riego como
San Rafael. Limitación: si todas las parcelas estuvieran bien
regadas en un período, algunas se clasificarían igual como
alto estrés por ser las peores relativas.

### Codificación circular del mes para features temporales
Se reemplazó la codificación numérica simple del período (T1-T4)
por codificación circular mediante seno y coseno del mes:

    mes_sin = sin(2π × mes / 12)
    mes_cos = cos(2π × mes / 12)

Justificación: el año es cíclico. Con codificación numérica simple
diciembre (12) y enero (1) quedan en extremos opuestos del rango,
cuando en realidad son meses consecutivos. La codificación circular
preserva esta continuidad, permitiendo que el modelo aprenda
correctamente patrones estacionales que cruzan el límite del año
(por ejemplo, la brotación de la vid entre agosto y octubre).

### Cambio de períodos trimestrales a mensuales
Se reemplazaron los 4 períodos trimestrales por 24 períodos
mensuales (2023 y 2024) por las siguientes razones:

- Captura fenológica más precisa: la vid tiene cambios abruptos
  mes a mes (brotación, floración, maduración, caída de hoja)
  que un trimestre promedia y oculta.
- Mayor volumen de datos: 400 parcelas × 24 meses = 9.600 muestras
  vs 400 × 4 = 1.600 anteriores. El dataset se multiplica por 6.
- Variabilidad interanual: incluir 2023 y 2024 expone al modelo
  a dos años con condiciones climáticas distintas, mejorando
  su capacidad de generalización.
- El trimestre T3 (invierno) era el más discriminativo entre
  vid y olivo. Con datos mensuales julio y agosto quedan
  separados y el modelo puede aprender esa diferencia con
  mayor precisión.

### Incorporación de bandas espectrales crudas como features
Se agregaron las bandas B2, B3, B4, B8 y B11 de Sentinel-2
como features adicionales al clasificador, sumándose a los
5 índices calculados (NDVI, NDMI, NDWI, MSI, SAVI).

Justificación: los índices son combinaciones de bandas y pueden
perder información al comprimirla en un solo número. Proveer
las bandas crudas directamente permite al modelo Random Forest
descubrir combinaciones no contempladas en los índices estándar.
Esto es especialmente útil para distinguir vid de olivo en
condiciones de baja cobertura vegetal (invierno) donde los
índices estándar tienen menor sensibilidad.

### Filtrado de parcelas pequeñas (< 5000m²)
Se filtraron las parcelas con área menor a 5000m² de la muestra
de entrenamiento. Justificación: Sentinel-2 tiene resolución
espacial de 10×10m (100m² por píxel). Una parcela de 5000m²
contiene aproximadamente 50 píxeles, por debajo de este umbral
la media de índices espectrales es muy sensible a píxeles
contaminados por bordes, caminos internos o canales de riego.

Resultado del filtrado:
- Parcelas antes: 400 (200 vid, 200 olivo)
- Parcelas después: 306 (179 vid, 127 olivo)
- Muestras antes: 9.600
- Muestras después: 7.344 (4.296 vid, 3.048 olivo)

El desbalance resultante (4.296 vid vs 3.048 olivo) se compensa
mediante class_weight="balanced" en el clasificador Random Forest,
que ajusta los pesos de cada clase inversamente proporcional
a su frecuencia.

### Evolución del accuracy del clasificador
Se registra la evolución del modelo a lo largo de las iteraciones
para documentar el impacto de cada decisión:

| Versión                              | Dataset        | Accuracy | Varianza |
|--------------------------------------|----------------|----------|----------|
| v1 — 35 parcelas manuales            | 140 muestras   |    96.4% |    ±3.2% |
| v2 — IDEMendoza trimestral           | 1.600 muestras |    65.2% |    ±2.7% |
| v3 — IDEMendoza + fecha numérica     | 1.600 muestras |    66.5% |    ±1.8% |
| v4 — Mensual + codificación circular | 9.600 muestras |    67.6% |    ±1.6% |
| v5 — Sin parcelas < 5000m²           | 7.344 muestras |    70.4% |    ±3.0% |

Nota sobre v1: el accuracy de 96.4% era artificialmente alto porque
las parcelas fueron seleccionadas y etiquetadas manualmente sobre
zonas claramente identificables. No es representativo del
rendimiento real sobre datos del mundo.

El accuracy de 70.4% con datos reales de IDEMendoza es el valor
de referencia para comparar contra el modelo ML de estrés hídrico
(HU-012). La principal fuente de error es el ruido en el catastro:
parcelas desactualizadas, mal delimitadas o con cultivos mixtos.

## 23/04/2026
### Próxima iteración pendiente: bandas espectrales crudas
Queda pendiente regenerar el dataset incluyendo las bandas
espectrales crudas de Sentinel-2 (B2, B3, B4, B8, B11) como
features adicionales del clasificador. Esto requiere volver a
correr el pipeline de extracción (~3 horas) y se estima que
puede mejorar el accuracy a 73-77% basándose en literatura
(Mustapha & Zineddine, 2024).

### Clasificación de parcelas desconocidas: umbral de confianza
Para manejar parcelas que no son vid ni olivo (frutales, suelo
desnudo, zonas urbanas, etc.) se implementó un umbral de confianza
sobre las probabilidades del modelo Random Forest en lugar de
agregar una tercera clase al dataset.

Lógica:
- prob_maxima >= 0.75 → predicción con confianza alta
- prob_maxima >= 0.60 → predicción con confianza media
- prob_maxima <  0.60 → clasificado como "otros"

Justificación: Random Forest devuelve probabilidades por clase.
Una parcela de frutales o suelo desnudo tendrá probabilidades
bajas y similares para vid y olivo porque sus valores espectrales
no se parecen a ninguna de las dos clases entrenadas. El umbral
captura este caso sin necesidad de reentrenar con una tercera
clase, simplificando el pipeline de datos.

Queda pendiente como mejora futura agregar parcelas de FRUTALES,
ANUALES e INCULTOS del catastro IDEMendoza como clase "otros"
explícita para mejorar la precisión de este caso.

### Resultado final clasificador v6: 72.4% accuracy
Incorporación de bandas espectrales crudas (B2, B3, B4, B8, B11)
como features adicionales mejoró el accuracy de 70.4% a 72.4%
con varianza ±2.1%.

La importancia de features se distribuyó más uniformemente entre
los 12 features, indicando que el modelo aprovecha mejor toda la
información disponible. B3 (banda verde, 560nm) resultó el quinto
feature más importante (8.9%), capturando la diferencia de
reflectancia en verde entre la hoja perenne del olivo y la hoja
caduca de la vid.

| Versión                              | Dataset        | Accuracy | Varianza |
|--------------------------------------|----------------|----------|----------|
| v1 — 35 parcelas manuales            | 140 muestras   |    96.4% |    ±3.2% |
| v2 — IDEMendoza trimestral           | 1.600 muestras |    65.2% |    ±2.7% |
| v3 — IDEMendoza + fecha numérica     | 1.600 muestras |    66.5% |    ±1.8% |
| v4 — Mensual + codificación circular | 9.600 muestras |    67.6% |    ±1.6% |
| v5 — Sin parcelas < 5000m²           | 7.344 muestras |    70.4% |    ±3.0% |
| v6 — + bandas crudas                 | 7.344 muestras |    72.4% |    ±2.1% |

### Umbral de confianza para clasificación: 0.63
Se definió 0.63 como umbral mínimo de probabilidad para aceptar
una predicción del clasificador. Por debajo de este valor la
parcela se clasifica como "otros".

Calibración realizada con casos reales del dataset:
- Vid real julio 2024: prob=0.639 → umbral 0.63 la acepta correctamente
- Olivo real julio 2024: prob=0.860 → clasificado con alta confianza
- Suelo desnudo sintético: prob=0.521 → correctamente descartado

Niveles de confianza definidos:
- prob >= 0.75 → confianza alta
- prob >= 0.63 → confianza media
- prob <  0.63 → otros

Nota: el umbral es conservador dado el accuracy del modelo (72.4%).
Con un modelo más preciso el umbral podría subirse a 0.70-0.75
para mayor seguridad en la clasificación.

### Resultado evaluación con umbral de confianza
Con umbral 0.63 el clasificador final muestra:
- 74.6% de parcelas clasificadas con confianza suficiente
- 25.4% descartadas como "otros" (confianza insuficiente)
- Accuracy sobre parcelas confiables: 75.4%

Esto representa una mejora real de 70.0% → 75.4% sobre los
casos donde el modelo tiene certeza. El 25.4% descartado
corresponde principalmente a parcelas con valores espectrales
ambiguos, posiblemente por cultivos mixtos, parcelas en
transición o errores en el catastro de IDEMendoza.

Para la tesis se reportan ambas métricas:
- Accuracy global: 72.4% (validación cruzada)
- Accuracy con umbral: 75.4% (sobre casos confiables)


## 06/05/2026

### Incorporación de clase "otros" al clasificador
Se agregó una tercera clase "otros" al dataset de entrenamiento
compuesta por parcelas de ANUALES, INCULTOS y FRUTALES del
catastro IDEMendoza. Justificación: en producción el modelo
recibe parcelas de cualquier tipo y necesita poder descartarlas
explícitamente en lugar de forzar una clasificación incorrecta
entre vid y olivo.

Distribución del dataset actualizado:
- vid:   200 parcelas × 24 meses = 4.800 muestras
- olivo: 200 parcelas × 24 meses = 4.800 muestras
- otros: 200 parcelas × 24 meses = 4.800 muestras
- Total: 14.400 muestras balanceadas

Fuentes de la clase "otros":
- ANUALES:  26.339 parcelas disponibles en San Rafael
- INCULTOS: 18.871 parcelas disponibles en San Rafael
- FRUTALES:  9.036 parcelas disponibles en San Rafael

Con "otros" como clase explícita el umbral de confianza pasa
de ser el único mecanismo de descarte a ser una capa adicional
de seguridad sobre una clasificación ya más robusta.

### Estrategia de ensemble de modelos (recomendación del tutor)
El tutor recomendó entrenar múltiples modelos de clasificación,
compararlos y combinarlos para alcanzar un accuracy objetivo
del 90%. Se decidió evaluar tres modelos:

**Modelo 1 — Random Forest**
Baseline actual. 100 árboles con votación mayoritaria.
Robusto con datos ruidosos. Accuracy actual: 72.4%.

**Modelo 2 — Gradient Boosting**
Construye árboles en secuencia donde cada árbol corrige los
errores del anterior. Generalmente supera al Random Forest
en datos tabulares. Parámetros: 100 estimadores, profundidad
máxima 5, learning rate 0.1.

**Modelo 3 — SVM (Support Vector Machine)**
Encuentra el hiperplano óptimo que separa las clases en el
espacio de features. Requiere normalización de datos (Pipeline
con StandardScaler). Kernel RBF con C=10 y gamma=scale.
class_weight=balanced para compensar desbalance entre clases.

**Combinaciones a evaluar:**
- Voting soft entre los 3 modelos
- Voting soft entre los 2 mejores modelos

Voting soft promedia las probabilidades de cada clase entre
los modelos participantes, dando más peso a las predicciones
más confiables que el voting hard (mayoría simple).

El modelo o combinación con mayor accuracy en validación
cruzada de 5 folds se guardará como clasificador definitivo
en models/clasificador_cultivo.pkl.

### Script preparar_dataset.py
Se creó el script scripts/preparar_dataset.py para documentar
y reproducir todo el proceso de preparación del dataset:
- Carga parcelas_ide.geojson (IDEMendoza)
- Filtra San Rafael por bounding box
- Separa en tres clases: vid, olivo, otros
- Reproyecta de EPSG:3857 a EPSG:4326
- Filtra parcelas < 5000m²
- Genera muestra balanceada de 200 parcelas por clase
- Exporta muestra_entrenamiento.geojson

Parámetros configurables en el script:
- MUESTRAS_POR_CLASE = 200
- AREA_MINIMA = 5000 m²
- RANDOM_SEED = 42

### Fecha del catastro IDEMendoza: 20 de febrero 2025
El parcelario de IDEMendoza tiene fecha de creación y última
edición del 20 de febrero de 2025 (timestamp 1740061366000).
Las imágenes satelitales utilizadas son de 2023 y 2024, por
lo que el desfase temporal entre etiquetas e imágenes es de
menos de 2 años. En la zona vitivinícola de San Rafael los
cambios de uso de suelo son lentos (reconversión de cultivos
tarda varios años), por lo que se considera que las etiquetas
son representativas de las imágenes utilizadas.

### Incorporación de bandas red-edge (B5, B6, B7) y NDRE
Se agregaron las bandas red-edge de Sentinel-2 (B5 705nm,
B6 740nm, B7 783nm) y el índice NDRE (Normalized Difference
Red Edge Index) como features adicionales del clasificador.

Fórmula NDRE: (B8 - B5) / (B8 + B5)

Justificación: las bandas red-edge son más sensibles a
diferencias en estructura del dosel y contenido de clorofila
que las bandas visibles e infrarrojo. Se esperaba que ayudaran
a separar vid de frutales espectralmente.

Resultado: mejora marginal en SVM de 46.0% a 47.2%.
La incorporación de red-edge no resolvió el problema de
separabilidad entre vid y frutales.


### Problema de separabilidad vid vs frutales
Se identificó que vid y frutales son espectralmente
indistinguibles con los features actuales (índices espectrales
+ bandas Sentinel-2 a 10m de resolución). Análisis de la
matriz de confusión del mejor modelo (SVM):

- Vid clasificada como frutales: 503/960 casos (52%)
- Frutales clasificados como vid: 75/960 casos (8%)

El solapamiento espectral entre vid y frutales es estructural:
ambos son cultivos perennes con dosel similar, ciclos
fenológicos parecidos y reflectancias similares en todas
las bandas disponibles de Sentinel-2.

Para resolver este problema se necesitaría alguna de las
siguientes alternativas:
- Imágenes de mayor resolución espacial (Planetscope 3m)
- Datos de campo con GPS en parcelas conocidas
- Imágenes hiperespectrales con más bandas espectrales
- Información auxiliar como altura del dosel (LiDAR)

### Evolución completa del clasificador — resumen

| Versión | Clases | Dataset | Accuracy |
|---------|--------|---------|----------|
| v1 — parcelas manuales | 2 (vid/olivo) | 140 muestras | 96.4% |
| v2 — IDEMendoza trimestral | 2 | 1.600 muestras | 65.2% |
| v3 — + fecha numérica | 2 | 1.600 muestras | 66.5% |
| v4 — mensual + circular | 2 | 9.600 muestras | 67.6% |
| v5 — sin parcelas < 5000m² | 2 | 7.344 muestras | 70.4% |
| v6 — + bandas crudas | 2 | 7.344 muestras | 72.4% |
| v7 — + clase otros | 3 | 14.400 muestras | 57.1% |
| v8 — 4 clases (vid/olivo/frutales/descarte) | 4 | 19.200 muestras | 46.0% |
| v9 — + bandas red-edge y NDRE | 4 | 19.200 muestras | 47.2% |

Conclusión: el mejor resultado con datos reales de IDEMendoza
es 72.4% con 2 clases (vid/olivo). Agregar más clases reduce
el accuracy por solapamiento espectral entre vid y frutales.

### Objetivo de accuracy 90% — análisis de viabilidad
El tutor estableció un objetivo de accuracy del 90%. Con los
datos y features actuales este objetivo no es alcanzable por
las siguientes razones:

1. Ruido en el catastro IDEMendoza: etiquetas con incertidumbre
   temporal y espacial.
2. Resolución espacial de Sentinel-2: píxeles de 10×10m
   contienen mezcla de cultivos en parcelas pequeñas.
3. Solapamiento espectral vid/frutales: clases no separables
   con los índices disponibles.

En literatura académica con datos controlados se reportan
accuracies de 85-92%. Con datos reales de catastro el rango
típico es 70-80%.

Próximos pasos a discutir con el tutor:
- Opción A: aceptar 72.4% con 2 clases como resultado válido
  y justificarlo con literatura de datos reales
- Opción B: estrategia de dos modelos en cascada
  (agrícola/no-agrícola → vid/olivo)
- Opción C: conseguir datos de campo validados para mejorar
  la calidad de las etiquetas


## 2026-05-08
### Corrección crítica del pipeline — eliminación de muestras inválidas
Se detectó que una gran proporción del dataset contenía valores
espectrales iguales a 0 en todas las bandas e índices. Estas
muestras provenían de píxeles enmascarados por nubes, parcelas
fuera de cobertura efectiva, bordes contaminados y geometrías
sin datos válidos en ciertos meses.

El problema original era que los valores None de GEE se
reemplazaban por 0:
    props.get("NDVI") or 0

Esto introducía ruido severo en el espacio espectral y degradaba
la separabilidad entre clases.

Correcciones aplicadas:
- Descartar parcelas sin datos válidos en lugar de reemplazar por 0
- Aplicar máscara real de nubes
- Usar buffer negativo en geometrías para evitar bordes contaminados
- Eliminar muestras inválidas antes de persistir el dataset

Resultado:
- Dataset: 19.200 → 12.752 muestras
- Accuracy SVM: 47.2% → 57.1%
- Fuerte reducción de confusión vid ↔ frutales

Conclusión: la principal limitación del clasificador no era el
modelo sino la calidad del dataset y el ruido espectral
introducido por muestras inválidas.

## 2026-05-08
### Mejora en separabilidad vid vs frutales tras limpieza del pipeline
Tras limpiar el pipeline se observó mejora importante en la
clasificación de vid.

Comparación SVM antes/después:
- Recall vid: 0.21 → 0.44
- Vid clasificada como frutales: 503 → 148 casos

Conclusión: el problema de separabilidad entre vid y frutales
no era completamente estructural sino amplificado por ruido
espectral del dataset.

## 2026-05-08
### Incorporación de estadísticas espaciales por parcela
El pipeline original usaba únicamente la media espectral
(Reducer.mean). Se modificó para calcular mean, stdDev, min
y max sobre todos los índices y bandas.

Ejemplo de nuevas features:
    ndvi_mean, ndvi_std, ndvi_min, ndvi_max

Justificación: los viñedos presentan mayor heterogeneidad
espacial (hileras, suelo expuesto, cobertura discontinua)
mientras que los frutales tienden a generar firmas más
homogéneas. La desviación estándar y rangos espectrales
capturan esta diferencia mejor que la media simple, mejorando
especialmente la separación vid ↔ frutales y vid ↔ descarte.

Estado: dataset regenerándose con nuevas features espaciales.

## 2026-05-08
### Incorporación de dataset temporal multi-fecha
Se detectó que usar una única fecha por parcela limitaba la
capacidad del modelo para capturar diferencias reales entre
cultivos. Se implementó un pipeline temporal donde cada parcela
se representa mediante una secuencia anual completa de
observaciones Sentinel-2.

El nuevo dataset agrupa todas las observaciones históricas por
parcela y concatena las features temporales generando columnas
como:
    ndvi_mean_2023_01, ndvi_std_2023_01,
    b8_mean_2023_06, savi_mean_2024_10

Cada fila ya no representa una imagen individual sino una
parcela completa con comportamiento temporal anual.

Resultado:
- 541 parcelas únicas
- 530 features temporales

Hipótesis: la evolución temporal anual es más discriminativa
que una observación aislada, especialmente para separar
vid ↔ frutales y vid ↔ descarte. Además permite a futuro
detectar cambios de cultivo mediante comportamiento fenológico
anómalo.

## 2026-05-08
### Ampliación masiva del dataset de entrenamiento
Se amplió la muestra utilizando parcelas IDE de San Rafael con
filtrado mínimo por superficie (>= 5000m²).

Disponibilidad por clase en San Rafael:
- vid:      15.447 parcelas
- olivo:       711 parcelas
- frutales:  9.036 parcelas
- descarte: 45.210 parcelas

Muestra balanceada parcial final:
- vid:      1.000
- frutales: 1.000
- descarte: 1.000
- olivo:      448 (limitación estructural: pocas parcelas reales)
- Total:    3.448 parcelas

Limitación detectada: en San Rafael existen muy pocas parcelas
de olivo en la base IDE, por lo que no es posible balancear
completamente esa clase sin introducir datos artificiales.
Se mantuvo class_weight="balanced" en los modelos para
compensar el desbalance natural.

## 2026-05-08
### Migración de Gradient Boosting clásico a XGBoost
Se reemplazó GradientBoostingClassifier de sklearn por XGBoost
por su mejor manejo de datasets tabulares complejos y grandes
cantidades de features temporales.

Configuración:
    n_estimators=300, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8

Resultado: XGBoost superó consistentemente a Random Forest en
accuracy y validación cruzada. Además provee feature importance
más interpretables sobre el comportamiento temporal y espectral.

## 2026-05-08
### Análisis de importancia de variables temporales (XGBoost)
Las features más relevantes según XGBoost corresponden a:
- SAVI, NDWI, NDMI, MSI
- Bandas SWIR/NIR
- Meses de primavera/verano

Ejemplos de features relevantes:
    b11_mean_2023_02, savi_mean_2023_10,
    ndwi_mean_2024_10, ndmi_mean_2023_11

Interpretación: el modelo aprende principalmente patrones de
comportamiento hídrico, vigor vegetativo, respuesta SWIR y
estacionalidad fenológica. Confirma que la discriminación entre
cultivos depende más de patrones temporales completos que de
una única imagen aislada.

## 2026-05-08
### Objetivo estratégico del clasificador — detección de cambios
El clasificador no fue diseñado únicamente para etiquetar
cultivos actuales. El objetivo principal es que a futuro pueda
detectar cambios de cultivo, reconversión agrícola, abandono
de parcelas y reemplazo de especies.

Hipótesis: si una parcela modifica su comportamiento espectral-
temporal histórico, el modelo detectará inconsistencias respecto
a la clase original aprendida.

Aplicaciones futuras previstas:
- Monitoreo agrícola automático
- Alertas de cambio de uso de suelo
- Detección de reconversión vid ↔ olivo ↔ frutales
- Análisis multitemporal automatizado


## 15/05/2026

Implementación de clasificador binario (cultivo vs descarte)

Se decidió incorporar una etapa previa de clasificación binaria para separar parcelas útiles (cultivos) de parcelas irrelevantes (descarte), en lugar de abordar directamente el problema multiclase completo.

El modelo original intentaba clasificar simultáneamente:

vid
frutales
olivo
descarte

Esto generaba una complejidad innecesaria, ya que la clase "descarte" introduce alta variabilidad espectral y no responde a un patrón agrícola definido.

Se rediseñó el pipeline en dos etapas:

Clasificador binario:
cultivo vs descarte
Clasificador multiclase:
vid vs frutales vs olivo

El clasificador binario fue implementado utilizando XGBoost con regularización y balanceo de clases mediante scale_pos_weight.

Se introdujo además el uso de probabilidades (predict_proba) en lugar de clasificación directa, permitiendo ajustar manualmente el umbral de decisión (threshold) para optimizar el comportamiento del modelo según el objetivo del sistema.

Se evaluaron distintos valores de threshold:

0.5 (default): comportamiento conservador, mayor pérdida de cultivos
0.4: mejora en recall de cultivo
0.3: máximo recall pero incremento significativo de falsos positivos
0.35: punto de equilibrio

El valor final seleccionado fue:

threshold = 0.35

Resultados obtenidos:

Accuracy: ~0.84
Validación cruzada: ~0.851 ± 0.012
Recall cultivo: ~0.93

Esto implica que el modelo detecta aproximadamente el 93% de las parcelas de cultivo reales, minimizando la pérdida de información relevante.

Se observó un aumento en falsos positivos (parcelas de descarte clasificadas como cultivo), lo cual es aceptable dado que estas serán posteriormente filtradas por el modelo multiclase.