# Futuro Del Proyecto

Este documento deja constancia del camino pendiente para convertir el prototipo
actual en un producto sólido de monitoreo de estrés hídrico para San Rafael,
Mendoza.

## Estado Actual

El proyecto ya cuenta con:

- pipeline operativo local/cloud para generar ranking hídrico;
- extracción Sentinel-2/GEE sobre parcelas de vid y olivo;
- modelos de regresión separados para vid y olivo;
- ranking actual y proyección operativa a 5 y 10 días;
- API FastAPI con PostGIS y fallback local;
- dashboard Streamlit con roles `admin`, `regional` y `productor`;
- vista regional por UM;
- CRUD inicial de usuarios;
- activación de parcelas disponibles para incorporarlas al universo operativo;
- PostGIS local y schema geoespacial versionado;
- smoke tests y tests unitarios básicos.

La estructura interna todavía conserva nombres como `clientes` y `cliente_id`
para representar la relación productor/campo-parcela. A nivel de producto, la
nomenclatura vigente es `productor`.

## Objetivo De Producción

El sistema final debe ejecutar automáticamente el flujo cuando haya una imagen
Sentinel-2 válida nueva, actualizar rankings y exponerlos según rol:

- `admin`: operación completa, auditorías, usuarios, parcelas y datos técnicos;
- `regional`: prioridad agregada por UM/zona;
- `productor`: solo parcelas asociadas a su campo.

El producto debe mostrar detección y proyección de estrés hídrico. No debe
recomendar riego de forma prescriptiva; debe aportar información para que el
productor o autoridad regional tome la decisión con su criterio.

## Camino Técnico Pendiente

### 1. Automatización Cloud

Pendiente:

- desplegar PostGIS, API y dashboard en la cloud UM;
- definir variables `.env` productivas;
- configurar ejecución programada del pipeline;
- usar `--skip-if-no-new-date` para evitar reprocesos innecesarios;
- guardar logs por corrida y estado final del pipeline;
- dejar health checks simples para API, DB y dashboard.

Criterio de listo:

```text
Una corrida automática detecta última imagen válida, actualiza PostGIS y el
dashboard muestra el nuevo ranking sin intervención manual.
```

### 2. Robustez Del Pipeline Sentinel-2

Pendiente:

- confirmar que siempre se usa la última fecha válida, no la fecha actual;
- mantener ventanas hacia atrás con peso decreciente;
- persistir metadatos de imagen usada: fecha, nubosidad, cantidad de píxeles,
  cobertura válida y fuente;
- auditar parcelas sin ranking después de cada corrida;
- separar claramente errores GEE, falta de imagen y geometrías problemáticas.

Criterio de listo:

```text
Cada parcela queda clasificada como evaluada, sin imagen válida, sin píxeles
suficientes o problema geométrico.
```

### 3. Calidad Del Ranking

Pendiente:

- seguir acumulando historial temporal por parcela;
- validar outliers espaciales con ventanas temporales recientes;
- exponer `confianza_lectura` al admin sin contaminar la vista productor;
- revisar parcelas pequeñas, empezando por umbral operativo de 4000 m2;
- decidir si algunas lecturas deben bajar confianza, no modificar score;
- evaluar calibración separada por cultivo y estación.

Criterio de listo:

```text
El score conserva la lectura satelital, pero cada ranking tiene confianza y
motivo técnico trazable para auditoría.
```

### 4. Proyección Operativa

Pendiente:

- diferenciar claramente predicción aprendida vs proyección sin riego;
- incorporar tendencia reciente de la parcela;
- mantener factor estacional por cultivo;
- evaluar clima futuro cuando esté disponible: temperatura, lluvia y demanda
  atmosférica;
- documentar que la proyección muestra deterioro esperado bajo continuidad de
  condiciones, no certeza agronómica.

Criterio de listo:

```text
La vista productor muestra riesgo actual y evolución esperada de forma coherente
con tendencia, cultivo y estación.
```

