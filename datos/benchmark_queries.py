#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Benchmark de Consultas Patrón Q1 - Q5 y Comparativa de Planes EXPLAIN (C5)
Mide con alta resolución (time.perf_counter) 200 iteraciones por consulta y escenario:
- Q1: Validar proveedor y contrato vigente por proveedor_id y fecha (<10 ms).
- Q2: 20 SKUs del catálogo negociado de un proveedor.
- Q3: Franjas disponibles de un CEDI para una fecha.
- Q4: OTIF y Fill Rate por proveedor y mes sobre 24 meses (Analítica pesada).
- Q5: Últimas 50 órdenes de un proveedor caliente, paginadas.

Genera los planes EXPLAIN (ANALYZE, BUFFERS) antes y después de:
1. idx_orden_proveedor_fecha
2. idx_linea_orden
"""

import csv
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple
import psycopg2

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "retail")
DB_USER = os.getenv("DB_USER", "retail")
DB_PASS = os.getenv("DB_PASS", "retail")

DATA_DIR = Path(__file__).resolve().parent / "output"
QUERIES_DIR = DATA_DIR / "queries"
EXPLAIN_DIR = DATA_DIR / "explain"
QUERIES_DIR.mkdir(parents=True, exist_ok=True)
EXPLAIN_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_FILE = DATA_DIR / "benchmark_queries_resultados.json"

ITERATIONS = 200

# Parámetros del benchmark obtenidos del dataset real
HOT_PROVEEDOR_ID = 1      # Superproveedor top 1% (acumula > 20.000 órdenes)
COLD_PROVEEDOR_ID = 50000  # Proveedor de cola larga

CEDI_ID = 1
COLD_FECHA_CEDI = "2024-05-15"   # Día representativo estándar
HOT_FECHA_CEDI = "2025-12-31"    # Día pico de fin de mes y alta concurrencia

def get_connection():
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

def percentile(data: List[float], p: float) -> float:
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

def ejecutar_benchmark_consulta(conn, sql: str, params: tuple, q_name: str, escenario: str, obs_writer) -> Dict:
    latencias_ms = []
    with conn.cursor() as cur:
        # Calentamiento (warmup) de 2 iteraciones
        for _ in range(2):
            cur.execute(sql, params)
            cur.fetchall()

        # 200 iteraciones cronometradas con reloj monotónico de alta resolución
        for it in range(1, ITERATIONS + 1):
            t_start = time.perf_counter()
            cur.execute(sql, params)
            cur.fetchall()
            t_end = time.perf_counter()
            lat_ms = (t_end - t_start) * 1000.0
            latencias_ms.append(lat_ms)
            if obs_writer:
                obs_writer.writerow([q_name, escenario, it, round(lat_ms, 4)])

    p50 = percentile(latencias_ms, 50)
    p95 = percentile(latencias_ms, 95)
    p99 = percentile(latencias_ms, 99)
    avg = sum(latencias_ms) / len(latencias_ms)

    return {
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "avg_ms": round(avg, 3),
        "min_ms": round(min(latencias_ms), 3),
        "max_ms": round(max(latencias_ms), 3),
        "iteraciones": len(latencias_ms)
    }

def capturar_explain_buffers(conn, sql: str, params: tuple) -> str:
    explain_sql = "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, COSTS, TIMING) " + sql
    with conn.cursor() as cur:
        cur.execute(explain_sql, params)
        lines = [r[0] for r in cur.fetchall()]
    return "\n".join(lines)

def evaluar_experimento_indices(conn, q4_sql, q5_sql):
    """
    Produce la evidencia exigida en C5:
    1. Baseline sin índices secundarios: Q4 y Q5 tras carga y ANALYZE.
    2. Después de idx_orden_proveedor_fecha: Q4 y Q5.
    3. Después de idx_linea_orden: Q4.
    """
    print("\n======================================================================")
    print(" GENERANDO EVIDENCIA COMPARATIVA EXPLAIN (ANALYZE, BUFFERS)")
    print("======================================================================")
    cur = conn.cursor()

    # 1. Quitar índices temporales para medir estado baseline sin índices
    print("[1/4] Eliminando índices secundarios para capturar baseline...")
    cur.execute("""
        DROP INDEX IF EXISTS ordenes.idx_orden_proveedor_fecha;
        DROP INDEX IF EXISTS ordenes.idx_linea_orden;
        ANALYZE ordenes.orden_compra;
        ANALYZE ordenes.linea_orden;
    """)
    conn.commit()

    plan_q4_antes = capturar_explain_buffers(conn, q4_sql, (HOT_PROVEEDOR_ID,))
    plan_q5_antes = capturar_explain_buffers(conn, q5_sql, (HOT_PROVEEDOR_ID,))

    with open(EXPLAIN_DIR / "q4_antes_indices.txt", "w", encoding="utf-8") as f:
        f.write(plan_q4_antes)
    with open(EXPLAIN_DIR / "q5_antes_indices.txt", "w", encoding="utf-8") as f:
        f.write(plan_q5_antes)
    print("      OK: q4_antes_indices.txt y q5_antes_indices.txt guardados.")

    # 2. Crear primer índice: idx_orden_proveedor_fecha
    print("[2/4] Creando idx_orden_proveedor_fecha...")
    cur.execute("""
        CREATE INDEX idx_orden_proveedor_fecha ON ordenes.orden_compra(proveedor_id, fecha_orden);
        ANALYZE ordenes.orden_compra;
    """)
    conn.commit()

    plan_q4_despues_idx_ord = capturar_explain_buffers(conn, q4_sql, (HOT_PROVEEDOR_ID,))
    plan_q5_despues_idx_ord = capturar_explain_buffers(conn, q5_sql, (HOT_PROVEEDOR_ID,))

    with open(EXPLAIN_DIR / "q4_despues_idx_orden_proveedor_fecha.txt", "w", encoding="utf-8") as f:
        f.write(plan_q4_despues_idx_ord)
    with open(EXPLAIN_DIR / "q5_despues_idx_orden_proveedor_fecha.txt", "w", encoding="utf-8") as f:
        f.write(plan_q5_despues_idx_ord)
    print("      OK: q4_despues_idx_orden_proveedor_fecha.txt y q5_despues_idx_orden_proveedor_fecha.txt guardados.")

    # 3. Crear segundo índice: idx_linea_orden
    print("[3/4] Creando idx_linea_orden...")
    cur.execute("""
        CREATE INDEX idx_linea_orden ON ordenes.linea_orden(orden_id);
        ANALYZE ordenes.linea_orden;
    """)
    conn.commit()

    plan_q4_despues_idx_lin = capturar_explain_buffers(conn, q4_sql, (HOT_PROVEEDOR_ID,))

    with open(EXPLAIN_DIR / "q4_despues_idx_linea_orden.txt", "w", encoding="utf-8") as f:
        f.write(plan_q4_despues_idx_lin)
    print("      OK: q4_despues_idx_linea_orden.txt guardado.")

    # 4. Asegurar todos los índices del catálogo y logística
    print("[4/4] Restaurando todos los índices secundarios restantes...")
    with open(Path(__file__).resolve().parent / "sql" / "indices_secundarios.sql", "r", encoding="utf-8") as f:
        cur.execute(f.read())
    cur.execute("ANALYZE;")
    conn.commit()
    print("      OK: Base de datos indexada y analizada completamente.")

    resumen_explain = {
        "q4": {
            "archivo_antes": "datos/output/explain/q4_antes_indices.txt",
            "archivo_idx_orden": "datos/output/explain/q4_despues_idx_orden_proveedor_fecha.txt",
            "archivo_idx_lineas": "datos/output/explain/q4_despues_idx_linea_orden.txt"
        },
        "q5": {
            "archivo_antes": "datos/output/explain/q5_antes_indices.txt",
            "archivo_despues": "datos/output/explain/q5_despues_idx_orden_proveedor_fecha.txt"
        }
    }
    with open(EXPLAIN_DIR / "resumen_comparacion_indices.json", "w", encoding="utf-8") as f:
        json.dump(resumen_explain, f, indent=2, ensure_ascii=False)

def main():
    print("======================================================================")
    print(" BENCHMARK DE CONSULTAS PATRÓN Q1 - Q5 (200 ITERACIONES)")
    print("======================================================================")

    conn = get_connection()

    # ------------------------------------------------------------------
    # DEFINICIÓN DE CONSULTAS SQL PATRÓN
    # ------------------------------------------------------------------

    # Q1: Proveedor y contrato vigente (Punto, SLA < 10 ms)
    # Sin JOIN entre esquemas: consulta sobre esquema proveedores
    q1_sql = """
    SELECT p.id, p.nit, p.nombre, c.id AS contrato_id, c.fecha_inicio, c.fecha_fin, c.estado
    FROM proveedores.proveedor p
    JOIN proveedores.contrato_suministro c ON c.proveedor_id = p.id
    WHERE p.id = %s AND %s BETWEEN c.fecha_inicio AND c.fecha_fin;
    """

    # Q2: 20 SKUs negociados de un proveedor (Lote pequeño)
    # Sin JOIN entre esquemas: consulta dentro del esquema catalogo
    q2_sql = """
    SELECT ps.sku_id, s.codigo, s.nombre, ps.precio_negociado
    FROM catalogo.proveedor_sku ps
    JOIN catalogo.sku s ON s.id = ps.sku_id
    WHERE ps.proveedor_id = %s AND ps.estado = 'ACTIVO'
    ORDER BY ps.sku_id
    LIMIT 20;
    """

    # Q3: Franjas disponibles de un CEDI para una fecha (Recurso escaso)
    # Sin JOIN entre esquemas: consulta dentro del esquema logistica
    q3_sql = """
    SELECT id, fecha, hora_inicio, hora_fin, capacidad, reservados
    FROM logistica.franja_descargue
    WHERE cedi_id = %s AND fecha = %s AND estado = 'DISPONIBLE' AND reservados < capacidad
    ORDER BY hora_inicio;
    """

    # Q4: OTIF y Fill Rate por proveedor y mes sobre 24 meses (Analítica pesada)
    # Validación semántica rigurosa: On-Time = entregada en o antes de la fecha acordada
    # In-Full = cantidades recibidas vs solicitadas en lineas
    # Sin JOIN entre esquemas: consulta dentro del esquema ordenes
    q4_sql = """
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

    # Q5: Últimas 50 órdenes de un proveedor caliente, paginadas
    # Sin JOIN entre esquemas: consulta dentro del esquema ordenes
    q5_sql = """
    SELECT id, numero_orden, proveedor_id, fecha_orden, estado, total
    FROM ordenes.orden_compra
    WHERE proveedor_id = %s
    ORDER BY fecha_orden DESC
    LIMIT 50;
    """

    # Generar primero los planes EXPLAIN antes/después
    evaluar_experimento_indices(conn, q4_sql, q5_sql)

    # Medición de 200 iteraciones con registro de observaciones individuales
    obs_file = QUERIES_DIR / "observaciones_latencias.csv"
    obs_f = open(obs_file, "w", newline="", encoding="utf-8")
    obs_writer = csv.writer(obs_f)
    obs_writer.writerow(["consulta", "escenario", "iteracion", "latencia_ms"])

    queries = {
        "Q1": (q1_sql, (COLD_PROVEEDOR_ID, "2025-06-15 12:00:00"), (HOT_PROVEEDOR_ID, "2025-06-15 12:00:00")),
        "Q2": (q2_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,)),
        "Q3": (q3_sql, (CEDI_ID, COLD_FECHA_CEDI), (CEDI_ID, HOT_FECHA_CEDI)),
        "Q4": (q4_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,)),
        "Q5": (q5_sql, (COLD_PROVEEDOR_ID,), (HOT_PROVEEDOR_ID,))
    }

    results = {}
    print("\n[Iniciando mediciones de 200 iteraciones por consulta...]")

    for q_name, (sql, p_cold, p_hot) in queries.items():
        print(f"\n  Midiendo {q_name} (Frío y Caliente)...")
        res_cold = ejecutar_benchmark_consulta(conn, sql, p_cold, q_name, "frio", obs_writer)
        res_hot = ejecutar_benchmark_consulta(conn, sql, p_hot, q_name, "caliente", obs_writer)

        results[q_name] = {
            "frio": res_cold,
            "caliente": res_hot
        }
        print(f"    - {q_name} Frío     : p50={res_cold['p50_ms']:<7.3f} ms, p95={res_cold['p95_ms']:<7.3f} ms, p99={res_cold['p99_ms']:<7.3f} ms")
        print(f"    - {q_name} Caliente : p50={res_hot['p50_ms']:<7.3f} ms, p95={res_hot['p95_ms']:<7.3f} ms, p99={res_hot['p99_ms']:<7.3f} ms")

    obs_f.close()
    conn.close()

    # Guardar resultados
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Exportar CSV resumen
    csv_resumen = QUERIES_DIR / "resumen_latencias_q1_q5.csv"
    with open(csv_resumen, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["consulta", "escenario", "p50_ms", "p95_ms", "p99_ms", "promedio_ms", "min_ms", "max_ms"])
        for q_name, d in results.items():
            for esc in ("frio", "caliente"):
                m = d[esc]
                writer.writerow([q_name, esc, m["p50_ms"], m["p95_ms"], m["p99_ms"], m["avg_ms"], m["min_ms"], m["max_ms"]])

    print("\n======================================================================")
    print(" TABLA RESUMEN DE LATENCIAS Q1 - Q5 (p50, p95, p99 en ms)")
    print("======================================================================")
    print(f"{'ID':<4} | {'Escenario':<10} | {'p50 (ms)':<10} | {'p95 (ms)':<10} | {'p99 (ms)':<10} | {'Prom (ms)':<10}")
    print("-" * 65)
    for q_name, d in results.items():
        for esc in ("frio", "caliente"):
            m = d[esc]
            print(f"{q_name:<4} | {esc.capitalize():<10} | {m['p50_ms']:<10.3f} | {m['p95_ms']:<10.3f} | {m['p99_ms']:<10.3f} | {m['avg_ms']:<10.3f}")
    print("======================================================================")
    print(f"Resultados guardados en {RESULTS_FILE}, {csv_resumen} y {obs_file}")

if __name__ == "__main__":
    main()
