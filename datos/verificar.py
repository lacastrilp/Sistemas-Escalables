#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Verificador de datos generados

Verifica:

1. Volúmenes mínimos y/o esperados
2. Integridad de IDs
3. Integridad de relaciones lógicas
4. Integridad de contratos
5. Integridad proveedor-SKU
6. Integridad de órdenes
7. Integridad de líneas
8. Integridad de eventos
9. Distribución Zipf de proveedores
10. Concentración de SKU calientes
11. Estacionalidad mensual
12. Estacionalidad horaria
13. Los 8 casos límite
14. Checksums
15. Reporte final PASS/FAIL
16. Código de salida != 0 si existe algún FAIL

El script trabaja directamente sobre los CSV generados.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple


# ============================================================
# CONFIGURACIÓN
# ============================================================

DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "output"

# Fecha de referencia del dataset.
# Debe coincidir con la utilizada por generar.py.
REFERENCE_DATE = date(2025, 12, 31)

# Mínimos exigidos por el taller.
MIN_PROVEEDORES = 100_000
MIN_CONTRATOS = 10_000
MIN_SKUS = 200_000
MIN_ORDENES = 300_000
MIN_LINEAS = 1_500_000
MIN_FRANJAS = 90_000
MIN_EVENTOS = 500_000

# Concentración esperada.
ZIPF_TOP_1_MIN = 0.15
ZIPF_TOP_5_MIN = 0.40

HOT_SKU_TOP_PERCENT = 0.10
HOT_SKU_LINE_SHARE_MIN = 0.60

# Horario pico.
PEAK_START = 8
PEAK_END = 10

PEAK_SHARE_MIN = 0.70
NIGHT_SHARE_MAX = 0.05

# Estacionalidad mensual:
# últimos 3 días hábiles deben concentrar aproximadamente 25%.
MONTH_END_SHARE_TARGET = 0.25
MONTH_END_TOLERANCE = 0.03

# Caso límite: proveedor caliente.
HOT_PROVIDER_MIN_ORDERS = 5_000

# Caso límite: orden con muchas líneas.
EDGE_ORDER_LINES = 300


# ============================================================
# UTILIDADES
# ============================================================

class Verifier:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passes: List[str] = []

    def ok(self, message: str):
        self.passes.append(message)
        print(f"[OK]   {message}")

    def fail(self, message: str):
        self.errors.append(message)
        print(f"[FAIL] {message}")

    def warn(self, message: str):
        self.warnings.append(message)
        print(f"[WARN] {message}")

    def check(self, condition: bool, ok_msg: str, fail_msg: str):
        if condition:
            self.ok(ok_msg)
        else:
            self.fail(fail_msg)

    @property
    def success(self):
        return len(self.errors) == 0


# ============================================================
# CSV
# ============================================================

def buscar_csv(data_dir: Path, nombres: List[str]) -> Path:
    """
    Busca un CSV aceptando variantes razonables del nombre.
    """

    for nombre in nombres:
        candidato = data_dir / nombre

        if candidato.exists():
            return candidato

    # búsqueda case-insensitive
    archivos = {
        p.name.lower(): p
        for p in data_dir.glob("*.csv")
    }

    for nombre in nombres:
        p = archivos.get(nombre.lower())
        if p:
            return p

    raise FileNotFoundError(
        f"No se encontró ninguno de estos archivos en {data_dir}: "
        + ", ".join(nombres)
    )


def leer_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def detectar_columna(row: Dict[str, str], candidatos: List[str]) -> str | None:
    """
    Devuelve el nombre real de la columna buscando variantes.
    """

    normalizadas = {
        k.strip().lower().replace(" ", "_"): k
        for k in row.keys()
    }

    for candidato in candidatos:
        clave = candidato.strip().lower().replace(" ", "_")

        if clave in normalizadas:
            return normalizadas[clave]

    return None


def valor(
    row: Dict[str, str],
    candidatos: List[str],
    default=None
):
    col = detectar_columna(row, candidatos)

    if col is None:
        return default

    return row.get(col)


def entero(
    row: Dict[str, str],
    candidatos: List[str],
    default=None
):
    v = valor(row, candidatos, default)

    if v is None or v == "":
        return default

    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def flotante(
    row: Dict[str, str],
    candidatos: List[str],
    default=None
):
    v = valor(row, candidatos, default)

    if v is None or v == "":
        return default

    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def fecha(
    row: Dict[str, str],
    candidatos: List[str],
    default=None
):
    v = valor(row, candidatos, default)

    if not v:
        return default

    try:
        return datetime.fromisoformat(v).date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return default


def fecha_hora(
    row: Dict[str, str],
    candidatos: List[str],
    default=None
):
    v = valor(row, candidatos, default)

    if not v:
        return default

    try:
        return datetime.fromisoformat(v)
    except ValueError:
        return default


# ============================================================
# CHECKSUM
# ============================================================

