## PARTE 4 — Cluster de PostgreSQL (3 nodos, streaming replication)

Arquitectura: **1 primario + 2 réplicas** en modo *streaming replication* asíncrona (el modelo de gestión básico e integrado de PostgreSQL, sin herramientas externas de alta disponibilidad como Patroni o repmgr). Esto significa: replicación automática de datos, pero **sin failover automático** — si el primario cae, alguien debe promover manualmente una réplica.

### 4.1 Repartición por equipos

Si el ejercicio se hace con varios equipos en la **misma red/máquina** (recomendado para la clase), un equipo corre el `docker compose up` completo y los demás observan/interactúan por psql. Si cada equipo tiene un **computador distinto**, ver la nota de la sección 4.5.

- **Equipo A:** levanta y administra `pg-primary`, corre las verificaciones de `pg_stat_replication`.
- **Equipo B:** administra `pg-replica1`, valida `pg_is_in_recovery()` y el lag.
- **Equipo C:** administra `pg-replica2`, hace las mismas validaciones y ejecuta la caída controlada del nodo (sección 4.4).

### 4.2 Levantar el cluster

```bash
cd 03-cluster
docker compose up -d --build
docker compose ps
```

Espere a que las tres filas aparezcan como `running` antes de consultar el
estado de PostgreSQL. `depends_on` inicia los contenedores en orden, pero no
espera a que el servidor termine de aceptar conexiones.

Qué pasa internamente:
1. `pg-primary` arranca con `wal_level=replica`, crea el rol `replicador` y dos *replication slots* (`slot_replica1`, `slot_replica2`) vía `init-replication.sql`, y habilita conexiones de replicación en `pg_hba.conf` vía `init-pg-hba.sh`.
2. `pg-replica1` y `pg-replica2` usan un `Dockerfile` propio (`03-cluster/replica/`) cuyo entrypoint corre `pg_basebackup -R` contra el primario apenas su volumen está vacío: esto clona físicamente los datos del primario **y** configura automáticamente `standby.signal` + `primary_conninfo`, dejando la réplica lista para conectarse en modo *streaming*.

Puertos expuestos en el host: primario `5543`, réplica1 `5544`, réplica2 `5545` (todos mapeados al `5432` interno). Se usan puertos separados para no interferir con otros servicios Docker del equipo.

### 4.3 Revisar el clúster paso a paso

Primero revise contenedores y logs:

```bash
docker compose ps
docker logs --tail 50 pg-primary
docker logs --tail 50 pg-replica1
docker logs --tail 50 pg-replica2
```

En el primario deben aparecer dos conexiones en estado `streaming`:

```bash
docker exec -it pg-primary psql -U eafit -d taller_cluster -c \
  "SELECT client_addr, application_name, state, sync_state, sent_lsn, replay_lsn FROM pg_stat_replication;"
docker exec -it pg-primary psql -U eafit -d taller_cluster -c \
  "SELECT pg_current_wal_lsn() AS wal_primario;"
```

En cada réplica, `pg_is_in_recovery()` debe devolver `t`:

```bash
docker exec -it pg-replica1 psql -U eafit -d taller_cluster -c \
  "SELECT pg_is_in_recovery() AS es_replica, pg_last_wal_replay_lsn() AS replay_lsn, now() - pg_last_xact_replay_timestamp() AS lag;"
docker exec -it pg-replica2 psql -U eafit -d taller_cluster -c \
  "SELECT pg_is_in_recovery() AS es_replica, pg_last_wal_replay_lsn() AS replay_lsn, now() - pg_last_xact_replay_timestamp() AS lag;"
```

Para comprobar la replicación de extremo a extremo, escriba solo en el
primario y lea desde ambas réplicas:

```bash
docker exec -it pg-primary psql -U eafit -d taller_cluster -c \
  "CREATE TABLE IF NOT EXISTS prueba_sync (id bigserial PRIMARY KEY, creado timestamptz DEFAULT now()); INSERT INTO prueba_sync DEFAULT VALUES;"
docker exec -it pg-replica1 psql -U eafit -d taller_cluster -c "SELECT * FROM prueba_sync ORDER BY id DESC LIMIT 3;"
docker exec -it pg-replica2 psql -U eafit -d taller_cluster -c "SELECT * FROM prueba_sync ORDER BY id DESC LIMIT 3;"
```

También puede consultar `verificacion.sql` por separado: sus primeras dos
consultas van en el primario y las tres últimas se ejecutan en cada réplica.
No envíe el archivo completo a un único nodo porque mezcla consultas de
primario y standby.

### 4.4 Conectarse al clúster de otro computador

Esta conexión usa la IP del computador de tu compañero y los puertos
publicados por Docker. No uses `pg-primary` ni `localhost`: esos nombres solo
funcionan dentro del computador donde está ejecutándose el clúster.

**En el computador del compañero**, obtener la IP local:

```bash
hostname -I              # Linux
ipconfig                  # Windows
```

