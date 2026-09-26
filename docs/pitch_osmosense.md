# Pitch OSMOSENSE

Duracion objetivo: 10 a 12 minutos, incluyendo demo en vivo.

## Ajustes De Precision Antes De Exponer

Conviene ajustar oralmente, o en las diapositivas si todavia es posible, estas
tres expresiones:

1. Cambiar `anticipar la sequia` por `anticipar la evolucion del estres
   hidrico`. OSMOSENSE no pronostica una sequia meteorologica: estima el riesgo
   hidrico futuro de parcelas.
2. Cambiar `hasta 5 dias` por `a 5 y 10 dias`, porque esos son los dos
   horizontes implementados y validados.
3. Presentar `gestion inteligente del riego` como `apoyo inteligente a la
   decision`. El sistema no ordena regar ni reemplaza el criterio agronomico.

La reduccion de rendimiento del 20-30% debe presentarse como un orden de
magnitud observado en estudios bajo condiciones especificas, no como una
consecuencia universal para cualquier finca.

## Distribucion Del Tiempo

| Bloque | Tiempo objetivo |
|---|---:|
| Apertura y problema | 1:45 |
| Propuesta de valor | 1:20 |
| Arquitectura y decisiones tecnicas | 4:40 |
| Demo Productor | 1:30 |
| Demo Regional | 0:55 |
| Demo Admin | 1:05 |
| Cierre | 0:30 |
| **Total** | **11:45** |

## 1. Apertura Y Problema - Diapositiva 1

### Guion hablado

> San Rafael es un oasis productivo. Eso significa que la produccion agricola
> depende de disponer de agua en el momento adecuado y decidir bien como
> utilizarla.
>
> Esa decision se toma en un contexto de escasez sostenida. El Departamento
> General de Irrigacion reconoce que la escasez se profundizo durante la ultima
> decada. Ademas, buena parte del agua se entrega mediante turnos: el productor
> recibe el recurso en momentos determinados y debe aprovechar esa oportunidad.
>
> Alli aparece un dolor concreto. Cuando llega el turno, algunos productores
> intentan cubrir la mayor superficie posible. No porque todas las parcelas
> esten iguales, sino porque no siempre cuentan con una lectura reciente y
> comparable que indique donde la condicion esta empeorando mas.

Si ese relato proviene de entrevistas o conversaciones propias, se puede
agregar como testimonio informal:

> Una forma en que este problema fue expresado por productores es: cuando llega
> el turno, primero se intenta alcanzar la mayor cantidad de cuadros posible;
> despues se evalua si alguno necesitaba mas atencion que otro.

No presentarlo como encuesta representativa si no hubo un relevamiento formal.

Continuar:

> Recorrer, observar sintomas y medir con sensores sigue siendo valioso, pero
> puede resultar costoso, puntual o dificil de escalar. Cuando el sintoma ya es
> evidente, parte de la capacidad de reaccion puede haberse perdido.
>
> El problema no es solo usar agua de forma ineficiente. Tambien es decidir
> tarde y tratar como iguales parcelas que evolucionan distinto. En vid, el
> momento del estres puede afectar crecimiento, rendimiento y baya. En olivo,
> la respuesta y la tolerancia son diferentes; por eso no corresponde analizar
> ambos cultivos de la misma manera.
>
> Para las autoridades el problema cambia de escala: necesitan reconocer que
> zonas concentran mayor riesgo, con que cobertura y confianza.

### Mensaje que debe quedar

El problema no es la falta absoluta de datos. Es la falta de una lectura
actualizada, comparable y accionable a escala de parcela y de region.

## 2. Propuesta De Valor - Diapositiva 2

### Guion hablado

