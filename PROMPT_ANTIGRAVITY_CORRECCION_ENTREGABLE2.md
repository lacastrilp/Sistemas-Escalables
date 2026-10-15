# Prompt maestro para Antigravity — Corrección integral del Entregable 2: Escalabilidad de los datos

## Rol y misión

Actúa como **ingeniero/a senior de datos, PostgreSQL, benchmarking, reproducibilidad y documentación técnica**. Trabaja directamente sobre el repositorio abierto en el workspace de Antigravity. Tu misión no es dar recomendaciones ni limitarte a elaborar un plan: **inspecciona, modifica, ejecuta, mide, valida y deja terminado el entregable**, con trazabilidad desde cada requisito hasta el código, la medición y la evidencia que lo demuestra.

Debes apuntar al máximo nivel de la rúbrica, especialmente corrigiendo las observaciones recibidas en C1, C2, C5 y C6. No afirmes que algo funciona porque aparezca en el Markdown, porque un script contenga el nombre de un objetivo o porque una ejecución anterior haya tenido éxito. Solo marca algo como cumplido cuando exista evidencia reproducible.

No pauses para pedirme confirmación. Primero inspecciona el workspace completo, determina qué existe y resuelve las brechas con criterio técnico. No inventes métricas ni resultados. Si alguna parte realmente no puede ejecutarse por una dependencia externa que no está disponible, deja el intento, la salida, el motivo concreto y el comando de reproducción; no simules éxito.

---

## 1. Fuentes de verdad y límites de edición

Lee y contrasta estos archivos en el workspace:

1. `Entregable2_Escalabilidad_de_datos.html`: **especificación de la asignatura**. Es de solo lectura; no lo sobrescribas ni lo conviertas en el informe final.
2. `Entregable2_Informe_Escalabilidad_de_Datos.md` o la variante de nombre que exista: informe actual que debe auditarse y actualizarse con resultados reales.
3. `modelo-fisico.sql`: DDL, restricciones, esquemas e índices actuales.
4. `Makefile`: orquestación de generación, reinicio, carga, verificación y benchmarks.
5. `docker-compose.yml` o `docker-compose.yaml`: infraestructura y arranque de PostgreSQL.
6. `Portal_B2B_Retail_corregido.pdf`: contexto del dominio, nombres de entidades, reglas de negocio y significado de OTIF/Fill Rate. Úsalo como referencia del dominio, no como reemplazo de los requisitos de Entregable 2.
7. Todo el resto del repositorio, especialmente `datos/`, scripts de generación/carga/verificación/benchmarks, consultas SQL, `datos/output/`, pruebas, `README`, dependencias y código del servicio o endpoint transaccional.

La especificación HTML prevalece para los requisitos de la entrega; el feedback identifica brechas prioritarias; el código y las ejecuciones reales determinan qué está implementado; el informe debe reflejar lo medido, nunca al revés. Si encuentras contradicciones entre los documentos, registra la contradicción en la matriz de trazabilidad y resuélvela explícitamente sin esconderla.

Antes de modificar:

- Inspecciona la raíz y el árbol completo del repositorio. No supongas que los archivos `datos/*.py` existen solo porque el `Makefile` los mencione.
- Comprueba `git status`, la rama y los cambios locales. No borres ni sobrescribas cambios ajenos a esta tarea.
- Conserva como histórico cualquier evidencia anterior que pueda ser útil. No presentes resultados antiguos como si se hubieran medido con el dataset nuevo.
- No ejecutes borrados globales, `docker system prune` ni operaciones que afecten proyectos Docker ajenos. Cualquier prueba destructiva debe usar el proyecto/volumen de Docker Compose aislado de esta entrega.

---

## 2. Primera etapa obligatoria: auditoría y matriz de trazabilidad

Antes de implementar, inspecciona archivos y ejecuciones actuales y crea `docs/MATRIZ_TRAZABILIDAD_ENTREGABLE2.md` (crea `docs/` si hace falta). Cada fila debe incluir:

- ID y descripción literal/resumida del requisito HTML.
- Archivo, función, consulta o target que lo implementa.
- Estado real inicial: `CUMPLE`, `PARCIAL`, `NO CUMPLE` o `NO VERIFICADO`.
- Brecha concreta encontrada.
- Cambio que se hará.
- Comando automatizado de verificación.
- Ruta de la evidencia final que demuestra el resultado.

Incluye los seis criterios de la rúbrica y todos los requisitos detallados, no solo los cuatro señalados en el feedback. Actualiza esta matriz al finalizar para que corresponda al estado final. No marques `CUMPLE` si el comando de verificación no fue ejecutado con éxito.