### 5. PostGIS Y Modelo De Datos

Pendiente:

- decidir si renombrar `clientes` a `productores` o mantener compatibilidad;
- agregar migraciones incrementales en vez de depender solo de schema completo;
- normalizar tablas de usuarios, productores/campos y relaciones parcela-campo;
- agregar índices para consultas frecuentes del dashboard;
- persistir snapshots históricos de ranking y no solo latest.

Criterio de listo:

```text
La base permite consultar ranking latest, histórico por fecha, parcelas por
productor y agregados regionales con tiempos razonables.
```

### 6. Seguridad Y Roles

Pendiente:

- reemplazar accesos demo por usuarios reales en producción;
- definir política de contraseñas;
- agregar cambio de contraseña;
- agregar desactivación segura de usuarios;
- revisar expiración del token y secreto `AUTH_SECRET`;
- limitar endpoints admin desde el frontend y backend;
- evitar exponer datos técnicos en roles productor/regional.

Criterio de listo:

```text
Un productor no puede consultar parcelas ajenas aunque manipule la URL o el
frontend.
```

### 7. Dashboard

Pendiente:

- separar más componentes Streamlit para reducir acoplamiento;
- mejorar la vista productor: foco en mapa, evolución y detalle de parcela;
- mejorar la vista regional: ranking por UM, filtros por cultivo y comparación;
- mantener la vista admin como herramienta técnica;
- agregar estados de carga, errores y mensajes operativos claros;
- optimizar carga del mapa admin con límites, clustering o simplificación.

Criterio de listo:

```text
Cada rol ve solo información útil para su decisión, sin filtros técnicos
innecesarios.
```

### 8. Validación Y QA

Pendiente:

- ampliar tests de API con permisos por rol;
- agregar tests para CRUD usuarios;
- agregar tests de consultas PostGIS si la DB está disponible;
- agregar smoke test cloud;
- validar que el dashboard no falle con columnas faltantes;
- registrar métricas de cobertura y performance por corrida.

Criterio de listo:

```text
Antes de desplegar se ejecutan tests unitarios, smoke API/PostGIS y una corrida
pipeline controlada.
```

### 9. Datos Reales Y Validación Agronómica

Pendiente:

- comparar casos seleccionados con conocimiento de campo;
- revisar si saltos fuertes entre parcelas vecinas son manejo real o ruido;
- validar estaciones críticas por cultivo;
- incorporar datos de riego o turnos cuando estén disponibles;
- incorporar clima cuando el flujo base esté estabilizado.

Criterio de listo:

```text
El sistema puede explicar por qué una parcela aparece con riesgo alto y cuándo
esa lectura debe tratarse con baja confianza.
```

## Orden Recomendado

1. Congelar estructura actual y documentar comandos de operación.
2. Completar tests de permisos y CRUD usuarios.
3. Ejecutar una corrida pipeline completa latest con PostGIS local.
4. Auditar cobertura, sin ranking y outliers de esa corrida.
5. Ajustar dashboard por rol con datos reales de la última corrida.
6. Preparar despliegue en cloud UM.
7. Automatizar corrida programada.
8. Agregar monitoreo/logs.
9. Validar con casos de campo.
10. Recién después incorporar clima y turnos de riego.

## Riesgos Principales

- confundir proyección de estrés con recomendación de riego;
- suavizar scores reales por asumir que los outliers son ruido;
- dejar demasiados datos técnicos en vistas no admin;
- depender de una imagen Sentinel-2 puntual con nubes o baja cobertura;
- no guardar suficiente histórico para explicar cambios de ranking;
- mezclar nombres internos `cliente_id` con concepto de producto `productor`.

## Decisión Actual

Para la próxima etapa conviene priorizar calidad y confiabilidad sobre nuevas
funciones. El sistema debe volverse repetible, auditable y claro antes de sumar
clima, turnos de riego o reglas regionales más complejas.
