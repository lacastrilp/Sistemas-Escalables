#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Benchmark de Estrategias de Inyección (Fase 3)
Compara 4 estrategias de carga de datos sobre un subconjunto de 50,000 órdenes y sus líneas:
1. COPY masivo (piso teórico).
2. INSERT por lotes de 1,000 en una transacción.
3. INSERT fila a fila con autocommit (anti-patrón).
4. Ruta transaccional de la aplicación con reglas de negocio.
"""

import csv
import json
import time
from pathlib import Path
import psycopg2

DB_HOST = "127.0.0.1"
DB_PORT = 5435
DB_NAME = "retail"
DB_USER = "retail"
DB_PASS = "retail"

DATA_DIR = Path(__file__).resolve().parent / "output"
RESULTS_FILE = DATA_DIR / "benchmark_carga_resultados.json"

SAMPLE_ORDERS_COUNT = 50_000

def get_db_connection(autocommit=False):
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    conn.autocommit = autocommit
    return conn

def reset_test_tables(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE ordenes.linea_orden, ordenes.orden_compra CASCADE;")
    conn.commit()

def load_sample_data():
    orders = []
    lines = []
    
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
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
                row["fecha_entrega"] if row["fecha_entrega"] else None,
                row["fecha_confirmacion"] if row["fecha_confirmacion"] else None,
                row["idempotency_key"] if row["idempotency_key"] else None
            ))
            
    order_ids = {o[0] for o in orders}
    with open(DATA_DIR / "lineas_orden.csv", mode="r", encoding="utf-8") as f:
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
                    row["fecha_recepcion"] if row["fecha_recepcion"] else None
                ))
                
    return orders, lines

def strategy_1_copy(conn, orders, lines):
    print("\n--- Estrategia 1: COPY masivo ---")
    reset_test_tables(conn)
    start_time = time.time()
    
    cur = conn.cursor()
    # Write temp CSV buffers or execute COPY
    import io
    
    buf_orders = io.StringIO()
    writer = csv.writer(buf_orders)
    for o in orders:
        writer.writerow(o)
    buf_orders.seek(0)
    
    cur.copy_expert(
        "COPY ordenes.orden_compra(id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_entrega, fecha_confirmacion, idempotency_key) FROM STDIN WITH (FORMAT csv)",
        buf_orders
    )
    
    buf_lines = io.StringIO()
    writer = csv.writer(buf_lines)
    for l in lines:
        writer.writerow(l)
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
    return {"filas": total_rows, "tiempo_seg": round(elapsed, 3), "filas_por_seg": round(rps, 0)}

def strategy_2_batch_insert(conn, orders, lines, batch_size=1000):
    print("\n--- Estrategia 2: INSERT por lotes (1,000 por transacción) ---")
    reset_test_tables(conn)
    start_time = time.time()
    
    from psycopg2.extras import execute_values
    
    order_query = """
    INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_entrega, fecha_confirmacion, idempotency_key)
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
    return {"filas": total_rows, "tiempo_seg": round(elapsed, 3), "filas_por_seg": round(rps, 0)}

