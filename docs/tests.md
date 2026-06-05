# Tests

Documentacion de la suite de pruebas automatizadas del proyecto.

## Comando general

Ejecutar toda la suite:

```bash
venv/bin/python -m pytest -q
```

Ejecutar un archivo puntual:

```bash
venv/bin/python -m pytest tests/test_auth.py -q
```

## Archivos de tests

### `tests/test_auth.py`

Valida la seguridad basica de autenticacion y permisos.

Cubre:

- hash y verificacion de passwords;
- creacion y lectura de access tokens;
- rechazo de requests sin token o con token invalido;
- permisos por rol;
- acceso de productor solo a su propio productor/campo;
- acceso admin a cualquier productor/campo;
- rechazo de regional sobre endpoints de productor.

Ejecutar cuando se modifica:

- `backend/app/services/auth.py`;
- dependencias de auth en `backend/app/main.py`;
- reglas de roles o permisos.

```bash
venv/bin/python -m pytest tests/test_auth.py -q
```

### `tests/test_api_handlers.py`

Valida que los handlers principales de FastAPI respondan o deleguen correctamente.

Cubre:

- `/health`;
- `/auth/login`;
- rankings latest;
- GeoJSON de rankings;
- estado del pipeline;
- ranking por fecha;
- endpoints regionales;
- CRUD administrativo de productores/campos;
- asignacion de parcelas a productores;
- CRUD de usuarios;
- consulta y activacion de parcelas disponibles.

Estos tests usan mocks para comprobar que `backend/app/main.py` llama al servicio correcto con los parametros esperados. No reemplazan un smoke test contra PostGIS real.

Ejecutar cuando se modifica:

- `backend/app/main.py`;
- schemas Pydantic de request/response;
- endpoints admin, regional, productor o ranking.

```bash
venv/bin/python -m pytest tests/test_api_handlers.py -q
```

### `tests/test_frontend_logic.py`

Valida logica de frontend que debe ser estable aunque cambie la presentacion visual.

Cubre:

- uso de proyecciones operativas en lugar de predicciones crudas;
- calculo de deltas operativos;
- prioridades dinamicas por percentiles sin modificar el score real;
- prioridades regionales dinamicas;
- datos mostrados en hover del mapa;
- columnas ocultas al productor;
- columnas tecnicas visibles en admin;
- labels legibles de tablas;
- resumen de estado del productor;
- filtrado de GeoJSON;
- lectura de errores de API para mostrar mensajes utiles.

Ejecutar cuando se modifica:

- `frontend/logic.py`;
- `frontend/data.py`;
- `frontend/table_config.py`;
- componentes que preparan datos para el dashboard;
- reglas de prioridad visual o columnas por rol.

```bash
venv/bin/python -m pytest tests/test_frontend_logic.py -q
```

### `tests/test_map_animation.py`

Valida la animacion del mapa de productor.

Cubre:

- el escenario sin riego no debe mostrar una mejora artificial del riesgo;
- el empeoramiento proyectado se acentua levemente;
- la categoria visual de la animacion se calcula con umbrales absolutos, no por posicion relativa contra otras parcelas.

Ejecutar cuando se modifica:

- `frontend/map.py`;
- logica de slider temporal;
- colores/categorias del mapa proyectado;
- reglas de riesgo actual, 5 dias y 10 dias.

```bash
venv/bin/python -m pytest tests/test_map_animation.py -q
```

### `tests/test_rankings_service.py`

Valida el servicio de rankings y sus fallbacks.

Cubre:

- lectura de ranking latest desde CSV cuando no hay PostGIS;
- generacion de GeoJSON latest;
- filtrado de ranking por productor/campo;
- ranking regional por UM;
- GeoJSON regional;
- parcelas de una UM;
- enriquecimiento de calidad con auditorias de vecinos, ruido, historial y outliers;
- ranking por fecha;
- errores claros cuando faltan columnas requeridas;
- errores claros cuando el GeoJSON de parcelas no tiene identificador.

Ejecutar cuando se modifica:

- `backend/app/services/rankings.py`;
- archivos CSV/GeoJSON esperados por el fallback local;
- enriquecimiento de calidad/outliers;
- estructura de ranking latest;
- endpoints que consumen ranking regional o por productor.

```bash
venv/bin/python -m pytest tests/test_rankings_service.py -q
```

## Smoke test operativo

Los tests anteriores son unitarios o de handlers con mocks. Para validar el flujo con API/PostGIS se usa smoke test:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```

Este comando valida que el sistema pueda consultar datos operativos reales desde PostGIS.

## Cuándo correr qué

Antes de commitear cambios chicos de frontend:

```bash
venv/bin/python -m pytest tests/test_frontend_logic.py tests/test_map_animation.py -q
```

Antes de commitear cambios de auth/API:

```bash
venv/bin/python -m pytest tests/test_auth.py tests/test_api_handlers.py -q
```

Antes de tocar ranking, PostGIS o estructura de datos:

```bash
venv/bin/python -m pytest tests/test_rankings_service.py -q
```

Antes de cerrar una tanda grande:

```bash
venv/bin/python -m pytest -q
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```
