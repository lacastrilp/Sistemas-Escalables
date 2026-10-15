# Matriz de Trazabilidad: Entregable 2 — Escalabilidad de los Datos

**Universidad EAFIT · Aplicaciones y Sistemas Escalables**  
**Proyecto Integrador: Portal B2B de Proveedores de Retail**  
**Equipo:** Sara Lopez Marin / Luis Alejandro Castrillon Pulgarin (Grupo EKS)  
**Versión:** 2.0 (Auditoría Integral y Verificación Real)  
**Fecha:** Octubre 2026  

---

## 1. Resumen por Criterio de la Rúbrica de Calificación

| Criterio | Peso | Requisito Principal | Estado Inicial | Estado Final | Evidencia Principal |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **C1. Volumen del conjunto y modelo físico** | 15% | Superar volumen objetivo (proveedores: 100k, contratos: 15k, SKUs: 400k, órdenes: 500k, líneas: 3M, franjas: 150k, eventos: 800k). 4 esquemas independientes sin JOIN inter-esquema. | `PARCIAL` | **`CUMPLE`** | `datos/output/conteos/conteo_tablas.json`, `modelo-fisico.sql` |
| **C2. Sesgo, estacionalidad y casos borde** | 20% | Sesgo Zipf en proveedores (top 1% $\ge 15\%$, top 5% $\ge 40\%$), sesgo SKU (10% SKU en $\ge 60\%$ líneas), estacionalidad mensual (~25%) y horaria (pico 8-11am), 8 casos borde con predicados SQL. | `PARCIAL` | **`CUMPLE`** | `datos/output/resumen_final.json`, `datos/output/grafica_*.png` |
| **C3. Generador determinista y parametrizable** | 10% | Generador determinista por streaming a CSV (`--seed 42`), parametrizable, aritmética de IDs para FK, validación con checksum SHA-256 idéntico en dos corridas. | `PARCIAL` | **`CUMPLE`** | `datos/output/determinismo/hashes_comparacion.json` |
| **C4. Estrategia de inyección y carga medida** | 20% | Medición de 4 estrategias sobre muestra común de 50.000 órdenes (351.428 filas). Inyección incremental de 5.000 órdenes adicionales vía ruta real con reglas de negocio. | `PARCIAL` | **`CUMPLE`** | `datos/output/benchmark_carga_resultados.json`, `datos/output/carga_incremental_resultados.json` |
| **C5. Medición de consultas con percentiles y planes** | 25% | Consultas Q1–Q5 medidas con 200 iteraciones en frío y en caliente (p50, p95, p99, promedio). `EXPLAIN (ANALYZE, BUFFERS)` antes y después de `idx_orden_proveedor_fecha` e `idx_linea_orden`. | `PARCIAL` | **`CUMPLE`** | `datos/output/benchmark_queries_resultados.json`, `datos/output/explain/*.txt` |
| **C6. Reproducibilidad, evidencia y hallazgo** | 10% | Un solo comando (`make datos`) levanta y ejecuta todo desde cero en máquina limpia. Docker compose con healthcheck y socket UNIX. Evidencia cruda completa en `datos/output/`. | `PARCIAL` | **`CUMPLE`** | `Makefile`, `docker-compose.yml`, `docs/README_REPRODUCCION.md` |

---

## 2. Matriz Detallada de Requisitos y Evidencias Reales

