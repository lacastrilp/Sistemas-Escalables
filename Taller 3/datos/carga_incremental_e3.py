#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entregable 3 - Carga incremental instrumentada (transacción de negocio "Crear Orden")
====================================================================================

Misma ruta transaccional del E2 (RF01 contrato -> RF02 catálogo -> RF03 franja ->
RF05 orden+líneas -> RF06 outbox), ahora:

* **Trazas**: un span raíz ``tx crear_orden`` por orden con hijos por paso de negocio
  (``proveedores.validar_contrato``, ``catalogo.validar_skus``, ``logistica.reservar_franja``,
  ``ordenes.insertar``, ``ordenes.outbox``) y spans ``SQL`` anidados.
* **Métricas**: ``e3_business_tx_seconds{resultado}`` y ``e3_business_tx_total``.
* **Motor de fallas** integrado (recarga en caliente):
    - F2: la llamada ``ordenes -> catalogo`` pasa por ``MotorFallas.llamar_catalogo`` (+ CB).
    - F3: las conexiones se obtienen de un pool acotado con timeout de adquisición.
    - F4: ``SET LOCAL lock_timeout`` + reintentos con backoff exponencial y jitter
      ante 40P01 / 40001 / 55P03 y errores transitorios inyectados.
* Concurrencia real con ``--workers`` hilos (necesaria para F3/F4).
* **Preserva el dataset**: por defecto cada orden hace ``ROLLBACK`` (``--commit`` para persistir).
  Así los 5.66 M de filas y el seed del E2 permanecen intactos entre experimentos.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2 import errors as pgerr

import telemetria as tel
from consultas import HOT_PROVEEDOR_ID, crear_pool, get_connection
from motor_fallas import (CatalogoTimeoutError, CircuitoAbiertoError, ErrorTransitorioDB, MotorFallas,
                          PoolAgotadoError)

log = logging.getLogger("e3.carga")
E3_DIR = Path(__file__).resolve().parent / "output" / "e3"

SEED = 20261012          # mismo seed del E2
PROB_HOT = 0.20          # 20 % de órdenes para el superproveedor (Zipf)
MAX_REINTENTOS = 3
BACKOFF_BASE_S = 0.05

TRANSITORIOS = (pgerr.DeadlockDetected, pgerr.SerializationFailure, pgerr.LockNotAvailable,
                ErrorTransitorioDB)


class Rechazo(Exception):
    """Rechazo por regla de negocio (no es error del sistema)."""

    def __init__(self, motivo: str):
        super().__init__(motivo)
        self.motivo = motivo


@dataclass
class Contadores:
    aceptadas: int = 0
    rechazos: Dict[str, int] = field(default_factory=dict)
    errores: Dict[str, int] = field(default_factory=dict)
    reintentos: int = 0
    latencias_ms: List[float] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def sumar(self, campo: str, clave: Optional[str] = None, lat_ms: Optional[float] = None) -> None:
        with self._lock:
            if clave is None:
                setattr(self, campo, getattr(self, campo) + 1)
            else:
                d = getattr(self, campo)
                d[clave] = d.get(clave, 0) + 1
            if lat_ms is not None:
                self.latencias_ms.append(lat_ms)


@dataclass(frozen=True)
class Contexto:
    proveedores: List[int]
    catalogo: Dict[int, List[int]]
    franjas: List[Tuple[int, int, int, int]]
    base_orden: int
    base_linea: int
    base_evento: int


