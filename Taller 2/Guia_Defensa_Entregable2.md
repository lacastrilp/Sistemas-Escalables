# Guía Magistral: Cómo Entender, Desplegar y Defender el Entregable 2 como un Experto

---

## 🎯 Módulo 1: ¿De qué se trata este proyecto y este Entregable? (Explicado desde cero)

### 1. ¿Qué estamos construyendo?
Estamos diseñando la base de datos para un **Portal B2B de Retail** (como el sistema que usan Éxito, Carulla o Walmart con sus proveedores).
- Un **Retail** vende productos en tiendas físicas o virtuales.
- Los **Proveedores** (ej. Nestlé, Alpina, Nutresa o pequeños productores) venden sus productos al Retail.
- Las **Órdenes de Compra** son las solicitudes de mercancía que hace el retail a los proveedores.
- Los **CEDI** (Centros de Distribución) son las bodegas donde los camiones de los proveedores entregan la mercancía en franjas horarias específicas.

### 2. ¿Qué es el Entregable 2?
En el Entregable 1 se hizo un diseño en papel ("de juguete" con 10 filas).
En este **Entregable 2 (Escalabilidad de los Datos)** la meta es responder:
> **«¿Qué le pasa a mi base de datos PostgreSQL cuando deja de tener 10 filas de prueba y recibe 5.4 MILLONES de filas reales con picos de tráfico, proveedores gigantes y casos borde?»**

### 3. La Regla de Oro de la Arquitectura
**Nuestra base de datos tiene 4 esquemas completamente aislados (Monolito Modular):**
1. `proveedores` (Tablas: `proveedor`, `contrato_suministro`)
2. `catalogo` (Tablas: `sku`, `proveedor_sku`)
3. `logistica` (Tablas: `cedi`, `franja_descargue`)
4. `ordenes` (Tablas: `orden_compra`, `linea_orden`, `evento_auditoria`)

> [!IMPORTANT]
> **REGLA DE ORO:** Está **estrictamente prohibido hacer `JOIN` entre tablas de diferentes esquemas** (por ejemplo, `ordenes.orden_compra` con `proveedores.proveedor`). Las relaciones entre módulos solo se guardan como un número `ID` (`BIGINT`), y la aplicación es la que valida las fronteras.

---

## 🚀 Módulo 2: ¿Cómo se despliega y ejecuta? (Paso a Paso)

Si el profesor o el jurado te dice: *"Muéstreme cómo funciona desde cero en su máquina"*, haces lo siguiente:

### Requisitos previos
- Tener Docker corriendo.
- Estar parado en la terminal en la carpeta del proyecto:
  `/home/lacastrilp/Documentos/Semestre 2026-2/Aplicables/Taller 2`

### El Comando Mágico (Ejecuta TODO solo)
```bash
make datos
```

### ¿Qué hace `make datos` paso a paso por detrás?

1. **`make db-reset` (Resetear la BD):**
   Ejecuta `modelo-fisico.sql` en PostgreSQL dentro de Docker. Borra los esquemas y crea las 8 tablas vacías e índices limpios.
2. **`make generar` (Generar los datos sintéticos):**
   Ejecuta `python3 datos/generar.py`. Crea en disco los archivos CSV en la carpeta `datos/output/` con **5.44 millones de filas** y calculando checksums deterministas (`--seed 20260918`).
3. **`make cargar` (Carga ultrarrápida):**
   Ejecuta `./datos/cargar.sh`. Usa el comando `COPY` nativo de PostgreSQL para meter las 5.44 millones de filas en **99 segundos**, crea los índices secundarios y ejecuta `ANALYZE`.
4. **`make verificar` (Validación de calidad):**
   Ejecuta `python3 datos/verificar.py`. Comprueba que el dataset tenga el volumen exigido, valide los 8 casos borde y la distribución Zipf. **Debe imprimir `RESULTADO FINAL: PASS` (60/60 pruebas ok)**.
5. **`make benchmark` (Mediciones de rendimiento):**
   - `make benchmark-carga`: Mide y compara las 4 estrategias de inyección de datos.
   - `make benchmark-queries`: Ejecuta 200 iteraciones de las consultas Q1 a Q5 registrando p50, p95, p99 y extrayendo los planes `EXPLAIN ANALYZE`.

---

## 📊 Módulo 3: Entendiendo y Explicando las 5 Gráficas

Cuando muestres el informe o la presentación, así debes explicar cada gráfica:

### Gráfica 1: Distribución Zipf de Proveedores (`grafica_zipf.png`)
- **¿Qué muestra?:** En la vida real el mercado no es equitativo. Pocos proveedores venden casi todo.
- **¿Cómo leerla?:**
  - La curva de la izquierda (Log-Log) es una línea recta descendente, demostrando matemáticamente la **Ley de Potencia (Zipf $s=0.95$)**.
  - La curva de la derecha (Acumulada) muestra que **el Top 1% de proveedores (1 000 proveedores) concentra el 49.45% de todas las órdenes**.
  - El **Proveedor 1 (el superproveedor o "Proveedor Hot")** acumula él solo **18 486 órdenes y 92 430 líneas**.

