#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entregable 3 - Telemetría unificada (OpenTelemetry -> Jaeger, prometheus_client -> Prometheus)
===========================================================================================

Diseño:
* **Trazas**: ``TracerProvider`` + ``BatchSpanProcessor`` + exportador OTLP/gRPC
  (``localhost:4317`` -> Jaeger). El batch exporta en segundo plano, por lo que el
  coste en la ruta caliente es sólo crear/cerrar el span (~5-15 µs).
* **Fidelidad de la línea base**: la latencia se mide con ``perf_counter`` *sólo*
  alrededor de ``execute + fetchall``; la creación del span queda fuera del
  cronómetro. La auto-instrumentación de psycopg2 (que sí añade overhead a
  cada query) es opcional: ``E3_AUTO_INSTRUMENT=1``.
* **Métricas**: histograma con buckets sub-milisegundo (Q1 ≈ 0.1 ms) + gauges de
  p50/p95/p99 calculados exactamente sobre las muestras (Prometheus sólo podría
  aproximarlos por buckets). Expuestas en ``:9464/metrics``.
* **Degradación elegante**: si faltan las librerías OTel o Jaeger no está
  arriba, el código sigue funcionando con un tracer no-op.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

log = logging.getLogger("e3.telemetria")

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "portal-b2b-retail")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
METRICS_PORT = int(os.getenv("E3_METRICS_PORT", "9464"))
TRACING_ON = os.getenv("E3_TRACING", "1") == "1"
AUTO_INSTRUMENT = os.getenv("E3_AUTO_INSTRUMENT", "0") == "1"

# ----------------------------------------------------------------------------
# Métricas Prometheus
# ----------------------------------------------------------------------------
try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    _PROM = True
except ImportError:  # pragma: no cover
    _PROM = False
    log.warning("prometheus_client no instalado: métricas deshabilitadas")

# Buckets en segundos: 20 µs .. 10 s (cubren Q1 caché L1, Q1 BD, Q4 caliente y fallas de 2 s)
_BUCKETS = (0.00002, 0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025,
            0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0)

if _PROM:
    QUERY_LATENCY = Histogram("e3_query_latency_seconds", "Latencia de consultas patrón Q1-Q5",
                              ["consulta", "escenario", "fase"], buckets=_BUCKETS)
    QUERY_QUANTILE_MS = Gauge("e3_query_latency_quantile_ms", "pXX exacto por corrida",
                              ["consulta", "escenario", "fase", "quantile"])
    QUERY_ERRORS = Counter("e3_query_errors_total", "Errores en consultas", ["consulta", "fase", "tipo"])
    TX_LATENCY = Histogram("e3_business_tx_seconds", "Latencia de transacción de negocio",
                           ["transaccion", "resultado"], buckets=_BUCKETS)
    TX_TOTAL = Counter("e3_business_tx_total", "Transacciones de negocio", ["transaccion", "resultado"])
    FAULT_ACTIVE = Gauge("e3_fault_active", "1 si la familia de falla está activa", ["familia"])
    FAULT_EVENTS = Counter("e3_fault_events_total", "Eventos del motor de fallas", ["familia", "accion"])
    CB_STATE = Gauge("e3_circuit_breaker_state", "0=CLOSED 1=HALF_OPEN 2=OPEN", ["circuito"])
    FASE_ACTUAL = Gauge("e3_fase_experimento", "Fase activa (1 = activa)", ["experimento", "fase"])

_metrics_started = False
_tracer = None


# ----------------------------------------------------------------------------
# Inicialización
# ----------------------------------------------------------------------------
def init_telemetria(service_name: str = SERVICE_NAME, metrics_port: Optional[int] = METRICS_PORT) -> None:
    """Idempotente. Arranca el exporter Prometheus y el TracerProvider OTel."""
    global _metrics_started, _tracer
    if _PROM and metrics_port and not _metrics_started:
        try:
            start_http_server(metrics_port)
            _metrics_started = True
            log.info("Métricas Prometheus en :%d/metrics", metrics_port)
        except OSError as e:
            log.warning("No se pudo abrir :%d para métricas (%s)", metrics_port, e)

    if _tracer is not None:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if TRACING_ON:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

            provider = TracerProvider(resource=Resource.create({
                "service.name": service_name, "service.version": "e3", "deployment.environment": "lab",
            }))
            provider.add_span_processor(BatchSpanProcessor(
                OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True),
                max_queue_size=8192, max_export_batch_size=1024, schedule_delay_millis=1000))
            trace.set_tracer_provider(provider)
            log.info("Trazas OTLP -> %s (service=%s)", OTLP_ENDPOINT, service_name)
        if AUTO_INSTRUMENT:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

            Psycopg2Instrumentor().instrument(enable_commenter=True)
            log.info("Auto-instrumentación psycopg2 habilitada (añade overhead por query)")
        _tracer = trace.get_tracer("e3.portal")
    except ImportError as e:
        log.warning("OpenTelemetry no disponible (%s): tracer no-op", e)
        _tracer = _NoopTracer()


