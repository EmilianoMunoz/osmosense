# Scripts Backend

Scripts organizados por dominio. Los comandos deben ejecutarse desde la raíz del
proyecto.

| Carpeta | Uso |
|---------|-----|
| `pipeline/` | Extracción Sentinel, targets, ranking y orquestador principal. |
| `postgis/` | Schema, cargas, usuarios demo, validación y smoke tests. |
| `audit/` | Cobertura, vecinos, outliers temporales y ruido puntual. |
| `zonificacion/` | Cruce de parcelas con unidades de manejo regionales. |
| `modeling/` | Validación, importancia de variables y optimización del ranking. |
| `maintenance/` | Reconstrucción de parcelas y GeoJSON auxiliares. |
| `experiments/` | Experimentos o scripts fuera del flujo operativo principal. |

## Principales

```bash
venv/bin/python backend/scripts/pipeline/run_pipeline_hidrico.py --mode local
venv/bin/python backend/scripts/postgis/setup_postgis_local.py --all-parcelas
venv/bin/python backend/scripts/postgis/smoke_test_operativo.py --require-source postgis
```

## Regla de organización

Si un script es parte del flujo estable, debe vivir en una carpeta de dominio.
Si es una prueba o exploración, debe quedar en `experiments/`.
