# Portal B2B Retail — Arquitectura, Escalabilidad y Observabilidad

**Universidad EAFIT**  
**Materia:** Aplicaciones y Sistemas Escalables (2026-2)  
**Grupo:** EKS  
**Integrantes:**  
- **Sara López Marín**  
- **Luis Alejandro Castrillón Pulgarin**  

---

## Descripción del Proyecto

El **Portal B2B Retail** es un sistema de integración y aprovisionamiento entre un operador masivo de comercio y su red de proveedores comerciales. A lo largo del semestre, el sistema se diseñó, implementó, escaló y sometió a ingeniería de caos bajo los más altos estándares de arquitectura de software y datos:

1. **Entrega 1 — Diseño Arquitectónico:** Especificación de dominio, patrones de integración desacoplados, modelo relacional formal y contrato de interfaces OpenAPI para el endpoint crítico `POST /ordenes-compra/{id}/confirmación`.
2. **Entrega 2 / Taller 2 — Escalabilidad de Datos Masivos:** Generación sintética determinista e ingesta masiva de **5.66 millones de registros** en PostgreSQL sobre 4 esquemas independientes, benchmarking de ingesta (`COPY` vs transacciones) y optimización de consultas analíticas/transaccionales (Q1 a Q5).
3. **Entrega 3 / Taller 3 — Laboratorio de Caos y Observabilidad:** Plataforma de ingeniería de resiliencia con observabilidad completa (Prometheus, Jaeger, Grafana, Toxiproxy), inyección controlada de fallas en 4 familias (Red, Dependencias, Recursos, Estado de Datos), Kill Switch maestro en caliente y demostración formal de cumplimiento del umbral de mejora ($\ge 10\%$).

---

## Estructura Unificada del Repositorio

El repositorio se encuentra estrictamente organizado en dos niveles: los **Entregables Oficiales** (documentos de diseño e informes técnicos) y el **Código Fuente de los Talleres**


## Resumen de Entregables e Informes Técnicos

| Entregable | Formato Principal | Ruta en el Repositorio | Descripción / Hito Evaluativo |
| :--- | :---: | :--- | :--- |
| **Entrega 1** | PDF | [`entregables/Entrega 1 - Diseno/`](entregables/Entrega%201%20-%20Diseno/Portal_B2B_Retail_Documento_Diseno.pdf) | Arquitectura de dominio, especificación OpenAPI, diagramas C4 y modelo relacional. |
| **Entrega 2** | HTML / MD | [`entregables/Entrega 2 - Escalabilidad de Datos/`](entregables/Entrega%202%20-%20Escalabilidad%20de%20Datos/Entregable2_Informe_Escalabilidad_de_Datos.html) | Población de 5.66M registros, modelos físicos desacoplados, benchmarking Q1 a Q5 y planes `EXPLAIN`. |
| **Entrega 3** | HTML / MD | [`entregables/Entrega 3 - Caos y Observabilidad/`](entregables/Entrega%203%20-%20Caos%20y%20Observabilidad/Entregable3_Informe_Laboratorio_Fallas_Observabilidad.html) | Laboratorio de caos, inyección Toxiproxy/OTel, Circuit Breakers, mitigaciones y validación de mejora $\ge 10\%$. |
| **Sustentación Final** | HTML / MD | [`entregables/Entrega Final - Sustentacion/`](entregables/Entrega%20Final%20-%20Sustentacion/Sustentacion.html) | **Sustentación del Proyecto Integrador:** Guía de defensa, guión de 15 minutos, demostración en vivo, análisis crítico y comparativa E2 vs E3. |

---

## Matriz de Experimentos de Caos (Entrega 3)

