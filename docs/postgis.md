# PostGIS operativo

El objetivo de PostGIS es ser la fuente geoespacial operativa del sistema.
Reemplaza el intercambio principal por CSV/GeoJSON cuando `DATABASE_URL` está
configurado. Los archivos locales quedan como respaldo y fallback de desarrollo.
En producción (`APP_ENV=production`) `DATABASE_URL` es obligatorio y el fallback
CSV/GeoJSON queda deshabilitado.

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
| `ranking_hidrico_cobertura_fechas` | Cobertura de parcelas rankeadas por fecha.         |
| `ranking_hidrico_latest_date` | Última fecha con cobertura suficiente para uso operativo. |
| `ranking_hidrico_latest`     | Ranking operativo latest, filtrado por cobertura mínima.  |
| `ranking_hidrico_latest_geo` | Último ranking unido con geometría para mapa.             |
| `clientes`                   | Perfil interno productor/cartera de parcelas. Conserva nombre legacy. |
| `usuarios`                   | Login operativo y rol del usuario.                        |
| `cliente_parcela`            | Relación interna productor-parcela. Conserva nombre legacy. |
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
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --update-recent-window --parcel-source postgis --load-postgis
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

Variables mínimas de producción:

```text
APP_ENV=production
DATABASE_URL=postgresql://usuario:password@host:5432/estres
AUTH_SECRET=<secreto-fuerte>
ENABLE_LOCAL_FALLBACK=false
ENABLE_QUICK_LOGIN=false
```

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

El compose publica PostGIS por defecto solo en `127.0.0.1:5433`.

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

| Rol                   | Vista dashboard | Requiere parcelas asignadas |
|-----------------------|-----------------|------------------|
| `admin`               | Admin           | No               |
| `productor`           | Productor       | Sí               |
| `regional`            | Regional        | No               |

Cargar usuarios operativos de desarrollo. El script elimina los usuarios
existentes y recrea los accesos base; no modifica los productores internos
(`clientes`) ni `cliente_parcela`, por lo que conserva las parcelas asignadas a
cada productor:

```bash
venv/bin/python backend/scripts/postgis/cargar_usuarios_demo_postgis.py
```

Usuarios cargados:

| Email | Contraseña | Rol |
|---|---|---|
| `admin@osmosense.local` | `admin123` | `admin` |
| `productor.vid@osmosense.local` | `cliente123` | `productor` |
| `productor.olivo@osmosense.local` | `cliente123` | `productor` |
| `regional@osmosense.local` | `regional123` | `regional` |

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
| `/clientes/{id}/rankings/*`   | `admin` o productor propietario          |
| `/regional/*`                 | `admin` o `regional`                     |

Nota: las rutas `/clientes/*` son compatibilidad interna. En la experiencia de
producto se muestran como productores y parcelas asignadas. `cliente_id` es hoy
el identificador interno de la cartera de parcelas del productor.

El dashboard Streamlit guarda el token en sesión y lo envía como:

```http
Authorization: Bearer <access_token>
```

Cargar ranking automáticamente desde el orquestador:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --update-recent-window --parcel-source postgis --skip-if-no-new-date --load-postgis
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

La selección de `latest` no usa solamente `max(fecha_ranking)`. Para evitar que
una imagen Sentinel parcial reemplace una corrida completa, el schema calcula
primero la cobertura por fecha en `ranking_hidrico_cobertura_fechas`.

Criterio operativo:

```text
parcelas objetivo = parcelas activas vid/olivo con area_m2 >= 4000
fecha latest válida = fecha más reciente con al menos 80% de cobertura
```

Esto permite conservar rankings parciales en `ranking_hidrico` para auditoría,
pero evita que alimenten el dashboard como fecha operativa principal.
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
