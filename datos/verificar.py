#!/usr/bin/env python3

import argparse
import csv
import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent / "output"


# UTILIDADES

def leer_csv(nombre):
    path = OUTPUT_DIR / nombre

    if not path.exists():
        raise FileNotFoundError(
            f"No existe: {path}"
        )

    with open(
        path,
        "r",
        encoding="utf-8",
        newline=""
    ) as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            yield fila


def contar_filas(nombre):
    total = 0

    for _ in leer_csv(nombre):
        total += 1

    return total


def porcentaje(parte, total):
    if total == 0:
        return 0

    return parte * 100 / total


def resultado(nombre, ok, detalle=""):
    simbolo = "OK" if ok else "FAIL"

    print(
        f"[{simbolo:4}] "
        f"{nombre}"
        + (f" -> {detalle}" if detalle else "")
    )


# VOLUMEN

def verificar_volumen(nombre, esperado):
    actual = contar_filas(nombre)

    if esperado is None:
        resultado(
            f"Volumen {nombre}",
            True,
            f"{actual:,}"
        )
    else:
        resultado(
            f"Volumen {nombre}",
            actual == esperado,
            f"{actual:,} / {esperado:,}"
        )

    return actual

# RANGOS DE IDs

def verificar_ids(nombre, minimo, maximo):

    errores = 0
    cantidad = 0

    for fila in leer_csv(nombre):

        cantidad += 1

        try:
            valor = int(fila["id"])
        except (ValueError, KeyError):
            errores += 1
            continue

        if valor < minimo or valor > maximo:
            errores += 1

    resultado(
        f"IDs válidos {nombre}",
        errores == 0,
        f"{errores:,} errores"
    )


# CONTRATOS

def verificar_contratos(cantidad_proveedores):

    errores = 0
    proveedores = set()

    for fila in leer_csv("contratos.csv"):

        proveedor_id = int(
            fila["proveedor_id"]
        )

        if not 1 <= proveedor_id <= cantidad_proveedores:
            errores += 1

        proveedores.add(proveedor_id)

    resultado(
        "FK lógica contratos -> proveedores",
        errores == 0,
        f"{errores:,} errores"
    )

    print(
        f"      Proveedores con contrato: "
        f"{len(proveedores):,}"
    )


# PROVEEDOR-SKU

def verificar_proveedor_sku(
    cantidad_proveedores,
    cantidad_skus
):

    errores = 0
    combinaciones = set()

    for fila in leer_csv("proveedor_sku.csv"):

        proveedor_id = int(
            fila["proveedor_id"]
        )

        sku_id = int(
            fila["sku_id"]
        )

        if not 1 <= proveedor_id <= cantidad_proveedores:
            errores += 1

        if not 1 <= sku_id <= cantidad_skus:
            errores += 1

        combinaciones.add(
            (proveedor_id, sku_id)
        )

    duplicados = (
        contar_filas("proveedor_sku.csv")
        - len(combinaciones)
    )

    resultado(
        "IDs proveedor-SKU válidos",
        errores == 0,
        f"{errores:,} errores"
    )

    resultado(
        "Duplicados proveedor-SKU",
        duplicados == 0,
        f"{duplicados:,}"
    )


# ============================================================
# ORDENES
# ============================================================

def verificar_ordenes(
    cantidad_proveedores,
    cantidad_cedis
):

    errores = 0
    proveedores = Counter()

    estados = Counter()

    for fila in leer_csv("ordenes.csv"):

        proveedor_id = int(
            fila["proveedor_id"]
        )

        cedi_id = int(
            fila["cedi_id"]
        )

        estado = fila["estado"]

        if not 1 <= proveedor_id <= cantidad_proveedores:
            errores += 1

        if not 1 <= cedi_id <= cantidad_cedis:
            errores += 1

        estados[estado] += 1
        proveedores[proveedor_id] += 1

    resultado(
        "IDs lógicos de órdenes",
        errores == 0,
        f"{errores:,} errores"
    )

    print("\n      Distribución de estados:")

    for estado, cantidad in estados.most_common():
        print(
            f"        {estado:15} "
            f"{cantidad:10,} "
            f"({porcentaje(cantidad, sum(estados.values())):6.2f}%)"
        )

    return proveedores


# LINEAS