def preparar_contexto(conn) -> Contexto:
    with tel.span("setup.contexto"), conn.cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id),0) FROM ordenes.orden_compra")
        bo = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(MAX(id),0) FROM ordenes.linea_orden")
        bl = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(MAX(id),0) FROM ordenes.evento_auditoria")
        be = cur.fetchone()[0]
        cur.execute("""SELECT DISTINCT proveedor_id FROM proveedores.contrato_suministro
                       WHERE estado='ACTIVO' ORDER BY proveedor_id LIMIT 1000""")
        provs = [r[0] for r in cur.fetchall()]
        cur.execute("""SELECT id, cedi_id, capacidad, reservados FROM logistica.franja_descargue
                       WHERE estado='DISPONIBLE' AND reservados < capacidad ORDER BY id LIMIT 2000""")
        franjas = cur.fetchall()
        muestra = tuple(sorted(set(provs[:100]) | {HOT_PROVEEDOR_ID}))
        cur.execute("""SELECT proveedor_id, sku_id FROM catalogo.proveedor_sku
                       WHERE proveedor_id IN %s AND estado='ACTIVO' ORDER BY proveedor_id, sku_id""", (muestra,))
        cat: Dict[int, List[int]] = {}
        for pid, sid in cur.fetchall():
            cat.setdefault(pid, []).append(sid)
    conn.rollback()
    return Contexto(sorted(cat), cat, franjas, bo, bl, be)


