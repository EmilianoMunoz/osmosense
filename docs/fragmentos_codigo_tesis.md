# Fragmentos De Codigo Para Marco Metodologico

Este documento selecciona fragmentos cortos del codigo fuente que pueden ser
citados en el marco metodologico. No reemplaza al repositorio ni pretende
documentar funciones completas. Cada bloque ilustra una decision de diseno no
trivial y debe ir acompanado por su explicacion.

Rutas equivalentes a las mencionadas en la guia:

| Nombre citado | Ruta actual en el proyecto |
|---|---|
| `run_pipeline_hidrico.py` | `backend/scripts/pipeline/run_pipeline_hidrico.py` |
| `generar_dataset_temporal_hidrico.py` | `backend/scripts/pipeline/generar_dataset_temporal_hidrico.py` |
| `generar_targets_hidricos_regresion.py` | `backend/scripts/pipeline/generar_targets_hidricos_regresion.py` |
| `entrenar_predictores_hidricos_regresion.py` | `backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py` |
| `generar_ranking_hidrico.py` | `backend/scripts/pipeline/generar_ranking_hidrico.py` |
| `app/main.py` | `backend/app/main.py` |
| `schema_postgis.sql` | `backend/sql/schema_postgis.sql` |
| `streamlit_app.py` | `streamlit_app.py` |

## 1. Seleccion De La Ultima Imagen Sentinel Valida

Fuente: `backend/scripts/pipeline/run_pipeline_hidrico.py`, lineas 208-225.

```python
for offset in range(0, args.latest_lookback_days + 1):
    candidate_end = end - timedelta(days=offset)
    candidate_start = candidate_end - timedelta(days=args.extract_window_days)
    coleccion = obtener_imagenes_sentinel(
        region,
        candidate_start.isoformat(),
        candidate_end.isoformat(),
        umbral_nubosidad=args.extract_cloud_threshold,
    )
    image_count = int(coleccion.size().getInfo())
    log(
        "Latest Sentinel candidato: "
        f"{candidate_start.isoformat()} -> {candidate_end.isoformat()} "
        f"imagenes={image_count}",
        log_path,
    )
    if image_count >= args.latest_min_images:
        return candidate_end.isoformat()
```

Decision metodologica:

El pipeline no asume que la fecha actual tiene una imagen Sentinel-2 util. En
lugar de usar "hoy", busca hacia atras la ultima ventana con imagenes validas.
Esto es necesario porque Sentinel-2 tiene revisita aproximada de 5 dias, pero
la disponibilidad real depende de nubosidad, cobertura y calidad de pixeles.

Por que no otra alternativa:

Usar siempre la fecha actual podria generar rankings sobre fechas sin imagenes,
o forzar datos incompletos. Buscar la ultima ventana valida hace que el sistema
sea mas robusto y reproducible.

## 2. Evitar Recalcular Si No Hay Nueva Fecha

Fuente: `backend/scripts/pipeline/run_pipeline_hidrico.py`, lineas 725-746.

```python
if (
    args.update_sentinel
    and args.skip_if_no_new_date
    and fecha_antes is not None
    and fecha_despues == fecha_antes
):
    state = {
        "mode": args.mode,
        "last_run_utc": utc_now(),
        "input_temporal": args.input,
        "fecha_dataset": fecha_despues,
        "fecha_dataset_antes": fecha_antes,
        "fecha_dataset_despues": fecha_despues,
        "log_path": str(log_path),
        "update_sentinel": args.update_sentinel,
        "load_postgis": args.load_postgis,
        "skipped": True,
        "reason": "sin_fecha_nueva",
    }
```

Decision metodologica:

El sistema registra la ejecucion aunque no haya datos nuevos, pero evita
regenerar rankings identicos. Esto permite automatizar el pipeline diariamente
sin duplicar resultados ni sobreescribir salidas innecesariamente.

Por que no otra alternativa:

Recalcular siempre aumentaria costo, ruido operativo y riesgo de inconsistencias
sin aportar informacion nueva. Omitir la corrida sin registrar estado impediria
auditar si el sistema se ejecuto.

## 3. Extraccion De Indices Por Parcela En Google Earth Engine

Fuente: `backend/scripts/pipeline/generar_dataset_temporal_hidrico.py`,
lineas 320-347.

