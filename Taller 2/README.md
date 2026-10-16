# Taller 2 — Escalabilidad de Datos Masivos (Portal B2B Retail)

**Curso:** Aplicaciones y Sistemas Escalables  
**Institución:** Universidad EAFIT · Semestre 2026-2  
**Equipo:** Grupo EKS — Sara López Marín & Luis Alejandro Castrillón Pulgarin  
**Entregable Oficial:** [`entregables/Entrega 2 - Escalabilidad de Datos/`](../entregables/Entrega%202%20-%20Escalabilidad%20de%20Datos/)

---

## 📋 Descripción General

Este taller implementa la capa de datos a gran escala para el **Portal B2B Retail**, poblando una base de datos PostgreSQL con más de **5.66 millones de registros** sintéticos realistas. Se evalúan arquitecturas desacopladas sin JOINs inter-esquema, estrategias de ingesta masiva (COPY vs INSERTs transaccionales) y se optimizan las consultas analíticas y transaccionales críticas del negocio (Q1 a Q5).

### Métricas Clave del Dataset
- **Total de registros inyectados:** 5,666,000+ filas.
- **Distribución de demanda:** Sesgo Zipfiano realista ($s=1.2$) en proveedores y SKUs calientes.
- **Estacionalidad:** Variaciones diarias y horarias modelando picos comerciales reales.
- **Desacoplamiento:** 4 esquemas independientes (`proveedores`, `catalogo`, `logistica`, `ordenes`) sin claves foráneas inter-módulo en base de datos.

---

## 📂 Estructura de Directorios

```text
Taller 2/
├── datos/
│   ├── generar.py                  # Generador sintético reproducible con semilla fija (5.66M filas)
│   ├── cargar.sh                   # Script de carga masiva vía COPY + creación de índices
│   ├── verificar.py                # Auditoría de integridad, volúmenes, Zipf y casos borde
│   ├── verificar_determinismo.py   # Validación de determinismo estricto (SHA-256)
│   ├── benchmark_carga.py          # Comparación de 4 estrategias de inyección (COPY, transacciones, etc.)
│   ├── carga_incremental.py        # Inyección concurrente de 5.000 órdenes adicionales
│   ├── benchmark_queries.py        # Medición p50/p95/p99 y EXPLAIN (ANALYZE, BUFFERS) Q1-Q5
│   ├── generar_graficas.py         # Generación de gráficos de latencias y distribuciones
│   ├── sql/
│   │   ├── esquema.sql             # Script envolvente del DDL
│   │   └── indices_secundarios.sql # Índices secundarios creados post-carga
│   └── output/                     # CSVs sintéticos, métricas JSON, planes EXPLAIN y gráficas PNG
├── docs/
│   ├── MATRIZ_TRAZABILIDAD_ENTREGABLE2.md  # Matriz de cumplimiento de requisitos
│   └── README_REPRODUCCION.md              # Bitácora detallada de reproducción
├── docker-compose.yml              # Contenedor PostgreSQL 16 con puerto 5435
├── modelo-fisico.sql               # DDL físico de los 4 esquemas desacoplados
├── convertir_informe_html.py       # Conversor del informe técnico a HTML estilizado
├── Entregable2_Informe_Escalabilidad_de_Datos.md    # Informe técnico completo
├── Entregable2_Informe_Escalabilidad_de_Datos.html  # Versión HTML con diseño moderno
├── Guia_Defensa_Entregable2.md     # Guía rápida para sustentar la entrega
└── Makefile                        # Automatización de tareas (make datos, etc.)
```

---

## 🚀 Guía de Reproducción Rápida

Todo el taller está automatizado a través del [`Makefile`](Makefile):

```bash
cd "Taller 2"

# 1. Levantar el servicio PostgreSQL
make db-up

# 2. Ejecutar el flujo completo de extremo a extremo
# (Generación sintética -> Determinismo -> Carga masiva -> Verificación -> Benchmarks)
make datos

# 3. Compilar el informe técnico a HTML
make informe
```

### Comandos Individuales Disponibles
| Comando | Descripción |
| :--- | :--- |
| `make db-up` | Levanta el contenedor `entregable2-postgres` en el puerto `5435`. |
| `make db-reset` | Aplica `modelo-fisico.sql` para limpiar esquemas y preparar tablas vacías. |
| `make generar` | Genera los archivos CSV sintéticos en `datos/output/`. |
| `make determinismo` | Comprueba determinismo bit a bit de dos corridas con checksums SHA-256. |
| `make cargar` | Inyecta datos masivos con `COPY`, ejecuta `ANALYZE` y crea índices secundarios. |
| `make verificar` | Audita conteos, ausencia de JOINs inter-esquema y distribución de probabilidad. |
| `make benchmark-carga` | Evalúa las 4 estrategias de inyección sobre 50.000 órdenes. |
| `make carga-incremental` | Inyecta 5.000 órdenes por la ruta transaccional real. |
| `make benchmark-queries` | Mide latencias p50/p95/p99 de consultas analíticas y transaccionales Q1 a Q5. |
| `make graficas` | Genera las figuras PNG para el informe técnico. |
