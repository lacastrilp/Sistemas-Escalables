-- ============================================================
-- ÍNDICES SECUNDARIOS - PORTAL B2B RETAIL (ENTREGABLE 2)
-- Se ejecutan POST-CARGA tras COPY masivo para optimizar tiempos de inserción
-- y permitir mediciones EXPLAIN de planes antes y después.
-- ============================================================

-- Módulo Proveedores (Soporte Q1)
CREATE INDEX IF NOT EXISTS idx_contrato_proveedor
    ON proveedores.contrato_suministro(proveedor_id);

CREATE INDEX IF NOT EXISTS idx_contrato_estado_fecha
    ON proveedores.contrato_suministro(estado, fecha_inicio, fecha_fin);

-- Módulo Catálogo (Soporte Q2)
CREATE INDEX IF NOT EXISTS idx_proveedor_sku_proveedor
    ON catalogo.proveedor_sku(proveedor_id);

CREATE INDEX IF NOT EXISTS idx_proveedor_sku_sku
    ON catalogo.proveedor_sku(sku_id);

CREATE INDEX IF NOT EXISTS idx_proveedor_sku_estado
    ON catalogo.proveedor_sku(proveedor_id, estado);

-- Módulo Logística (Soporte Q3)
CREATE INDEX IF NOT EXISTS idx_franja_cedi_fecha
    ON logistica.franja_descargue(cedi_id, fecha);

-- Módulo Órdenes (Soporte Q4 y Q5)
CREATE INDEX IF NOT EXISTS idx_orden_proveedor_fecha
    ON ordenes.orden_compra(proveedor_id, fecha_orden);

CREATE INDEX IF NOT EXISTS idx_orden_fecha
    ON ordenes.orden_compra(fecha_orden);

CREATE INDEX IF NOT EXISTS idx_orden_cedi_fecha
    ON ordenes.orden_compra(cedi_id, fecha_orden);

CREATE INDEX IF NOT EXISTS idx_orden_franja
    ON ordenes.orden_compra(franja_id);

CREATE INDEX IF NOT EXISTS idx_linea_orden
    ON ordenes.linea_orden(orden_id);

CREATE INDEX IF NOT EXISTS idx_linea_sku
    ON ordenes.linea_orden(sku_id);

-- Eventos de auditoría
CREATE INDEX IF NOT EXISTS idx_evento_orden_fecha
    ON ordenes.evento_auditoria(orden_id, fecha_evento);

CREATE INDEX IF NOT EXISTS idx_evento_fecha
    ON ordenes.evento_auditoria(fecha_evento);
