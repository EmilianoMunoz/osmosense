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
- exigencia de `AUTH_SECRET` explicito en produccion;
- rechazo de requests sin token o con token invalido;
- permisos por rol;
- acceso de productor solo a sus parcelas asignadas;
- acceso admin a cualquier cartera de productor;
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
- endpoints `/me`, `/me/rankings/latest/geojson` y `/me/parcelas`;
- rankings latest;
- GeoJSON de rankings;
- estado del pipeline;
- ranking por fecha;
- error 503 cuando falta `DATABASE_URL` en modo produccion;
- validacion de que `/me/*` usa el `cliente_id` del token y no un parametro URL;
- endpoints regionales;
- CRUD administrativo de productores y relaciones con parcelas;
- asignacion de parcelas a productores;
- CRUD de usuarios, incluida baja logica por `DELETE`;
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
- validacion de alta/edicion de usuarios productores;
- parseo de IDs para asignacion manual de parcelas;
- deshabilitacion de fallback local y accesos rapidos en produccion;
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

### `tests/test_cloud_maintenance.py`

Valida utilidades de mantenimiento previas al despliegue cloud.

Cubre:

- parseo de contraseñas explícitas `EMAIL=PASSWORD`;
- rechazo de contraseñas demasiado cortas;
- inclusión de usuarios explícitos en la rotación;
- generación de contraseñas aleatorias con largo esperado.

Ejecutar cuando se modifica:

- `backend/scripts/maintenance/rotar_credenciales_cloud.py`;
- flujo de preparación de credenciales para demo cloud.

```bash
venv/bin/python -m pytest tests/test_cloud_maintenance.py -q
```

### `tests/test_smoke_credentials.py`

Valida que los smoke tests lean credenciales rotadas desde variables de entorno.

Cubre:

- `OSMOSENSE_ADMIN_EMAIL` y `OSMOSENSE_ADMIN_PASSWORD`;
- `OSMOSENSE_PRODUCTOR_EMAIL` y `OSMOSENSE_PRODUCTOR_PASSWORD`;
- `OSMOSENSE_REGIONAL_EMAIL` y `OSMOSENSE_REGIONAL_PASSWORD`;
- compatibilidad de los smoke operativo, productor, regional y CRUD.

Ejecutar cuando se modifica:

- `backend/scripts/postgis/smoke_test_operativo.py`;
- `backend/scripts/postgis/smoke_test_productor.py`;
- `backend/scripts/postgis/smoke_test_regional.py`;
- `backend/scripts/postgis/smoke_test_crud_productor.py`.

```bash
venv/bin/python -m pytest tests/test_smoke_credentials.py -q
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
- filtrado de ranking por productor;
- ranking regional por UM;
- GeoJSON regional;
- parcelas de una UM;
- exigencia de `DATABASE_URL` para rankings operativos en produccion;
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

### `tests/test_predictor_validation_report.py`

Valida el reporte reproducible de validacion historica del predictor hidrico.

Cubre:

- agregacion ponderada de metricas por cantidad de parcelas;
- calculo de tolerancias de error absoluto a 5 y 10 puntos;
- acierto de direccion de la evolucion;
- seleccion de fechas a revisar por mayor MAE y menor Spearman.

Ejecutar cuando se modifica:

- `backend/scripts/modeling/generar_reporte_validacion_predictor_hidrico.py`;
- estructura de los CSV de validacion del predictor;
- criterios de resumen historico del modelo predictivo.

```bash
venv/bin/python -m pytest tests/test_predictor_validation_report.py -q
```

### `tests/test_tensorflow_classifier_experiment.py`

Valida utilidades del experimento TensorFlow/Keras para clasificación.

Cubre:

- preparación de features;
- separación por `parcela_id` para evitar fuga de información;
- serialización de métricas;
- comportamiento esperado cuando TensorFlow no está instalado.

Ejecutar cuando se modifica:

- `backend/scripts/experiments/entrenar_clasificador_tensorflow.py`;
- configuración de features del clasificador neuronal;
- dependencias opcionales de `requirements-tensorflow.txt`.

```bash
venv/bin/python -m pytest tests/test_tensorflow_classifier_experiment.py -q
```

### `tests/test_cnn_temporal_classifier.py`

Valida utilidades de la CNN temporal multiclase.

Cubre:

- construcción de tensores por parcela y fecha;
- filtrado de secuencias temporales incompletas;
- separación train/test por parcela;
- preparación de datos para clasificación multiclase.

Ejecutar cuando se modifica:

- `backend/scripts/experiments/entrenar_cnn_temporal_clasificacion.py`;
- dataset temporal multiclase;
- lógica de secuencias por parcela.

```bash
venv/bin/python -m pytest tests/test_cnn_temporal_classifier.py -q
```

## Smoke test operativo

Los tests anteriores son unitarios o de handlers con mocks. Para validar el flujo con API/PostGIS se usa smoke test:

En cloud, si las credenciales demo fueron rotadas, definir:

```bash
export OSMOSENSE_ADMIN_EMAIL=admin@osmosense.local
export OSMOSENSE_ADMIN_PASSWORD='<password-admin-rotado>'
export OSMOSENSE_PRODUCTOR_EMAIL=productor.vid@osmosense.local
export OSMOSENSE_PRODUCTOR_PASSWORD='<password-productor-rotado>'
export OSMOSENSE_REGIONAL_EMAIL=regional@osmosense.local
export OSMOSENSE_REGIONAL_PASSWORD='<password-regional-rotado>'
```

```bash
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
```

Este comando valida que el sistema pueda consultar datos operativos reales desde PostGIS.

Smoke productor-parcela:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_productor.py
```

Este comando valida, sin modificar datos, que existan productores activos,
parcelas analizables sin productor, parcelas asignadas al productor de
desarrollo y que el productor no pueda consultar endpoints admin.

Smoke CRUD productor-parcela:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_crud_productor.py --confirm-mutating
```

Este comando modifica temporalmente PostGIS: toma una parcela libre, la asigna
al productor de desarrollo, verifica que aparezca en `/me/parcelas` y
`/me/rankings/latest/geojson`, la desasigna y verifica que desaparezca. El flag
`--confirm-mutating` es obligatorio para evitar ejecuciones accidentales contra
una base real.

Smoke regional:

```bash
venv/bin/python backend/scripts/postgis/smoke_test_regional.py
```

Este comando valida, sin modificar datos, que el usuario regional pueda consultar
ranking UM, mapa regional y parcelas de una UM, y que no pueda consultar endpoints
admin ni vistas de productor.

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

Antes de tocar validacion historica del predictor:

```bash
venv/bin/python -m pytest tests/test_predictor_validation_report.py -q
```

Antes de tocar experimentos neuronales:

```bash
venv/bin/python -m pytest tests/test_tensorflow_classifier_experiment.py tests/test_cnn_temporal_classifier.py -q
```

Antes de cerrar una tanda grande:

```bash
venv/bin/python -m pytest -q
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis --check-postgis
venv/bin/python backend/scripts/postgis/smoke_test_productor.py
venv/bin/python backend/scripts/postgis/smoke_test_regional.py
```