---

## 3. C1 — Corregir volumetría, modelo físico y consistencia de los conteos

El informe actual registra varios valores en el mínimo, pero no llega a los objetivos. Debes cambiar los valores por defecto del generador para que la ejecución normal alcance **y preferiblemente supere con un margen pequeño** cada objetivo explícito. No compenses una entidad que está por debajo del objetivo con filas de otra tabla o con la tabla de relación `proveedor_sku`.

### Objetivos que deben quedar cubiertos

| Entidad lógica | Tabla esperada | Mínimo obligatorio del HTML | Objetivo del HTML | Requisito de aceptación por defecto |
|---|---|---:|---:|---|
| Proveedores | `proveedores.proveedor` | 100.000 | 100.000 | Más de 100.000, si el coste de la prueba lo permite; nunca menos de 100.000 |
| Contratos de suministro | `proveedores.contrato_suministro` | 10.000 | 15.000 | Al menos 15.000; preferiblemente un margen pequeño por encima |
| SKU del catálogo | `catalogo.sku` | 200.000 | 400.000 | Al menos 400.000; preferiblemente un margen pequeño por encima |
| Órdenes de compra en 24 meses | `ordenes.orden_compra` | 300.000 | 500.000 | Al menos 500.000; preferiblemente un margen pequeño por encima |
| Líneas de orden | `ordenes.linea_orden` | 1.500.000 | 3.000.000 | Al menos 3.000.000; preferiblemente un margen pequeño por encima |
| Franjas de descargue | `logistica.franja_descargue` | 90.000 | 150.000 | Al menos 150.000; preferiblemente un margen pequeño por encima |
| Eventos de auditoría | `ordenes.evento_auditoria` | 500.000 | 800.000 | Al menos 800.000; preferiblemente un margen pequeño por encima |
| CEDI | `logistica.cedi` | El HTML exige al menos 5 | 5 | Mantener al menos 5; el valor 10 actual es válido si se verifica |
| Relación proveedor–SKU | `catalogo.proveedor_sku` | El HTML no le asigna un objetivo numérico específico | No especificado | Generar relaciones válidas y medirlas por separado; no usarlas para sustituir el objetivo de `catalogo.sku` |

El margen extra debe ser pequeño, configurable y explicable. Añade parámetros claros para ajustar volúmenes, semilla y sesgo sin editar el código. Los valores predeterminados deben dejar el entregable completo, no un dataset de prueba reducido. Puedes conservar perfiles `smoke` o `dev` para pruebas rápidas, pero `make datos` debe ejecutar el perfil completo de entrega.

### Verificaciones físicas y numéricas

- La verificación debe consultar el conteo real en PostgreSQL de **cada tabla**, no inferirlo por la cantidad de líneas de los CSV ni por el log del generador.
- Imprime mínimo, objetivo, logrado, diferencia y estado para cada tabla. Distingue entre `PASA_MINIMO` y `PASA_OBJETIVO`; la entrega completa debe alcanzar todos los objetivos.
- Verifica las cuatro fronteras de esquema: `proveedores`, `catalogo`, `logistica` y `ordenes`. No introduzcas `JOIN` entre esquemas en las cinco consultas patrón ni en la solución propuesta. No confundas esta prohibición de `JOIN` con la mera existencia de una clave foránea, y no elimines restricciones válidas sin una razón de dominio.
- Revisa tipos, claves, restricciones y cardinalidades. Documenta por qué cada índice secundario existe y a qué consulta patrón ayuda; elimina únicamente índices redundantes o sin justificación demostrable.
- El DDL debe poder ejecutarse repetidamente desde una base limpia. Un reinicio debe crear la estructura esperada y no depender del estado previo de PostgreSQL.

### Corrige la suma de volúmenes en el informe

El HTML lista volúmenes mínimos y objetivos por entidad, pero las sumas aproximadas que aparecen en su tabla no cuadran exactamente con los valores de las filas. Con los siete renglones que tienen mínimo/objetivo numérico explícito, las sumas son **2.700.000 como mínimo** y **4.965.000 como objetivo**, antes de agregar el número observado de relaciones `catalogo.proveedor_sku` y de CEDI. Calcula y presenta las sumas de nuevo; explica claramente qué tablas se incluyen en cada total. El total real de filas debe calcularse desde la base cargada. No digas que 5,44 millones “superan en más del 100 % el mínimo” si la comparación mezcla entidades sin objetivo o si varias entidades no alcanzan su objetivo individual.

