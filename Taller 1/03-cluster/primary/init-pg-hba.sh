#!/bin/bash
# Permite que las réplicas se conecten al canal especial "replication"
# (el "all" genérico de pg_hba.conf NO cubre la pseudo-base "replication")
set -e
echo "host replication replicador 0.0.0.0/0 scram-sha-256" >> "$PGDATA/pg_hba.conf"