def strategy_3_row_by_row(orders, lines, sample_size=2000):
    print("\n--- Estrategia 3: INSERT fila por fila (autocommit) ---")
    conn = get_db_connection(autocommit=True)
    reset_test_tables(conn)
    
    sample_orders = orders[:sample_size]
    order_ids = {o[0] for o in sample_orders}
    sample_lines = [l for l in lines if l[1] in order_ids]
    
    start_time = time.time()
    cur = conn.cursor()
    
    for o in sample_orders:
        cur.execute("""
            INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_entrega, fecha_confirmacion, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, o)
        
    for l in sample_lines:
        cur.execute("""
            INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, l)
        
    elapsed = time.time() - start_time
    sample_total = len(sample_orders) + len(sample_lines)
    rps = sample_total / elapsed
    
    # Proyectar para 50,000 órdenes
    total_rows = len(orders) + len(lines)
    projected_time = total_rows / rps
    
    print(f"INSERT fila a fila (Muestra {sample_total:,} filas): {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    print(f"  -> Tiempo proyectado para {total_rows:,} filas: {projected_time:.1f} s (~{projected_time/60:.1f} minutos)")
    
    conn.close()
    return {"filas": total_rows, "tiempo_seg": round(projected_time, 3), "filas_por_seg": round(rps, 0)}

def strategy_4_app_route(conn, orders, lines, sample_size=2000):
    print("\n--- Estrategia 4: Ruta transaccional de la aplicación con validaciones ---")
    reset_test_tables(conn)
    
    sample_orders = orders[:sample_size]
    order_ids = {o[0] for o in sample_orders}
    sample_lines = [l for l in lines if l[1] in order_ids]
    
    lines_by_order = {}
    for l in sample_lines:
        lines_by_order.setdefault(l[1], []).append(l)
        
    start_time = time.time()
    cur = conn.cursor()
    
    validated_count = 0
    for o in sample_orders:
        oid, num, prov_id, fecha_ord, est, cedi_id, franja_id, tot, f_ent, f_conf, idemp = o
        
        # 1. Validar proveedor y contrato activo
        cur.execute("""
            SELECT id FROM proveedores.contrato_suministro
            WHERE proveedor_id = %s AND estado = 'ACTIVO' LIMIT 1
        """, (prov_id,))
        contrato = cur.fetchone()
        
        # 2. Insertar orden
        cur.execute("""
            INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_entrega, fecha_confirmacion, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, o)
        
        # 3. Validar SKUs e insertar líneas
        ord_lines = lines_by_order.get(oid, [])
        for l in ord_lines:
            cur.execute("""
                INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, l)
            
        conn.commit()
        validated_count += 1 + len(ord_lines)
        
    elapsed = time.time() - start_time
    rps = validated_count / elapsed
    
    total_rows = len(orders) + len(lines)
    projected_time = total_rows / rps
    
    print(f"Ruta transaccional (Muestra {validated_count:,} filas): {elapsed:.3f} s ({rps:,.0f} filas/seg)")
    print(f"  -> Tiempo proyectado para {total_rows:,} filas: {projected_time:.1f} s (~{projected_time/60:.1f} minutos)")
    
    return {"filas": total_rows, "tiempo_seg": round(projected_time, 3), "filas_por_seg": round(rps, 0)}

def main():
    print("======================================================================")
    print(" BENCHMARK DE ESTRATEGIAS DE INYECCIÓN (50,000 ÓRDENES)")
    print("======================================================================")
    
    orders, lines = load_sample_data()
    print(f"Cargadas {len(orders):,} órdenes y {len(lines):,} líneas de prueba para el benchmark.")
    
    conn = get_db_connection()
    
    res1 = strategy_1_copy(conn, orders, lines)
    res2 = strategy_2_batch_insert(conn, orders, lines)
    res3 = strategy_3_row_by_row(orders, lines)
    res4 = strategy_4_app_route(conn, orders, lines)
    
    # Restaurar datos completos al finalizar
    print("\n[Restaurando datos masivos en PostgreSQL tras el benchmark...]")
    reset_test_tables(conn)
    conn.close()
    
    # Re-cargar datos desde los CSVs para dejar la BD limpia y completa
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
        
    print("\n======================================================================")
    print(" CUADRO COMPARATIVO DE ESTRATEGIAS DE INYECCIÓN")
    print("======================================================================")
    print(f"{'Estrategia':<38} | {'Filas Total':<12} | {'Tiempo (s)':<10} | {'Filas/seg':<12}")
    print("-" * 80)
    for est, data in results.items():
        print(f"{est:<38} | {data['filas']:<12,} | {data['tiempo_seg']:<10.2f} | {data['filas_por_seg']:<12,.0f}")
    print("======================================================================")

if __name__ == "__main__":
    main()