---

### Gráfica 2: Estacionalidad Diaria (`grafica_estacionalidad_diaria.png`)
- **¿Qué muestra?:** La cantidad de órdenes de compra emitidas día a día durante 24 meses (2024 a 2025).
- **¿Qué destacar?:** Verás "serruchos" o picos periódicos al final de cada mes.
- **Explicación de negocio:** Los **últimos 3 días hábiles del mes concentran el 25.02% de los pedidos**. Esto ocurre porque los jefes de compras del retail cierran presupuestos y metas comerciales a fin de mes.

---

### Gráfica 3: Estacionalidad Horaria (`grafica_estacionalidad_horaria.png`)
- **¿Qué muestra?:** A qué hora del día se emiten las órdenes.
- **¿Qué destacar?:** La barra gigante azul entre las **08:00 AM y las 11:00 AM**.
- **Explicación de negocio:** El **75.07% de las órdenes** se generan en la mañana cuando abren las tiendas y los supervisores envían las listas de reabastecimiento. En la madrugada (00:00 a 05:59 AM) solo hay un 2% de tráfico (valle nocturno) y de 6:00 PM a medianoche no se emiten órdenes (0%).

---

### Gráfica 4: Comparativa de Estrategias de Inyección (`grafica_estrategias_inyeccion.png`)
- **¿Qué muestra?:** La velocidad (filas por segundo) de 4 formas distintas de meter datos a la base de datos.
- **Los Números Clave:**
  1. **`COPY` masivo:** **38 195 filas/seg** (Tarda solo 7.86 segundos en meter 300 000 filas). Es el **piso teórico**.
  2. **`INSERT` por lotes (1 000 por tx):** **16 707 filas/seg** (Tarda 17.96 s). Es 2.3 veces más lento que COPY.
  3. **Ruta Transaccional con validaciones:** **1 342 filas/seg** (Tarda 223 s). Aplica reglas de negocio antes de insertar.
  4. **`INSERT` fila por fila (Autocommit):** **801 filas/seg** (Tarda 374 s). **¡Es el antipatrón y es 47.7 veces más lento que `COPY`!**
- **¿Por qué Autocommit es tan lento?:** Porque por cada fila la base de datos se detiene a escribir físicamente en el disco (*fsync* del WAL). En cambio, `COPY` manda bloques masivos en memoria sin pausar el disco.

---

### Gráfica 5: Latencias de Consultas Q1 a Q5 (`grafica_latencias_consultas.png`)
- **¿Qué muestra?:** El tiempo que tarda PostgreSQL en responder las 5 consultas clave (Q1 a Q5), comparando un proveedor normal ("Frío") vs. el superproveedor ("Caliente").
- **Los Números Clave:**
  - **Q1 (Validar Contrato):** **0.11 ms** (Rapidísimo, sub-milisegundo).
  - **Q2 (20 SKUs negociados):** **0.37 ms**.
  - **Q3 (Franjas CEDI):** **0.12 ms**.
  - **Q5 (Paginación de 50 órdenes):** **0.78 ms**.
  - **Q4 (OTIF / Fill Rate - Analítica):**
    - En proveedor Frío: **0.47 ms**.
    - En proveedor Caliente: **129.31 ms** (¡Degradación masiva!).

---

## 🔍 Módulo 4: Las 5 Consultas (Q1 a Q5) Explicadas Fácil

### Q1 — Validar proveedor y contrato vigente
- **¿Qué hace?:** Revisa si un proveedor tiene un contrato activo en una fecha dada.
- **¿Por qué es tan rápida (0.11 ms)?:** Porque usa un índice compuesto `idx_contrato_proveedor(proveedor_id)`. Busca exactamente una fila por llave primaria/índice.

### Q2 — 20 SKUs del catálogo negociado
- **¿Qué hace?:** Busca 20 productos autorizados que un proveedor puede venderle al retail.
- **¿Por qué es rápida (0.37 ms)?:** Hace un `JOIN` **interno** dentro del esquema `catalogo` (entre `proveedor_sku` y `sku`), usando el índice `idx_proveedor_sku_proveedor(proveedor_id)`.

### Q3 — Franjas disponibles de un CEDI
- **¿Qué hace?:** Muestra los horarios disponibles de descarga en una bodega CEDI para un día específico.
- **¿Por qué es rápida (0.12 ms)?:** Filtra por `cedi_id`, `fecha` y `estado = 'DISPONIBLE'` usando el índice `idx_franja_cedi_fecha`.

### Q4 — OTIF y Fill Rate de los últimos 24 meses (Analítica Pesada)
- **¿Qué hace?:** Calcula qué porcentaje de órdenes se entregaron a tiempo y completas (OTIF) y qué porcentaje de unidades se entregaron (Fill Rate), agrupado mes a mes.
- **¿Por qué tarda 129 ms en el proveedor caliente?:** Porque para el superproveedor debe sumar y calcular indicadores sobre **18 486 órdenes y 92 430 líneas de orden**. Debe procesar casi 100 mil filas en memoria RAM.

