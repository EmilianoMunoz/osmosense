# API de ranking hídrico

La API expone el ranking hídrico para que lo consuma el dashboard o mapa.

## Ejecutar local

```bash
venv/bin/uvicorn app.main:app --reload
```

URL local:

```text
http://127.0.0.1:8000
```

## Fuente de datos

La API usa fuente dual:

1. Si existe `DATABASE_URL`, lee desde PostGIS.
2. Si no existe `DATABASE_URL`, usa archivos locales:

```text
data/rankings/ranking_hidrico_latest.csv
data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

Esto permite desarrollar localmente sin base de datos y pasar a PostGIS en
cloud sin cambiar endpoints.

Si `DATABASE_URL` está definido, la API intenta leer desde PostGIS. Si PostGIS
falla, el error se reporta explícitamente; no se hace fallback silencioso a CSV
para evitar mezclar fuentes sin advertencia.

## Validaciones del fallback local

Cuando usa archivos locales, la API valida que el ranking tenga las columnas
mínimas:

```text
fecha_actual
parcela_id
cultivo
ranking_global
ranking_por_cultivo
prioridad
prioridad_score
riesgo_actual
riesgo_pred_5d
riesgo_pred_10d
delta_5d
delta_10d
```

En rankings nuevos también se exponen:

```text
fecha_lectura
dias_desde_lectura
riesgo_operativo_5d
riesgo_operativo_10d
delta_operativo_5d
delta_operativo_10d
tendencia_reciente_5d
pendiente_operativa_5d
factor_estacional
```

También valida que el GeoJSON de parcelas tenga la columna `fid`, usada como
identificador de parcela. Internamente se renombra a `parcela_id` para hacer el
merge con el ranking.

Si el merge entre ranking y parcelas no produce features, la API devuelve un
error explícito para detectar rápido problemas de IDs o artefactos desfasados.

## Endpoints

### Health

```http
GET /health
```

Respuesta:

```json
{"status": "ok"}
```

### Último ranking

```http
GET /rankings/latest
GET /rankings/latest?limit=100
```

Devuelve filas del último ranking, ordenadas por `ranking_global`.

### Último ranking como GeoJSON

```http
GET /rankings/latest/geojson
```

Devuelve un `FeatureCollection` con geometría de todas las parcelas oficiales
vid/olivo y propiedades del ranking cuando existen. Este endpoint es el
principal para el mapa interactivo.

Las parcelas con ranking latest tienen:

```text
estado_cobertura = rankeada
prioridad = critica | alta | media | baja
```

Las parcelas sin ranking latest se devuelven igualmente para visualización, con:

```text
estado_cobertura = sin_ranking_latest
prioridad = sin ranking
```

Esto permite que el dashboard muestre todo el universo oficial vid/olivo y no
solo las parcelas evaluadas.

### Ranking por fecha

```http
GET /rankings/2024-12-31
GET /rankings/2024-12-31?limit=100
```

Con fallback CSV solo devuelve datos si la fecha coincide con el archivo
`data/rankings/ranking_hidrico_<fecha>.csv`. Con PostGIS puede consultar
cualquier fecha cargada en `ranking_hidrico`.

### Clientes

```http
GET /clientes
```

Devuelve clientes activos con la cantidad de parcelas asignadas.

En fallback local lee:

```text
data/clientes/clientes.csv
data/clientes/cliente_parcela.csv
```

Formato mínimo:

```csv
cliente_id,nombre,tipo,descripcion,activo
1,Finca Demo,particular,Cliente de prueba,true
```

```csv
cliente_id,parcela_id,etiqueta
1,38695,Lote norte
```

### Ranking latest por cliente

```http
GET /clientes/1/rankings/latest/geojson
```

Devuelve solo las parcelas asociadas al cliente. El filtrado se hace en backend,
no en el dashboard. En PostGIS usa `cliente_parcela`; en fallback local usa los
CSV de `data/clientes`.

Este endpoint conserva parcelas asociadas aunque no tengan ranking latest,
marcándolas como `sin_ranking_latest`.

## Admin clientes

Estos endpoints son de administración operativa y requieren PostGIS
(`DATABASE_URL`). No tienen fallback CSV porque modifican estado persistente.
La autenticación real queda pendiente para producción; por ahora son endpoints
internos para preparar el CRUD del dashboard admin.

## Admin parcelas

Estos endpoints permiten administrar el universo operativo de parcelas en
PostGIS. Sirven para casos como: una parcela actualmente frutal que el cliente
informa que pasará a vid y se quiere incorporar al análisis futuro.

La baja es lógica: `DELETE /admin/parcelas/{id}` marca `activo=false`. No borra
históricos ni rankings previos.

### Listar parcelas

```http
GET /admin/parcelas
GET /admin/parcelas?limit=100
GET /admin/parcelas?cultivo=vid&activo=true
```

Devuelve parcelas con datos básicos y ranking latest si existe.

### Listar parcelas disponibles

```http
GET /admin/parcelas/disponibles
GET /admin/parcelas/disponibles?limit=100
```

Devuelve parcelas activas cuyo `cultivo_oficial` todavía no es `vid` ni
`olivo`. Son candidatas para el mapa admin de disponibles.

### Activar parcela disponible como vid/olivo

```http
POST /admin/parcelas/12345/activar-disponible
```

Body:

```json
{
  "cultivo_oficial": "vid",
  "cliente_id": 1,
  "etiqueta": "Nuevo cuadro vid"
}
```

`cliente_id` y `etiqueta` son opcionales. Si se envía `cliente_id`, además de
cambiar la etiqueta operativa de la parcela se crea o actualiza la relación
`cliente_parcela`.

### Ver parcela con geometría

```http
GET /admin/parcelas/38695
```

Devuelve la parcela con `geometry` GeoJSON.

### Crear parcela

```http
POST /admin/parcelas
```

Body:

```json
{
  "parcela_id": 900001,
  "cultivo_oficial": "vid",
  "fuente": "manual",
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [-68.40, -34.70],
        [-68.39, -34.70],
        [-68.39, -34.69],
        [-68.40, -34.69],
        [-68.40, -34.70]
      ]
    ]
  }
}
```

Si `area_m2` no se envía, PostGIS la calcula con `ST_Area(...::geography)`.

Para una parcela que hoy figura como frutal pero pasará a vid, debe cargarse con:

```json
{"cultivo_oficial": "vid"}
```

porque ese es el cultivo objetivo que se quiere evaluar.

### Actualizar parcela

```http
PUT /admin/parcelas/900001
```

Body parcial:

```json
{
  "cultivo_oficial": "olivo",
  "activo": true
}
```

También puede actualizarse `geometry`; si no se envía `area_m2`, se recalcula.

### Desactivar parcela

```http
DELETE /admin/parcelas/900001
```

Marca la parcela como inactiva.

### Limitación actual

El CRUD deja la parcela disponible en PostGIS. Para que una parcela nueva sea
evaluada automáticamente con la próxima imagen Sentinel, el siguiente ajuste
necesario es permitir que `generar_dataset_temporal_hidrico.py` tome parcelas
objetivo desde PostGIS además del GeoJSON local.

### Listar clientes

```http
GET /admin/clientes
GET /admin/clientes?limit=100
```

Devuelve clientes activos e inactivos con cantidad de parcelas asignadas.

### Crear cliente

```http
POST /admin/clientes
```

Body:

```json
{
  "nombre": "Finca Demo",
  "tipo": "particular",
  "descripcion": "Cliente de prueba",
  "activo": true
}
```

`tipo` acepta:

```text
particular
regional
```

También se puede enviar `cliente_id` para cargas controladas de demo, aunque en
producción debería dejarse autogenerado.

### Actualizar cliente

```http
PUT /admin/clientes/1
```

Body parcial:

```json
{
  "nombre": "Finca Demo Actualizada",
  "activo": true
}
```

### Ver parcelas de cliente

```http
GET /admin/clientes/1/parcelas
```

Devuelve las parcelas asociadas con datos básicos de cultivo, área y ranking
latest cuando existe.

### Asociar parcela a cliente

```http
POST /admin/clientes/1/parcelas
```

Body:

```json
{
  "parcela_id": 38695,
  "etiqueta": "Lote norte"
}
```

Si la relación ya existe, actualiza `etiqueta`.

### Quitar parcela de cliente

```http
DELETE /admin/clientes/1/parcelas/38695
```

## Endpoints previstos para el mapa

El dashboard Streamlit puede consumir directamente:

```text
/rankings/latest/geojson
/clientes/{cliente_id}/rankings/latest/geojson
/regional/um/latest/geojson
/regional/um/{um_id}/parcelas/latest/geojson
```

Campos principales en `properties`:

```text
parcela_id
cultivo
prioridad
prioridad_score
ranking_global
ranking_por_cultivo
riesgo_actual
riesgo_pred_5d
riesgo_pred_10d
riesgo_operativo_5d
riesgo_operativo_10d
delta_5d
delta_10d
delta_operativo_5d
delta_operativo_10d
tendencia_reciente_5d
pendiente_operativa_5d
factor_estacional
ndmi_mean
msi_mean
ndwi_mean
nbr_mean
ndvi_mean
```

`riesgo_pred_*` son predicciones históricas crudas del modelo ML. Las columnas
`riesgo_operativo_*` son la proyección conservadora usada por la vista cliente.

## Regional

### Último ranking por UM

```http
GET /regional/um/latest
GET /regional/um/latest?limit=10
```

Devuelve el ranking regional agregado por UM, ordenado por `ranking_um`.

### Último ranking por UM como GeoJSON

```http
GET /regional/um/latest/geojson
```

Devuelve un `FeatureCollection` con geometría de las UM que tienen cultivos
oficiales vid/olivo y propiedades agregadas:

```text
um_id
ranking_um
prioridad_regional
parcelas_total
parcelas_rankeadas
pct_parcelas_rankeadas
area_cultivada_ha
vid_parcelas
olivo_parcelas
prioridad_score_prom_pond
riesgo_actual_prom_pond
riesgo_10d_prom_pond
delta_10d_prom_pond
pct_alta_critica
pct_critica
```

### Parcelas de una UM

```http
GET /regional/um/0/parcelas/latest/geojson
```

Devuelve las parcelas oficiales asociadas a una UM, con la misma estructura de
propiedades que `/rankings/latest/geojson`. Este endpoint alimenta el drill-down
regional del dashboard.

Fallback local:

```text
data/zonificacion/um_con_cultivos.geojson
data/zonificacion/ranking_um_latest.csv
data/zonificacion/parcelas_um.csv
```