def checksum_archivo(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            bloque = f.read(1024 * 1024)

            if not bloque:
                break

            h.update(bloque)

    return h.hexdigest()


def verificar_checksums(data_dir: Path, v: Verifier):

    checksum_path = data_dir / "checksums.sha256"

    if not checksum_path.exists():
        v.warn(
            "No existe checksums.sha256; no se puede verificar "
            "integridad mediante checksums."
        )
        return

    diferencias = 0
    encontrados = 0

    with checksum_path.open(
        "r",
        encoding="utf-8"
    ) as f:

        for linea in f:
            linea = linea.strip()

            if not linea:
                continue

            partes = linea.split()

            if len(partes) < 2:
                continue

            esperado = partes[0]
            nombre = partes[-1]

            archivo = data_dir / nombre

            if not archivo.exists():
                v.fail(
                    f"Checksum referencia archivo inexistente: {nombre}"
                )
                diferencias += 1
                continue

            encontrados += 1

            actual = checksum_archivo(archivo)

            if actual != esperado:
                diferencias += 1
                v.fail(
                    f"Checksum diferente: {nombre}"
                )

    if diferencias == 0:
        v.ok(
            f"Checksums OK ({encontrados} archivos verificados)"
        )


# ============================================================
# CARGA DE DATASET
# ============================================================

def cargar_dataset(data_dir: Path):

    nombres = {
        "proveedores": [
            "proveedores.csv",
            "proveedor.csv",
        ],
        "contratos": [
            "contratos.csv",
            "contrato_suministro.csv",
        ],
        "skus": [
            "skus.csv",
            "sku.csv",
        ],
        "proveedor_sku": [
            "proveedor_sku.csv",
            "proveedores_sku.csv",
        ],
        "cedi": [
            "cedi.csv",
            "cedis.csv",
        ],
        "franjas": [
            "franjas.csv",
            "franjas_descargue.csv",
            "franja_descargue.csv",
        ],
        "ordenes": [
            "ordenes.csv",
            "orden_compra.csv",
        ],
        "lineas": [
            "lineas_orden.csv",
            "linea_orden.csv",
        ],
        "eventos": [
            "eventos.csv",
            "evento.csv",
        ],
    }

    archivos = {}

    for tabla, candidatos in nombres.items():
        archivos[tabla] = buscar_csv(data_dir, candidatos)

    datos = {
        tabla: leer_csv(path)
        for tabla, path in archivos.items()
    }

    return archivos, datos


# ============================================================
# VOLUMEN
# ============================================================

def verificar_volumen(
    datos: Dict[str, List[Dict[str, str]]],
    args,
    v: Verifier
):

    objetivos = {
        "proveedores": (
            args.proveedores,
            MIN_PROVEEDORES
        ),
        "contratos": (
            args.contratos,
            MIN_CONTRATOS
        ),
        "skus": (
            args.skus,
            MIN_SKUS
        ),
        "ordenes": (
            args.ordenes,
            MIN_ORDENES
        ),
        "lineas": (
            args.lineas,
            MIN_LINEAS
        ),
        "franjas": (
            args.franjas,
            MIN_FRANJAS
        ),
        "eventos": (
            args.eventos,
            MIN_EVENTOS
        ),
    }

    print("\n=== VOLUMEN ===")

    for tabla, (esperado, minimo) in objetivos.items():

        actual = len(datos[tabla])

        # Si el usuario especificó un objetivo exacto,
        # verificamos ese objetivo.
        if esperado is not None:

            v.check(
                actual == esperado,
                f"{tabla}: {actual:,}/{esperado:,}",
                f"{tabla}: {actual:,}/{esperado:,}"
            )

        else:

            v.check(
                actual >= minimo,
                f"{tabla}: {actual:,} >= mínimo {minimo:,}",
                f"{tabla}: {actual:,} < mínimo {minimo:,}"
            )

    # Tablas derivadas
    v.check(
        len(datos["proveedor_sku"]) > 0,
        f"proveedor_sku: {len(datos['proveedor_sku']):,}",
        "proveedor_sku está vacío"
    )

    v.check(
        len(datos["cedi"]) > 0,
        f"cedi: {len(datos['cedi']):,}",
        "cedi está vacío"
    )


# ============================================================
# IDs
# ============================================================

def verificar_ids(datos, v: Verifier):

    print("\n=== IDs ===")

    tablas = [
        ("proveedores", ["id", "proveedor_id"]),
        ("contratos", ["id", "contrato_id"]),
        ("skus", ["id", "sku_id"]),
        ("cedi", ["id", "cedi_id"]),
        ("franjas", ["id", "franja_id"]),
        ("ordenes", ["id", "orden_id"]),
        ("lineas", ["id", "linea_id"]),
        ("eventos", ["id", "evento_id"]),
    ]

    for tabla, candidatos in tablas:

        ids = []

        for row in datos[tabla]:
            x = entero(row, candidatos)

            if x is not None:
                ids.append(x)

        invalidos = [
            x for x in ids
            if x <= 0
        ]

        duplicados = len(ids) - len(set(ids))

        v.check(
            len(invalidos) == 0,
            f"{tabla}: IDs positivos",
            f"{tabla}: {len(invalidos)} IDs inválidos"
        )

        v.check(
            duplicados == 0,
            f"{tabla}: IDs únicos",
            f"{tabla}: {duplicados} IDs duplicados"
        )


# ============================================================
# CONTRATOS
# ============================================================

def verificar_contratos(datos, v: Verifier):

    print("\n=== CONTRATOS ===")

    proveedores = {
        entero(r, ["id", "proveedor_id"])
        for r in datos["proveedores"]
    }

    contratos = datos["contratos"]

    proveedores_contrato = set()

    for c in contratos:

        cid = entero(c, ["id", "contrato_id"])
        pid = entero(c, ["proveedor_id"])

        inicio = fecha(
            c,
            ["fecha_inicio", "inicio"]
        )

        fin = fecha(
            c,
            ["fecha_fin", "fin"]
        )

        if pid is not None:
            proveedores_contrato.add(pid)

            if pid not in proveedores:
                v.fail(
                    f"Contrato {cid} referencia proveedor inexistente {pid}"
                )

        if inicio and fin:

            if fin < inicio:
                v.fail(
                    f"Contrato {cid}: fecha_fin < fecha_inicio"
                )

    v.check(
        len(proveedores_contrato) > 0,
        f"{len(proveedores_contrato):,} proveedores tienen contrato",
        "Ningún proveedor tiene contrato"
    )

    # Caso 2
    expirado = False

    for c in contratos:

        fin = fecha(
            c,
            ["fecha_fin", "fin"]
        )

        if fin == REFERENCE_DATE - timedelta(days=1):
            expirado = True
            break

    v.check(
        expirado,
        "Caso 2: existe contrato vencido ayer",
        "Caso 2 FAIL: no se encontró contrato vencido ayer"
    )

    # Caso 3
    # El modelo actual usa DATE, por lo tanto no puede representar
    # literalmente "hoy a las 12:00".
    hoy = False

    for c in contratos:

        fin = fecha(
            c,
            ["fecha_fin", "fin"]
        )

        if fin == REFERENCE_DATE:
            hoy = True
            break

    v.check(
        hoy,
        "Caso 3: existe contrato que vence hoy (modelo DATE)",
        "Caso 3 FAIL: no existe contrato con fecha_fin = hoy"
    )

    print(
        "Nota: con fecha_fin DATE no es posible verificar "
        "la hora exacta 12:00. Para eso el modelo debe usar "
        "TIMESTAMP o una columna hora_fin."
    )


# ============================================================
# PROVEEDOR-SKU
# ============================================================

def verificar_proveedor_sku(datos, v: Verifier):

    print("\n=== PROVEEDOR-SKU ===")

    proveedores = {
        entero(r, ["id", "proveedor_id"])
        for r in datos["proveedores"]
    }

    skus = {
        entero(r, ["id", "sku_id"])
        for r in datos["skus"]
    }

    pares = set()
    errores = 0

    por_proveedor = defaultdict(set)

    for r in datos["proveedor_sku"]:

        pid = entero(r, ["proveedor_id"])
        sid = entero(r, ["sku_id"])

        if pid not in proveedores:
            errores += 1
            v.fail(
                f"proveedor_sku referencia proveedor inexistente: {pid}"
            )

        if sid not in skus:
            errores += 1
            v.fail(
                f"proveedor_sku referencia SKU inexistente: {sid}"
            )

        par = (pid, sid)

        if par in pares:
            errores += 1
            v.fail(
                f"proveedor_sku duplicado: proveedor={pid}, sku={sid}"
            )

        pares.add(par)
        por_proveedor[pid].add(sid)

    if errores == 0:
        v.ok(
            f"Proveedor-SKU íntegro: {len(pares):,} relaciones"
        )

    sin_catalogo = [
        pid
        for pid in proveedores
        if pid not in por_proveedor
    ]

    v.check(
        len(sin_catalogo) == 0,
        "Todos los proveedores tienen catálogo",
        f"{len(sin_catalogo):,} proveedores sin SKU negociado"
    )


# ============================================================
# ÓRDENES
# ============================================================

def construir_indices(datos):

    proveedores = {
        entero(r, ["id", "proveedor_id"])
        for r in datos["proveedores"]
    }

    skus = {
        entero(r, ["id", "sku_id"])
        for r in datos["skus"]
    }

    cedis = {
        entero(r, ["id", "cedi_id"])
        for r in datos["cedi"]
    }

    franjas = {
        entero(r, ["id", "franja_id"])
        for r in datos["franjas"]
    }

    return proveedores, skus, cedis, franjas


def verificar_ordenes(datos, v: Verifier):

    print("\n=== ÓRDENES ===")

    proveedores, _, cedis, franjas = construir_indices(datos)

    ids_ordenes = set()
    ordenes_por_proveedor = Counter()
    ordenes_por_fecha = Counter()

    estados = Counter()

    errores = 0

    for row in datos["ordenes"]:

        oid = entero(row, ["id", "orden_id"])
        pid = entero(row, ["proveedor_id"])
        cedi = entero(row, ["cedi_id"])
        franja = entero(row, ["franja_id"])

        f = fecha(
            row,
            ["fecha", "fecha_orden", "fecha_creacion"]
        )

        estado = (
            valor(
                row,
                ["estado", "status"],
                ""
            )
            or ""
        ).upper()

        ids_ordenes.add(oid)

        if pid not in proveedores:
            errores += 1
            v.fail(
                f"Orden {oid}: proveedor inexistente {pid}"
            )

        if cedi not in cedis:
            errores += 1
            v.fail(
                f"Orden {oid}: CEDI inexistente {cedi}"
            )

        if franja not in franjas:
            errores += 1
            v.fail(
                f"Orden {oid}: franja inexistente {franja}"
            )

        if pid is not None:
            ordenes_por_proveedor[pid] += 1

        if f:
            ordenes_por_fecha[f] += 1

        if estado:
            estados[estado] += 1

    if errores == 0:
        v.ok(
            f"FK lógica de órdenes OK: {len(ids_ordenes):,} órdenes"
        )

    print("\nDistribución de estados:")

    total = sum(estados.values())

    for estado, cantidad in estados.most_common():

        porcentaje = (
            cantidad / total * 100
            if total
            else 0
        )

        print(
            f"  {estado:<15} "
            f"{cantidad:>10,} "
            f"({porcentaje:6.2f}%)"
        )

    return ids_ordenes, ordenes_por_proveedor, ordenes_por_fecha


# ============================================================
# LÍNEAS
# ============================================================

def verificar_lineas(
    datos,
    ids_ordenes,
    v: Verifier
):

    print("\n=== LÍNEAS ===")

    skus = {
        entero(r, ["id", "sku_id"])
        for r in datos["skus"]
    }

    lineas_por_orden = Counter()
    errores = 0

    for row in datos["lineas"]:

        oid = entero(row, ["orden_id"])
        sid = entero(row, ["sku_id"])

        numero = entero(
            row,
            ["numero_linea", "linea", "line_number"]
        )

        if oid not in ids_ordenes:
            errores += 1
            v.fail(
                f"Línea referencia orden inexistente: {oid}"
            )

        if sid not in skus:
            errores += 1
            v.fail(
                f"Línea referencia SKU inexistente: {sid}"
            )

        if numero is not None and numero <= 0:
            errores += 1
            v.fail(
                f"Línea con numero_linea inválido: {numero}"
            )

        lineas_por_orden[oid] += 1

    if errores == 0:
        v.ok(
            f"Integridad de líneas OK: {len(datos['lineas']):,}"
        )

    sin_lineas = [
        oid
        for oid in ids_ordenes
        if lineas_por_orden[oid] == 0
    ]

    v.check(
        len(sin_lineas) == 0,
        "Todas las órdenes tienen al menos una línea",
        f"{len(sin_lineas):,} órdenes no tienen líneas"
    )

    distribucion = Counter(
        lineas_por_orden.values()
    )

    print("\nLíneas por orden:")

    for cantidad, frecuencia in sorted(distribucion.items()):

        print(
            f"  {cantidad:>4} líneas: "
            f"{frecuencia:>10,} órdenes"
        )

    max_lineas = max(
        lineas_por_orden.values(),
        default=0
    )

    print(
        f"\nMáximo de líneas en una orden: {max_lineas}"
    )

    v.check(
        max_lineas >= EDGE_ORDER_LINES,
        f"Caso 1: existe orden con >= {EDGE_ORDER_LINES} líneas",
        f"Caso 1 FAIL: máximo encontrado = {max_lineas}, "
        f"se requieren >= {EDGE_ORDER_LINES}"
    )

    return lineas_por_orden


# ============================================================
# EVENTOS
# ============================================================

def verificar_eventos(
    datos,
    ids_ordenes,
    v: Verifier
):

    print("\n=== EVENTOS ===")

    errores = 0

    for row in datos["eventos"]:

        oid = entero(row, ["orden_id"])

        if oid not in ids_ordenes:
            errores += 1
            v.fail(
                f"Evento referencia orden inexistente: {oid}"
            )

    if errores == 0:
        v.ok(
            f"Eventos -> órdenes OK: {len(datos['eventos']):,}"
        )


# ============================================================
# ZIPF
# ============================================================

def verificar_zipf(
    ordenes_por_proveedor,
    total_ordenes,
    v: Verifier
):

    print("\n=== ZIPF / PROVEEDORES HOT ===")

    frecuencias = sorted(
        ordenes_por_proveedor.values(),
        reverse=True
    )

    if not frecuencias:
        v.fail("No existen órdenes por proveedor")
        return

    def share_top(fraccion):

        n = max(
            1,
            math.ceil(
                len(frecuencias) * fraccion
            )
        )

        return (
            sum(frecuencias[:n]) / total_ordenes
            if total_ordenes
            else 0
        )

    top1 = share_top(0.01)
    top5 = share_top(0.05)
    top20 = share_top(0.20)

    print(
        f"Top 1% : {top1 * 100:.2f}%"
    )

    print(
        f"Top 5% : {top5 * 100:.2f}%"
    )

    print(
        f"Top 20%: {top20 * 100:.2f}%"
    )

    v.check(
        top1 >= ZIPF_TOP_1_MIN,
        f"Zipf top 1% >= {ZIPF_TOP_1_MIN * 100:.0f}%",
        f"Zipf top 1% = {top1 * 100:.2f}% "
        f"< {ZIPF_TOP_1_MIN * 100:.0f}%"
    )

    v.check(
        top5 >= ZIPF_TOP_5_MIN,
        f"Zipf top 5% >= {ZIPF_TOP_5_MIN * 100:.0f}%",
        f"Zipf top 5% = {top5 * 100:.2f}% "
        f"< {ZIPF_TOP_5_MIN * 100:.0f}%"
    )

    hot_provider = max(
        ordenes_por_proveedor.items(),
        key=lambda x: x[1],
        default=(None, 0)
    )

    pid, cantidad = hot_provider

    print(
        f"Proveedor más caliente: {pid} "
        f"con {cantidad:,} órdenes"
    )

    v.check(
        cantidad >= HOT_PROVIDER_MIN_ORDERS,
        f"Caso 7: proveedor hot >= {HOT_PROVIDER_MIN_ORDERS:,} órdenes",
        f"Caso 7 FAIL: proveedor hot = {cantidad:,}; "
        f"se requieren >= {HOT_PROVIDER_MIN_ORDERS:,}"
    )


# ============================================================
# HOT SKU
# ============================================================

def verificar_hot_sku(
    datos,
    v: Verifier
):

    print("\n=== HOT SKU ===")

    sku_ids = {
        entero(r, ["id", "sku_id"])
        for r in datos["skus"]
    }

    conteo = Counter()

    for row in datos["lineas"]:

        sid = entero(row, ["sku_id"])

        if sid is not None:
            conteo[sid] += 1

    if not conteo:
        v.fail("No hay SKU utilizados en líneas")
        return

    ranking = sorted(
        conteo.items(),
        key=lambda x: x[1],
        reverse=True
    )

    n_hot = max(
        1,
        math.ceil(
            len(sku_ids) * HOT_SKU_TOP_PERCENT
        )
    )

    hot = ranking[:n_hot]

    lineas_hot = sum(
        cantidad
        for _, cantidad in hot
    )

    total_lineas = sum(
        conteo.values()
    )

    share = (
        lineas_hot / total_lineas
        if total_lineas
        else 0
    )

    print(
        f"SKU totales: {len(sku_ids):,}"
    )

    print(
        f"Top 10% SKU: {n_hot:,}"
    )

    print(
        f"Líneas en top 10%: "
        f"{lineas_hot:,}/{total_lineas:,} "
        f"({share * 100:.2f}%)"
    )

    v.check(
        share >= HOT_SKU_LINE_SHARE_MIN,
        f"Hot SKU: top 10% concentra >= "
        f"{HOT_SKU_LINE_SHARE_MIN * 100:.0f}%",
        f"Hot SKU FAIL: concentración = "
        f"{share * 100:.2f}%"
    )


# ============================================================
# ESTACIONALIDAD HORARIA
# ============================================================

def verificar_estacionalidad_horaria(
    datos,
    v: Verifier
):

    print("\n=== ESTACIONALIDAD HORARIA ===")

    horas = Counter()

    for row in datos["ordenes"]:

        dt = fecha_hora(
            row,
            [
                "fecha_hora",
                "timestamp",
                "created_at",
                "fecha_creacion",
                "fecha_orden"
            ]
        )

        if dt is None:

            f = valor(
                row,
                ["fecha"]
            )

            h = valor(
                row,
                ["hora"]
            )

            if h is not None:

                try:
                    hora_int = int(
                        str(h)[:2]
                    )

                    horas[hora_int] += 1

                except ValueError:
                    pass

            continue

        horas[dt.hour] += 1

    total = sum(horas.values())

    if total == 0:
        v.fail(
            "No se pudo determinar la hora de las órdenes"
        )
        return

    pico = sum(
        cantidad
        for hora, cantidad in horas.items()
        if PEAK_START <= hora <= PEAK_END
    )

    noche = sum(
        cantidad
        for hora, cantidad in horas.items()
        if 0 <= hora <= 5
    )

    share_pico = pico / total
    share_noche = noche / total

    print(
        f"08:00-10:59: "
        f"{pico:,}/{total:,} "
        f"({share_pico * 100:.2f}%)"
    )

    print(
        f"00:00-05:59: "
        f"{noche:,}/{total:,} "
        f"({share_noche * 100:.2f}%)"
    )

    v.check(
        share_pico >= PEAK_SHARE_MIN,
        f"Pico 08-10 >= {PEAK_SHARE_MIN * 100:.0f}%",
        f"Pico 08-10 = {share_pico * 100:.2f}%"
    )

    v.check(
        share_noche <= NIGHT_SHARE_MAX,
        f"Madrugada <= {NIGHT_SHARE_MAX * 100:.0f}%",
        f"Madrugada = {share_noche * 100:.2f}%"
    )

    print("\nDistribución por hora:")

    for hora in range(24):

        cantidad = horas.get(hora, 0)

        print(
            f"  {hora:02d}:00 "
            f"{cantidad:>10,}"
        )


# ============================================================
# DÍAS HÁBILES
# ============================================================

def ultimos_tres_dias_habiles(
    year: int,
    month: int
) -> Set[date]:

    if month == 12:
        siguiente = date(
            year + 1,
            1,
            1
        )
    else:
        siguiente = date(
            year,
            month + 1,
            1
        )

    ultimo = siguiente - timedelta(days=1)

    dias = []
    actual = ultimo

    while len(dias) < 3:

        if actual.weekday() < 5:
            dias.append(actual)

        actual -= timedelta(days=1)

    return set(dias)


# ============================================================
# ESTACIONALIDAD MENSUAL
# ============================================================

def verificar_estacionalidad_mensual(
    datos,
    v: Verifier
):

    print("\n=== ESTACIONALIDAD MENSUAL ===")

    ordenes_por_mes = Counter()
    ordenes_ultimos_3 = Counter()

    fechas = []

    for row in datos["ordenes"]:

        f = fecha(
            row,
            [
                "fecha",
                "fecha_orden",
                "fecha_creacion"
            ]
        )

        if f is None:
            continue

        fechas.append(f)

        clave = (f.year, f.month)

        ordenes_por_mes[clave] += 1

        if f in ultimos_tres_dias_habiles(
            f.year,
            f.month
        ):
            ordenes_ultimos_3[clave] += 1

    if not ordenes_por_mes:

        v.fail(
            "No se pudieron obtener fechas de órdenes"
        )

        return

    shares = []

    for mes, total in sorted(
        ordenes_por_mes.items()
    ):

        ultimo = ordenes_ultimos_3[mes]

        share = ultimo / total

        shares.append(share)

        print(
            f"{mes[0]}-{mes[1]:02d}: "
            f"{ultimo:,}/{total:,} "
            f"({share * 100:.2f}%)"
        )

    promedio = sum(shares) / len(shares)

    print(
        f"Promedio últimos 3 días hábiles: "
        f"{promedio * 100:.2f}%"
    )

    v.check(
        abs(
            promedio - MONTH_END_SHARE_TARGET
        ) <= MONTH_END_TOLERANCE,
        "Estacionalidad mensual: "
        "últimos 3 días hábiles ≈ 25%",
        f"Estacionalidad mensual FAIL: "
        f"promedio = {promedio * 100:.2f}%"
    )


# ============================================================
# CASOS LÍMITE
# ============================================================

def verificar_casos_limite(
    datos,
    ordenes_por_proveedor,
    lineas_por_orden,
    v: Verifier
):

    print("\n=== 8 CASOS LÍMITE ===")

    # --------------------------------------------------------
    # Caso 1
    # Orden con 300 líneas
    # --------------------------------------------------------

    max_lineas = max(
        lineas_por_orden.values(),
        default=0
    )

    v.check(
        max_lineas >= 300,
        "Caso 1 OK: orden con 300 o más líneas",
        f"Caso 1 FAIL: máximo = {max_lineas}"
    )

    # --------------------------------------------------------
    # Caso 2
    # Contrato vencido ayer
    # --------------------------------------------------------

    caso2 = any(
        fecha(
            r,
            ["fecha_fin", "fin"]
        ) == REFERENCE_DATE - timedelta(days=1)
        for r in datos["contratos"]
    )

    v.check(
        caso2,
        "Caso 2 OK: contrato vencido ayer",
        "Caso 2 FAIL: contrato vencido ayer no encontrado"
    )

    # --------------------------------------------------------
    # Caso 3
    # Contrato que vence hoy
    # --------------------------------------------------------

    caso3 = any(
        fecha(
            r,
            ["fecha_fin", "fin"]
        ) == REFERENCE_DATE
        for r in datos["contratos"]
    )

    v.check(
        caso3,
        "Caso 3 OK: contrato que vence hoy",
        "Caso 3 FAIL: contrato que vence hoy no encontrado"
    )

    # --------------------------------------------------------
    # Caso 4
    # Última franja disponible del día
    # --------------------------------------------------------

    franjas_por_cedi = defaultdict(list)

    for r in datos["franjas"]:

        cedi = entero(
            r,
            ["cedi_id"]
        )

        inicio = valor(
            r,
            ["hora_inicio"]
        )

        fin = valor(
            r,
            ["hora_fin"]
        )

        if cedi is not None:
            franjas_por_cedi[cedi].append(
                (inicio, fin, r)
            )

    caso4 = False

    for cedi, franjas in franjas_por_cedi.items():

        if not franjas:
            continue

        def convertir_hora(x):

            if x is None:
                return -1

            try:
                partes = str(x).split(":")
                return (
                    int(partes[0]) * 3600
                    + int(partes[1]) * 60
                    + int(partes[2])
                    if len(partes) >= 3
                    else int(partes[0]) * 3600
                )
            except Exception:
                return -1

        ultima = max(
            franjas,
            key=lambda x: convertir_hora(x[0])
        )

        hora_inicio = convertir_hora(
            ultima[0]
        )

        # Una franja empieza a las 22:00 o más tarde.
        if hora_inicio >= 22 * 3600:
            caso4 = True
            break

    v.check(
        caso4,
        "Caso 4 OK: existe última franja del día",
        "Caso 4 FAIL: no se encontró franja nocturna/final"
    )

    # --------------------------------------------------------
    # Caso 5
    # Proveedor sin contrato actual
    # --------------------------------------------------------

    contratos_actuales = set()

    for r in datos["contratos"]:

        pid = entero(
            r,
            ["proveedor_id"]
        )

        inicio = fecha(
            r,
            ["fecha_inicio", "inicio"]
        )

        fin = fecha(
            r,
            ["fecha_fin", "fin"]
        )

        if pid is None:
            continue

        inicio_ok = (
            inicio is None
            or inicio <= REFERENCE_DATE
        )

        fin_ok = (
            fin is None
            or fin >= REFERENCE_DATE
        )

        if inicio_ok and fin_ok:
            contratos_actuales.add(pid)

    proveedores = {
        entero(r, ["id", "proveedor_id"])
        for r in datos["proveedores"]
    }

    sin_contrato_actual = (
        proveedores - contratos_actuales
    )

    v.check(
        len(sin_contrato_actual) > 0,
        "Caso 5 OK: existe proveedor sin contrato actual",
        "Caso 5 FAIL: todos los proveedores tienen contrato actual"
    )

    # --------------------------------------------------------
    # Caso 6
    # SKU fuera del catálogo negociado
    # --------------------------------------------------------

    catalogo = set()

    for r in datos["proveedor_sku"]:

        pid = entero(
            r,
            ["proveedor_id"]
        )

        sid = entero(
            r,
            ["sku_id"]
        )

        catalogo.add(
            (pid, sid)
        )

    orden_proveedor = {}

    for r in datos["ordenes"]:

        oid = entero(
            r,
            ["id", "orden_id"]
        )

        pid = entero(
            r,
            ["proveedor_id"]
        )

        orden_proveedor[oid] = pid

    caso6 = False

    for r in datos["lineas"]:

        oid = entero(
            r,
            ["orden_id"]
        )

        sid = entero(
            r,
            ["sku_id"]
        )

        pid = orden_proveedor.get(oid)

        if pid is not None and (
            pid,
            sid
        ) not in catalogo:

            caso6 = True
            break

    v.check(
        caso6,
        "Caso 6 OK: existe SKU fuera del catálogo negociado",
        "Caso 6 FAIL: no se encontró SKU fuera del catálogo"
    )

    # --------------------------------------------------------
    # Caso 7
    # Proveedor hot >= 5000 órdenes
    # --------------------------------------------------------

    max_ordenes = max(
        ordenes_por_proveedor.values(),
        default=0
    )

    v.check(
        max_ordenes >= HOT_PROVIDER_MIN_ORDERS,
        f"Caso 7 OK: proveedor hot >= "
        f"{HOT_PROVIDER_MIN_ORDERS:,}",
        f"Caso 7 FAIL: máximo = {max_ordenes:,}"
    )

    # --------------------------------------------------------
    # Caso 8
    # Mes sin órdenes para un proveedor activo
    # --------------------------------------------------------

    ordenes_proveedor_mes = defaultdict(
        lambda: defaultdict(int)
    )

    for r in datos["ordenes"]:

        pid = entero(
            r,
            ["proveedor_id"]
        )

        f = fecha(
            r,
            [
                "fecha",
                "fecha_orden",
                "fecha_creacion"
            ]
        )

        if pid is None or f is None:
            continue

        ordenes_proveedor_mes[pid][
            (f.year, f.month)
        ] += 1

    # Detectar meses presentes en dataset.
    meses = set()

    for r in datos["ordenes"]:

        f = fecha(
            r,
            [
                "fecha",
                "fecha_orden",
                "fecha_creacion"
            ]
        )

        if f:
            meses.add(
                (f.year, f.month)
            )

    caso8 = False

    proveedor_caso8 = None
    mes_caso8 = None

    for pid in ordenes_proveedor_mes:

        for mes in meses:

            if (
                ordenes_proveedor_mes[pid].get(
                    mes,
                    0
                ) == 0
            ):

                caso8 = True
                proveedor_caso8 = pid
                mes_caso8 = mes
                break

        if caso8:
            break

    v.check(
        caso8,
        (
            "Caso 8 OK: proveedor activo con mes sin órdenes"
            + (
                f" (proveedor={proveedor_caso8}, "
                f"mes={mes_caso8[0]}-{mes_caso8[1]:02d})"
                if caso8
                else ""
            )
        ),
        "Caso 8 FAIL: no se encontró proveedor activo "
        "con un mes sin órdenes"
    )


# ============================================================
# VALIDACIÓN ESTRUCTURAL
# ============================================================

def verificar_columnas(datos, v: Verifier):

    print("\n=== ESTRUCTURA CSV ===")

    esperadas = {
        "proveedores": [
            ["id", "proveedor_id"]
        ],
        "contratos": [
            "proveedor_id",
            "fecha_inicio",
            "fecha_fin"
        ],
        "skus": [
            ["id", "sku_id"]
        ],
        "proveedor_sku": [
            "proveedor_id",
            "sku_id"
        ],
        "cedi": [
            ["id", "cedi_id"]
        ],
        "franjas": [
            "cedi_id",
            "hora_inicio",
            "hora_fin"
        ],
        "ordenes": [
            "proveedor_id",
            "cedi_id",
            "franja_id"
        ],
        "lineas": [
            "orden_id",
            "sku_id"
        ],
        "eventos": [
            "orden_id"
        ],
    }

    for tabla, candidatos in esperadas.items():

        if not datos[tabla]:

            v.fail(
                f"{tabla}: CSV vacío"
            )

            continue

        row = datos[tabla][0]

        faltantes = []

        for requisito in candidatos:

            aliases = (
                requisito
                if isinstance(requisito, list)
                else [requisito]
            )

            if not any(
                detectar_columna(row, [alias]) is not None
                for alias in aliases
            ):
                faltantes.append(" o ".join(aliases))

        v.check(
            len(faltantes) == 0,
            f"{tabla}: columnas requeridas presentes",
            f"{tabla}: faltan columnas "
            + ", ".join(faltantes)
        )


# ============================================================
# RESUMEN
# ============================================================

def resumen(
    datos,
    archivos,
    v: Verifier
):

    print("\n" + "=" * 70)
    print("RESUMEN DE VERIFICACIÓN")
    print("=" * 70)

    print(
        f"PASS : {len(v.passes)}"
    )

    print(
        f"WARN : {len(v.warnings)}"
    )

    print(
        f"FAIL : {len(v.errors)}"
    )

    print("\nArchivos:")

    for tabla, path in archivos.items():

        print(
            f"  {tabla:<20} "
            f"{path.name:<35} "
            f"{len(datos[tabla]):>12,} filas"
        )

    print()

    if v.success:

        print(
            "RESULTADO FINAL: PASS"
        )

        print(
            "El dataset supera todas las validaciones "
            "implementadas."
        )

    else:

        print(
            "RESULTADO FINAL: FAIL"
        )

        print(
            "Hay validaciones que requieren corrección."
        )

        print("\nFallos:")

        for error in v.errors:
            print(
                f"  - {error}"
            )


# ============================================================
# ARGUMENTOS
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Verificador completo del dataset "
            "del Taller 2."
        )
    )

    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Directorio donde están los CSV"
    )

    parser.add_argument(
        "--proveedores",
        type=int,
        default=None,
        help="Cantidad exacta esperada de proveedores"
    )

    parser.add_argument(
        "--contratos",
        type=int,
        default=None,
        help="Cantidad exacta esperada de contratos"
    )

    parser.add_argument(
        "--skus",
        type=int,
        default=None,
        help="Cantidad exacta esperada de SKU"
    )

    parser.add_argument(
        "--ordenes",
        type=int,
        default=None,
        help="Cantidad exacta esperada de órdenes"
    )

    parser.add_argument(
        "--lineas",
        type=int,
        default=None,
        help="Cantidad exacta esperada de líneas"
    )

    parser.add_argument(
        "--franjas",
        type=int,
        default=None,
        help="Cantidad exacta esperada de franjas"
    )

    parser.add_argument(
        "--eventos",
        type=int,
        default=None,
        help="Cantidad exacta esperada de eventos"
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()

    data_dir = Path(
        args.data_dir
    ).expanduser().resolve()

    print("=" * 70)
    print("VERIFICADOR - TALLER 2")
    print("=" * 70)

    print(
        f"Directorio: {data_dir}"
    )

    print(
        f"Fecha de referencia: {REFERENCE_DATE}"
    )

    v = Verifier()

    try:

        archivos, datos = cargar_dataset(
            data_dir
        )

    except Exception as e:

        print(
            f"\n[FAIL] Error cargando dataset: {e}"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # 1. estructura
    # --------------------------------------------------------

    verificar_columnas(
        datos,
        v
    )

    # --------------------------------------------------------
    # 2. volumen
    # --------------------------------------------------------

    verificar_volumen(
        datos,
        args,
        v
    )

    # --------------------------------------------------------
    # 3. IDs
    # --------------------------------------------------------

    verificar_ids(
        datos,
        v
    )

    # --------------------------------------------------------
    # 4. contratos
    # --------------------------------------------------------

    verificar_contratos(
        datos,
        v
    )

    # --------------------------------------------------------
    # 5. proveedor-SKU
    # --------------------------------------------------------

    verificar_proveedor_sku(
        datos,
        v
    )

    # --------------------------------------------------------
    # 6. órdenes
    # --------------------------------------------------------

    (
        ids_ordenes,
        ordenes_por_proveedor,
        ordenes_por_fecha
    ) = verificar_ordenes(
        datos,
        v
    )

    # --------------------------------------------------------
    # 7. líneas
    # --------------------------------------------------------

    lineas_por_orden = verificar_lineas(
        datos,
        ids_ordenes,
        v
    )

    # --------------------------------------------------------
    # 8. eventos
    # --------------------------------------------------------

    verificar_eventos(
        datos,
        ids_ordenes,
        v
    )

    # --------------------------------------------------------
    # 9. Zipf
    # --------------------------------------------------------

    verificar_zipf(
        ordenes_por_proveedor,
        len(datos["ordenes"]),
        v
    )

    # --------------------------------------------------------
    # 10. Hot SKU
    # --------------------------------------------------------

    verificar_hot_sku(
        datos,
        v
    )

    # --------------------------------------------------------
    # 11. estacionalidad horaria
    # --------------------------------------------------------

    verificar_estacionalidad_horaria(
        datos,
        v
    )

    # --------------------------------------------------------
    # 12. estacionalidad mensual
    # --------------------------------------------------------

    verificar_estacionalidad_mensual(
        datos,
        v
    )

    # --------------------------------------------------------
    # 13. casos límite
    # --------------------------------------------------------

    verificar_casos_limite(
        datos,
        ordenes_por_proveedor,
        lineas_por_orden,
        v
    )

    # --------------------------------------------------------
    # 14. checksums
    # --------------------------------------------------------

    verificar_checksums(
        data_dir,
        v
    )

    # --------------------------------------------------------
    # 15. resumen
    # --------------------------------------------------------

    resumen(
        datos,
        archivos,
        v
    )

    # --------------------------------------------------------
    # código de salida
    # --------------------------------------------------------

    if not v.success:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()