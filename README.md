# Detección y Predicción de Estrés Hídrico en Viñedos y Olivares
### San Rafael, Mendoza — Tesis de Grado

## Descripción
Plataforma web para monitorear y predecir el estrés hídrico de viñedos y olivares
en parcelas agrícolas de San Rafael, Mendoza, mediante el procesamiento de imágenes
satelitales Sentinel-2 y modelos de inteligencia artificial.

## Funcionalidades
- Obtención y filtrado de imágenes Sentinel-2 via Google Earth Engine
- Cálculo de índices espectrales (NDVI, NDWI) por parcela
- Clasificación automática de tipo de cultivo (vid / olivo)
- Detección del nivel de estrés hídrico mediante modelos ML
- Visualización en mapa interactivo web
- Predicción a corto plazo integrando datos climáticos

## Requisitos
- Python 3.10+
- Cuenta en Google Earth Engine (plan Comunidad / Académico)
- Ubuntu 22.04 o superior (desarrollado y probado en este entorno)

## Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/tuusuario/estres-hidrico.git
cd estres-hidrico
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
pip install -e .
```

### 4. Configurar variables de entorno
Crear un archivo `.env` en la raíz del proyecto:
GEE_PROJECT_ID=tu-proyecto-gee

### 5. Autenticarse con Google Earth Engine
```bash
earthengine authenticate
```

## Uso

### Verificar pipeline de imágenes
```bash
python scripts/test_pipeline.py
```

Resultado esperado:
GEE inicializado correctamente
Obteniendo geometría de San Rafael...
Geometría obtenida correctamente
Buscando imágenes Sentinel-2...
Imágenes disponibles: 268
Mejor imagen → fecha: 2024-03-25 | nubosidad: 0.0%
Bandas seleccionadas: ['B2', 'B3', 'B4', 'B8', 'B11', 'B12']