> OSMOSENSE busca cubrir ese vacio. Es un sistema de apoyo a decisiones que
> transforma observaciones Sentinel-2 en una lectura de estres hidrico para
> parcelas de vid y olivo de San Rafael.
>
> Para cada parcela calcula una condicion actual, estima su evolucion a 5 y 10
> dias y genera un ranking de atencion. En lugar de entregar un mapa tecnico de
> NDVI, comunica una prioridad baja, media, alta o critica, su evolucion y la
> fecha real de la observacion utilizada.
>
> El productor compara sus parcelas; la autoridad compara unidades regionales;
> y el administrador controla calidad, cobertura, usuarios y pipeline.
>
> OSMOSENSE no reemplaza al productor ni recomienda automaticamente que regar.
> Reduce incertidumbre y complementa su conocimiento del suelo y del manejo.
>
> No requiere instalar un sensor en cada parcela y se actualiza cuando aparece
> una nueva observacion satelital valida.
>
> No es solo un desarrollo de notebook: ya esta desplegado en UM-Cloud de la
> Universidad de Mendoza, con base geoespacial, API, dashboard y tareas
> programadas accesibles de forma remota.

### Resultado cuantitativo breve

> En la validacion historica, comparando predicciones contra observaciones
> Sentinel-2 futuras, el error medio global fue de aproximadamente 4.1 puntos a
> 5 dias y 4.7 puntos a 10 dias, sobre una escala de 0 a 100. La correlacion de
> Spearman fue 0.958 y 0.951. Esto importa porque el objetivo no es solamente
> acertar un valor aislado, sino ordenar correctamente las parcelas que
> requieren mayor atencion.

## 3. Arquitectura - Diagrama De Secuencia

### Introduccion al diagrama

> Esta arquitectura fue disenada para automatizar el recorrido completo, desde
> una nueva observacion satelital hasta el mapa que consulta el usuario. El
> diagrama es de secuencia: de izquierda a derecha aparecen los componentes y,
> de arriba hacia abajo, el orden en que se comunican. Las flechas continuas son
> solicitudes o escrituras; las respuestas devuelven datos procesados.

### Cron/Systemd

> El flujo comienza con systemd en la VM de UM-Cloud. Hay servicios permanentes
> para FastAPI y Streamlit, y timers para pipeline y backup. Inicia los procesos
> con la VM y puede reiniciarlos si fallan, sin sumar Kubernetes o Airflow.
>
> El timer puede ejecutarse diariamente aunque Sentinel-2 no produzca una imagen
> util todos los dias. El pipeline compara fechas y, si no encontro una nueva
> observacion valida, finaliza sin recalcular ni sobrescribir el ranking.

### Pipeline Y Lectura De Parcelas

> Al comenzar, el pipeline consulta PostGIS para obtener las parcelas activas de
> vid y olivo, su geometria y etiqueta oficial. Esa consulta define el
> territorio y lo limita al poligono oficial de San Rafael.
>
> PostGIS combina datos relacionales y geoespaciales. Guarda parcelas, usuarios,
> asignaciones, zonas, observaciones y rankings, evitando copias inconsistentes.
> En produccion es la fuente obligatoria; los CSV quedan como respaldo.

### Google Earth Engine Y Sentinel-2

> Luego el pipeline consulta Google Earth Engine. Elegi GEE porque procesa
> Sentinel-2 del lado del servidor y evita descargar mosaicos raster completos
> a la VM. Busca ventanas recientes, filtra nubes y pixeles invalidos y compone
> varias escenas cuando una sola no cubre San Rafael.
>
> El sistema no supone que hoy existe una imagen util. Busca hacia atras la
> ultima ventana valida y calcula por parcela indices como NDVI, NDMI, NDWI, MSI
> y NBR. GEE devuelve una tabla resumida, reduciendo almacenamiento y trafico.

Nota opcional si preguntan: ningun indice se interpreta aisladamente como
equivalente directo a estres. La senal surge de su combinacion, contexto
temporal y diferencia respecto de parcelas del mismo cultivo y fecha.

### Dataset Temporal Y Features

