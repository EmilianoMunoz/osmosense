# Límite departamental de San Rafael

El proyecto ya no depende de FAO/GAUL para obtener la geometría de San Rafael.

La fuente preferida es un GeoJSON local:

```text
backend/data/limites/san_rafael.geojson
```

Si ese archivo existe, el código lo usa para:

- filtrar parcelas oficiales;
- construir la región de consulta en Google Earth Engine;
- evitar depender de límites externos que pueden no coincidir exactamente.

Si el archivo no existe, el sistema mantiene el fallback actual por bounding box:

```text
(-69.61384291, -35.52309910, -67.41312966, -34.47910163)
```

Archivos relevantes:

```text
app/core/region.py
app/services/images.py
scripts/recalcular_dataset_desde_ide.py
scripts/generar_dataset_temporal_hidrico.py
```

## Formato esperado

El GeoJSON debe estar en EPSG:4326 o tener CRS detectable para reproyectarlo.
Puede ser `Polygon` o `MultiPolygon`.

Ejemplo mínimo:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {"nombre": "San Rafael"},
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-68.0, -34.8],
            [-68.1, -34.9],
            [-68.2, -34.8],
            [-68.0, -34.8]
          ]
        ]
      }
    }
  ]
}
```

Ese ejemplo es ilustrativo, no debe usarse como límite real.
