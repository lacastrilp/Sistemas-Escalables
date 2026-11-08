# Prompt para Generar Diapositivas en otra IA (Gamma, Claude, ChatGPT o Marp)

Copia y pega el siguiente bloque de texto en la IA de tu preferencia (por ejemplo Gamma App, Claude, ChatGPT o SlidesGPT) para generar la presentación completa, sobria y profesional:

```text
Actúa como un diseñador instruccional y experto en arquitectura de software. Necesito que generes una presentación técnica de 11 diapositivas para la sustentación final de la materia "Aplicaciones y Sistemas Escalables" en la Universidad EAFIT.

Pautas de estilo y formato obligatorias:
1. Tono: Académico, riguroso, formal y de nivel universitario en ingeniería de sistemas.
2. Cero emojis: No utilices ningún emoji ni expresiones coloquiales o de marketing ("increíble", "revolucionario", "mágico").
3. Estilo visual: Minimalista, sobrio y profesional. Paleta de colores recomendada: azul marino oscuro (#1E3A8A), fondo blanco o gris tenue (#F8FAFC), texto en gris oscuro (#1F2937) y resaltados en azul neutro (#2563EB) o verde tenue (#059669) para métricas que cumplen.
4. Para cada una de las 11 diapositivas debes incluir:
   - Número y Título de la diapositiva.
   - Expositor asignado (Sara López Marín o Luis Alejandro Castrillón Pulgarin).
   - Estructura visual sugerida (disposición de columnas, tablas, diagramas o tarjetas de datos).
   - Contenido exacto en viñetas claras y técnicas.
   - Notas para el presentador (lo que debe decir el estudiante en 1 o 2 minutos).

A continuación está el contenido estructurado que debe contener cada diapositiva:

---

DIAPOSITIVA 1: Portada
- Título: Portal B2B Retail: Arquitectura, Escalabilidad y Observabilidad
- Subtítulo: Sustentación Final del Proyecto Integrador
- Metadatos: Universidad EAFIT · Escuela de Informática y Tecnologías Aplicadas
- Materia: Aplicaciones y Sistemas Escalables (2026-2)
- Integrantes: Sara López Marín y Luis Alejandro Castrillón Pulgarin (Grupo EKS)
- Expositor: Sara López Marín
- Disposición visual: Centrada, formal, tipografía sans-serif limpia.

DIAPOSITIVA 2: Dominio de Negocio y Arquitectura Base
- Título: Arquitectura del Sistema: Monolito Modular Desacoplado
- Expositor: Sara López Marín
- Disposición visual: 2 columnas (Izquierda: Reglas de Diseño, Derecha: Características del Dataset).
- Viñetas columna 1:
  * Monolito modular sobre PostgreSQL 16 con 4 esquemas independientes: proveedores, catalogo, logistica y ordenes.
  * Regla estricta de arquitectura: Cero JOINs inter-esquemas. Las relaciones se mantienen como llaves foráneas lógicas (BIGINT).
  * Aislamiento por diseño que habilita extracción futura hacia microservicios independientes.
- Viñetas columna 2:
  * Dataset sintético masivo de 5.66 millones de registros.
  * Distribución Zipfiana con parámetro s=1.2 para modelar superproveedores y cola larga real.
  * Estacionalidad temporal y casos borde incorporados (contratos vencidos, cancelaciones).

DIAPOSITIVA 3: Estado Inicial y Línea Base de Rendimiento
- Título: Estado Inicial del Sistema y Línea Base (Momento 1)
- Expositor: Luis Alejandro Castrillón Pulgarin
- Disposición visual: Tarjetas métricas + captura o tabla de latencias base.
- Viñetas:
  * Reconstrucción del entorno canónico antes de inyectar fallas.
  * Latencias de referencia sub-milisegundo en consultas analíticas y transaccionales (Q1 a Q5): p50 entre 0.08 ms y 0.48 ms.
  * Tasa de error inicial: 0.00% y throughput transaccional estable.
  * Observabilidad en reposo: Grafana y Jaeger registran métricas limpias sin contención de conexiones ni bloqueos.
  * Comando de demostración: make t3-m1.

DIAPOSITIVA 4: Catálogo de las Ocho Fallas Implementadas
- Título: Plataforma de Caos: Catálogo de las Ocho Fallas
- Expositor: Sara López Marín
- Disposición visual: Matriz o tabla de 4 bloques (las 4 familias requeridas por la rúbrica).
- Viñetas:
  * Familia Red (Toxiproxy): Latencia downstream de 150 ms ± 10 ms jitter y estrangulamiento de ancho de banda a 64 kbps.
  * Familia Dependencias: Retardo síncrono simulado de 2.000 ms en Catálogo y mitigación con Circuit Breaker adaptativo.
  * Familia Recursos: Secuestro de pool mediante 4 conexiones zombie con pg_sleep(15) y timeout estricto de adquisición (0.5 s).
  * Familia Estado/Datos: Bloqueo exclusivo pesimista (SELECT FOR UPDATE) sobre proveedor caliente 1 y aborto por lock_timeout (300 ms).
  * Control en caliente: Archivo config_fallas.json sin necesidad de redespliegue de contenedores.

DIAPOSITIVA 5: Falla Combinada en Cascada (Demostración en Vivo)
- Título: Falla Combinada Multivariable y Propagación en Cascada
- Expositor: Luis Alejandro Castrillón Pulgarin
- Disposición visual: Diagrama de flujo secuencial del efecto dominó.
- Viñetas:
  * Inyección simultánea: Latencia Toxiproxy (150 ms) + 2 Zombies en Pool (de 5) + Lock pesimista en Proveedor 1.
  * Propagación en cascada:
    1. La latencia de red hace que cada consulta retenga su conexión 150 veces más tiempo.
    2. Con solo 3 conexiones útiles en el pool, 6 workers saturan la cola en <0.5 s, disparando PoolAgotadoError.
    3. Las órdenes dirigidas al proveedor caliente superan el lock_timeout de 300 ms debido al viaje de red acumulado.
  * Resultado sistémico: Tasa de error salta al 55% y latencia se degrada drásticamente.
  * Comando en vivo: make t3-exp-combinado.

DIAPOSITIVA 6: Diagnóstico con Observabilidad y Reversión en Caliente
- Título: Diagnóstico de Observabilidad y Kill Switch Maestro
- Expositor: Sara López Marín y Luis Alejandro Castrillón Pulgarin
- Disposición visual: 2 columnas (Izquierda: Señales correlacionadas, Derecha: Reversión y datos).
- Viñetas columna 1:
  * Correlación de señales:
    - Prometheus: Salto en bucket de 0.15s en latencia y subida de e3_query_errors_total.
    - Jaeger: Trazas que muestran spans con timeout de adquisición de 500 ms y etiquetas de error.
- Viñetas columna 2:
  * Reversión en caliente mediante Kill Switch: make t3-killswitch.
  * Tiempo de recuperación medido: 0.38 segundos para retirar el toxic y cancelar zombies.
  * Integridad de datos garantizada: Cero filas mutadas o corruptas gracias a transacciones con ROLLBACK forzado.

DIAPOSITIVA 7: Contraste de Hipótesis vs. Resultados Medidos
- Título: Contraste Experimental: Hipótesis vs. Realidad
- Expositor: Sara López Marín
- Disposición visual: Tabla comparativa de 4 filas con columnas: Familia, Hipótesis Previa, Resultado Real, Estado.
- Contenido de la tabla:
  * Red: Hipótesis ~150 ms -> Medido: 152.57 ms p50 (Confirmada).
  * Dependencias: Fail-fast con Circuit Breaker -> Duración cayó de 6.12 s a 0.08 s (Aceleración de 76.5x).
  * Recursos: Saturación por zombies -> 63.3% de errores por timeout controlado (Confirmada).
  * Datos: Absorción de contención -> 7 colisiones absorbidas con backoff exponencial y jitter (Confirmada).

DIAPOSITIVA 8: Decisiones Técnicas que NO Repetiríamos
- Título: Análisis Crítico de Diseño: Qué NO Volveríamos a Hacer
- Expositor: Sara López Marín
- Disposición visual: 3 cajas o paneles de advertencia técnica.
- Viñetas:
  * 1. No instrumentar trazas al 100% sobre microconsultas transaccionales:
    - El SDK de OpenTelemetry añade un overhead de ~0.25 ms por span. En consultas sub-milisegundo de 0.08 ms, la telemetría costaba más que la consulta.
    - Solución productiva: Muestreo de trazas (trace sampling) al 1% o 5%.
  * 2. No implementar validaciones síncronas entre dominios de negocio:
    - El retardo de 2 s en catálogo bloqueó los workers de órdenes.
    - Solución productiva: Comunicación asíncrona basada en eventos (EDA) o réplica local en caché con CQRS.
  * 3. No confiar en los defaults infinitos de bloqueo en PostgreSQL:
    - Sin lock_timeout explícito, los superproveedores pueden colgar el sistema entero.
    - Solución productiva: SET LOCAL lock_timeout estricto con reintentos exponenciales y jitter.

DIAPOSITIVA 9: Optimizaciones Arquitectónicas Implementadas
- Título: Estado Final: Correcciones Arquitectónicas para la Meta del 10%
- Expositor: Luis Alejandro Castrillón Pulgarin
- Disposición visual: 2 tarjetas comparativas (Optimización Q1 y Optimización Q4).
- Viñetas Optimización Q1 (Contrato Vigente):
  * Problema: Consultas repetitivas a la base de datos para validar vigencia de contratos.
  * Solución: Caché LRU en memoria en capa de aplicación con expiración TTL.
  * Impacto: Latencia p50 reducida de 0.081 ms a 0.0018 ms (Mejora del 97.8%).
- Viñetas Optimización Q4 (OTIF y Logística - Hallazgo Incómodo E2):
  * Problema: Agregación masiva de millones de líneas de orden en caliente (203.28 ms).
  * Solución: Read Model precalculado en tabla ordenes.resumen_otif_mensual con índices dedicados.
  * Impacto: Latencia p50 reducida de 203.28 ms a 0.2046 ms (Mejora del 99.9%).

DIAPOSITIVA 10: Tabla Formal de Comparación E2 vs. E3 (Requisito Oficial)
- Título: Evaluación Cuantitativa: Comparativa Oficial E2 vs. E3
- Expositor: Luis Alejandro Castrillón Pulgarin
- Disposición visual: Tabla formal completa que responde al requisito de la rúbrica (Página 5).
- Contenido de la tabla:
  * Columnas: Consulta, Escenario, Métrica, Valor E2, Meta E3 (-10%), E3 Final, ¿Cumple Meta?, Justificación.
  * Fila 1: Q1 | Frío | p50 | 0.081 ms | <= 0.0729 ms | 0.0018 ms | SÍ (97.8%) | Caché LRU L1 en aplicación.
  * Fila 2: Q1 | Caliente | p50 | 0.085 ms | <= 0.0765 ms | 0.0015 ms | SÍ (98.2%) | Resolución directa en memoria.
  * Fila 3: Q4 | Caliente | p50 | 203.28 ms | <= 182.95 ms | 0.2046 ms | SÍ (99.9%) | Read Model proyectado resuelve hallazgo incómodo.
  * Fila 4: Q4 | Frío | p50 | 0.692 ms | <= 0.6228 ms | 0.1549 ms | SÍ (77.6%) | Índice precalculado mensual.
  * Fila 5: Q2 / Q3 / Q5 | Varios | p50 | 0.06 - 0.39 ms | Metas teóricas | 0.30 - 0.42 ms | No aplica | Transparencia técnica: overhead fijo de ~0.25 ms por spans de OpenTelemetry en microconsultas.

DIAPOSITIVA 11: Conclusiones y Demostración Técnica
- Título: Conclusiones del Proyecto Integrador
- Expositor: Sara López Marín y Luis Alejandro Castrillón Pulgarin
- Disposición visual: Resumen en 3 bloques ejecutivos.
- Viñetas:
  * Escalabilidad y datos: El desacoplamiento en 4 esquemas y el modelado Zipfiano permitieron gestionar 5.66 millones de registros de forma robusta.
  * Resiliencia e ingeniería de caos: Se evidenció cómo las fallas se propagan en cascada entre red, recursos y datos, y cómo el aislamiento (bulkheads, timeouts y kill switch) rescata el sistema.
  * Rigor y reproducibilidad: Todo el ciclo cuenta con automatización completa en Makefiles y scripts reproducibles.
  * Espacio abierto para preguntas del docente.
```