Debe compartir una IP de la misma red, por ejemplo `192.168.1.25`. También
debe permitir en el firewall el puerto `5543` para el primario y, si se desean
consultar directamente las réplicas, los puertos `5544` y `5545`.

El archivo `primary/init-pg-hba.sh` autoriza inicialmente el canal especial de
replicación, pero no clientes SQL remotos. Para permitir temporalmente a los
equipos de una red `192.168.1.x`, el compañero ejecuta en el primario:

```bash
docker exec pg-primary sh -c \
  "echo 'host taller_cluster eafit 192.168.1.0/24 scram-sha-256' >> \$PGDATA/pg_hba.conf"
docker exec pg-primary psql -U eafit -d taller_cluster -c "SELECT pg_reload_conf();"
```

Debe reemplazar `192.168.1.0/24` por la red real. Para una práctica rápida y
controlada también puede usar temporalmente `0.0.0.0/0`, pero no es apropiado
dejar esa regla en una red pública.

**Desde tu computador**, probar primero la red:

```bash
nc -vz 192.168.1.25 5543
```

Si el puerto está disponible, conectarse al primario con:

```bash
psql "host=192.168.1.25 port=5543 dbname=taller_cluster user=eafit password=eafit2026"
```

Para conectarse directamente a las réplicas se usan sus puertos publicados:

```bash
psql "host=192.168.1.25 port=5544 dbname=taller_cluster user=eafit password=eafit2026"
psql "host=192.168.1.25 port=5545 dbname=taller_cluster user=eafit password=eafit2026"
```

Las réplicas aceptan lecturas, pero no escrituras mientras
`pg_is_in_recovery()` sea `true`. Las escrituras deben hacerse en el primario.
En DBeaver o pgAdmin use la misma IP, puerto, base de datos, usuario y
contraseña.

### 4.5 Medir lag y latencia de replicación

El lag se puede observar desde el primario comparando el LSN enviado con el
LSN reproducido por cada réplica:

```bash
docker exec pg-primary psql -U eafit -d taller_cluster -c \
  "SELECT application_name, state, pg_size_pretty(pg_wal_lsn_diff(sent_lsn, replay_lsn)) AS bytes_lag, write_lag, flush_lag, replay_lag FROM pg_stat_replication;"
```

`bytes_lag = 0 bytes` significa que la réplica ya reprodujo todo el WAL que el
primario le envió. `write_lag`, `flush_lag` y `replay_lag` pueden aparecer
`NULL` en una replicación asíncrona cuando no hay suficiente actividad reciente;
por eso el LSN es la referencia principal.

En cada réplica también se puede revisar el LSN recibido y aplicado:

```bash
docker exec pg-replica1 psql -U eafit -d taller_cluster -c \
  "SELECT pg_last_wal_receive_lsn() AS recibido, pg_last_wal_replay_lsn() AS aplicado, now() - pg_last_xact_replay_timestamp() AS tiempo_desde_ultima_aplicacion;"
docker exec pg-replica2 psql -U eafit -d taller_cluster -c \
  "SELECT pg_last_wal_receive_lsn() AS recibido, pg_last_wal_replay_lsn() AS aplicado, now() - pg_last_xact_replay_timestamp() AS tiempo_desde_ultima_aplicacion;"
```

Para medir la latencia de una escritura concreta, escriba una fila con la
hora del primario y consulte repetidamente esa misma fila en cada réplica:

```bash
docker exec pg-primary psql -U eafit -d taller_cluster -c \
  "CREATE TABLE IF NOT EXISTS medicion_replicacion (id bigserial PRIMARY KEY, escrito_en timestamptz NOT NULL DEFAULT clock_timestamp()); INSERT INTO medicion_replicacion DEFAULT VALUES; SELECT id, escrito_en FROM medicion_replicacion ORDER BY id DESC LIMIT 1;"
```

Guarde el `id` devuelto y reemplácelo en estas consultas:

```bash
docker exec pg-replica1 psql -U eafit -d taller_cluster -c \
  "SELECT id, escrito_en, clock_timestamp() - escrito_en AS latencia_replica1 FROM medicion_replicacion WHERE id = <ID>;"
docker exec pg-replica2 psql -U eafit -d taller_cluster -c \
  "SELECT id, escrito_en, clock_timestamp() - escrito_en AS latencia_replica2 FROM medicion_replicacion WHERE id = <ID>;"
```

La latencia total hasta que **ambas** réplicas tienen la fila es el tiempo de
la réplica más lenta, es decir, `max(latencia_replica1, latencia_replica2)`, no
la suma. No se escribe directamente en cada réplica: están en modo standby y
solo aceptan lecturas. Si se suman los tiempos de dos comandos ejecutados uno
después del otro, también se está sumando el tiempo de las consultas y de la
red, no solo la replicación.

### 4.6 Validar que los 3 nodos están arriba y sincronizados

