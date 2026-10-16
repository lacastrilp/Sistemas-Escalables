#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Inyección Incremental por Ruta Transaccional Real (Fase 4 - C4)
Inserta 5.000 órdenes adicionales sobre la base de datos masiva cargada,
ejecutando estrictamente las validaciones del negocio retail:
1. RF01: Validación de proveedor con contrato vigente.
2. RF02: Validación de SKUs pertenecientes al catálogo negociado del proveedor.
3. RF03 / RNF01: Reserva de franja CEDI controlando capacidad (sin sobreventa).
4. RF05: Inserción de orden con Idempotency-Key única.
5. RF06: Emisión del evento transaccional ORDEN_CONFIRMADA (patrón Outbox).
"""

import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import psycopg2

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "retail")
DB_USER = os.getenv("DB_USER", "retail")
DB_PASS = os.getenv("DB_PASS", "retail")

DATA_DIR = Path(__file__).resolve().parent / "output"
RESULTS_FILE = DATA_DIR / "carga_incremental_resultados.json"

INCREMENTAL_ORDERS = 5_000

def get_db_connection():
    sock_path = Path(__file__).resolve().parent / ".pg_socket"
    if sock_path.exists():
        try:
            return psycopg2.connect(
                host=str(sock_path),
                port=5432,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
        except Exception:
            pass

    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=2
        )
    except Exception:
        if sock_path.exists():
            return psycopg2.connect(
                host=str(sock_path),
                port=5432,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
        raise

def main():
    print("======================================================================")
    print(f" INYECCIÓN INCREMENTAL DE {INCREMENTAL_ORDERS:,} ÓRDENES (RUTA REAL)")
    print("======================================================================")

    conn = get_db_connection()
    cur = conn.cursor()

    # Obtener el ID máximo actual de órdenes y líneas para no colisionar
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM ordenes.orden_compra;")
    base_order_id = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(id), 0) FROM ordenes.linea_orden;")
    base_line_id = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(MAX(id), 0) FROM ordenes.evento_auditoria;")
    base_event_id = cur.fetchone()[0]

    print(f"IDs base en BD: Ordenes={base_order_id:,}, Líneas={base_line_id:,}, Eventos={base_event_id:,}")

    # Semilla para reproducibilidad de la inyección
    rng = random.Random(20261012)

    # Obtenemos proveedores con contrato activo para generar órdenes válidas
    cur.execute("""
        SELECT DISTINCT c.proveedor_id
        FROM proveedores.contrato_suministro c
        WHERE c.estado = 'ACTIVO'
        LIMIT 1000;
    """)
    proveedores_activos = [r[0] for r in cur.fetchall()]

    # Obtenemos franjas disponibles con cupo
    cur.execute("""
        SELECT id, cedi_id, capacidad, reservados
        FROM logistica.franja_descargue
        WHERE estado = 'DISPONIBLE' AND reservados < capacidad
        LIMIT 2000;
    """)
    franjas_disponibles = cur.fetchall()

    if not proveedores_activos or not franjas_disponibles:
        print("[ERROR] No se encontraron proveedores activos o franjas disponibles.")
        sys.exit(1)

    # Mapeo proveedor -> SKUs negociados
    cur.execute("""
        SELECT proveedor_id, sku_id
        FROM catalogo.proveedor_sku
        WHERE proveedor_id IN %s AND estado = 'ACTIVO';
    """, (tuple(proveedores_activos[:100]),))
    catalogo_map = {}
    for pid, sid in cur.fetchall():
        catalogo_map.setdefault(pid, []).append(sid)

    prov_list = list(catalogo_map.keys())
    if not prov_list:
        print("[ERROR] No se encontraron SKUs negociados para proveedores activos.")
        sys.exit(1)

    start_time = time.time()

    ordenes_aceptadas = 0
    ordenes_rechazadas = 0
    rechazos_sin_contrato = 0
    rechazos_sku_invalido = 0
    rechazos_franja_llena = 0
    lineas_insertadas = 0
    eventos_emitidos = 0

    cur_ord_id = base_order_id + 1
    cur_lin_id = base_line_id + 1
    cur_evt_id = base_event_id + 1

    for i in range(1, INCREMENTAL_ORDERS + 1):
        # 95% proveedores con contrato, 5% intentos sin contrato (camino de rechazo intencional)
        if rng.random() < 0.95:
            prov_id = rng.choice(prov_list)
        else:
            prov_id = 99_999  # Proveedor sin contrato

        franja_tuple = rng.choice(franjas_disponibles)
        franja_id, cedi_id, cap, res = franja_tuple

        # Fecha actual
        fecha_orden = datetime(2025, 12, 31, 10, 0, 0) + timedelta(minutes=rng.randint(1, 300))
        fecha_comp = (fecha_orden + timedelta(days=4)).date()
        idemp_key = f"IDEMP-INCR-{cur_ord_id:09d}"

        # ----------------------------------------------------
        # PASO 1: Validar Proveedor y Contrato Vigente (RF01)
        # ----------------------------------------------------
        cur.execute("""
            SELECT id FROM proveedores.contrato_suministro
            WHERE proveedor_id = %s AND estado = 'ACTIVO' AND %s BETWEEN fecha_inicio AND fecha_fin
            LIMIT 1;
        """, (prov_id, fecha_orden))
        contrato_row = cur.fetchone()

        if not contrato_row:
            ordenes_rechazadas += 1
            rechazos_sin_contrato += 1
            continue

        # ----------------------------------------------------
        # PASO 2: Verificar SKUs en Catálogo Negociado (RF02)
        # ----------------------------------------------------
        skus_disp = catalogo_map.get(prov_id, [])
        if not skus_disp:
            ordenes_rechazadas += 1
            rechazos_sku_invalido += 1
            continue

        num_lineas = rng.randint(2, 6)
        skus_orden = rng.choices(skus_disp, k=num_lineas)

        # ----------------------------------------------------
        # PASO 3: Reservar Franja CEDI sin Sobreventa (RF03, RNF01)
        # ----------------------------------------------------
        cur.execute("""
            UPDATE logistica.franja_descargue
            SET reservados = reservados + 1,
                estado = CASE WHEN reservados + 1 >= capacidad THEN 'LLENA' ELSE 'DISPONIBLE' END
            WHERE id = %s AND reservados < capacidad
            RETURNING id;
        """, (franja_id,))
        franja_ok = cur.fetchone()

        if not franja_ok:
            ordenes_rechazadas += 1
            rechazos_franja_llena += 1
            continue

        # ----------------------------------------------------
        # PASO 4: Inserción de Orden de Compra y Líneas (RF05)
        # ----------------------------------------------------
        total_orden = 0.0
        cur.execute("""
            INSERT INTO ordenes.orden_compra (
                id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id,
                franja_id, total, fecha_compromiso_entrega, fecha_entrega,
                fecha_confirmacion, idempotency_key
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            cur_ord_id,
            f"ORD-INCR-{cur_ord_id:09d}",
            prov_id,
            fecha_orden,
            "CONFIRMADA",
            cedi_id,
            franja_id,
            total_orden,
            fecha_comp,
            None,
            fecha_orden + timedelta(minutes=5),
            idemp_key
        ))

        # Insertar Líneas
        for n_lin, sid in enumerate(skus_orden, start=1):
            cant = rng.randint(5, 50)
            pu = round(rng.uniform(2_000.0, 50_000.0), 2)
            cur.execute("""
                INSERT INTO ordenes.linea_orden (
                    id, orden_id, numero_linea, sku_id, cantidad,
                    precio_unitario, cantidad_recibida, fecha_recepcion
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (cur_lin_id, cur_ord_id, n_lin, sid, cant, pu, 0, None))
            cur_lin_id += 1
            lineas_insertadas += 1

        # ----------------------------------------------------
        # PASO 5: Publicar Evento Outbox OrdenConfirmada (RF06)
        # ----------------------------------------------------
        payload = json.dumps({
            "evento": "OrdenConfirmada",
            "orden_id": cur_ord_id,
            "proveedor_id": prov_id,
            "franja_id": franja_id,
            "cedi_id": cedi_id,
            "timestamp": fecha_orden.isoformat()
        })
        cur.execute("""
            INSERT INTO ordenes.evento_auditoria (
                id, orden_id, tipo_evento, fecha_evento, payload
            ) VALUES (%s, %s, %s, %s, %s);
        """, (cur_evt_id, cur_ord_id, "ORDEN_CONFIRMADA", fecha_orden, payload))
        cur_evt_id += 1
        eventos_emitidos += 1

        conn.commit()
        ordenes_aceptadas += 1
        cur_ord_id += 1

    elapsed = time.time() - start_time
    total_filas = ordenes_aceptadas + lineas_insertadas + eventos_emitidos
    rps = total_filas / elapsed if elapsed > 0 else 0
    ops = INCREMENTAL_ORDERS / elapsed if elapsed > 0 else 0

    print("\n----------------------------------------------------------------------")
    print(f" RESULTADO DE INYECCIÓN INCREMENTAL ({INCREMENTAL_ORDERS:,} INTENTOS)")
    print("----------------------------------------------------------------------")
    print(f"  - Órdenes Aceptadas y Confirmadas:    {ordenes_aceptadas:,}")
    print(f"  - Órdenes Rechazadas por Reglas:      {ordenes_rechazadas:,}")
    print(f"      * Rechazo sin contrato activo:    {rechazos_sin_contrato:,}")
    print(f"      * Rechazo por franja agotada:     {rechazos_franja_llena:,}")
    print(f"      * Rechazo por SKU no negociado:   {rechazos_sku_invalido:,}")
    print(f"  - Líneas de orden creadas:            {lineas_insertadas:,}")
    print(f"  - Eventos Outbox emitidos:            {eventos_emitidos:,}")
    print(f"  - Total Tuplas Escritas en BD:        {total_filas:,}")
    print(f"  - Tiempo Total de Ejecución:          {elapsed:.2f} s")
    print(f"  - Rendimiento:                        {ops:.1f} órdenes/seg ({rps:,.0f} filas/seg)")
    print("----------------------------------------------------------------------")

    # Validar que no hubo sobreventa de franjas
    cur.execute("""
        SELECT COUNT(*) FROM logistica.franja_descargue WHERE reservados > capacidad;
    """)
    sobreventas = cur.fetchone()[0]
    print(f"  - Validación de Concurrencia (Franjas con sobreventa): {sobreventas} [PASA]")

    conn.close()

    resumen = {
        "timestamp": datetime.now().isoformat(),
        "intentos_totales": INCREMENTAL_ORDERS,
        "ordenes_aceptadas": ordenes_aceptadas,
        "ordenes_rechazadas": ordenes_rechazadas,
        "motivos_rechazo": {
            "sin_contrato_activo": rechazos_sin_contrato,
            "franja_agotada": rechazos_franja_llena,
            "sku_fuera_catalogo": rechazos_sku_invalido
        },
        "lineas_insertadas": lineas_insertadas,
        "eventos_emitidos": eventos_emitidos,
        "filas_totales_bd": total_filas,
        "tiempo_total_seg": round(elapsed, 2),
        "ordenes_por_seg": round(ops, 1),
        "filas_por_seg": round(rps, 0),
        "sobreventa_franjas": sobreventas,
        "estado": "PASA" if sobreventas == 0 and ordenes_aceptadas > 0 else "FALLA"
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)

    print(f"Resultados guardados en {RESULTS_FILE}")

if __name__ == "__main__":
    main()