> Las observaciones nuevas se integran al historial de cada parcela. A partir de
> ese historial se construyen las variables de entrada: estado actual, valores
> anteriores, diferencias, pendientes recientes, mes, estacion y posicion
> relativa dentro del cultivo. Una sola fotografia no permite distinguir bien
> entre una condicion puntual y una tendencia sostenida.

Nota opcional si preguntan: el entrenamiento usa division temporal; aprende con
fechas anteriores y se evalua contra fechas posteriores para evitar fuga de
informacion futura.

### Modelo Predictivo Y Ranking

> Con el historial por parcela se aplican cuatro modelos XGBoost de regresion:
> vid a 5 y 10 dias, y olivo a 5 y 10 dias. Elegi XGBoost porque los datos son
> tabulares, sus relaciones son no lineales y permite analizar importancia de
> variables.
>
> Separe los cultivos porque la vid es caducifolia y el olivo perenne; un unico
> modelo mezclaria dinamicas distintas. Tambien se separaron horizontes porque
> predecir a 5 dias no tiene la misma incertidumbre que a 10.
>
> Los regresores devuelven un score continuo futuro entre 0 y 100. El ranking
> combina 30% de riesgo actual, 15% de prediccion a 5 dias, 25% de prediccion a
> 10 dias y 30% del deterioro positivo esperado a 10 dias. Los pesos se
> seleccionaron mediante validacion historica para mejorar el ordenamiento.
>
> Luego los umbrales generan prioridad baja, media, alta o critica. Son una
> interpretacion operativa del score, no un diagnostico fisiologico absoluto.
> Para productor se agrega un escenario conservador de continuidad; la salida
> cruda del modelo se conserva para auditoria admin.

### Control De Calidad Y Cobertura

> Antes de publicar, se realizan controles espaciales por vecinos cercanos. Si
> una parcela difiere demasiado de las proximas, no se corrige automaticamente:
> se compara el salto espacial con ventanas temporales anteriores. Si persiste
> puede representar suelo, cultivo o manejo real; si aparece una sola vez y con
> bajo soporte espectral puede ser ruido. El sistema baja confianza o marca
> revision, pero evita suavizar una diferencia legitima.
>
> Tambien existe una barrera de cobertura. Una fecha nueva no reemplaza el
> ranking si solo cubre parte del departamento. Se exige al menos 80% para
> promoverla como operativa. La corrida parcial queda registrada, pero se
> conserva el ultimo ranking completo. Por eso el sistema distingue entre
> `ultima corrida`, `ranking operativo` y `lectura satelital`.

### Escritura En PostGIS Y Publicacion

> Si la corrida supera los controles, el pipeline inserta observaciones y
> ranking en PostGIS. No elimina el historico: agrega una fecha y actualiza la
> vista `latest`. Tambien guarda estado y logs de la ejecucion.
>
> FastAPI consulta esas vistas y entrega JSON o GeoJSON. GeoJSON contiene la
> geometria y metricas para pintar parcelas. Hay endpoints por rol. Para un
> productor, la API toma la identidad del token y filtra sus parcelas.

### Streamlit Y Cloud

> Streamlit y Plotly construyen la interfaz. Los elegi porque permiten crear una
> aplicacion geoespacial interactiva en Python y reducen el costo de construir
> un frontend separado. Streamlit consume FastAPI, por lo que la interfaz puede
> cambiar sin reescribir modelos, permisos ni consultas.

> Esta arquitectura ya esta desplegada en una VM Ubuntu de UM-Cloud. PostGIS
> corre en Docker; FastAPI y Streamlit como servicios systemd; y timers ejecutan
> pipeline y backups. Se accede por SSH y ZeroTier, mientras la base permanece
> sin exposicion publica. Si la VM reinicia, los servicios vuelven a levantarse
> sin una terminal abierta.
>
> Por lo tanto, el prototipo incorpora condiciones reales de produccion:
> disponibilidad remota, persistencia, automatizacion, logs y recuperacion por
> backups. GEE conserva las imagenes pesadas y UM-Cloud los datos derivados,
> modelos, geometria, usuarios y rankings.

