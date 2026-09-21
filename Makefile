# ============================================================
# MAKEFILE - PORTAL B2B RETAIL (ENTREGABLE 2)
# ============================================================

.PHONY: all db-reset generar cargar verificar benchmark-carga benchmark-queries benchmark datos clean help

PYTHON ?= python3
SHELL  := /usr/bin/env bash

all: datos

help:
	@echo "Targets disponibles:"
	@echo "  make db-reset          - Resetea los 4 esquemas de la BD ejecutando modelo-fisico.sql"
	@echo "  make generar           - Genera los datos sintéticos masivos a CSV con Zipf y casos borde"
	@echo "  make cargar            - Carga masivamente los CSVs en PostgreSQL con COPY y ANALYZE"
	@echo "  make verificar         - Corre la verificación de integridad, volúmenes, Zipf y casos borde"
	@echo "  make benchmark-carga   - Corre el benchmark de las 4 estrategias de inyección"
	@echo "  make benchmark-queries - Mide latencias p50/p95/p99 y EXPLAIN ANALYZE de consultas Q1-Q5"
	@echo "  make datos             - Ejecuta la secuencia completa de preparación, carga, verificación y benchmarks"

db-reset:
	@echo "==> Reseteando esquemas de PostgreSQL con modelo-fisico.sql..."
	@docker exec -i entregable2-postgres psql -U retail -d retail < modelo-fisico.sql > /dev/null
	@echo "    OK: Esquemas proveedores, catalogo, logistica y ordenes reseteados."

generar:
	@echo "==> Generando dataset sintético masivo a CSV (datos/generar.py)..."
	@$(PYTHON) datos/generar.py

cargar:
	@echo "==> Ejecutando carga masiva con COPY (datos/cargar.sh)..."
	@./datos/cargar.sh

verificar:
	@echo "==> Verificando dataset y estructura de datos (datos/verificar.py)..."
	@$(PYTHON) datos/verificar.py

benchmark-carga:
	@echo "==> Ejecutando benchmark de estrategias de inyección (datos/benchmark_carga.py)..."
	@$(PYTHON) datos/benchmark_carga.py

benchmark-queries:
	@echo "==> Ejecutando benchmark de consultas Q1-Q5 (datos/benchmark_queries.py)..."
	@$(PYTHON) datos/benchmark_queries.py

benchmark: benchmark-carga benchmark-queries

datos: db-reset generar cargar verificar benchmark
	@echo "======================================================================"
	@echo " FLUSO COMPLETO 'make datos' EJECUTADO EXITOSAMENTE"
	@echo "======================================================================"
