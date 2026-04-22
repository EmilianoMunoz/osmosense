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