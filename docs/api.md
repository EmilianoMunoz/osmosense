# API de ranking hídrico

La API expone el ranking hídrico para que lo consuma el dashboard o mapa.

## Ejecutar local

```bash
venv/bin/uvicorn backend.app.main:app --reload
```

URL local:

```text
http://127.0.0.1:8000
```

## Fuente de datos

La API usa fuente dual en desarrollo:

1. Si existe `DATABASE_URL`, lee desde PostGIS.
2. Si no existe `DATABASE_URL`, usa archivos locales:

```text
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

Esto permite desarrollar localmente sin base de datos y pasar a PostGIS en
cloud sin cambiar endpoints.

En producción (`APP_ENV=production`) `DATABASE_URL` es obligatorio. Si no está
configurado, la API responde error y no usa CSV/GeoJSON local. Esta restricción
evita que el sistema productivo muestre datos viejos o artefactos de respaldo
sin advertencia.

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

### Login

```http
POST /auth/login
```

Body:

```json
{"email": "admin@osmosense.local", "password": "admin123"}
```

Valida contra la tabla `usuarios` de PostGIS y devuelve el rol operativo para
abrir la vista correspondiente del dashboard. También devuelve un token firmado
que debe enviarse en las rutas protegidas.

Roles operativos actuales:

- `admin`: administración completa.
- `regional`: vista agregada por UM/zona.
- `productor`: parcelas asociadas al usuario productor.

Respuesta:

```json
{
  "source": "postgis",
  "token_type": "bearer",
  "access_token": "...",
  "user": {
    "usuario_id": 1,
    "email": "admin@osmosense.local",
    "nombre": "Administrador",
    "apellido": null,
    "dni": null,
    "rol": "admin",
    "cliente_id": null,
    "view_mode": "Admin"
  }
}
```

Uso del token:

```http
Authorization: Bearer <access_token>
```

El token expira por defecto a las 8 horas. En desarrollo puede configurarse con:

```text
AUTH_SECRET=...
AUTH_TOKEN_TTL_SECONDS=28800
```

Estados:

```text
401 credenciales inválidas
503 DATABASE_URL no configurado o PostGIS no disponible
```

### Último ranking

```http
GET /rankings/latest
GET /rankings/latest?limit=100
```

Devuelve filas del último ranking, ordenadas por `ranking_global`.

Requiere rol `admin`.

### Último ranking como GeoJSON

```http
GET /rankings/latest/geojson
GET /rankings/latest/geojson?simplify_meters=2
```

Devuelve un `FeatureCollection` con geometría de todas las parcelas oficiales
vid/olivo y propiedades del ranking cuando existen. Este endpoint es el
principal para el mapa interactivo.

Requiere rol `admin`.

`simplify_meters` es opcional. Cuando hay PostGIS, simplifica la geometría solo
para visualización con `ST_SimplifyPreserveTopology` antes de serializar el
GeoJSON. No modifica la geometría persistida ni el ranking.

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

### Estado del pipeline

```http
GET /pipeline/state
```

Devuelve el estado persistido de la última corrida y, cuando PostGIS está
configurado, un bloque `ranking_coverage` calculado desde
`ranking_hidrico_cobertura_fechas`.

Ese bloque permite que el dashboard distinga:

```text
Ranking operativo usado
Última corrida disponible
Cobertura de la última corrida
Motivo por el cual una fecha reciente no reemplazó el latest operativo
```

Requiere rol `admin`.

### Ranking por fecha

```http
GET /rankings/2024-12-31
GET /rankings/2024-12-31?limit=100
```

Con fallback CSV solo devuelve datos si la fecha coincide con el archivo
`backend/data/rankings/ranking_hidrico_<fecha>.csv`. Con PostGIS puede consultar
cualquier fecha cargada en `ranking_hidrico`.

### Productores internos (`/clientes`)

```http
GET /clientes
```

Devuelve productores/carteras activos con la cantidad de parcelas asignadas.
El nombre `/clientes` se mantiene por compatibilidad interna con el schema
actual, pero en la interfaz y en la tesis debe describirse como productores y
parcelas asignadas.

En fallback local lee:

```text
backend/data/clientes/clientes.csv
backend/data/clientes/cliente_parcela.csv
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

### Sesión actual (`/me`)

```http
GET /me
GET /me/rankings/latest/geojson
GET /me/parcelas
```

