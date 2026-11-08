# Guión de Presentación y Sustentación (15 Minutos)
## Portal B2B Retail: Arquitectura, Escalabilidad y Observabilidad
### Universidad EAFIT - Aplicaciones y Sistemas Escalables (2026-2)
**Integrantes:** Sara López Marín y Luis Alejandro Castrillón Pulgarin (Grupo EKS)

---

## Estructura General y Distribución del Tiempo

| Minuto | Sección | Diapositiva | Expositor | Acción / Demostración Técnica |
| :---: | :--- | :---: | :---: | :--- |
| **00:00 - 02:00** | Introducción y Arquitectura Base | Diapositiva 1 y 2 | Sara | Presentación del equipo y regla de los 4 esquemas |
| **02:00 - 04:30** | Estado Inicial y Línea Base | Diapositiva 3 | Alejandro | Ejecución de `make t3-m1` y Grafana en reposo |
| **04:30 - 08:30** | Fallas en Vivo y Observabilidad | Diapositiva 4, 5 y 6 | Sara y Alejandro | Ejecución de `make t3-exp-combinado`, Jaeger y Kill Switch |
| **08:30 - 11:30** | Análisis Crítico y Aprendizajes | Diapositiva 7 y 8 | Sara | Las 3 decisiones que no repetiríamos |
| **11:30 - 14:00** | Optimizaciones y Tabla E2 vs E3 | Diapositiva 9 y 10 | Alejandro | Tabla formal de métricas (Q1 caché 98%, Q4 read model 99.9%) |
| **14:00 - 15:00** | Conclusiones y Preguntas | Diapositiva 11 | Sara y Alejandro | Cierre y paso a preguntas del docente |

---

## Guión Paso a Paso Minuto a Minuto

### Minuto 0:00 a 2:00 · Introducción y Arquitectura (Sara)
- **Diapositiva:** 1 (Portada) y 2 (Arquitectura del Monolito Modular)
- **Qué decir:**
  > "Buenos días profesor. Nuestro proyecto es el Portal B2B de Retail, un sistema que modela el aprovisionamiento masivo entre una cadena de supermercados y su red de proveedores comerciales.
  > 
  > A nivel de datos, el sistema corre sobre PostgreSQL 16 con una regla estricta de diseño: implementamos un monolito modular dividido en 4 esquemas desacoplados: proveedores, catálogo, logística y órdenes. No permitimos ningún `JOIN` entre esquemas; todas las relaciones inter-módulo se preservan como identificadores lógicos de tipo `BIGINT`. Esto nos permite aislar fallas y preparar el terreno para una eventual extracción a microservicios.
  > 
  > El sistema fue probado con 5.66 millones de registros sintéticos reales, modelando una distribución Zipfiana con parámetro 1.2 donde pocos proveedores concentran la mayor parte de las órdenes, tal como ocurre en el retail real."

---

### Minuto 2:00 a 4:30 · Estado Inicial y Línea Base (Alejandro)
- **Diapositiva:** 3 (Línea Base y Condiciones de Medición)
- **Acción en vivo:**
  - Ejecutar en la terminal: `make t3-m1`
  - Mostrar la pestaña de Grafana (`http://localhost:3000`).
- **Qué decir:**
  > "Para evaluar el sistema, primero reconstruimos la línea base reproducible antes de introducir cualquier perturbación.
  > 
  > Como se puede observar en la terminal tras ejecutar `make t3-m1`, nuestras consultas principales Q1 a Q5 responden de manera consistente en sub-milisegundos, con latencias p50 entre 0.08 ms y 0.48 ms. 
  > 
  > En la pantalla de Grafana podemos ver que el sistema está completamente operativo: la tasa de error es del 0%, el throughput es estable y no hay conexiones retenidas ni bloqueos en base de datos. Este es el punto de partida contra el cual mediremos el impacto del caos."

---

### Minuto 4:30 a 8:30 · Inyección de Fallas en Vivo y Observabilidad (Sara y Alejandro)
- **Diapositivas:** 4 (Catálogo de 8 Fallas), 5 (Falla Combinada en Cascada), 6 (Diagnóstico y Kill Switch)
- **Sara (Explicación conceptual de las fallas):**
  > "En el proyecto implementamos 8 fallas configurables distribuidas en las 4 familias exigidas: en red implementamos latencia y ancho de banda limitado con Toxiproxy; en dependencias simulamos lentitud en catálogo y un Circuit Breaker; en recursos inyectamos conexiones zombie y agotamiento de pool; y en datos generamos contención con locks pesimistas y `lock_timeout`.
  > 
  > Para la demostración en vivo, decidimos ir más allá de probarlas aisladas y configuramos un escenario de falla combinada donde interactúan tres familias al tiempo."
- **Alejandro (Ejecución en vivo y observabilidad):**
  - Ejecutar en la terminal: `make t3-exp-combinado`
  - Abrir la pestaña de Jaeger (`http://localhost:16686`).
  - **Qué decir:**
    > "Acabo de disparar el experimento combinado. En este momento, Toxiproxy está inyectando 150 ms de latencia downstream en la conexión de base de datos; al mismo tiempo, 2 conexiones zombie están ocupando un pool acotado de 5 conexiones, y un worker mantiene un `SELECT FOR UPDATE` sobre el Proveedor 1.
    > 
    > Miren lo que sucede en la terminal: la tasa de error sube de inmediato al 55%. ¿Por qué? Porque la latencia de red de 150 ms hace que cada consulta retenga la conexión 150 veces más tiempo. Con solo 3 conexiones útiles disponibles, los 6 workers concurrentes saturan la cola en menos de 0.5 segundos y se disparan excepciones de `PoolAgotadoError`. Además, las órdenes que intentan entrar al Proveedor 1 superan el `lock_timeout` de 300 ms y abortan.
    > 
    > Si pasamos a Jaeger, en esta traza vemos con claridad cómo el span de adquisición de pool muestra la cola de espera de 500 ms marcada con error, mientras los spans SQL registran el incremento de 150 ms causado por el proxy."
