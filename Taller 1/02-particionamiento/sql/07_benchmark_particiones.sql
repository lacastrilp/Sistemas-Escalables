\echo 'Escenario A: tabla plana + indice'
EXPLAIN (ANALYZE, BUFFERS)
SELECT *
FROM pedidos
WHERE cliente_id = 350000 AND fecha_pedido BETWEEN DATE '2023-01-01' AND DATE '2023-12-31';

\echo 'Escenario B: particionada + indice'
EXPLAIN (ANALYZE, BUFFERS)
SELECT *
FROM pedidos_part
WHERE cliente_id = 350000 AND fecha_pedido BETWEEN DATE '2023-01-01' AND DATE '2023-12-31';

\echo 'Escenario C: particionada sin indice'
DROP INDEX IF EXISTS idx_pp_cliente;
DROP INDEX IF EXISTS idx_pp_sku;
DROP INDEX IF EXISTS idx_pp_estado;

EXPLAIN (ANALYZE, BUFFERS)
SELECT *
FROM pedidos_part
WHERE cliente_id = 350000 AND fecha_pedido BETWEEN DATE '2023-01-01' AND DATE '2023-12-31';

CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
CREATE INDEX idx_pp_sku ON pedidos_part (sku_id);
CREATE INDEX idx_pp_estado ON pedidos_part (estado);
