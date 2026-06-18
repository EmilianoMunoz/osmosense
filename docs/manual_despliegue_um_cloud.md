# Manual Del Despliegue UM-Cloud

Este documento resume el despliegue real de OSMOSENSE en UM-Cloud, incluyendo
los pasos ejecutados, errores encontrados, soluciones aplicadas y diferencias
respecto del uso local.

No incluye secretos, contraseñas ni tokens.

## Estado Final

```text
VM: osmosense-vm
IP interna: 10.201.3.193
Acceso: ZeroTier / UM-Cloud
Ruta del proyecto: /opt/osmosense
PostGIS: Docker, contenedor estres-postgis
PostGIS host: 127.0.0.1:5433
API: osmosense-api.service
Dashboard: osmosense-dashboard.service
Pipeline: osmosense-pipeline.timer
Backup: osmosense-postgis-backup.timer
```

Validación final:

```text
run_preflight_cloud.py --check-db -> 0 fallas, 0 advertencias
API -> active/running
Dashboard -> active/running
Pipeline timer -> activo
Backup timer -> activo
Backup válido -> estres_20260618_162731.sql.gz (~9.1M)
Ranking cloud generado -> 2026-06-13
Parcelas rankeadas -> 4714
```

URL de acceso al dashboard, con ZeroTier activo:

```text
http://10.201.3.193:8501
```

Healthcheck API:

```text
http://10.201.3.193:8000/health
```

## Qué Ganamos Al Pasar A Cloud

El sistema deja de depender de ejecutar procesos manuales desde la notebook.
Ahora queda montado como servicio persistente:

- la API y el dashboard siguen corriendo aunque se cierre la sesión SSH;
- PostGIS queda como fuente operativa central;
- el dashboard consume datos desde la API/PostGIS, no desde CSV locales;
- el pipeline puede ejecutarse automáticamente por timer;
- hay backup periódico de PostGIS;
- el entorno se parece más a producción, con `APP_ENV=production`, sin fallback
  local y sin login rápido;
- se puede acceder desde otra máquina conectada a la red UM-Cloud/ZeroTier.

La notebook local queda como entorno de desarrollo. La VM queda como entorno de
demo/despliegue.

## Diferencias Respecto Del Modo Local

En local:

- se puede trabajar con CSV/GeoJSON como fallback;
- el dashboard puede cargar datos locales;
- se usan credenciales y accesos de desarrollo;
- los procesos se levantan manualmente con `boot.sh`;
- si se cierra la terminal, puede frenarse el servicio.

En cloud:

- `ENABLE_LOCAL_FALLBACK=false`;
- `ENABLE_QUICK_LOGIN=false`;
- `DATABASE_URL` apunta a PostGIS;
- API, dashboard, pipeline y backup corren con `systemd`;
- PostGIS no se expone a la red, solo está disponible en `127.0.0.1:5433`;
- los servicios corren con usuario de sistema `osmosense`;
- los datos grandes no versionados deben copiarse como artefactos operativos.

## Acceso A La VM

La VM se accede desde la notebook con ZeroTier activo.

Comando SSH:

```bash
ssh -i ~/Descargas/osmosense-key.pem ubuntu@10.201.3.193
```

Si el archivo `.pem` da error de permisos:

```bash
chmod 600 ~/Descargas/osmosense-key.pem
```

El proyecto está en:

```bash
cd /opt/osmosense
```

Después de instalar `systemd`, la carpeta quedó bajo propiedad del usuario
`osmosense`. Para hacer `git pull`:

```bash
sudo -u osmosense -H git -C /opt/osmosense pull
```

Si Git marca `dubious ownership`:

```bash
sudo -u osmosense -H git -C /opt/osmosense config --global --add safe.directory /opt/osmosense
```

## Pasos Ejecutados

### 1. Preparación De UM-Cloud

Se usó la guía `docs/UM_Cloud_Setup_Guide.md`:

1. ingreso al portal UM-Cloud;
2. obtención de credenciales OpenStack;
3. conexión de la notebook a ZeroTier;
4. creación de keypair SSH;
5. creación de security group;
6. lanzamiento de VM.

Security group usado:

```text
22/tcp   -> 192.168.3.0/24
8000/tcp -> 192.168.3.0/24
8501/tcp -> 192.168.3.0/24
```

No se abrió PostGIS (`5433`). La base queda solo local a la VM.

Imagen usada:

```text
srv-docker-ubuntu2404
```

### 2. Clonado Del Proyecto

En la VM:

```bash
sudo mkdir -p /opt/osmosense
sudo chown "$USER":"$USER" /opt/osmosense
git clone https://github.com/EmilianoMunoz/osmosense.git /opt/osmosense
cd /opt/osmosense
```

Se usó HTTPS porque la key SSH configurada en GitHub correspondía a la notebook,
no a la VM.

### 3. Bootstrap De La VM

Primer intento:

```bash
deployment/scripts/bootstrap_vm.sh --install-docker
```

Error encontrado:

```text
containerd.io : Conflicts: containerd
```

Causa:

La imagen `srv-docker-ubuntu2404` ya traía parte del stack Docker instalado.
Instalar `docker.io` encima generaba conflicto de paquetes.

Solución:

```bash
deployment/scripts/bootstrap_vm.sh --skip-packages
```

Resultado:

- `venv` creado;
- dependencias Python instaladas;
- `.env` creado desde `.env.cloud.example`;
- usuario de servicio `osmosense` preparado.

### 4. Configuración De `.env`

Se configuró:

```text
APP_ENV=production
ENABLE_LOCAL_FALLBACK=false
ENABLE_QUICK_LOGIN=false
API_BASE_URL=http://10.201.3.193:8000
API_HOST=0.0.0.0
STREAMLIT_HOST=0.0.0.0
POSTGIS_BIND=127.0.0.1
POSTGIS_HOST_PORT=5433
DATABASE_URL=postgresql://estres:<password>@127.0.0.1:5433/estres
GEE_PROJECT_ID=estres-hidrico-493912
```

Para PostGIS se usó password hexadecimal:

```bash
openssl rand -hex 24
```

Motivo:

El primer password se generó en base64 y tenía caracteres como `/`, `+` y `=`.
Eso rompía `DATABASE_URL`.

Error observado:

```text
psycopg.OperationalError: failed to resolve host 'estres'
```

Solución:

- borrar volumen vacío;
- generar password con `openssl rand -hex 24`;
- actualizar `POSTGRES_PASSWORD` y `DATABASE_URL`;
- recrear PostGIS.

### 5. PostGIS En Docker

Comando:

```bash
docker compose -f docker-compose.postgis.yml up -d
```

Verificación:

```bash
docker ps
```

Resultado:

```text
estres-postgis -> healthy
127.0.0.1:5433->5432/tcp
```

### 6. Copia De Artefactos Operativos

Los datos grandes están fuera de Git. Por eso el primer setup falló con:

```text
backend/data/parcelas/san_rafael_completo_wgs84.geojson: No such file or directory
```

Solución:

Se empaquetaron desde la notebook y se copiaron por `scp` a la VM:

```text
backend/data/parcelas/san_rafael_completo_wgs84.geojson
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
backend/data/rankings/ranking_hidrico_latest.csv
backend/data/clientes/clientes.csv
backend/data/clientes/cliente_parcela.csv
backend/data/zonificacion/regional_dgi_san_rafael.geojson
backend/data/zonificacion/um_con_cultivos.geojson
backend/data/zonificacion/parcelas_um.csv
backend/data/zonificacion/ranking_um_latest.csv
backend/data/limites/san_rafael.geojson
backend/models/ranking_hidrico_config.json
backend/models/hidrico_regresion/
```

### 7. Carga Inicial De PostGIS

Comando:

```bash
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
```

Resultado:

```text
Parcelas cargadas: 47091
Ranking latest cargado: 9679 filas
Clientes: 2
Relaciones productor-parcela: 29
Zonas UM: 34
Relaciones parcela-UM: 10667
Usuarios operativos: 4
```

Después se rotaron credenciales demo:

```bash
venv/bin/python backend/scripts/maintenance/rotar_credenciales_cloud.py --confirm
```

Validación:

```bash
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py --check-db
```