| Familia de Falla | Inyección Aplicada | Mitigación Implementada | Evidencia Cuantitativa |
| :--- | :--- | :--- | :--- |
| **1. Red** | Latencia estocástica de 150 ms en enlace PostgreSQL (Toxiproxy). | Bypass de enlace proxy / Kill Switch en caliente. | p50 subió a 152.57 ms. Reversión instantánea a 1.25 ms en **0.35 s** sin reiniciar servicios. |
| **2. Dependencias** | Simulación de saturación en Catálogo con timeout de 2000 ms. | Circuit Breaker adaptativo con apertura rápida al 2do fallo consecutivo. | Latencia bajó de 2000 ms a 0.08 ms (**76.5x más rápido**), protegiendo los hilos del servidor. |
| **3. Recursos** | Bloqueo por inanición de conexiones (4 conexiones zombi en pool de 5). | Manejo de excepción `PoolAgotadoError` y reciclaje forzado de pool. | 63.3% de fallos controlados bajo inanición. Reanudación inmediata al drenar las conexiones zombi. |
| **4. Estado de Datos** | Transacción `FOR UPDATE` bloqueante sobre proveedor caliente 1. | Configuración de `lock_timeout = '300ms'` y reintentos con Exponential Backoff. | 30 hilos completaron absorbiendo 7 reintentos sin bloqueo indefinido y garantizando 0 mutaciones espurias. |

---

## Demostración Cuantitativa de Mejora ($\ge 10\%$)

| Caso / Consulta Crítica | Línea Base E2 (p50) | Umbral Requerido ($\le 0.90 \times \text{E2}$) | Resultado Medido (E3) | Reducción Real | Mecanismo de Optimización |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Q1 — Contrato Vigente** | $0.0833\text{ ms}$ | $\le 0.0750\text{ ms}$ | **$0.0018\text{ ms}$** | **$97.8\%$ de mejora** | Caché L1 en memoria (LRU Cache con TTL e invalidación dirigida). |
| **Q4 — OTIF y Fill Rate** | $203.28\text{ ms}$ | $\le 182.95\text{ ms}$ | **$0.2046\text{ ms}$** | **$99.9\%$ de mejora** | Read Model pre-agregado indexado (`ordenes.resumen_otif_mensual`). |

---

## Guía Rápida de Comandos (Master Makefile)

El archivo [`Makefile`](Makefile) en la raíz del repositorio permite controlar cualquier fase del proyecto:

### Comandos Generales
```bash
make help               # Despliega el catálogo completo de comandos organizados por taller
```

### Comandos de Entrega 3 (Caos y Observabilidad)
```bash
make t3-up              # Levanta Postgres, Toxiproxy, Jaeger, Prometheus y Grafana
make t3-status          # Inspecciona el estado de los contenedores y del motor de fallas
make t3-todo            # Ejecuta la suite experimental completa de caos y optimización
make t3-informe         # Compila el informe técnico oficial de Entrega 3 a HTML
make t3-killswitch      # Desactiva de inmediato todas las fallas inyectadas (< 1 s)
make t3-down            # Detiene los contenedores preservando los datos
```

### Comandos de Entrega 2 (Escalabilidad de Datos)
```bash
make t2-up              # Levanta PostgreSQL en el puerto 5435
make t2-datos           # Ejecuta el flujo integral: generación, carga de 5.66M y benchmarks
make t2-verificar       # Audita conteos, reglas de negocio y distribución Zipfiana
make t2-benchmark       # Ejecuta benchmarks de consultas Q1-Q5 con EXPLAIN ANALYZE
make t2-informe         # Compila el informe técnico de Entrega 2 a HTML
```

### Comandos de Taller 1 (Infraestructura y Replicación)
```bash
make t1-standalone-up   # Levanta entorno standalone para pruebas de índices
make t1-cluster-up      # Levanta clúster de 3 nodos con streaming replication
make t1-cluster-down    # Detiene clúster de Taller 1
```

---

## URLs de Acceso a Servicios Locales

Una vez iniciado el stack de Entrega 3 (`make t3-up`), las consolas de observabilidad están disponibles en:

| Servicio | URL Local | Credenciales / Uso |
| :--- | :--- | :--- |
| **Grafana** | `http://localhost:3000` | `admin` / `admin` (Dashboards aprovisionados) |
| **Jaeger UI** | `http://localhost:16686` | Trazas distribuidas OpenTelemetry |
| **Prometheus** | `http://localhost:9090` | Métricas y gráficos de series temporales |
| **Métricas Python** | `http://localhost:9464/metrics` | Endpoint scraping de Prometheus |
| **Toxiproxy API** | `http://localhost:8474` | API HTTP de control de inyección de latencia |
| **PostgreSQL Directo** | `localhost:5435` | `retail` / `retail` (`db: retail`) |
| **PostgreSQL con Toxiproxy** | `localhost:25432` | Canal controlado para simulación de degradaciones |

---
