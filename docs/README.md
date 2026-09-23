# Documentación de OSMOSENSE

Este índice organiza la documentación técnica y metodológica del proyecto. El
[README principal](../README.md) ofrece una presentación general; los documentos
de esta carpeta profundizan decisiones, evidencia y procedimientos específicos.

## Tesis y visión general

- [Contexto de tesis](contexto_tesis.md): problema, objetivos, alcance, fuentes
  de datos y metodología.
- [Estructura del proyecto](estructura_proyecto.md): organización actual del
  backend, frontend, scripts y datos.
- [Diagramas del sistema](diagramas.md): arquitectura, pipeline, modelo PostGIS,
  autenticación y navegación.
- [Decisiones técnicas](../DECISIONS.md): bitácora y decisiones vigentes.
- [Trabajo futuro](FUTURE.md): mejoras y líneas de evolución.

## Metodología y modelos

- [Índices espectrales](indices_espectrales.md): fundamento y uso de las
  variables derivadas de Sentinel-2.
- [Modelo predictivo](modelo_predictivo.md): features, entrenamiento temporal,
  modelos y métricas.
- [Validación del predictor hídrico](validacion_predictor_hidrico.md): resultados
  multifecha, desglose por cultivo y análisis estacional.
- [Modelo clasificador](modelo_clasificador.md): experimentos de clasificación
  preservados como respaldo metodológico.
- [Fragmentos de código para tesis](fragmentos_codigo_tesis.md): ejemplos breves
  vinculados con la metodología.

## Producto y arquitectura

- [Dashboard](dashboard.md): vistas, navegación y comportamiento por rol.
- [Roles y productores](roles_clientes.md): modelo funcional de usuarios,
  productores y asignaciones.
- [API](api.md): endpoints y contratos principales.
- [Seguridad y autenticación](seguridad_auth.md): tokens, contraseñas y controles
  por entorno.
- [Arquitectura cloud del pipeline](arquitectura_cloud_pipeline.md): flujo entre
  automatización, GEE, PostGIS, API y dashboard.

## Datos y persistencia

- [PostGIS](postgis.md): esquema, cargas, vistas y validaciones.
- [Límite de San Rafael](limite_san_rafael.md): alcance geográfico controlado.
- [Reconstrucción desde IDEMendoza](reconstruccion_dataset_desde_ide.md):
  preparación reproducible de parcelas.
- [Inventario de código](inventario_codigo.md): componentes vigentes, auxiliares
  y legacy.
- [Artefactos operativos](artefactos_operativos.md): archivos versionados,
  locales y regenerables.

## Operación y calidad

- [Comandos](comandos.md): referencia operativa.
- [Pruebas](tests.md): pruebas automatizadas, smoke tests y alcance.
- [Checklist operativo](checklist_operativo.md): controles previos y posteriores
  a una ejecución.
- [Despliegue en UM-Cloud](despliegue_um_cloud.md): instalación y validación del
  entorno objetivo.
- [Manual de despliegue](manual_despliegue_um_cloud.md): operación detallada.
- [Guía de preparación de UM-Cloud](UM_Cloud_Setup_Guide.md): aprovisionamiento
  de la infraestructura.

> La documentación de despliegue describe un entorno institucional específico.
> Antes de reutilizarla o compartir capturas, deben revisarse accesos, redes,
> credenciales y políticas de la organización correspondiente.
