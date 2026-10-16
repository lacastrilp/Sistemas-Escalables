# ============================================================
# MAKEFILE - PORTAL B2B RETAIL (ENTREGABLE 2: ESCALABILIDAD DE DATOS)
# Universidad EAFIT · Aplicaciones y Sistemas Escalables
# ============================================================

.PHONY: all db-up db-reset generar determinismo cargar verificar benchmark-carga carga-incremental benchmark-queries graficas benchmark datos clean clean-test help

PYTHON ?= python3
SHELL  := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

CONTAINER_NAME ?= entregable2-postgres
DB_USER        ?= retail
DB_NAME        ?= retail

all: datos

help:
	@echo "======================================================================"
	@echo " COMANDOS DISPONIBLES - ENTREGABLE 2 (ESCALABILIDAD DE DATOS)"
	@echo "======================================================================"
	@echo "  make db-up              - Levanta PostgreSQL con Docker Compose y espera healthcheck"
	@echo "  make db-reset           - Resetea los 4 esquemas de la BD ejecutando modelo-fisico.sql"
	@echo "  make generar            - Genera los datos sintéticos masivos a CSV con Zipf y casos borde"
	@echo "  make determinismo       - Demuestra determinismo estricto comparando 2 corridas independientes"
	@echo "  make cargar             - Carga masivamente los CSVs con COPY, ANALYZE e índices secundarios"
	@echo "  make verificar          - Audita volúmenes en BD, esquemas, Zipf, estacionalidad y casos borde"
	@echo "  make benchmark-carga    - Evalúa las 4 estrategias de inyección sobre 50.000 órdenes"
	@echo "  make carga-incremental  - Inserta 5.000 órdenes adicionales vía ruta transaccional real"
	@echo "  make benchmark-queries  - Mide latencias p50/p95/p99 y genera EXPLAIN (ANALYZE, BUFFERS) Q1-Q5"
	@echo "  make graficas           - Genera las figuras PNG y CSVs de datos para el informe técnico"
	@echo "  make datos              - Flujo integral: levanta, resetea, genera, carga, verifica y mide"
	@echo "  make clean-test         - Simula una máquina limpia en volumen/proyecto Docker aislado"
	@echo "  make clean              - Detiene y elimina el contenedor y volumen de este entregable"
	@echo "======================================================================"

db-up:
	@echo "==> [db-up] Iniciando servicio PostgreSQL con Docker Compose..."
	@docker compose up -d postgres
	@echo "==> [db-up] Esperando a que PostgreSQL pase el healthcheck..."
	@for i in {1..30}; do \
		status=$$(docker inspect --format='{{json .State.Health.Status}}' $(CONTAINER_NAME) 2>/dev/null || echo '"starting"'); \
		if [ "$$status" = '"healthy"' ]; then \
			echo "    OK: PostgreSQL está listo y saludable."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "    ERROR: PostgreSQL no alcanzó estado saludable a tiempo."; \
	exit 1

db-reset: db-up
	@echo "==> [db-reset] Reseteando esquemas base con modelo-fisico.sql..."
	@docker exec -i $(CONTAINER_NAME) psql -U $(DB_USER) -d $(DB_NAME) < modelo-fisico.sql > /dev/null
	@echo "    OK: Esquemas proveedores, catalogo, logistica y ordenes preparados."

generar:
	@echo "==> [generar] Generando dataset sintético masivo a CSV (datos/generar.py)..."
	@$(PYTHON) datos/generar.py

determinismo:
	@echo "==> [determinismo] Verificando determinismo con dos corridas independientes..."
	@$(PYTHON) datos/verificar_determinismo.py

cargar: db-up
	@echo "==> [cargar] Ejecutando carga masiva con COPY y creación posterior de índices..."
	@./datos/cargar.sh

verificar: db-up
	@echo "==> [verificar] Verificando dataset real en PostgreSQL y CSVs (datos/verificar.py)..."
	@$(PYTHON) datos/verificar.py

benchmark-carga: db-up
	@echo "==> [benchmark-carga] Evaluando 4 estrategias de inyección (datos/benchmark_carga.py)..."
	@$(PYTHON) datos/benchmark_carga.py

carga-incremental: db-up
	@echo "==> [carga-incremental] Inyectando 5.000 órdenes vía ruta transaccional (datos/carga_incremental.py)..."
	@$(PYTHON) datos/carga_incremental.py

benchmark-queries: db-up
	@echo "==> [benchmark-queries] Midiendo Q1-Q5 y generando EXPLAINs (datos/benchmark_queries.py)..."
	@$(PYTHON) datos/benchmark_queries.py

graficas:
	@echo "==> [graficas] Generando gráficas de evidencia en datos/output/ (datos/generar_graficas.py)..."
	@$(PYTHON) datos/generar_graficas.py

benchmark: benchmark-carga carga-incremental benchmark-queries

datos: db-up db-reset generar determinismo cargar verificar benchmark graficas
	@echo "======================================================================"
	@echo " FLUJO COMPLETO 'make datos' EJECUTADO EXITOSAMENTE AL 100%"
	@echo "======================================================================"

clean:
	@echo "==> Deteniendo y eliminando contenedor y volumen de desarrollo..."
	@docker compose down -v
	@echo "    OK: Entorno limpio."

clean-test:
	@echo "======================================================================"
	@echo " SIMULANDO EJECUCIÓN EN MÁQUINA LIMPIA (PROYECTO DOCKER AISLADO)"
	@echo "======================================================================"
	@mkdir -p datos/output/logs
	@bash -c '\
		PROJECT_CLEAN="entregable2_clean_$$RANDOM"; \
		LOG_FILE="datos/output/logs/clean_test.log"; \
		echo "Iniciando prueba limpia en proyecto Docker: $$PROJECT_CLEAN" | tee "$$LOG_FILE"; \
		trap "docker compose -p $$PROJECT_CLEAN down -v >/dev/null 2>&1 || true" EXIT; \
		docker compose -p $$PROJECT_CLEAN up -d postgres >> "$$LOG_FILE" 2>&1; \
		echo "Esperando readiness en proyecto aislado..." | tee -a "$$LOG_FILE"; \
		for i in {1..30}; do \
			if docker compose -p $$PROJECT_CLEAN exec -T postgres pg_isready -U $(DB_USER) -d $(DB_NAME) >/dev/null 2>&1; then \
				break; \
			fi; \
			sleep 1; \
		done; \
		echo "Ejecutando make datos contra el entorno limpio..." | tee -a "$$LOG_FILE"; \
		CONTAINER_NAME="$$PROJECT_CLEAN-postgres-1" make datos >> "$$LOG_FILE" 2>&1; \
		echo "PRUEBA LIMPIA COMPLETADA CON ÉXITO. Log guardado en $$LOG_FILE." | tee -a "$$LOG_FILE"; \
	'

# Forwarding para Entregable 3
e3-up e3-down e3-status e3-m1 e3-exp1 e3-exp2 e3-exp3 e3-exp4 e3-mejora e3-todo e3-killswitch e3-informe:
	@$(MAKE) -C "Taller 3" $@

