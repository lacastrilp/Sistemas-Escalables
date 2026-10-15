-- Se ejecuta automáticamente en el primer arranque del primario
-- (Postgres corre todo lo que está en /docker-entrypoint-initdb.d/)
CREATE ROLE replicador WITH REPLICATION LOGIN PASSWORD 'replica2026';

SELECT pg_create_physical_replication_slot('slot_replica1');
SELECT pg_create_physical_replication_slot('slot_replica2');
