#!/usr/bin/env python3

import argparse
import csv
import hashlib
import math
import random
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

DEFAULT_SEED = 20260918
DEFAULT_START_DATE = date(2024, 1, 1)
DEFAULT_END_DATE = date(2025, 12, 31)

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
    return inicio + timedelta(days=rng.randint(0, dias))


def hora_operativa(rng):
    x = rng.random()

    if x < 0.75:
        return rng.randint(8, 10)

    if x < 0.93:
        return rng.randint(11, 17)

    if x < 0.98:
        return rng.randint(6, 7)

    return rng.randint(0, 5)


def fecha_hora_aleatoria(rng, inicio, fin):
    dias = (fin - inicio).days

    fecha = inicio + timedelta(days=rng.randint(0, dias))

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


def precio(rng, minimo=10, maximo=100000):
    return round(rng.uniform(minimo, maximo), 2)


# ============================================================
# PROVEEDORES
# ============================================================

def generar_proveedores(cantidad, rng):

    print(f"[1/8] Generando {cantidad:,} proveedores...")

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
        for proveedor_id in range(1, cantidad + 1):

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

def generar_contratos(cantidad, proveedores, rng):

    print(f"[2/8] Generando {cantidad:,} contratos...")

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

    try:
        for contrato_id in range(1, cantidad + 1):

            proveedor_id = contrato_id

            if proveedor_id > proveedores:
                proveedor_id = (
                    ((contrato_id - 1) % proveedores) + 1
                )

            fecha_inicio = date(2024, 1, 1)

            fecha_fin = date(2025, 12, 31)

            writer.writerow([
                contrato_id,
                proveedor_id,
                fecha_inicio.isoformat(),
                fecha_fin.isoformat(),
                "ACTIVO",
                precio(rng, 10000, 1000000)
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# SKU
# ============================================================

def generar_skus(cantidad, rng):

    print(f"[3/8] Generando {cantidad:,} SKU...")

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
        for sku_id in range(1, cantidad + 1):

            writer.writerow([
                sku_id,
                f"SKU-{sku_id:08d}",
                f"Producto {sku_id:08d}",
                categorias[(sku_id - 1) % len(categorias)],
                precio(rng, 1, 500000),
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

    print("[4/8] Generando catálogo negociado...")

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

    try:

        # Cada proveedor recibe una cantidad pequeña
        # de SKU negociados.
        for proveedor_id in range(1, proveedores + 1):

            cantidad_skus = rng.randint(
                5,
                min(50, skus)
            )

            sku_ids = rng.sample(
                range(1, skus + 1),
                cantidad_skus
            )

            for sku_id in sku_ids:

                writer.writerow([
                    relacion_id,
                    proveedor_id,
                    sku_id,
                    precio(rng, 1, 450000),
                    "2024-01-01",
                    "2025-12-31",
                    "ACTIVO"
                ])

                relacion_id += 1

    finally:
        archivo.close()

    print(f"      OK ({relacion_id - 1:,} relaciones)")


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
        for cedi_id in range(1, cantidad_cedis + 1):

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

    return cantidad_cedis


# ============================================================
# FRANJAS
# ============================================================

def generar_franjas(cantidad, cedis, rng):

    print(f"[6/8] Generando {cantidad:,} franjas...")

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

    inicio = date(2024, 1, 1)

    try:

        for franja_id in range(1, cantidad + 1):

            cedi_id = (
                ((franja_id - 1) % cedis) + 1
            )

            fecha = inicio + timedelta(
                days=(franja_id - 1) // (cedis * 10)
            )

            bloque = (franja_id - 1) % 10

            hora_inicio = 6 + bloque * 2
            hora_fin = hora_inicio + 2

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
                f"{hora_inicio:02d}:00:00",
                f"{hora_fin:02d}:00:00",
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

def crear_distribucion_zipf(cantidad, s=0.95):

    pesos = [
        1 / (i ** s)
        for i in range(1, cantidad + 1)
    ]

    total = sum(pesos)

    acumuladas = []

    acumulado = 0.0

    for peso in pesos:
        acumulado += peso / total
        acumuladas.append(acumulado)

    return acumuladas


def seleccionar_zipf(rng, acumuladas):

    x = rng.random()

    izquierda = 0
    derecha = len(acumuladas) - 1

    while izquierda < derecha:

        medio = (izquierda + derecha) // 2

        if acumuladas[medio] >= x:
            derecha = medio
        else:
            izquierda = medio + 1

    return izquierda + 1


# ============================================================
# ORDENES
# ============================================================

def generar_ordenes(
    cantidad,
    proveedores,
    cedis,
    rng,
    s_zipf=1.15
):

    print(f"[7/8] Generando {cantidad:,} órdenes...")

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

    zipf = crear_distribucion_zipf(
        proveedores,
        s_zipf
    )

    try:

        for orden_id in range(1, cantidad + 1):

            proveedor_id = seleccionar_zipf(
                rng,
                zipf
            )

            fecha_orden = fecha_hora_aleatoria(
                rng,
                DEFAULT_START_DATE,
                DEFAULT_END_DATE
            )

            cedi_id = rng.randint(
                1,
                cedis
            )

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

            fecha_entrega = (
                fecha_orden.date()
                + timedelta(days=rng.randint(1, 10))
            )

            if estado == "ENTREGADA":
                fecha_confirmacion = (
                    fecha_orden
                    + timedelta(
                        hours=rng.randint(1, 24)
                    )
                )
            else:
                fecha_confirmacion = None

            franja_id = rng.randint(
                1,
                max(1, cantidad)
            )

            total = precio(
                rng,
                100,
                5000000
            )

            idempotency_key = (
                f"IDEMP-{orden_id:012d}"
            )

            writer.writerow([
                orden_id,
                f"OC-{orden_id:012d}",
                proveedor_id,
                fecha_orden.isoformat(sep=" "),
                estado,
                cedi_id,
                franja_id,
                total,
                fecha_entrega.isoformat(),
                (
                    fecha_confirmacion.isoformat(sep=" ")
                    if fecha_confirmacion
                    else ""
                ),
                idempotency_key
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# LINEAS
# ============================================================

def generar_lineas(
    cantidad_ordenes,
    cantidad_lineas,
    cantidad_skus,
    rng
):

    print(f"[8/8] Generando {cantidad_lineas:,} líneas...")

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

    # Distribución aproximada de líneas por orden.
    lineas_base = cantidad_lineas // cantidad_ordenes
    resto = cantidad_lineas % cantidad_ordenes

    linea_id = 1
    cantidad_hot = max(
        1,
        math.ceil(cantidad_skus * 0.10)
    )

    cantidad_lineas_hot = round(
        cantidad_lineas * 0.60
    )

    contador_lineas = 0

    try:

        for orden_id in range(1, cantidad_ordenes + 1):

            numero_lineas = lineas_base

            if orden_id <= resto:
                numero_lineas += 1

            for numero_linea in range(
                1,
                numero_lineas + 1
            ):

                if contador_lineas < cantidad_lineas_hot:
                    sku_id = rng.randint(
                        1,
                        cantidad_hot
                    )
                else:
                    sku_id = rng.randint(
                        cantidad_hot + 1,
                        cantidad_skus
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
                    precio(rng, 1, 500000),
                    cantidad_recibida,
                    ""
                ])

                linea_id += 1

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# EVENTOS
# ============================================================

def generar_eventos(
    cantidad,
    ordenes,
    rng
):

    print("Generando eventos de auditoría...")

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

    try:

        for evento_id in range(1, cantidad + 1):

            orden_id = rng.randint(
                1,
                ordenes
            )

            tipo = rng.choice(tipos)

            fecha_evento = datetime(
                2025,
                1,
                1
            ) + timedelta(
                seconds=rng.randint(
                    0,
                    365 * 24 * 3600
                )
            )

            payload = (
                '{"evento_id": '
                f'"{evento_id}", '
                f'"tipo": "{tipo}"}}'
            )

            writer.writerow([
                evento_id,
                orden_id,
                tipo,
                fecha_evento.isoformat(sep=" "),
                payload
            ])

    finally:
        archivo.close()

    print("      OK")


# ============================================================
# CHECKSUM
# ============================================================

def calcular_checksums():

    print("\nCalculando checksums...")

    checksum_file = OUTPUT_DIR / "checksums.sha256"

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

                    sha.update(bloque)

            salida.write(
                f"{sha.hexdigest()}  "
                f"{path.name}\n"
            )

            print(
                f"  {path.name}: "
                f"{sha.hexdigest()}"
            )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Generador determinista de datos "
            "para el Entregable 2"
        )
    )

    parser.add_argument(
        "--proveedores",
        type=int,
        default=100
    )

    parser.add_argument(
        "--contratos",
        type=int,
        default=20
    )

    parser.add_argument(
        "--skus",
        type=int,
        default=500
    )

    parser.add_argument(
        "--ordenes",
        type=int,
        default=1000
    )

    parser.add_argument(
        "--lineas",
        type=int,
        default=5000
    )

    parser.add_argument(
        "--franjas",
        type=int,
        default=100
    )

    parser.add_argument(
        "--eventos",
        type=int,
        default=1000
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

    crear_directorio()

    rng = random.Random(args.seed)

    print("=" * 60)
    print("GENERADOR DE DATOS - ENTREGABLE 2")
    print("=" * 60)

    print(f"Seed: {args.seed}")
    print(f"Zipf s: {args.zipf_s}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    generar_proveedores(
        args.proveedores,
        rng
    )

    generar_contratos(
        args.contratos,
        args.proveedores,
        rng
    )

    generar_skus(
        args.skus,
        rng
    )

    generar_proveedor_sku(
        args.proveedores,
        args.skus,
        rng
    )

    cantidad_cedis = generar_cedis(rng)

    generar_franjas(
        args.franjas,
        cantidad_cedis,
        rng
    )

    generar_ordenes(
        args.ordenes,
        args.proveedores,
        cantidad_cedis,
        rng,
        args.zipf_s
    )

    generar_lineas(
        args.ordenes,
        args.lineas,
        args.skus,
        rng
    )

    generar_eventos(
        args.eventos,
        args.ordenes,
        rng
    )

    calcular_checksums()

    print()
    print("=" * 60)
    print("GENERACIÓN COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()