### Seguridad Y Clasificacion

> Las contrasenas se almacenan con hash PBKDF2-SHA256 y los tokens se firman
> con HMAC-SHA256. PostGIS no se expone publicamente y en produccion se
> deshabilitan login rapido y fallback local. Cada endpoint verifica permisos.

Nota opcional si preguntan: se evaluaron clasificadores y una CNN temporal, pero
el flujo usa etiquetas oficiales de IDEMendoza. La red neuronal queda como linea
experimental para no agregar incertidumbre a parcelas ya conocidas.

## 4. Demo En Vivo

Antes de comenzar, tener abiertas las tres sesiones o disponer de credenciales
preparadas. No ejecutar GEE ni modificar datos sensibles durante la demo.

### 4.1 Vista Productor - 1 Minuto 30 Segundos

#### Accion 1: ingresar como productor y abrir `Mapa`

> Empiezo por productor porque es el usuario principal. El token determina su
> identidad y la API devuelve solamente sus parcelas.

Senalar:

- `Ranking operativo usado`;
- `Lectura satelital`;
- cantidad de parcelas evaluadas y en atencion.

> Ranking y lectura pueden tener fechas distintas: una indica la fecha objetivo
> y la otra la observacion realmente utilizada.

#### Accion 2: explicar mapa, colores y slider

> Verde representa menor atencion y rojo mayor riesgo. Una flecha roja comunica
> aumento; se evita el signo positivo porque podia interpretarse como mejora.

Mover lentamente el slider de actual a 5 y 10 dias.

> El slider sigue cada parcela contra si misma y muestra actual, 5 y 10 dias. Es
> apoyo a la decision, no una orden de riego.

#### Accion 3: seleccionar una parcela

> Al seleccionar una parcela aparece una explicacion simple, sin indices que el
> productor no necesita auditar.

#### Accion 4: abrir `Resumen`

> En Resumen se compara la parcela con el promedio de su campo. Se separan
> condicion actual y escenario a 10 dias, manteniendo los colores del mapa.

Senalar `Mayor aumento esperado`.

> `Mayor aumento esperado` distingue una parcela ya comprometida de otra que se
> esta deteriorando mas rapido.

### 4.2 Vista Regional - 55 Segundos

#### Accion 1: ingresar como regional y abrir `Mapa regional`

> Regional cambia la unidad de decision: compara unidades de manejo DGI y solo
> muestra zonas con cultivos.

Mostrar filtros y selector fijo/percentiles.

> Los umbrales fijos mantienen una escala estable; los percentiles permiten
> priorizar cuando casi todas las zonas presentan valores elevados.

#### Accion 2: seleccionar una UM y abrir `Foco regional`

> La UM seleccionada resume riesgo, proyeccion, superficie y cobertura. `Foco
> regional` separa deterioro, concentracion de riesgo y falta de datos.

#### Accion 3: mostrar `Ranking UM` y `Parcelas de la UM`

> El ranking compara unidades y `Parcelas de la UM` permite verificar que
> parcelas explican cada resultado agregado.

### 4.3 Vista Admin - 1 Minuto 5 Segundos

#### Accion 1: abrir `Analisis > Estado`

> Admin separa ultimo ranking confiable y ultima corrida. Una imagen parcial se
> registra, pero no reemplaza el producto.

Senalar cobertura, fecha y estado de pipeline.

#### Accion 2: abrir `Mapa operativo`

> El mapa carga primero alta y critica para acelerar y enfocar la revision; el
> administrador puede solicitar el universo completo.

#### Accion 3: abrir `Cobertura` y `Revision tecnica`

> Cobertura explica faltantes y Revision tecnica concentra vecinos, saltos y
> baja confianza. Es control interno, no informacion para productor.

#### Accion 4: abrir `Gestion`

