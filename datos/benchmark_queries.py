#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Benchmark de Consultas (Q1 - Q5)
Mide la latencia de las 5 consultas patrón en PostgreSQL con el dataset cargado a escala (5.4M filas).
Calcula percentiles p50, p95, p99 para 200 ejecuciones en escenarios frío (proveedor cola larga) y caliente (proveedor top 1%).
Extrae los planes EXPLAIN (ANALYZE, BUFFERS) para Q4 y Q5.
"""

import json
import math
import time
from pathlib import Path
import psycopg2

DB_HOST = "127.0.0.1"
DB_PORT = 5435
DB_NAME = "retail"
DB_USER = "retail"
DB_PASS = "retail"

DATA_DIR = Path(__file__).resolve().parent / "output"
RESULTS_FILE = DATA_DIR / "benchmark_queries_resultados.json"

ITERATIONS = 200

# Parámetros del benchmark
COLD_PROVEEDOR_ID = 50000
HOT_PROVEEDOR_ID = 1

COLD_FECHA_CEDI = "2024-05-15"
HOT_FECHA_CEDI = "2025-12-31" # Días pico de fin de mes

CEDI_ID = 1

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def percentile(data, p):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1

def run_query_benchmark(conn, sql, params, iterations=ITERATIONS):
    latencies_ms = []
    with conn.cursor() as cur:
        # Calentamiento rápido (1 ejecucion)
        cur.execute(sql, params)
        cur.fetchall()
        
        for _ in range(iterations):
            start = time.perf_counter()
            cur.execute(sql, params)
            cur.fetchall()
            end = time.perf_counter()
            latencies_ms.append((end - start) * 1000.0)
            
    p50 = percentile(latencies_ms, 50)
    p95 = percentile(latencies_ms, 95)
    p99 = percentile(latencies_ms, 99)
    avg = sum(latencies_ms) / len(latencies_ms)
    
    return {
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "avg_ms": round(avg, 3),
        "min_ms": round(min(latencies_ms), 3),
        "max_ms": round(max(latencies_ms), 3)
    }

def get_explain_analyze(conn, sql, params):
    explain_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql
    with conn.cursor() as cur:
        cur.execute(explain_sql, params)
        raw_plan = cur.fetchone()[0]
    return raw_plan

def main():
    print("======================================================================")
    print(" BENCHMARK DE CONSULTAS PATRÓN Q1 - Q5 (200 ITERACIONES)")
    print("======================================================================")
    
    conn = get_connection()
    
    # ------------------------------------------------------------------
    # DEFINICIÓN DE CONSULTAS SQL
    # ------------------------------------------------------------------
    
    # Q1: Proveedor + Contrato Vigente
    q1_sql = """
    SELECT p.id, p.nit, p.nombre, c.id AS contrato_id, c.fecha_inicio, c.fecha_fin, c.estado
    FROM proveedores.proveedor p
    JOIN proveedores.contrato_suministro c ON c.proveedor_id = p.id
    WHERE p.id = %s AND %s BETWEEN c.fecha_inicio AND c.fecha_fin;
    """
    
    # Q2: 20 SKU del Catálogo Negociado
    q2_sql = """
    SELECT ps.sku_id, s.codigo, s.nombre, ps.precio_negociado
    FROM catalogo.proveedor_sku ps
    JOIN catalogo.sku s ON s.id = ps.sku_id
    WHERE ps.proveedor_id = %s AND ps.estado = 'ACTIVO'
    ORDER BY ps.sku_id
    LIMIT 20;
    """
    
    # Q3: Franjas disponibles de un CEDI
    q3_sql = """
    SELECT id, fecha, hora_inicio, hora_fin, capacidad, reservados
    FROM logistica.franja_descargue
    WHERE cedi_id = %s AND fecha = %s AND estado = 'DISPONIBLE' AND reservados < capacidad
    ORDER BY hora_inicio;
    """
    
    # Q4: OTIF y Fill Rate
    q4_sql = """
    SELECT 
        o.proveedor_id,
        DATE_TRUNC('month', o.fecha_orden) AS mes,
        COUNT(DISTINCT o.id) AS total_ordenes,
        COUNT(DISTINCT CASE WHEN o.estado = 'ENTREGADA' AND o.fecha_entrega IS NOT NULL AND o.fecha_confirmacion IS NOT NULL AND o.fecha_confirmacion <= o.fecha_entrega THEN o.id END) AS ordenes_otif,
        ROUND(
            COUNT(DISTINCT CASE WHEN o.estado = 'ENTREGADA' AND o.fecha_entrega IS NOT NULL AND o.fecha_confirmacion IS NOT NULL AND o.fecha_confirmacion <= o.fecha_entrega THEN o.id END)::NUMERIC / NULLIF(COUNT(DISTINCT o.id), 0) * 100, 2
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
    
    # Q5: Últimas 50 órdenes paginadas
    q5_sql = """
    SELECT id, numero_orden, proveedor_id, fecha_orden, estado, total
    FROM ordenes.orden_compra
    WHERE proveedor_id = %s
    ORDER BY fecha_orden DESC
    LIMIT 50;
    """
    
    queries = {
        "Q1": (q1_sql, (COLD_PROVEEDOR_ID, "2025-06-15"), (HOT_PROVEEDOR_ID, "2025-06-15")),
        "Q2": (q2_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,)),
        "Q3": (q3_sql, (CEDI_ID, COLD_FECHA_CEDI), (CEDI_ID, HOT_FECHA_CEDI)),
        "Q4": (q4_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,)),
        "Q5": (q5_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,))
    }
    
    results = {}
    explains = {}
    
    for q_name, (sql, params_cold, params_hot) in queries.items():
        print(f"\n[Midiendo {q_name}...]")
        cold_res = run_query_benchmark(conn, sql, params_cold)
        hot_res = run_query_benchmark(conn, sql, params_hot)
        
        results[q_name] = {
            "frio": cold_res,
            "caliente": hot_res
        }
        
        print(f"  {q_name} Frío     : p50={cold_res['p50_ms']} ms, p95={cold_res['p95_ms']} ms, p99={cold_res['p99_ms']} ms")
        print(f"  {q_name} Caliente : p50={hot_res['p50_ms']} ms, p95={hot_res['p95_ms']} ms, p99={hot_res['p99_ms']} ms")
        
        if q_name in ("Q4", "Q5"):
            explains[f"{q_name}_frio"] = get_explain_analyze(conn, sql, params_cold)
            explains[f"{q_name}_caliente"] = get_explain_analyze(conn, sql, params_hot)
            
    conn.close()
    
    # Guardar resultados
    output_payload = {
        "metricas": results,
        "explains": explains
    }
    
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)
        
    print("\n======================================================================")
    print(" TABLA RESUMEN DE LATENCIAS Q1 - Q5 (p50, p95, p99 en ms)")
    print("======================================================================")
    print(f"{'ID':<4} | {'Escenario':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Prom (ms)':<10}")
    print("-" * 65)
    for q_name, data in results.items():
        for esc in ("frio", "caliente"):
            m = data[esc]
            print(f"{q_name:<4} | {esc.capitalize():<10} | {m['p50_ms']:<10.3f} | {m['p95_ms']:<10.3f} | {m['p99_ms']:<10.3f} | {m['avg_ms']:<10.3f}")
    print("======================================================================")

if __name__ == "__main__":
    main()
