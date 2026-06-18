# Deployment

Plantillas de despliegue para ambientes persistentes.

## systemd

`deployment/systemd/` contiene units para:

- API FastAPI (`osmosense-api.service`);
- dashboard Streamlit (`osmosense-dashboard.service`);
- pipeline Sentinel/GEE diario (`osmosense-pipeline.service` + timer);
- backup diario de PostGIS (`osmosense-postgis-backup.service` + timer).

Estan pensadas para una instalacion en `/opt/osmosense` con usuario de servicio
`osmosense` y archivo `/opt/osmosense/.env`.

La guia completa esta en `docs/despliegue_um_cloud.md`.

## Scripts

`deployment/scripts/` contiene ayudas para repetir el despliegue en una VM:

- `bootstrap_vm.sh`: prepara una VM Ubuntu luego de clonar el repositorio.
  Instala paquetes base, opcionalmente Docker, crea `venv`, instala
  `requirements.txt`, crea `.env` desde `.env.cloud.example` si falta y deja
  permisos `600`.
- `install_systemd.sh`: copia las units a `/etc/systemd/system`, ejecuta
  `daemon-reload` y, si se indica, habilita o arranca API, dashboard, pipeline
  y backup.

Ejemplo de primer despliegue:

```bash
deployment/scripts/bootstrap_vm.sh --install-docker
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py
deployment/scripts/install_systemd.sh --chown-service-user --enable --start
```

Antes de instalar systemd, revisar `.env` y validar PostGIS/datos iniciales.
