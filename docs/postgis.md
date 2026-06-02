# PostGIS operativo

El objetivo de PostGIS es reemplazar el intercambio operativo por CSV/GeoJSON
cuando el sistema pase a backend/API/mapa.

## Tablas

El schema está en:

```text
backend/sql/schema_postgis.sql
```

Las tablas no se generan con backend/models/ORM. Se crean con SQL explícito e
idempotente:

```sql
CREATE TABLE IF NOT EXISTS ...
CREATE INDEX IF NOT EXISTS ...
CREATE OR REPLACE VIEW ...
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...
```

El script que aplica ese schema es:

```bash
venv/bin/python backend/scripts/postgis/aplicar_schema_postgis.py
```

El setup completo ejecuta ese schema y luego carga datos operativos:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py
```

Motivo de esta decisión: el proyecto todavía no necesita una capa ORM. El SQL
directo deja claro el contrato geoespacial, evita migraciones prematuras y
facilita replicar la estructura en UM-Cloud.

Define:

| Tabla / vista                | Uso                                                       |
|------------------------------|-----------------------------------------------------------|
| `parcelas`                   | Geometría oficial de parcelas, cultivo oficial y área.    |
| `observaciones_sentinel`     | Serie temporal de índices Sentinel-2 por parcela y fecha. |
| `ranking_hidrico`            | Resultado de cada corrida del modelo predictor.           |
| `ranking_hidrico_latest`     | Último ranking disponible.                                |
| `ranking_hidrico_latest_geo` | Último ranking unido con geometría para mapa.             |
| `clientes`                   | Clientes particulares o regionales.                       |
| `usuarios`                   | Login operativo y vínculo usuario-rol-cliente.            |
| `cliente_parcela`            | Relación cliente-parcela para vistas particulares.        |
| `zonas_um`                   | Geometría de unidades de manejo regionales.               |
| `parcela_um`                 | Relación espacial parcela-UM.                             |
| `ranking_um`                 | Ranking agregado regional por UM.                         |

### Parcelas manuales

`parcelas` incluye:

```text
cultivo_original
fuente
activo
```

Las parcelas oficiales cargadas desde IDEMendoza usan `fuente='idemendoza'`.
Las parcelas agregadas por API admin pueden usar `fuente='manual'`.
Si una parcela oficial no era vid/olivo y el admin la activa para análisis, se
mantiene `cultivo_original` con la etiqueta del gobierno y se actualiza
`cultivo_oficial` a `vid` u `olivo`.

La baja operativa de una parcela se modela con `activo=false`, no con borrado
físico, para preservar históricos y relaciones. Las vistas operativas filtran
parcelas activas.

Si se agrega una parcela nueva en PostGIS y se activa como `vid` u `olivo`,
puede entrar a la próxima extracción Sentinel cuando el pipeline se ejecuta con
`--parcel-source postgis`.

El extractor temporal ya soporta esa fuente con:

```bash
venv/bin/python backend/scripts/pipeline/generar_dataset_temporal_hidrico.py --all-target-parcels --parcel-source postgis --start-date 2026-05-21 --end-date 2026-05-26
```

Desde el orquestador operativo:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --load-postgis
```

Cargar solo vid/olivo:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py
```

Cargar todas las parcelas oficiales para habilitar mapa de disponibles:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
```

## Configuración

Para desarrollo local se agregó:

```text
docker-compose.postgis.yml
.env.postgis.example
```

Imagen usada:

```text
postgis/postgis:17-3.6-alpine
```

Motivo:

- usa PostgreSQL 17 con PostGIS 3.6;
- evita `latest` para que el entorno no cambie solo;
- es compatible con el schema actual.

Levantar PostGIS local:

```bash
docker compose -f docker-compose.postgis.yml up -d
```

URL local por defecto:

```text
DATABASE_URL=postgresql://estres:estres_dev@127.0.0.1:5433/estres
```

Copiar a `.env` o exportar:

```text
cp .env.postgis.example .env
```

La base debe tener PostGIS disponible. El schema ejecuta:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

## Comandos

