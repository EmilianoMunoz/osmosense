# Diagramas Del Sistema

Este documento contiene diagramas en formato Mermaid para explicar la
arquitectura, el pipeline, la base de datos y las vistas del sistema. Estan
pensados como insumo para la tesis y para documentacion tecnica.

Los diagramas reflejan el flujo operativo actual:

- PostGIS es la fuente productiva.
- Los CSV/GeoJSON locales quedan solo como fallback de desarrollo.
- La clasificacion queda como soporte metodologico/experimental.
- El producto operativo se concentra en riesgo hidrico para vid y olivo.

## 1. Arquitectura General

```mermaid
flowchart LR
    subgraph Fuentes["Fuentes de datos"]
        S2["Sentinel-2 SR Harmonized"]
        IDE["Parcelas oficiales IDEMendoza"]
        LIM["Limite San Rafael GeoJSON"]
        UM["Zonificacion DGI / UM"]
    end

    subgraph Procesamiento["Procesamiento satelital y ML"]
        GEE["Google Earth Engine"]
        PIPE["Pipeline hidrico<br/>run_pipeline_hidrico.py"]
        MOD["Modelos de regresion<br/>vid y olivo"]
        RANK["Ranking hidrico<br/>actual, 5 dias, 10 dias"]
    end

    subgraph Persistencia["Persistencia operativa"]
        PG["PostGIS"]
        ART["Artefactos locales<br/>CSV/GeoJSON de desarrollo"]
        LOG["Logs y estado<br/>pipeline_hidrico_state.json"]
    end

    subgraph Aplicacion["Aplicacion"]
        API["FastAPI"]
        WEB["Dashboard Streamlit"]
    end

    subgraph Roles["Usuarios"]
        ADMIN["Admin"]
        PROD["Productor"]
        REG["Regional"]
    end

    S2 --> GEE
    IDE --> PG
    LIM --> GEE
    UM --> PG
    GEE --> PIPE
    PG --> PIPE
    MOD --> PIPE
    PIPE --> RANK
    PIPE --> PG
    PIPE --> ART
    PIPE --> LOG
    PG --> API
    API --> WEB
    WEB --> ADMIN
    WEB --> PROD
    WEB --> REG
```

Lectura metodologica: Google Earth Engine concentra el procesamiento
multiespectral pesado, mientras que UM-Cloud/PostGIS conserva el estado
operativo. La API desacopla el almacenamiento geoespacial del dashboard.

## 2. Pipeline Operativo

```mermaid
flowchart TD
    A["Disparador programado<br/>cron o systemd timer"] --> B["run_pipeline_hidrico.py"]
    B --> C["Buscar ultima imagen Sentinel-2 valida"]
    C --> D{Hay fecha nueva<br/>respecto al ranking latest?}
    D -- No --> E["Registrar estado<br/>sin actualizacion"]
    E --> F["Mantener ranking vigente"]

    D -- Si --> G["Extraer indices por parcela<br/>GEE reduceRegions"]
    G --> H["Actualizar dataset temporal"]
    H --> I["Generar targets o features<br/>segun flujo requerido"]
    I --> J["Aplicar modelos hidricos<br/>vid y olivo"]
    J --> K["Calcular score, proyecciones<br/>y ranking"]
    K --> L["Auditar calidad<br/>vecinos, outliers, cobertura"]
    L --> M["Cargar ranking y observaciones<br/>en PostGIS"]
    M --> N["Actualizar vistas latest<br/>API y dashboard"]
    N --> O["Persistir logs y estado"]
```

Decision clave: el pipeline no asume que "hoy" tiene imagen valida. Busca la
ultima observacion Sentinel-2 util y solo recalcula si existe una fecha nueva.
Esto evita reescribir rankings con datos repetidos o de mala calidad.

## 3. Flujo De Datos Sentinel-2

```mermaid
sequenceDiagram
    participant Timer as Cron/Systemd
    participant Pipeline as Pipeline hidrico
    participant GEE as Google Earth Engine
    participant PG as PostGIS
    participant API as FastAPI
    participant UI as Streamlit

    Timer->>Pipeline: Ejecutar corrida programada
    Pipeline->>PG: Leer parcelas activas vid/olivo
    Pipeline->>GEE: Consultar ventanas Sentinel-2 recientes
    GEE-->>Pipeline: Indices por parcela y fecha valida
    Pipeline->>Pipeline: Calcular score y predicciones
    Pipeline->>PG: Insertar observaciones y ranking
    Pipeline->>PG: Actualizar ranking latest
    UI->>API: Solicitar GeoJSON latest
    API->>PG: Leer ranking_hidrico_latest_geo
    PG-->>API: Features con geometria y metricas
    API-->>UI: GeoJSON operativo
```