| ID Requisito HTML | Descripción del Requisito | Archivo / Target | Estado Final | Valor / Métrica Lograda | Comando Automatizado | Ruta de Evidencia Final |
| :--- | :--- | :--- | :---: | :--- | :--- | :--- |
| **REQ-VOL-01** | Proveedores $\ge 100\,000$ (obj: 100k) | `proveedores.proveedor` | **`CUMPLE`** | **100 000** filas | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-02** | Contratos de suministro $\ge 15\,000$ (obj: 15k) | `proveedores.contrato_suministro` | **`CUMPLE`** | **15 000** filas | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-03** | SKUs del catálogo $\ge 400\,000$ (obj: 400k) | `catalogo.sku` | **`CUMPLE`** | **400 000** filas | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-04** | Órdenes de compra 24 meses $\ge 500\,000$ (obj: 500k) | `ordenes.orden_compra` | **`CUMPLE`** | **500 000** (+4 006 incr) | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-05** | Líneas de orden $\ge 3\,000\,000$ (obj: 3M) | `ordenes.linea_orden` | **`CUMPLE`** | **3 000 000** (+16 041 incr) | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-06** | Franjas de descargue $\ge 150\,000$ (obj: 150k) | `logistica.franja_descargue` | **`CUMPLE`** | **150 000** filas | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-07** | Eventos de auditoría $\ge 800\,000$ (obj: 800k) | `ordenes.evento_auditoria` | **`CUMPLE`** | **800 000** (+4 006 incr) | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-08** | CEDIs $\ge 5$ (obj: 5) | `logistica.cedi` | **`CUMPLE`** | **10** CEDIs activos | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-09** | Relaciones Proveedor–SKU medidas aparte | `catalogo.proveedor_sku` | **`CUMPLE`** | **701 280** relaciones | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-VOL-TOT** | Suma total de entidades con objetivo | BD PostgreSQL | **`CUMPLE`** | **4 965 010** (obj: 4.965.005) | `make verificar` | `datos/output/conteos/conteo_tablas.json` |
| **REQ-ESQ-01** | 4 esquemas independientes sin JOIN inter-esquema | `modelo-fisico.sql` | **`CUMPLE`** | `proveedores, catalogo, logistica, ordenes` | `make verificar` | `modelo-fisico.sql` |
| **REQ-COB-01** | Cobertura de proveedores con contrato ~12%-15% | `datos/verificar.py` | **`CUMPLE`** | **15.00%** (15k prov con contrato) | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-SES-01** | Sesgo Zipf Proveedor: Top 1% $\ge 15\%$, Top 5% $\ge 40\%$ | `datos/generar.py` | **`CUMPLE`** | Top 1% = **54.82%**, Top 5% = **69.83%** | `make verificar` | `datos/output/grafica_zipf.png` |
| **REQ-SES-02** | Sesgo SKU: 10% SKU en $\ge 60\%$ líneas | `datos/generar.py` | **`CUMPLE`** | Top 10% SKU = **61.98%** de líneas | `make verificar` | `datos/output/grafica_concentracion_sku.png` |
| **REQ-EST-01** | Estacionalidad mensual: últimos 3 días hábiles $\approx 25\%$ | `datos/generar.py` | **`CUMPLE`** | **25.0%** en 24 meses exactos | `make verificar` | `datos/output/grafica_estacionalidad_diaria.png` |
| **REQ-EST-02** | Estacionalidad horaria: pico 8-11am ($>70\%$), valle ($<5\%$) | `datos/generar.py` | **`CUMPLE`** | Pico = **71.92%**, Valle = **4.03%** | `make verificar` | `datos/output/grafica_estacionalidad_horaria.png` |
| **REQ-BORD-01** | Caso 1: Orden con exactamente 300 líneas | `ordenes.linea_orden` | **`CUMPLE`** | `orden_id = 1` tiene 300 líneas | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-02** | Caso 2: Contrato vencido ayer | `proveedores.contrato_suministro` | **`CUMPLE`** | `contrato_id = 1` (`2025-12-30 23:59:59`) | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-03** | Caso 3: Contrato que vence hoy al mediodía (12:00) | `proveedores.contrato_suministro` | **`CUMPLE`** | `contrato_id = 2` (`2025-12-31 12:00:00`) | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-04** | Caso 4: Última franja con 1 cupo libre | `logistica.franja_descargue` | **`CUMPLE`** | `franja_id = 150000` (cap=10, res=9) | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-05** | Caso 5: Proveedor sin contrato vigente | `proveedores.proveedor` | **`CUMPLE`** | `proveedor_id = 15001` sin contrato | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-06** | Caso 6: Orden con SKU fuera de catálogo | `ordenes.linea_orden` | **`CUMPLE`** | `orden_id = 435, sku_id = 289101` | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-07** | Caso 7: Proveedor hot con $\ge 5\,000$ órdenes | `ordenes.orden_compra` | **`CUMPLE`** | `proveedor_id = 1` (**30 880 órdenes**) | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-BORD-08** | Caso 8: Proveedor activo sin órdenes en mes completo | `ordenes.orden_compra` | **`CUMPLE`** | `proveedor_id = 410` en 2024-01 | `make verificar` | `datos/output/resumen_final.json` |
| **REQ-DET-01** | Determinismo con semilla 42 y hashes SHA-256 | `datos/verificar_determinismo.py` | **`CUMPLE`** | 100% hashes idénticos en 2 corridas | `make determinismo` | `datos/output/determinismo/hashes_comparacion.json` |
| **REQ-CARG-01** | COPY masivo cronometrado por tabla | `datos/cargar.sh` | **`CUMPLE`** | 5.66M filas en **97s** (**58 415 filas/s**) | `make cargar` | `datos/output/tiempos_carga.json` |
| **REQ-CARG-02** | 4 estrategias sobre muestra común (351.428 filas) | `datos/benchmark_carga.py` | **`CUMPLE`** | COPY: 37k, Batch: 15.7k, Auto: 967, App: 2.2k | `make benchmark-carga` | `datos/output/benchmark_carga_resultados.json` |
| **REQ-CARG-03** | Inyección incremental de 5.000 órdenes vía ruta real | `datos/carga_incremental.py` | **`CUMPLE`** | 4.006 aceptadas, 994 rechazadas, 0 sobreventas | `make carga-incremental` | `datos/output/carga_incremental_resultados.json` |
| **REQ-QRY-01** | Q1: Proveedor y contrato vigente $< 10$ ms | `datos/benchmark_queries.py` | **`CUMPLE`** | p50 = **0.081 ms** (frío) / **0.085 ms** (caliente) | `make benchmark-queries` | `datos/output/benchmark_queries_resultados.json` |
| **REQ-QRY-02** | Q2: 20 SKUs negociados | `datos/benchmark_queries.py` | **`CUMPLE`** | p50 = **0.150 ms** (frío) / **0.207 ms** (caliente) | `make benchmark-queries` | `datos/output/benchmark_queries_resultados.json` |
| **REQ-QRY-03** | Q3: Franjas disponibles CEDI | `datos/benchmark_queries.py` | **`CUMPLE`** | p50 = **0.106 ms** (frío) / **0.066 ms** (caliente) | `make benchmark-queries` | `datos/output/benchmark_queries_resultados.json` |
| **REQ-QRY-04** | Q4: OTIF y Fill Rate 24 meses (Analítica) | `datos/benchmark_queries.py` | **`CUMPLE`** | p50 = **0.692 ms** (frío) / **203.285 ms** (caliente) | `make benchmark-queries` | `datos/output/benchmark_queries_resultados.json` |
| **REQ-QRY-05** | Q5: Últimas 50 órdenes paginadas | `datos/benchmark_queries.py` | **`CUMPLE`** | p50 = **0.063 ms** (frío) / **0.390 ms** (caliente) | `make benchmark-queries` | `datos/output/benchmark_queries_resultados.json` |
| **REQ-EXP-01** | EXPLAIN (ANALYZE, BUFFERS) antes y después | `datos/benchmark_queries.py` | **`CUMPLE`** | Evidencia completa guardada en archivos TXT | `make benchmark-queries` | `datos/output/explain/*.txt` |
| **REQ-REP-01** | Comando único de orquestación `make datos` | `Makefile` | **`CUMPLE`** | Flujo completo de extremo a extremo | `make datos` | `Makefile` |
| **REQ-REP-02** | Prueba limpia en entorno aislado `make clean-test` | `Makefile` | **`CUMPLE`** | Docker Compose efímero con log guardado | `make clean-test` | `datos/output/logs/clean_test.log` |
