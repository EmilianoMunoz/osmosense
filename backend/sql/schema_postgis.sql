CREATE EXTENSION IF NOT EXISTS postgis;

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

ALTER TABLE parcelas
    ADD COLUMN IF NOT EXISTS activo boolean NOT NULL DEFAULT true;

ALTER TABLE parcelas
    ADD COLUMN IF NOT EXISTS cultivo_original text;

CREATE INDEX IF NOT EXISTS idx_parcelas_geom
    ON parcelas
    USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_parcelas_cultivo
    ON parcelas (cultivo_oficial);

CREATE INDEX IF NOT EXISTS idx_parcelas_cultivo_original
    ON parcelas (cultivo_original);

CREATE INDEX IF NOT EXISTS idx_parcelas_activo
    ON parcelas (activo);

CREATE TABLE IF NOT EXISTS observaciones_sentinel (
    parcela_id bigint NOT NULL REFERENCES parcelas(parcela_id),
    fecha date NOT NULL,
    fecha_fin date,
    cultivo text NOT NULL,
    area_m2 double precision,
    ndvi_mean double precision,
    ndmi_mean double precision,
    ndwi_mean double precision,
    msi_mean double precision,
    savi_mean double precision,
    ndre_mean double precision,
    gndvi_mean double precision,
    evi_mean double precision,
    bsi_mean double precision,
    nbr_mean double precision,
    mtci_mean double precision,
    ireci_mean double precision,
    b2_mean double precision,
    b3_mean double precision,
    b4_mean double precision,
    b5_mean double precision,
    b6_mean double precision,
    b7_mean double precision,
    b8_mean double precision,
    b11_mean double precision,
    b12_mean double precision,
    riesgo_hidrico double precision,
    payload jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (parcela_id, fecha)
);

CREATE INDEX IF NOT EXISTS idx_observaciones_sentinel_fecha
    ON observaciones_sentinel (fecha);

CREATE INDEX IF NOT EXISTS idx_observaciones_sentinel_cultivo_fecha
    ON observaciones_sentinel (cultivo, fecha);

CREATE TABLE IF NOT EXISTS ranking_hidrico (
    fecha_ranking date NOT NULL,
    fecha_lectura date,
    dias_desde_lectura integer,
    parcela_id bigint NOT NULL REFERENCES parcelas(parcela_id),
    cultivo text NOT NULL,
    ranking_global integer NOT NULL,
    ranking_por_cultivo integer NOT NULL,
    prioridad text NOT NULL CHECK (prioridad IN ('baja', 'media', 'alta', 'critica')),
    prioridad_score double precision NOT NULL,
    riesgo_actual double precision,
    riesgo_pred_5d double precision,
    riesgo_pred_10d double precision,
    delta_5d double precision,
    delta_10d double precision,
    riesgo_operativo_5d double precision,
    riesgo_operativo_10d double precision,
    delta_operativo_5d double precision,
    delta_operativo_10d double precision,
    tendencia_reciente_5d double precision,
    pendiente_operativa_5d double precision,
    factor_estacional double precision,
    ndmi_mean double precision,
    msi_mean double precision,
    ndwi_mean double precision,
    nbr_mean double precision,
    ndvi_mean double precision,
    model_dir text,
    ranking_config text,
    pipeline_run_id text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (fecha_ranking, parcela_id)
);

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS fecha_lectura date;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS dias_desde_lectura integer;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS riesgo_operativo_5d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS riesgo_operativo_10d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS delta_operativo_5d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS delta_operativo_10d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS tendencia_reciente_5d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS pendiente_operativa_5d double precision;

ALTER TABLE ranking_hidrico
    ADD COLUMN IF NOT EXISTS factor_estacional double precision;

CREATE INDEX IF NOT EXISTS idx_ranking_hidrico_fecha_prioridad
    ON ranking_hidrico (fecha_ranking, prioridad, ranking_global);

CREATE INDEX IF NOT EXISTS idx_ranking_hidrico_cultivo_fecha
    ON ranking_hidrico (cultivo, fecha_ranking, ranking_por_cultivo);

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

