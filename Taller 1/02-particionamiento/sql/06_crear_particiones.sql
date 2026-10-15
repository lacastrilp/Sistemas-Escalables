DROP TABLE IF EXISTS pedidos_part CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;

CREATE TABLE pedidos (
    pedido_id INTEGER,
    cliente_id INTEGER,
    sku_id INTEGER,
    fecha_pedido DATE,
    cantidad INTEGER,
    estado TEXT,
    monto NUMERIC(12,2)
);

INSERT INTO pedidos (pedido_id, cliente_id, sku_id, fecha_pedido, cantidad, estado, monto)
SELECT
    pedido_id,
    cliente_id,
    sku_id,
    fecha_pedido,
    cantidad,
    estado,
    monto
FROM public.pedidos;

CREATE TABLE pedidos_part (
    pedido_id INTEGER NOT NULL,
    cliente_id INTEGER,
    sku_id INTEGER,
    fecha_pedido DATE NOT NULL,
    cantidad INTEGER,
    estado TEXT,
    monto NUMERIC(12,2),
    PRIMARY KEY (pedido_id, fecha_pedido)
) PARTITION BY RANGE (fecha_pedido);

CREATE TABLE pedidos_2022 PARTITION OF pedidos_part
    FOR VALUES FROM ('2022-01-01') TO ('2023-01-01');

CREATE TABLE pedidos_2023 PARTITION OF pedidos_part
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');

CREATE TABLE pedidos_2024 PARTITION OF pedidos_part
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE pedidos_2025 PARTITION OF pedidos_part
    FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');

CREATE TABLE pedidos_2026 PARTITION OF pedidos_part
    FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');

CREATE TABLE pedidos_default PARTITION OF pedidos_part DEFAULT;

INSERT INTO pedidos_part (pedido_id, cliente_id, sku_id, fecha_pedido, cantidad, estado, monto)
SELECT pedido_id, cliente_id, sku_id, fecha_pedido, cantidad, estado, monto
FROM pedidos;

CREATE INDEX idx_pp_cliente ON pedidos_part (cliente_id);
CREATE INDEX idx_pp_sku ON pedidos_part (sku_id);
CREATE INDEX idx_pp_estado ON pedidos_part (estado);
