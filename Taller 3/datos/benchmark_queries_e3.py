#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entregable 3 - Benchmark instrumentado Q1-Q5 (OpenTelemetry + Prometheus)
=========================================================================

Mismo protocolo que el E2 (2 warmups + 200 iteraciones, ``perf_counter``,
percentil por interpolación lineal) pero:

* Cada consulta genera un span padre ``benchmark Qn/escenario`` con un span
  hijo ``SQL Qn`` por iteración -> visible en Jaeger.
* Latencias, errores y p50/p95/p99 exactos se exportan a Prometheus (:9464).
* **No** elimina/crea índices (a diferencia del E2) -> no muta el dataset.
* Tolera errores (necesario bajo fallas): se registran y la corrida continúa.
* Compara automáticamente contra ``output/benchmark_queries_resultados.json`` (E2).

Uso::

    python3 datos/benchmark_queries_e3.py --fase baseline
    python3 datos/benchmark_queries_e3.py --fase falla_red --ruta toxiproxy --iteraciones 50
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

import psycopg2

import telemetria as tel
from consultas import CONSULTAS, ConsultaPatron, get_connection

log = logging.getLogger("e3.benchmark")

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
E3_DIR = OUTPUT_DIR / "e3"
E2_RESULTS = OUTPUT_DIR / "benchmark_queries_resultados.json"
ITERACIONES = 200
WARMUP = 2

# Ejecutor: (cursor, params, escenario, fase) -> latencia_ms. Permite que el
# orquestador sustituya Q1 por caché L1 o Q4 por la vista materializada.
Ejecutor = Callable[[object, tuple, str, str], float]


def percentile(data: List[float], p: float) -> float:
    """Idéntico al E2 (interpolación lineal) para comparabilidad estricta."""
    if not data:
        return float("nan")
    s = sorted(data)
    k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def estadisticas(lat: List[float], errores: int, duracion_s: float) -> Dict[str, float]:
    total = len(lat) + errores
    return {
        "p50_ms": round(percentile(lat, 50), 4),
        "p95_ms": round(percentile(lat, 95), 4),
        "p99_ms": round(percentile(lat, 99), 4),
        "avg_ms": round(sum(lat) / len(lat), 4) if lat else float("nan"),
        "min_ms": round(min(lat), 4) if lat else float("nan"),
        "max_ms": round(max(lat), 4) if lat else float("nan"),
        "ok": len(lat),
        "errores": errores,
        "tasa_error": round(errores / total, 4) if total else 0.0,
        "throughput_qps": round(total / duracion_s, 2) if duracion_s > 0 else 0.0,
    }


def ejecutor_sql(q: ConsultaPatron) -> Ejecutor:
    def _run(cur, params, escenario, fase) -> float:
        lat, _ = tel.ejecutar_sql(cur, q.sql, params, q.nombre, escenario, fase)
        return lat
    return _run


def medir_consulta(conn, nombre: str, ejecutor: Ejecutor, params: tuple, escenario: str, fase: str,
                   iteraciones: int, obs_writer=None, presupuesto_s: Optional[float] = None) -> Dict[str, float]:
    """Mide una consulta/escenario. ``presupuesto_s`` corta la corrida si una falla
    la vuelve demasiado lenta (p.ej. 200 × 2 s = 400 s)."""
    lat: List[float] = []
    errores = 0
    with tel.span(f"benchmark {nombre}/{escenario}", **{"e3.consulta": nombre, "e3.escenario": escenario,
                                                        "e3.fase": fase, "e3.iteraciones": iteraciones}) as sp:
        with conn.cursor() as cur:
            for _ in range(WARMUP):
                try:
                    ejecutor(cur, params, escenario, f"{fase}_warmup")
                except Exception:  # noqa: BLE001
                    conn.rollback()
            t_ini = time.perf_counter()
            for it in range(1, iteraciones + 1):
                try:
                    ms = ejecutor(cur, params, escenario, fase)
                    lat.append(ms)
                    if obs_writer:
                        obs_writer.writerow([fase, nombre, escenario, it, round(ms, 4), ""])
                except (psycopg2.Error, Exception) as e:  # noqa: BLE001 - bajo caos se esperan errores
                    errores += 1
                    if obs_writer:
                        obs_writer.writerow([fase, nombre, escenario, it, "", type(e).__name__])
                    if conn.closed:
                        raise
                    conn.rollback()
                if presupuesto_s and time.perf_counter() - t_ini > presupuesto_s:
                    log.warning("%s/%s: presupuesto de %.0fs agotado tras %d iteraciones",
                                nombre, escenario, presupuesto_s, it)
                    break
            dur = time.perf_counter() - t_ini
        st = estadisticas(lat, errores, dur)
        for k in ("p50_ms", "p95_ms", "p99_ms", "errores"):
            sp.set_attribute(f"e3.{k}", st[k])
    tel.publicar_percentiles(nombre, escenario, fase, st)
    return st