### Q5 — Últimas 50 órdenes paginadas del proveedor hot
- **¿Qué hace?:** Muestra la lista de las 50 órdenes más recientes del proveedor 1.
- **¿Por me tarda solo 0.78 ms a pesar de tener 18 486 órdenes?:** Porque usa el índice `idx_orden_proveedor_fecha (proveedor_id, fecha_orden DESC)`. El motor recorre el índice al revés (*Index Scan Backward*), toma las primeras 50 y se detiene inmediatamente (`Limit`).

---

## ⚡ Módulo 5: El "Hallazgo Incómodo" (La clave para sacar 5.0)

Si el profesor te pregunta: *"¿Qué fue lo que descubrieron que no esperaban?"*, esta es la respuesta perfecta:

> **«Profesor, nuestro hallazgo incómodo fue descubrir que los índices secundarios NO resuelven la escalabilidad de las consultas analíticas sobre Hot Partitions (particiones calientes).»**

### La Explicación Técnica:
1. En la consulta **Q4 (OTIF)**, la base de datos **utilizó correctamente todos nuestros índices** (`idx_orden_proveedor_fecha` e `idx_linea_orden`).
2. Sin embargo, para un proveedor de la cola larga (3 órdenes) la consulta tardó **0.47 ms**, mientras que para el proveedor caliente (18 486 órdenes) tardó **129.31 ms**.
3. **¡La consulta fue 275 veces más lenta a pesar de que el índice funcionó perfectamente!**
4. **¿Por qué ocurre?:** Porque el índice ayuda a encontrar dónde están los datos, pero PostgreSQL igual tiene que leer físicamente **48 215 páginas de memoria (Buffer Hits)** y sumar **92 430 líneas de orden** en CPU.

### La Solución de Arquitectura para el Futuro:
No debemos calcular indicadores analíticos haciendo `JOIN` en vivo sobre tablas transaccionales en caliente. Para la Entrega 3 implementaremos **Vistas Materializadas** o **Tablas Proyectadas de Analítica (Patrón CQRS / Outbox)** que se actualicen asincrónicamente mediante eventos (`OrdenConfirmada`), haciendo que Q4 responda en **$< 1\text{ ms}$**.

---

## ❓ Módulo 6: Banco de Preguntas Trampa del Jurado y Respuestas Exactas

### Pregunta 1: ¿Por qué no hicieron JOIN entre `ordenes.orden_compra` y `proveedores.proveedor`?
**Respuesta:** Porque una restricción fundamental de la arquitectura es mantener **un esquema independiente por módulo sin `JOIN`s entre esquemas**. Esto nos permite en el futuro separar la base de datos en microservicios o bases de datos físicas distintas si el sistema lo requiere. Las relaciones se resuelven mediante identificadores `BIGINT` a nivel de servicio.

### Pregunta 2: ¿Cómo garantizan que dos ejecuciones generen los mismos datos exactamente?
**Respuesta:** Fijando la semilla del generador aleatorio en Python con `--seed 20260918`. Además, generamos checksums SHA-256 sobre cada archivo CSV generado. `verificar.py` comprueba que los checksums coincidan fila por fila.

### Pregunta 3: ¿Por qué crearon los índices después de hacer `COPY` y no antes?
**Respuesta:** Porque si creas los índices antes del `COPY`, PostgreSQL debe actualizar el árbol B-Tree del índice por cada una de las 5.4 millones de filas insertadas, lo que triplica o cuadruplica el tiempo de carga. Crear los índices al final en un solo paso en bloque (*Bulk Index Build*) redujo el tiempo total a 99 segundos.

### Pregunta 4: ¿Por qué ejecutaron `ANALYZE` al finalizar la carga?
**Respuesta:** Porque `COPY` no actualiza automáticamente las estadísticas del optimizador de consultas (`pg_statistic`). Sin `ANALYZE`, el planeador de PostgreSQL miente, estima mal la cantidad de filas y elige planes de ejecución pésimos (como *Sequential Scan* en lugar de *Index Scan*).

### Pregunta 5: ¿Por qué la ruta transaccional de aplicación fue más rápida que el `INSERT` fila por fila?
**Respuesta:** Aunque la ruta transaccional realiza lecturas previas para validar contratos y SKUs, agrupa toda la orden con sus líneas dentro de una única transacción explícita (`BEGIN...COMMIT`). El `INSERT` fila por fila en autocommit obliga a realizar un *fsync* síncrono al disco por cada instrucción, destruyendo el rendimiento.

### Pregunta 6: ¿Por qué Q5 (últimas 50 órdenes) es tan rápida en el proveedor gigante?
**Respuesta:** Gracias a la estrategia de indexación compuesta `(proveedor_id, fecha_orden DESC)`. El optimizador realiza un `Index Scan Backward` y aplica el operador `Limit 50`, deteniendo la lectura de disco en apenas 6 páginas de memoria (`shared hit=6`).
