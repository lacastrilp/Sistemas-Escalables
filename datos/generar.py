#!/usr/bin/env python3

import argparse
import csv
import hashlib
import math
import random
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

DEFAULT_SEED = 20260918

DEFAULT_START_DATE = date(2024, 1, 1)
DEFAULT_END_DATE = date(2025, 12, 31)

# Fecha lógica de referencia del dataset.
#
# Se utiliza para construir casos borde:
# - contrato vencido ayer
# - contrato que vence hoy
#
# IMPORTANTE:
# El modelo físico usa DATE para fecha_fin, por lo que
# "hoy a las 12:00" no puede representarse exactamente.
REFERENCE_DATE = DEFAULT_END_DATE

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


# ============================================================
# UTILIDADES
# ============================================================

def crear_directorio():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def crear_csv(nombre, headers):
    path = OUTPUT_DIR / nombre

    archivo = open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    )

    writer = csv.writer(archivo)
    writer.writerow(headers)

    return archivo, writer


def fecha_aleatoria(rng, inicio, fin):
    dias = (fin - inicio).days

    return inicio + timedelta(
        days=rng.randint(0, dias)
    )


def es_dia_habil(fecha):
    return fecha.weekday() < 5


def ultimos_tres_dias_habiles_del_mes(anio, mes):
    """
    Devuelve los últimos tres días hábiles del mes.
    """

    if mes == 12:
        siguiente_mes = date(anio + 1, 1, 1)
    else:
        siguiente_mes = date(anio, mes + 1, 1)

    ultimo_dia = siguiente_mes - timedelta(days=1)

    dias = []
    actual = ultimo_dia

    while len(dias) < 3:
        if es_dia_habil(actual):
            dias.append(actual)

        actual -= timedelta(days=1)

    return set(dias)


def construir_dias_pico_mensuales(inicio, fin):
    """
    Construye el conjunto de fechas que corresponden
    a los últimos tres días hábiles de cada mes.
    """

    resultado = set()

    actual = date(inicio.year, inicio.month, 1)

    while actual <= fin:

        resultado.update(
            ultimos_tres_dias_habiles_del_mes(
                actual.year,
                actual.month
            )
        )

        if actual.month == 12:
            actual = date(
                actual.year + 1,
                1,
                1
            )
        else:
            actual = date(
                actual.year,
                actual.month + 1,
                1
            )

    return resultado


def fecha_hora_aleatoria(rng, inicio, fin):
    """
    Genera una fecha/hora respetando la estacionalidad horaria.
    """

    dias = (fin - inicio).days

    fecha = inicio + timedelta(
        days=rng.randint(0, dias)
    )

    hora = hora_operativa(rng)

    minuto = rng.randint(0, 59)
    segundo = rng.randint(0, 59)

    return datetime(
        fecha.year,
        fecha.month,
        fecha.day,
        hora,
        minuto,
        segundo
    )


def hora_operativa(rng):
    """
    Distribución aproximada:

    08:00-10:59 -> 75%
    11:00-17:59 -> 18%
    06:00-07:59 -> 5%
    00:00-05:59 -> 2%

    No se generan órdenes entre 18:00 y 23:59.
    """

    x = rng.random()

    if x < 0.75:
        return rng.randint(8, 10)

    if x < 0.93:
        return rng.randint(11, 17)

    if x < 0.98:
        return rng.randint(6, 7)

    return rng.randint(0, 5)


def fecha_hora_para_dia(rng, fecha):
    """
    Genera una hora para una fecha determinada.
    """

    hora = hora_operativa(rng)

    return datetime(
        fecha.year,
        fecha.month,
        fecha.day,
        hora,
        rng.randint(0, 59),
        rng.randint(0, 59)
    )


def precio(rng, minimo=10, maximo=100000):
    return round(
        rng.uniform(minimo, maximo),
        2
    )


def elegir_de_rango(rng, minimo, maximo):
    if maximo < minimo:
        return minimo

    return rng.randint(
        minimo,
        maximo
    )


# ============================================================
# PROVEEDORES
# ============================================================