### Contratos y cobertura de proveedores

El HTML señala que solo alrededor del 12 % de proveedores tiene contrato. Haz compatibles ambos requisitos: cantidad objetivo de contratos y cantidad de proveedores distintos cubiertos. Cuenta por separado contratos totales, contratos vigentes y proveedores distintos con al menos un contrato; documenta las proporciones observadas y su tolerancia. Evita conseguir 15.000 contratos simplemente dando contrato a una proporción no documentada de todos los proveedores.

---

## 4. C2 — Sesgo, estacionalidad y ocho casos borde: demostrar la forma de los datos

No basta con sembrar datos que se llaman “Zipf” o que tienen un campo de fecha. Debes verificar la distribución real con consultas sobre la carga final y producir evidencia en tablas, métricas y gráficos.

### Sesgo requerido

1. **Sesgo Zipf por proveedor:** conserva un parámetro `s` configurable y una semilla fija. Verifica que el top 1 % de proveedores concentre como mínimo el 15 % de las órdenes y el top 5 % como mínimo el 40 %. Reporta también el top 20 %, la curva acumulada y el identificador y volumen real del proveedor más caliente.
2. **Sesgo por SKU:** el 10 % de los SKU debe aparecer en al menos aproximadamente el 60 % de las líneas de orden. Esta condición aparece en el HTML y debe medirse explícitamente; no la sustituyas por la distribución Zipf de proveedores. Si la implementación actual no la tiene, impleméntala y valida el porcentaje real.
3. **Estacionalidad mensual:** los últimos tres días hábiles de cada mes deben concentrar aproximadamente el 25 % de las órdenes del mes. Usa días hábiles reales (no simplemente los últimos tres días calendario), aplica una convención documentada para festivos y muestra el resultado mensual y agregado.
4. **Estacionalidad horaria:** debe existir un pico entre 08:00 y 11:00 y un valle nocturno cercano a cero entre 00:00 y 06:00. Reporta los conteos y porcentajes por hora; evita declarar cumplida la estacionalidad solo por describirla en texto.
5. Grafica al menos la distribución/concentración Zipf por proveedor, concentración de SKU en las líneas, órdenes por día y distribución horaria. Cada gráfico debe tener título, unidades, periodo, volumen observado y fuente de datos. Los CSV usados para construirlos deben guardarse junto con la evidencia.

### Ocho casos borde obligatorios

Asegura que los ocho casos existan **realmente después de cargar**, puedan localizarse por identificador y sean validados por SQL o pruebas automáticas. Los IDs deben descubrirse desde la generación y escribirse en el reporte/evidencia; no los hardcodees en el informe si cambian con los parámetros.

1. Una orden con exactamente 300 líneas.
2. Un contrato vencido el día anterior a la fecha lógica de referencia.
3. Un contrato que vence el día lógico de referencia **a las 12:00 del mediodía**.
4. La última franja disponible de un CEDI, con exactamente un cupo libre.
5. Un proveedor sin contrato vigente.
6. Una orden con al menos un SKU que existe en el catálogo global, pero no pertenece al catálogo negociado de ese proveedor.
7. Un proveedor caliente que tenga al menos 5.000 órdenes.
8. Un proveedor activo que no tenga órdenes en un mes completo (por ejemplo, enero de 2024 si se conserva el periodo 2024–2025).

Para los casos temporales, define un parámetro reproducible `--as-of` (o equivalente) con valor predeterminado fijo, por ejemplo `2025-12-31T12:00:00`, de modo que “ayer” y “hoy al mediodía” tengan significado estable aunque el generador se ejecute en fechas distintas. El informe debe decir cuál es la fecha lógica utilizada.

Revisa la incompatibilidad entre el caso “vence hoy al mediodía” y el campo actual `fecha_fin DATE`. Una fecha sin hora no puede representar exactamente el mediodía. Ajusta el tipo/modelo de datos al mínimo necesario (por ejemplo, un `TIMESTAMP` con convención horaria definida) y actualiza generador, CSV, carga, consultas y pruebas; o implementa una representación equivalente, exacta y documentada. No dejes como evidencia de este caso únicamente `fecha_fin = '2025-12-31'` si eso no demuestra la hora del vencimiento.

Después de generar y cargar, `make verificar` debe comprobar los ocho casos y emitir un resultado por cada uno: identificador, consulta o predicado verificado, valor observado y `PASA/FALLA`. Debe devolver código de salida distinto de cero si cualquiera falla.

---

## 5. Generador determinista, parametrizable y por streaming

