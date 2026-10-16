# ============================================================
# MAKEFILE - PORTAL B2B RETAIL (ENTREGABLE 2: ESCALABILIDAD DE DATOS)
# Universidad EAFIT · Aplicaciones y Sistemas Escalables
# ============================================================

.PHONY: all db-up db-reset generar determinismo cargar verificar benchmark-carga carga-incremental benchmark-queries graficas benchmark datos clean clean-test help e3-up e3-down e3-status e3-m1 e3-exp1 e3-exp2 e3-exp3 e3-exp4 e3-mejora e3-todo e3-killswitch e3-informe

PYTHON ?= $(shell which python3)
SHELL  := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

CONTAINER_NAME ?= entregable2-postgres
DB_USER        ?= retail
DB_NAME        ?= retail

all: datos

help:
	@echo "======================================================================"
	@echo " COMANDOS DISPONIBLES - ENTREGABLE 3 (EL CORAZÓN DEL PROYECTO)"
	@echo "======================================================================"
	@echo "  make e3-up              - Levanta el stack completo (Postgres, Toxiproxy, Jaeger, Prometheus, Grafana)"
	@echo "  make e3-down            - Detiene contenedores preservando el volumen de 5.66M filas"
	@echo "  make e3-status          - Estado de contenedores Docker y configuración de fallas en caliente"
	@echo "  make e3-killswitch      - KILL SWITCH maestro: apaga todas las fallas en < 1 segundo"
	@echo "  make e3-m1              - Momento 1: Línea base reproducible y tabla de metas (-10%)"
	@echo "  make e3-exp1            - Experimento 1: Familia Red / Latencia 150ms con Toxiproxy"
	@echo "  make e3-exp2            - Experimento 2: Familia Dependencias / Timeout Catálogo y Circuit Breaker"
	@echo "  make e3-exp3            - Experimento 3: Familia Recursos / Inanición de Pool con Zombies"
	@echo "  make e3-exp4            - Experimento 4: Familia Datos / Locks FOR UPDATE en Proveedor Caliente"
	@echo "  make e3-mejora          - Demostración de Mejora del 10% (Caché LRU Q1 y Read Model Q4)"
	@echo "  make e3-todo            - Ejecuta la suite experimental completa de E3 de extremo a extremo"
	@echo "  make e3-informe         - Genera el informe técnico de Entrega 3 en HTML"
	@echo "----------------------------------------------------------------------"
	@echo " COMANDOS BASE ENTREGABLE 2"
	@echo "----------------------------------------------------------------------"
	@echo "  make db-up              - Levanta PostgreSQL con Docker Compose y espera healthcheck"
	@echo "  make db-reset           - Resetea los 4 esquemas de la BD ejecutando modelo-fisico.sql"
	@echo "  make generar            - Genera los datos sintéticos masivos a CSV con Zipf y casos borde"
	@echo "  make determinismo       - Demuestra determinismo estricto comparando 2 corridas independientes"
	@echo "  make cargar             - Carga masivamente los CSVs con COPY, ANALYZE e índices secundarios"
	@echo "  make verificar          - Audita volúmenes en BD, esquemas, Zipf, estacionalidad y casos borde"
	@echo "  make benchmark          - Evalúa benchmarks de carga y consultas Q1-Q5"
	@echo "  make datos              - Flujo integral de E2 completo"
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

# ============================================================
# TARGETS ENTREGABLE 3: OBSERVABILIDAD Y LABORATORIO DE FALLAS
# ============================================================

e3-up:
	@echo "==> [e3-up] Iniciando stack completo de observabilidad y fallas..."
	@docker compose up -d
	@echo "==> [e3-up] Esperando healthcheck de PostgreSQL..."
	@for i in {1..30}; do \
		status=$$(docker inspect --format='{{json .State.Health.Status}}' $(CONTAINER_NAME) 2>/dev/null || echo '"starting"'); \
		if [ "$$status" = '"healthy"' ]; then \
			echo "    OK: Stack E3 activo (PostgreSQL, Toxiproxy, Jaeger, Prometheus, Grafana)."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "    ERROR: PostgreSQL no alcanzó estado saludable a tiempo."; exit 1

e3-down:
	@echo "==> [e3-down] Deteniendo contenedores preservando el volumen de datos..."
	@docker compose down

e3-status:
	@echo "==> [e3-status] Estado de contenedores Docker:"
	@docker compose ps
	@echo "==> [e3-status] Estado de fallas configurables:"
	@$(PYTHON) datos/motor_fallas.py status

e3-killswitch:
	@echo "==> [e3-killswitch] Activando KILL SWITCH maestro en caliente..."
	@$(PYTHON) datos/motor_fallas.py off

e3-m1: e3-up
	@echo "==> [e3-m1] Ejecutando Momento 1: Línea base y tabla de metas (-10%)..."
	@$(PYTHON) datos/experimentos_e3.py --m1

e3-exp1: e3-up
	@echo "==> [e3-exp1] Ejecutando Experimento 1: Familia Red (Toxiproxy Latencia 150ms)..."
	@$(PYTHON) datos/experimentos_e3.py --exp1

e3-exp2: e3-up
	@echo "==> [e3-exp2] Ejecutando Experimento 2: Familia Dependencias (Catálogo + Circuit Breaker)..."
	@$(PYTHON) datos/experimentos_e3.py --exp2

e3-exp3: e3-up
	@echo "==> [e3-exp3] Ejecutando Experimento 3: Familia Recursos (Pool zombies)..."
	@$(PYTHON) datos/experimentos_e3.py --exp3

e3-exp4: e3-up
	@echo "==> [e3-exp4] Ejecutando Experimento 4: Familia Datos (Locks en Proveedor Caliente)..."
	@$(PYTHON) datos/experimentos_e3.py --exp4

e3-mejora: e3-up
	@echo "==> [e3-mejora] Ejecutando Demostración de Mejora del 10% (Caché LRU y Read Model)..."
	@$(PYTHON) datos/experimentos_e3.py --mejora

e3-todo: e3-up
	@echo "======================================================================"
	@echo " EJECUTANDO SUITE COMPLETA DEL ENTREGABLE 3 (100% AUTOMATIZADO)"
	@echo "======================================================================"
	@$(PYTHON) datos/experimentos_e3.py --todo

e3-informe:
	@echo "==> [e3-informe] Generando informe técnico HTML de Entrega 3..."
	@$(PYTHON) convertir_informe_e3_html.py
