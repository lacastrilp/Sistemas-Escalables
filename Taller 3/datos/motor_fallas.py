#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entregable 3 - Motor de Fallas Configurables (sin redespliegue)
================================================================

Lee ``datos/config_fallas.json`` y lo recarga en caliente cada 2 s (por mtime).
Un *kill switch* maestro (``"fallas_activas": false``) anula todas las familias
de forma inmediata y revierte los efectos externos (toxics, zombies, locks).

Familias implementadas
----------------------
1. Red/Infraestructura   -> ``ToxiproxyClient`` (latency / bandwidth vía API REST).
2. Lógica/Dependencias   -> ``MotorFallas.llamar_catalogo`` + ``CircuitBreaker``.
3. Concurrencia/Recursos -> ``ZombieConnections`` agota un ``ThreadedConnectionPool``.
4. Estado/Datos          -> ``LockBlockers`` (``SELECT ... FOR UPDATE`` + ``pg_sleep``)
                            sobre ``proveedores.proveedor`` (FK de ``orden_compra``)
                            y errores transitorios probabilísticos (SQLSTATE 40P01).

Ninguna falla modifica datos: los bloqueadores hacen ROLLBACK, por lo que los
5.66M de filas y el seed del E2 se preservan.

Uso mínimo::

    motor = MotorFallas(conn_factory=get_connection)
    motor.start()                       # hilo de recarga en caliente
    ...
    motor.llamar_catalogo(lambda: validar_skus(conn, orden))
    motor.maybe_error_transitorio()
    ...
    motor.stop()                        # revierte todo
