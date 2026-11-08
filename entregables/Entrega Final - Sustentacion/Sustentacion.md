# Sustentación - Proyecto Integrador
## Portal B2B Retail: Arquitectura, Escalabilidad y Observabilidad
### Universidad EAFIT - Aplicaciones y Sistemas Escalables (2026-2)
**Integrantes:** Sara López Marín y Luis Alejandro Castrillón Pulgarin (Grupo EKS)  
**Evaluación:** Presentación Final (100 Puntos)

---

## 1. Resumen del Proyecto y Arquitectura

El sistema corresponde a un Portal B2B de Retail que gestiona órdenes de compra, catálogos y entregas entre un retail y sus proveedores comerciales.

### Arquitectura de Base de Datos
- **Monolito modular en PostgreSQL 16:** Implementa 4 esquemas desacoplados:
  - `proveedores` (`proveedor`, `contrato_suministro`)
  - `catalogo` (`sku`, `proveedor_sku`)
  - `logistica` (`cedi`, `franja_descargue`)
  - `ordenes` (`orden_compra`, `linea_orden`, `evento_auditoria`)
- **Regla estricta de diseño:** Cero `JOIN`s inter-esquemas. Las dependencias entre dominios solo se guardan como llaves foráneas lógicas (`BIGINT`).
- **Volumen de datos:** 5.66 millones de registros generados sintéticamente con distribución Zipfiana ($s=1.2$) para simular proveedores calientes (superproveedores como Nestlé o Alpina) y una larga cola de proveedores pequeños, además de estacionalidad temporal y casos borde reales.

### Stack de Infraestructura y Observabilidad
- **Base de datos:** PostgreSQL 16 (`localhost:5435`).
- **Inyección de fallas de red:** Toxiproxy (`localhost:8474` API, `localhost:25432` proxy a BD).
- **Métricas:** Prometheus (`localhost:9090`) y Grafana (`localhost:3000`).
- **Trazas distribuidas:** Jaeger all-in-one con OpenTelemetry (`localhost:16686`).
- **Motor de caos:** `motor_fallas.py` con configuración en caliente vía `config_fallas.json` y Kill Switch maestro.

---

## 2. Criterio 1: Catálogo de las Ocho Fallas y Efecto en Cascada (25 Puntos)

### 2.1. Las Ocho Fallas del Sistema (2 por Familia)

| Familia | ID | Falla | Mecanismo | Efecto en la Aplicación |
| :--- | :---: | :--- | :--- | :--- |
| **Red / Infraestructura** | **F1.1** | Latencia de red | Toxic downstream de 150 ms ± 10 ms jitter en Toxiproxy | Aumenta el tiempo de roundtrip en cada consulta SQL. |
| | **F1.2** | Ancho de banda limitado | Toxic bandwidth a 64 kbps en Toxiproxy | Congestiona transferencias de lotes de líneas de orden. |
| **Lógica / Dependencias** | **F2.1** | Timeout en Catálogo | Bloqueo síncrono simulado de 2.000 ms en validación de SKUs | Inanición de hilos en la API de órdenes de compra. |
| | **F2.2** | Circuito Abierto | Conmutación de Circuit Breaker a estado OPEN tras 5 fallos | Fail-fast inmediato (< 1 ms) devolviendo `CircuitoAbiertoError`. |
| **Concurrencia / Recursos** | **F3.1** | Conexiones Zombie | Hilos concurrentes reteniendo conexiones con `pg_sleep(15)` | Ocupa 4 de las 5 conexiones del pool disponible. |
| | **F3.2** | Agotamiento de Pool | Timeout de adquisición de 500 ms en el connection pool | Solicitudes que no obtienen conexión fallan con `PoolAgotadoError`. |
| **Estado / Datos** | **F4.1** | Lock Pesimista Hot | `SELECT FOR UPDATE` concurrente en Proveedor 1 | Bloquea la fila del superproveedor impidiendo validaciones. |
| | **F4.2** | Aborto por lock_timeout | Configuración de `SET LOCAL lock_timeout = '300ms'` | Cancela la transacción si el bloqueo supera los 300 ms (código `55P03`). |

### 2.2. Combinación de Fallas y Propagación en Cascada (EXP-05-COMBINADO)

Para la sustentación en vivo, se ejecuta una combinación de tres familias al tiempo:
1. **Red:** Latencia de 150 ms en Toxiproxy (`F1.1`).
2. **Recursos:** 2 conexiones zombie ocupando un pool de 5 (`F3.1`).
3. **Datos:** Lock pesimista en Proveedor 1 (`F4.1`).

