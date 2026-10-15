#!/bin/bash
# Entrypoint personalizado para las réplicas.
# Si el volumen de datos está vacío, clona el primario con
# pg_basebackup usando el flag -R, que crea automáticamente:
#   - standby.signal
#   - postgresql.auto.conf con primary_conninfo apuntando al primario
# A partir de eso el contenedor arranca como standby normal.
set -e

if [ -z "$(ls -A "$PGDATA" 2>/dev/null)" ]; then
  echo ">> Directorio de datos vacío. Esperando al primario ($PRIMARY_HOST)..."
  until pg_isready -h "$PRIMARY_HOST" -p 5432 -U "$REPL_USER"; do
    sleep 2
  done

  echo ">> Ejecutando pg_basebackup contra $PRIMARY_HOST..."
  PGPASSWORD="$REPL_PASSWORD" pg_basebackup \
    -h "$PRIMARY_HOST" -p 5432 -U "$REPL_USER" \
    -D "$PGDATA" -Fp -Xs -P -R -S "$REPL_SLOT"

  chmod 700 "$PGDATA"
  echo ">> Clonación completa. Iniciando como standby."
fi

exec docker-entrypoint.sh postgres