"""

from __future__ import annotations

import copy
import json
import logging
import os
import random
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

log = logging.getLogger("e3.fallas")

T = TypeVar("T")

CONFIG_PATH = Path(os.getenv("E3_CONFIG_FALLAS", Path(__file__).resolve().parent / "config_fallas.json"))
TOXIPROXY_API = os.getenv("TOXIPROXY_API", "http://127.0.0.1:8474")
TOXIPROXY_PROXY = os.getenv("TOXIPROXY_PROXY", "postgres")
RELOAD_INTERVAL_S = 2.0

DEFAULT_CONFIG: Dict[str, Any] = {
    "fallas_activas": False,
    "red": {"enabled": False, "tipo": "latency", "latencia_ms": 150, "jitter_ms": 10,
            "bandwidth_kbps": 64, "direccion": "downstream"},
    "dependencia_catalogo": {"enabled": False, "probabilidad_fallo": 1.0, "timeout_simulado_ms": 2000,
                             "circuit_breaker": {"enabled": False, "umbral_fallos": 5,
                                                 "ventana_reset_s": 10, "llamadas_half_open": 1}},
    "pool_conexiones": {"enabled": False, "pool_max": 5, "zombies": 4, "zombie_sleep_s": 30,
                        "timeout_adquisicion_s": 1.0},
    "estado_datos": {"enabled": False, "probabilidad_error_transitorio": 0.2,
                     "bloqueadores_concurrentes": 3, "lock_sleep_s": 5, "lock_timeout_app_ms": 500},
}


# ============================================================================
# Excepciones de dominio
# ============================================================================
class FallaInyectada(Exception):
    """Base de toda excepción producida deliberadamente por el laboratorio."""


class CatalogoTimeoutError(FallaInyectada, TimeoutError):
    """El módulo ``catalogo`` no respondió dentro del timeout (Familia 2)."""


class CircuitoAbiertoError(FallaInyectada):
    """Fail-fast: el circuit breaker está OPEN y no se intenta la llamada."""


class ErrorTransitorioDB(FallaInyectada):
    """Simula ``deadlock_detected`` (SQLSTATE 40P01) - reintentable (Familia 4)."""

    pgcode = "40P01"


class PoolAgotadoError(FallaInyectada):
    """No se obtuvo conexión del pool dentro del timeout (Familia 3)."""


# ============================================================================
# Utilidades
# ============================================================================
def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def escribir_config(cambios: Dict[str, Any], path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """Aplica un *patch* atómico (write + rename) al JSON. Lo usa el orquestador
    de experimentos para activar/desactivar fallas sin reiniciar procesos."""
    actual = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    nuevo = _deep_merge(actual, cambios)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(nuevo, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return nuevo


def kill_switch(path: Path = CONFIG_PATH) -> None:
    """Apaga todas las fallas de inmediato (efectivo en <= RELOAD_INTERVAL_S)."""
    escribir_config({"fallas_activas": False}, path)


# ============================================================================
# Familia 1 - Red / Infraestructura (Toxiproxy)
# ============================================================================
class ToxiproxyClient:
    """Cliente mínimo (stdlib) de la API REST de Toxiproxy."""

    TOXIC_NAME = "e3_red"

    def __init__(self, api: str = TOXIPROXY_API, proxy: str = TOXIPROXY_PROXY, timeout: float = 2.0):
        self.api = api.rstrip("/")
        self.proxy = proxy
        self.timeout = timeout

    def _req(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.api}{path}", data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def disponible(self) -> bool:
        try:
            self._req("GET", "/version")
            return True
        except (urllib.error.URLError, OSError):
            return False

    def listar_toxics(self) -> List[dict]:
        return self._req("GET", f"/proxies/{self.proxy}/toxics") or []

    def aplicar(self, cfg: Dict[str, Any]) -> None:
        """Idempotente: elimina el toxic previo y crea el configurado."""
        self.quitar()
        tipo = cfg.get("tipo", "latency")
        if tipo == "latency":
            attrs = {"latency": int(cfg["latencia_ms"]), "jitter": int(cfg.get("jitter_ms", 0))}
        elif tipo == "bandwidth":
            attrs = {"rate": int(cfg["bandwidth_kbps"])}
        elif tipo == "timeout":  # corte de red: retiene datos y cierra tras N ms (0 = nunca)
            attrs = {"timeout": int(cfg.get("timeout_ms", 0))}
        else:
            raise ValueError(f"Tipo de toxic no soportado: {tipo}")
        self._req("POST", f"/proxies/{self.proxy}/toxics", {
            "name": self.TOXIC_NAME, "type": tipo,
            "stream": cfg.get("direccion", "downstream"), "toxicity": 1.0, "attributes": attrs,
        })
        log.warning("[F1] Toxic '%s' aplicado: %s", tipo, attrs)

    def quitar(self) -> None:
        try:
            self._req("DELETE", f"/proxies/{self.proxy}/toxics/{self.TOXIC_NAME}")
            log.info("[F1] Toxic de red retirado")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise


# ============================================================================
# Familia 2 - Circuit Breaker (ordenes -> catalogo)
# ============================================================================
class EstadoCircuito(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Circuit breaker thread-safe clásico (Nygard): CLOSED -> OPEN -> HALF_OPEN."""

    def __init__(self, nombre: str, umbral_fallos: int = 5, ventana_reset_s: float = 10.0,
                 llamadas_half_open: int = 1,
                 on_cambio: Optional[Callable[[str, EstadoCircuito], None]] = None):
        self.nombre = nombre
        self.umbral_fallos = umbral_fallos
        self.ventana_reset_s = ventana_reset_s
        self.llamadas_half_open = llamadas_half_open
        self._on_cambio = on_cambio
        self._lock = threading.Lock()
        self._estado = EstadoCircuito.CLOSED
        self._fallos = 0
        self._abierto_en = 0.0
        self._en_prueba = 0

    @property
    def estado(self) -> EstadoCircuito:
        with self._lock:
            self._evaluar_timeout()
            return self._estado

    def reconfigurar(self, umbral_fallos: int, ventana_reset_s: float, llamadas_half_open: int) -> None:
        with self._lock:
            self.umbral_fallos, self.ventana_reset_s = umbral_fallos, ventana_reset_s
            self.llamadas_half_open = llamadas_half_open

    def reset(self) -> None:
        with self._lock:
            self._transicion(EstadoCircuito.CLOSED)
            self._fallos = self._en_prueba = 0

    def _transicion(self, nuevo: EstadoCircuito) -> None:
        if nuevo is not self._estado:
            log.warning("[CB:%s] %s -> %s", self.nombre, self._estado.value, nuevo.value)
            self._estado = nuevo
            if self._on_cambio:
                self._on_cambio(self.nombre, nuevo)

    def _evaluar_timeout(self) -> None:
        if self._estado is EstadoCircuito.OPEN and time.monotonic() - self._abierto_en >= self.ventana_reset_s:
            self._transicion(EstadoCircuito.HALF_OPEN)
            self._en_prueba = 0

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            self._evaluar_timeout()
            if self._estado is EstadoCircuito.OPEN:
                raise CircuitoAbiertoError(f"Circuito '{self.nombre}' abierto (fail-fast)")
            if self._estado is EstadoCircuito.HALF_OPEN:
                if self._en_prueba >= self.llamadas_half_open:
                    raise CircuitoAbiertoError(f"Circuito '{self.nombre}' en HALF_OPEN saturado")
                self._en_prueba += 1
        try:
            resultado = fn()
        except Exception:
            with self._lock:
                self._fallos += 1
                if self._estado is EstadoCircuito.HALF_OPEN or self._fallos >= self.umbral_fallos:
                    self._transicion(EstadoCircuito.OPEN)
                    self._abierto_en = time.monotonic()
            raise
        with self._lock:
            self._fallos = 0
            self._transicion(EstadoCircuito.CLOSED)
        return resultado


