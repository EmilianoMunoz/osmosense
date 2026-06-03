# Roles y clientes

> Estado: referencia histórica. El flujo actual de login y permisos está en
> `docs/postgis.md` y en `backend.app.main`. Este documento conserva el diseño
> conceptual original de roles.

## Objetivo

Separar el producto en vistas con distinto alcance de datos:

- `admin`: ve todo el sistema, auditorías y métricas técnicas.
- `productor`: ve únicamente sus parcelas asociadas.
- `regional`: verá parcelas agregadas por zona o región.

El filtrado de parcelas debe hacerse en backend/PostGIS. El dashboard no debe
recibir parcelas que el usuario no puede ver.

## Modelo de datos

Tablas agregadas al schema PostGIS:

```text
clientes
usuarios
cliente_parcela
```

Relación principal:

```text
clientes.cliente_id -> cliente_parcela.cliente_id
parcelas.parcela_id -> cliente_parcela.parcela_id
```

Por ahora `usuarios` deja preparado el vínculo para login real, pero el flujo
inicial puede operar con selección explícita de cliente en entorno local/demo.

## CSV local de carga

Clientes:

```csv
cliente_id,nombre,tipo,descripcion,activo
1,Finca Demo,particular,Cliente de prueba,true
```

Relación cliente-parcela:

```csv
cliente_id,parcela_id,etiqueta
1,38695,Lote norte
1,44094,Lote sur
```

Rutas esperadas:

```text
data/clientes/clientes.csv
data/clientes/cliente_parcela.csv
```

## Carga en PostGIS

```bash
venv/bin/python scripts/aplicar_schema_postgis.py
venv/bin/python scripts/cargar_clientes_parcelas_postgis.py
```

El script valida:

- columnas mínimas;
- `cliente_id` existentes en el CSV de clientes;
- duplicados por `(cliente_id, parcela_id)`.

La integridad contra parcelas reales la garantiza PostGIS mediante foreign key
contra `parcelas(parcela_id)`.

## API

Endpoints:

```text
GET /clientes
GET /clientes/{cliente_id}/rankings/latest/geojson
```

`/clientes/{cliente_id}/rankings/latest/geojson` devuelve solo parcelas
asociadas al cliente. Conserva también parcelas sin ranking latest para que el
usuario vea su universo completo.

## Próximo paso

Adaptar `streamlit_app.py` para:

- mantener vista admin actual;
- agregar selector local de cliente en modo demo;
- consumir `/clientes/{cliente_id}/rankings/latest/geojson`;
- ocultar auditorías técnicas en vista cliente.