Uso en tesis: este diagrama muestra la separacion entre procesamiento remoto
en GEE, persistencia geoespacial en PostGIS y visualizacion en el dashboard.

## 4. Modelo De Datos PostGIS

```mermaid
erDiagram
    USUARIOS {
        int usuario_id PK
        string email
        string password_hash
        string rol
        int cliente_id FK
        boolean activo
    }

    CLIENTES {
        int cliente_id PK
        string nombre
        string tipo
        boolean activo
    }

    CLIENTE_PARCELA {
        int cliente_id FK
        int parcela_id FK
        string etiqueta
    }

    PARCELAS {
        int parcela_id PK
        string cultivo_oficial
        string cultivo_original
        float area_m2
        geometry geom
        boolean activo
    }

    OBSERVACIONES_SENTINEL {
        int observacion_id PK
        int parcela_id FK
        date fecha
        float ndvi_mean
        float ndmi_mean
        float msi_mean
        float nbr_mean
    }

    RANKING_HIDRICO {
        int ranking_id PK
        int parcela_id FK
        date fecha_ranking
        string cultivo
        float riesgo_actual
        float riesgo_operativo_5d
        float riesgo_operativo_10d
        string prioridad
    }

    RANKING_HIDRICO_LATEST {
        int parcela_id FK
        date fecha_ranking
        float riesgo_actual
        string prioridad
    }

    ZONAS_UM {
        int um_id PK
        string nombre
        geometry geom
    }

    PARCELA_UM {
        int parcela_id FK
        int um_id FK
        float intersection_m2
    }

    RANKING_UM {
        int um_id FK
        date fecha_ranking
        float prioridad_score_prom_pond
        float pct_alta_critica
    }

    CLIENTES ||--o{ USUARIOS : "tiene usuarios productores"
    CLIENTES ||--o{ CLIENTE_PARCELA : "agrupa parcelas"
    PARCELAS ||--o{ CLIENTE_PARCELA : "se asigna a"
    PARCELAS ||--o{ OBSERVACIONES_SENTINEL : "genera observaciones"
    PARCELAS ||--o{ RANKING_HIDRICO : "recibe ranking"
    PARCELAS ||--o| RANKING_HIDRICO_LATEST : "ultimo estado"
    PARCELAS ||--o{ PARCELA_UM : "intersecta"
    ZONAS_UM ||--o{ PARCELA_UM : "contiene"
    ZONAS_UM ||--o{ RANKING_UM : "agrega riesgo"
```

Nota: `clientes` y `cliente_parcela` conservan nombres legacy internos. En la
interfaz se presentan como productores y parcelas asignadas.

## 5. Autenticacion Y Permisos

```mermaid
sequenceDiagram
    participant User as Usuario
    participant UI as Streamlit
    participant API as FastAPI
    participant Auth as Servicio auth
    participant PG as PostGIS

    User->>UI: Ingresa email y password
    UI->>API: POST /auth/login
    API->>Auth: authenticate_user(email, password)
    Auth->>PG: Buscar usuario activo
    PG-->>Auth: usuario, rol, password_hash
    Auth->>Auth: Verificar PBKDF2-SHA256
    Auth->>Auth: Firmar token HMAC-SHA256
    Auth-->>API: access_token + rol
    API-->>UI: Sesion autenticada
    UI->>API: Requests con Authorization Bearer
    API->>API: Validar token y rol
    API-->>UI: Datos permitidos por rol
```

Reglas vigentes:

- `admin`: acceso a ranking global, gestion de usuarios, productores y parcelas.
- `productor`: acceso solo a parcelas asociadas a su cartera interna.
- `regional`: acceso a agregados por UM y ranking regional.

En produccion, `AUTH_SECRET` es obligatorio. Si falta, la API no debe firmar ni
validar tokens con un secreto de desarrollo.

## 6. Navegacion Del Dashboard