**Desde el primario:**
```bash
docker exec -it pg-primary psql -U eafit -d taller_cluster -f /dev/stdin <<'SQL'
SELECT client_addr, state, sync_state, replay_lsn FROM pg_stat_replication;
SELECT pg_current_wal_lsn();
SQL
```
Deben aparecer **2 filas** (una por réplica), `state = streaming`.

**Desde cada réplica:**
```bash
docker exec -it pg-replica1 psql -U eafit -d taller_cluster -c "SELECT pg_is_in_recovery();"
docker exec -it pg-replica1 psql -U eafit -d taller_cluster -c "SELECT now() - pg_last_xact_replay_timestamp() AS lag;"
```
`pg_is_in_recovery()` debe devolver `t` (true) — confirma que el nodo es standby. El `lag` debería estar en milisegundos.

**Prueba de sincronización real:** insertar en el primario y confirmar que aparece en ambas réplicas.
```bash
docker exec -it pg-primary psql -U eafit -d taller_cluster -c \
  "CREATE TABLE IF NOT EXISTS prueba_sync (id serial, creado timestamp default now()); INSERT INTO prueba_sync DEFAULT VALUES;"

sleep 1

docker exec -it pg-replica1 psql -U eafit -d taller_cluster -c "SELECT * FROM prueba_sync;"
docker exec -it pg-replica2 psql -U eafit -d taller_cluster -c "SELECT * FROM prueba_sync;"
```

Todas las consultas de esta sección también están reunidas en `verificacion.sql`.

### 4.7 "Tumbar" temporalmente un nodo

```bash
docker stop pg-replica1
```

**Qué observar:**
- En el primario, `SELECT * FROM pg_stat_replication;` ahora muestra **1 sola fila** (solo `pg-replica2` sigue conectada).
- El primario **sigue aceptando escrituras normalmente** — la replicación es asíncrona por defecto (`synchronous_standby_names` vacío), así que la caída de una réplica no bloquea al primario.
- `pg-replica2` sigue recibiendo y aplicando WAL sin ningún problema.

Reintegrar el nodo:
```bash
docker start pg-replica1
```
Al volver a levantar, la réplica retoma el streaming desde donde se quedó (gracias al *replication slot*, el primario retuvo el WAL necesario) y se pondrá al día. Verifiquen de nuevo `pg_stat_replication` en el primario: debe reaparecer la fila de `pg-replica1`, con el lag bajando hasta 0.

**Punto de discusión (modelo básico vs. alta disponibilidad real):** si en vez de tumbar una réplica se tumba el **primario** (`docker stop pg-primary`), ninguna réplica se promueve sola — eso es exactamente la limitación del modelo básico de streaming replication. Para promover manualmente una réplica a primario:
```bash
docker exec -it pg-replica2 psql -U eafit -d taller_cluster -c "SELECT pg_promote();"
```
Esto rompe la topología original (esa réplica deja de ser standby) — es material para comparar con herramientas de HA con failover automático como **Patroni**, **repmgr** o **Pgpool-II**, que agregan el "elección de líder" que PostgreSQL no trae de fábrica.

### 4.8 Variante: cada equipo en un computador distinto

Si en vez de un solo Docker Desktop, cada equipo trabaja en su propio portátil dentro de la misma red (salón/wifi):
1. El equipo del primario identifica su IP local (`ipconfig` / `ifconfig`) y se asegura de que el firewall permita conexiones entrantes al puerto `5543`.
2. En el `docker-compose.yml` de cada réplica, cambiar `PRIMARY_HOST: pg-primary` por la **IP real** del portátil del primario, y usar `network_mode: host` o mapear puertos explícitamente en vez de la red interna `pgcluster` (que solo funciona entre contenedores de un mismo Docker Engine).
3. En `pg_hba.conf` del primario, la línea ya generada (`host replication replicador 0.0.0.0/0 scram-sha-256`) acepta conexiones desde cualquier IP, así que no hace falta tocarla — solo el firewall/red del sistema operativo.

Es más frágil de coordinar en vivo (depende del wifi del salón), por eso se recomienda la variante de un solo Docker Desktop para la sesión de hoy, y dejar esta variante como reto adicional.

### 4.9 Apagar todo al terminar

```bash
docker compose down          # detiene y elimina contenedores, conserva los volúmenes
docker compose down -v       # además elimina los volúmenes (borra los datos)
```

(Mismo comando aplica en `01-standalone/` para esa instancia.)

---

## Resumen de comandos clave

| Acción | Comando |
|---|---|
| Ver contenedores activos | `docker ps` |
| Logs de un contenedor | `docker logs -f pg-primary` |
| Entrar por psql | `docker exec -it <contenedor> psql -U eafit -d <db>` |
| Correr un .sql desde el host | `docker exec -i <contenedor> psql -U eafit -d <db> < archivo.sql` |
| Ver plan de ejecución | `EXPLAIN (ANALYZE, BUFFERS) <consulta>;` |
| Medir tiempo de cada sentencia en psql | `\timing on` |
| Tamaño de una tabla/índice | `SELECT pg_size_pretty(pg_relation_size('nombre'));` |
