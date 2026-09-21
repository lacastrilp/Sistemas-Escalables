-- ============================================================
-- MODELO FÍSICO Y DDL DE BASE DE DATOS - PORTAL B2B RETAIL
-- Entregable 2: Escalabilidad de los datos
-- 
-- Principios de Diseño:
-- 1. Separación estricta de esquemas: Un esquema por módulo.
--    - proveedores (proveedor, contrato_suministro)
--    - catalogo (sku, proveedor_sku)
--    - logistica (cedi, franja_descargue)
--    - ordenes (orden_compra, linea_orden, evento_auditoria)
--    PROHIBIDO hacer JOINs entre tablas de diferentes esquemas.
-- 2. Llaves primarias tipo BIGINT generadas secuencialmente/aritméticamente.
-- 3. Índices optimizados para las consultas patrón Q1 a Q5.
-- ============================================================

DROP SCHEMA IF EXISTS ordenes CASCADE;
DROP SCHEMA IF EXISTS logistica CASCADE;
DROP SCHEMA IF EXISTS catalogo CASCADE;
DROP SCHEMA IF EXISTS proveedores CASCADE;

CREATE SCHEMA proveedores;
CREATE SCHEMA catalogo;
CREATE SCHEMA ordenes;
CREATE SCHEMA logistica;



-- ============================================================
-- PROVEEDORES
-- ============================================================

CREATE TABLE proveedores.proveedor (
    id                  BIGINT PRIMARY KEY,
    nit                 VARCHAR(20) NOT NULL UNIQUE,
    nombre              VARCHAR(200) NOT NULL,
    estado              VARCHAR(20) NOT NULL,
    fecha_registro      DATE NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT proveedor_estado_ck
        CHECK (estado IN ('ACTIVO', 'INACTIVO'))
);


-- ============================================================
-- CONTRATOS DE SUMINISTRO
-- ============================================================

CREATE TABLE proveedores.contrato_suministro (
    id                  BIGINT PRIMARY KEY,
    proveedor_id        BIGINT NOT NULL,
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE NOT NULL,
    estado              VARCHAR(20) NOT NULL,
    limite_credito      NUMERIC(14,2),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT contrato_fecha_valida
        CHECK (fecha_fin >= fecha_inicio),

    CONSTRAINT contrato_estado_ck
        CHECK (
            estado IN (
                'ACTIVO',
                'VENCIDO',
                'PENDIENTE'
            )
        ),

    CONSTRAINT contrato_limite_credito_ck
        CHECK (
            limite_credito IS NULL
            OR limite_credito >= 0
        ),

    CONSTRAINT contrato_proveedor_fk
        FOREIGN KEY (proveedor_id)
        REFERENCES proveedores.proveedor(id)
);


-- ============================================================
-- SKU
-- ============================================================

CREATE TABLE catalogo.sku (
    id                  BIGINT PRIMARY KEY,
    codigo              VARCHAR(50) NOT NULL UNIQUE,
    nombre              VARCHAR(200) NOT NULL,
    categoria           VARCHAR(100) NOT NULL,
    precio_base         NUMERIC(14,2) NOT NULL,
    estado              VARCHAR(20) NOT NULL,

    CONSTRAINT sku_precio_ck
        CHECK (precio_base > 0),

    CONSTRAINT sku_estado_ck
        CHECK (
            estado IN (
                'ACTIVO',
                'INACTIVO'
            )
        )
);


-- ============================================================
-- CATÁLOGO PROVEEDOR - SKU
-- ============================================================

