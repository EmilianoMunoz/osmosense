# Arquitectura cloud del pipeline hídrico

Este documento define cómo debe desplegarse el sistema en UM-Cloud. No
reemplaza la guía de acceso `docs/UM_Cloud_Setup_Guide.md`; la complementa con
la arquitectura propia del proyecto. Los comandos concretos de instalacion en
la VM estan en `docs/despliegue_um_cloud.md`.

## Objetivo operativo

El sistema debe ejecutar periódicamente el pipeline de monitoreo hídrico
para parcelas de vid y olivo de San Rafael, Mendoza. Cada ejecución debe:

1. consultar nuevas observaciones Sentinel-2 válidas mediante Google Earth
   Engine;
2. actualizar el dataset temporal;
3. generar el ranking hídrico con modelos de regresión a 5 y 10 días;
4. cargar resultados en PostGIS;
5. publicar el ranking latest por API;
6. dejar logs y estado auditable de la ejecución.

## División de responsabilidades

### Google Earth Engine

GEE sigue siendo el motor de procesamiento satelital. Allí se filtran las
imágenes Sentinel-2, se aplican máscaras de calidad y se calculan los índices
por parcela. Esto evita descargar imágenes crudas completas en la VM.

### UM-Cloud

UM-Cloud aloja la aplicación operativa:

- repositorio del proyecto;
- entorno Python y dependencias;
- credenciales/configuración de GEE;
- datasets tabulares derivados;
- modelos entrenados;
- PostGIS operativo;
- orquestador programado;
- rankings generados;
- API FastAPI para servir rankings al dashboard/mapa;
- dashboard Streamlit para visualización operativa.

La VM no necesita procesar rasters pesados si GEE mantiene el procesamiento
server-side.

## Componentes iniciales en la VM

Una primera versión puede correr en una única VM Ubuntu de UM-Cloud:

- `git` para obtener el proyecto;
- Python 3.10+ y `venv`;
- archivo `.env` con `GEE_PROJECT_ID`;
- autenticación Earth Engine configurada para el usuario de ejecución;
- PostGIS configurado;
- modelos en `backend/models/hidrico_regresion/`;
- datasets base en `backend/data/`;
- ejecución programada con `systemd timer` o `cron`.

El comando operativo previsto es:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Para pruebas sin consultar GEE:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud
```

## Entradas esperadas

| Entrada              | Ubicación prevista| Nota                                               |
|----------------------|-------------------|----------------------------------------------------|
| Parcelas base        | `backend/data/parcelas/`  | Geometrías/etiquetas oficiales o muestra operativa.|
| Dataset temporal     | `backend/data/dataset_temporal_hidrico.csv` | Regenerable; no debe versionarse en Git. |
| Modelos de regresión | `backend/models/hidrico_regresion/*.pkl` | Artefactos pesados; idealmente subir por release/artifact, no Git normal. |
| Base PostGIS         | `DATABASE_URL` | Fuente operativa geoespacial. |
| Configuración GEE    | `.env` + credenciales EE | No versionar secretos. |

## Salidas operativas

El orquestador genera:

```text
backend/data/rankings/ranking_hidrico_YYYY-MM-DD.csv
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/state/pipeline_hidrico_state.json
backend/data/logs/pipeline_hidrico_YYYYMMDD_HHMMSS.log
```

Estas salidas son artefactos de ejecución y quedan ignoradas por Git. En cloud
deben conservarse en disco como respaldo, pero la publicación operativa se hace
desde PostGIS.

## Publicación del ranking

El flujo vigente publica rankings desde PostGIS cuando `DATABASE_URL` está
configurado. Los CSV/GeoJSON locales quedan como respaldo y fallback de
desarrollo. En producción (`APP_ENV=production`) `DATABASE_URL` es obligatorio
y el fallback local queda deshabilitado.

Endpoints FastAPI principales:

- `GET /rankings/latest`
- `GET /rankings/latest/geojson`
- `GET /rankings/{fecha}`
- `GET /health`
- `GET /me/rankings/latest/geojson`
- `GET /clientes/{cliente_id}/rankings/latest/geojson`
- `GET /regional/um/latest/geojson`

El dashboard Streamlit consume esos endpoints con token bearer y permisos por
rol.

## Programación automática

Sentinel-2 tiene revisita aproximada de 5 días, pero no toda imagen es válida
por nubes, máscara SCL o baja cantidad de píxeles útiles. Por eso conviene
ejecutar el pipeline más seguido que cada 5 días, por ejemplo diariamente o cada
48 horas, y que el sistema rankee solo cuando haya una nueva fecha válida.

Configuración recomendada inicial:

- ejecución diaria de madrugada;
- logs por ejecución;
- estado persistido en `backend/data/state/pipeline_hidrico_state.json`;
- alerta manual si el comando falla.

El flag `--skip-if-no-new-date` evita reescribir rankings cuando GEE no agregó
una observación Sentinel-2 nueva y válida al dataset temporal.

## Red y acceso en UM-Cloud

Según `docs/UM_Cloud_Setup_Guide.md`, la VM estará en `net_umstack`
(`10.201.0.0/16`) y se accede por ZeroTier. Las floating IP de `ext_net` son
privadas (`192.168.3.x`), por lo tanto no exponen el servicio a internet.

Implicaciones:

- para administración, usar SSH por ZeroTier;
- para demo interna, consumir la app desde clientes con ZeroTier;
- para acceso público real, usar túnel saliente o pedir IP pública real al
  administrador del laboratorio.

Security group inicial:

| Puerto | Uso            | Origen                   |
|--------|----------------|--------------------------|
| 22     | SSH            | `192.168.3.0/24`         |
| 8000   | FastAPI        | `192.168.3.0/24` o tunel |
| 8501   | Streamlit      | `192.168.3.0/24` o tunel |

## Decisión actual

PostGIS, API y dashboard ya están integrados localmente. Para subir a UM-Cloud
falta convertir esa integración en operación repetible:

1. provisionar VM y PostGIS;
2. configurar `.env`, `DATABASE_URL`, `AUTH_SECRET` y credenciales GEE;
3. cargar parcelas, usuarios, zonificación y ranking inicial;
4. instalar servicios `systemd` para API, dashboard, pipeline y backup;
5. validar smoke tests contra API/PostGIS;
6. definir respaldo de base y artefactos.

Las plantillas de servicios estan en `deployment/systemd/`.
