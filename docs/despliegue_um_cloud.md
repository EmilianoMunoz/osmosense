# Despliegue en UM-Cloud

Este documento convierte la arquitectura cloud en pasos operativos para dejar
OSMOSENSE corriendo en una VM de UM-Cloud. Complementa:

- `docs/UM_Cloud_Setup_Guide.md`: acceso a OpenStack/ZeroTier y creacion de VM.
- `docs/arquitectura_cloud_pipeline.md`: arquitectura del pipeline.
- `docs/postgis.md`: schema, carga y validacion de PostGIS.

## Objetivo

En cloud deben quedar activos:

- PostGIS como fuente operativa;
- API FastAPI;
- dashboard Streamlit;
- pipeline Sentinel/GEE programado;
- backups periodicos de PostGIS;
- smoke tests para validar que el despliegue sirve datos reales.

En produccion no se debe depender de CSV locales como fuente principal.

## 1. Preparar VM

Recomendado inicialmente:

- Ubuntu 24.04 o imagen equivalente disponible en UM-Cloud.
- Acceso por ZeroTier.
- Disco persistente suficiente para PostGIS, logs, rankings y backups.
- Puertos habilitados en security group:

| Puerto | Uso | Origen recomendado |
|--------|-----|--------------------|
| 22 | SSH | red ZeroTier/UM |
| 8000 | API FastAPI | red ZeroTier/UM o proxy |
| 8501 | Dashboard Streamlit | red ZeroTier/UM o proxy |

Instalar base del sistema:

```bash
sudo apt update
sudo apt install -y git python3-venv python3-dev build-essential postgresql-client
```

Si PostGIS se ejecuta con Docker en la misma VM:

```bash
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Cerrar y volver a abrir la sesion para que el grupo `docker` aplique.

Si el repositorio ya fue clonado, este paso puede automatizarse con:

```bash
deployment/scripts/bootstrap_vm.sh --install-docker
```

El script instala paquetes base, crea `venv`, instala dependencias, prepara
`.env` si falta y crea el usuario de servicio `osmosense`. No carga datos ni
arranca servicios.

## 2. Instalar proyecto

Ruta recomendada:

```bash
sudo mkdir -p /opt/osmosense
sudo chown "$USER":"$USER" /opt/osmosense
git clone <URL_DEL_REPO> /opt/osmosense
cd /opt/osmosense
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Alternativa recomendada despues de clonar:

```bash
cd /opt/osmosense
deployment/scripts/bootstrap_vm.sh --install-docker
```

Crear usuario de servicio si se van a usar las units incluidas:

```bash
sudo useradd --system --home /opt/osmosense --shell /usr/sbin/nologin osmosense
```

Mantener la propiedad del directorio en el usuario SSH durante configuracion,
carga inicial y validaciones. Antes de activar `systemd`, cambiar la propiedad
al usuario de servicio. Si se decide ejecutar los servicios con el usuario SSH,
ajustar `User=` y `Group=` en las units de `deployment/systemd/`.

## 3. Configurar `.env`

```bash
cp .env.cloud.example .env
nano .env
chmod 600 .env
```

Valores obligatorios en produccion:

```text
APP_ENV=production
ENABLE_LOCAL_FALLBACK=false
ENABLE_QUICK_LOGIN=false
DATABASE_URL=postgresql://usuario:password@host:5432/estres
AUTH_SECRET=<secreto-largo-no-versionado>
GEE_PROJECT_ID=<proyecto-gee>
API_BASE_URL=http://IP_O_DNS_DE_LA_VM:8000
```

Notas:

- `DATABASE_URL` debe apuntar al PostGIS operativo.
- `AUTH_SECRET` no debe ser el valor de ejemplo.
- `API_BASE_URL` es lo que consume Streamlit para hablar con la API.
- `API_HOST=0.0.0.0` y `STREAMLIT_HOST=0.0.0.0` permiten acceso desde otra
  maquina de la red autorizada.