def shutdown_telemetria() -> None:
    """Fuerza el flush de spans pendientes antes de salir."""
    try:
        from opentelemetry import trace

        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
    except ImportError:
        pass


def tracer():
    if _tracer is None:
        init_telemetria(metrics_port=None)
    return _tracer


# ----------------------------------------------------------------------------
# Helpers de instrumentación
# ----------------------------------------------------------------------------
@contextmanager
def span(nombre: str, **atributos: Any) -> Iterator[Any]:
    """Span genérico que registra excepciones y status=ERROR automáticamente."""
    with tracer().start_as_current_span(nombre) as s:
        for k, v in atributos.items():
            if v is not None:
                s.set_attribute(k, v)
        try:
            yield s
        except Exception as e:
            _registrar_error(s, e)
            raise


def _registrar_error(s: Any, e: BaseException) -> None:
    if hasattr(s, "record_exception"):
        s.record_exception(e)
        try:
            from opentelemetry.trace import Status, StatusCode

            s.set_status(Status(StatusCode.ERROR, type(e).__name__))
        except ImportError:
            pass


def ejecutar_sql(cur, sql: str, params: tuple, consulta: str, escenario: str = "-", fase: str = "-",
                 fetch: bool = True) -> tuple[float, Any]:
    """Ejecuta una consulta dentro de un span ``db.query`` y devuelve ``(latencia_ms, filas)``.
    El cronómetro sólo envuelve ``execute+fetch``: el overhead de tracing no contamina p50/p95/p99."""
    with tracer().start_as_current_span(f"SQL {consulta}") as s:
        s.set_attribute("db.system", "postgresql")
        s.set_attribute("db.statement", " ".join(sql.split())[:2000])
        s.set_attribute("e3.consulta", consulta)
        s.set_attribute("e3.escenario", escenario)
        s.set_attribute("e3.fase", fase)
        t0 = time.perf_counter()
        try:
            cur.execute(sql, params)
            filas = cur.fetchall() if fetch else None
        except Exception as e:
            lat = (time.perf_counter() - t0) * 1000.0
            observar_error(consulta, fase, e)
            _registrar_error(s, e)
            s.set_attribute("e3.latencia_ms", lat)
            raise
        lat = (time.perf_counter() - t0) * 1000.0
        s.set_attribute("e3.latencia_ms", round(lat, 4))
        if filas is not None:
            s.set_attribute("db.rows", len(filas))
    observar_latencia(consulta, escenario, fase, lat)
    return lat, filas


def observar_latencia(consulta: str, escenario: str, fase: str, lat_ms: float) -> None:
    if _PROM:
        QUERY_LATENCY.labels(consulta, escenario, fase).observe(lat_ms / 1000.0)


def observar_error(consulta: str, fase: str, e: BaseException) -> None:
    if _PROM:
        QUERY_ERRORS.labels(consulta, fase, getattr(e, "pgcode", None) or type(e).__name__).inc()


def publicar_percentiles(consulta: str, escenario: str, fase: str, stats: Dict[str, float]) -> None:
    if _PROM:
        for q in ("p50", "p95", "p99"):
            QUERY_QUANTILE_MS.labels(consulta, escenario, fase, q).set(stats[f"{q}_ms"])


def observar_tx(transaccion: str, resultado: str, seg: float) -> None:
    if _PROM:
        TX_LATENCY.labels(transaccion, resultado).observe(seg)
        TX_TOTAL.labels(transaccion, resultado).inc()


def marcar_fase(experimento: str, fase: str, activa: bool = True) -> None:
    if _PROM:
        FASE_ACTUAL.labels(experimento, fase).set(1 if activa else 0)


def on_evento_fallas(familia: str, accion: str, detalle: Dict[str, Any]) -> None:
    """Callback para ``MotorFallas(on_evento=...)``: traduce eventos a métricas + span events."""
    if _PROM:
        FAULT_EVENTS.labels(familia, accion).inc()
        if accion in ("activada", "desactivada"):
            FAULT_ACTIVE.labels(familia).set(1 if accion == "activada" else 0)
        if accion.startswith("cb_"):
            CB_STATE.labels("catalogo").set({"cb_closed": 0, "cb_half_open": 1, "cb_open": 2}[accion])
    try:
        from opentelemetry import trace

        trace.get_current_span().add_event(f"falla.{familia}.{accion}")
    except ImportError:
        pass


# ----------------------------------------------------------------------------
# Tracer no-op (sin dependencias)
# ----------------------------------------------------------------------------
class _NoopSpan:
    def set_attribute(self, *_: Any) -> None: ...
    def add_event(self, *_: Any, **__: Any) -> None: ...
    def record_exception(self, *_: Any) -> None: ...
    def set_status(self, *_: Any) -> None: ...
    def __enter__(self) -> "_NoopSpan": return self
    def __exit__(self, *_: Any) -> None: ...


class _NoopTracer:
    def start_as_current_span(self, *_: Any, **__: Any) -> _NoopSpan:
        return _NoopSpan()
