# PostGIS operativo

El objetivo de PostGIS es reemplazar el intercambio operativo por CSV/GeoJSON
cuando el sistema pase a backend/API/mapa.

## Tablas

El schema está en:

```text
sql/schema_postgis.sql
```

Define:

| Tabla / vista | Uso |
|---|---|
| `parcelas` | Geometría oficial de parcelas, cultivo oficial y área. |
| `observaciones_sentinel` | Serie temporal de índices Sentinel-2 por parcela y fecha. |
| `ranking_hidrico` | Resultado de cada corrida del modelo predictor. |
| `ranking_hidrico_latest` | Último ranking disponible. |
| `ranking_hidrico_latest_geo` | Último ranking unido con geometría para mapa. |

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
venv/bin/python scripts/setup_postgis_local.py
```

Esto ejecuta:

```text
scripts/aplicar_schema_postgis.py
scripts/cargar_parcelas_postgis.py
scripts/cargar_ranking_postgis.py
scripts/cargar_clientes_parcelas_postgis.py
scripts/cargar_zonificacion_um_postgis.py
```

Validar conteos:

```bash
venv/bin/python scripts/validar_postgis_local.py
```

Comandos individuales:

```bash
venv/bin/python scripts/aplicar_schema_postgis.py
venv/bin/python scripts/cargar_parcelas_postgis.py
venv/bin/python scripts/cargar_ranking_postgis.py
venv/bin/python scripts/cargar_clientes_parcelas_postgis.py
venv/bin/python scripts/cargar_zonificacion_um_postgis.py
```

Cargar ranking automáticamente desde el orquestador:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py --mode cloud --update-sentinel --skip-if-no-new-date --load-postgis
```

Pruebas sin conectarse a la DB:

```bash
venv/bin/python scripts/aplicar_schema_postgis.py --dry-run
venv/bin/python scripts/cargar_parcelas_postgis.py --dry-run
venv/bin/python scripts/cargar_ranking_postgis.py --dry-run
venv/bin/python scripts/cargar_clientes_parcelas_postgis.py --dry-run
venv/bin/python scripts/cargar_zonificacion_um_postgis.py --dry-run
venv/bin/python scripts/setup_postgis_local.py --dry-run
venv/bin/python scripts/run_pipeline_hidrico.py --mode local --load-postgis --dry-run
```

## Supuesto de identificador

El GeoJSON `data/parcelas/san_rafael_vid_olivo_wgs84.geojson` usa `fid`.
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
venv/bin/python scripts/cargar_zonificacion_um_postgis.py
```

Entradas locales:

```text
data/zonificacion/um_con_cultivos.geojson
data/zonificacion/parcelas_um.csv
data/zonificacion/ranking_um_latest.csv
```

El pipeline puede regenerar estos archivos después de cada ranking con
`--update-zonificacion-um` y cargarlos junto con el ranking cuando se usa
`--load-postgis`.
