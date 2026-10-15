-- =========================================================
-- 02_generar_datos.sql
-- Generación masiva de datos con generate_series() nativo
-- de Postgres. Es MUCHO más rápido que insertar fila a fila
-- desde un script externo (Python/Java) porque no hay
-- round-trips de red: todo corre dentro del motor.
--
-- Volúmenes:
--   clientes   : 1.000.000
--   inventario :   550.000
--   pedidos    : 1.300.000
-- =========================================================

\timing on

-- ---------- CLIENTES (1,000,000) ----------
INSERT INTO clientes (cliente_id, nombres, apellidos, email, telefono, ciudad, pais, fecha_registro, activo)
SELECT
    i,
    (ARRAY['Juan','Maria','Carlos','Ana','Luis','Sofia','Andres','Laura','Diego','Camila',
           'Jorge','Valentina','Mateo','Isabella','Santiago','Daniela','Felipe','Gabriela','Ricardo','Paula'])[1 + (i % 20)],
    (ARRAY['Gomez','Rodriguez','Perez','Lopez','Martinez','Garcia','Hernandez','Diaz','Torres','Ramirez',
           'Vargas','Castro','Ortiz','Rojas','Moreno','Suarez','Jimenez','Munoz','Cardenas','Restrepo'])[1 + (i % 20)],
    'cliente' || i || '@correo' || (1 + (i % 50)) || '.com',
    '3' || lpad((100000000 + (i % 899999999))::text, 9, '0'),
    (ARRAY['Medellin','Bogota','Cali','Barranquilla','Cartagena','Bucaramanga','Pereira','Manizales','Ibague','Cucuta'])[1 + (i % 10)],
    'Colombia',
    date '2015-01-01' + ((i % 4000) || ' days')::interval,
    (i % 10) <> 0
FROM generate_series(1, 1000000) AS s(i);

-- ---------- INVENTARIO (550,000 SKU) ----------
INSERT INTO inventario (sku_id, sku_code, nombre_producto, categoria, precio, stock, bodega, fecha_actualizacion)
SELECT
    i,
    'SKU-' || lpad(i::text, 8, '0'),
    'Producto ' || i,
    (ARRAY['Electrodomesticos','Ropa','Alimentos','Tecnologia','Hogar','Deportes','Salud','Juguetes','Belleza','Ferreteria'])[1 + (i % 10)],
    round((random()*490 + 10)::numeric, 2),
    (random()*1000)::int,
    (ARRAY['Bodega-Norte','Bodega-Sur','Bodega-Centro','Bodega-Oriente'])[1 + (i % 4)],
    now() - ((i % 365) || ' days')::interval
FROM generate_series(1, 550000) AS s(i);

-- ---------- PEDIDOS (1,300,000) ----------
-- cliente_id y sku_id se generan aleatoriamente dentro de los
-- rangos ya cargados arriba, para simular referencias reales.
INSERT INTO pedidos (pedido_id, cliente_id, sku_id, fecha_pedido, cantidad, valor_total, estado, ciudad_envio)
SELECT
    i,
    1 + floor(random()*1000000)::bigint,
    1 + floor(random()*550000)::bigint,
    timestamp '2022-01-01' + (floor(random()*1460) || ' days')::interval
             + (floor(random()*86400) || ' seconds')::interval,
    1 + (random()*5)::int,
    round((random()*950 + 50)::numeric, 2),
    (ARRAY['Pendiente','Enviado','Entregado','Cancelado','Devuelto'])[1 + floor(random()*5)::int],
    (ARRAY['Medellin','Bogota','Cali','Barranquilla','Cartagena','Bucaramanga','Pereira','Manizales','Ibague','Cucuta'])[1 + floor(random()*10)::int]
FROM generate_series(1, 1300000) AS s(i);

-- Estadísticas para que el planner tenga información real
-- (sin esto, EXPLAIN puede mostrar estimaciones erróneas)
ANALYZE clientes;
ANALYZE inventario;
ANALYZE pedidos;

SELECT 'clientes'   AS tabla, count(*) FROM clientes
UNION ALL
SELECT 'inventario', count(*) FROM inventario
UNION ALL
SELECT 'pedidos',    count(*) FROM pedidos;
