-- =========================================================
-- 01_schema.sql
-- Modelo de datos SIN índices adicionales (ni siquiera PK)
-- El objetivo es medir el comportamiento "crudo" de Postgres
-- antes de indexar nada. Las PK e índices se agregan en 04.
-- =========================================================

DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS inventario CASCADE;
DROP TABLE IF EXISTS clientes CASCADE;

CREATE TABLE clientes (
    cliente_id      BIGINT,
    nombres         TEXT,
    apellidos       TEXT,
    email           TEXT,
    telefono        TEXT,
    ciudad          TEXT,
    pais            TEXT,
    fecha_registro  DATE,
    activo          BOOLEAN
);

CREATE TABLE inventario (
    sku_id               BIGINT,
    sku_code             TEXT,
    nombre_producto      TEXT,
    categoria            TEXT,
    precio               NUMERIC(12,2),
    stock                INT,
    bodega               TEXT,
    fecha_actualizacion  TIMESTAMP
);

CREATE TABLE pedidos (
    pedido_id       BIGINT,
    cliente_id      BIGINT,
    sku_id          BIGINT,
    fecha_pedido    TIMESTAMP,
    cantidad        INT,
    valor_total     NUMERIC(14,2),
    estado          TEXT,
    ciudad_envio    TEXT
);
