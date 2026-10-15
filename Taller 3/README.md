## Q1 — Proveedor + contrato actual

Necesitamos consultar:

> ¿Cuál es el contrato vigente de este proveedor en determinada fecha?

La consulta será conceptualmente:

```sql
SELECT
    p.id,
    p.nit,
    p.nombre,
    c.id AS contrato_id,
    c.fecha_inicio,
    c.fecha_fin,
    c.estado
FROM proveedores.proveedor p
JOIN proveedores.contrato_suministro c
    ON c.proveedor_id = p.id
WHERE p.id = 12345
  AND DATE '2026-09-18'
      BETWEEN c.fecha_inicio AND c.fecha_fin;
```

**Ojo:** este JOIN está permitido porque ambas tablas están dentro de `proveedores`.

Nuestro índice:

```sql
CREATE INDEX idx_contrato_proveedor
ON proveedores.contrato_suministro(proveedor_id);
```

ayudará aquí.

---

# Q2 — 20 SKU negociados

Necesitamos:

> Obtener 20 SKU negociados para un proveedor.

Por ejemplo:

```sql
SELECT
    ps.sku_id,
    s.codigo,
    s.nombre,
    ps.precio_negociado
FROM catalogo.proveedor_sku ps
JOIN catalogo.sku s
    ON s.id = ps.sku_id
WHERE ps.proveedor_id = 12345
  AND ps.estado = 'ACTIVO'
ORDER BY ps.sku_id
LIMIT 20;
```

También es un JOIN **interno al schema `catalogo`**, así que está bien.

Nuestro índice:

```sql
CREATE INDEX idx_proveedor_sku_proveedor
ON catalogo.proveedor_sku(proveedor_id);
```

será importante.

---

# Q3 — Franjas disponibles de CEDI

La consulta busca:

> Franjas de descargue disponibles para un CEDI en determinada fecha.

Por ejemplo:

```sql
SELECT
    id,
    fecha,
    hora_inicio,
    hora_fin,
    capacidad,
    reservados
FROM logistica.franja_descargue
WHERE cedi_id = 10
  AND fecha = DATE '2026-09-18'
  AND estado = 'DISPONIBLE'
  AND reservados < capacidad
ORDER BY hora_inicio;
```

Aquí el índice:

```sql
CREATE INDEX idx_franja_cedi_fecha
ON logistica.franja_descargue(cedi_id, fecha);
```

tiene bastante sentido.

---

# Q4 — OTIF + Fill Rate

Esta será probablemente nuestra consulta más pesada.

Necesitamos analizar los últimos **24 meses** y obtener métricas por proveedor/mes.

Para esto necesitamos utilizar:

```text
orden_compra
      │
      ▼
linea_orden
```

La idea será calcular:

### OTIF

Orden entregada:

```text
On Time + In Full
```

es decir, que:

```text
fecha_recepcion <= fecha_entrega
```

y la cantidad recibida sea suficiente.

### Fill Rate

Conceptualmente:

```text
cantidad_recibida / cantidad_solicitada
```

Esta consulta nos servirá especialmente para demostrar el comportamiento de una consulta analítica frente al crecimiento de:

```text
500.000 órdenes
3.000.000 líneas
```

Aquí **no quiero optimizarla todavía**.

Primero vamos a tener la consulta funcionando.

---

# Q5 — Últimas 50 órdenes del proveedor caliente

Esta es particularmente importante por la distribución Zipf.

Queremos tener un proveedor que tenga:

```text
≥ 5.000 órdenes
```

y posteriormente ejecutar:

```sql
SELECT
    id,
    numero_orden,
    proveedor_id,
    fecha_orden,
    estado,
    total
FROM ordenes.orden_compra
WHERE proveedor_id = 1
ORDER BY fecha_orden DESC
LIMIT 50;
```

Nuestro índice:

```sql
CREATE INDEX idx_orden_proveedor_fecha
ON ordenes.orden_compra(proveedor_id, fecha_orden);
```

está pensado precisamente para este patrón.

---