CREATE TABLE IF NOT EXISTS clientes (
    cliente_id bigserial PRIMARY KEY,
    nombre text NOT NULL,
    tipo text NOT NULL CHECK (tipo IN ('particular', 'regional')),
    descripcion text,
    activo boolean NOT NULL DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

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

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS last_login_at timestamptz;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS apellido text;

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS dni text;

ALTER TABLE usuarios
    ALTER COLUMN password_hash DROP NOT NULL;

ALTER TABLE usuarios
    DROP CONSTRAINT IF EXISTS usuarios_rol_check;

ALTER TABLE usuarios
    DROP CONSTRAINT IF EXISTS usuarios_cliente_requerido_para_cliente;

UPDATE usuarios
SET rol = CASE
    WHEN rol = 'cliente_particular' THEN 'productor'
    WHEN rol = 'cliente_regional' THEN 'regional'
    ELSE rol
END
WHERE rol IN ('cliente_particular', 'cliente_regional');

ALTER TABLE usuarios
    ADD CONSTRAINT usuarios_rol_check CHECK (
        rol IN ('admin', 'regional', 'productor')
    );

ALTER TABLE usuarios
    DROP CONSTRAINT IF EXISTS usuarios_cliente_requerido_para_cliente;

CREATE TABLE IF NOT EXISTS cliente_parcela (
    cliente_id bigint NOT NULL REFERENCES clientes(cliente_id) ON DELETE CASCADE,
    parcela_id bigint NOT NULL REFERENCES parcelas(parcela_id) ON DELETE CASCADE,
    etiqueta text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (cliente_id, parcela_id)
);

CREATE INDEX IF NOT EXISTS idx_cliente_parcela_parcela
    ON cliente_parcela (parcela_id);

CREATE INDEX IF NOT EXISTS idx_usuarios_cliente
    ON usuarios (cliente_id);

CREATE OR REPLACE VIEW cliente_ranking_hidrico_latest_geo AS
SELECT
    cp.cliente_id,
    c.nombre AS cliente_nombre,
    c.tipo AS cliente_tipo,
    cp.etiqueta AS parcela_etiqueta_cliente,
    p.parcela_id,
    p.cultivo_oficial,
    p.area_m2 AS parcela_area_m2,
    r.fecha_ranking,
    r.fecha_lectura,
    r.dias_desde_lectura,
    COALESCE(r.cultivo, p.cultivo_oficial) AS cultivo,
    r.ranking_global,
    r.ranking_por_cultivo,
    CASE
        WHEN r.ranking_global IS NULL THEN 'sin_ranking_latest'
        ELSE 'rankeada'
    END AS estado_cobertura,
    COALESCE(r.prioridad, 'sin ranking') AS prioridad,
    r.prioridad_score,
    r.riesgo_actual,
    r.riesgo_pred_5d,
    r.riesgo_pred_10d,
    r.delta_5d,
    r.delta_10d,
    r.riesgo_operativo_5d,
    r.riesgo_operativo_10d,
    r.delta_operativo_5d,
    r.delta_operativo_10d,
    r.tendencia_reciente_5d,
    r.pendiente_operativa_5d,
    r.factor_estacional,
    r.ndmi_mean,
    r.msi_mean,
    r.ndwi_mean,
    r.nbr_mean,
    r.ndvi_mean,
    p.geom
FROM cliente_parcela cp
JOIN clientes c
    ON c.cliente_id = cp.cliente_id
JOIN parcelas p
    ON p.parcela_id = cp.parcela_id
LEFT JOIN ranking_hidrico_latest r
    ON r.parcela_id = cp.parcela_id
WHERE c.activo = true
  AND p.activo = true;

CREATE TABLE IF NOT EXISTS zonas_um (
    um_id bigint PRIMARY KEY,
    um_fid bigint,
    nombre text NOT NULL,
    cuenca text,
    sup_ha_san_rafael double precision,
    pct_sup_en_san_rafael double precision,
    fuente text DEFAULT 'dgi',
    updated_at timestamptz DEFAULT now(),
    geom geometry(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zonas_um_geom
    ON zonas_um
    USING gist (geom);

CREATE INDEX IF NOT EXISTS idx_zonas_um_cuenca
    ON zonas_um (cuenca);

CREATE TABLE IF NOT EXISTS parcela_um (
    parcela_id bigint NOT NULL REFERENCES parcelas(parcela_id) ON DELETE CASCADE,
    um_id bigint NOT NULL REFERENCES zonas_um(um_id) ON DELETE CASCADE,
    intersection_m2 double precision,
    pct_parcela_en_um double precision,
    updated_at timestamptz DEFAULT now(),
    PRIMARY KEY (parcela_id)
);

CREATE INDEX IF NOT EXISTS idx_parcela_um_um
    ON parcela_um (um_id);

CREATE TABLE IF NOT EXISTS ranking_um (
    fecha_ranking date NOT NULL,
    um_id bigint NOT NULL REFERENCES zonas_um(um_id) ON DELETE CASCADE,
    ranking_um integer NOT NULL,
    prioridad_regional text NOT NULL CHECK (
        prioridad_regional IN ('baja', 'media', 'alta', 'critica', 'sin ranking')
    ),
    parcelas_total integer,
    parcelas_rankeadas integer,
    parcelas_sin_ranking integer,
    pct_parcelas_rankeadas double precision,
    area_cultivada_ha double precision,
    area_rankeada_ha double precision,
    vid_parcelas integer,
    olivo_parcelas integer,
    prioridad_score_prom_pond double precision,
    prioridad_score_mediana double precision,
    riesgo_actual_prom_pond double precision,
    riesgo_5d_prom_pond double precision,
    riesgo_10d_prom_pond double precision,
    delta_10d_prom_pond double precision,
    pct_alta_critica double precision,
    pct_critica double precision,
    pipeline_run_id text,
    created_at timestamptz DEFAULT now(),
    PRIMARY KEY (fecha_ranking, um_id)
);

CREATE INDEX IF NOT EXISTS idx_ranking_um_fecha_ranking
    ON ranking_um (fecha_ranking, ranking_um);

CREATE OR REPLACE VIEW ranking_um_latest AS
SELECT r.*
FROM ranking_um r
WHERE r.fecha_ranking = (
    SELECT max(fecha_ranking)
    FROM ranking_um
);

CREATE OR REPLACE VIEW ranking_um_latest_geo AS
SELECT
    r.*,
    z.um_fid,
    z.nombre,
    z.cuenca,
    z.sup_ha_san_rafael,
    z.pct_sup_en_san_rafael,
    z.geom
FROM ranking_um_latest r
JOIN zonas_um z
    ON z.um_id = r.um_id;