Audita y corrige el generador actual, sin asumir que su existencia o comportamiento están demostrados.

- Usa semilla fija por defecto `42` y permite cambiarla mediante argumento de línea de comandos. Conserva determinismo entre corridas con igual configuración y versión del generador.
- Permite parametrizar volúmenes de proveedores, contratos, SKU, órdenes, líneas, franjas y eventos; parámetros de sesgo por proveedor y por SKU; rango temporal; y fecha lógica de referencia de los casos borde.
- Escribe los CSV por streaming/bloques a disco: no acumules millones de filas en listas o DataFrames en memoria. Resuelve IDs y referencias deterministas sin consultas individuales a la base de datos cuando puedan derivarse aritméticamente.
- Define un orden de generación/carga compatible con claves y restricciones: proveedores, contratos, SKU, relaciones proveedor–SKU, CEDI, franjas, órdenes, líneas y eventos de auditoría (ajusta el orden si el DDL real lo requiere y documéntalo).
- Cada CSV debe tener encabezados consistentes con el DDL, UTF-8, fechas ISO, nulls definidos y conteos registrados. Valida que todas las FK y restricciones se puedan satisfacer antes de considerar terminado el generador.
- Demuestra determinismo ejecutando dos generaciones separadas con la misma semilla y configuración. Compara SHA-256 de los CSV o checksum reproducible de una columna estable y reporta los dos valores, igualdad y configuración. Incluye una prueba automatizada; no aceptes como demostración la mera presencia de `random.seed()`.
- Asegura que el `checksum` no dependa del orden incidental del sistema de archivos o del orden de iteración no determinista.

Guarda configuración, resumen de generación, conteos, tamaños, tiempos y hashes en `datos/output/` o en la estructura de evidencia equivalente.

---

## 6. Carga: cuatro estrategias comparables y carga incremental real

El HTML exige cuatro estrategias sobre **el mismo subconjunto de 50.000 órdenes**. La evidencia actual declara una muestra de 50.000 órdenes y 250.137 líneas, pero debes volver a medirla y verificar los conteos; no reutilices esos números sin confirmación.

### Cuatro estrategias obligatorias

1. `COPY` masivo.
2. `INSERT` por lotes de 1.000 registros dentro de transacciones explícitas.
3. `INSERT` fila a fila con `autocommit`.
4. Ruta transaccional real de la aplicación/servicio, que ejecuta las validaciones de negocio relevantes: contrato vigente, pertenencia de SKU al catálogo negociado y reserva de franja.

Todas deben procesar el mismo subconjunto válido, derivado una sola vez y reutilizado por los cuatro métodos. Conserva la misma lista de órdenes/líneas y las mismas condiciones de datos, documenta las diferencias intencionales de cada estrategia y verifica los mismos conteos finales. No uses casos intencionalmente inválidos dentro de la muestra comparativa si la ruta de negocio debe rechazarlos; los casos borde se prueban aparte.

Para cada método mide tiempo total, filas realmente insertadas y filas/segundo. Registra timestamp, configuración, tamaño exacto del subconjunto, resultado y errores. Guarda resultados crudos en CSV/JSON y el resumen tabular. Explica las diferencias solo con lo que muestren las mediciones. No atribuyas tiempos a `fsync`, CPU o red sin evidencia suficiente.

### Ruta transaccional

Inspecciona la implementación existente del endpoint/servicio en el repositorio y úsala. No declares “ruta real de la aplicación” a un script que haga `INSERT` directo saltándose el servicio. Si el workspace incluye el servicio, arráncalo y llama a su ruta real. Si solo existe una capa de dominio reutilizable, invócala de forma reproducible e identifica la modalidad. Si la implementación requerida no existe, implementa o conecta la mínima ruta legítima respetando la arquitectura ya presente; no fabriques una medición que aparente pasar.

Además de la comparación común, el HTML exige insertar **5.000 órdenes adicionales** tras la carga masiva por el servicio/endpoint real, nunca por `COPY`. Separa esta prueba incremental del benchmark comparable de 50.000 órdenes. Reporta órdenes aceptadas/rechazadas, motivos, líneas insertadas, franja reservada, tiempo y validaciones ejecutadas. Verifica que no haya sobreventa de franjas. Si no es técnicamente posible ejecutar la ruta por una dependencia que no existe/disponible, deja el bloqueo explícito y no marques C4 como completo.

---

## 7. Orden correcto de preparación, carga e índices