**¿Cómo se propaga la falla en cascada?**
- En condiciones normales, una consulta a base de datos toma menos de 1 ms. Al inyectar 150 ms de latencia de red, cada worker retiene su conexión en el pool durante cientos de milisegundos.
- Como 2 conexiones del pool están secuestradas por hilos zombie, solo quedan 3 conexiones útiles.
- Cuando llegan múltiples órdenes concurrentes, la cola de espera del pool se llena de inmediato y supera el timeout de adquisición (0.5 s), provocando una oleada de excepciones `PoolAgotadoError` (tasa de error del 55%).
- Al mismo tiempo, las órdenes que sí logran conexión e intentan validar al Proveedor 1 chocan contra el lock pesimista. Debido a que el viaje de red ya consumió 150 ms, el límite de `lock_timeout = 300ms` se agota casi de inmediato, abortando las transacciones.
- **Conclusión:** Una lentitud de red a nivel de infraestructura multiplicó la contención de datos y colapsó los recursos de la aplicación.

### 2.3. Señales de Observabilidad Correlacionadas
- **Prometheus:** Subida del histograma `e3_query_latency_seconds` al bucket de 0.15s y salto vertical en `e3_query_errors_total{tipo="PoolAgotadoError"}`.
- **Jaeger:** Trazas con spans `adquirir_conexion_pool` superando los 500 ms con tag `error=true` y spans SQL con duración de ~152 ms.
- **Logs:** Mensajes estructurados indicando la aplicación del toxic, la captura de `PoolAgotadoError` y el disparo del Kill Switch.

---

## 3. Criterio 2: Reproducción de Fallas en Vivo y Estado Inicial (25 Puntos)

### 3.1. Preparación del Entorno
Antes de iniciar la exposición, tener los contenedores activos:
```bash
make t3-up
make t3-status
```
Tener abiertas en el navegador las pestañas de Grafana (`http://localhost:3000`) y Jaeger (`http://localhost:16686`).

### 3.2. Paso a Paso de la Demostración

1. **Estado Inicial (Línea Base Sin Fallas):**
   ```bash
   make t3-m1
   ```
   - Mostrar en terminal y en Grafana que las consultas Q1 a Q5 corren en sub-milisegundos y con 0% de errores.
2. **Inyección de la Falla Combinada en Vivo:**
   ```bash
   make t3-exp-combinado
   ```
   - Mostrar en la terminal cómo la tasa de error sube al 55% por saturación del pool y cómo las órdenes absorben reintentos.
3. **Diagnóstico con Observabilidad:**
   - En Jaeger, abrir la traza más reciente del servicio `portal-b2b-lab-e3` y mostrar la acumulación de tiempo entre el pool y la red.
   - En Grafana, mostrar la gráfica de errores y el salto en latencia.
4. **Reversión con el Kill Switch:**
   ```bash
   make t3-killswitch
   ```
   - Mostrar que el comando apaga el toxic de Toxiproxy y cancela los zombies en **0.38 segundos**.
   - Mostrar en la salida que la medición limpia posterior vuelve a **0% de error** y latencia normal, manteniendo los **5.66M registros intactos** (las pruebas usan transacciones con `ROLLBACK`).

---

## 4. Criterio 3: Análisis de Resultados y Aprendizajes (20 Puntos)

### 4.1. Contraste de Hipótesis vs. Mediciones

- **Red (Toxiproxy):** Hipótesis de subida a ~150 ms confirmada (resultado medido: 152.57 ms en p50). Reversión confirmada en 0.35 s.
- **Dependencias (Catálogo + CB):** Hipótesis de fail-fast confirmada. Sin Circuit Breaker el lote tardó 6.12 s; con Circuit Breaker bajó a 0.08 s (**aceleración de 76.5x**).
- **Recursos (Pool Zombies):** Hipótesis confirmada. La inanición causó 63.3% de rechazos controlados por timeout de 0.5 s.
- **Datos (Locks Hot):** Hipótesis confirmada. Se absorbieron 7 reintentos con backoff exponencial y jitter sin colapsar el sistema.

### 4.2. Decisiones Técnicas que NO Repetiríamos y Lecciones de Diseño

1. **No instrumentar trazas al 100% en microconsultas de base de datos:**
   - En queries muy rápidas (como Q1 o Q3 que tardan 0.08 ms en Postgres), la sobrecarga de crear spans en Python y propagar contexto añade ~0.25 ms. Es decir, la telemetría costaba más que la propia consulta.
   - *Qué haríamos en producción:* Configurar muestreo de trazas (*trace sampling*) al 1% o 5% en operaciones normales y solo muestrear al 100% cuando haya errores o latencias altas.