`GET /me` devuelve la identidad contenida en el token activo. No consulta datos
de otro usuario ni requiere pasar IDs internos desde el frontend.

`GET /me/rankings/latest/geojson` es la ruta operativa para la vista
`productor`. El backend obtiene el `cliente_id` desde el token, valida que el
rol sea `productor` y devuelve solo las parcelas asociadas a ese productor.

`GET /me/parcelas` devuelve el listado tabular de parcelas asignadas al
productor autenticado, tambien derivado del token.

### Ranking latest por productor

```http
GET /clientes/1/rankings/latest/geojson
```

Devuelve solo las parcelas asociadas al productor propietario de ese perfil
interno. El filtrado se hace en backend, no en el dashboard. En PostGIS usa
`cliente_parcela` como compatibilidad técnica; en fallback local usa los CSV de
`backend/data/clientes`.

Este endpoint queda como compatibilidad interna y para uso admin/debug. Para la
vista Productor se prefiere `/me/rankings/latest/geojson`.

Este endpoint conserva parcelas asociadas aunque no tengan ranking latest,
marcándolas como `sin_ranking_latest`.

## Admin usuarios

Requiere rol `admin`.

```http
GET /admin/usuarios
GET /admin/usuarios?limit=100&activo=true
```

Devuelve usuarios sin `password_hash`.

```http
POST /admin/usuarios
```

Payload:

```json
{
  "email": "productor.vid@osmosense.local",
  "nombre": "Martín",
  "apellido": "Videla",
  "dni": "30111222",
  "rol": "productor",
  "cliente_id": null,
  "password": "cliente123",
  "activo": true
}
```

Para usuarios con rol `productor`, `apellido` y `dni` son obligatorios. El DNI
se normaliza sin puntos ni guiones y debe contener entre 7 y 9 dígitos.

```http
PUT /admin/usuarios/1
```

Permite actualizar `email`, `nombre`, `rol`, `cliente_id`, `activo` y resetear
contraseña con `password`.

```http
DELETE /admin/usuarios/1
```

Desactiva el acceso del usuario (`activo=false`) sin borrar el registro físico.
Se usa baja lógica para conservar trazabilidad.

El backend impide desactivar o cambiar de rol al último admin activo.

## Admin productores internos

Estos endpoints son de administración operativa y requieren PostGIS
(`DATABASE_URL`). No tienen fallback CSV porque modifican estado persistente.
Requieren rol `admin`. El nombre técnico conserva `/admin/clientes`, pero el
dashboard los presenta como productores y parcelas.

## Admin parcelas

Estos endpoints permiten administrar el universo operativo de parcelas en
PostGIS. Sirven para casos como: una parcela actualmente frutal que el productor
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

### Evaluación posterior de parcelas nuevas

El CRUD deja la parcela disponible en PostGIS. Para que entre a la próxima
extracción Sentinel, el pipeline debe ejecutarse usando parcelas objetivo desde
PostGIS:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --update-recent-window --parcel-source postgis --load-postgis
```

### Listar productores internos

```http
GET /admin/clientes
GET /admin/clientes?limit=100
```

Devuelve productores/carteras activos e inactivos con cantidad de parcelas
asignadas.

### Crear productor interno

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

También se puede enviar `cliente_id` para cargas controladas, aunque en
producción debería dejarse autogenerado.

### Actualizar productor interno

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

### Ver parcelas de productor

```http
GET /admin/clientes/1/parcelas
```

Devuelve las parcelas asociadas con datos básicos de cultivo, área y ranking
latest cuando existe.

### Asociar parcela a productor

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

### Quitar parcela de productor

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
`riesgo_operativo_*` son la proyección conservadora usada por la vista productor.

## Regional

### Último ranking por UM

```http
GET /regional/um/latest
GET /regional/um/latest?limit=10
```

Devuelve el ranking regional agregado por UM, ordenado por `ranking_um`.
Requiere rol `admin` o `regional`.

### Último ranking por UM como GeoJSON

```http
GET /regional/um/latest/geojson
```

Devuelve un `FeatureCollection` con geometría de las UM que tienen cultivos
oficiales vid/olivo y propiedades agregadas:
Requiere rol `admin` o `regional`.

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
Requiere rol `admin` o `regional`.

Fallback local:

```text
backend/data/zonificacion/um_con_cultivos.geojson
backend/data/zonificacion/ranking_um_latest.csv
backend/data/zonificacion/parcelas_um.csv
```
