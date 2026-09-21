#!/usr/bin/env bash
set -e
export LC_ALL=C

# ============================================================
# SCRIPT DE CARGA MASIVA - PORTAL B2B RETAIL (ENTREGABLE 2)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$SCRIPT_DIR/output"

CONTAINER_NAME="${CONTAINER_NAME:-entregable2-postgres}"
DB_USER="${DB_USER:-retail}"
DB_NAME="${DB_NAME:-retail}"

echo "======================================================================"
echo " CARGA MASIVA DE DATOS A POSTGRESQL (COPY)"
echo "======================================================================"
echo "Contenedor: $CONTAINER_NAME"
echo "Base datos: $DB_NAME ($DB_USER)"
echo "CSV Dir:    $OUTPUT_DIR"
echo "======================================================================"

if [ ! -d "$OUTPUT_DIR" ] || [ ! -f "$OUTPUT_DIR/proveedores.csv" ]; then
    echo "[ERROR] No se encontraron archivos CSV en $OUTPUT_DIR."
    echo "Por favor ejecute primero 'python3 datos/generar.py'"
    exit 1
fi

# 1. RESET DE ESQUEMAS Y TABLAS
echo ""
echo "[Fase 0] Reseteando esquemas con modelo-fisico.sql..."
START_RESET=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/modelo-fisico.sql" > /dev/null 2>&1
END_RESET=$(date +%s)
DIFF_RESET=$((END_RESET - START_RESET))
echo "         OK (${DIFF_RESET}s)"

# Eliminar temporalmente índices secundarios para acelerar la carga masiva
echo ""
echo "[Fase 1] Preparando entorno para COPY (eliminando índices secundarios)..."
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" << 'EOF' > /dev/null 2>&1
DROP INDEX IF EXISTS proveedores.idx_contrato_proveedor;
DROP INDEX IF EXISTS proveedores.idx_contrato_estado_fecha;
DROP INDEX IF EXISTS catalogo.idx_proveedor_sku_proveedor;
DROP INDEX IF EXISTS catalogo.idx_proveedor_sku_sku;
DROP INDEX IF EXISTS catalogo.idx_proveedor_sku_estado;
DROP INDEX IF EXISTS ordenes.idx_orden_proveedor_fecha;
DROP INDEX IF EXISTS ordenes.idx_orden_fecha;
DROP INDEX IF EXISTS ordenes.idx_orden_cedi_fecha;
DROP INDEX IF EXISTS ordenes.idx_orden_franja;
DROP INDEX IF EXISTS ordenes.idx_linea_orden;
DROP INDEX IF EXISTS ordenes.idx_linea_sku;
DROP INDEX IF EXISTS ordenes.idx_evento_orden_fecha;
DROP INDEX IF EXISTS ordenes.idx_evento_fecha;
DROP INDEX IF EXISTS logistica.idx_franja_cedi_fecha;
EOF
echo "         OK"

# 2. CARGA POR TABLAS CON COPY Y ESPECIFICACIÓN DE COLUMNAS
echo ""
echo "[Fase 2] Ejecutando COPY masivo por tabla..."

cargar_tabla() {
    local esquema=$1
    local tabla=$2
    local columnas=$3
    local csv_filename=$4
    local csv_path="$OUTPUT_DIR/$csv_filename"

    if [ ! -f "$csv_path" ]; then
        echo "   - $esquema.$tabla: [SKIP] archivo $csv_filename no existe"
        return
    fi

    local start_time=$(date +%s)
    local rows=$(wc -l < "$csv_path")
    rows=$((rows - 1)) # descontar header

    docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c \
        "\copy $esquema.$tabla($columnas) FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'utf-8')" < "$csv_path" > /dev/null

    local end_time=$(date +%s)
    local diff=$((end_time - start_time))
    if [ "$diff" -eq 0 ]; then
        diff=1
    fi
    local rps=$((rows / diff))

    printf "   - %-32s : %10d filas en %3ds (%8d filas/seg)\n" "$esquema.$tabla" "$rows" "$diff" "$rps"
}

START_COPY_TOTAL=$(date +%s)