- **Sara (Reversión y Kill Switch):**
  - Ejecutar en la terminal: `make t3-killswitch`
  - **Qué decir:**
    > "Para mitigar esto en caliente sin reiniciar la base de datos, ejecutamos el Kill Switch maestro. En 0.38 segundos, la API de Toxiproxy retiró el toxic y el motor cerró los hilos zombie. 
    > 
    > Inmediatamente corremos una verificación limpia y vemos que la tasa de error vuelve al 0% y las latencias vuelven a menos de 1 ms. Muy importante: como todas las operaciones de prueba se ejecutan con `ROLLBACK`, los 5.66 millones de registros de la base de datos permanecen exactamente intactos."

---

### Minuto 8:30 a 11:30 · Análisis Crítico y Aprendizajes (Sara)
- **Diapositivas:** 7 (Hipótesis vs Resultados) y 8 (Decisiones que NO repetiríamos)
- **Qué decir:**
  > "Uno de los aspectos más valiosos del laboratorio fue contrastar nuestras hipótesis con la realidad y reconocer errores de diseño. Hay tres decisiones técnicas que identificamos con claridad y que no repetiríamos en un entorno productivo:
  > 
  > Primero: no instrumentaríamos trazas OpenTelemetry al 100% sobre microconsultas de base de datos. En consultas transaccionales simples que tardan 0.08 ms en PostgreSQL, el código del cliente Python tardaba cerca de 0.25 ms generando spans, tomando marcas de tiempo y exportando trazas. Es decir, la observabilidad costaba tres veces más que la consulta misma. La solución real en producción es aplicar muestreo de trazas (trace sampling) al 1% o 5%.
  > 
  > Segundo: no usaríamos dependencias síncronas entre órdenes y catálogo. Cuando el servicio de catálogo sufrió un retardo de 2 segundos, los hilos de órdenes se congelaron y tumbaron el throughput a 1.9 transacciones por segundo. Con el Circuit Breaker logramos un fail-fast a 0.08 segundos, pero la lección arquitectónica de fondo es que la validación de catálogo debe desacoplarse mediante eventos asíncronos o una réplica local en caché con CQRS.
  > 
  > Tercero: nunca depender de los valores por defecto de PostgreSQL para bloqueos. Por defecto, `lock_timeout` es infinito. Sin un timeout explícito, un bloqueo sobre el superproveedor habría paralizado todo el sistema. Establecer `SET LOCAL lock_timeout = '300ms'` junto con reintentos con backoff exponencial y jitter fue indispensable para que el sistema absorbiera las colisiones sin caídas."

---

### Minuto 11:30 a 14:00 · Correcciones Finales y Tabla E2 vs E3 (Alejandro)
- **Diapositivas:** 9 (Soluciones Arquitectónicas) y 10 (Tabla Oficial E2 vs E3)
- **Qué decir:**
  > "Para cumplir con la meta obligatoria de la rúbrica de reducir el tiempo de respuesta en al menos un 10% respecto al Entregable 2, implementamos dos optimizaciones concretas:
  > 
  > Para la consulta Q1 (validación de contrato vigente), implementamos una caché LRU en memoria en la capa de aplicación con expiración TTL. En la tabla comparativa se evidencia que la latencia p50 pasó de 0.081 ms a 0.0018 ms en frío y 0.0015 ms en caliente. Esto representa una mejora del 97.8% y 98.2%, superando con creces la meta del 10%.
  > 
  > Para la consulta Q4, abordamos lo que en el Entregable 2 llamamos 'el hallazgo incómodo': el cálculo de indicadores de entrega OTIF tardaba 203.28 ms porque requería agregar millones de líneas de orden en caliente. La solución fue diseñar un Read Model precalculado en la tabla `ordenes.resumen_otif_mensual`. Con esto, la consulta pasó de 203.28 ms a 0.2046 ms, logrando una reducción del 99.9% (casi 1.000 veces más rápida).
  > 
  > Queremos ser muy transparentes con el jurado sobre Q2, Q3 y Q5: como se observa en la tabla, estas consultas muestran latencias ligeramente superiores a E2 debido al overhead del SDK de telemetría que explicamos antes. No quisimos apagar artificialmente OpenTelemetry para falsear los números; demostramos con rigor técnico que en Q1 y Q4 las mejoras de arquitectura superaron la meta, y que en microconsultas el camino es el muestreo."

---

### Minuto 14:00 a 15:00 · Conclusión y Cierre (Sara y Alejandro)
- **Diapositiva:** 11 (Conclusiones y Lecciones del Proyecto)
- **Qué decir:**
  > "En conclusión, el proyecto integrador nos permitió vivir el ciclo completo de la ingeniería de sistemas escalables: desde el diseño con esquemas desacoplados y el manejo de 5.66 millones de registros con distribución Zipfiana, hasta la resiliencia bajo fallas combinadas en cascada y la justificación cuantitativa de mejoras de latencia.
  > 
  > El repositorio cuenta con Makefiles y scripts reproducibles para auditar cada uno de estos resultados. Muchas gracias por su atención y quedamos atentos a sus preguntas."