def verificar_lineas(
    cantidad_ordenes,
    cantidad_skus
):

    errores = 0
    lineas_por_orden = Counter()

    ids_por_orden = defaultdict(set)

    for fila in leer_csv("lineas_orden.csv"):

        orden_id = int(
            fila["orden_id"]
        )

        sku_id = int(
            fila["sku_id"]
        )

        numero_linea = int(
            fila["numero_linea"]
        )

        cantidad = int(
            fila["cantidad"]
        )

        cantidad_recibida = int(
            fila["cantidad_recibida"]
        )

        if not 1 <= orden_id <= cantidad_ordenes:
            errores += 1

        if not 1 <= sku_id <= cantidad_skus:
            errores += 1

        if cantidad <= 0:
            errores += 1

        if (
            cantidad_recibida < 0
            or cantidad_recibida > cantidad
        ):
            errores += 1

        if numero_linea in ids_por_orden[orden_id]:
            errores += 1

        ids_por_orden[orden_id].add(
            numero_linea
        )

        lineas_por_orden[orden_id] += 1

    resultado(
        "Integridad de líneas",
        errores == 0,
        f"{errores:,} errores"
    )

    if lineas_por_orden:

        minimo = min(
            lineas_por_orden.values()
        )

        maximo = max(
            lineas_por_orden.values()
        )

        promedio = (
            sum(lineas_por_orden.values())
            / len(lineas_por_orden)
        )

        print(
            "\n      Líneas por orden:"
        )

        print(
            f"        mínimo : {minimo}"
        )

        print(
            f"        máximo : {maximo}"
        )

        print(
            f"        promedio: {promedio:.2f}"
        )

    return lineas_por_orden


# EVENTOS


def verificar_eventos(cantidad_ordenes):

    errores = 0

    for fila in leer_csv("eventos.csv"):

        orden_id = int(
            fila["orden_id"]
        )

        if not 1 <= orden_id <= cantidad_ordenes:
            errores += 1

    resultado(
        "FK lógica eventos -> órdenes",
        errores == 0,
        f"{errores:,} errores"
    )



# ZIPF


def verificar_zipf(
    ordenes_por_proveedor,
    cantidad_ordenes,
    cantidad_proveedores
):

    if not ordenes_por_proveedor:
        return

    ordenes = sorted(
        ordenes_por_proveedor.values(),
        reverse=True
    )

    top_1_n = max(
        1,
        int(cantidad_proveedores * 0.01)
    )

    top_5_n = max(
        1,
        int(cantidad_proveedores * 0.05)
    )

    top_20_n = max(
        1,
        int(cantidad_proveedores * 0.20)
    )

    top_1 = sum(
        ordenes[:top_1_n]
    )

    top_5 = sum(
        ordenes[:top_5_n]
    )

    top_20 = sum(
        ordenes[:top_20_n]
    )

    print("\n      Distribución de órdenes por proveedor:")

    print(
        f"        Top 1% : "
        f"{top_1:,} / {cantidad_ordenes:,} "
        f"= {porcentaje(top_1, cantidad_ordenes):.2f}%"
    )

    print(
        f"        Top 5% : "
        f"{top_5:,} / {cantidad_ordenes:,} "
        f"= {porcentaje(top_5, cantidad_ordenes):.2f}%"
    )

    print(
        f"        Top 20%: "
        f"{top_20:,} / {cantidad_ordenes:,} "
        f"= {porcentaje(top_20, cantidad_ordenes):.2f}%"
    )

    # Requisitos del entregable:
    # Top 1% ≈ 15%
    # Top 5% >= 40%

    top_1_ok = (
        10 <= porcentaje(
            top_1,
            cantidad_ordenes
        ) <= 20
    )

    top_5_ok = (
        porcentaje(
            top_5,
            cantidad_ordenes
        ) >= 40
    )

    resultado(
        "Zipf Top 1% aproximadamente 15%",
        top_1_ok
    )

    resultado(
        "Zipf Top 5% >= 40%",
        top_5_ok
    )

    max_ordenes = max(ordenes)

    print(
        f"\n      Máximo de órdenes de un proveedor: "
        f"{max_ordenes:,}"
    )

    resultado(
        "Proveedor hot >= 5.000 órdenes",
        max_ordenes >= 5000
    )



# SKU HOT


def verificar_sku_hot(cantidad_lineas):

    contador = Counter()

    for fila in leer_csv("lineas_orden.csv"):

        sku_id = int(
            fila["sku_id"]
        )

        contador[sku_id] += 1

    total = sum(
        contador.values()
    )

    if total == 0:
        return

    top_10_n = max(
        1,
        int(len(contador) * 0.10)
    )

    top_10 = sum(
        cantidad
        for _, cantidad
        in contador.most_common(top_10_n)
    )

    porcentaje_hot = porcentaje(
        top_10,
        total
    )

    print(
        "\n      Hot SKU:"
    )

    print(
        f"        SKU distintos utilizados: "
        f"{len(contador):,}"
    )

    print(
        f"        Top 10% concentra: "
        f"{porcentaje_hot:.2f}% de las líneas"
    )

    resultado(
        "Hot SKU aproximadamente 60%",
        50 <= porcentaje_hot <= 70
    )



