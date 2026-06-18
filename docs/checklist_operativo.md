# Checklist Operativo

Checklist corto para levantar, validar y actualizar el sistema sin depender de pasos manuales dispersos.

## 1. Antes de levantar

- Confirmar que existe `.env` con las variables de PostGIS/API usadas por el proyecto.
- Confirmar que Docker esta disponible si se usa PostGIS local.
- Confirmar credenciales de Google Earth Engine si se va a ejecutar el pipeline con Sentinel.
- En producción, confirmar `APP_ENV=production`, `DATABASE_URL`, `AUTH_SECRET`,
  `ENABLE_LOCAL_FALLBACK=false` y `ENABLE_QUICK_LOGIN=false`.
- Antes de demo cloud, correr:

```bash
venv/bin/python backend/scripts/maintenance/rotar_credenciales_cloud.py --confirm
venv/bin/python backend/scripts/maintenance/run_preflight_cloud.py --check-db
```

## 2. Levantar el stack

Uso normal:

```bash
./boot.sh start
```

Primera carga completa o reconstruccion local:

```bash
./boot.sh start --setup --all-parcelas --smoke
```

Verificar estado:

```bash
./boot.sh status
```

URLs esperadas:

- API: `http://127.0.0.1:8000/health`
- Dashboard: `http://127.0.0.1:8501`

En UM-Cloud, el arranque productivo recomendado no es `boot.sh`, sino
`systemd` con las plantillas de `deployment/systemd/`. El procedimiento completo
esta en `docs/despliegue_um_cloud.md`.

## 3. Validar acceso

- Entrar al dashboard.
- Usar login rapido PostGIS para `admin`, `regional` o `productor`.
- Verificar que no aparezcan avisos de fallback local.
- En admin, revisar `Estado general` y `Estado operativo del pipeline`.

## 4. Actualizar ranking

Actualizar solo si existe una imagen Sentinel valida nueva:

```bash
./boot.sh start --update-ranking
```

O ejecutar el pipeline directamente:

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode cloud --update-sentinel --parcel-source postgis --skip-if-no-new-date --load-postgis
```

Luego, en el dashboard admin, usar `Actualizar datos` para limpiar cache y recargar la vista.

## 5. Validaciones rapidas

Smoke PostGIS:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```

Smoke productor-parcela:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_productor.py
```

Smoke CRUD productor-parcela:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_crud_productor.py --confirm-mutating
```

Smoke regional:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_regional.py
```

Tests:

```bash
venv/bin/python -m pytest -q
```

## 6. Revisión por rol

- Admin: gestion de usuarios/parcelas separada del analisis.
- Productor: solo parcelas asignadas, mapa y detalle simple.
- Regional: resumen por UM y foco regional.

## 7. Problemas comunes

- `Usando fallback local`: revisar API levantada, token/sesion y conexion a PostGIS.
- `422` al crear usuario: revisar email, password minimo de 6 caracteres y datos requeridos.
- `Sin imagen nueva`: estado esperado cuando Sentinel no tiene una fecha valida posterior a la ultima cargada.
- Mapa desactualizado despues de correr pipeline: usar `Actualizar datos` en admin.

## 8. Apagar

```bash
./boot.sh stop
```

En cloud:

```bash
sudo systemctl stop osmosense-dashboard.service
sudo systemctl stop osmosense-api.service
```