Aplicar schema y cargar todo el estado operativo local:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py
```

Esto ejecuta:

```text
backend/scripts/postgis/aplicar_schema_postgis.py
backend/scripts/postgis/cargar_parcelas_postgis.py
backend/scripts/postgis/cargar_ranking_postgis.py
backend/scripts/postgis/cargar_clientes_parcelas_postgis.py
backend/scripts/postgis/cargar_zonificacion_um_postgis.py
backend/scripts/postgis/cargar_usuarios_demo_postgis.py
```

Validar conteos:

```bash
venv/bin/python backend/scripts/postgis/validar_postgis_local.py
```

Validar flujo operativo con smoke test:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --skip-api --check-postgis
```

Con la API levantada y `DATABASE_URL` configurado:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis
```

Comandos individuales:

```bash
venv/bin/python backend/scripts/postgis/aplicar_schema_postgis.py
venv/bin/python backend/scripts/postgis/cargar_parcelas_postgis.py
venv/bin/python backend/scripts/postgis/cargar_ranking_postgis.py
venv/bin/python backend/scripts/postgis/cargar_clientes_parcelas_postgis.py
venv/bin/python backend/scripts/postgis/cargar_zonificacion_um_postgis.py
venv/bin/python backend/scripts/postgis/cargar_usuarios_demo_postgis.py
```

## Autenticación

La tabla `usuarios` guarda el login del dashboard. Los passwords se almacenan
como hash PBKDF2-SHA256, no en texto plano.

Roles soportados:

| Rol                   | Vista dashboard | Requiere cliente |
|-----------------------|-----------------|------------------|
| `admin`               | Admin           | No               |
| `cliente_particular`  | Cliente         | Sí               |
| `cliente_regional`    | Regional        | No               |

Cargar o actualizar usuarios demo:

```bash
venv/bin/python backend/scripts/postgis/cargar_usuarios_demo_postgis.py
```

Usuarios cargados:

| Login      | Contraseña    | Rol                  |
|------------|---------------|----------------------|
| `admin`    | `admin123`    | `admin`              |
| `finca`    | `cliente123`  | `cliente_particular` |
| `olivar`   | `cliente123`  | `cliente_particular` |
| `regional` | `regional123` | `cliente_regional`   |

El endpoint de login es:

```http
POST /auth/login
```

El login devuelve un token `Bearer` firmado. Las rutas operativas quedan
protegidas por rol:

| Rutas                         | Roles permitidos                         |
|-------------------------------|------------------------------------------|
| `/admin/*`                    | `admin`                                  |
| `/rankings/latest*`           | `admin`                                  |
| `/rankings/{fecha}`           | `admin`                                  |
| `/clientes`                   | `admin`                                  |
| `/clientes/{id}/rankings/*`   | `admin` o cliente particular propietario |
| `/regional/*`                 | `admin` o `cliente_regional`             |

El dashboard Streamlit guarda el token en sesión y lo envía como:

```http
Authorization: Bearer <access_token>
```

Cargar ranking automáticamente desde el orquestador:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --skip-if-no-new-date --load-postgis
```

Pruebas sin conectarse a la DB:

```bash
venv/bin/python backend/scripts/postgis/aplicar_schema_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_parcelas_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_ranking_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_clientes_parcelas_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/cargar_zonificacion_um_postgis.py --dry-run
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --dry-run
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local --load-postgis --dry-run
```

## Supuesto de identificador

El GeoJSON `backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson` usa `fid`.
Los rankings usan `parcela_id`.

Para esta etapa se asume:

```text
parcela_id = fid
```

El script `cargar_parcelas_postgis.py` permite cambiarlo con:

```bash
--id-column otra_columna
```

## Vista para el mapa

La vista principal para el mapa es:

```sql
SELECT *
FROM ranking_hidrico_latest_geo;
```

Contiene ranking, prioridad, predicciones y geometría `geom`.
## Zonificación Regional UM

El schema contempla la vista regional con tres tablas:

```text
zonas_um
parcela_um
ranking_um
```

Vistas:

```text
ranking_um_latest
ranking_um_latest_geo
```

Carga:

```bash
venv/bin/python backend/scripts/postgis/cargar_zonificacion_um_postgis.py
```

Entradas locales:

```text
backend/data/zonificacion/um_con_cultivos.geojson
backend/data/zonificacion/parcelas_um.csv
backend/data/zonificacion/ranking_um_latest.csv
```

El pipeline puede regenerar estos archivos después de cada ranking con
`--update-zonificacion-um` y cargarlos junto con el ranking cuando se usa
`--load-postgis`.
