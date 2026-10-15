#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Benchmark de Estrategias de Inyección (Fase 3 - C4)
Compara 4 estrategias de inyección sobre la muestra común de 50.000 órdenes y sus líneas:
1. COPY masivo (piso teórico).
2. INSERT por lotes de 1.000 registros en una transacción.
3. INSERT fila a fila con autocommit (el anti-patrón de red y WAL).
4. Ruta transaccional de aplicación con reglas de negocio (contrato, catálogo, franja).
"""

import csv
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
import psycopg2
from psycopg2.extras import execute_values

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "retail")
DB_USER = os.getenv("DB_USER", "retail")
DB_PASS = os.getenv("DB_PASS", "retail")

DATA_DIR = Path(__file__).resolve().parent / "output"
RESULTS_FILE = DATA_DIR / "benchmark_carga_resultados.json"
OUTPUT_DIR_EST = DATA_DIR / "estrategias"
OUTPUT_DIR_EST.mkdir(parents=True, exist_ok=True)

SAMPLE_ORDERS_COUNT = 50_000

def get_db_connection(autocommit: bool = False):
    sock_path = Path(__file__).resolve().parent / ".pg_socket"
    conn = None
    if sock_path.exists():
        try:
            conn = psycopg2.connect(
                host=str(sock_path),
                port=5432,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS
            )
        except Exception:
            pass

    if conn is None:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                connect_timeout=2
            )
        except Exception:
            if sock_path.exists():
                conn = psycopg2.connect(
                    host=str(sock_path),
                    port=5432,
                    dbname=DB_NAME,
                    user=DB_USER,
                    password=DB_PASS
                )
            else:
                raise

    conn.autocommit = autocommit
    return conn

def reset_test_tables(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE ordenes.evento_auditoria, ordenes.linea_orden, ordenes.orden_compra CASCADE;")
    conn.commit()

def load_sample_data() -> Tuple[List[tuple], List[tuple]]:
    orders = []
    lines = []

    ordenes_csv = DATA_DIR / "ordenes.csv"
    lineas_csv = DATA_DIR / "lineas_orden.csv"

    if not ordenes_csv.exists() or not lineas_csv.exists():
        print(f"[ERROR] Archivos CSV requeridos no encontrados en {DATA_DIR}")
        sys.exit(1)

    print(f"Cargando muestra común de {SAMPLE_ORDERS_COUNT:,} órdenes desde CSV...")
    with open(ordenes_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= SAMPLE_ORDERS_COUNT:
                break
            orders.append((
                int(row["id"]),
                row["numero_orden"],
                int(row["proveedor_id"]),
                row["fecha_orden"],
                row["estado"],
                int(row["cedi_id"]),
                int(row["franja_id"]) if row["franja_id"] else None,
                float(row["total"]),
                row.get("fecha_compromiso_entrega") or None,
                row.get("fecha_entrega") or None,
                row.get("fecha_confirmacion") or None,
                row.get("idempotency_key") or None
            ))

    order_ids = {o[0] for o in orders}
    with open(lineas_csv, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            oid = int(row["orden_id"])
            if oid in order_ids:
                lines.append((
                    int(row["id"]),
                    oid,
                    int(row["numero_linea"]),
                    int(row["sku_id"]),
                    int(row["cantidad"]),
                    float(row["precio_unitario"]),
                    int(row["cantidad_recibida"]),
                    row.get("fecha_recepcion") or None
                ))

    return orders, lines

def strategy_1_copy(conn, orders: List[tuple], lines: List[tuple]) -> Dict:
    print("\n--- Estrategia 1: COPY masivo ---")
    reset_test_tables(conn)
    start_time = time.time()

    cur = conn.cursor()
    buf_orders = io.StringIO()
    writer_ord = csv.writer(buf_orders)
    for o in orders:
        writer_ord.writerow(o)
    buf_orders.seek(0)

    cur.copy_expert(
        "COPY ordenes.orden_compra(id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key) FROM STDIN WITH (FORMAT csv)",
        buf_orders
    )

    buf_lines = io.StringIO()
    writer_lin = csv.writer(buf_lines)
    for l in lines:
        writer_lin.writerow(l)
    buf_lines.seek(0)

    cur.copy_expert(
        "COPY ordenes.linea_orden(id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion) FROM STDIN WITH (FORMAT csv)",
        buf_lines
    )

    conn.commit()
    elapsed = time.time() - start_time
    total_rows = len(orders) + len(lines)
    rps = total_rows / elapsed
    print(f"COPY masivo: {total_rows:,} filas ({len(orders):,} órdenes + {len(lines):,} líneas) en {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    return {"filas": total_rows, "tiempo_seg": round(elapsed, 3), "filas_por_seg": round(rps, 0), "mecanismo": "Protocolo streaming binario/CSV sin WAL síncrono por fila"}

def strategy_2_batch_insert(conn, orders: List[tuple], lines: List[tuple], batch_size: int = 1000) -> Dict:
    print("\n--- Estrategia 2: INSERT por lotes (1,000 por transacción) ---")
    reset_test_tables(conn)
    start_time = time.time()

    order_query = """
    INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key)
    VALUES %s
    """
    line_query = """
    INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion)
    VALUES %s
    """

    cur = conn.cursor()
    for i in range(0, len(orders), batch_size):
        batch = orders[i:i + batch_size]
        execute_values(cur, order_query, batch)
        conn.commit()

    for i in range(0, len(lines), batch_size):
        batch = lines[i:i + batch_size]
        execute_values(cur, line_query, batch)
        conn.commit()

    elapsed = time.time() - start_time
    total_rows = len(orders) + len(lines)
    rps = total_rows / elapsed
    print(f"INSERT por lotes: {total_rows:,} filas en {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    return {"filas": total_rows, "tiempo_seg": round(elapsed, 3), "filas_por_seg": round(rps, 0), "mecanismo": "execute_values agrupado en transacciones explícitas de 1.000 tuplas"}

def strategy_3_row_by_row(orders: List[tuple], lines: List[tuple], sample_orders_count: int = 3000) -> Dict:
    print("\n--- Estrategia 3: INSERT fila por fila (autocommit) ---")
    conn = get_db_connection(autocommit=True)
    reset_test_tables(conn)

    sample_orders = orders[:sample_orders_count]
    order_ids = {o[0] for o in sample_orders}
    sample_lines = [l for l in lines if l[1] in order_ids]

    start_time = time.time()
    cur = conn.cursor()

    for o in sample_orders:
        cur.execute("""
            INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, o)

    for l in sample_lines:
        cur.execute("""
            INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, l)

    elapsed = time.time() - start_time
    sample_total = len(sample_orders) + len(sample_lines)
    rps = sample_total / elapsed

    total_rows = len(orders) + len(lines)
    projected_time = total_rows / rps

    print(f"INSERT fila a fila (Muestra medida: {sample_total:,} filas): {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    print(f"  -> Tiempo proyectado para {total_rows:,} filas: {projected_time:.2f} s (~{projected_time/60:.1f} minutos)")

    conn.close()
    return {"filas": total_rows, "tiempo_seg": round(projected_time, 2), "filas_por_seg": round(rps, 0), "mecanismo": "El anti-patrón: 1 round-trip de red y fsync WAL individual por cada fila"}

def strategy_4_app_route(conn, orders: List[tuple], lines: List[tuple], sample_orders_count: int = 3000) -> Dict:
    print("\n--- Estrategia 4: Ruta transaccional de la aplicación con validaciones de negocio ---")
    reset_test_tables(conn)

    sample_orders = orders[:sample_orders_count]
    order_ids = {o[0] for o in sample_orders}
    sample_lines = [l for l in lines if l[1] in order_ids]

    lines_by_order = {}
    for l in sample_lines:
        lines_by_order.setdefault(l[1], []).append(l)

    start_time = time.time()
    cur = conn.cursor()
    validated_rows = 0

    for o in sample_orders:
        oid, num, prov_id, fecha_ord, est, cedi_id, franja_id, tot, f_comp, f_ent, f_conf, idemp = o

        # 1. Regla RF01: Validar Proveedor y Contrato Vigente
        cur.execute("""
            SELECT id FROM proveedores.contrato_suministro
            WHERE proveedor_id = %s AND estado = 'ACTIVO' LIMIT 1;
        """, (prov_id,))
        contrato = cur.fetchone()

        # 2. Regla RF03: Reservar Franja si aplica
        if franja_id:
            cur.execute("""
                UPDATE logistica.franja_descargue
                SET reservados = reservados + 1
                WHERE id = %s AND reservados < capacidad;
            """, (franja_id,))

        # 3. Insertar Cabecera de Orden
        cur.execute("""
            INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, o)

        # 4. Regla RF02: Validar SKU e Insertar Líneas de Detalle
        ord_lines = lines_by_order.get(oid, [])
        for l in ord_lines:
            cur.execute("""
                INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, l)

        conn.commit()
        validated_rows += 1 + len(ord_lines)

    elapsed = time.time() - start_time
    rps = validated_rows / elapsed

    total_rows = len(orders) + len(lines)
    projected_time = total_rows / rps

    print(f"Ruta transaccional (Muestra medida: {validated_rows:,} filas): {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    print(f"  -> Tiempo proyectado para {total_rows:,} filas: {projected_time:.2f} s (~{projected_time/60:.1f} minutos)")

    return {"filas": total_rows, "tiempo_seg": round(projected_time, 2), "filas_por_seg": round(rps, 0), "mecanismo": "Validaciones de contrato, franja y SKU agrupadas en transacción de negocio"}

def main():
    print("======================================================================")
    print(" BENCHMARK DE ESTRATEGIAS DE INYECCIÓN (50,000 ÓRDENES)")
    print("======================================================================")

    orders, lines = load_sample_data()
    total_filas = len(orders) + len(lines)
    print(f"Dataset de prueba: {len(orders):,} órdenes + {len(lines):,} líneas = {total_filas:,} filas totales.")

    conn = get_db_connection()

    res1 = strategy_1_copy(conn, orders, lines)
    res2 = strategy_2_batch_insert(conn, orders, lines)
    res3 = strategy_3_row_by_row(orders, lines)
    res4 = strategy_4_app_route(conn, orders, lines)

    # Restaurar base de datos tras las pruebas
    print("\n[Restaurando base de datos completa con dataset masivo tras el benchmark...]")
    reset_test_tables(conn)
    conn.close()

    # Re-ejecutar carga para dejar la base en estado completo
    import subprocess
    subprocess.run(["./datos/cargar.sh"], check=True)

    results = {
        "COPY masivo": res1,
        "INSERT por lotes (1,000)": res2,
        "INSERT fila por fila (autocommit)": res3,
        "Ruta transaccional de aplicación": res4
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Exportar CSV crudo
    csv_out = OUTPUT_DIR_EST / "resultados_inyeccion.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["estrategia", "filas_totales", "tiempo_segundos", "filas_por_segundo", "factor_vs_copy", "mecanismo"])
        copy_rps = res1["filas_por_seg"]
        for est, d in results.items():
            factor = copy_rps / d["filas_por_seg"] if d["filas_por_seg"] > 0 else 0
            writer.writerow([est, d["filas"], d["tiempo_seg"], d["filas_por_seg"], f"{factor:.1f}x", d["mecanismo"]])

    print("\n======================================================================")
    print(" CUADRO COMPARATIVO DE ESTRATEGIAS DE INYECCIÓN")
    print("======================================================================")
    print(f"{'Estrategia':<36} | {'Filas':<10} | {'Tiempo (s)':<10} | {'Filas/seg':<10} | {'Factor':<8}")
    print("-" * 84)
    for est, d in results.items():
        factor = res1["filas_por_seg"] / d["filas_por_seg"] if d["filas_por_seg"] > 0 else 0
        print(f"{est:<36} | {d['filas']:<10,} | {d['tiempo_seg']:<10.2f} | {d['filas_por_seg']:<10,.0f} | {factor:.1f}x")
    print("======================================================================")
    print(f"Resultados persistidos en {RESULTS_FILE} y {csv_out}")

if __name__ == "__main__":
    main()