cargar_tabla "proveedores" "proveedor" "id, nit, nombre, estado, fecha_registro" "proveedores.csv"
cargar_tabla "proveedores" "contrato_suministro" "id, proveedor_id, fecha_inicio, fecha_fin, estado, limite_credito" "contratos.csv"
cargar_tabla "catalogo" "sku" "id, codigo, nombre, categoria, precio_base, estado" "skus.csv"
cargar_tabla "catalogo" "proveedor_sku" "id, proveedor_id, sku_id, precio_negociado, fecha_inicio, fecha_fin, estado" "proveedor_sku.csv"
cargar_tabla "logistica" "cedi" "id, codigo, nombre, ciudad, capacidad_diaria, estado" "cedi.csv"
cargar_tabla "logistica" "franja_descargue" "id, cedi_id, fecha, hora_inicio, hora_fin, capacidad, reservados, estado" "franjas.csv"
cargar_tabla "ordenes" "orden_compra" "id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_entrega, fecha_confirmacion, idempotency_key" "ordenes.csv"
cargar_tabla "ordenes" "linea_orden" "id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion" "lineas_orden.csv"
cargar_tabla "ordenes" "evento_auditoria" "id, orden_id, tipo_evento, fecha_evento, payload" "eventos.csv"

END_COPY_TOTAL=$(date +%s)
DIFF_COPY_TOTAL=$((END_COPY_TOTAL - START_COPY_TOTAL))

echo "----------------------------------------------------------------------"
printf " TIEMPO TOTAL COPY MASIVO: %3ds\n" "$DIFF_COPY_TOTAL"
echo "----------------------------------------------------------------------"

# 3. CREACIÓN DE ÍNDICES SECUNDARIOS POST-CARGA
echo ""
echo "[Fase 3] Creando índices secundarios post-carga..."
START_IDX=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" << 'EOF' > /dev/null
CREATE INDEX idx_contrato_proveedor ON proveedores.contrato_suministro(proveedor_id);
CREATE INDEX idx_contrato_estado_fecha ON proveedores.contrato_suministro(estado, fecha_inicio, fecha_fin);
CREATE INDEX idx_proveedor_sku_proveedor ON catalogo.proveedor_sku(proveedor_id);
CREATE INDEX idx_proveedor_sku_sku ON catalogo.proveedor_sku(sku_id);
CREATE INDEX idx_proveedor_sku_estado ON catalogo.proveedor_sku(proveedor_id, estado);
CREATE INDEX idx_orden_proveedor_fecha ON ordenes.orden_compra(proveedor_id, fecha_orden);
CREATE INDEX idx_orden_fecha ON ordenes.orden_compra(fecha_orden);
CREATE INDEX idx_orden_cedi_fecha ON ordenes.orden_compra(cedi_id, fecha_orden);
CREATE INDEX idx_orden_franja ON ordenes.orden_compra(franja_id);
CREATE INDEX idx_linea_orden ON ordenes.linea_orden(orden_id);
CREATE INDEX idx_linea_sku ON ordenes.linea_orden(sku_id);
CREATE INDEX idx_evento_orden_fecha ON ordenes.evento_auditoria(orden_id, fecha_evento);
CREATE INDEX idx_evento_fecha ON ordenes.evento_auditoria(fecha_evento);
CREATE INDEX idx_franja_cedi_fecha ON logistica.franja_descargue(cedi_id, fecha);
EOF
END_IDX=$(date +%s)
DIFF_IDX=$((END_IDX - START_IDX))
echo "         OK (${DIFF_IDX}s)"

# 4. ANALYZE
echo ""
echo "[Fase 4] Ejecutando ANALYZE para actualizar estadísticas del planeador..."
START_ANA=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "ANALYZE;" > /dev/null
END_ANA=$(date +%s)
DIFF_ANA=$((END_ANA - START_ANA))
echo "         OK (${DIFF_ANA}s)"

TOTAL_TIEMPO=$((DIFF_RESET + DIFF_COPY_TOTAL + DIFF_IDX + DIFF_ANA))
echo "======================================================================"
printf " CARGA COMPLETADA EXITOSAMENTE EN %3d SEGUNDOS\n" "$TOTAL_TIEMPO"
echo "======================================================================"
