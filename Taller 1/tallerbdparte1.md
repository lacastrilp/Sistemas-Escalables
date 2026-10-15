# Taller práctico: Índices, Particionamiento y Clustering en PostgreSQL

**EAFIT — Aplicaciones y Sistemas escalables**
Todo el material corre sobre **Docker Desktop**. No se necesita instalar PostgreSQL en el sistema operativo.

## Estructura del proyecto

```
postgres-taller/
├── 01-standalone/          Parte 1 y 2: instancia única, datos, benchmarks sin/con índices
│   ├── docker-compose.yml
│   └── sql/
│       ├── 01_schema.sql
│       ├── 02_generar_datos.sql
│       ├── 03_benchmark_sin_indices.sql
│       ├── 04_crear_indices.sql
│       └── 05_benchmark_con_indices.sql
├── 02-particionamiento/    Parte 3: redefinición particionada + benchmarks
│   └── sql/
│       ├── 06_crear_particiones.sql
│       └── 07_benchmark_particiones.sql
└── 03-cluster/              Parte 4: cluster de 3 nodos con streaming replication
    ├── docker-compose.yml
    ├── primary/
    ├── replica/
    └── verificacion.sql
```

---

## PARTE 1 — Instancia PostgreSQL en Docker Desktop

### 1.1 Prerrequisitos
- Docker Desktop instalado y corriendo (Windows/Mac/Linux), con `docker compose` v2.
- Verificar en terminal:
  ```bash
  docker --version
  docker compose version
  ```

### 1.2 Levantar el contenedor

```bash
cd 01-standalone
docker compose up -d
docker compose ps
```

Esto crea un contenedor `pg_taller` con:
- Usuario: `eafit` / Password: `eafit2026` / Base de datos: `taller_indices`
- Puerto expuesto en el host: `5542` (PostgreSQL escucha en `5432` dentro del contenedor)
- Volumen persistente `pgdata` (los datos sobreviven si se reinicia el contenedor)

Para conexiones desde el host use `localhost:5542`.

### 1.3 Conectarse

```bash
docker exec -it pg_taller psql -U eafit -d taller_indices
```

(Alternativa gráfica: usar DBeaver, pgAdmin o TablePlus apuntando a `localhost:5432`.)

### 1.4 Crear el esquema (sin índices)

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/01_schema.sql
```

Las tres tablas (`clientes`, `inventario`, `pedidos`) se crean **sin ninguna llave primaria ni índice**. Es intencional: así el primer benchmark mide el comportamiento "crudo" de un `Seq Scan`.

---

## PARTE 2 — Carga masiva de datos aleatorios y benchmark sin/con índices

### 2.1 Generar los datos

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/02_generar_datos.sql
```

El script usa `generate_series()` **dentro** del motor (no un script externo fila por fila), por lo cual carga rápido incluso en un portátil:

| Tabla | Registros |
|---|---|
| `clientes` | 1.000.000 |
| `inventario` | 550.000 |
| `pedidos` | 1.300.000 |

`\timing on` queda activo en el script: al final verán cuánto tardó cada `INSERT`. Anótenlo — es el primer dato de la tabla de resultados (abajo).

> Si prefieren datos "más realistas" (nombres, direcciones, etc. con la librería Faker de Python) en vez de los arreglos de valores fijos usados aquí, es posible, pero cargar 1M+ filas fila por fila desde Python vía `psycopg2` puede tardar 10-20x más que este enfoque nativo. Si quieren esa variante para otro ejercicio, usen `COPY` con un CSV pre-generado por Python en vez de `INSERT` uno a uno.

### 2.2 Benchmark SIN índices

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/03_benchmark_sin_indices.sql > resultados_sin_indices.txt
```

Revisen `resultados_sin_indices.txt`. Para cada consulta (Q1 a Q6) va a aparecer algo como:

```
Seq Scan on pedidos  (cost=0.00..... rows=... width=...) (actual time=... rows=... loops=1)
  Filter: (cliente_id = 350000)
  Rows Removed by Filter: 1299996
Planning Time: ...
Execution Time: ...
```

**Qué anotar:** el nodo del plan (`Seq Scan`), el `Execution Time` y `Rows Removed by Filter` (cuántas filas tuvo que descartar sin poder saltárselas).

### 2.3 Crear los índices

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/04_crear_indices.sql
```

Anoten también el `\timing` de esta operación: crear índices sobre 1M+ filas no es gratis, y es parte de la discusión (índices aceleran lectura pero cuestan en escritura y espacio).

### 2.4 Benchmark CON índices

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/05_benchmark_con_indices.sql > resultados_con_indices.txt
```

Ahora deberían ver `Index Scan`, `Bitmap Index Scan` o `Index Only Scan` en las consultas selectivas (Q1, Q3), y una caída notable en `Execution Time`.

> **Nota importante:** en Q2 y Q6, si el filtro toca una fracción grande de la tabla (ej. una ciudad con 100.000 de 1.000.000 de clientes), el optimizador puede **seguir prefiriendo `Seq Scan`** aunque exista el índice — leer secuencialmente puede ser más barato que saltar por el índice cuando se va a tocar mucho del disco de todas formas. Este es justamente un buen punto de discusión en clase: el índice ayuda, pero el optimizador decide según selectividad, no por dogma.

### 2.5 Plantilla de resultados (llenar en clase)

| Consulta | Seq/Index Scan (sin idx) | Tiempo sin idx | Seq/Index Scan (con idx) | Tiempo con idx |
|---|---|---|---|---|
| Q1 – email puntual | | | | |
| Q2 – ciudad | | | | |
| Q3 – pedidos de un cliente | | | | |
| Q4 – rango de fechas | | | | |
| Q5 – JOIN 3 tablas | | | | |
| Q6 – GROUP BY estado | | | | |

---