2. **No usar acoplamiento síncrono entre órdenes y catálogo:**
   - En el diseño inicial, la validación de SKUs se hacía llamando directamente al servicio de catálogo en la misma petición HTTP. Cuando el catálogo tuvo un retardo de 2 s, todos los hilos de la aplicación se bloquearon.
   - *Qué haríamos en producción:* Usar comunicación asíncrona mediante eventos (ej. Kafka o RabbitMQ) o una copia local en caché de solo lectura con CQRS.
3. **No depender del timeout por defecto de PostgreSQL:**
   - Por defecto `lock_timeout` es 0 (espera infinita). Si una transacción bloquea un registro caliente, cuelga a todas las demás.
   - *Qué haríamos en producción:* Establecer siempre `SET LOCAL lock_timeout = '300ms'` acompañado de reintentos exponenciales con jitter.

---

## 5. Criterio 4: Correcciones Finales y Comparativa E2 vs E3 (30 Puntos)

### 5.1. Justificación de las Optimizaciones Implementadas

1. **Caché LRU en memoria para Consulta Q1 (Contrato Vigente):**
   - Se implementó una caché L1 en Python con política LRU y expiración TTL para evitar consultar repetidamente `proveedores.contrato_suministro`.
   - La latencia p50 pasó de **0.081 ms a 0.0018 ms** (reducción del **97.8%** en frío y **98.2%** en caliente).
2. **Read Model Proyectado para Consulta Q4 (OTIF y Logística):**
   - En el Entregable 2, Q4 era el «hallazgo incómodo» porque tardaba **203.28 ms** al agregar millones de líneas de orden en caliente.
   - Se creó una tabla proyectada (`ordenes.resumen_otif_mensual`) que mantiene los cálculos preagregados por mes y proveedor.
   - La latencia p50 bajó de **203.28 ms a 0.2046 ms**, logrando una mejora del **99.9%** (más de 990 veces más rápida).

---

### 5.2. Tabla Oficial de Comparación E2 vs. E3

| Consulta | Escenario | Métrica | Valor E2 | Meta E3 (-10%) | E3 Línea Base | E3 Optimizado (Final) | ¿Cumple Meta? | Análisis Técnico |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Q1** | **Frío** | **p50** | 0.081 ms | $\le$ 0.0729 ms | 0.2620 ms | **0.0018 ms** | **SÍ** | Caché LRU en memoria elimina roundtrips a BD. |
| **Q1** | **Caliente** | **p50** | 0.085 ms | $\le$ 0.0765 ms | 0.2763 ms | **0.0015 ms** | **SÍ** | Resolución en memoria en nanosegundos. |
| **Q1** | **Frío** | **p95** | 0.292 ms | $\le$ 0.2628 ms | 1.3656 ms | **0.0042 ms** | **SÍ** | Estabilidad total en la cola de latencia. |
| **Q4** | **Caliente** | **p50** | 203.28 ms | $\le$ 182.95 ms | 209.22 ms | **0.2046 ms** | **SÍ** | Read model proyectado resuelve el hallazgo incómodo. |
| **Q4** | **Frío** | **p50** | 0.692 ms | $\le$ 0.6228 ms | 0.7446 ms | **0.1549 ms** | **SÍ** | Consulta sobre índice de resumen precalculado. |
| **Q4** | **Caliente** | **p95** | 220.45 ms | $\le$ 198.40 ms | 248.57 ms | **0.4810 ms** | **SÍ** | Elimina consumo intensivo de CPU en PostgreSQL. |
| **Q2** | **Frío** | **p50** | 0.150 ms | $\le$ 0.1350 ms | 0.4098 ms | 0.4098 ms | *No aplica* | Consulta sin caché: la sobrecarga del SDK de Jaeger suma ~0.25 ms. |
| **Q3** | **Caliente** | **p50** | 0.066 ms | $\le$ 0.0594 ms | 0.3033 ms | 0.3033 ms | *No aplica* | Refleja el overhead fijo de spans en operaciones ultra-cortas. |
| **Q5** | **Caliente** | **p50** | 0.390 ms | $\le$ 0.3510 ms | 0.4262 ms | 0.4262 ms | *No aplica* | En producción se soluciona con muestreo de trazas (sampling). |

---

## 6. Comandos Rápidos de Terminal para la Sustentación

```bash
# 1. Levantar el stack completo (Postgres, Toxiproxy, Jaeger, Prometheus, Grafana)
make t3-up

# 2. Verificar estado de contenedores
make t3-status

# 3. Fase 1: Línea base y estado inicial
make t3-m1

# 4. Fase 2: Ejecutar falla combinada en vivo (Red + Pool + Locks)
make t3-exp-combinado

# 5. Fase 3: Kill switch (apagar fallas en < 1 segundo)
make t3-killswitch

# 6. Fase 4: Demostración de mejoras cuantitativas E2 vs E3 (Q1 y Q4)
make t3-mejora
```
