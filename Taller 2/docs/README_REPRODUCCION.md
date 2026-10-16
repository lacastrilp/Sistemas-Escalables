# Guía de Reproducción: Entregable 2 — Escalabilidad de los Datos

**Universidad EAFIT · Aplicaciones y Sistemas Escalables**  
**Proyecto Integrador: Portal B2B de Proveedores de Retail**  
**Autores:** Sara Lopez Marin / Luis Alejandro Castrillon Pulgarin (Grupo EKS)  

---

## 1. Prerrequisitos de la Máquina

- **Docker y Docker Compose:** Docker 24+ con plugin `docker compose`.
- **Python:** Python 3.10 o superior.
- **Bibliotecas Python:**
  ```bash
  pip install psycopg2-binary matplotlib numpy markdown
  ```
- **Make y Bash:** Herramientas estándar de terminal Linux/Unix.

---

## 2. Reproducción Rápida con un Solo Comando

Para ejecutar todo el pipeline de generación masiva, carga en PostgreSQL, verificación de integridad, benchmarks de inyección y consultas, y generación de gráficas de evidencia:

```bash
make datos
```

Este único comando orquesta de manera secuencial y determinista:
1. `make db-up`: Inicia PostgreSQL y espera hasta que el healthcheck reporte estado `healthy`.
2. `make db-reset`: Aplica `modelo-fisico.sql` para preparar los 4 esquemas limpios (`proveedores`, `catalogo`, `logistica`, `ordenes`).
3. `make generar`: Genera por streaming a CSV los 5.66 millones de registros con semilla determinista (`--seed 42`), Zipf ($s=0.95$), estacionalidad y los 8 casos borde.
4. `make determinismo`: Demuestra determinismo ejecutando dos generaciones aisladas y comparando hashes SHA-256.
5. `make cargar`: Ejecuta carga masiva con `COPY`, ejecuta `ANALYZE` baseline, crea los índices secundarios post-carga y ejecuta `ANALYZE` final.
6. `make verificar`: Audita directamente en PostgreSQL los conteos contra mínimos y objetivos, Zipf, estacionalidad, los 8 casos borde y checksums.
7. `make benchmark-carga`: Evalúa las 4 estrategias de inyección sobre la muestra común de 50.000 órdenes y 301.428 líneas.
8. `make carga-incremental`: Inyecta 5.000 órdenes adicionales vía ruta transaccional real aplicando reglas de negocio retail.
9. `make benchmark-queries`: Mide 200 iteraciones por consulta (Q1–Q5) en frío y caliente y genera los planes `EXPLAIN (ANALYZE, BUFFERS)` antes y después.
10. `make graficas`: Genera las 6 figuras PNG y CSVs de datos en `datos/output/`.

---

## 3. Simulación de Máquina Limpia Aislada

Para certificar la reproducibilidad en un entorno completamente aislado sin riesgo de afectar otros contenedores o volúmenes existentes:

```bash
make clean-test
```

Este comando levanta un proyecto Docker Compose temporal (`entregable2_clean_*`) con volumen efímero, ejecuta `make datos` completo, guarda el log íntegro en `datos/output/logs/clean_test.log` y destruye el entorno temporal al terminar.

---

## 4. Estructura de Salidas y Evidencias Crudas

```text
datos/output/
├── cedi.csv
├── contratos.csv
├── skus.csv
├── proveedor_sku.csv
├── franjas.csv
├── ordenes.csv
├── lineas_orden.csv
├── eventos.csv
├── checksums.sha256
├── resumen_generacion.json
├── resumen_final.json
├── tiempos_carga.json
├── benchmark_carga_resultados.json
├── carga_incremental_resultados.json
├── benchmark_queries_resultados.json
├── conteos/
│   └── conteo_tablas.json
├── determinismo/
│   └── hashes_comparacion.json
├── estrategias/
│   └── resultados_inyeccion.csv
├── queries/
│   ├── resumen_latencias_q1_q5.csv
│   └── observaciones_latencias.csv
├── explain/
│   ├── q4_antes_indices.txt
│   ├── q5_antes_indices.txt
│   ├── q4_despues_idx_orden_proveedor_fecha.txt
│   ├── q5_despues_idx_orden_proveedor_fecha.txt
│   ├── q4_despues_idx_linea_orden.txt
│   └── resumen_comparacion_indices.json
└── graficas/
    ├── grafica_zipf.png
    ├── grafica_concentracion_sku.png
    ├── grafica_estacionalidad_diaria.png
    ├── grafica_estacionalidad_horaria.png
    ├── grafica_estrategias_inyeccion.png
    ├── grafica_latencias_consultas.png
    └── datos_*.csv
```

---

## 5. Variables de Configuración

Si se requiere ejecutar contra un PostgreSQL externo o en otro puerto, configure las variables de entorno:
- `DB_HOST`: Host de PostgreSQL (default: `127.0.0.1`).
- `DB_PORT`: Puerto de PostgreSQL (default: `5435`).
- `DB_USER`: Usuario (default: `retail`).
- `DB_PASS`: Contraseña (default: `retail`).
- `DB_NAME`: Base de datos (default: `retail`).