# ESTACIONALIDAD HORARIA


def verificar_horaria():

    horas = Counter()

    for fila in leer_csv("ordenes.csv"):

        fecha = datetime.fromisoformat(
            fila["fecha_orden"]
        )

        horas[fecha.hour] += 1

    total = sum(
        horas.values()
    )

    pico = sum(
        horas[h]
        for h in range(8, 11)
    )

    noche = sum(
        horas[h]
        for h in [0, 1, 2, 3, 4, 5]
    )

    print(
        "\n      Estacionalidad horaria:"
    )

    print(
        f"        08:00-10:59: "
        f"{porcentaje(pico, total):.2f}%"
    )

    print(
        f"        00:00-05:59: "
        f"{porcentaje(noche, total):.2f}%"
    )

    for hora in range(24):

        print(
            f"        {hora:02d}:00 "
            f"{horas[hora]:8,}"
        )



# CHECKSUM


def calcular_checksum(path):

    sha = hashlib.sha256()

    with open(path, "rb") as archivo:

        while True:

            bloque = archivo.read(
                1024 * 1024
            )

            if not bloque:
                break

            sha.update(bloque)

    return sha.hexdigest()


def verificar_checksums():

    checksum_path = (
        OUTPUT_DIR /
        "checksums.sha256"
    )

    if not checksum_path.exists():

        resultado(
            "Archivo de checksums",
            False,
            "no existe"
        )

        return

    errores = 0

    with open(
        checksum_path,
        "r",
        encoding="utf-8"
    ) as archivo:

        for linea in archivo:

            linea = linea.strip()

            if not linea:
                continue

            esperado, nombre = (
                linea.split(maxsplit=1)
            )

            path = OUTPUT_DIR / nombre

            if not path.exists():

                errores += 1
                continue

            actual = calcular_checksum(
                path
            )

            if actual != esperado:
                errores += 1

    resultado(
        "Checksums",
        errores == 0,
        f"{errores:,} diferencias"
    )



# MAIN


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Verificación del dataset "
            "del Entregable 2"
        )
    )

    parser.add_argument(
        "--proveedores",
        type=int,
        required=True
    )

    parser.add_argument(
        "--contratos",
        type=int,
        required=True
    )

    parser.add_argument(
        "--skus",
        type=int,
        required=True
    )

    parser.add_argument(
        "--ordenes",
        type=int,
        required=True
    )

    parser.add_argument(
        "--lineas",
        type=int,
        required=True
    )

    parser.add_argument(
        "--franjas",
        type=int,
        required=True
    )

    parser.add_argument(
        "--eventos",
        type=int,
        required=True
    )

    args = parser.parse_args()

    print("=" * 70)
    print("VERIFICACIÓN DEL DATASET")
    print("=" * 70)

    print("\n1. VOLUMEN\n")

    verificar_volumen(
        "proveedores.csv",
        args.proveedores
    )

    verificar_volumen(
        "contratos.csv",
        args.contratos
    )

    verificar_volumen(
        "skus.csv",
        args.skus
    )

    verificar_volumen(
        "proveedor_sku.csv",
        None
    )

    verificar_volumen(
        "cedi.csv",
        10
    )

    verificar_volumen(
        "franjas.csv",
        args.franjas
    )

    verificar_volumen(
        "ordenes.csv",
        args.ordenes
    )

    verificar_volumen(
        "lineas_orden.csv",
        args.lineas
    )

    verificar_volumen(
        "eventos.csv",
        args.eventos
    )

    print("\n2. RANGOS DE IDs\n")

    verificar_ids(
        "proveedores.csv",
        1,
        args.proveedores
    )

    verificar_ids(
        "skus.csv",
        1,
        args.skus
    )

    print("\n3. RELACIONES\n")

    verificar_contratos(
        args.proveedores
    )

    verificar_proveedor_sku(
        args.proveedores,
        args.skus
    )

    ordenes_por_proveedor = (
        verificar_ordenes(
            args.proveedores,
            10
        )
    )

    verificar_lineas(
        args.ordenes,
        args.skus
    )

    verificar_eventos(
        args.ordenes
    )

    print("\n4. DISTRIBUCIONES\n")

    verificar_zipf(
        ordenes_por_proveedor,
        args.ordenes,
        args.proveedores
    )

    verificar_sku_hot(
        args.lineas
    )

    verificar_horaria()

    print("\n5. REPRODUCIBILIDAD\n")

    verificar_checksums()

    print("\n" + "=" * 70)
    print("VERIFICACIÓN TERMINADA")
    print("=" * 70)


if __name__ == "__main__":
    main()