> Gestion permite administrar usuarios, asignar parcelas y activar nuevas
> parcelas de vid u olivo. Todo queda persistido en PostGIS.

No realizar una baja o reasignacion real salvo que exista un usuario preparado
especificamente para la demostracion.

## 5. Pruebas Y Cierre

### Guion hablado

> El sistema no se valido solamente mirando el dashboard. La suite automatizada
> prueba autenticacion, permisos por rol, endpoints, logica del frontend,
> animacion de riesgo, reportes del predictor y operaciones con PostGIS. Ademas
> se ejecutan smoke tests y verificaciones previas al despliegue cloud.
>
> UM-Cloud completa la validacion: pipeline, PostGIS, API y las tres vistas
> funcionan fuera del entorno local como servicios persistentes.
>
> OSMOSENSE no intenta reemplazar la experiencia del productor ni automatizar
> una decision agronomica sensible. Convierte informacion satelital dispersa en
> una lectura parcelaria, predictiva y trazable. El productor entiende que esta
> ocurriendo en su finca; la autoridad puede observar el territorio; y el
> administrador puede verificar de donde sale cada resultado.
>
> El aporte central es pasar de reaccionar cuando el estres ya es visible a
> disponer de una senal anticipada para observar antes y decidir con mas
> informacion, mediante una solucion que ya puede ejecutarse de forma remota y
> automatizada en la infraestructura cloud de la Universidad de Mendoza.

## Plan De Recorte Si Quedan Solo 8 Minutos

- En arquitectura, resumir seguridad y clasificacion en una sola frase.
- En productor, no abrir la tabla `Parcelas`.
- En regional, mostrar `Foco regional` sin abrir `Parcelas de la UM`.
- En admin, mostrar `Estado` y `Revision tecnica`; mencionar Gestion sin
  recorrerla.
- No eliminar la explicacion de cobertura ni la diferencia entre ranking y
  lectura satelital: son decisiones centrales del sistema.

## Preparacion De La Demo

1. Verificar acceso a ZeroTier y abrir el dashboard cloud.
2. Probar previamente las credenciales de productor, regional y admin.
3. Elegir una parcela que muestre una evolucion visible en el slider.
4. Elegir una UM con datos suficientes y otra con cobertura menor para explicar
   la diferencia.
5. Dejar cargado el mapa admin en prioridades altas/criticas.
6. Cerrar paneles del navegador, notificaciones y pestanas irrelevantes.
7. Tener capturas de respaldo de las tres vistas por si falla la conectividad.
8. No ejecutar el pipeline durante la exposicion; mostrar su estado y explicar
   la automatizacion.

## Fuentes Para Respaldar El Problema

- Departamento General de Irrigacion. Asistencia Tecnica en Riego Agricola en
  San Rafael y necesidad de mejorar el uso del agua ante la escasez sostenida:
  <https://www.irrigacion.gov.ar/web/2025/09/25/irrigacion-continuo-en-san-rafael-con-la-asistencia-tecnica-en-riego-agricola/>
- Departamento General de Irrigacion. Entrega por turnos y seccionado de riego
  en el sur mendocino:
  <https://www.irrigacion.gov.ar/web/2019/02/07/fuerte-coordinacion-de-irrigacion-en-el-sur-por-escasez/>
- INTA Rama Caida y FCAI-UNCuyo. Evaluacion del estado hidrico de vinedos de San
  Rafael para optimizar el agua de riego:
  <https://repositorio.inta.gob.ar/bitstream/handle/20.500.12123/24365/INTA_CRMendoza-SanJuan_EEARamaCa%C3%ADda_Nahuel_G._como_optimizar_agua_riego_vi%C3%B1edos_2025.pdf?isAllowed=y&sequence=1>
- Romero et al. Evidencia experimental sobre deficit hidrico, rendimiento y
  respuesta de la vid bajo condiciones semiaridas:
  <https://pmc.ncbi.nlm.nih.gov/articles/PMC3398444/>
