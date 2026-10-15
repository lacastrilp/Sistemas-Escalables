#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

# ============================================================
# SCRIPT DE CARGA MASIVA - PORTAL B2B RETAIL (ENTREGABLE 2)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$SCRIPT_DIR/output"
LOG_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOG_DIR"

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

# 1. RESET DE ESQUEMAS Y TABLAS LIMPIAS (SIN ÍNDICES SECUNDARIOS)
echo ""
echo "[Fase 0] Reseteando esquemas con modelo-fisico.sql..."
START_RESET=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/modelo-fisico.sql" > /dev/null
END_RESET=$(date +%s)
DIFF_RESET=$((END_RESET - START_RESET))
echo "         OK (${DIFF_RESET}s)"

# 2. CARGA POR TABLAS CON COPY
echo ""
echo "[Fase 1] Ejecutando COPY masivo por tabla (sin índices secundarios)..."

METRICS_FILE="$OUTPUT_DIR/tiempos_carga.json"
echo "{" > "$METRICS_FILE"

cargar_tabla() {
    local esquema=$1
    local tabla=$2
    local columnas=$3
    local csv_filename=$4
    local is_last=${5:-0}
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

    local comma=","
    if [ "$is_last" -eq 1 ]; then
        comma=""
    fi
    echo "  \"$esquema.$tabla\": {\"filas\": $rows, \"tiempo_seg\": $diff, \"filas_por_seg\": $rps}$comma" >> "$METRICS_FILE"
}

START_COPY_TOTAL=$(date +%s)

cargar_tabla "proveedores" "proveedor" "id, nit, nombre, estado, fecha_registro" "proveedores.csv" 0
cargar_tabla "proveedores" "contrato_suministro" "id, proveedor_id, fecha_inicio, fecha_fin, estado, limite_credito" "contratos.csv" 0
cargar_tabla "catalogo" "sku" "id, codigo, nombre, categoria, precio_base, estado" "skus.csv" 0
cargar_tabla "catalogo" "proveedor_sku" "id, proveedor_id, sku_id, precio_negociado, fecha_inicio, fecha_fin, estado" "proveedor_sku.csv" 0
cargar_tabla "logistica" "cedi" "id, codigo, nombre, ciudad, capacidad_diaria, estado" "cedi.csv" 0
cargar_tabla "logistica" "franja_descargue" "id, cedi_id, fecha, hora_inicio, hora_fin, capacidad, reservados, estado" "franjas.csv" 0
cargar_tabla "ordenes" "orden_compra" "id, numero_orden, proveedor_id, fecha_orden, estado, cedi_id, franja_id, total, fecha_compromiso_entrega, fecha_entrega, fecha_confirmacion, idempotency_key" "ordenes.csv" 0
cargar_tabla "ordenes" "linea_orden" "id, orden_id, numero_linea, sku_id, cantidad, precio_unitario, cantidad_recibida, fecha_recepcion" "lineas_orden.csv" 0
cargar_tabla "ordenes" "evento_auditoria" "id, orden_id, tipo_evento, fecha_evento, payload" "eventos.csv" 1

END_COPY_TOTAL=$(date +%s)
DIFF_COPY_TOTAL=$((END_COPY_TOTAL - START_COPY_TOTAL))

echo "}" >> "$METRICS_FILE"

echo "----------------------------------------------------------------------"
printf " TIEMPO TOTAL COPY MASIVO: %3ds\n" "$DIFF_COPY_TOTAL"
echo "----------------------------------------------------------------------"

# 3. ANALYZE BASELINE PREVIO A ÍNDICES SECUNDARIOS
echo ""
echo "[Fase 2] Ejecutando ANALYZE baseline para estadísticas previas a índices..."
START_ANA_PRE=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "ANALYZE;" > /dev/null
END_ANA_PRE=$(date +%s)
DIFF_ANA_PRE=$((END_ANA_PRE - START_ANA_PRE))
echo "         OK (${DIFF_ANA_PRE}s)"

# 4. CREACIÓN DE ÍNDICES SECUNDARIOS POST-CARGA
echo ""
echo "[Fase 3] Creando índices secundarios post-carga (datos/sql/indices_secundarios.sql)..."
START_IDX=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" < "$ROOT_DIR/datos/sql/indices_secundarios.sql" > /dev/null
END_IDX=$(date +%s)
DIFF_IDX=$((END_IDX - START_IDX))
echo "         OK (${DIFF_IDX}s)"

# 5. ANALYZE FINAL POST-ÍNDICES
echo ""
echo "[Fase 4] Ejecutando ANALYZE final para actualizar estadísticas del optimizador..."
START_ANA_POST=$(date +%s)
docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "ANALYZE;" > /dev/null
END_ANA_POST=$(date +%s)
DIFF_ANA_POST=$((END_ANA_POST - START_ANA_POST))
echo "         OK (${DIFF_ANA_POST}s)"

TOTAL_TIEMPO=$((DIFF_RESET + DIFF_COPY_TOTAL + DIFF_IDX + DIFF_ANA_POST))
echo "======================================================================"
printf " CARGA COMPLETADA EXITOSAMENTE EN %3d SEGUNDOS\n" "$TOTAL_TIEMPO"
echo "======================================================================"
