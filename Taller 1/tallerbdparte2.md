## PARTE 3 — Particionamiento de `pedidos`

Ejecute estos comandos desde la carpeta raíz `Taller 1`. El archivo válido es
`02-particionamiento/sql/06_crear_particiones.sql`; no use copias anidadas de
esa ruta.

### 3.1 Crear la tabla particionada y migrar los datos

```bash
cd 02-particionamiento
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/06_crear_particiones.sql
```

Esto:
1. Crea `pedidos_part`, particionada por `RANGE (fecha_pedido)`, una partición por año (2022–2026) más una `pedidos_default` de resguardo.
2. Migra los 1.300.000 registros desde `pedidos` (tabla plana) hacia `pedidos_part`.
3. Crea la PK compuesta `(pedido_id, fecha_pedido)` — obligatoria porque en PostgreSQL toda PK/UNIQUE de una tabla particionada debe incluir la columna de partición.
4. Crea índices sobre la tabla **padre** (`idx_pp_cliente`, `idx_pp_sku`, `idx_pp_estado`), que Postgres propaga automáticamente a cada partición hija.

### 3.2 Benchmark: plano vs particionado, con y sin índice

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices < sql/07_benchmark_particiones.sql > resultados_particiones.txt
```

Lo que hay que buscar en el `EXPLAIN`:

- **Escenario A (tabla plana, con índice):** plan típico `Index Scan` sobre `pedidos`.
- **Escenario B (particionada, con índice):** el plan debe mostrar que **solo se tocó la partición `pedidos_2023`** (aparece como `-> Index Scan ... on pedidos_2023`), no las 6 particiones. A esto se le llama **partition pruning**: el optimizador descarta particiones completas sin siquiera abrirlas, antes de aplicar cualquier índice.
- **Escenario C (particionada, sin índice — el script dropea los índices momentáneamente):** debe verse `Seq Scan` pero **solo dentro de la partición correspondiente**, no de toda la tabla. Esto ilustra que el particionamiento y el indexado son optimizaciones **independientes y complementarias**: particionar ya reduce el volumen a escanear antes de que el índice entre a jugar.

Para restaurar los índices después de este ejercicio (están comentadas al final del script):

```sql
CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
CREATE INDEX idx_pp_sku     ON pedidos_part (sku_id);
CREATE INDEX idx_pp_estado  ON pedidos_part (estado);
```

Después de ejecutar el benchmark, restaure los índices con el bloque anterior y
actualice las estadísticas:

```bash
docker exec -i pg_taller psql -U eafit -d taller_indices <<'SQL'
CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
CREATE INDEX idx_pp_sku ON pedidos_part (sku_id);
CREATE INDEX idx_pp_estado ON pedidos_part (estado);
ANALYZE pedidos_part;
SQL
```

### 3.3 Plantilla de resultados

| Escenario | Particiones tocadas | Tipo de scan | Execution Time |
|---|---|---|---|
| A: plana + índice | — (n/a) | | |
| B: particionada + índice | | | |
| C: particionada sin índice | | | |

---