def generar_proveedores(cantidad, rng):

    print(
        f"[1/8] Generando "
        f"{cantidad:,} proveedores..."
    )

    archivo, writer = crear_csv(
        "proveedores.csv",
        [
            "id",
            "nit",
            "nombre",
            "estado",
            "fecha_registro"
        ]
    )

    try:

        for proveedor_id in range(
            1,
            cantidad + 1
        ):

            # Reservamos un proveedor activo sin órdenes
            # cuando sea posible.
            #
            # Este proveedor se determina más adelante
            # y simplemente permanece activo.
            estado = (
                "ACTIVO"
                if rng.random() < 0.95
                else "INACTIVO"
            )

            fecha_registro = fecha_aleatoria(
                rng,
                date(2018, 1, 1),
                DEFAULT_END_DATE
            )

            writer.writerow([
                proveedor_id,
                f"NIT-{proveedor_id:09d}",
                f"Proveedor {proveedor_id:06d}",
                estado,
                fecha_registro.isoformat()
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# CONTRATOS
# ============================================================

def generar_contratos(
    cantidad,
    proveedores,
    rng
):

    print(
        f"[2/8] Generando "
        f"{cantidad:,} contratos..."
    )

    archivo, writer = crear_csv(
        "contratos.csv",
        [
            "id",
            "proveedor_id",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "limite_credito"
        ]
    )

    if cantidad < 0:
        raise ValueError(
            "La cantidad de contratos no puede ser negativa."
        )

    if cantidad > proveedores:
        print(
            "      ADVERTENCIA: hay más contratos que "
            "proveedores; se reutilizarán proveedores."
        )

    try:

        for contrato_id in range(
            1,
            cantidad + 1
        ):

            proveedor_id = (
                ((contrato_id - 1) % proveedores)
                + 1
            )

            # ------------------------------------------------
            # CASOS BORDE
            # ------------------------------------------------

            # Contrato 1:
            # Vencido ayer.
            if contrato_id == 1:

                fecha_inicio = (
                    REFERENCE_DATE
                    - timedelta(days=365)
                )

                fecha_fin = (
                    REFERENCE_DATE
                    - timedelta(days=1)
                )

                estado = "VENCIDO"

            # Contrato 2:
            # Vence hoy.
            #
            # LIMITACIÓN:
            # El modelo físico utiliza DATE.
            # No es posible almacenar "12:00".
            elif contrato_id == 2:

                fecha_inicio = (
                    REFERENCE_DATE
                    - timedelta(days=180)
                )

                fecha_fin = REFERENCE_DATE

                estado = "ACTIVO"

            # Contratos normales.
            else:

                fecha_inicio = date(
                    2024,
                    1,
                    1
                )

                fecha_fin = date(
                    2025,
                    12,
                    31
                )

                estado = "ACTIVO"

            writer.writerow([
                contrato_id,
                proveedor_id,
                fecha_inicio.isoformat(),
                fecha_fin.isoformat(),
                estado,
                precio(
                    rng,
                    10000,
                    1000000
                )
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# SKU
# ============================================================

def generar_skus(cantidad, rng):

    print(
        f"[3/8] Generando "
        f"{cantidad:,} SKU..."
    )

    archivo, writer = crear_csv(
        "skus.csv",
        [
            "id",
            "codigo",
            "nombre",
            "categoria",
            "precio_base",
            "estado"
        ]
    )

    categorias = [
        "ALIMENTOS",
        "BEBIDAS",
        "ASEO",
        "HOGAR",
        "ELECTRONICA",
        "PAPELERIA",
        "TEXTIL",
        "FERRETERIA"
    ]

    try:

        for sku_id in range(
            1,
            cantidad + 1
        ):

            writer.writerow([
                sku_id,
                f"SKU-{sku_id:08d}",
                f"Producto {sku_id:08d}",
                categorias[
                    (sku_id - 1)
                    % len(categorias)
                ],
                precio(
                    rng,
                    1,
                    500000
                ),
                "ACTIVO"
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# RELACIÓN PROVEEDOR-SKU
# ============================================================

def generar_proveedor_sku(
    proveedores,
    skus,
    rng
):

    print(
        "[4/8] Generando catálogo negociado..."
    )

    archivo, writer = crear_csv(
        "proveedor_sku.csv",
        [
            "id",
            "proveedor_id",
            "sku_id",
            "precio_negociado",
            "fecha_inicio",
            "fecha_fin",
            "estado"
        ]
    )

    relacion_id = 1

    # Guardamos en memoria los SKU negociados
    # para poder generar posteriormente líneas
    # coherentes con el proveedor.
    catalogo_por_proveedor = defaultdict(set)

    try:

        for proveedor_id in range(
            1,
            proveedores + 1
        ):

            cantidad_skus = rng.randint(
                5,
                min(50, skus)
            )

            sku_ids = rng.sample(
                range(1, skus + 1),
                cantidad_skus
            )

            for sku_id in sku_ids:

                catalogo_por_proveedor[
                    proveedor_id
                ].add(sku_id)

                writer.writerow([
                    relacion_id,
                    proveedor_id,
                    sku_id,
                    precio(
                        rng,
                        1,
                        450000
                    ),
                    "2024-01-01",
                    "2025-12-31",
                    "ACTIVO"
                ])

                relacion_id += 1

    finally:
        archivo.close()

    print(
        f"      OK "
        f"({relacion_id - 1:,} relaciones)"
    )

    return catalogo_por_proveedor


# ============================================================
# CEDI
# ============================================================

def generar_cedis(rng):

    print("[5/8] Generando CEDI...")

    cantidad_cedis = 10

    archivo, writer = crear_csv(
        "cedi.csv",
        [
            "id",
            "codigo",
            "nombre",
            "ciudad",
            "capacidad_diaria",
            "estado"
        ]
    )

    ciudades = [
        "Bogota",
        "Medellin",
        "Cali",
        "Barranquilla",
        "Cartagena",
        "Bucaramanga",
        "Pereira",
        "Manizales",
        "Ibague",
        "Villavicencio"
    ]

    try:

        for cedi_id in range(
            1,
            cantidad_cedis + 1
        ):

            writer.writerow([
                cedi_id,
                f"CEDI-{cedi_id:03d}",
                f"CEDI {ciudades[cedi_id - 1]}",
                ciudades[cedi_id - 1],
                1000,
                "ACTIVO"
            ])

    finally:
        archivo.close()

    print("      OK")

    return cantidad_cedis


# ============================================================
# FRANJAS
# ============================================================

def generar_franjas(
    cantidad,
    cedis,
    rng
):

    print(
        f"[6/8] Generando "
        f"{cantidad:,} franjas..."
    )

    archivo, writer = crear_csv(
        "franjas.csv",
        [
            "id",
            "cedi_id",
            "fecha",
            "hora_inicio",
            "hora_fin",
            "capacidad",
            "reservados",
            "estado"
        ]
    )

    inicio = DEFAULT_START_DATE

    # 10 franjas de dos horas por CEDI/día.
    franjas_por_dia = cedis * 10

    try:

        for franja_id in range(
            1,
            cantidad + 1
        ):

            indice = franja_id - 1

            cedi_id = (
                (indice % cedis) + 1
            )

            fecha = (
                inicio
                + timedelta(
                    days=indice // franjas_por_dia
                )
            )

            bloque = (
                (indice // cedis) % 10
            )

            hora_inicio = (
                6 + bloque * 2
            )

            # Evitamos que el formato de TIME
            # llegue a 24:00.
            #
            # El bloque 9 será:
            # 00:00 - 02:00 del día siguiente.
            if hora_inicio >= 24:

                hora_inicio_real = (
                    hora_inicio - 24
                )

            else:

                hora_inicio_real = hora_inicio

            hora_fin_real = (
                hora_inicio_real + 2
            )

            capacidad = 10

            reservados = rng.randint(
                0,
                capacidad
            )

            if reservados >= capacidad:
                estado = "LLENA"

            else:
                estado = "DISPONIBLE"

            writer.writerow([
                franja_id,
                cedi_id,
                fecha.isoformat(),
                f"{hora_inicio_real:02d}:00:00",
                f"{hora_fin_real:02d}:00:00",
                capacidad,
                reservados,
                estado
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# ZIPF
# ============================================================

def crear_distribucion_zipf(
    cantidad,
    s=0.95
):

    if cantidad <= 0:
        return []

    pesos = [
        1 / (i ** s)
        for i in range(
            1,
            cantidad + 1
        )
    ]

    total = sum(pesos)

    acumuladas = []

    acumulado = 0.0

    for peso in pesos:

        acumulado += (
            peso / total
        )

        acumuladas.append(
            acumulado
        )

    # Evita errores de precisión
    # en el último elemento.
    acumuladas[-1] = 1.0

    return acumuladas


def seleccionar_zipf(
    rng,
    acumuladas
):

    x = rng.random()

    izquierda = 0
    derecha = len(
        acumuladas
    ) - 1

    while izquierda < derecha:

        medio = (
            izquierda + derecha
        ) // 2

        if acumuladas[medio] >= x:
            derecha = medio

        else:
            izquierda = (
                medio + 1
            )

    return izquierda + 1


# ============================================================
# FECHAS DE ÓRDENES
# ============================================================

def construir_fechas_ordenes(
    cantidad,
    rng,
    inicio,
    fin
):
    """
    Genera fechas para las órdenes.

    25%:
        últimos tres días hábiles de cada mes.

    75%:
        resto de fechas del periodo.

    La selección se hace por orden, por lo que el porcentaje
    global se mantiene aproximadamente en 25%.
    """

    dias_pico = construir_dias_pico_mensuales(
        inicio,
        fin
    )

    todos_los_dias = []

    dia = inicio

    while dia <= fin:

        todos_los_dias.append(dia)

        dia += timedelta(
            days=1
        )

    dias_normales = [
        d
        for d in todos_los_dias
        if d not in dias_pico
    ]

    if not dias_pico:
        raise RuntimeError(
            "No se encontraron días pico mensuales."
        )

    if not dias_normales:
        raise RuntimeError(
            "No existen días normales para "
            "la estacionalidad mensual."
        )

    cantidad_pico = round(
        cantidad * 0.25
    )

    cantidad_normal = (
        cantidad - cantidad_pico
    )

    fechas = []

    # 25% pico
    for _ in range(cantidad_pico):

        fecha = rng.choice(
            list(dias_pico)
        )

        fechas.append(
            fecha
        )

    # 75% normal
    for _ in range(cantidad_normal):

        fecha = rng.choice(
            dias_normales
        )

        fechas.append(
            fecha
        )

    # Mezclamos para no dejar todos
    # los pedidos pico al principio.
    rng.shuffle(fechas)

    return fechas


# ============================================================
# ORDENES
# ============================================================

def generar_ordenes(
    cantidad,
    proveedores,
    cedis,
    franjas,
    rng,
    s_zipf=0.95
):

    print(
        f"[7/8] Generando "
        f"{cantidad:,} órdenes..."
    )

    archivo, writer = crear_csv(
        "ordenes.csv",
        [
            "id",
            "numero_orden",
            "proveedor_id",
            "fecha_orden",
            "estado",
            "cedi_id",
            "franja_id",
            "total",
            "fecha_entrega",
            "fecha_confirmacion",
            "idempotency_key"
        ]
    )

    if cantidad <= 0:
        archivo.close()
        return {}

    if proveedores <= 0:
        archivo.close()
        raise ValueError(
            "Debe existir al menos un proveedor."
        )

    if cedis <= 0:
        archivo.close()
        raise ValueError(
            "Debe existir al menos un CEDI."
        )

    if franjas <= 0:
        archivo.close()
        raise ValueError(
            "Debe existir al menos una franja."
        )

    zipf = crear_distribucion_zipf(
        proveedores,
        s_zipf
    )

    fechas = construir_fechas_ordenes(
        cantidad,
        rng,
        DEFAULT_START_DATE,
        DEFAULT_END_DATE
    )

    ordenes_por_proveedor = Counter()

    try:

        for orden_id in range(
            1,
            cantidad + 1
        ):

            # -----------------------------------------------
            # PROVEEDOR
            # -----------------------------------------------

            proveedor_id = seleccionar_zipf(
                rng,
                zipf
            )

            ordenes_por_proveedor[
                proveedor_id
            ] += 1

            # -----------------------------------------------
            # FECHA
            # -----------------------------------------------

            fecha_dia = fechas[
                orden_id - 1
            ]

            fecha_orden = fecha_hora_para_dia(
                rng,
                fecha_dia
            )

            # -----------------------------------------------
            # CEDI
            # -----------------------------------------------

            cedi_id = rng.randint(
                1,
                cedis
            )

            # -----------------------------------------------
            # FRANJA
            # -----------------------------------------------

            franja_id = rng.randint(
                1,
                franjas
            )

            # -----------------------------------------------
            # ESTADO
            # -----------------------------------------------

            estado = rng.choices(
                [
                    "PENDIENTE",
                    "CONFIRMADA",
                    "ENTREGADA",
                    "CANCELADA"
                ],
                weights=[
                    5,
                    20,
                    70,
                    5
                ]
            )[0]

            # -----------------------------------------------
            # FECHA DE CONFIRMACIÓN
            # -----------------------------------------------

            if estado in (
                "CONFIRMADA",
                "ENTREGADA"
            ):

                fecha_confirmacion = (
                    fecha_orden
                    + timedelta(
                        hours=rng.randint(
                            1,
                            24
                        )
                    )
                )

            else:

                fecha_confirmacion = None

            # -----------------------------------------------
            # FECHA DE ENTREGA
            # -----------------------------------------------

            if estado == "ENTREGADA":

                fecha_entrega = (
                    fecha_orden.date()
                    + timedelta(
                        days=rng.randint(
                            1,
                            10
                        )
                    )
                )

            else:

                fecha_entrega = None

            # -----------------------------------------------
            # TOTAL
            # -----------------------------------------------

            total = precio(
                rng,
                100,
                5000000
            )

            # -----------------------------------------------
            # IDEMPOTENCY KEY
            # -----------------------------------------------

            idempotency_key = (
                f"IDEMP-{orden_id:012d}"
            )

            writer.writerow([
                orden_id,
                f"OC-{orden_id:012d}",
                proveedor_id,
                fecha_orden.isoformat(
                    sep=" "
                ),
                estado,
                cedi_id,
                franja_id,
                total,
                (
                    fecha_entrega.isoformat()
                    if fecha_entrega
                    else ""
                ),
                (
                    fecha_confirmacion.isoformat(
                        sep=" "
                    )
                    if fecha_confirmacion
                    else ""
                ),
                idempotency_key
            ])

    finally:
        archivo.close()

    print("      OK")

    return ordenes_por_proveedor


# ============================================================
# LINEAS
# ============================================================

def generar_lineas(
    cantidad_ordenes,
    cantidad_lineas,
    cantidad_skus,
    rng,
    catalogo_por_proveedor,
    ordenes_por_proveedor,
    proveedores
):

    print(
        f"[8/8] Generando "
        f"{cantidad_lineas:,} líneas..."
    )

    archivo, writer = crear_csv(
        "lineas_orden.csv",
        [
            "id",
            "orden_id",
            "numero_linea",
            "sku_id",
            "cantidad",
            "precio_unitario",
            "cantidad_recibida",
            "fecha_recepcion"
        ]
    )

    if cantidad_ordenes <= 0:
        archivo.close()
        return

    if cantidad_skus <= 0:
        archivo.close()
        raise ValueError(
            "Debe existir al menos un SKU."
        )

    if cantidad_lineas < cantidad_ordenes:
        archivo.close()
        raise ValueError(
            "Debe haber al menos una línea "
            "por orden."
        )

    # --------------------------------------------------------
    # Ordenes que tendrán exactamente 300 líneas.
    #
    # El caso borde exige una orden con 300 líneas.
    # --------------------------------------------------------

    orden_hot_lineas = None

    if cantidad_ordenes >= 1 and cantidad_lineas >= 300:

        orden_hot_lineas = 1

    # --------------------------------------------------------
    # Distribución base
    # --------------------------------------------------------

    lineas_por_orden = {
        orden_id: 1
        for orden_id in range(
            1,
            cantidad_ordenes + 1
        )
    }

    restantes = (
        cantidad_lineas
        - cantidad_ordenes
    )

    # Reservamos 299 líneas adicionales
    # para que la orden 1 tenga 300.
    if orden_hot_lineas is not None:

        adicionales_hot = 299

        if restantes >= adicionales_hot:

            lineas_por_orden[
                orden_hot_lineas
            ] = 300

            restantes -= adicionales_hot

    # --------------------------------------------------------
    # Distribuimos el resto de líneas.
    # --------------------------------------------------------

    ordenes_disponibles = [
        orden_id
        for orden_id in range(
            1,
            cantidad_ordenes + 1
        )
        if orden_id != orden_hot_lineas
    ]

    if ordenes_disponibles:

        for _ in range(restantes):

            orden_id = rng.choice(
                ordenes_disponibles
            )

            lineas_por_orden[
                orden_id
            ] += 1

    elif restantes > 0:

        lineas_por_orden[
            1
        ] += restantes

    # --------------------------------------------------------
    # Hot SKU
    # --------------------------------------------------------

    cantidad_hot = max(
        1,
        math.ceil(
            cantidad_skus * 0.10
        )
    )

    cantidad_lineas_hot = round(
        cantidad_lineas * 0.60
    )

    contador_lineas = 0
    linea_id = 1

    # --------------------------------------------------------
    # Necesitamos reconstruir orden -> proveedor.
    #
    # El CSV de órdenes ya fue escrito, así que utilizamos
    # el archivo como fuente para no duplicar lógica.
    # --------------------------------------------------------

    orden_proveedor = {}

    ordenes_path = (
        OUTPUT_DIR / "ordenes.csv"
    )

    with open(
        ordenes_path,
        "r",
        encoding="utf-8",
        newline=""
    ) as archivo_ordenes:

        lector = csv.DictReader(
            archivo_ordenes
        )

        for fila in lector:

            orden_proveedor[
                int(fila["id"])
            ] = int(
                fila["proveedor_id"]
            )

    # --------------------------------------------------------
    # Determinar proveedores especiales
    # --------------------------------------------------------

    proveedor_sin_catalogo = None

    if proveedores > 1:

        # Elegimos el último proveedor.
        proveedor_sin_catalogo = proveedores

    # --------------------------------------------------------
    # Orden especial para SKU fuera de catálogo.
    #
    # Se intentará que la primera línea de la primera orden
    # utilice un SKU que NO pertenezca al catálogo negociado
    # del proveedor.
    # --------------------------------------------------------

    orden_sku_fuera_catalogo = None

    for orden_id in range(
        1,
        cantidad_ordenes + 1
    ):

        proveedor_id = orden_proveedor[
            orden_id
        ]

        catalogo = catalogo_por_proveedor.get(
            proveedor_id,
            set()
        )

        if len(catalogo) < cantidad_skus:

            orden_sku_fuera_catalogo = orden_id
            break

    try:

        for orden_id in range(
            1,
            cantidad_ordenes + 1
        ):

            numero_lineas = lineas_por_orden[
                orden_id
            ]

            proveedor_id = orden_proveedor[
                orden_id
            ]

            catalogo_proveedor = (
                catalogo_por_proveedor.get(
                    proveedor_id,
                    set()
                )
            )

            catalogo_lista = list(
                catalogo_proveedor
            )

            for numero_linea in range(
                1,
                numero_lineas + 1
            ):

                # --------------------------------------------
                # SKU HOT
                # --------------------------------------------

                if (
                    contador_lineas
                    < cantidad_lineas_hot
                ):

                    sku_id = rng.randint(
                        1,
                        cantidad_hot
                    )

                else:

                    if cantidad_skus > cantidad_hot:

                        sku_id = rng.randint(
                            cantidad_hot + 1,
                            cantidad_skus
                        )

                    else:

                        sku_id = rng.randint(
                            1,
                            cantidad_skus
                        )

                # --------------------------------------------
                # Caso borde:
                # SKU fuera del catálogo negociado.
                # --------------------------------------------

                if (
                    orden_id
                    == orden_sku_fuera_catalogo
                    and numero_linea == 1
                ):

                    catalogo_set = (
                        catalogo_proveedor
                    )

                    candidatos = [
                        sku
                        for sku in range(
                            1,
                            cantidad_skus + 1
                        )
                        if sku not in catalogo_set
                    ]

                    if candidatos:

                        sku_id = rng.choice(
                            candidatos
                        )

                # --------------------------------------------
                # Si queremos que las líneas normales
                # respeten el catálogo, elegimos un SKU
                # negociado.
                #
                # EXCEPCIÓN:
                # mantenemos la concentración hot SKU.
                # --------------------------------------------

                if (
                    numero_linea != 1
                    or orden_id
                    != orden_sku_fuera_catalogo
                ):

                    if catalogo_lista:

                        # 60% hot SKU si está negociado.
                        hot_candidatos = [
                            sku
                            for sku in catalogo_lista
                            if sku <= cantidad_hot
                        ]

                        if (
                            hot_candidatos
                            and contador_lineas
                            < cantidad_lineas_hot
                        ):

                            sku_id = rng.choice(
                                hot_candidatos
                            )

                        else:

                            sku_id = rng.choice(
                                catalogo_lista
                            )

                contador_lineas += 1

                cantidad = rng.randint(
                    1,
                    100
                )

                cantidad_recibida = rng.randint(
                    0,
                    cantidad
                )

                writer.writerow([
                    linea_id,
                    orden_id,
                    numero_linea,
                    sku_id,
                    cantidad,
                    precio(
                        rng,
                        1,
                        500000
                    ),
                    cantidad_recibida,
                    ""
                ])

                linea_id += 1

    finally:
        archivo.close()

    print("      OK")

    if orden_hot_lineas is not None:

        print(
            f"      Caso borde: "
            f"orden {orden_hot_lineas:,} "
            f"con 300 líneas"
        )

    if orden_sku_fuera_catalogo is not None:

        print(
            f"      Caso borde: "
            f"orden {orden_sku_fuera_catalogo:,} "
            f"con SKU fuera de catálogo"
        )


# ============================================================
# EVENTOS
# ============================================================

def generar_eventos(
    cantidad,
    ordenes,
    rng
):

    print(
        f"[9/9] Generando "
        f"{cantidad:,} eventos..."
    )

    archivo, writer = crear_csv(
        "eventos.csv",
        [
            "id",
            "orden_id",
            "tipo_evento",
            "fecha_evento",
            "payload"
        ]
    )

    tipos = [
        "ORDEN_CREADA",
        "ORDEN_CONFIRMADA",
        "ORDEN_CANCELADA",
        "ORDEN_ENTREGADA",
        "SLOT_RESERVADO",
        "VALIDACION_FISCAL"
    ]

    if ordenes <= 0:

        archivo.close()

        if cantidad > 0:
            raise ValueError(
                "No se pueden generar eventos "
                "sin órdenes."
            )

        return

    try:

        for evento_id in range(
            1,
            cantidad + 1
        ):

            orden_id = rng.randint(
                1,
                ordenes
            )

            tipo = rng.choice(
                tipos
            )

            fecha_evento = (
                datetime(
                    2024,
                    1,
                    1
                )
                + timedelta(
                    seconds=rng.randint(
                        0,
                        2 * 365 * 24 * 3600
                    )
                )
            )

            payload = (
                "{"
                f'"evento_id": {evento_id}, '
                f'"tipo": "{tipo}"'
                "}"
            )

            writer.writerow([
                evento_id,
                orden_id,
                tipo,
                fecha_evento.isoformat(
                    sep=" "
                ),
                payload
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# CHECKSUM
# ============================================================

def calcular_checksums():

    print(
        "\nCalculando checksums..."
    )

    checksum_file = (
        OUTPUT_DIR
        / "checksums.sha256"
    )

    archivos = sorted(
        p
        for p in OUTPUT_DIR.glob("*.csv")
    )

    with open(
        checksum_file,
        "w",
        encoding="utf-8"
    ) as salida:

        for path in archivos:

            sha = hashlib.sha256()

            with open(
                path,
                "rb"
            ) as archivo:

                while True:

                    bloque = archivo.read(
                        1024 * 1024
                    )

                    if not bloque:
                        break

                    sha.update(
                        bloque
                    )

            salida.write(
                f"{sha.hexdigest()}  "
                f"{path.name}\n"
            )

            print(
                f"  {path.name}: "
                f"{sha.hexdigest()}"
            )


# ============================================================
# VALIDACIONES PREVIAS
# ============================================================

def validar_argumentos(args):

    valores = {
        "proveedores": args.proveedores,
        "contratos": args.contratos,
        "skus": args.skus,
        "ordenes": args.ordenes,
        "lineas": args.lineas,
        "franjas": args.franjas,
        "eventos": args.eventos
    }

    for nombre, valor in valores.items():

        if valor < 0:

            raise ValueError(
                f"--{nombre} no puede ser negativo."
            )

    if args.proveedores == 0:
        raise ValueError(
            "--proveedores debe ser mayor que 0."
        )

    if args.skus == 0:
        raise ValueError(
            "--skus debe ser mayor que 0."
        )

    if args.ordenes == 0:

        if args.lineas > 0:
            raise ValueError(
                "No puede haber líneas sin órdenes."
            )

        if args.eventos > 0:
            raise ValueError(
                "No puede haber eventos sin órdenes."
            )

    if args.lineas < args.ordenes:

        raise ValueError(
            "Debe haber al menos una línea "
            "por orden."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generador determinista de datos "
            "para el Taller 2"
        )
    )

    parser.add_argument(
        "--proveedores",
        type=int,
        default=100000
    )

    parser.add_argument(
        "--contratos",
        type=int,
        default=10000
    )

    parser.add_argument(
        "--skus",
        type=int,
        default=200000
    )

    parser.add_argument(
        "--ordenes",
        type=int,
        default=300000
    )

    parser.add_argument(
        "--lineas",
        type=int,
        default=1500000
    )

    parser.add_argument(
        "--franjas",
        type=int,
        default=90000
    )

    parser.add_argument(
        "--eventos",
        type=int,
        default=500000
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED
    )

    parser.add_argument(
        "--zipf-s",
        type=float,
        default=0.95
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # VALIDACIÓN
    # --------------------------------------------------------

    validar_argumentos(args)

    crear_directorio()

    rng = random.Random(
        args.seed
    )

    print(
        "=" * 70
    )

    print(
        "GENERADOR DE DATOS - TALLER 2"
    )

    print(
        "=" * 70
    )

    print(
        f"Seed:       {args.seed}"
    )

    print(
        f"Zipf s:     {args.zipf_s}"
    )

    print(
        f"Inicio:     {DEFAULT_START_DATE}"
    )

    print(
        f"Fin:        {DEFAULT_END_DATE}"
    )

    print(
        f"Output:     {OUTPUT_DIR}"
    )

    print()

    # --------------------------------------------------------
    # 1. PROVEEDORES
    # --------------------------------------------------------

    generar_proveedores(
        args.proveedores,
        rng
    )

    # --------------------------------------------------------
    # 2. CONTRATOS
    # --------------------------------------------------------

    generar_contratos(
        args.contratos,
        args.proveedores,
        rng
    )

    # --------------------------------------------------------
    # 3. SKU
    # --------------------------------------------------------

    generar_skus(
        args.skus,
        rng
    )

    # --------------------------------------------------------
    # 4. PROVEEDOR-SKU
    # --------------------------------------------------------

    catalogo_por_proveedor = (
        generar_proveedor_sku(
            args.proveedores,
            args.skus,
            rng
        )
    )

    # --------------------------------------------------------
    # 5. CEDI
    # --------------------------------------------------------

    cantidad_cedis = generar_cedis(
        rng
    )

    # --------------------------------------------------------
    # 6. FRANJAS
    # --------------------------------------------------------

    generar_franjas(
        args.franjas,
        cantidad_cedis,
        rng
    )

    # --------------------------------------------------------
    # 7. ORDENES
    # --------------------------------------------------------

    ordenes_por_proveedor = (
        generar_ordenes(
            args.ordenes,
            args.proveedores,
            cantidad_cedis,
            args.franjas,
            rng,
            args.zipf_s
        )
    )

    # --------------------------------------------------------
    # 8. LINEAS
    # --------------------------------------------------------

    generar_lineas(
        args.ordenes,
        args.lineas,
        args.skus,
        rng,
        catalogo_por_proveedor,
        ordenes_por_proveedor,
        args.proveedores
    )

    # --------------------------------------------------------
    # 9. EVENTOS
    # --------------------------------------------------------

    generar_eventos(
        args.eventos,
        args.ordenes,
        rng
    )

    # --------------------------------------------------------
    # CHECKSUMS
    # --------------------------------------------------------

    calcular_checksums()

    print()

    print(
        "=" * 70
    )

    print(
        "GENERACIÓN COMPLETADA"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()