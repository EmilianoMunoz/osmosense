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