# ============================================================================
# Familia 3 - Agotamiento del Connection Pool (queries zombie)
# ============================================================================
class ZombieConnections:
    """Toma N conexiones del pool y las retiene con ``pg_sleep`` en bucle."""

    def __init__(self, pool, n: int, sleep_s: float):
        self.pool, self.n, self.sleep_s = pool, n, sleep_s
        self._stop = threading.Event()
        self._hilos: List[threading.Thread] = []

    def _zombie(self, idx: int) -> None:
        conn = None
        try:
            conn = self.pool.getconn()
            conn.autocommit = True
            with conn.cursor() as cur:
                # statement_timeout acota cada sleep para poder liberar rápido al apagar
                cur.execute("SET statement_timeout = %s", (int(self.sleep_s * 1000) + 500,))
                while not self._stop.is_set():
                    cur.execute("SELECT pg_sleep(LEAST(%s, 1.0)) /* e3_zombie */", (self.sleep_s,))
        except Exception as e:  # noqa: BLE001 - un zombie nunca debe tumbar el proceso
            log.debug("[F3] zombie %d terminó: %s", idx, e)
        finally:
            if conn is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute("RESET statement_timeout")
                except Exception:  # noqa: BLE001
                    pass
                self.pool.putconn(conn)

    def start(self) -> None:
        self._stop.clear()
        for i in range(self.n):
            t = threading.Thread(target=self._zombie, args=(i,), name=f"e3-zombie-{i}", daemon=True)
            t.start()
            self._hilos.append(t)
        log.warning("[F3] %d conexiones zombie retenidas del pool", self.n)

    def stop(self) -> None:
        self._stop.set()
        for t in self._hilos:
            t.join(timeout=3)
        self._hilos.clear()
        log.info("[F3] zombies liberados")


