-- =========================================================
-- 04_crear_indices.sql
-- Agrega llaves primarias e índices sobre las columnas que
-- realmente se usan en los WHERE/JOIN del benchmark.
-- =========================================================

\timing on

-- Llaves primarias (cada una crea automáticamente un índice único btree)
ALTER TABLE clientes   ADD PRIMARY KEY (cliente_id);
ALTER TABLE inventario ADD PRIMARY KEY (sku_id);
ALTER TABLE pedidos    ADD PRIMARY KEY (pedido_id);

-- Índices puntuales sobre columnas de filtro/join
CREATE UNIQUE INDEX idx_clientes_email   ON clientes (email);
CREATE INDEX        idx_clientes_ciudad  ON clientes (ciudad);
CREATE INDEX        idx_pedidos_cliente  ON pedidos (cliente_id);
CREATE INDEX        idx_pedidos_sku      ON pedidos (sku_id);
CREATE INDEX        idx_pedidos_fecha    ON pedidos (fecha_pedido);
CREATE INDEX        idx_pedidos_estado   ON pedidos (estado);

ANALYZE clientes;
ANALYZE inventario;
ANALYZE pedidos;

-- Tamaño de cada índice creado (útil para discutir el costo
-- de espacio en disco que trae indexar)
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) AS tamano
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