CREATE TABLE catalogo.proveedor_sku (
    id                  BIGINT PRIMARY KEY,
    proveedor_id        BIGINT NOT NULL,
    sku_id              BIGINT NOT NULL,
    precio_negociado    NUMERIC(14,2) NOT NULL,
    fecha_inicio        DATE NOT NULL,
    fecha_fin           DATE,
    estado              VARCHAR(20) NOT NULL,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT proveedor_sku_fechas
        CHECK (
            fecha_fin IS NULL
            OR fecha_fin >= fecha_inicio
        ),

    CONSTRAINT proveedor_sku_estado_ck
        CHECK (
            estado IN (
                'ACTIVO',
                'INACTIVO'
            )
        ),

    CONSTRAINT proveedor_sku_precio_ck
        CHECK (
            precio_negociado > 0
        ),

    CONSTRAINT proveedor_sku_unica
        UNIQUE (
            proveedor_id,
            sku_id
        ),

    CONSTRAINT proveedor_sku_proveedor_fk
        FOREIGN KEY (proveedor_id)
        REFERENCES proveedores.proveedor(id),

    CONSTRAINT proveedor_sku_sku_fk
        FOREIGN KEY (sku_id)
        REFERENCES catalogo.sku(id)
);


-- ============================================================
-- CEDI
-- ============================================================

CREATE TABLE logistica.cedi (
    id                  BIGINT PRIMARY KEY,
    codigo              VARCHAR(30) NOT NULL UNIQUE,
    nombre              VARCHAR(150) NOT NULL,
    ciudad              VARCHAR(100) NOT NULL,
    capacidad_diaria    INTEGER NOT NULL,
    estado              VARCHAR(20) NOT NULL,

    CONSTRAINT cedi_estado_ck
        CHECK (
            estado IN (
                'ACTIVO',
                'INACTIVO'
            )
        ),

    CONSTRAINT cedi_capacidad_ck
        CHECK (
            capacidad_diaria > 0
        )
);


-- ============================================================
-- FRANJAS DE DESCARGUE
-- ============================================================

CREATE TABLE logistica.franja_descargue (
    id                  BIGINT PRIMARY KEY,
    cedi_id             BIGINT NOT NULL,
    fecha               DATE NOT NULL,
    hora_inicio         TIME NOT NULL,
    hora_fin            TIME NOT NULL,
    capacidad           INTEGER NOT NULL,
    reservados          INTEGER NOT NULL DEFAULT 0,
    estado              VARCHAR(20) NOT NULL,

    CONSTRAINT franja_cedi_fk
        FOREIGN KEY (cedi_id)
        REFERENCES logistica.cedi(id),

    CONSTRAINT franja_horas_validas
        CHECK (
            hora_fin > hora_inicio
        ),

    CONSTRAINT capacidad_valida
        CHECK (
            capacidad > 0
        ),

    CONSTRAINT reservados_validos
        CHECK (
            reservados >= 0
            AND reservados <= capacidad
        ),

    CONSTRAINT franja_estado_ck
        CHECK (
            estado IN (
                'DISPONIBLE',
                'LLENA',
                'CERRADA'
            )
        ),

    CONSTRAINT franja_unica_cedi_fecha_hora
        UNIQUE (
            cedi_id,
            fecha,
            hora_inicio,
            hora_fin
        )
);


-- ============================================================
-- ORDENES DE COMPRA
-- ============================================================

CREATE TABLE ordenes.orden_compra (
    id                  BIGINT PRIMARY KEY,
    numero_orden        VARCHAR(50) NOT NULL UNIQUE,
    proveedor_id        BIGINT NOT NULL,
    fecha_orden         TIMESTAMP NOT NULL,
    estado              VARCHAR(30) NOT NULL,
    cedi_id             BIGINT NOT NULL,
    franja_id           BIGINT,
    total               NUMERIC(16,2) NOT NULL DEFAULT 0,
    fecha_entrega       DATE,
    fecha_confirmacion  TIMESTAMP,
    idempotency_key     VARCHAR(100),
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT orden_estado_ck
        CHECK (
            estado IN (
                'PENDIENTE',
                'CONFIRMADA',
                'ENTREGADA',
                'CANCELADA'
            )
        ),

    CONSTRAINT orden_total_ck
        CHECK (
            total >= 0
        ),

    CONSTRAINT orden_proveedor_fk
        FOREIGN KEY (proveedor_id)
        REFERENCES proveedores.proveedor(id),

    CONSTRAINT orden_cedi_fk
        FOREIGN KEY (cedi_id)
        REFERENCES logistica.cedi(id),

    CONSTRAINT orden_franja_fk
        FOREIGN KEY (franja_id)
        REFERENCES logistica.franja_descargue(id),

    CONSTRAINT orden_idempotency_unique
        UNIQUE (idempotency_key)
);


