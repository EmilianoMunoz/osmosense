# Arquitectura cloud del pipeline hídrico

Este documento define cómo debe quedar desplegado el sistema en UM-Cloud
cuando el pipeline local esté estabilizado. No reemplaza la guía de acceso
`docs/UM_Cloud_Setup_Guide.md`; la complementa con la arquitectura propia
del proyecto.

## Objetivo operativo

El sistema debe ejecutar periódicamente el pipeline de monitoreo hídrico
para parcelas de vid y olivo de San Rafael, Mendoza. Cada ejecución debe:

1. consultar nuevas observaciones Sentinel-2 válidas mediante Google Earth
   Engine;
2. actualizar el dataset temporal local;
3. generar el ranking hídrico con modelos de regresión a 5 y 10 días;
4. publicar un archivo `latest` consumible por backend/mapa;
5. dejar logs y estado auditable de la ejecución.

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
- orquestador programado;
- rankings generados;
- API FastAPI para servir rankings al dashboard/mapa.
- dashboard Streamlit para visualización operativa.

La VM no necesita procesar rasters pesados si GEE mantiene el procesamiento
server-side.

## Componentes iniciales en la VM

Una primera versión puede correr en una única VM Ubuntu de UM-Cloud:

- `git` para obtener el proyecto;
- Python 3.10+ y `venv`;
- archivo `.env` con `GEE_PROJECT_ID`;
- autenticación Earth Engine configurada para el usuario de ejecución;
- modelos en `models/hidrico_regresion/`;
- datasets base en `data/`;
- ejecución programada con `systemd timer` o `cron`.

El comando operativo previsto es:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py --mode cloud --update-sentinel --skip-if-no-new-date --load-postgis
```

Para pruebas sin consultar GEE:

```bash
venv/bin/python scripts/run_pipeline_hidrico.py --mode cloud
```

## Entradas esperadas

| Entrada              | Ubicación prevista| Nota                                               |
|----------------------|-------------------|----------------------------------------------------|
| Parcelas base        | `data/parcelas/`  | Geometrías/etiquetas oficiales o muestra operativa.|
| Dataset temporal     | `data/dataset_temporal_hidrico.csv` | Regenerable; no debe versionarse en Git. |
| Modelos de regresión | `models/hidrico_regresion/*.pkl` | Artefactos pesados; idealmente subir por release/artifact, no Git normal. |
| Configuración GEE    | `.env` + credenciales EE | No versionar secretos. |

## Salidas operativas

El orquestador genera:

```text
data/rankings/ranking_hidrico_YYYY-MM-DD.csv
data/rankings/ranking_hidrico_latest.csv
data/state/pipeline_hidrico_state.json
data/logs/pipeline_hidrico_YYYYMMDD_HHMMSS.log
```

Estas salidas son artefactos de ejecución y quedan ignoradas por Git. En cloud
deben conservarse en disco, respaldarse o migrarse luego a base de datos.

## Publicación del ranking

Fase 1:
el mapa/backend lee `data/rankings/ranking_hidrico_latest.csv`.

Fase 2:
persistir rankings en PostgreSQL/PostGIS o una tabla relacional simple,
manteniendo histórico por fecha.

Fase 3:
exponer endpoints FastAPI:

- `GET /rankings/latest`
- `GET /rankings/latest/geojson`
- `GET /rankings/{fecha}`
- `GET /health`

Fase 4:
dashboard Streamlit consumiendo `/rankings/latest/geojson`.

## Programación automática

Sentinel-2 tiene revisita aproximada de 5 días, pero no toda imagen es válida
por nubes, máscara SCL o baja cantidad de píxeles útiles. Por eso conviene
ejecutar el pipeline más seguido que cada 5 días, por ejemplo diariamente o cada
48 horas, y que el sistema rankee solo cuando haya una nueva fecha válida.

Configuración recomendada inicial:

- ejecución diaria de madrugada;
- logs por ejecución;
- estado persistido en `data/state/pipeline_hidrico_state.json`;
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
| 8000   | FastAPI futura | `192.168.3.0/24` o túnel |

## Decisión actual

No se sube todavía el proyecto a UM-Cloud como ambiente productivo. Primero se
cierran y validan:

1. orquestador local/cloud;
2. contrato de archivos de entrada/salida;
3. ranking histórico y métricas;
4. documentación mínima de operación;
5. limpieza de artefactos pesados fuera de Git.
6. carga del ranking en PostGIS.

Cuando eso esté estable, el despliegue en UM-Cloud debería ser principalmente
provisionar la VM, instalar dependencias, cargar artefactos y programar el
orquestador.
