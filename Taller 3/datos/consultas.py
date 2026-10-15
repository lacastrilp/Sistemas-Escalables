#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entregable 3 - Catálogo compartido de consultas patrón Q1-Q5 y rutas de conexión.

Las sentencias SQL y los parámetros son **idénticos** a ``benchmark_queries.py`` (E2)
para que la línea base sea comparable 1:1.

Rutas de conexión (``E3_DB_RUTA`` o argumento ``ruta``):
* ``directa``   -> socket ``datos/.pg_socket`` o ``127.0.0.1:5435`` (igual que E2).
* ``toxiproxy`` -> ``127.0.0.1:25432`` (pasa por el proxy de fallas de red, Familia 1).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import psycopg2
import psycopg2.pool

BASE_DIR = Path(__file__).resolve().parent
SOCK_PATH = BASE_DIR / ".pg_socket"

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "retail")
DB_USER = os.getenv("DB_USER", "retail")
DB_PASS = os.getenv("DB_PASS", "retail")
TOXI_HOST = os.getenv("TOXI_HOST", "127.0.0.1")
TOXI_PORT = int(os.getenv("TOXI_PORT", "25432"))
RUTA_DEFECTO = os.getenv("E3_DB_RUTA", "directa")

HOT_PROVEEDOR_ID = 1
COLD_PROVEEDOR_ID = 50000
CEDI_ID = 1
COLD_FECHA_CEDI = "2024-05-15"
HOT_FECHA_CEDI = "2025-12-31"
FECHA_Q1 = "2025-06-15 12:00:00"


def _dsn(ruta: str) -> Dict[str, object]:
    base = {"dbname": DB_NAME, "user": DB_USER, "password": DB_PASS, "application_name": f"e3-{ruta}"}
    if ruta == "toxiproxy":
        return {**base, "host": TOXI_HOST, "port": TOXI_PORT, "connect_timeout": 5}
    if SOCK_PATH.exists() and any(SOCK_PATH.glob(".s.PGSQL.*")):
        return {**base, "host": str(SOCK_PATH), "port": 5432}
    return {**base, "host": DB_HOST, "port": DB_PORT, "connect_timeout": 2}


def get_connection(ruta: str = RUTA_DEFECTO):
    """Conexión individual. ``directa`` replica la preferencia por socket del E2."""
    try:
        return psycopg2.connect(**_dsn(ruta))
    except psycopg2.OperationalError:
        if ruta == "directa":  # fallback TCP si el socket existe pero no responde
            return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS,
                                    host=DB_HOST, port=DB_PORT, connect_timeout=2)
        raise


def crear_pool(maxconn: int, ruta: str = RUTA_DEFECTO, minconn: int = 1) -> psycopg2.pool.ThreadedConnectionPool:
    return psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, **_dsn(ruta))


# ----------------------------------------------------------------------------
# SQL patrón (copiado literalmente de E2)
# ----------------------------------------------------------------------------
Q1_SQL = """
    SELECT p.id, p.nit, p.nombre, c.id AS contrato_id, c.fecha_inicio, c.fecha_fin, c.estado
    FROM proveedores.proveedor p
    JOIN proveedores.contrato_suministro c ON c.proveedor_id = p.id
    WHERE p.id = %s AND %s BETWEEN c.fecha_inicio AND c.fecha_fin;
    """

Q2_SQL = """
    SELECT ps.sku_id, s.codigo, s.nombre, ps.precio_negociado
    FROM catalogo.proveedor_sku ps
    JOIN catalogo.sku s ON s.id = ps.sku_id
    WHERE ps.proveedor_id = %s AND ps.estado = 'ACTIVO'
    ORDER BY ps.sku_id
    LIMIT 20;
    """

Q3_SQL = """
    SELECT id, fecha, hora_inicio, hora_fin, capacidad, reservados
    FROM logistica.franja_descargue
    WHERE cedi_id = %s AND fecha = %s AND estado = 'DISPONIBLE' AND reservados < capacidad
    ORDER BY hora_inicio;
    """

Q4_SQL = """
    SELECT 
        o.proveedor_id,
        DATE_TRUNC('month', o.fecha_orden) AS mes,
        COUNT(DISTINCT o.id) AS total_ordenes,
        COUNT(DISTINCT CASE 
            WHEN o.estado = 'ENTREGADA' 
             AND o.fecha_entrega IS NOT NULL 
             AND o.fecha_compromiso_entrega IS NOT NULL 
             AND o.fecha_entrega <= o.fecha_compromiso_entrega 
            THEN o.id END) AS ordenes_otif,
        ROUND(
            COUNT(DISTINCT CASE 
                WHEN o.estado = 'ENTREGADA' 
                 AND o.fecha_entrega IS NOT NULL 
                 AND o.fecha_compromiso_entrega IS NOT NULL 
                 AND o.fecha_entrega <= o.fecha_compromiso_entrega 
                THEN o.id END)::NUMERIC 
            / NULLIF(COUNT(DISTINCT o.id), 0) * 100, 2
        ) AS porcentaje_otif,
        COALESCE(SUM(l.cantidad_recibida), 0) AS total_recibido,
        COALESCE(SUM(l.cantidad), 0) AS total_solicitado,
        ROUND(
            COALESCE(SUM(l.cantidad_recibida), 0)::NUMERIC / NULLIF(COALESCE(SUM(l.cantidad), 0), 0) * 100, 2
        ) AS fill_rate_porcentaje
    FROM ordenes.orden_compra o
    JOIN ordenes.linea_orden l ON l.orden_id = o.id
    WHERE o.proveedor_id = %s
      AND o.fecha_orden >= '2024-01-01' AND o.fecha_orden <= '2025-12-31'
    GROUP BY o.proveedor_id, DATE_TRUNC('month', o.fecha_orden)
    ORDER BY mes;
    """

Q5_SQL = """
    SELECT id, numero_orden, proveedor_id, fecha_orden, estado, total
    FROM ordenes.orden_compra
    WHERE proveedor_id = %s
    ORDER BY fecha_orden DESC
    LIMIT 50;
    """


@dataclass(frozen=True)
class ConsultaPatron:
    nombre: str
    sql: str
    params_frio: Tuple
    params_caliente: Tuple
    descripcion: str


CONSULTAS: Dict[str, ConsultaPatron] = {
    "Q1": ConsultaPatron("Q1", Q1_SQL, (COLD_PROVEEDOR_ID, FECHA_Q1), (HOT_PROVEEDOR_ID, FECHA_Q1),
                         "Validar proveedor y contrato vigente"),
    "Q2": ConsultaPatron("Q2", Q2_SQL, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,), "20 SKUs negociados"),
    "Q3": ConsultaPatron("Q3", Q3_SQL, (CEDI_ID, COLD_FECHA_CEDI), (CEDI_ID, HOT_FECHA_CEDI),
                         "Franjas disponibles CEDI"),
    "Q4": ConsultaPatron("Q4", Q4_SQL, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,), "OTIF / Fill Rate 24 meses"),
    "Q5": ConsultaPatron("Q5", Q5_SQL, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,), "Últimas 50 órdenes"),
}
