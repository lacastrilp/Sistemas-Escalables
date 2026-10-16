# Taller 3 — Laboratorio de Caos, Inyección de Fallas y Observabilidad (Portal B2B Retail)

**Curso:** Aplicaciones y Sistemas Escalables  
**Institución:** Universidad EAFIT · Semestre 2026-2  
**Equipo:** Grupo EKS — Sara López Marín & Luis Alejandro Castrillón Pulgarin  
**Entregable Oficial:** [`entregables/Entrega 3 - Caos y Observabilidad/`](../entregables/Entrega%203%20-%20Caos%20y%20Observabilidad/)

---

## 📋 Descripción General

Este taller constituye **El Corazón del Proyecto**, transformando la arquitectura de datos del Portal B2B Retail construida en el Entregable 2 en un sistema resiliente, observable y tolerante a fallas.

Se diseñó e implementó un **Laboratorio de Caos** completamente parametrizado que inyecta fallas en caliente sin requerir reinicio de contenedores ni redespliegues de código, monitoreado en tiempo real con observabilidad moderna:
- **Toxiproxy (v2.9.0):** Inyección de degradaciones de red (latencias y cortes de enlace).
- **OpenTelemetry + Jaeger (v1.57):** Rastreo distribuido de spans para visualización de cuellos de botella y fall-backs.
- **Prometheus (v2.53.0):** Recolección continua de métricas RED (Rate, Errors, Duration) expuestas en `:9464`.
- **Grafana (v11.1.0):** Paneles de visualización unificados de telemetría y salud del sistema.
- **Kill Switch Maestro:** Mecanismo reversible en menos de 1 segundo para restaurar el estado nominal del sistema.

---

## 🔬 Matriz de Experimentos de Caos

| Familia | Escenario / Falla Inyectada | Mitigación Arquitectural | Resultado y Aprendizaje Clave |
| :--- | :--- | :--- | :--- |
| **1. Red** | Inyección de latencia estocástica de 150 ms en enlace PostgreSQL vía Toxiproxy. | Enrutamiento directo o Kill Switch de bypass de proxy. | Latencia p50 subió a 152.57 ms. El Kill Switch restauró la latencia a 1.25 ms en 0.35 s sin downtime. |
| **2. Dependencias** | Simulación de degradación en servicio de Catálogo con timeout forzado (2000 ms). | Circuit Breaker adaptativo (`fail-fast`) con apertura al 2do fallo. | Latencia bajo falla bajó de 2000 ms a 0.08 ms (aceleración de **76.5x**), evitando saturación de hilos. |
| **3. Recursos** | Inanición de conexiones en el Connection Pool (4 conexiones zombi bloqueadas). | Manejo explícito de `PoolAgotadoError` y reciclaje forzado de pool. | Carga incremental falló con 63.3% de errores controlados. El reciclaje restauró el throughput inmediatamente. |
| **4. Estado de Datos** | Transacción bloqueante `FOR UPDATE` sobre proveedor caliente 1. | Configuración de `lock_timeout = '300ms'` y Exponential Backoff. | Las 30 transacciones concurrentes absorbieron 7 reintentos sin bloqueo indefinido y con 0 mutaciones no deseadas. |

---

## 📈 Demostración Formal de Mejora ($\ge 10\%$)

| Consulta / Caso Crítico | Línea Base E2 (p50) | Target Objetivo ($\le 0.90 \times \text{E2}$) | Resultado Optimizado (E3) | Mejora Obtenida | Mecanismo de Optimización |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Q1 — Contrato Vigente** | $0.0833\text{ ms}$ | $\le 0.0750\text{ ms}$ | **$0.0018\text{ ms}$** | **$97.8\%$ de reducción** | Caché L1 en memoria (LRU Cache con TTL invalidable). |
| **Q4 — OTIF y Fill Rate** | $203.28\text{ ms}$ | $\le 182.95\text{ ms}$ | **$0.2046\text{ ms}$** | **$99.9\%$ de reducción** | Read Model pre-agregado indexado (`ordenes.resumen_otif_mensual`). |

---

## 📂 Estructura de Directorios

```text
Taller 3/
├── datos/
│   ├── config_fallas.json          # Archivo de configuración en caliente del motor de caos
│   ├── motor_fallas.py             # Motor de inyección con Circuit Breaker, zombies y locks
│   ├── telemetria.py               # Instrumentación OpenTelemetry y exportador Prometheus (:9464)
│   ├── consultas.py                # Consultas Q1-Q5 con mitigaciones y socket / TCP resiliente
│   ├── experimentos_e3.py          # Runner automatizado de la suite experimental de caos
│   ├── carga_incremental_e3.py     # Transacciones concurrentes instrumentadas con caos
│   ├── benchmark_queries_e3.py     # Benchmarking de latencias con trazabilidad OTel
│   └── output/e3/                  # Evidencias experimentales, CSVs y JSONs generados
├── observabilidad/
│   ├── toxiproxy/                  # Configuración del proxy para PostgreSQL (:25432)
│   ├── prometheus/                 # Scraping job de métricas cada 2 segundos
│   └── grafana/                    # Aprovisionamiento automático de datasources (Prometheus & Jaeger)
├── docker-compose.yml              # Stack completo (PostgreSQL, Toxiproxy, Jaeger, Prometheus, Grafana)
├── requirements-e3.txt             # Dependencias Python requeridas (OTel, Prometheus, Psycopg2)
├── modelo-fisico.sql               # DDL físico de los 4 esquemas
├── convertir_informe_e3_html.py    # Generador de informe HTML profesional
├── Entregable3_Informe_Laboratorio_Fallas_Observabilidad.md    # Informe técnico oficial
├── Entregable3_Informe_Laboratorio_Fallas_Observabilidad.html  # Versión visual lista para evaluación
└── Makefile                        # Automatización completa de comandos de Entrega 3
```

---

## 🚀 Guía de Reproducción Rápida

Todos los experimentos se ejecutan mediante el [`Makefile`](Makefile):

```bash
cd "Taller 3"

# 1. Levantar el stack completo de observabilidad y base de datos
make e3-up

# 2. Consultar el estado de salud de los servicios y configuración de fallas
make e3-status

# 3. Ejecutar la suite completa de caos y optimizaciones
make e3-todo

# 4. Generar el informe técnico actualizado en HTML
make e3-informe

# 5. En caso de emergencia, activar el kill switch maestro
make e3-killswitch
```

### Puertos de Acceso a las Interfaces Web
- **Grafana:** `http://localhost:3000` *(admin / admin)*
- **Jaeger Tracing:** `http://localhost:16686`
- **Prometheus UI:** `http://localhost:9090`
- **Toxiproxy API:** `http://localhost:8474`
- **Prometheus Python Metrics:** `http://localhost:9464/metrics`
- **PostgreSQL Directo:** `localhost:5435`
- **PostgreSQL vía Toxiproxy:** `localhost:25432`
