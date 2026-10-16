# ============================================================
# MASTER MAKEFILE - REPOSITORIO DE SISTEMAS ESCALABLES
# Universidad EAFIT · Aplicaciones y Sistemas Escalables (2026-2)
# Grupo EKS · Sara López Marín & Luis Alejandro Castrillón Pulgarin
# ============================================================

.PHONY: help all \
        t1-help t1-standalone-up t1-standalone-down t1-cluster-up t1-cluster-down \
        t2-help t2-up t2-datos t2-verificar t2-benchmark t2-informe t2-down \
        t3-help t3-up t3-down t3-status t3-killswitch t3-m1 t3-exp1 t3-exp2 t3-exp3 t3-exp4 t3-mejora t3-todo t3-informe \
        e3-up e3-down e3-status e3-killswitch e3-m1 e3-exp1 e3-exp2 e3-exp3 e3-exp4 e3-mejora e3-todo e3-informe

SHELL := /usr/bin/env bash
.SHELLFLAGS := -euo pipefail -c

all: help

help:
	@echo "=========================================================================================="
	@echo " UNIVERSIDAD EAFIT - APLICACIONES Y SISTEMAS ESCALABLES (2026-2)"
	@echo " Repositorio Central · Grupo EKS (Sara López Marín & Luis Alejandro Castrillón Pulgarin)"
	@echo "=========================================================================================="
	@echo " COMANDOS PRINCIPALES POR TALLER / ENTREGABLE:"
	@echo "------------------------------------------------------------------------------------------"
	@echo " [TALLER 1: ARQUITECTURA DE DATOS, ÍNDICES Y REPLICACIÓN]"
	@echo "   make t1-standalone-up   - Levanta entorno Docker standalone de Taller 1"
	@echo "   make t1-standalone-down - Detiene entorno standalone"
	@echo "   make t1-cluster-up      - Levanta clúster primary-standby (3 nodos)"
	@echo "   make t1-cluster-down    - Detiene clúster de Taller 1"
	@echo ""
	@echo " [TALLER 2: ESCALABILIDAD DE DATOS MASIVOS (5.66M REGISTROS)]"
	@echo "   make t2-up              - Levanta PostgreSQL para Taller 2"
	@echo "   make t2-datos           - Ejecuta pipeline completo: genera, carga, audita y benchmark"
	@echo "   make t2-verificar       - Audita volúmenes en BD, esquemas, Zipf y casos borde"
	@echo "   make t2-benchmark       - Ejecuta benchmarks de carga y consultas Q1 a Q5"
	@echo "   make t2-informe         - Compila informe técnico de Entrega 2 a HTML"
	@echo "   make t2-down            - Detiene servicio PostgreSQL de Taller 2"
	@echo ""
	@echo " [TALLER 3: LABORATORIO DE CAOS, INYECCIÓN DE FALLAS Y OBSERVABILIDAD]"
	@echo "   make t3-up              - Levanta stack completo (Postgres, Toxiproxy, Jaeger, Prometheus, Grafana)"
	@echo "   make t3-status          - Estado de contenedores Docker y configuración de fallas en caliente"
	@echo "   make t3-killswitch      - Kill switch maestro: apaga todas las fallas en < 1 segundo"
	@echo "   make t3-m1              - Momento 1: Línea base reproducible y tabla de metas (-10%)"
	@echo "   make t3-exp1            - Experimento 1: Familia Red / Latencia 150ms con Toxiproxy"
	@echo "   make t3-exp2            - Experimento 2: Familia Dependencias / Timeout Catálogo y Circuit Breaker"
	@echo "   make t3-exp3            - Experimento 3: Familia Recursos / Inanición de Pool con Zombies"
	@echo "   make t3-exp4            - Experimento 4: Familia Datos / Locks FOR UPDATE en Proveedor Caliente"
	@echo "   make t3-mejora          - Demostración de Mejora del 10% (Caché LRU Q1 y Read Model Q4)"
	@echo "   make t3-todo            - Ejecuta la suite experimental completa de E3 de extremo a extremo"
	@echo "   make t3-informe         - Genera el informe técnico de Entrega 3 en HTML"
	@echo "   make t3-down            - Detiene contenedores preservando el volumen de 5.66M filas"
	@echo "=========================================================================================="

# -----------------------------------------------------------------------------------------
# Taller 1 Target Forwarding
# -----------------------------------------------------------------------------------------
t1-help:
	@cat "Taller 1/README.md"

t1-standalone-up:
	@$(MAKE) -C "Taller 1/01-standalone" -f - <<< "$$(echo -e 'all:\n\tdocker compose up -d')"

t1-standalone-down:
	@docker compose -f "Taller 1/01-standalone/docker-compose.yml" down

t1-cluster-up:
	@docker compose -f "Taller 1/03-cluster/docker-compose.yml" up -d

t1-cluster-down:
	@docker compose -f "Taller 1/03-cluster/docker-compose.yml" down

# -----------------------------------------------------------------------------------------
# Taller 2 Target Forwarding
# -----------------------------------------------------------------------------------------
t2-help:
	@$(MAKE) -C "Taller 2" help

t2-up:
	@$(MAKE) -C "Taller 2" db-up

t2-datos:
	@$(MAKE) -C "Taller 2" datos

t2-verificar:
	@$(MAKE) -C "Taller 2" verificar

t2-benchmark:
	@$(MAKE) -C "Taller 2" benchmark

t2-informe:
	@$(MAKE) -C "Taller 2" informe

t2-down:
	@$(MAKE) -C "Taller 2" clean

# -----------------------------------------------------------------------------------------
# Taller 3 Target Forwarding (with backward-compatible e3-* aliases)
# -----------------------------------------------------------------------------------------
t3-help:
	@$(MAKE) -C "Taller 3" help

t3-up:
	@$(MAKE) -C "Taller 3" e3-up

t3-down:
	@$(MAKE) -C "Taller 3" e3-down

t3-status:
	@$(MAKE) -C "Taller 3" e3-status

t3-killswitch:
	@$(MAKE) -C "Taller 3" e3-killswitch

t3-m1:
	@$(MAKE) -C "Taller 3" e3-m1

t3-exp1:
	@$(MAKE) -C "Taller 3" e3-exp1

t3-exp2:
	@$(MAKE) -C "Taller 3" e3-exp2

t3-exp3:
	@$(MAKE) -C "Taller 3" e3-exp3

t3-exp4:
	@$(MAKE) -C "Taller 3" e3-exp4

t3-mejora:
	@$(MAKE) -C "Taller 3" e3-mejora

t3-todo:
	@$(MAKE) -C "Taller 3" e3-todo

t3-informe:
	@$(MAKE) -C "Taller 3" e3-informe

# Backward-compatible e3-* aliases:
e3-up: t3-up
e3-down: t3-down
e3-status: t3-status
e3-killswitch: t3-killswitch
e3-m1: t3-m1
e3-exp1: t3-exp1
e3-exp2: t3-exp2
e3-exp3: t3-exp3
e3-exp4: t3-exp4
e3-mejora: t3-mejora
e3-todo: t3-todo
e3-informe: t3-informe