En el `modelo-fisico.sql` actual los índices secundarios están creados dentro del DDL, por lo que aparecen antes de la carga masiva. Esto contradice la secuencia pedida por el HTML y dificulta una comparación real de planes antes/después.

Organiza el flujo para que:

1. Se cree una base/esquema limpio con tablas, PK, restricciones y FK necesarias.
2. Se generen los CSV.
3. Se carguen los datos con `COPY`.
4. Se realice un `ANALYZE` del estado sin los índices secundarios que se evaluarán, de modo que las estadísticas estén disponibles para el plan inicial.
5. Se guarden los planes `EXPLAIN` previos a índices secundarios.
6. Se creen los índices secundarios después de la carga, en un script claro separado (por ejemplo `datos/sql/indices_secundarios.sql`), conservando PK/UNIQUE obligatorias.
7. Se ejecute de nuevo `ANALYZE` en todas las tablas afectadas.
8. Se guarden los planes posteriores y se ejecute el benchmark final de consultas con el modelo físico definitivo.

Si eliges otra organización, debe cumplir exactamente esas propiedades y quedar explicada en la matriz y el README.

---

## 8. C5 — Q1–Q5: medición completa y EXPLAIN antes/después

Implementa o corrige `datos/benchmark_queries.py` (o el módulo equivalente) y verifica todas las consultas patrón definidas en el HTML:

- **Q1:** proveedor y contrato vigente por `proveedor_id` y fecha. Referencia de rendimiento del enunciado: por debajo de 10 ms.
- **Q2:** precio/vigencia de 20 SKU en el catálogo negociado de un proveedor.
- **Q3:** franjas disponibles de un CEDI para una fecha.
- **Q4:** OTIF y Fill Rate por proveedor y mes durante 24 meses.
- **Q5:** últimas 50 órdenes de un proveedor caliente, ordenadas y paginadas.

### Protocolo de medición obligatorio

- Ejecuta 200 iteraciones por consulta y escenario. Mide cada iteración con un reloj monotónico de alta resolución; registra cada observación individual, no solo el resumen.
- Calcula y reporta `p50`, `p95`, `p99` y promedio, en milisegundos, usando un método de percentiles consistente y documentado. El informe no puede limitarse al promedio.
- Mide parámetros obtenidos del dataset final real: proveedor caliente del top 1 % y proveedor de cola larga para Q1, Q2, Q4 y Q5. Registra los IDs y cantidades reales que justifican la selección.
- El HTML usa “parámetro frío/caliente” para describir la selectividad del parámetro. No lo confundas con una caché fría/caliente a nivel de memoria u OS. En gráficas y texto usa “parámetro de cola larga” y “parámetro caliente” cuando eso sea lo que se midió. Si también experimentas con caché fría/caliente, sepáralo como otro experimento y documenta cómo se limpió/rehidrató la caché.
- Q3 no filtra por proveedor: selecciona parámetros representativos reales por CEDI/fecha (poca frente a alta presión/selectividad), explícitalos y no inventes un proveedor frío/caliente en esa consulta.
- Registra la configuración de la BD, versión de PostgreSQL, escala de datos, estado de índices, parámetros, número de ejecuciones y unidades junto a cada resultado.
- Guarda salida cruda por iteración en CSV y el resumen en JSON/CSV. Genera gráficos desde esos archivos, con unidades y volumen. Las gráficas no reemplazan los datos crudos.

### Evidencia `EXPLAIN (ANALYZE, BUFFERS)`

El HTML exige planes de Q4 y Q5 antes y después del índice elegido y la rúbrica de máximo nivel pide que el antes/después justifique cada índice revisado. Como mínimo, produce este recorrido medible:

1. **Estado base sin índices secundarios objetivo:** captura el plan completo de Q4 y Q5 con `EXPLAIN (ANALYZE, BUFFERS)` después de cargar y hacer `ANALYZE`.
2. **Después de `idx_orden_proveedor_fecha`** (sobre `ordenes.orden_compra(proveedor_id, fecha_orden)`): vuelve a capturar Q4 y Q5, con los mismos parámetros y SQL.
3. **Antes/después de `idx_linea_orden`** (sobre `ordenes.linea_orden(orden_id)`): compara Q4 después de tener el índice de orden y antes/después de crear el índice de líneas.
4. Si propones o modificas otro índice relevante, genera el par antes/después de ese índice también. No cites un índice sin mostrar el estado previo y posterior que permite evaluarlo.

Guarda el texto completo real (y, si es útil, JSON) en archivos independientes, con nombres inequívocos, por ejemplo:

- `datos/output/explain/q4_antes_indices.txt`
- `datos/output/explain/q5_antes_indices.txt`
- `datos/output/explain/q4_despues_idx_orden_proveedor_fecha.txt`
- `datos/output/explain/q5_despues_idx_orden_proveedor_fecha.txt`
- `datos/output/explain/q4_despues_idx_linea_orden.txt`
- `datos/output/explain/resumen_comparacion_indices.json`

Usa los mismos parámetros, fechas, SQL y tamaño de base para las comparaciones. Guarda la definición de cada índice, tiempo real, filas estimadas/observadas, método de scan, loops, buffers hit/read, sort/memoria si aparece y cualquier advertencia relevante. Presenta una tabla antes/después con cambios absolutos y porcentuales calculados automáticamente.

No fuerces al optimizador a utilizar un índice ni declares que mejoró si no lo hizo. Si PostgreSQL elige un `Seq Scan`, documenta el motivo plausible con datos, selectividad y estadísticas reales. Recuerda que `shared hit` indica bloques encontrados en caché de PostgreSQL; **no demuestra por sí solo contención o bloqueo**. Tampoco llames “partición física” a un proveedor caliente si no existe particionamiento real; usa “clave/proveedor caliente”.

### Validación semántica de Q4

Revisa Q4 con el contexto del dominio en `Portal_B2B_Retail_corregido.pdf`. OTIF significa entrega completa y a tiempo. La consulta del informe actual usa una comparación entre `fecha_confirmacion` y `fecha_entrega`; eso no demuestra por sí solo que la entrega ocurrió antes de su fecha prometida. Valida qué significa cada fecha en el modelo real. Si falta una fecha comprometida/esperada para medir puntualidad, agrega el atributo mínimo correcto o implementa una regla de negocio defendible, cambia la generación y prueba sus casos. No alteres silenciosamente el significado de OTIF.

Comprueba también que el JOIN entre cabecera y líneas no distorsione los indicadores. `COUNT(DISTINCT ...)` evita algunas duplicaciones de conteo, pero confirma la fórmula de OTIF y el denominador/numerador del Fill Rate con pruebas pequeñas de resultado conocido. Añade pruebas SQL o unitarias de un caso completo/a tiempo, uno tardío, uno incompleto y un caso sin líneas o sin denominador válido si el dominio lo permite.

---

## 9. C6 — Reproducción desde una máquina limpia con un solo comando

El requisito es que el evaluador pueda clonar el repositorio, instalar los prerrequisitos documentados y ejecutar un solo comando principal para generar, cargar, verificar y medir desde cero. En el estado adjunto, `Makefile` intenta ejecutar `docker exec` sobre `entregable2-postgres` sin levantarlo; `docker-compose` define solo PostgreSQL y no contiene una comprobación de salud. Corrígelo.

### Requisitos del arranque limpio

- Añade un target de arranque (`db-up` o similar) que invoque `docker compose up -d` para el servicio correcto, con healthcheck de PostgreSQL y espera explícita a que esté disponible. No confíes en un `sleep` fijo como única condición.
- El target principal `make datos` debe orquestar toda la secuencia completa: arranque y readiness, esquema limpio, generación, carga, verificación, análisis de determinismo, baseline EXPLAIN, creación de índices, ANALYZE final, benchmark de carga, benchmark de consultas, carga incremental de 5.000 órdenes por ruta real y empaquetado de evidencias/documento final.
- Si son necesarias bibliotecas Python, declara versiones razonables en `requirements.txt` (o equivalente) y documenta/automatiza un entorno virtual local sin contaminar el Python del sistema. No presupongas dependencias que solo existen en tu portátil.
- Usa variables configurables para host, puerto, usuario, base y contraseña. Los defaults de desarrollo deben estar claramente identificados. Evita credenciales sensibles en el repositorio.
- Haz que el proceso falle rápido y con mensajes accionables ante error de Docker, conexión, CSV ausente, FK violada, conteos insuficientes, script fallido o evidencia no generada. Los targets no deben imprimir “OK” o “completo” si los comandos anteriores fallaron.
- Corrige detalles de portabilidad de `Makefile`/shell (por ejemplo `SHELL`, rutas relativas al repositorio y uso de `set -euo pipefail` donde corresponda). Todos los comandos deben funcionar desde la raíz indicada y no depender del directorio actual de quien los lanzó.
- No hagas que un volumen viejo esconda que el proceso no funciona desde cero. El reset debe preparar de manera determinista el esquema y los índices en el orden correcto. Mantén un target explícito y seguro para limpiar la base del proyecto, con advertencia de que elimina los datos de esta entrega.
- Si hay endpoint/servicio para la ruta transaccional, incluye la forma de iniciarlo y esperar a que esté sano como parte de la orquestación. Si necesita un broker u otra dependencia declarada en el proyecto, incorpora la dependencia cuando sea necesario para la prueba, sin reconstruir arquitectura fuera del alcance.

