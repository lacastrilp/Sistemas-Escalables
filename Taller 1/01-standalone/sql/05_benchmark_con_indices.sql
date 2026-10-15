-- =========================================================
-- 05_benchmark_con_indices.sql
-- Mismas 6 consultas de 03_benchmark_sin_indices.sql.
-- Ahora se espera ver Index Scan / Bitmap Index Scan / Index
-- Only Scan en lugar de Seq Scan, y un "Execution Time" menor
-- en las consultas selectivas (Q1, Q3). Q6 y Q2 pueden seguir
-- prefiriendo Seq Scan si tocan una fracción grande de la
-- tabla: eso también es un resultado válido para discutir en
-- clase (el optimizador no siempre usa el índice).
-- =========================================================

\timing on

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM clientes WHERE email = 'cliente500000@correo25.com';

EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM clientes WHERE ciudad = 'Medellin';

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pedidos WHERE cliente_id = 350000;

EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), sum(valor_total)
FROM pedidos
WHERE fecha_pedido BETWEEN '2023-06-01' AND '2023-06-30';

EXPLAIN (ANALYZE, BUFFERS)
SELECT c.ciudad, i.categoria, sum(p.valor_total) AS total
FROM pedidos p
JOIN clientes c   ON c.cliente_id = p.cliente_id
JOIN inventario i ON i.sku_id     = p.sku_id
WHERE p.estado = 'Entregado'
GROUP BY c.ciudad, i.categoria
ORDER BY total DESC
LIMIT 20;

EXPLAIN (ANALYZE, BUFFERS)
SELECT estado, count(*) FROM pedidos GROUP BY estado;
