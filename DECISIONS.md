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

## 2025-04-20
### Próxima iteración pendiente: bandas espectrales crudas
Queda pendiente regenerar el dataset incluyendo las bandas
espectrales crudas de Sentinel-2 (B2, B3, B4, B8, B11) como
features adicionales del clasificador. Esto requiere volver a
correr el pipeline de extracción (~3 horas) y se estima que
puede mejorar el accuracy a 73-77% basándose en literatura
(Mustapha & Zineddine, 2024).