# ============================================================================
# Familia 4 - Contención de locks (interbloqueo temporal)
# ============================================================================
class LockBlockers:
    """N sesiones concurrentes que sostienen ``FOR UPDATE`` sobre el proveedor
    caliente durante ``lock_sleep_s``. Toda inserción en ``ordenes.orden_compra``
    para ese proveedor requiere ``FOR KEY SHARE`` (FK) y queda bloqueada; con
    ``lock_timeout`` en la app se materializa como error transitorio (55P03)."""

    SQL_LOCK = "SELECT id FROM proveedores.proveedor WHERE id = %s FOR UPDATE /* e3_lock */"

    def __init__(self, conn_factory: Callable[[], Any], n: int, sleep_s: float, proveedor_id: int = 1):
        self.conn_factory, self.n, self.sleep_s, self.proveedor_id = conn_factory, n, sleep_s, proveedor_id
        self._stop = threading.Event()
        self._hilos: List[threading.Thread] = []

    def _bloqueador(self, idx: int) -> None:
        try:
            conn = self.conn_factory()
        except Exception as e:  # noqa: BLE001
            log.error("[F4] bloqueador %d sin conexión: %s", idx, e)
            return
        try:
            while not self._stop.is_set():
                with conn.cursor() as cur:
                    cur.execute(self.SQL_LOCK, (self.proveedor_id,))
                    deadline = time.monotonic() + self.sleep_s
                    while not self._stop.is_set() and time.monotonic() < deadline:
                        cur.execute("SELECT pg_sleep(0.25)")
                conn.rollback()  # nunca se persiste nada
        except Exception as e:  # noqa: BLE001
            log.debug("[F4] bloqueador %d terminó: %s", idx, e)
        finally:
            try:
                conn.rollback()
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    def start(self) -> None:
        self._stop.clear()
        for i in range(self.n):
            t = threading.Thread(target=self._bloqueador, args=(i,), name=f"e3-lock-{i}", daemon=True)
            t.start()
            self._hilos.append(t)
        log.warning("[F4] %d bloqueadores FOR UPDATE sobre proveedor %d", self.n, self.proveedor_id)

    def stop(self) -> None:
        self._stop.set()
        for t in self._hilos:
            t.join(timeout=3)
        self._hilos.clear()
        log.info("[F4] bloqueadores liberados")


# ============================================================================
# Controlador principal
# ============================================================================
@dataclass(frozen=True)
class EstadoFallas:
    """Vista inmutable de qué familias están efectivamente activas (kill switch aplicado)."""

    red: bool
    dependencia_catalogo: bool
    pool_conexiones: bool
    estado_datos: bool
    circuit_breaker: bool