```mermaid
flowchart TD
    LOGIN["Login"] --> ROLE{Rol autenticado}

    ROLE -- admin --> ADMIN["Vista Admin"]
    ROLE -- productor --> PROD["Vista Productor"]
    ROLE -- regional --> REG["Vista Regional"]

    ADMIN --> A1["Analisis"]
    ADMIN --> A2["Gestion"]
    A1 --> A11["Estado"]
    A1 --> A12["Mapa operativo"]
    A1 --> A13["Datos"]
    A1 --> A14["Cobertura"]
    A1 --> A15["Revision tecnica"]
    A2 --> A21["Productores y parcelas"]
    A2 --> A22["Usuarios"]
    A2 --> A23["Parcelas disponibles"]

    PROD --> P1["Mapa"]
    PROD --> P2["Resumen"]
    PROD --> P3["Parcelas"]
    P1 --> P11["Slider actual, 5 dias, 10 dias"]
    P1 --> P12["Detalle simple de parcela"]
    P2 --> P21["Lectura comparativa del campo"]

    REG --> R1["Mapa regional"]
    REG --> R2["Foco regional"]
    REG --> R3["Ranking UM"]
    REG --> R4["Parcelas de la UM"]
```

Decision de diseño: la vista Admin separa analisis y gestion para evitar una
pantalla inicial demasiado pesada. La vista Productor evita graficos tecnicos y
prioriza mensajes interpretables.

## 7. Modelo Predictivo Y Ranking

```mermaid
flowchart LR
    A["Serie temporal por parcela<br/>indices Sentinel-2"] --> B["Features hidricas"]
    B --> C["Score hidrico actual"]
    B --> D{Cultivo}
    D -- vid --> E["Modelo regresion vid<br/>horizontes 5 y 10 dias"]
    D -- olivo --> F["Modelo regresion olivo<br/>horizontes 5 y 10 dias"]
    E --> G["Prediccion cruda"]
    F --> G
    C --> H["Ajuste operativo<br/>sin riego, estacionalidad, tendencia"]
    G --> H
    H --> I["Riesgo operativo 5d y 10d"]
    I --> J["Ranking por parcela"]
    J --> K["Ranking por cultivo"]
    J --> L["Agregado regional por UM"]
```

Interpretacion: los modelos aprenden la evolucion historica observada, pero la
visualizacion operativa usa una proyeccion ajustada para representar el
escenario de desmejora si la parcela no recibe intervencion.

## 8. Flujo Productor-Parcela

```mermaid
flowchart TD
    A["Admin abre Gestion"] --> B["Selecciona productor"]
    B --> C["Consulta parcelas analizadas sin productor activo"]
    C --> D["Mapa de asignacion"]
    D --> E["Selecciona una o varias parcelas"]
    E --> F["Opcional: etiqueta visible"]
    F --> G["Crear relacion productor-parcela"]
    G --> H["PostGIS: cliente_parcela"]
    H --> I["Productor inicia sesion"]
    I --> J["Dashboard filtra solo sus parcelas"]
```

Este flujo permite incorporar parcelas ya analizadas a la cartera de un
productor sin modificar el ranking global ni recalcular inmediatamente el
modelo.

## 9. Produccion Vs Desarrollo

```mermaid
flowchart TD
    A{APP_ENV}
    A -- development --> B["Permite fallback local<br/>CSV/GeoJSON"]
    A -- development --> C["Permite accesos rapidos<br/>contra usuarios PostGIS"]
    A -- production --> D["DATABASE_URL obligatorio"]
    A -- production --> E["AUTH_SECRET obligatorio"]
    A -- production --> F["Fallback local deshabilitado"]
    A -- production --> G["Accesos rapidos deshabilitados"]

    D --> H["API lee PostGIS"]
    F --> H
    H --> I["Dashboard muestra solo datos operativos"]
```

Esta separacion evita que el sistema productivo oculte una caida de API/PostGIS
mostrando artefactos locales viejos.

## Exportacion

Opciones practicas para usar estos diagramas en la tesis:

1. Abrir este archivo en VSCode con preview Mermaid.
2. Copiar cada bloque en <https://mermaid.live> y exportar como PNG o SVG.
3. Usar extensiones de Markdown/Mermaid para generar imagenes desde la tesis.

Para el marco metodologico conviene usar al menos:

- Arquitectura general.
- Pipeline operativo.
- Modelo de datos PostGIS.
- Autenticacion y permisos.
- Modelo predictivo y ranking.
