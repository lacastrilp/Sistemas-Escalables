# ============================================================
# MAKEFILE - PORTAL B2B RETAIL (TALLER 2: ESCALABILIDAD DE DATOS)
# Universidad EAFIT · Aplicaciones y Sistemas Escalables
# ============================================================

.PHONY: all db-up db-reset generar determinismo cargar verificar benchmark-carga carga-incremental benchmark-queries graficas benchmark datos clean clean-test help informe

PYTHON ?= python3
SHELL  := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

CONTAINER_NAME ?= entregable2-postgres
DB_USER        ?= retail
DB_NAME        ?= retail

all: datos

help:
	@echo "======================================================================"
	@echo " COMANDOS DISPONIBLES - TALLER 2 (ESCALABILIDAD DE DATOS)"
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
	@echo "  make informe            - Compila el informe técnico a HTML con estilos visuales"
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
	@echo "==> [determinismo] Ejecutando validación de determinismo estricto..."
	@$(PYTHON) datos/verificar_determinismo.py

cargar: db-reset
	@echo "==> [cargar] Inyectando datos con COPY masivo y creando índices secundarios..."
	@chmod +x datos/cargar.sh
	@./datos/cargar.sh

verificar:
	@echo "==> [verificar] Auditando integridad física, volúmenes y reglas de negocio..."
	@$(PYTHON) datos/verificar.py

benchmark-carga:
	@echo "==> [benchmark-carga] Comparando las 4 estrategias de inyección masiva..."
	@$(PYTHON) datos/benchmark_carga.py

carga-incremental:
	@echo "==> [carga-incremental] Inyectando 5.000 órdenes adicionales..."
	@$(PYTHON) datos/carga_incremental.py

benchmark-queries:
	@echo "==> [benchmark-queries] Midiendo p50/p95/p99 y EXPLAIN de consultas Q1 a Q5..."
	@$(PYTHON) datos/benchmark_queries.py

graficas:
	@echo "==> [graficas] Generando gráficos de latencias y distribuciones..."
	@$(PYTHON) datos/generar_graficas.py

benchmark: benchmark-carga carga-incremental benchmark-queries graficas
	@echo "==> Suite completa de benchmarks ejecutada con éxito."

datos: db-up generar determinismo cargar verificar benchmark
	@echo "======================================================================"
	@echo " FLUJO INTEGRAL DE TALLER 2 COMPLETADO CON ÉXITO (5.66M REGISTROS)"
	@echo "======================================================================"

informe:
	@echo "==> Generando informe técnico en HTML..."
	@$(PYTHON) convertir_informe_html.py

clean-test:
	@echo "==> [clean-test] Ejecutando prueba de reproducibilidad limpia..."
	@docker compose down -v 2>/dev/null || true
	@$(MAKE) datos

clean:
	@echo "==> [clean] Deteniendo contenedores y eliminando volumen..."
	@docker compose down -v
