-- =========================================================
-- 03_benchmark_sin_indices.sql
-- Ejecutar y capturar: "Planning Time", "Execution Time" y
-- el tipo de nodo (Seq Scan vs Index Scan). En esta fase
-- TODO debe salir como Seq Scan porque no hay índices.
--
-- Sugerencia pedagógica: correr cada consulta 2 veces.
-- La primera "calienta" el caché de páginas (shared_buffers /
-- OS cache); la segunda es la que se debe comparar entre
-- corridas para que la comparación sea justa.
-- =========================================================

\timing on

-- Q1: búsqueda puntual por email (alta cardinalidad, sin índice)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM clientes WHERE email = 'cliente500000@correo25.com';

-- Q2: búsqueda por ciudad (baja cardinalidad, ~100.000 filas)
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM clientes WHERE ciudad = 'Medellin';

-- Q3: pedidos de un cliente específico (típico "detalle de cliente")
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM pedidos WHERE cliente_id = 350000;

-- Q4: pedidos por rango de fechas (típico reporte mensual)
EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*), sum(valor_total)
FROM pedidos
WHERE fecha_pedido BETWEEN '2023-06-01' AND '2023-06-30';

-- Q5: JOIN de las 3 tablas + agregación (el más costoso)
EXPLAIN (ANALYZE, BUFFERS)
SELECT c.ciudad, i.categoria, sum(p.valor_total) AS total
FROM pedidos p
JOIN clientes c   ON c.cliente_id = p.cliente_id
JOIN inventario i ON i.sku_id     = p.sku_id
WHERE p.estado = 'Entregado'
GROUP BY c.ciudad, i.categoria
ORDER BY total DESC
LIMIT 20;

-- Q6: conteo por estado (todo pedidos, GROUP BY simple)
EXPLAIN (ANALYZE, BUFFERS)
SELECT estado, count(*) FROM pedidos GROUP BY estado;
