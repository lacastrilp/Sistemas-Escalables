# Taller 1 — Índices, Particionamiento y Replicación en PostgreSQL

**Curso:** Aplicaciones y Sistemas Escalables  
**Institución:** Universidad EAFIT · Semestre 2026-2  
**Equipo:** Grupo EKS — Sara López Marín & Luis Alejandro Castrillón Pulgarin  

---

## 📋 Descripción General

Este taller aborda los fundamentos de rendimiento, diseño físico y alta disponibilidad en bases de datos relacionales PostgreSQL a través de entornos reproducibles en Docker:

1. **01-standalone:** Instancia individual de PostgreSQL. Creación y evaluación comparativa de índices (`B-Tree`, `Hash`, `GIN`, `BRIN`) frente a consultas de filtrado, rangos y búsqueda de texto.
2. **02-particionamiento:** Implementación de particionamiento declarativo en tablas masivas por rango de fechas y particiones hash. Evaluación de planes de ejecución (`Partition Pruning`).
3. **03-cluster:** Clúster de alta disponibilidad con streaming replication física (1 nodo `primary` y 2 nodos `replica` de solo lectura) utilizando `pg_basebackup` y slots de replicación.

---

## 📂 Estructura de Directorios

```text
Taller 1/
├── 01-standalone/                # Parte 1 y 2: Benchmarking con y sin índices
│   ├── docker-compose.yml
│   ├── resultados_sin_indices.txt
│   ├── resultados_con_indices.txt
│   └── sql/
│       ├── 01_schema.sql
│       ├── 02_generar_datos.sql
│       ├── 03_benchmark_sin_indices.sql
│       ├── 04_crear_indices.sql
│       └── 05_benchmark_con_indices.sql
├── 02-particionamiento/          # Parte 3: Particionamiento declarativo
│   ├── resultados_particiones.txt
│   └── sql/
│       └── 06_crear_particiones.sql
├── 03-cluster/                   # Parte 4: Clúster con streaming replication
│   ├── docker-compose.yml
│   ├── primary/
│   ├── replica/
│   └── verificacion.sql
├── tallerbdparte1.md             # Guía paso a paso: Parte 1
├── tallerbdparte2.md             # Guía paso a paso: Parte 2
└── tallerbdparte3.md             # Guía paso a paso: Parte 3
```

---

## 🚀 Guía de Ejecución

### 1. Standalone y Benchmarking de Índices
```bash
cd "Taller 1/01-standalone"
docker compose up -d

# Ejecutar benchmarks y creación de índices
docker exec -i postgres-standalone psql -U postgres -d taller < sql/01_schema.sql
docker exec -i postgres-standalone psql -U postgres -d taller < sql/02_generar_datos.sql
docker exec -i postgres-standalone psql -U postgres -d taller < sql/03_benchmark_sin_indices.sql
docker exec -i postgres-standalone psql -U postgres -d taller < sql/04_crear_indices.sql
docker exec -i postgres-standalone psql -U postgres -d taller < sql/05_benchmark_con_indices.sql
```

### 2. Particionamiento Declarativo
```bash
cd "Taller 1/02-particionamiento"
docker exec -i postgres-standalone psql -U postgres -d taller < sql/06_crear_particiones.sql
```

### 3. Clúster de Replicación Streaming
```bash
cd "Taller 1/03-cluster"
docker compose up -d

# Verificar estado de replicación entre primary y réplicas
docker exec -i postgres-primary psql -U postgres -d taller < verificacion.sql
```
