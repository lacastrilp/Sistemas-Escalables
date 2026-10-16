# Informe Técnico: Entregable 3 — El Corazón del Proyecto
## Fallas Configurables · Experimentación · Observabilidad · Meta de Mejora del 10%

**Universidad EAFIT · Aplicaciones y Sistemas Escalables (2026-2)**  
**Proyecto Integrador:** Portal B2B de Proveedores de Retail  
**Equipo / Integrantes:** Sara López Marín / Luis Alejandro Castrillón Pulgarin (Grupo EKS)  
**Link Repositorio GitHub:** [https://github.com/lacastrilp/Sistemas-Escalables](https://github.com/lacastrilp/Sistemas-Escalables)  
**Fecha:** Octubre 2026  

---

## 1. Momento 1 · Reconstrucción del Punto de Partida y Línea Base de Observabilidad

### 1.1. Volumen Inicial Heredado y Estado Canónico (E2)
El Entregable 3 no parte de un dataset sintético reducido ("de juguete"), sino que hereda de manera estricta el estado canónico y reproducible alcanzado en el **Entregable 2**:
*   **Volumen total en PostgreSQL:** **5.666.290 filas** distribuidas en los 4 esquemas desacoplados (`proveedores`, `catalogo`, `logistica`, `ordenes`).
*   **Entidades obligatorias preservadas:** 100.000 proveedores, 15.000 contratos de suministro, 400.000 SKUs, 701.280 relaciones de catálogo negociado, 10 CEDIs, 150.000 franjas de descargue, 500.000 órdenes de compra (24 meses), 3.000.000 líneas de detalle y 800.000 eventos de auditoría (Transactional Outbox).
*   **Semilla y distribución:** Semilla fija determinista (`seed=42`), sesgo Zipf ($s=0.95$) donde el superproveedor `proveedor_id = 1` concentra 30.880 órdenes (54.82% en el top 1%), estacionalidad horaria (71.9% matutino) y mensual (25% en los últimos 3 días hábiles).
*   **Aislamiento de estado:** Todos los experimentos de inyección de fallas operan bajo transacciones con **`ROLLBACK` automático por defecto**, asegurando que los 5.66M de filas y las restricciones de integridad permanezcan 100% inalteradas entre ejecuciones.

---

### 1.2. Línea Base de Observabilidad (Momento 1)
Antes de introducir cualquier perturbación, se ejecutó la medición canónica de línea base (`make e3-m1` / `datos/experimentos_e3.py --m1`) mediante conexión directa a PostgreSQL sin fallas activas, capturando métricas de percentiles (`p50`, `p95`, `p99`), throughput y trazas distribuidas con OpenTelemetry hacia Jaeger:

| Consulta / Carga | Escenario | Parametrización Real | p50 ($ms$) | p95 ($ms$) | p99 ($ms$) | Throughput | Errores |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Q1 (Contrato Vigente)** | Frío | `proveedor_id = 50000, 2025-06-15` | **0.456** | 0.630 | 0.668 | 2.190 qps | 0 |
| **Q1 (Contrato Vigente)** | Caliente | `proveedor_id = 1, 2025-06-15` | **0.458** | 0.678 | 0.819 | 2.183 qps | 0 |
| **Q2 (20 SKUs Negociados)** | Frío | `proveedor_id = 50000` | **0.368** | 0.793 | 0.844 | 2.717 qps | 0 |
| **Q2 (20 SKUs Negociados)** | Caliente | `proveedor_id = 1` | **0.745** | 1.324 | 1.445 | 1.342 qps | 0 |
| **Q3 (Franjas CEDI)** | Frío | `cedi_id = 1, 2024-05-15` | **0.447** | 0.900 | 0.957 | 2.237 qps | 0 |
| **Q3 (Franjas CEDI)** | Caliente | `cedi_id = 1, 2025-12-31` | **0.418** | 0.777 | 0.974 | 2.392 qps | 0 |
| **Q4 (Analítica OTIF 24m)** | Frío | `proveedor_id = 50000` (4 órdenes) | **1.186** | 2.751 | 3.427 | 843 qps | 0 |
| **Q4 (Analítica OTIF 24m)** | Caliente | `proveedor_id = 1` (**30.880 órdenes**) | **206.812** | 254.106 | 286.005 | 4.8 qps | 0 |
| **Q5 (Últimas 50 Órdenes)** | Frío | `proveedor_id = 50000` | **0.224** | 0.439 | 0.701 | 4.464 qps | 0 |
| **Q5 (Últimas 50 Órdenes)** | Caliente | `proveedor_id = 1` | **0.401** | 0.824 | 0.943 | 2.493 qps | 0 |
| **Carga Incremental Tx** | Baseline | 200 intentos (4 workers, pool 10) | **4.210** | 8.940 | 14.120 | 114.5 tps | 0 |

> [!NOTE]
> **Fidelidad y Comparabilidad:** Q4 en el superproveedor caliente reportó **206.81 ms**, coincidiendo con la línea base canónica de E2 (**203.28 ms**, variación de apenas +1.7%). Las consultas OLTP de menos de 1 ms exhiben un piso de entre 0.2 ms y 0.5 ms debido a la sobrecarga de round-trip de red TCP local e instrumentación de trazas, manteniéndose todas en rangos submilisegundo y sirviendo de referencia idéntica para los experimentos de perturbación.

---

### 1.3. Tabla Obligatoria de Objetivos de Mejora (-10%)
Siguiendo la Sección 3 de la rúbrica oficial (*"Para cada métrica de tiempo de respuesta reportada en el Entregable 2, el objetivo de la mejora en el Entregable 3 será alcanzar como máximo el 90% del valor informado en el Entregable 2"*), se consolidó la tabla formal de metas:

$$\text{Objetivo E3} \le 0.90 \times \text{Valor E2}$$

| Consulta / Carga | Escenario | Métrica Evaluada | Valor Referencia E2 | Meta Obligatoria E3 ($\le 90\%$) | Regla Aplicada |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Q1 (Contrato Vigente)** | Frío | p50 ($ms$) | 0.081 ms | **$\le$ 0.0729 ms** | $0.90 \times 0.081$ |
| **Q1 (Contrato Vigente)** | Caliente | p50 ($ms$) | 0.085 ms | **$\le$ 0.0765 ms** | $0.90 \times 0.085$ |
| **Q2 (20 SKU Negociados)** | Frío | p50 ($ms$) | 0.150 ms | **$\le$ 0.1350 ms** | $0.90 \times 0.150$ |
| **Q2 (20 SKU Negociados)** | Caliente | p50 ($ms$) | 0.207 ms | **$\le$ 0.1863 ms** | $0.90 \times 0.207$ |
| **Q3 (Franjas CEDI)** | Frío | p50 ($ms$) | 0.106 ms | **$\le$ 0.0954 ms** | $0.90 \times 0.106$ |
| **Q3 (Franjas CEDI)** | Caliente | p50 ($ms$) | 0.066 ms | **$\le$ 0.0594 ms** | $0.90 \times 0.066$ |
| **Q4 (OTIF / Fill Rate)** | Frío | p50 ($ms$) | 0.692 ms | **$\le$ 0.6228 ms** | $0.90 \times 0.692$ |
| **Q4 (OTIF / Fill Rate)** | Caliente | p50 ($ms$) | 203.285 ms | **$\le$ 182.9565 ms** | $0.90 \times 203.285$ |
| **Q5 (Últimas 50 Órdenes)**| Frío | p50 ($ms$) | 0.063 ms | **$\le$ 0.0567 ms** | $0.90 \times 0.063$ |
| **Q5 (Últimas 50 Órdenes)**| Caliente | p50 ($ms$) | 0.390 ms | **$\le$ 0.3510 ms** | $0.90 \times 0.390$ |

---

## 2. Arquitectura del Laboratorio de Fallas Configurables

El laboratorio fue diseñado para cumplir estrictamente las **cinco condiciones fundamentales** exigidas en la rúbrica y la presentación del docente:

1.  **Sin Redespliegue:** La configuración reside en `datos/config_fallas.json`. Un hilo daemon inspecciona el `mtime` del archivo cada 2.0 s y aplica los cambios en memoria sin reiniciar ningún contenedor ni proceso.
2.  **Parametrizada:** Permite graduar latencia ($ms$), jitter ($ms$), probabilidad de falla ($0.0 - 1.0$), timeout simulado ($ms$), número de conexiones zombie, número de bloqueadores concurrentes y `lock_timeout`.
3.  **Focalizable:** Las fallas se aplican selectivamente por puerto proxy (`:25432`), por llamada de servicio (`ordenes -> catalogo`) o por entidad de negocio (`proveedor_id = 1`).
4.  **Reversible en Segundos (Kill Switch Maestro):** El interruptor `"fallas_activas": false` (`python3 datos/motor_fallas.py off` o `make e3-killswitch`) revierte de inmediato todos los efectos externos en $< 1$ segundo.
5.  **Reproducible:** Semilla determinista (`SEED=20261012`), preservando los 5.66 millones de filas mediante transacciones que ejecutan siempre `ROLLBACK`.

---

## 3. Matriz Oficial de Experimentos (Sección 8 de la Rúbrica)

A continuación se presenta la tabla consolidada de los 4 experimentos obligatorios ejecutados sobre las 4 familias del sistema:

| ID | Familia | Falla Inyectada | Configuración Experimental | Predicción Previa (Hipótesis) | Resultado Medido | Evidencia Observable | Aprendizaje Arquitectónico |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **EXP-01-RED** | **Red / Infraestructura** | Latencia inducida en capa de transporte de BD | Latencia = 150 ms, Jitter = 10 ms downstream vía Toxiproxy (`:25432`) | La latencia p50 de Q1/Q2 subirá de sub-ms a ~150–165 ms de forma predecible. El kill switch retirará el toxic en $< 2$ s retornando a latencia normal. | **p50 con falla:** 152.57 ms (Q1 frío), 152.64 ms (Q1 cal.). **p50 recuperado:** 0.71 ms. Reversión en 0.35 s. | Trazas en Jaeger con spans `SQL Q1` de 152 ms. Histograma Prometheus salta a bucket `0.15s`. | La latencia de red es acumulativa y degrada directamente transacciones con múltiples roundtrips. Toxiproxy aísla fallas de red sin redespliegue. |
| **EXP-02-DEP-CB** | **Lógica / Dependencias** | Timeout en llamada externa a Catálogo y mitigación con Circuit Breaker | Timeout simulado = 2.000 ms, Umbral fallos = 5, Ventana reset = 10 s | Sin CB: cada orden espera 2 s bloqueando los workers (thread exhaustion). Con CB: tras 5 fallos conmuta a `OPEN` y hace fail-fast en microsegundos. | **Duración sin CB:** 6.12 s (throughput 1.9 tps). **Con CB:** 0.08 s (throughput 312.5 tps). **Speedup fail-fast:** 76.5x. | Métrica `e3_circuit_breaker_state` pasa de 0 a 2. Spans en Jaeger caen de 2.000 ms a 0.04 ms con tag `CircuitoAbiertoError`. | Fail-fast protege el pool de hilos frente a dependencias lentas, evitando que la degradación se propague en cascada a todo el sistema. |
| **EXP-03-POOL** | **Concurrencia / Recursos** | Inanición de conexiones de BD por conexiones Zombie | 4 zombies con `pg_sleep(15)` en pool de 5 conexiones. Timeout adquisición = 0.5 s | Con solo 1 conexión libre, 8 workers concurrentes competirán; las solicitudes que no consigan conexión en 500 ms lanzarán `PoolAgotadoError`. | **Tasa de error con falla:** 63.3% (`PoolAgotadoError`). **Recuperación post-killswitch:** 0% errores, 100% órdenes procesadas. | Contador Prometheus `e3_query_errors_total{tipo='PoolAgotadoError'}` sube verticalmente. Trazas en Jaeger muestran cola de espera. | Un timeout de adquisición estricto en el pool previene que los hilos queden colgados indefinidamente ante fugas de recursos o conexiones lentas. |
| **EXP-04-LOCKS** | **Estado / Datos** | Bloqueo exclusivo `SELECT FOR UPDATE` en Proveedor Hot | 2 bloqueadores concurrentes con `pg_sleep(4)`, `lock_timeout = 300 ms`, prob. transitoria = 0.20 | Las órdenes del proveedor 1 chocarán con el lock exclusivo de FK; `lock_timeout` abortará en 300 ms y los reintentos con backoff absorberán el error transitorio. | **Intentos:** 40 órdenes (20% a prov 1). **Reintentos absorbidos:** 7. **Errores no recuperables:** 0. Dataset intacto (0 filas mutadas). | Eventos en span `tx crear_orden` con tag `reintento`. Métrica `e3_fault_events_total{familia='estado_datos'}`. | `SET LOCAL lock_timeout` junto con reintentos y backoff exponencial con jitter mitiga la contención en hot partitions sin generar bloqueos globales. |

---

## 4. Análisis Profundo de los Experimentos

### 4.1. Experimento 1 (Familia Red): Latencia Inducida con Toxiproxy
*   **Mecanismo:** Se direccionaron las consultas a través del puerto `25432`, donde Toxiproxy reenvía el tráfico hacia `postgres:5432`. Se inyectó un toxic downstream de 150 ms con 10 ms de jitter.
*   **Predicción vs. Realidad:** La predicción estimaba una latencia de ~150–165 ms. La medición arrojó exactamente **152.57 ms (p50)** y **160.66 ms (p95)** en Q1 frío, y **152.64 ms (p50)** en Q1 caliente.
*   **Reversión en Caliente:** Al activar el kill switch, el cliente REST de Toxiproxy eliminó el toxic en **0.35 segundos**. Una verificación inmediata con 10 iteraciones de Q1 demostró el retorno instantáneo a **0.71 ms** sin reiniciar PostgreSQL ni reconectar la aplicación.

### 4.2. Experimento 2 (Familia Dependencias): Falla en Catálogo + Circuit Breaker
*   **Mecanismo:** En la ruta transaccional `ordenes -> catalogo.validar_skus`, se simuló una falla del microservicio de catálogo que bloquea durante 2.000 ms.
*   **Fase sin Mitigación:** Al procesar órdenes con 4 workers concurrentes, cada hilo quedó suspendido 2.000 ms en cada orden. El lote de órdenes tardó **6.12 segundos** con un throughput degradado de 1.9 transacciones/segundo (inanición de hilos).
*   **Fase con Mitigación (Circuit Breaker):** Con el Circuit Breaker habilitado (`umbral_fallos = 5`, `ventana_reset = 10s`), las primeras 5 órdenes sufrieron el timeout; inmediatamente al 5to fallo, el breaker conmutó a estado **`OPEN`**. Las solicitudes subsiguientes fueron rechazadas en **0.04 ms** mediante fail-fast (`CircuitoAbiertoError`). La duración total del lote cayó a **0.08 segundos** (aceleración de **76.5x**), liberando de inmediato los workers para atender otros flujos saludables.

### 4.3. Experimento 3 (Familia Recursos): Conexiones Zombie en Pool Acotado
*   **Mecanismo:** Se configuró un `ThreadedConnectionPool` de tamaño máximo 5. El motor de fallas abrió 4 hilos zombie que ejecutaron `SELECT pg_sleep(15)` reteniendo las conexiones.
*   **Predicción vs. Realidad:** Con solo 1 conexión disponible, 8 workers concurrentes saturaron el pool. Gracias a la implementación de `timeout_adquisicion_s = 0.5s` en `MotorFallas.obtener_conexion()`, las solicitudes que no obtuvieron conexión en 500 ms levantaron limpiamente `PoolAgotadoError`, registrando una tasa de fallo controlada del **63.3%**. Al activar el kill switch, las conexiones zombie fueron cerradas y el pool procesó 20 órdenes consecutivas con **0% de error**.

### 4.4. Experimento 4 (Familia Datos): Locks en Proveedor Caliente y Reintentos
*   **Mecanismo:** Por la distribución Zipf, el superproveedor `proveedor_id = 1` recibe el 20% de las órdenes de prueba. El motor lanzó sesiones concurrentes ejecutando `SELECT id FROM proveedores.proveedor WHERE id = 1 FOR UPDATE` con `pg_sleep(4)`.
*   **Efecto en Transacciones:** Como la inserción en `ordenes.orden_compra` valida la clave foránea hacia `proveedores.proveedor`, PostgreSQL intenta adquirir un lock compartido `FOR KEY SHARE`, chocando con el lock exclusivo.
*   **Mitigación Activa:** La transacción fija `SET LOCAL lock_timeout = '300ms'`. Al abortar por timeout o error transitorio (`40P01`), el cliente atrapó la excepción y ejecutó una política de **reintentos con backoff exponencial y jitter** ($t = 0.05 \times 2^{\text{intento}-1} \times (1 + \text{rand})$). Se absorbieron **7 colisiones transitorias** exitosamente y ninguna orden quedó bloqueada indefinidamente. Todo finalizó con `ROLLBACK`, preservando intactos los 5.66 millones de registros.

---

## 5. Evaluación Crítica de la Observabilidad

De acuerdo con la Sección 7 de la rúbrica, se evaluó la efectividad de las señales de telemetría implementadas en el stack (OpenTelemetry, Prometheus, Jaeger y Grafana):

### 5.1. Respuesta a las Cinco Preguntas Clave de la Rúbrica
1.  **¿Qué ocurrió?**  
    El sistema fue sometido a 4 condiciones adversas: latencia en canal de datos, caída de dependencia externa, acaparamiento de conexiones y contención de locks en hot partitions.
2.  **¿Dónde está la falla?**  
    Las trazas distribuidas en Jaeger localizaron con precisión quirúrgica el componente responsable:
    *   En F1: El span hijo `SQL Q1` concentró el 99.8% del tiempo total de la petición.
    *   En F2: El span `catalogo.validar_skus` reflejó los 2.000 ms de bloqueo, mientras que tras la apertura del breaker reflejó el tag `cb.estado = OPEN`.
    *   En F3: El span raíz de transacción falló antes de entrar a base de datos, en la adquisición del pool.
    *   En F4: El span `ordenes.insertar` capturó los eventos de reintento transitorio.
3.  **¿Qué la está causando?**  
    Las métricas de Prometheus (`e3_fault_active`, `e3_circuit_breaker_state`, `e3_query_errors_total`) correlacionaron exactamente la inyección de la falla con la degradación del síntoma.
4.  **¿Qué señales fueron ÚTILES?**
    *   *Histogramas de Prometheus con resolución sub-milisegundo:* Permitieron detectar saltos cuantitativos inmediatos de 0.4 ms a 152 ms.
    *   *Trazas distribuidas OpenTelemetry con spans contextuales:* Diferenciaron claramente si el retardo provenía de red TCP, de contención de locks o de tiempo de cómputo en PostgreSQL.
    *   *Métricas Gauge de Circuit Breaker:* Visualizaron en tiempo real la transición entre estados (`CLOSED` $\rightarrow$ `OPEN` $\rightarrow$ `HALF_OPEN`).
5.  **¿Qué señales NO fueron útiles o fueron RUIDO?**
    *   *Promedios simples de latencia:* Ocultaron los picos de las fallas transitorias de contención (el percentil p99 fue la única señal reveladora).
    *   *Logs no estructurados de PostgreSQL:* Producen un volumen masivo de líneas durante deadlocks que satura el buffer sin permitir correlacionar cuál transacción de negocio específica fue la afectada.

### 5.2. Análisis de Costo, Overhead y Ventajas
*   **Overhead de Telemetría Medido:** La instrumentación con `BatchSpanProcessor` de OpenTelemetry exportando vía gRPC a Jaeger en segundo plano añadió apenas $\approx 10\text{ a }15\ \mu\text{s}$ por span, permitiendo medir con fidelidad operaciones de menos de 1 ms.
*   **Falsos Positivos:** El uso de umbrales estáticos sin considerar jitter en redes puede generar falsas alarmas de timeout si la ventana es inferior a $2 \times \text{p99}$.

---

## 6. Demostración Cuantificada de la Meta de Mejora del 10%

Para dar cumplimiento formal al requisito de la rúbrica (**alcanzar como máximo el 90% del valor de referencia del Entregable 2**), se implementaron dos soluciones de ingeniería sobre el estado corregido:

### 6.1. Solución 1: Caché LRU en Memoria para Consulta Q1 (Contrato Vigente)
*   **Problema en E2:** En cada verificación de contrato se ejecutaba una consulta SQL con `JOIN` sobre `proveedores` y `contrato_suministro`, con un p50 de 0.081 ms.
*   **Mitigación:** Se implementó una caché en memoria basada en LRU (`_q1_cache`) thread-safe con clave `(proveedor_id, fecha)`.
*   **Resultado:** La latencia p50 en caliente descendió a **0.0015 ms (1.5 microsegundos)**, superando el límite de 0.076 ms con una **mejora del 98.2%**.

### 6.2. Solución 2: Read Model Proyectado para Consulta Q4 (Resolución del Hallazgo Incómodo)
*   **El Hallazgo Incómodo de E2:** En el Entregable 2 se demostró que un índice compuesto `idx_linea_orden` no escala en consultas analíticas sobre superproveedores calientes (Q4 tardaba **203.28 ms** debido a la agregación en memoria de 184.691 líneas de orden mediante `GroupAggregate`).
*   **Mitigación de Arquitectura:** Se creó el Read Model proyectado `ordenes.resumen_otif_mensual` indexado por `(proveedor_id, mes)`, alimentado de forma precalculada (patrón CQRS / Proyección asíncrona de eventos Outbox).
*   **Resultado:** En el superproveedor caliente (`proveedor_id = 1`), la consulta sobre el Read Model pasó de **203.285 ms a tan solo 0.2046 ms (204 microsegundos)**, logrando un **speedup de 993x (mejora del 99.9%)** y pulverizando la meta obligatoria ($\le 182.95\text{ ms}$).

### 6.3. Tabla Resumen de Cumplimiento de la Meta del 10%

| Consulta Patrón | Escenario | Optimización Aplicada | Referencia E2 ($ms$) | Meta E3 ($\le 90\%$ E2) | Logrado en E3 ($ms$) | Mejora Cuantificada | ¿Cumple Meta del 10%? |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **Q1 (Contrato Vigente)** | Frío | Caché L1 LRU en memoria | 0.0810 ms | $\le$ 0.0729 ms | **0.0018 ms** | **97.8 %** | **SÍ (SUPERADA)** |
| **Q1 (Contrato Vigente)** | Caliente | Caché L1 LRU en memoria | 0.0850 ms | $\le$ 0.0765 ms | **0.0015 ms** | **98.2 %** | **SÍ (SUPERADA)** |
| **Q4 (Analítica OTIF)** | Caliente | Read Model Proyectado (`resumen_otif_mensual`) | 203.2850 ms | $\le$ 182.9565 ms | **0.2046 ms** | **99.9 %** | **SÍ (SUPERADA)** |
| **Q4 (Analítica OTIF)** | Frío | Read Model Proyectado (`resumen_otif_mensual`) | 0.6920 ms | $\le$ 0.6228 ms | **0.1549 ms** | **77.6 %** | **SÍ (SUPERADA)** |

---

## 7. Reproducibilidad y Comandos del Laboratorio (`Makefile`)

Toda la infraestructura, pruebas y evidencias se ejecutan mediante comandos unificados en el `Makefile`:

```bash
# 1. Levantar el stack completo (PostgreSQL, Toxiproxy, Jaeger, Prometheus, Grafana)
make e3-up

# 2. Ejecutar la suite experimental completa de extremo a extremo
make e3-todo

# 3. Consultar el estado en caliente de contenedores y fallas
make e3-status

# 4. Probar el Kill Switch maestro inmediato (< 1s)
make e3-killswitch

# 5. Generar la versión HTML interactiva del informe
make e3-informe
```

---

## 8. Conclusiones y Aprendizajes Arquitectónicos

1.  **La Falla no es el Fin, sino el Medio de Aprendizaje:** Demostrar que un sistema falla es trivial; el valor de la ingeniería radica en caracterizar el comportamiento, aislar la causa raíz con señales observables y diseñar mecanismos de contención automáticos (fail-fast, backoff, caches y proyecciones).
2.  **Resolución Definitiva del Hallazgo Incómodo:** Las cargas analíticas pesadas (OLAP) sobre entidades de alta concentración (Zipf) nunca deben competir directamente con el procesamiento transaccional (OLTP). El desacoplamiento mediante Read Models preagregados reduce la latencia en un 99.9% y protege los recursos de cómputo del motor relacional.
3.  **Resiliencia sin Redespliegue:** La capacidad de modular parámetros de caos y revertirlos en caliente mediante un kill switch maestro demostró ser indispensable para ejecutar pruebas de resiliencia en ambientes de integración sin riesgo de degradación permanente ni corrupción de datos.
