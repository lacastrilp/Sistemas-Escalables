-- =========================================================
-- 06_crear_particiones.sql
-- Redefine "pedidos" como tabla particionada por RANGE sobre
-- fecha_pedido (partición anual). En Postgres, la PK de una
-- tabla particionada debe incluir la(s) columna(s) de
-- partición, por eso queda (pedido_id, fecha_pedido).
-- =========================================================

\timing on

DROP TABLE IF EXISTS pedidos_part CASCADE;

CREATE TABLE pedidos_part (
    pedido_id       BIGINT,
    cliente_id      BIGINT,
    sku_id          BIGINT,
    fecha_pedido    TIMESTAMP NOT NULL,
    cantidad        INT,
    valor_total     NUMERIC(14,2),
    estado          TEXT,
    ciudad_envio    TEXT
) PARTITION BY RANGE (fecha_pedido);

-- Particiones anuales (los datos generados van de 2022 a ~2026)
CREATE TABLE pedidos_2022 PARTITION OF pedidos_part FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');
CREATE TABLE pedidos_2023 PARTITION OF pedidos_part FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
CREATE TABLE pedidos_2024 PARTITION OF pedidos_part FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE pedidos_2025 PARTITION OF pedidos_part FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE pedidos_2026 PARTITION OF pedidos_part FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');
-- Partición de resguardo por si algún registro cae fuera de rango
CREATE TABLE pedidos_default PARTITION OF pedidos_part DEFAULT;

-- Migración de datos desde la tabla original (no particionada)
INSERT INTO pedidos_part
SELECT * FROM pedidos;

-- PK compuesta (obligatoria en tablas particionadas)
ALTER TABLE pedidos_part ADD PRIMARY KEY (pedido_id, fecha_pedido);

-- Nota: crear un índice sobre la tabla PADRE particionada crea
-- automáticamente el índice equivalente en CADA partición (y en
-- las que se creen después). Un solo DROP INDEX las elimina todas.
CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
CREATE INDEX idx_pp_sku     ON pedidos_part (sku_id);
CREATE INDEX idx_pp_estado  ON pedidos_part (estado);

ANALYZE pedidos_part;

-- Verificación de cuántas filas quedaron en cada partición
SELECT relname AS particion, n_live_tup AS filas
FROM pg_stat_user_tables
WHERE relname LIKE 'pedidos_%'
ORDER BY relname;