Validar configuracion antes de continuar:

```bash
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py
```

## 4. Configurar PostGIS

Opcion A: PostGIS por Docker en la VM:

Configurar en `.env` una contraseña fuerte para el contenedor:

```text
POSTGRES_DB=estres
POSTGRES_USER=estres
POSTGRES_PASSWORD=<password-postgis-fuerte>
POSTGIS_BIND=127.0.0.1
POSTGIS_HOST_PORT=5433
DATABASE_URL=postgresql://estres:<password-postgis-fuerte>@127.0.0.1:5433/estres
```

Luego levantar la base:

```bash
docker compose -f docker-compose.postgis.yml up -d
```

El compose expone PostGIS solo en `127.0.0.1:5433` desde la VM. No abrir el
puerto `5433` en el security group.

Opcion B: PostGIS administrado o externo:

- crear base `estres`;
- habilitar extension PostGIS;
- configurar `DATABASE_URL` contra esa base;
- no exponer el puerto fuera de la red necesaria.

## 5. Cargar datos iniciales

Primera carga operativa:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
```

Aunque el script conserva `local` en el nombre, usa `DATABASE_URL`; por lo
tanto sirve para la base PostGIS cloud si `.env` apunta a esa base.

Este comando aplica schema y carga:

- parcelas;
- ranking latest disponible;
- relaciones productor-parcela demo/operativas;
- zonificacion UM;
- usuarios iniciales.

Validar PostGIS sin API:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --skip-api --check-postgis
```

Antes de exponer la VM, cambiar o reemplazar las credenciales demo cargadas por
el setup. En produccion no deben quedar contraseñas conocidas como
`admin123`, `cliente123` o `regional123`.

Rotacion automatica de credenciales demo:

```bash
venv/bin/python backend/scripts/maintenance/rotar_credenciales_cloud.py --confirm
```

El comando imprime las nuevas contraseñas generadas. Si se quiere definir una
contraseña concreta para un usuario:

```bash
venv/bin/python backend/scripts/maintenance/rotar_credenciales_cloud.py --confirm --set admin@osmosense.local='CONTRASEÑA_LARGA'
```

Validar tambien contra la base:

```bash
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py --check-db
```

## 6. Configurar Google Earth Engine

La VM debe poder inicializar Earth Engine con `GEE_PROJECT_ID`.

Para una demo/tesis se puede autenticar manualmente desde la VM:

```bash
venv/bin/earthengine authenticate
```

El pipeline `systemd` corre con el usuario `osmosense`, por lo que las
credenciales deben quedar disponibles en su home (`/opt/osmosense`). Si se
autenticó con el usuario SSH, copiar las credenciales antes de instalar
`systemd`:

```bash
mkdir -p /opt/osmosense/.config/earthengine
cp ~/.config/earthengine/credentials /opt/osmosense/.config/earthengine/credentials
sudo chown -R osmosense:osmosense /opt/osmosense/.config
```

Para producción formal, preferir una cuenta de servicio de GEE y credenciales
no interactivas.

Validar manualmente antes de programar el pipeline:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud
```

Para una ejecucion real con Sentinel y carga en PostGIS:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Si no hay imagen Sentinel valida nueva, el pipeline debe terminar sin
sobrescribir el ranking.

## 7. Levantar servicios manualmente

Para una prueba rapida sin systemd:

```bash
API_HOST=0.0.0.0 STREAMLIT_HOST=0.0.0.0 ./boot.sh start --smoke
```

URLs esperadas desde la red habilitada:

- API: `http://IP_O_DNS_DE_LA_VM:8000/health`
- Dashboard: `http://IP_O_DNS_DE_LA_VM:8501`

## 8. Instalar servicios systemd

Dar permisos al usuario de servicio:

```bash
sudo chown -R osmosense:osmosense /opt/osmosense
```

