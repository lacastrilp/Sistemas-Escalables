-- =========================================================
-- 07_benchmark_particiones.sql
-- Compara 3 escenarios sobre la MISMA consulta filtrando por
-- fecha:
--   A) tabla NO particionada, CON índice   (pedidos)
--   B) tabla particionada,    CON índice   (pedidos_part)
--   C) tabla particionada,    SIN índice   (se dropean los
--      índices de pedidos_part temporalmente)
--
-- Lo que se debe observar en el EXPLAIN de (B) es "partition
-- pruning": el plan solo debe tocar la partición pedidos_2023,
-- no las 6 particiones. Eso es justamente lo que particionar
-- por fecha optimiza en reportes por rango de tiempo.
-- =========================================================

\timing on

-- ---- A) Tabla original (no particionada), ya con índices del paso 04 ----
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), sum(valor_total)
FROM pedidos
WHERE fecha_pedido BETWEEN '2023-06-01' AND '2023-06-30';

-- ---- B) Tabla particionada CON índices ----
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), sum(valor_total)
FROM pedidos_part
WHERE fecha_pedido BETWEEN '2023-06-01' AND '2023-06-30';

-- Filtro además por cliente_id, para ver partition pruning + index scan combinados
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pedidos_part
WHERE fecha_pedido BETWEEN '2023-01-01' AND '2023-12-31'
  AND cliente_id = 350000;

-- ---- C) Tabla particionada SIN índices (se eliminan temporalmente) ----
DROP INDEX IF EXISTS idx_pp_cliente;
DROP INDEX IF EXISTS idx_pp_sku;
DROP INDEX IF EXISTS idx_pp_estado;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pedidos_part
WHERE fecha_pedido BETWEEN '2023-01-01' AND '2023-12-31'
  AND cliente_id = 350000;

-- Para restaurar los índices después de la comparación:
-- CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
-- CREATE INDEX idx_pp_sku     ON pedidos_part (sku_id);
-- CREATE INDEX idx_pp_estado  ON pedidos_part (estado);