```python
imagen = calcular_indices(obtener_imagen_compuesta(coleccion, region))
bandas = imagen.bandNames().getInfo()
resultados = []

for start in range(0, len(muestra), chunk_size):
    end = min(start + chunk_size, len(muestra))
    chunk = muestra.iloc[start:end]
    fc = feature_collection_from_gdf(chunk)

    reducido = imagen.select(bandas).reduceRegions(
        collection=fc,
        reducer=reducer_estadisticas(),
        scale=10,
        tileScale=4,
    )
```

Decision metodologica:

La extraccion se realiza por ventanas temporales y por lotes de parcelas. Google
Earth Engine calcula los indices y reduce estadisticamente la imagen por
geometria de parcela.

Por que no otra alternativa:

Descargar rasters completos y procesarlos localmente seria mas pesado y menos
escalable. `reduceRegions` permite mantener el procesamiento principal del lado
de GEE y guardar solo estadisticas tabulares por parcela.

## 4. Construccion Del Score Hidrico Relativo

Fuente: `backend/scripts/pipeline/generar_targets_hidricos_regresion.py`,
lineas 45-65.

```python
def agregar_riesgo_hidrico(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    parts = []

    for _, group in df.groupby(["cultivo", "fecha"], sort=False):
        riesgo = (
            0.35 * robust_percentile(group["ndmi_mean"], high_is_risk=False)
            + 0.30 * robust_percentile(group["msi_mean"], high_is_risk=True)
            + 0.15 * robust_percentile(group["ndwi_mean"], high_is_risk=False)
            + 0.10 * robust_percentile(group["nbr_mean"], high_is_risk=False)
            + 0.10 * robust_percentile(group["ndvi_mean"], high_is_risk=False)
        )
        item = group.copy()
        item["riesgo_hidrico"] = (100 * riesgo).clip(0, 100)
```

Decision metodologica:

El riesgo hidrico se define como un score relativo dentro del mismo cultivo y
fecha. Combina indices sensibles a agua, sequedad y vigor: NDMI, MSI, NDWI, NBR
y NDVI.

Por que no otra alternativa:

No se dispone de mediciones de campo directas de estres hidrico. Por eso no se
entrena un modelo supervisado contra una variable fisiologica medida. El score
por percentiles permite comparar parcelas en un mismo contexto temporal y
agronomico sin asumir una escala absoluta universal.

## 5. Creacion De Pares Temporales X(t) -> Y(t+h)

Fuente: `backend/scripts/pipeline/generar_targets_hidricos_regresion.py`,
lineas 142-163.

```python
def crear_pares(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    df = preparar_observaciones(df)
    future_cols = [
        "riesgo_hidrico",
        "ndmi_mean", "msi_mean", "ndwi_mean", "nbr_mean", "ndvi_mean",
    ]

    pairs = []
    for horizon in horizons:
        future = df[["parcela_id", "fecha"] + future_cols].copy()
        future["fecha"] = future["fecha"] - pd.to_timedelta(horizon, unit="D")
        future = future.rename(columns={col: f"{col}_future" for col in future_cols})

        merged = df.merge(future, on=["parcela_id", "fecha"], how="inner")
        merged["horizon_days"] = horizon
        pairs.append(merged)

```

Decision metodologica:

El problema predictivo se formula como regresion temporal: variables observadas
en `t` para estimar el estado en `t+h`, con horizontes de 5 y 10 dias.

Por que no otra alternativa:

Una clasificacion binaria de "estres/no estres" perderia informacion sobre
gradientes de deterioro. La regresion conserva la escala continua del score y
permite ordenar parcelas por severidad esperada.

## 6. Seleccion De Features Sin Fuga De Informacion

Fuente: `backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py`,
lineas 39-56.

```python
def feature_columns(df: pd.DataFrame, targets: list[str]) -> list[str]:
    excluded = {
        "parcela_id", "cultivo", "fecha", "fecha_fin",
        "year", "month", "day_of_year",
    }
    excluded.update(targets)
    excluded_prefixes = ("delta_", "scl_")
    excluded_suffixes = ("_future",)

    features = []
    for col in df.select_dtypes(include=[np.number]).columns:
        if col in excluded:
            continue
        if col.startswith(excluded_prefixes) or col.endswith(excluded_suffixes):
            continue
        features.append(col)

    return features
```