Copiar plantillas:

```bash
sudo cp deployment/systemd/osmosense-api.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-dashboard.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-pipeline.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-pipeline.timer /etc/systemd/system/
sudo cp deployment/systemd/osmosense-postgis-backup.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-postgis-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
```

Alternativa con script:

```bash
deployment/scripts/install_systemd.sh --chown-service-user --enable --start
```

El script copia todas las units, ejecuta `systemctl daemon-reload`, habilita
los servicios y los arranca. Si se quiere revisar antes de iniciar, omitir
`--start`.

Activar API y dashboard:

```bash
sudo systemctl enable --now osmosense-api.service
sudo systemctl enable --now osmosense-dashboard.service
```

Activar pipeline y backup programados:

```bash
sudo systemctl enable --now osmosense-pipeline.timer
sudo systemctl enable --now osmosense-postgis-backup.timer
```

Verificar estado:

```bash
systemctl status osmosense-api.service
systemctl status osmosense-dashboard.service
systemctl list-timers "osmosense-*"
```

Ver logs:

```bash
journalctl -u osmosense-api.service -f
journalctl -u osmosense-dashboard.service -f
journalctl -u osmosense-pipeline.service -n 200
```

## 9. Smoke tests post-despliegue

Con API levantada:

```bash
API_BASE_URL=http://IP_O_DNS_DE_LA_VM:8000 venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
API_BASE_URL=http://IP_O_DNS_DE_LA_VM:8000 venv/bin/python backend/scripts/postgis/smoke_test_productor.py
API_BASE_URL=http://IP_O_DNS_DE_LA_VM:8000 venv/bin/python backend/scripts/postgis/smoke_test_regional.py
```

Smoke mutante de CRUD productor-parcela:

```bash
API_BASE_URL=http://IP_O_DNS_DE_LA_VM:8000 venv/bin/python backend/scripts/postgis/smoke_test_crud_productor.py --confirm-mutating
```

Este ultimo asigna temporalmente una parcela libre, valida `/me/parcelas` y
`/me/rankings/latest/geojson`, y revierte la asignacion.

## 10. Backups

La unit `osmosense-postgis-backup.timer` ejecuta `pg_dump` diario y guarda:

```text
backend/data/backups/postgis/estres_YYYYMMDD_HHMMSS.sql.gz
```

Ese directorio debe quedar fuera de Git y, en produccion, copiarse
periodicamente a almacenamiento externo o volumen persistente.

## 11. Criterios de listo para demo cloud

Antes de mostrar la demo desde UM-Cloud:

- `APP_ENV=production`.
- `ENABLE_LOCAL_FALLBACK=false`.
- `ENABLE_QUICK_LOGIN=false`.
- Credenciales demo reemplazadas o contraseñas rotadas.
- `.env` con permisos restringidos al usuario de servicio.
- `run_preflight_cloud.py --check-db` sin fallas.
- API responde `/health`.
- Dashboard carga sin avisos de fallback.
- Login funciona para admin, productor y regional.
- Productor ve solo sus parcelas asignadas.
- Admin puede asignar/desasignar parcelas y el productor refleja el cambio.
- Regional carga UM y detalle de parcelas.
- `osmosense-pipeline.timer` queda activo.
- `osmosense-postgis-backup.timer` queda activo.
- Hay al menos un backup restaurable reciente.

## 12. Riesgos a revisar antes de produccion abierta

Para una demo interna por ZeroTier alcanza con restringir red, secretos y
credenciales. Para exposicion mas amplia, revisar ademas:

- HTTPS mediante proxy inverso;
- rate limiting en `/auth/login`;
- politica de rotacion de `AUTH_SECRET`;
- backups cifrados o copiados a almacenamiento con acceso restringido;
- usuario PostGIS no superusuario y sin acceso remoto innecesario;
- auditoria minima de altas, bajas y asignaciones productor-parcela.