class CreadorOrdenes:
    """Ejecuta la transacción de negocio "Crear Orden" con resiliencia y trazas."""

    def __init__(self, motor: MotorFallas, ctx: Contexto, commit: bool, fase: str):
        self.motor, self.ctx, self.commit, self.fase = motor, ctx, commit, fase
        self.cnt = Contadores()
        self._ids = threading.Lock()
        self._sig_orden, self._sig_linea, self._sig_evento = ctx.base_orden + 1, ctx.base_linea + 1, ctx.base_evento + 1

    def _reservar_ids(self, n_lineas: int) -> Tuple[int, int, int]:
        with self._ids:
            o, l, e = self._sig_orden, self._sig_linea, self._sig_evento
            self._sig_orden += 1
            self._sig_linea += n_lineas
            self._sig_evento += 1
            return o, l, e

    # --------------- pasos de negocio ---------------
    def _validar_contrato(self, cur, prov: int, fecha: datetime) -> None:
        with tel.span("proveedores.validar_contrato", **{"proveedor.id": prov}):
            _, filas = tel.ejecutar_sql(cur, """
                SELECT id FROM proveedores.contrato_suministro
                WHERE proveedor_id=%s AND estado='ACTIVO' AND %s BETWEEN fecha_inicio AND fecha_fin LIMIT 1""",
                (prov, fecha), "RF01_contrato", fase=self.fase)
            if not filas:
                raise Rechazo("sin_contrato")

    def _validar_skus(self, cur, prov: int, skus: List[int]) -> None:
        """Llamada inter-módulo ordenes -> catalogo (punto de inyección F2)."""
        def _consulta() -> None:
            _, filas = tel.ejecutar_sql(cur, """
                SELECT COUNT(DISTINCT sku_id) FROM catalogo.proveedor_sku
                WHERE proveedor_id=%s AND estado='ACTIVO' AND sku_id = ANY(%s)""",
                (prov, list(set(skus))), "RF02_catalogo", fase=self.fase)
            if filas[0][0] != len(set(skus)):
                raise Rechazo("sku_fuera_catalogo")

        with tel.span("catalogo.validar_skus", **{"proveedor.id": prov, "skus": len(skus),
                                                  "cb.estado": self.motor.cb_catalogo.estado.value}):
            self.motor.llamar_catalogo(_consulta)

    def _reservar_franja(self, cur, franja: int) -> None:
        with tel.span("logistica.reservar_franja", **{"franja.id": franja}):
            _, filas = tel.ejecutar_sql(cur, """
                UPDATE logistica.franja_descargue
                SET reservados = reservados + 1,
                    estado = CASE WHEN reservados + 1 >= capacidad THEN 'LLENA' ELSE 'DISPONIBLE' END
                WHERE id=%s AND reservados < capacidad RETURNING id""", (franja,), "RF03_franja", fase=self.fase)
            if not filas:
                raise Rechazo("franja_agotada")

    def _insertar(self, cur, ids, prov, cedi, franja, fecha, lineas) -> None:
        oid, lid, eid = ids
        with tel.span("ordenes.insertar", **{"orden.id": oid, "lineas": len(lineas)}):
            self.motor.maybe_error_transitorio()  # F4: error transitorio inyectado
            tel.ejecutar_sql(cur, """
                INSERT INTO ordenes.orden_compra (id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id,
                    franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key)
                VALUES (%s,%s,%s,%s,'CONFIRMADA',%s,%s,0,%s,NULL,%s,%s)""",
                (oid, f"ORD-E3-{oid:09d}", prov, fecha, cedi, franja, (fecha + timedelta(days=4)).date(),
                 fecha + timedelta(minutes=5), f"IDEMP-E3-{oid:09d}"), "RF05_orden", fase=self.fase, fetch=False)
            cur.executemany("""
                INSERT INTO ordenes.linea_orden (id, orden_id, numero_linea, sku_id, cantidad,
                    precio_unitario, cantidad_recibida, fecha_recepcion) VALUES (%s,%s,%s,%s,%s,%s,0,NULL)""",
                [(lid + i, oid, i + 1, sku, cant, pu) for i, (sku, cant, pu) in enumerate(lineas)])
        with tel.span("ordenes.outbox", **{"evento": "ORDEN_CONFIRMADA"}):
            payload = json.dumps({"evento": "OrdenConfirmada", "orden_id": oid, "proveedor_id": prov,
                                  "franja_id": franja, "cedi_id": cedi, "timestamp": fecha.isoformat()})
            tel.ejecutar_sql(cur, """INSERT INTO ordenes.evento_auditoria (id, orden_id, tipo_evento, fecha_evento,
                payload) VALUES (%s,%s,'ORDEN_CONFIRMADA',%s,%s)""", (eid, oid, fecha, payload),
                "RF06_outbox", fase=self.fase, fetch=False)

    # --------------- transacción completa ---------------
    def crear(self, i: int) -> str:
        rng = random.Random(SEED + i)  # determinista por orden, independiente del scheduling de hilos
        r = rng.random()
        prov = HOT_PROVEEDOR_ID if r < PROB_HOT else (rng.choice(self.ctx.proveedores) if r < 0.95 else 99_999)
        franja, cedi, _, _ = rng.choice(self.ctx.franjas)
        fecha = datetime(2025, 12, 31, 10) + timedelta(minutes=rng.randint(1, 300))
        skus = self.ctx.catalogo.get(prov) or [0]
        lineas = [(rng.choice(skus), rng.randint(5, 50), round(rng.uniform(2000, 50000), 2))
                  for _ in range(rng.randint(2, 6))]

        t0 = time.perf_counter()
        resultado = "error"
        with tel.span("tx crear_orden", **{"orden.intento": i, "proveedor.id": prov,
                                          "proveedor.caliente": prov == HOT_PROVEEDOR_ID, "e3.fase": self.fase}) as sp:
            for intento in range(1, MAX_REINTENTOS + 1):
                conn = None
                try:
                    conn = self.motor.obtener_conexion()
                    with conn.cursor() as cur:
                        lt = self.motor.lock_timeout_ms()
                        if lt:
                            cur.execute("SET LOCAL lock_timeout = %s", (f"{lt}ms",))
                        self._validar_contrato(cur, prov, fecha)
                        self._validar_skus(cur, prov, [s for s, _, _ in lineas])
                        self._reservar_franja(cur, franja)
                        self._insertar(cur, self._reservar_ids(len(lineas)), prov, cedi, franja, fecha, lineas)
                    conn.commit() if self.commit else conn.rollback()
                    resultado = "aceptada"
                    self.cnt.sumar("aceptadas")
                    break
                except Rechazo as e:
                    conn.rollback()
                    resultado = f"rechazo_{e.motivo}"
                    self.cnt.sumar("rechazos", e.motivo)
                    break
                except TRANSITORIOS as e:
                    if conn:
                        conn.rollback()
                    self.cnt.sumar("reintentos")
                    sp.add_event("reintento", {"intento": intento, "error": type(e).__name__})
                    if intento == MAX_REINTENTOS:
                        resultado = "error_transitorio"
                        self.cnt.sumar("errores", type(e).__name__)
                    else:
                        time.sleep(BACKOFF_BASE_S * 2 ** (intento - 1) * (1 + rng.random()))
                except (CatalogoTimeoutError, CircuitoAbiertoError, PoolAgotadoError) as e:
                    if conn:
                        conn.rollback()
                    resultado = {"CatalogoTimeoutError": "error_catalogo_timeout",
                                 "CircuitoAbiertoError": "degradada_cb_abierto",
                                 "PoolAgotadoError": "error_pool_agotado"}[type(e).__name__]
                    self.cnt.sumar("errores", type(e).__name__)
                    break
                except psycopg2.Error as e:
                    if conn and not conn.closed:
                        conn.rollback()
                    resultado = "error_db"
                    self.cnt.sumar("errores", e.pgcode or type(e).__name__)
                    break
                finally:
                    if conn is not None:
                        self.motor.pool.putconn(conn, close=bool(conn.closed))
            sp.set_attribute("tx.resultado", resultado)
        seg = time.perf_counter() - t0
        tel.observar_tx("crear_orden", resultado, seg)
        self.cnt.latencias_ms.append(seg * 1000)
        return resultado