Decision metodologica:

El entrenamiento excluye identificadores, fechas directas, targets futuros,
deltas futuros y variables `SCL`. Esto evita fuga de informacion y reduce la
posibilidad de que el modelo aprenda artefactos de calidad de escena en lugar
de senales agronomicas.

Por que no otra alternativa:

Incluir columnas futuras o deltas calculados con valores futuros inflaria
artificialmente las metricas. Incluir `SCL` podria hacer que el modelo aprenda
condiciones de captura o mascara de escena, no dinamica hidrica.

## 7. Modelo De Regresion XGBoost

Fuente: `backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py`,
lineas 59-72.

```python
def crear_modelo() -> XGBRegressor:
    return XGBRegressor(
        objective="reg:squarederror",
        n_estimators=450,
        max_depth=4,
        learning_rate=0.035,
        subsample=0.9,
        colsample_bytree=0.85,
        gamma=0.05,
        min_child_weight=2,
        reg_lambda=1.5,
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
```

Decision metodologica:

Se usa XGBoost Regressor para modelar relaciones no lineales entre indices
espectrales, historial, tendencias y riesgo futuro.

Por que no otra alternativa:

Un modelo lineal seria mas interpretable, pero podria subrepresentar
interacciones espectrales y fenologicas. XGBoost ofrece buen desempeno en datos
tabulares, regularizacion y tiempos razonables para el tamano del dataset.

## 8. Validacion Temporal Y Metricas De Ranking

Fuente: `backend/scripts/experiments/entrenar_predictores_hidricos_regresion.py`,
lineas 82-113.

```python
def split_temporal(df: pd.DataFrame, test_size: float) -> tuple[np.ndarray, np.ndarray]:
    fechas = np.array(sorted(pd.to_datetime(df["fecha"]).unique()))
    cutoff_idx = max(1, int(len(fechas) * (1 - test_size)))
    cutoff = fechas[cutoff_idx]
    fechas_df = pd.to_datetime(df["fecha"]).values
    train_idx = np.flatnonzero(fechas_df < cutoff)
    test_idx = np.flatnonzero(fechas_df >= cutoff)

    if len(train_idx) == 0 or len(test_idx) == 0:
        raise RuntimeError("Split temporal vacio; revisar rango de fechas.")

    return train_idx, test_idx


def top_decile_overlap(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    n = max(1, int(np.ceil(len(y_true) * 0.10)))
    true_top = set(np.argsort(y_true)[-n:])
    pred_top = set(np.argsort(y_pred)[-n:])
    return len(true_top & pred_top) / n
```

Decision metodologica:

La validacion separa fechas pasadas para entrenamiento y fechas posteriores
para prueba. Ademas de metricas de error, se mide coincidencia del 10% mas
critico.

Por que no otra alternativa:

Un split aleatorio por filas podria mezclar fechas cercanas en train y test,
generando una evaluacion demasiado optimista. Como el producto busca priorizar
parcelas, Top10 overlap es mas informativo que accuracy.

## 9. Ranking Con Pesos Configurables

Fuente: `backend/scripts/pipeline/generar_ranking_hidrico.py`, lineas 231-249.

```python
def asignar_prioridad(row: pd.Series, thresholds: dict) -> str:
    score = row["prioridad_score"]

    if score >= thresholds["critica"]:
        return "critica"
    if score >= thresholds["alta"]:
        return "alta"
    if score >= thresholds["media"]:
        return "media"
    return "baja"


def score_prioridad(df: pd.DataFrame, weights: dict) -> pd.Series:
    return (
        weights["riesgo_pred_10d"] * df["riesgo_pred_10d"]
        + weights["riesgo_pred_5d"] * df["riesgo_pred_5d"]
        + weights["delta_10d_pos"] * df["delta_10d"].clip(lower=0)
        + weights["delta_5d_pos"] * df["delta_5d"].clip(lower=0)
        + weights["riesgo_actual"] * df["riesgo_hidrico"]
```

Decision metodologica:

El ranking no depende solo del estado actual: combina riesgo futuro y deterioro
positivo esperado. Los pesos y umbrales se cargan desde configuracion externa,
lo que permite calibrar el criterio sin modificar codigo.