def medir_consultas(conn, fase: str, iteraciones: int = ITERACIONES,
                    ejecutores: Optional[Dict[str, Ejecutor]] = None,
                    seleccion: Optional[List[str]] = None, escenarios=("frio", "caliente"),
                    obs_writer=None, presupuesto_s: Optional[float] = None) -> Dict[str, Dict[str, Dict]]:
    """API reutilizable por ``experimentos_e3.py``."""
    ejecutores = ejecutores or {}
    res: Dict[str, Dict[str, Dict]] = {}
    with tel.span(f"fase {fase}", **{"e3.fase": fase}):
        for nombre, q in CONSULTAS.items():
            if seleccion and nombre not in seleccion:
                continue
            ej = ejecutores.get(nombre, ejecutor_sql(q))
            res[nombre] = {}
            for esc in escenarios:
                params = q.params_frio if esc == "frio" else q.params_caliente
                st = medir_consulta(conn, nombre, ej, params, esc, fase, iteraciones, obs_writer, presupuesto_s)
                res[nombre][esc] = st
                log.info("  %s %-8s p50=%9.3f p95=%9.3f p99=%9.3f ms  err=%d",
                         nombre, esc, st["p50_ms"], st["p95_ms"], st["p99_ms"], st["errores"])
    return res


def cargar_e2() -> Dict:
    if not E2_RESULTS.exists():
        log.warning("No existe %s: no se puede comparar contra E2", E2_RESULTS)
        return {}
    return json.loads(E2_RESULTS.read_text(encoding="utf-8"))


def comparar_con_e2(res: Dict, e2: Dict, tolerancia: float = 0.25) -> List[Dict]:
    """Fila por consulta/escenario con delta % de p50 vs E2. ``cuadra`` = |delta| <= tolerancia
    (por defecto ±25 %: la varianza de caché/SO entre corridas es normal en sub-ms)."""
    filas = []
    for q, escs in res.items():
        for esc, st in escs.items():
            ref = e2.get(q, {}).get(esc, {})
            p50_e2 = ref.get("p50_ms")
            delta = (st["p50_ms"] - p50_e2) / p50_e2 if p50_e2 else None
            filas.append({
                "consulta": q, "escenario": esc,
                "e2_p50_ms": p50_e2, "e2_p95_ms": ref.get("p95_ms"), "e2_p99_ms": ref.get("p99_ms"),
                "e3_p50_ms": st["p50_ms"], "e3_p95_ms": st["p95_ms"], "e3_p99_ms": st["p99_ms"],
                "delta_p50_pct": round(delta * 100, 2) if delta is not None else None,
                "cuadra_e2": (abs(delta) <= tolerancia) if delta is not None else None,
                "errores": st["errores"],
            })
    return filas


def guardar(fase: str, res: Dict, comparacion: List[Dict]) -> Path:
    E3_DIR.mkdir(parents=True, exist_ok=True)
    (E3_DIR / f"benchmark_{fase}.json").write_text(json.dumps(
        {"fase": fase, "timestamp": datetime.now().isoformat(), "resultados": res}, indent=2,
        ensure_ascii=False), encoding="utf-8")
    out = E3_DIR / f"comparacion_e2_{fase}.csv"
    if comparacion:
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(comparacion[0].keys()))
            w.writeheader()
            w.writerows(comparacion)
    return out


def imprimir_tabla(comparacion: List[Dict]) -> None:
    print(f"\n{'Q':<3} {'Esc':<9}{'E2 p50':>10}{'E3 p50':>10}{'E3 p95':>10}{'E3 p99':>10}{'Δp50%':>9}  Cuadra")
    print("-" * 72)
    for r in comparacion:
        e2 = f"{r['e2_p50_ms']:.3f}" if r["e2_p50_ms"] is not None else "-"
        d = f"{r['delta_p50_pct']:+.1f}" if r["delta_p50_pct"] is not None else "-"
        ok = {True: "SÍ", False: "NO", None: "-"}[r["cuadra_e2"]]
        print(f"{r['consulta']:<3} {r['escenario']:<9}{e2:>10}{r['e3_p50_ms']:>10.3f}"
              f"{r['e3_p95_ms']:>10.3f}{r['e3_p99_ms']:>10.3f}{d:>9}  {ok}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Benchmark Q1-Q5 instrumentado (E3)")
    ap.add_argument("--fase", default="baseline")
    ap.add_argument("--ruta", choices=["directa", "toxiproxy"], default="directa")
    ap.add_argument("--iteraciones", type=int, default=ITERACIONES)
    ap.add_argument("--consultas", nargs="*", help="Subconjunto, ej: Q1 Q4")
    ap.add_argument("--presupuesto-s", type=float, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    tel.init_telemetria(service_name="portal-b2b-benchmark")
    print("=" * 72)
    print(f" BENCHMARK E3 Q1-Q5 | fase={args.fase} ruta={args.ruta} it={args.iteraciones}")
    print("=" * 72)

    conn = get_connection(args.ruta)
    E3_DIR.mkdir(parents=True, exist_ok=True)
    obs_path = E3_DIR / f"observaciones_{args.fase}.csv"
    try:
        with obs_path.open("w", newline="", encoding="utf-8") as fobs:
            w = csv.writer(fobs)
            w.writerow(["fase", "consulta", "escenario", "iteracion", "latencia_ms", "error"])
            res = medir_consultas(conn, args.fase, args.iteraciones, seleccion=args.consultas,
                                  obs_writer=w, presupuesto_s=args.presupuesto_s)
    finally:
        conn.close()
        tel.shutdown_telemetria()

    comp = comparar_con_e2(res, cargar_e2())
    out = guardar(args.fase, res, comp)
    imprimir_tabla(comp)
    print(f"\nResultados: {out} | observaciones: {obs_path}")
    print("Trazas: http://localhost:16686  (service=portal-b2b-benchmark)")


if __name__ == "__main__":
    main()
