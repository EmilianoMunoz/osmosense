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