Por que no otra alternativa:

Ordenar solo por riesgo actual ignoraria parcelas que todavia no estan en
estado critico pero se proyectan en deterioro. Usar pesos configurables permite
ajustar el criterio de priorizacion a partir de validacion historica.

## 10. Proyeccion Operativa Conservadora Para Productor

Fuente: `backend/scripts/pipeline/generar_ranking_hidrico.py`, lineas 279-294.

```python
ranking["riesgo_operativo_5d"] = np.maximum.reduce(
    [
        actual,
        ranking["riesgo_pred_5d"],
        actual + ranking["pendiente_operativa_5d"],
    ]
).clip(0, 100)
ranking["riesgo_operativo_10d"] = np.maximum.reduce(
    [
        ranking["riesgo_operativo_5d"],
        ranking["riesgo_pred_10d"],
        ranking["riesgo_operativo_5d"] + ranking["pendiente_operativa_5d"],
    ]
).clip(0, 100)
ranking["delta_operativo_5d"] = ranking["riesgo_operativo_5d"] - actual
ranking["delta_operativo_10d"] = ranking["riesgo_operativo_10d"] - actual
```

Decision metodologica:

La vista productor muestra una proyeccion conservadora: el riesgo operativo no
baja respecto del estado actual. Esto separa la prediccion cruda del modelo de
la comunicacion del escenario "si la condicion no mejora".

Por que no otra alternativa:

La prediccion ML cruda puede bajar porque el historico incluye riego o lluvia
entre imagenes. Mostrar esa baja al productor podria interpretarse como mejora
garantizada. La proyeccion operativa evita comunicar recuperaciones que el
sistema no puede asegurar.

## 11. Control De Acceso Por Rol En La API

Fuente: `backend/app/main.py`, lineas 142-159.

```python
def require_roles(*roles: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["rol"] not in roles:
            raise HTTPException(status_code=403, detail="Rol no autorizado.")
        return user

    return dependency


def require_cliente_or_admin(
    cliente_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    if user["rol"] == "admin":
        return user
    if user["rol"] == "productor" and user.get("cliente_id") == cliente_id:
        return user
    raise HTTPException(status_code=403, detail="Productor no autorizado.")
```

Decision metodologica:

La restriccion de acceso se aplica en backend, no solo en el dashboard. El admin
puede consultar todo; el productor solo accede a la cartera de parcelas
asociada a su usuario.

Por que no otra alternativa:

Filtrar solamente en el frontend seria inseguro: el usuario podria consultar la
API directamente. La regla debe vivir en FastAPI para que el control de acceso
sea independiente de la interfaz.

## 12. GeoJSON Optimizado Para Mapa Admin

Fuente: `backend/app/main.py`, lineas 197-204.

```python
@app.get("/rankings/latest/geojson")
def get_latest_ranking_geojson(
    simplify_meters: float | None = Query(default=None, ge=0, le=20),
    _user: dict[str, Any] = Depends(require_roles("admin")),
) -> dict:
    try:
        return latest_geojson(simplify_meters=simplify_meters)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
```

Decision metodologica:

El endpoint permite pedir geometria simplificada para visualizacion. Esto
reduce el peso del GeoJSON cuando el admin carga miles de parcelas.

Por que no otra alternativa:

Enviar siempre la geometria completa hace mas lenta la visualizacion. Simplificar
solo en la respuesta mantiene intacta la geometria persistida en PostGIS y no
afecta el calculo de modelos.

## 13. Modelo Geoespacial De Parcelas En PostGIS

Fuente: `backend/sql/schema_postgis.sql`, lineas 3-12.

```sql
CREATE TABLE IF NOT EXISTS parcelas (
    parcela_id bigint PRIMARY KEY,
    cultivo_oficial text NOT NULL,
    cultivo_original text,
    area_m2 double precision,
    fuente text DEFAULT 'idemendoza',
    globalid text,
    activo boolean NOT NULL DEFAULT true,
    updated_at timestamptz DEFAULT now(),
    geom geometry(MultiPolygon, 4326) NOT NULL
);
```

Decision metodologica:

Las parcelas se almacenan en PostGIS con geometria `MultiPolygon` en EPSG:4326,
etiqueta oficial, cultivo original y estado activo.