def ejecutar_carga(n: int, workers: int, pool_max: int, commit: bool, fase: str, ruta: str,
                   motor: Optional[MotorFallas] = None) -> Dict:
    """API reutilizable por el orquestador. Si ``motor`` es None crea uno propio."""
    from benchmark_queries_e3 import percentile

    pool = crear_pool(pool_max, ruta)
    propio = motor is None
    if propio:
        motor = MotorFallas(conn_factory=lambda: get_connection(ruta), pool=pool,
                            on_evento=tel.on_evento_fallas).start()
    else:
        motor.pool = pool
    try:
        c0 = pool.getconn()
        ctx = preparar_contexto(c0)
        pool.putconn(c0)
        creador = CreadorOrdenes(motor, ctx, commit, fase)
        t0 = time.perf_counter()
        with tel.span(f"carga_incremental {fase}", **{"ordenes": n, "workers": workers, "pool_max": pool_max}):
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="e3-tx") as ex:
                list(ex.map(creador.crear, range(1, n + 1)))
        dur = time.perf_counter() - t0
    finally:
        if propio:
            motor.stop()
        pool.closeall()

    c = creador.cnt
    lat = c.latencias_ms
    resumen = {
        "fase": fase, "timestamp": datetime.now().isoformat(), "intentos": n, "workers": workers,
        "pool_max": pool_max, "commit": commit, "ruta": ruta,
        "aceptadas": c.aceptadas, "rechazos": c.rechazos, "errores": c.errores, "reintentos": c.reintentos,
        "tasa_error": round(sum(c.errores.values()) / n, 4),
        "tx_p50_ms": round(percentile(lat, 50), 3), "tx_p95_ms": round(percentile(lat, 95), 3),
        "tx_p99_ms": round(percentile(lat, 99), 3),
        "duracion_s": round(dur, 2), "throughput_tps": round(n / dur, 1) if dur else 0.0,
    }
    E3_DIR.mkdir(parents=True, exist_ok=True)
    (E3_DIR / f"carga_incremental_{fase}.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
    return resumen


def main() -> None:
    ap = argparse.ArgumentParser(description="Carga incremental instrumentada (E3)")
    ap.add_argument("--ordenes", type=int, default=5000)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--pool-max", type=int, default=10)
    ap.add_argument("--fase", default="baseline")
    ap.add_argument("--ruta", choices=["directa", "toxiproxy"], default="directa")
    ap.add_argument("--commit", action="store_true", help="Persistir órdenes (por defecto ROLLBACK)")
    a = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    tel.init_telemetria(service_name="portal-b2b-ordenes")
    try:
        r = ejecutar_carga(a.ordenes, a.workers, a.pool_max, a.commit, a.fase, a.ruta)
    finally:
        tel.shutdown_telemetria()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    print("Trazas: http://localhost:16686  (service=portal-b2b-ordenes)")


if __name__ == "__main__":
    main()