-- ============================================================
-- LÍNEAS DE ORDEN
-- ============================================================

CREATE TABLE ordenes.linea_orden (
    id                  BIGINT PRIMARY KEY,
    orden_id            BIGINT NOT NULL,
    numero_linea        INTEGER NOT NULL,
    sku_id              BIGINT NOT NULL,
    cantidad            INTEGER NOT NULL,
    precio_unitario     NUMERIC(14,2) NOT NULL,
    cantidad_recibida   INTEGER NOT NULL DEFAULT 0,
    fecha_recepcion     TIMESTAMP,

    CONSTRAINT linea_orden_fk
        FOREIGN KEY (orden_id)
        REFERENCES ordenes.orden_compra(id),

    CONSTRAINT linea_sku_fk
        FOREIGN KEY (sku_id)
        REFERENCES catalogo.sku(id),

    CONSTRAINT numero_linea_positivo
        CHECK (
            numero_linea > 0
        ),

    CONSTRAINT cantidad_positiva
        CHECK (
            cantidad > 0
        ),

    CONSTRAINT cantidad_recibida_valida
        CHECK (
            cantidad_recibida >= 0
            AND cantidad_recibida <= cantidad
        ),

    CONSTRAINT precio_positivo
        CHECK (
            precio_unitario > 0
        ),

    CONSTRAINT linea_unica
        UNIQUE (
            orden_id,
            numero_linea
        )
);


-- ============================================================
-- EVENTOS DE AUDITORÍA
-- ============================================================

CREATE TABLE ordenes.evento_auditoria (
    id                  BIGINT PRIMARY KEY,
    orden_id            BIGINT NOT NULL,
    tipo_evento         VARCHAR(50) NOT NULL,
    fecha_evento        TIMESTAMP NOT NULL,
    payload             JSONB,
    created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT evento_orden_fk
        FOREIGN KEY (orden_id)
        REFERENCES ordenes.orden_compra(id),

    CONSTRAINT evento_tipo_ck
        CHECK (
            tipo_evento IN (
                'ORDEN_CREADA',
                'ORDEN_CONFIRMADA',
                'ORDEN_CANCELADA',
                'ORDEN_ENTREGADA',
                'SLOT_RESERVADO',
                'VALIDACION_FISCAL'
            )
        )
);


-- ============================================================
-- ÍNDICES
-- ============================================================

CREATE INDEX idx_contrato_proveedor
    ON proveedores.contrato_suministro(proveedor_id);

CREATE INDEX idx_contrato_estado_fecha
    ON proveedores.contrato_suministro(
        estado,
        fecha_inicio,
        fecha_fin
    );

CREATE INDEX idx_proveedor_sku_proveedor
    ON catalogo.proveedor_sku(proveedor_id);

CREATE INDEX idx_proveedor_sku_sku
    ON catalogo.proveedor_sku(sku_id);

CREATE INDEX idx_proveedor_sku_estado
    ON catalogo.proveedor_sku(
        proveedor_id,
        estado
    );

CREATE INDEX idx_orden_proveedor_fecha
    ON ordenes.orden_compra(
        proveedor_id,
        fecha_orden
    );

CREATE INDEX idx_orden_fecha
    ON ordenes.orden_compra(fecha_orden);

CREATE INDEX idx_orden_cedi_fecha
    ON ordenes.orden_compra(
        cedi_id,
        fecha_orden
    );

CREATE INDEX idx_orden_franja
    ON ordenes.orden_compra(franja_id);

CREATE INDEX idx_linea_orden
    ON ordenes.linea_orden(orden_id);

CREATE INDEX idx_linea_sku
    ON ordenes.linea_orden(sku_id);

CREATE INDEX idx_evento_orden_fecha
    ON ordenes.evento_auditoria(
        orden_id,
        fecha_evento
    );

CREATE INDEX idx_evento_fecha
    ON ordenes.evento_auditoria(fecha_evento);

CREATE INDEX idx_franja_cedi_fecha
    ON logistica.franja_descargue(
        cedi_id,
        fecha
    );