Por que no otra alternativa:

Guardar geometria como texto o GeoJSON plano dificultaria consultas espaciales,
indices y cruces regionales. PostGIS permite mantener integridad espacial y
consultas geograficas reproducibles.

## 14. Vista Latest Con Geometria Para El Mapa

Fuente: `backend/sql/schema_postgis.sql`, lineas 140-157.

```sql
CREATE OR REPLACE VIEW ranking_hidrico_latest AS
SELECT r.*
FROM ranking_hidrico r
WHERE r.fecha_ranking = (
    SELECT max(fecha_ranking)
    FROM ranking_hidrico
);

CREATE OR REPLACE VIEW ranking_hidrico_latest_geo AS
SELECT
    r.*,
    p.area_m2 AS parcela_area_m2,
    p.cultivo_oficial,
    p.geom
FROM ranking_hidrico_latest r
JOIN parcelas p
    ON p.parcela_id = r.parcela_id
WHERE p.activo = true;
```

Decision metodologica:

La vista `latest` separa la persistencia historica del ranking operativo que
consume el dashboard. La vista geoespacial une ranking y geometria activa.

Por que no otra alternativa:

Sobrescribir una unica tabla `latest` haria perder historico. Consultar siempre
manualmente la ultima fecha en la aplicacion duplicaria logica. La vista
centraliza esa regla en la base.

## 15. Usuarios Y Relacion Productor-Parcela

Fuente: `backend/sql/schema_postgis.sql`, lineas 169-182 y 218-224.

```sql
CREATE TABLE IF NOT EXISTS usuarios (
    usuario_id bigserial PRIMARY KEY,
    email text NOT NULL UNIQUE,
    nombre text,
    apellido text,
    dni text,
    rol text NOT NULL CHECK (rol IN ('admin', 'regional', 'productor')),
    cliente_id bigint REFERENCES clientes(cliente_id),
    password_hash text,
    activo boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
```

La relacion productor-parcela se persiste en otra tabla:

```sql
CREATE TABLE IF NOT EXISTS cliente_parcela (
    cliente_id bigint NOT NULL REFERENCES clientes(cliente_id) ON DELETE CASCADE,
    parcela_id bigint NOT NULL REFERENCES parcelas(parcela_id) ON DELETE CASCADE,
    etiqueta text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (cliente_id, parcela_id)
);

CREATE INDEX IF NOT EXISTS idx_cliente_parcela_parcela
    ON cliente_parcela (parcela_id);
```

Decision metodologica:

El sistema modela usuarios con rol y una relacion explicita entre productor y
parcelas. Aunque el nombre tecnico conserve `cliente_id`, en producto se
interpreta como cartera de parcelas del productor.

Por que no otra alternativa:

Asociar parcelas solo desde el frontend seria fragil. Persistir la relacion en
PostGIS permite filtrar desde backend, auditar asignaciones y mantener
consistencia entre API y dashboard.

## 16. Entrypoint Minimo Del Dashboard

Fuente: `streamlit_app.py`, lineas 1-9.

```python
from frontend.views.dashboard import render_dashboard


def main() -> None:
    render_dashboard()


if __name__ == "__main__":
    main()
```

Decision metodologica:

El archivo principal de Streamlit queda deliberadamente minimo y delega la
composicion a modulos del paquete `frontend`.

Por que no otra alternativa:

Mantener toda la interfaz en `streamlit_app.py` dificultaria mantenimiento,
tests y lectura. Separar entrada, componentes, logica y vistas permite explicar
mejor la arquitectura y evolucionar el dashboard sin mezclar responsabilidades.

## Recomendacion De Uso En La Tesis

Para el marco metodologico conviene seleccionar entre 6 y 8 fragmentos, no
incluirlos todos. Una seleccion equilibrada seria:

1. ultima imagen Sentinel valida;
2. extraccion GEE por parcela;
3. score hidrico relativo;
4. pares temporales `X(t) -> Y(t+h)`;
5. exclusion de features con fuga;
6. XGBoost Regressor;
7. ranking con pesos;
8. PostGIS latest geo o control de acceso por rol.

Los demas fragmentos pueden quedar como respaldo para anexos o defensa oral.
