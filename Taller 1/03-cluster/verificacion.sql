-- =========================================================
-- verificacion.sql
-- Ejecutar en el PRIMARIO para ver el estado del cluster:
--   docker exec -it pg-primary psql -U eafit -d taller_cluster
-- =========================================================

-- Debe mostrar 2 filas (una por réplica conectada), estado "streaming"
SELECT client_addr, state, sync_state, replay_lsn, write_lsn, flush_lsn
FROM pg_stat_replication;

-- LSN actual de escritura en el primario (para comparar contra las réplicas)
SELECT pg_current_wal_lsn();


-- =========================================================
-- Ejecutar en CADA RÉPLICA:
--   docker exec -it pg-replica1 psql -U eafit -d taller_cluster
--   docker exec -it pg-replica2 psql -U eafit -d taller_cluster
-- =========================================================

-- Debe devolver "t" (true) -> confirma que este nodo es standby
SELECT pg_is_in_recovery();

-- LSN hasta donde la réplica ha aplicado WAL (compararlo con
-- pg_current_wal_lsn() del primario: entre más cerca, menor el lag)
SELECT pg_last_wal_replay_lsn();

-- Rezago de replicación en tiempo (segundos)
SELECT now() - pg_last_xact_replay_timestamp() AS lag_replicacion;