### Prueba limpia que debes ejecutar de verdad

Crea y ejecuta un target como `make clean-test` o un script equivalente que use un **proyecto/volumen Docker aislado** para simular una máquina limpia. Debe bajar y eliminar únicamente el volumen propio y temporal de esta prueba, luego ejecutar el flujo completo `make datos` y conservar el log. No borres volúmenes compartidos ni recursos de otros proyectos.

La prueba debe dejar evidencia, al menos:

- versión de Docker/Compose, Python y PostgreSQL;
- comando exacto ejecutado desde el estado limpio;
- log completo de inicio a fin;
- código de salida;
- conteos reales de todas las tablas;
- estado de todos los casos borde;
- checksum de dos generaciones iguales;
- tiempos de carga y Q1–Q5;
- planes antes/después;
- índice de archivos de evidencia producidos.

No marques reproducibilidad completa si el test no se ejecutó desde un entorno limpio real. Si el entorno de ejecución de Antigravity impide usar Docker, deja scripts y comandos listos, ejecuta todas las validaciones que sí sean posibles y marca el test Docker como `NO EJECUTADO`, explicando el bloqueo exacto; nunca lo declares `PASA` por inferencia.

---

## 10. Evidencia y reporte final

Crea una estructura clara, manteniendo compatibilidad con la existente. Como referencia:

```text
docs/
  MATRIZ_TRAZABILIDAD_ENTREGABLE2.md
  README_REPRODUCCION.md
Entregable2_Informe_Escalabilidad_de_Datos.md
datos/
  generar.py
  cargar.sh
  verificar.py
  benchmark_carga.py
  benchmark_queries.py
  sql/
    esquema.sql                 # o modelo-fisico.sql sin índices secundarios de prueba
    indices_secundarios.sql
    consultas_q1_q5.sql
  output/
    logs/
    conteos/
    determinismo/
    estrategias/
    queries/
    explain/
    graficas/
    resumen_final.json
    inventario_evidencias.txt
```

Adapta la estructura al repositorio, sin duplicar archivos innecesariamente. Conserva `modelo-fisico.sql` con ese nombre si el proyecto depende de él; puedes separar los índices a otro script.

Actualiza el informe final con **datos nuevos generados y medidos por la ejecución final**. No hardcodees métricas en el documento ni copies la tabla actual de forma manual. Idealmente, genera sus tablas desde `resumen_final.json` y los CSV/JSON de salida. Actualiza gráficos, rutas relativas y pies de figura para que todas las imágenes existan en una clonación fresca tras `make datos`.

El documento de entrega del HTML pide un informe corto de máximo ocho páginas. Mantén el informe principal conciso, legible y dentro de ese límite al imprimir/exportar. Puede haber un apéndice/directorio aparte para logs, resultados crudos y planes íntegros. En el reporte incluye:

1. tabla por entidad con mínimo, objetivo, logrado, diferencia, estado y total explícito;
2. separación de los cuatro esquemas;
3. mediciones verificables de Zipf de proveedores y SKU, estacionalidad mensual y horaria;
4. identificadores y validación de los ocho casos borde;
5. demostración de determinismo con semilla y checksum de dos corridas;
6. tiempo, volumen y filas/segundo de COPY por tabla; ANALYZE e índices después de carga;
7. comparativa de las cuatro estrategias sobre la muestra común, con resultados crudos;
8. prueba incremental de 5.000 órdenes por la ruta real;
9. tabla Q1–Q5 con p50/p95/p99 y promedio, parámetros, número de iteraciones y volumen final;
10. EXPLAIN antes/después de al menos dos índices, referencias a archivos completos y explicación honesta;
11. un hallazgo incómodo calculado desde los resultados finales, explicando cómo llevó a una decisión de diseño;
12. procedimiento de reproducción desde limpio y resultado real de la prueba.

El hallazgo incómodo actual —Q4 degrada notablemente en un proveedor caliente pese a que existen índices— puede mantenerse solo si la corrida nueva lo vuelve a demostrar. Mide su magnitud con resultados nuevos. Evalúa una decisión concreta (por ejemplo, proyección analítica/materialización asíncrona) y deja claro si es propuesta futura o si ya fue implementada y medida. No prometas que Q4 pasará a `<1 ms` sin hacer la prueba correspondiente.

