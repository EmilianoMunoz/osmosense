# Reconstrucción del dataset desde IDEMendoza

> Estado: histórico/metodológico. La estructura actual del backend está en
> `backend/`; este documento conserva el razonamiento de reconstrucción de datos
> y no debe usarse como guía de comandos operativos sin revisar rutas.

## Objetivo

Reconstruir los datasets de clasificación partiendo desde
`data/parcelas/parcelas_ide.geojson`, para mejorar la calidad de las
features espectrales antes de avanzar con el predictor de estrés hídrico.

La hipótesis de trabajo es que parte del techo actual de performance no
está en el modelo, sino en:

- filtros de imágenes Sentinel-2,
- máscara de nubes/sombras,
- geometrías contaminadas por bordes,
- estadísticas demasiado simples,
- índices insuficientes para separar vid, olivo y frutales.

## Fuente base

Archivo original:

```text
data/parcelas/parcelas_ide.geojson
```

Características observadas:

- 216.721 parcelas.
- CRS original: EPSG:3857.
- Campo de cultivo original: `tipo_culti`.

Derivados existentes:

```text
data/parcelas/san_rafael_completo_wgs84.geojson
data/parcelas/san_rafael_vid_olivo_wgs84.geojson
data/parcelas/muestra_entrenamiento.geojson
```

Distribución en San Rafael:

```text
descarte: 45.210
vid:      15.447
frutales:  9.036
olivo:       711
```

## Decisión metodológica

Para el producto final, la clasificación no debe ser la única fuente de
verdad. Como se cuenta con etiquetas oficiales del gobierno, estas deben
usarse como base para definir qué parcelas entran al sistema de estrés
hídrico.

El modelo clasificador queda como:

- validador de consistencia,
- detector de posibles cambios de cultivo,
- filtro para parcelas nuevas o dudosas,
- herramienta para detectar reconversión de parcelas incultas u otros
  cultivos hacia vid/olivo.

## Mejoras aplicadas al pipeline base

### Máscara SCL más estricta

Se amplió `app/services/images.py` para remover también:

```text
0  = no data
1  = saturated / defective
3  = cloud shadow
8  = cloud medium probability
9  = cloud high probability
10 = cirrus
11 = snow / ice
```

Antes se removían solo 3, 8, 9 y 10.

### Nuevos índices espectrales

Se amplió `app/services/indices.py`.

Índices previos:

```text
NDVI
NDMI
NDWI
MSI
SAVI
NDRE
```

Índices agregados:

```text
GNDVI
EVI
BSI
NBR
MTCI
IRECI
```

Justificación:

- `GNDVI` y `EVI` pueden captar diferencias de vigor que NDVI no
  separa bien cuando se satura.
- `BSI` ayuda a detectar suelo desnudo o baja cobertura.
- `NBR` incorpora SWIR2 y puede aportar información de sequedad/biomasa.
- `MTCI` e `IRECI` explotan el red-edge, útil para diferencias de
  clorofila y estructura de dosel.

### Estadísticas por parcela más completas

La extracción por parcela ahora contempla:

```text
mean
stdDev
min
max
count
```

Antes muchas extracciones usaban principalmente `mean`.

`count` es especialmente importante para descartar muestras con muy
pocos píxeles válidos luego del enmascarado.

## Recomendaciones para el próximo dataset

1. Reproyectar desde `parcelas_ide.geojson` a EPSG:4326.
2. Filtrar San Rafael.
3. Normalizar etiquetas a:

   ```text
   vid
   olivo
   frutales
   descarte
   ```

4. Mantener `frutales` y `descarte` para entrenamiento/evaluación, pero
   no como clases finales del producto.
5. Filtrar parcelas pequeñas o usar buffer negativo para evitar bordes.
6. Extraer series mensuales 2023-2024 como mínimo.
7. Probar dos composiciones:

   - mediana mensual con máscara SCL estricta,
   - percentil temporal o quality mosaic por NDVI/NDMI para comparar.

8. Descartar observaciones con `count` bajo.
9. Generar features fenológicas por índice, no solo por NDVI.
10. Evaluar el resultado con foco operativo:

    ```text
    vid confiable
    olivo confiable
    no_objetivo / baja_confianza
    ```

## Nota sobre imágenes para predictor

Puede ser conveniente usar un dataset para clasificación y otro para
estrés hídrico.

Clasificación:

- prioriza separabilidad entre cultivos,
- puede usar ventanas fenológicas amplias,
- puede usar bandas/índices estructurales y red-edge.

Predictor hídrico:

- prioriza actualidad temporal,
- requiere series recientes,
- debe combinar NDMI/MSI/NDWI/NDVI con clima y turnos de riego,
- se ejecutará periódicamente en cloud.

Esta separación evita optimizar una sola representación para dos
objetivos distintos.