Resultado final:

```text
0 fallas, 0 advertencias
```

### 7.1. Ranking Latest Y Cobertura

Durante el primer ensayo cloud se generó un ranking nuevo para `2026-06-13`
con `4714` parcelas rankeadas. El dashboard mostraba una franja parcial del
departamento porque la vista `ranking_hidrico_latest` tomaba simplemente la
fecha más reciente.

Corrección aplicada:

```text
ranking_hidrico_cobertura_fechas
ranking_hidrico_latest_date
ranking_hidrico_latest
ranking_um_latest
```

Ahora PostGIS conserva el ranking parcial, pero solo lo usa como `latest`
operativo si cubre al menos el `80%` de las parcelas objetivo vid/olivo con
`area_m2 >= 4000`. Si una fecha nueva no cumple esa cobertura, el dashboard
sigue usando la última fecha completa disponible.

Consulta útil de diagnóstico:

```sql
SELECT fecha_ranking, parcelas_rankeadas, parcelas_objetivo,
       round(cobertura_ratio::numeric, 3) AS cobertura_ratio,
       elegible_latest
FROM ranking_hidrico_cobertura_fechas
ORDER BY fecha_ranking DESC;
```

### 8. API Y Dashboard

Primera prueba manual:

```bash
API_HOST=0.0.0.0 STREAMLIT_HOST=0.0.0.0 ./boot.sh start --smoke
```

El smoke falló porque usaba passwords demo viejas (`admin123`) después de haber
rotado credenciales. Esto no bloqueó el despliegue: API y dashboard estaban
levantados.

Verificación manual:

```text
http://10.201.3.193:8501
```

Resultado:

- dashboard accesible;
- login correcto;
- parcelas cargadas desde PostGIS.

### 9. Instalación Con `systemd`

Se detuvo el arranque manual y se instalaron servicios:

```bash
./boot.sh stop
deployment/scripts/install_systemd.sh --chown-service-user --enable --start
```

Servicios:

```text
osmosense-api.service
osmosense-dashboard.service
osmosense-pipeline.timer
osmosense-postgis-backup.timer
```

Verificación:

```bash
systemctl status osmosense-api.service --no-pager
systemctl status osmosense-dashboard.service --no-pager
systemctl list-timers "osmosense-*"
```

Resultado:

```text
API active/running
Dashboard active/running
Pipeline timer activo
Backup timer activo
```

### 10. Earth Engine En La VM

Primer intento:

```bash
venv/bin/earthengine authenticate
```

Error:

```text
gcloud command not found
```

Causa:

Earth Engine intentó autenticarse por modo `gcloud`, pero la VM no tenía Google
Cloud CLI instalado.

Solución:

```bash
venv/bin/earthengine authenticate --auth_mode=notebook
venv/bin/earthengine set_project estres-hidrico-493912
```

Luego se copiaron credenciales al home del usuario de servicio:

```bash
sudo mkdir -p /opt/osmosense/.config/earthengine
sudo cp ~/.config/earthengine/credentials /opt/osmosense/.config/earthengine/credentials
sudo chown -R osmosense:osmosense /opt/osmosense/.config
```

Validación:

```bash
sudo -u osmosense -H bash -lc 'cd /opt/osmosense && venv/bin/python -c "import ee, os; from dotenv import load_dotenv; load_dotenv(); ee.Initialize(project=os.getenv(\"GEE_PROJECT_ID\")); print(ee.Number(1).getInfo())"'
```

Resultado:

```text
1
```

### 11. Pipeline Cloud

Primer error:

```text
backend/data/parcelas/parcelas_ide.geojson: No such file or directory
```

Causa:

El servicio `osmosense-pipeline.service` corría sin `--update-recent-window`.
Eso intentaba reconstruir todo el histórico desde `2023-01-01` y terminaba
buscando archivos locales.

Solución:

Actualizar la unit:

```text
--update-sentinel --update-recent-window --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Resultado posterior:

```text
Latest Sentinel candidato: 2026-06-13 -> 2026-06-18 imagenes=10
Muestra PostGIS: 9679 parcelas
Observaciones válidas: 4714/9679
Ranking generado: 2026-06-13
```

Segundo error:

```text
backend/data/zonificacion/regional_dgi_san_rafael.geojson: No such file or directory
```

Causa:

Faltaban artefactos regionales no versionados.

Solución:

Copiar:

```text
backend/data/zonificacion/regional_dgi_san_rafael.geojson
backend/data/parcelas/san_rafael_vid_olivo_wgs84.geojson
```

Luego regenerar zonificación y cargar ranking/zonificación en PostGIS.

### 12. Backup PostGIS

Primer backup:

```text
estres_20260618_160546.sql.gz -> 20 B
```

Problema:

El archivo era inválido. El log mostró:

```text
pg_dump: aborting because of server version mismatch
server version: 17.10
pg_dump version: 16.14
```

Causa:

PostGIS corre en Docker con PostgreSQL 17, pero el host Ubuntu tenía
`pg_dump` 16.

Solución:

`deployment/scripts/backup_postgis.sh` usa `pg_dump` dentro del contenedor
`estres-postgis`. La unit `osmosense-postgis-backup.service` permite acceso al
grupo `docker`.

Backup válido:

```text
estres_20260618_162731.sql.gz -> ~9.1M
```

El backup vacío anterior se puede borrar:

```bash
sudo rm /opt/osmosense/backend/data/backups/postgis/estres_20260618_160546.sql.gz
```

## Operación Diaria

### Ver Servicios

```bash
systemctl status osmosense-api.service --no-pager
systemctl status osmosense-dashboard.service --no-pager
systemctl list-timers "osmosense-*"
```

### Ver Logs

```bash
journalctl -u osmosense-api.service -n 120 --no-pager
journalctl -u osmosense-dashboard.service -n 120 --no-pager
journalctl -u osmosense-pipeline.service -n 160 --no-pager
journalctl -u osmosense-postgis-backup.service -n 80 --no-pager
```

Para seguir logs en vivo:

```bash
journalctl -u osmosense-pipeline.service -f
```

Salir con `Ctrl + C`.

### Reiniciar Servicios

```bash
sudo systemctl restart osmosense-api.service
sudo systemctl restart osmosense-dashboard.service
```

### Ejecutar Backup Manual

```bash
sudo systemctl start osmosense-postgis-backup.service
ls -lh /opt/osmosense/backend/data/backups/postgis
```

### Ejecutar Pipeline Manual

```bash
sudo systemctl start osmosense-pipeline.service
journalctl -u osmosense-pipeline.service -f
```

### Actualizar Código En La VM

En la notebook:

```bash
git add .
git commit -m "mensaje"
git push
```

En la VM:

```bash
sudo -u osmosense -H git -C /opt/osmosense pull
```

Si se modificaron units:

```bash
cd /opt/osmosense
sudo cp deployment/systemd/osmosense-api.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-dashboard.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-pipeline.service /etc/systemd/system/
sudo cp deployment/systemd/osmosense-postgis-backup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart osmosense-api.service osmosense-dashboard.service
```

## Qué No Hay Que Hacer

- No abrir `5433` en el security group.
- No subir `.env` al repositorio.
- No documentar contraseñas en Markdown.
- No ejecutar `docker compose down -v` si ya hay datos cargados, porque borra el
  volumen de PostGIS.
- No depender de CSV locales en producción.
- No usar `admin123`, `cliente123` o `regional123` en cloud.

## Cierre De Sesión

No hace falta dejar ninguna terminal abierta.

Los servicios siguen ejecutándose por `systemd`:

- API;
- dashboard;
- pipeline timer;
- backup timer;
- PostGIS por Docker con `restart: unless-stopped`.

Para salir de la VM:

```bash
exit
```

En la notebook se pueden cerrar las terminales y el editor. Mantener ZeroTier
activo solo es necesario para acceder al dashboard o a la VM.

## Pendientes No Bloqueantes

- Copiar backups a almacenamiento externo o volumen persistente adicional.
- Evaluar HTTPS/proxy inverso si se quiere acceso fuera de ZeroTier.
- Reemplazar autenticación manual Earth Engine por cuenta de servicio si el
  proyecto pasa de demo/tesis a producción formal.