Además del Markdown final, puedes generar un HTML de informe con nombre distinto, por ejemplo `Entregable2_Informe_Escalabilidad_de_Datos.html`; **nunca uses ni sobrescribas `Entregable2_Escalabilidad_de_datos.html`, que es la especificación de la asignatura**.

---

## 11. Pruebas de aceptación finales: no des por terminada la tarea hasta recorrerlas

Ejecuta todo lo viable desde el workspace y registra el resultado real:

- [ ] `make help` describe targets que existen y funcionan.
- [ ] `make datos` arranca desde una base/esquema limpio y termina con código 0.
- [ ] Todos los conteos reales cumplen los objetivos individuales; ninguna tabla queda por debajo de su objetivo.
- [ ] La suma de volumen del informe está aritméticamente comprobada y separa entidades con objetivo de tablas sin objetivo explícito.
- [ ] Hay cuatro esquemas funcionales y las consultas patrón no hacen `JOIN` entre ellos.
- [ ] Zipf proveedor cumple top 1 % ≥15 % y top 5 % ≥40 %.
- [ ] El 10 % superior de SKU concentra aproximadamente ≥60 % de líneas, demostrado con SQL y evidencia.
- [ ] Se demuestra la estacionalidad mensual de los últimos tres días hábiles y la horaria, con gráficos y datos crudos.
- [ ] Los ocho casos borde existen, tienen IDs generados y pasan validación automática.
- [ ] La fecha/hora del caso de vencimiento al mediodía está representada y probada con precisión.
- [ ] Dos corridas con la misma semilla y configuración generan checksum idéntico; queda registro de ambas.
- [ ] Las cuatro estrategias procesan exactamente la misma muestra válida de 50.000 órdenes y el mismo conjunto de líneas, con tiempo total y filas/segundo reales.
- [ ] Se ejecuta aparte la carga incremental de 5.000 órdenes a través del servicio/endpoint real y se verifica el resultado transaccional.
- [ ] Q1–Q5 tienen 200 iteraciones por escenario y p50/p95/p99; los CSV conservan las observaciones individuales.
- [ ] Q4 y Q5 tienen planes previos y posteriores; `idx_orden_proveedor_fecha` y `idx_linea_orden` tienen evidencia comparativa inequívoca.
- [ ] Los índices secundarios se crean después de COPY; hay `ANALYZE` antes del baseline y después de crear los índices.
- [ ] `make clean-test` demuestra la reproducción en proyecto/volumen aislado, o queda honesta y claramente marcado como no ejecutado por una limitación comprobada.
- [ ] Los archivos de salida citados por el informe existen, se regeneran y sus cifras coinciden con los CSV/JSON y logs.
- [ ] El informe final no presenta métricas heredadas del informe anterior como nuevas ni afirma cumplimientos no verificados.
- [ ] El informe principal es corto (máximo ocho páginas en la versión imprimible), y la matriz de trazabilidad está actualizada.
- [ ] Ejecuta validaciones finales adicionales (`git diff --check`, lint/tests aplicables, compilación/importación de scripts, verificación SQL) y corrige errores encontrados.

Si cualquier casilla falla, continúa corrigiendo dentro del alcance y vuelve a ejecutar las pruebas afectadas. Si una falla es imposible de resolver por una dependencia real que no está disponible, documenta exactamente qué falta y separa claramente `FALLA`, `NO EJECUTADO` y `PASA`; nunca disimules un fallo.

---

## 12. Forma de trabajo y respuesta final

Trabaja de forma end-to-end, no te detengas después de producir la matriz o el plan. Al acabar, entrega un resumen con:

1. archivos creados/modificados;
2. brechas encontradas y cómo se corrigieron;
3. comandos realmente ejecutados y código de salida;
4. conteos reales por entidad, con los objetivos al lado;
5. resumen de sesgo/casos borde/determinismo;
6. tabla de las cuatro estrategias y Q1–Q5 usando datos medidos;
7. índices evaluados y rutas a cada EXPLAIN antes/después;
8. evidencia de `make datos` desde limpio;
9. rutas del informe final, matriz y evidencias crudas;
10. cualquier punto todavía no verificado, con motivo preciso.

**Regla final:** el entregable está terminado únicamente cuando requisito, implementación, medición y evidencia coinciden. No basta con que los scripts existan, no basta con que la documentación lo afirme y no basta con que una ejecución previa haya funcionado.