class MotorFallas:
    """Controlador central del laboratorio. Thread-safe.

    :param conn_factory: crea conexiones psycopg2 *fuera* del pool (para F4).
    :param pool: ``psycopg2.pool.ThreadedConnectionPool`` de la app (para F3).
    :param on_evento: callback ``(familia, accion, detalle)`` para métricas/trazas.
    """

    def __init__(self, conn_factory: Optional[Callable[[], Any]] = None, pool=None,
                 config_path: Path = CONFIG_PATH, toxiproxy: Optional[ToxiproxyClient] = None,
                 on_evento: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
                 rng_seed: int = 42):
        self.config_path = Path(config_path)
        self.conn_factory = conn_factory
        self.pool = pool
        self.toxiproxy = toxiproxy or ToxiproxyClient()
        self._on_evento = on_evento
        self._rng = random.Random(rng_seed)  # reproducibilidad de fallas probabilísticas
        self._lock = threading.RLock()
        self._cfg: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
        self._mtime = 0.0
        self._stop = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._zombies: Optional[ZombieConnections] = None
        self._blockers: Optional[LockBlockers] = None
        self._red_aplicada = False
        cb = self._cfg["dependencia_catalogo"]["circuit_breaker"]
        self.cb_catalogo = CircuitBreaker("catalogo", cb["umbral_fallos"], cb["ventana_reset_s"],
                                          cb["llamadas_half_open"],
                                          on_cambio=lambda n, e: self._emit("F2", "cb_" + e.value.lower(), {}))
        self.recargar(force=True)

    # ---------------- ciclo de vida ----------------
    def start(self) -> "MotorFallas":
        if self._hilo is None:
            self._stop.clear()
            self._hilo = threading.Thread(target=self._loop, name="e3-config-reloader", daemon=True)
            self._hilo.start()
            log.info("Motor de fallas iniciado (recarga cada %.1fs desde %s)", RELOAD_INTERVAL_S, self.config_path)
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._hilo:
            self._hilo.join(timeout=RELOAD_INTERVAL_S + 1)
            self._hilo = None
        with self._lock:
            self._cfg["fallas_activas"] = False
            self._sincronizar()

    def __enter__(self) -> "MotorFallas":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    def _loop(self) -> None:
        while not self._stop.wait(RELOAD_INTERVAL_S):
            try:
                self.recargar()
            except Exception:  # noqa: BLE001 - el reloader nunca debe morir
                log.exception("Error recargando config de fallas")

    # ---------------- configuración ----------------
    def recargar(self, force: bool = False) -> bool:
        """Relee el JSON si cambió su mtime. Devuelve True si hubo cambio.
        Si el JSON es inválido se conserva la última configuración válida."""
        try:
            mtime = self.config_path.stat().st_mtime
        except FileNotFoundError:
            return False
        if not force and mtime == self._mtime:
            return False
        try:
            nuevo = _deep_merge(DEFAULT_CONFIG, json.loads(self.config_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as e:
            log.error("config_fallas.json inválido (%s); se mantiene la última válida", e)
            return False
        with self._lock:
            self._mtime = mtime
            self._cfg = nuevo
            cb = nuevo["dependencia_catalogo"]["circuit_breaker"]
            self.cb_catalogo.reconfigurar(cb["umbral_fallos"], cb["ventana_reset_s"], cb["llamadas_half_open"])
            self._sincronizar()
        self._emit("motor", "recarga", {"estado": self.estado().__dict__})
        return True

    def config(self) -> Dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._cfg)

    def estado(self) -> EstadoFallas:
        with self._lock:
            on = bool(self._cfg["fallas_activas"])
            c = self._cfg
            return EstadoFallas(
                red=on and c["red"]["enabled"],
                dependencia_catalogo=on and c["dependencia_catalogo"]["enabled"],
                pool_conexiones=on and c["pool_conexiones"]["enabled"],
                estado_datos=on and c["estado_datos"]["enabled"],
                # El CB es una *mitigación*: funciona aunque el kill switch esté apagado.
                circuit_breaker=c["dependencia_catalogo"]["circuit_breaker"]["enabled"],
            )

    # ---------------- reconciliación de efectos externos ----------------
    def _sincronizar(self) -> None:
        """Lleva los efectos externos (Toxiproxy, zombies, locks) al estado deseado."""
        est = self.estado()
        c = self._cfg

        # F1 - Red
        try:
            if est.red:
                self.toxiproxy.aplicar(c["red"])
                self._red_aplicada = True
                self._emit("F1", "activada", c["red"])
            elif self._red_aplicada:
                self.toxiproxy.quitar()
                self._red_aplicada = False
                self._emit("F1", "desactivada", {})
        except (urllib.error.URLError, OSError) as e:
            log.error("[F1] Toxiproxy no disponible (%s): ¿corriste 'make e3-infra'?", e)

        # F3 - Pool
        if est.pool_conexiones and self._zombies is None:
            if self.pool is None:
                log.error("[F3] Se requiere un pool para inyectar zombies")
            else:
                pc = c["pool_conexiones"]
                self._zombies = ZombieConnections(self.pool, int(pc["zombies"]), float(pc["zombie_sleep_s"]))
                self._zombies.start()
                self._emit("F3", "activada", pc)
        elif not est.pool_conexiones and self._zombies is not None:
            self._zombies.stop()
            self._zombies = None
            self._emit("F3", "desactivada", {})

        # F4 - Locks
        if est.estado_datos and self._blockers is None:
            if self.conn_factory is None:
                log.error("[F4] Se requiere conn_factory para bloqueadores")
            else:
                ed = c["estado_datos"]
                self._blockers = LockBlockers(self.conn_factory, int(ed["bloqueadores_concurrentes"]),
                                              float(ed["lock_sleep_s"]))
                self._blockers.start()
                self._emit("F4", "activada", ed)
        elif not est.estado_datos and self._blockers is not None:
            self._blockers.stop()
            self._blockers = None
            self._emit("F4", "desactivada", {})

    # ---------------- puntos de inyección (llamados desde la app) ----------------
    def llamar_catalogo(self, fn: Callable[[], T]) -> T:
        """Envuelve la llamada inter-módulo ``ordenes -> catalogo`` (Familia 2).

        Con la falla activa, simula un timeout (bloquea ``timeout_simulado_ms``
        y lanza ``CatalogoTimeoutError``). Si el circuit breaker está habilitado,
        tras ``umbral_fallos`` errores se hace fail-fast en ~0 ms."""
        est = self.estado()
        dep = self.config()["dependencia_catalogo"]

        def _invocacion() -> T:
            if est.dependencia_catalogo and self._rng.random() < float(dep["probabilidad_fallo"]):
                time.sleep(float(dep["timeout_simulado_ms"]) / 1000.0)
                self._emit("F2", "timeout", {})
                raise CatalogoTimeoutError("catalogo no respondió (timeout simulado)")
            return fn()

        return self.cb_catalogo.call(_invocacion) if est.circuit_breaker else _invocacion()

    def maybe_error_transitorio(self) -> None:
        """Lanza ``ErrorTransitorioDB`` con la probabilidad configurada (Familia 4)."""
        if not self.estado().estado_datos:
            return
        p = float(self.config()["estado_datos"]["probabilidad_error_transitorio"])
        if self._rng.random() < p:
            self._emit("F4", "error_transitorio", {})
            raise ErrorTransitorioDB("deadlock_detected (inyectado)")

    def lock_timeout_ms(self) -> Optional[int]:
        """``lock_timeout`` que la app debe fijar en su sesión mientras F4 está activa."""
        return int(self.config()["estado_datos"]["lock_timeout_app_ms"]) if self.estado().estado_datos else None

    def obtener_conexion(self):
        """``getconn`` con timeout (psycopg2 no lo trae): materializa la Familia 3
        como ``PoolAgotadoError`` en lugar de colgar indefinidamente."""
        if self.pool is None:
            raise RuntimeError("MotorFallas sin pool configurado")
        timeout = float(self.config()["pool_conexiones"]["timeout_adquisicion_s"])
        deadline = time.monotonic() + timeout
        import psycopg2.pool  # import local: el módulo es usable sin psycopg2 para F1/F2

        while True:
            try:
                return self.pool.getconn()
            except psycopg2.pool.PoolError:
                if time.monotonic() >= deadline:
                    self._emit("F3", "pool_agotado", {})
                    raise PoolAgotadoError(f"Sin conexión libre tras {timeout:.1f}s")
                time.sleep(0.01)

    # ---------------- telemetría ----------------
    def _emit(self, familia: str, accion: str, detalle: Dict[str, Any]) -> None:
        if self._on_evento:
            try:
                self._on_evento(familia, accion, detalle)
            except Exception:  # noqa: BLE001
                log.exception("on_evento falló")


# ============================================================================
# CLI de control: python datos/motor_fallas.py {on|off|set <familia> <bool>|status}
# ============================================================================
def _cli() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Control en caliente del laboratorio de fallas E3")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("on", help="Activa el kill switch maestro (fallas_activas=true)")
    sub.add_parser("off", help="KILL SWITCH: apaga todas las fallas")
    sub.add_parser("status", help="Muestra la configuración y los toxics activos")
    s = sub.add_parser("set", help="Habilita/deshabilita una familia")
    s.add_argument("familia", choices=["red", "dependencia_catalogo", "pool_conexiones", "estado_datos"])
    s.add_argument("valor", choices=["true", "false"])
    a = p.parse_args()

    if a.cmd == "on":
        escribir_config({"fallas_activas": True})
    elif a.cmd == "off":
        kill_switch()
    elif a.cmd == "set":
        escribir_config({a.familia: {"enabled": a.valor == "true"}})
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    if a.cmd == "status":
        tp = ToxiproxyClient()
        print("Toxiproxy:", tp.listar_toxics() if tp.disponible() else "no disponible")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _cli()
