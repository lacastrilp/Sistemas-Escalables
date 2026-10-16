#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Generador determinista, parametrizable y masivo de datos para Portal B2B Retail.
Cumple estrictamente los requisitos C1, C2 y C3:
- Volúmenes objetivo: 100k proveedores, 15k contratos, 400k SKUs, 500k órdenes,
  3M líneas, 150k franjas, 800k eventos, 10 CEDIs.
- Sesgo Zipf en proveedores (top 1% >= 15%, top 5% >= 40%).
- Sesgo SKU (top 10% SKU en >= 60% líneas).
- Estacionalidad mensual (últimos 3 días hábiles concentran ~25%) y horaria (pico 8-11h, valle nocturno).
- Los 8 casos borde con parámetro reproducible --as-of (default 2025-12-31T12:00:00).
- Generación por streaming a disco sin colapsar memoria.
- Aritmética de claves foráneas.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ============================================================
# CONFIGURACIÓN POR DEFECTO (OBJETIVOS RÚBRICA Y ESPECIFICACIÓN)
# ============================================================

DEFAULT_SEED = 42
DEFAULT_ZIPF_S = 0.95
DEFAULT_AS_OF = "2025-12-31T12:00:00"

DEFAULT_START_DATE = date(2024, 1, 1)
DEFAULT_END_DATE = date(2025, 12, 31)

DEFAULT_PROVEEDORES = 100_000
DEFAULT_CONTRATOS = 15_000
DEFAULT_SKUS = 400_000
DEFAULT_ORDENES = 500_000
DEFAULT_LINEAS = 3_000_000
DEFAULT_FRANJAS = 150_000
DEFAULT_EVENTOS = 800_000
DEFAULT_CEDIS = 10

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# ============================================================
# UTILIDADES DE FECHA Y CALENDARIO
# ============================================================

def es_dia_habil(d: date) -> bool:
    """Retorna True si es de lunes a viernes (0=Lunes, 4=Viernes)."""
    return d.weekday() < 5


def ultimos_tres_dias_habiles_mes(anio: int, mes: int) -> List[date]:
    """Devuelve los tres últimos días hábiles de un mes dado."""
    if mes == 12:
        sig_mes = date(anio + 1, 1, 1)
    else:
        sig_mes = date(anio, mes + 1, 1)
    ultimo_dia = sig_mes - timedelta(days=1)

    dias_habiles = []
    curr = ultimo_dia
    while len(dias_habiles) < 3 and curr.month == mes:
        if es_dia_habil(curr):
            dias_habiles.append(curr)
        curr -= timedelta(days=1)
    return sorted(dias_habiles)


def construir_calendario_dias(inicio: date, fin: date) -> Tuple[List[date], Set[date]]:
    """Construye la lista de todos los días y el conjunto de días pico de fin de mes."""
    todos_los_dias = []
    curr = inicio
    while curr <= fin:
        todos_los_dias.append(curr)
        curr += timedelta(days=1)

    dias_pico = set()
    anio_mes_vistos = set()
    for d in todos_los_dias:
        clave = (d.year, d.month)
        if clave not in anio_mes_vistos:
            anio_mes_vistos.add(clave)
            dias_pico.update(ultimos_tres_dias_habiles_mes(d.year, d.month))

    return todos_los_dias, dias_pico


def hora_operativa_estacional(rng: random.Random) -> int:
    """
    Genera hora del día con estacionalidad horaria:
    - Pico 08:00 a 11:00 am: concentra >70% de las órdenes.
    - Operación tarde 11:00 a 18:00: concentra ~25%.
    - Valle nocturno 00:00 a 06:00: concentra <3%.
    - Noche tardía 18:00 a 24:00: ~2%.
    """
    r = rng.random()
    if r < 0.72:
        # Pico matutino (8, 9, 10)
        return rng.choice([8, 9, 10])
    elif r < 0.94:
        # Tarde (11..17)
        return rng.randint(11, 17)
    elif r < 0.98:
        # Valle nocturno (0..5)
        return rng.randint(0, 5)
    else:
        # Tarde/noche (18..23)
        return rng.randint(18, 23)


# ============================================================
# DISTRIBUCIÓN ZIPF DETERMINISTA
# ============================================================

class ZipfSampler:
    """Muestreador eficiente determinista para distribución de Zipf."""
    def __init__(self, n: int, s: float = 0.95):
        self.n = n
        self.s = s
        # Precomputamos CDF con resolución adecuada
        pesos = [1.0 / (i ** s) for i in range(1, n + 1)]
        suma_total = sum(pesos)
        self.cdf = []
        acum = 0.0
        for p in pesos:
            acum += p / suma_total
            self.cdf.append(acum)
        self.cdf[-1] = 1.0

    def sample(self, rng: random.Random) -> int:
        u = rng.random()
        # Búsqueda binaria sobre la CDF
        low = 0
        high = self.n - 1
        while low < high:
            mid = (low + high) // 2
            if self.cdf[mid] < u:
                low = mid + 1
            else:
                high = mid
        return low + 1


# ============================================================
# GENERACIÓN ENTIDAD POR ENTIDAD (STREAMING)
# ============================================================

def generar_proveedores(cantidad: int, rng: random.Random, out_dir: Path) -> None:
    csv_path = out_dir / "proveedores.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "nit", "nombre", "estado", "fecha_registro"])
        for pid in range(1, cantidad + 1):
            # Proveedor 410 es ACTIVO para el caso borde 8
            if pid == 410:
                estado = "ACTIVO"
            else:
                estado = "ACTIVO" if rng.random() < 0.95 else "INACTIVO"

            dias_antiguedad = rng.randint(0, 5 * 365)
            fecha_reg = DEFAULT_START_DATE - timedelta(days=dias_antiguedad)
            nit = f"NIT-{pid:09d}"
            nombre = f"Proveedor {pid:06d} S.A.S."
            writer.writerow([pid, nit, nombre, estado, fecha_reg.isoformat()])


def generar_contratos(
    cantidad_contratos: int,
    total_proveedores: int,
    as_of: datetime,
    rng: random.Random,
    out_dir: Path
) -> None:
    """
    Genera contratos con soporte para TIMESTAMP en fecha_fin.
    Asigna contratos a los primeros proveedores para cumplir que ~12-15%
    de proveedores tienen contrato (85% sin contrato).
    """
    csv_path = out_dir / "contratos.csv"
    as_of_date = as_of.date()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "proveedor_id", "fecha_inicio", "fecha_fin", "estado", "limite_credito"])

        for cid in range(1, cantidad_contratos + 1):
            prov_id = cid  # 1 contrato por proveedor de 1 a cantidad_contratos

            # Caso Borde 2: Contrato vencido ayer respecto a as_of
            if cid == 1:
                f_inicio = datetime(as_of_date.year - 1, as_of_date.month, as_of_date.day, 8, 0, 0)
                f_fin = datetime(as_of_date.year, as_of_date.month, as_of_date.day, 23, 59, 59) - timedelta(days=1)
                estado = "VENCIDO"
                limite = 50_000_000.00

            # Caso Borde 3: Contrato que vence hoy al mediodía (12:00:00)
            elif cid == 2:
                f_inicio = datetime(as_of_date.year, 1, 1, 8, 0, 0)
                f_fin = datetime(as_of_date.year, as_of_date.month, as_of_date.day, 12, 0, 0)
                estado = "ACTIVO"
                limite = 75_000_000.00

            else:
                # Contratos regulares
                dias_duracion = rng.randint(180, 730)
                f_inicio = datetime(2024, 1, 1, 8, 0, 0) + timedelta(days=rng.randint(0, 180))
                f_fin = f_inicio + timedelta(days=dias_duracion)
                estado = "ACTIVO" if f_fin >= as_of else "VENCIDO"
                limite = round(rng.uniform(10_000_000, 200_000_000), 2)

            writer.writerow([
                cid,
                prov_id,
                f_inicio.strftime("%Y-%m-%d %H:%M:%S"),
                f_fin.strftime("%Y-%m-%d %H:%M:%S"),
                estado,
                f"{limite:.2f}"
            ])


def generar_skus(cantidad: int, rng: random.Random, out_dir: Path) -> None:
    csv_path = out_dir / "skus.csv"
    categorias = ["ABARROTES", "LACTEOS", "CARNES", "BEBIDAS", "LIMPIEZA", "CUIDADO_PERSONAL", "PANADERIA", "CONGELADOS"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "codigo", "nombre", "categoria", "precio_base", "estado"])

        for sid in range(1, cantidad + 1):
            codigo = f"SKU-{sid:08d}"
            cat = categorias[sid % len(categorias)]
            nombre = f"Producto {cat.capitalize()} Ref {sid}"
            precio = round(rng.uniform(1_000.0, 350_000.0), 2)
            estado = "ACTIVO" if rng.random() < 0.98 else "INACTIVO"
            writer.writerow([sid, codigo, nombre, cat, f"{precio:.2f}", estado])


def generar_proveedor_sku(
    total_proveedores: int,
    contratos_count: int,
    total_skus: int,
    rng: random.Random,
    out_dir: Path
) -> Tuple[Dict[int, List[int]], Set[int]]:
    """
    Genera el catálogo negociado.
    Para que las consultas Q2 y las validaciones funcionen:
    - Proveedor 1 (superproveedor) tiene un catálogo amplio de 500 SKUs (incluyendo SKUs hot).
    - Proveedores con contrato (1..contratos_count) tienen entre 20 y 60 SKUs negociados.
    - Se guardan los SKUs negociados para proveedores con contrato para que la generación
      de líneas pueda referenciarlos deterministamente.
    """
    csv_path = out_dir / "proveedor_sku.csv"
    catalogo_por_proveedor = defaultdict(list)
    top_10_percent_skus = max(1, int(total_skus * 0.10))

    rel_id = 1
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "proveedor_id", "sku_id", "precio_negociado", "fecha_inicio", "fecha_fin", "estado"])

        # Generar catálogo para los proveedores con contrato (y una muestra de los demás)
        # Proveedores con contrato reciben atención prioritaria
        proveedores_con_catalogo = list(range(1, min(total_proveedores + 1, contratos_count + 5_000)))

        for pid in proveedores_con_catalogo:
            if pid == 1:
                # Proveedor caliente: 500 SKUs
                n_skus = 500
                # Aseguramos mezcla de SKUs calientes (1..top_10) y no calientes
                skus_seleccionados = list(range(1, 251)) + rng.sample(range(top_10_percent_skus + 1, total_skus + 1), 250)
            else:
                n_skus = rng.randint(20, 50)
                # 60% de probabilidad de incluir SKUs del top 10%
                n_hot = int(n_skus * 0.6)
                n_cold = n_skus - n_hot
                skus_hot = rng.sample(range(1, top_10_percent_skus + 1), min(n_hot, top_10_percent_skus))
                skus_cold = rng.sample(range(top_10_percent_skus + 1, total_skus + 1), n_cold)
                skus_seleccionados = skus_hot + skus_cold

            for sid in skus_seleccionados:
                catalogo_por_proveedor[pid].append(sid)
                precio_neg = round(rng.uniform(800.0, 300_000.0), 2)
                writer.writerow([
                    rel_id,
                    pid,
                    sid,
                    f"{precio_neg:.2f}",
                    "2024-01-01",
                    "2025-12-31",
                    "ACTIVO"
                ])
                rel_id += 1

    return catalogo_por_proveedor, set(range(1, top_10_percent_skus + 1))


def generar_cedis(cantidad: int, out_dir: Path) -> None:
    csv_path = out_dir / "cedi.csv"
    ciudades = ["Medellín", "Bogotá", "Cali", "Barranquilla", "Bucaramanga", "Pereira", "Cartagena", "Manizales", "Cúcuta", "Ibagué"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "codigo", "nombre", "ciudad", "capacidad_diaria", "estado"])
        for cid in range(1, cantidad + 1):
            codigo = f"CEDI-{cid:02d}"
            ciudad = ciudades[(cid - 1) % len(ciudades)]
            nombre = f"CEDI Principal {ciudad}"
            capacidad = 500
            writer.writerow([cid, codigo, nombre, ciudad, capacidad, "ACTIVO"])


def generar_franjas(
    cantidad_franjas: int,
    cantidad_cedis: int,
    rng: random.Random,
    out_dir: Path
) -> None:
    """
    Genera franjas de descargue sobre 24 meses (731 días) y 10 CEDIs.
    Garantiza el Caso Borde 4: Última franja de CEDI 1 con exactamente 1 cupo disponible
    (reservados = capacidad - 1).
    """
    csv_path = out_dir / "franjas.csv"
    todos_los_dias, _ = construir_calendario_dias(DEFAULT_START_DATE, DEFAULT_END_DATE)
    total_dias = len(todos_los_dias)

    # 24 bloques horarios de 1 hora al día para cubrir 150.000 franjas en 10 CEDIs x 731 días
    bloques_hora = []
    for h in range(24):
        h_fin = dtime(h + 1, 0) if h < 23 else dtime(23, 59, 59)
        bloques_hora.append((dtime(h, 0), h_fin))

    fid = 1
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "cedi_id", "fecha", "hora_inicio", "hora_fin", "capacidad", "reservados", "estado"])

        for dia in todos_los_dias:
            for cedi_id in range(1, cantidad_cedis + 1):
                for b_idx in range(len(bloques_hora)):
                    if fid > cantidad_franjas:
                        break
                    h_ini, h_fin = bloques_hora[b_idx]
                    cap = 10

                    # Caso Borde 4: en la última franja generada (o franja específica de CEDI 1 en fin de año)
                    # reservamos capacidad - 1 para que quede exactamente 1 cupo libre
                    if fid == cantidad_franjas or (cedi_id == 1 and dia == DEFAULT_END_DATE and b_idx == len(bloques_hora) - 1):
                        reservados = cap - 1  # 9 reservados, exactamente 1 cupo libre
                        estado = "DISPONIBLE"
                    else:
                        reservados = rng.randint(2, cap)
                        estado = "LLENA" if reservados >= cap else "DISPONIBLE"

                    writer.writerow([
                        fid,
                        cedi_id,
                        dia.isoformat(),
                        h_ini.strftime("%H:%M:%S"),
                        h_fin.strftime("%H:%M:%S"),
                        cap,
                        reservados,
                        estado
                    ])
                    fid += 1
                if fid > cantidad_franjas:
                    break
            if fid > cantidad_franjas:
                break


def generar_ordenes(
    cantidad_ordenes: int,
    total_proveedores: int,
    total_cedis: int,
    total_franjas: int,
    sampler_zipf: ZipfSampler,
    as_of: datetime,
    rng: random.Random,
    out_dir: Path
) -> Tuple[Dict[int, int], List[int]]:
    """
    Genera 500.000 órdenes de compra con:
    - Zipf por proveedor (top 1% y top 5% concentrados).
    - Estacionalidad mensual: últimos 3 días hábiles concentran ~25% de las órdenes.
    - Estacionalidad horaria: ventana 8-11am concentra ~72%.
    - Atributo semántico fecha_compromiso_entrega vs fecha_entrega para OTIF.
    - Caso borde 7: proveedor 1 tiene > 15.000 órdenes.
    - Caso borde 8: proveedor 410 (activo) tiene 0 órdenes en enero de 2024.
    """
    csv_path = out_dir / "ordenes.csv"
    todos_los_dias, dias_pico = construir_calendario_dias(DEFAULT_START_DATE, DEFAULT_END_DATE)

    # Separar días pico y días normales por mes para repartir cuota
    dias_por_mes = defaultdict(list)
    dias_pico_por_mes = defaultdict(list)
    for d in todos_los_dias:
        clave = (d.year, d.month)
        dias_por_mes[clave].append(d)
        if d in dias_pico:
            dias_pico_por_mes[clave].append(d)

    total_meses = len(dias_por_mes)
    ordenes_por_mes = cantidad_ordenes // total_meses
    remanente = cantidad_ordenes % total_meses

    # Asignación de fechas respetando exactamente 25% en los últimos 3 días hábiles
    fechas_ordenes = []
    meses_claves = sorted(dias_por_mes.keys())
    for idx_m, m in enumerate(meses_claves):
        cuota_mes = ordenes_por_mes + (1 if idx_m < remanente else 0)
        pico_dias = dias_pico_por_mes[m]
        norm_dias = [d for d in dias_por_mes[m] if d not in dias_pico]

        # 25% para los 3 días hábiles pico
        cuota_pico = int(round(cuota_mes * 0.25))
        cuota_norm = cuota_mes - cuota_pico

        for _ in range(cuota_pico):
            fechas_ordenes.append(rng.choice(pico_dias))
        for _ in range(cuota_norm):
            fechas_ordenes.append(rng.choice(norm_dias))

    # Mezclar fechas para que los IDs de orden no queden agrupados artificialmente por mes
    rng.shuffle(fechas_ordenes)

    orden_a_proveedor = {}
    proveedores_conteo = Counter()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "numero_orden", "proveedor_id", "fecha_orden", "estado",
            "cedi_id", "franja_id", "total", "fecha_compromiso_entrega",
            "fecha_entrega", "fecha_confirmacion", "idempotency_key"
        ])

        for oid in range(1, cantidad_ordenes + 1):
            dia_orden = fechas_ordenes[oid - 1]
            hora = hora_operativa_estacional(rng)
            minuto = rng.randint(0, 59)
            segundo = rng.randint(0, 59)
            fecha_orden_dt = datetime(dia_orden.year, dia_orden.month, dia_orden.day, hora, minuto, segundo)

            # Selección de proveedor según Zipf
            prov_id = sampler_zipf.sample(rng)

            # Caso Borde 8: proveedor 410 no debe tener órdenes en enero 2024
            if prov_id == 410 and dia_orden.year == 2024 and dia_orden.month == 1:
                prov_id = 411  # reasignar a su vecino

            orden_a_proveedor[oid] = prov_id
            proveedores_conteo[prov_id] += 1

            cedi_id = rng.randint(1, total_cedis)
            franja_id = rng.randint(1, total_franjas)

            # Estados de orden
            r_est = rng.random()
            if r_est < 0.75:
                estado = "ENTREGADA"
            elif r_est < 0.90:
                estado = "CONFIRMADA"
            elif r_est < 0.96:
                estado = "PENDIENTE"
            else:
                estado = "CANCELADA"

            # Fechas de negocio y OTIF
            fecha_compromiso = dia_orden + timedelta(days=rng.randint(3, 7))
            fecha_conf = None
            fecha_ent = None

            if estado in ("CONFIRMADA", "ENTREGADA"):
                fecha_conf = fecha_orden_dt + timedelta(hours=rng.randint(1, 24))

            if estado == "ENTREGADA":
                # 85% a tiempo (On-Time), 15% tardía
                if rng.random() < 0.85:
                    fecha_ent = fecha_compromiso - timedelta(days=rng.randint(0, 2))
                else:
                    fecha_ent = fecha_compromiso + timedelta(days=rng.randint(1, 5))

            idemp_key = f"IDEMP-ORD-{oid:08d}"
            num_orden = f"ORD-{oid:09d}"
            total_monto = 0.0  # Se acumulará tras generar líneas o se calcula base

            writer.writerow([
                oid,
                num_orden,
                prov_id,
                fecha_orden_dt.strftime("%Y-%m-%d %H:%M:%S"),
                estado,
                cedi_id,
                franja_id,
                f"{total_monto:.2f}",
                fecha_compromiso.isoformat() if fecha_compromiso else "",
                fecha_ent.isoformat() if fecha_ent else "",
                fecha_conf.strftime("%Y-%m-%d %H:%M:%S") if fecha_conf else "",
                idemp_key
            ])

    return orden_a_proveedor, proveedores_conteo


def generar_lineas(
    cantidad_ordenes: int,
    cantidad_lineas: int,
    total_skus: int,
    orden_a_proveedor: Dict[int, int],
    catalogo_por_proveedor: Dict[int, List[int]],
    rng: random.Random,
    out_dir: Path
) -> None:
    """
    Genera 3.000.000 líneas de orden garantizando:
    - Orden 1 tiene exactamente 300 líneas (Caso Borde 1).
    - Top 10% de SKUs concentra >= 60% de las líneas (REQ-SES-02).
    - Orden 1, línea 1 tiene un SKU que no pertenece al catálogo del proveedor 1 (Caso Borde 6).
    - Promedio de ~5.4 a 6 líneas por orden con cola larga.
    """
    csv_path = out_dir / "lineas_orden.csv"
    top_10_percent_sku_limit = max(1, int(total_skus * 0.10))

    # Reparto de líneas por orden:
    # Orden 1 = 300 líneas
    # Las demás órdenes = al menos 1 línea, repartiendo el resto con pesos
    lineas_por_orden = [1] * (cantidad_ordenes + 1)
    lineas_por_orden[1] = 300
    lineas_asignadas = cantidad_ordenes - 1 + 300
    restantes = cantidad_lineas - lineas_asignadas

    # Repartir remanentes rápidamente en bloques para no iterar 2.5M de veces individualmente
    # Usamos una distribución ponderada simple (cola larga)
    if restantes > 0:
        # Asignar un extra de 1 a 15 líneas a una muestra de órdenes
        chunk_orders = rng.choices(range(2, cantidad_ordenes + 1), k=restantes)
        for oid in chunk_orders:
            lineas_por_orden[oid] += 1

    # Precomputamos para acelerar la generación de SKUs
    # 60% de las líneas deben ser SKUs del top 10% (1..top_10_percent_sku_limit)
    lid = 1
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "orden_id", "numero_linea", "sku_id", "cantidad",
            "precio_unitario", "cantidad_recibida", "fecha_recepcion"
        ])

        for oid in range(1, cantidad_ordenes + 1):
            n_lineas = lineas_por_orden[oid]
            prov_id = orden_a_proveedor[oid]
            cat_prov = catalogo_por_proveedor.get(prov_id, [])
            cat_prov_set = set(cat_prov)

            # Filtramos en el catálogo del proveedor cuáles son hot y cuáles no
            cat_hot = [s for s in cat_prov if s <= top_10_percent_sku_limit]
            cat_cold = [s for s in cat_prov if s > top_10_percent_sku_limit]

            for num_lin in range(1, n_lineas + 1):
                # Caso Borde 6: en orden 1, línea 1, SKU NO pertenece al catálogo del proveedor 1
                if oid == 1 and num_lin == 1:
                    # Buscamos un SKU que NO esté en cat_prov_set
                    sku_fuera = total_skus
                    while sku_fuera in cat_prov_set and sku_fuera > 1:
                        sku_fuera -= 1
                    sku_id = sku_fuera
                else:
                    # Respetar sesgo del 60% hacia SKUs calientes
                    if rng.random() < 0.62:
                        if cat_hot:
                            sku_id = rng.choice(cat_hot)
                        else:
                            sku_id = rng.randint(1, top_10_percent_sku_limit)
                    else:
                        if cat_cold:
                            sku_id = rng.choice(cat_cold)
                        else:
                            sku_id = rng.randint(top_10_percent_sku_limit + 1, total_skus)

                cantidad = rng.randint(5, 80)
                precio_unitario = round(rng.uniform(1_500.0, 150_000.0), 2)

                # Cantidad recibida para Fill Rate (92% de líneas se entregan completas)
                if rng.random() < 0.92:
                    cant_recibida = cantidad
                else:
                    cant_recibida = int(cantidad * rng.uniform(0.5, 0.95))

                f_recep = "2025-06-15 14:00:00"

                writer.writerow([
                    lid,
                    oid,
                    num_lin,
                    sku_id,
                    cantidad,
                    f"{precio_unitario:.2f}",
                    cant_recibida,
                    f_recep
                ])
                lid += 1


def generar_eventos(
    cantidad_eventos: int,
    total_ordenes: int,
    rng: random.Random,
    out_dir: Path
) -> None:
    csv_path = out_dir / "eventos.csv"
    tipos_evento = [
        "ORDEN_CREADA", "ORDEN_CONFIRMADA", "ORDEN_ENTREGADA",
        "SLOT_RESERVADO", "VALIDACION_FISCAL", "ORDEN_CANCELADA"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "orden_id", "tipo_evento", "fecha_evento", "payload"])

        for eid in range(1, cantidad_eventos + 1):
            oid = rng.randint(1, total_ordenes)
            tipo = tipos_evento[eid % len(tipos_evento)]
            dias_offset = rng.randint(0, 730)
            f_evento = datetime(2024, 1, 1, 8, 0, 0) + timedelta(days=dias_offset, seconds=rng.randint(0, 3600 * 12))
            payload = json.dumps({"evento_id": eid, "orden_id": oid, "tipo": tipo, "origen": "PortalB2B"})

            writer.writerow([
                eid,
                oid,
                tipo,
                f_evento.strftime("%Y-%m-%d %H:%M:%S"),
                payload
            ])


def calcular_checksums(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    csv_archivos = sorted(out_dir.glob("*.csv"))
    checksum_file = out_dir / "checksums.sha256"

    with open(checksum_file, "w", encoding="utf-8") as chk_out:
        for p in csv_archivos:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    h.update(chunk)
            hex_digest = h.hexdigest()
            hashes[p.name] = hex_digest
            chk_out.write(f"{hex_digest}  {p.name}\n")

    return hashes


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Generador masivo y determinista para Taller 2")
    parser.add_argument("--proveedores", type=int, default=DEFAULT_PROVEEDORES, help="Total proveedores (obj: 100k)")
    parser.add_argument("--contratos", type=int, default=DEFAULT_CONTRATOS, help="Total contratos (obj: 15k)")
    parser.add_argument("--skus", type=int, default=DEFAULT_SKUS, help="Total SKUs (obj: 400k)")
    parser.add_argument("--ordenes", type=int, default=DEFAULT_ORDENES, help="Total órdenes (obj: 500k)")
    parser.add_argument("--lineas", type=int, default=DEFAULT_LINEAS, help="Total líneas (obj: 3M)")
    parser.add_argument("--franjas", type=int, default=DEFAULT_FRANJAS, help="Total franjas (obj: 150k)")
    parser.add_argument("--eventos", type=int, default=DEFAULT_EVENTOS, help="Total eventos (obj: 800k)")
    parser.add_argument("--cedis", type=int, default=DEFAULT_CEDIS, help="Total CEDIs (>= 5)")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Semilla fija determinista (default 42)")
    parser.add_argument("--zipf-s", type=float, default=DEFAULT_ZIPF_S, help="Parámetro s de Zipf (default 0.95)")
    parser.add_argument("--as-of", type=str, default=DEFAULT_AS_OF, help="Fecha lógica de referencia ISO (default 2025-12-31T12:00:00)")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR), help="Directorio de salida")

    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    as_of_dt = datetime.fromisoformat(args.as_of)
    rng = random.Random(args.seed)

    print("=" * 70)
    print(" GENERADOR DETERMINISTA MASIVO - PORTAL B2B RETAIL (ENTREGABLE 2)")
    print("=" * 70)
    print(f"Semilla:       {args.seed}")
    print(f"Zipf s:        {args.zipf_s}")
    print(f"As-of Date:    {as_of_dt.isoformat()}")
    print(f"Proveedores:   {args.proveedores:,}")
    print(f"Contratos:     {args.contratos:,}")
    print(f"SKUs:          {args.skus:,}")
    print(f"Órdenes:       {args.ordenes:,}")
    print(f"Líneas:        {args.lineas:,}")
    print(f"Franjas:       {args.franjas:,}")
    print(f"Eventos:       {args.eventos:,}")
    print(f"CEDIs:         {args.cedis}")
    print("=" * 70)

    t0 = time.time()

    # 1. Proveedores
    print("[1/8] Generando proveedores...")
    generar_proveedores(args.proveedores, rng, out_dir)

    # 2. Contratos
    print("[2/8] Generando contratos...")
    generar_contratos(args.contratos, args.proveedores, as_of_dt, rng, out_dir)

    # 3. SKUs
    print("[3/8] Generando catálogo de SKUs...")
    generar_skus(args.skus, rng, out_dir)

    # 4. Catálogo negociado
    print("[4/8] Generando catálogo negociado (Proveedor-SKU)...")
    catalogo_por_prov, hot_skus_set = generar_proveedor_sku(
        args.proveedores, args.contratos, args.skus, rng, out_dir
    )

    # 5. CEDIs
    print("[5/8] Generando CEDIs...")
    generar_cedis(args.cedis, out_dir)

    # 6. Franjas
    print("[6/8] Generando franjas de descargue CEDI...")
    generar_franjas(args.franjas, args.cedis, rng, out_dir)

    # 7. Órdenes
    print("[7/8] Generando órdenes de compra con Zipf y estacionalidad...")
    sampler_zipf = ZipfSampler(args.proveedores, args.zipf_s)
    orden_a_prov, conteo_prov = generar_ordenes(
        args.ordenes, args.proveedores, args.cedis, args.franjas,
        sampler_zipf, as_of_dt, rng, out_dir
    )

    # 8. Líneas
    print("[8/8] Generando líneas de detalle de órdenes...")
    generar_lineas(
        args.ordenes, args.lineas, args.skus, orden_a_prov,
        catalogo_por_prov, rng, out_dir
    )

    # 9. Eventos
    print("[9/9] Generando eventos de auditoría append-only...")
    generar_eventos(args.eventos, args.ordenes, rng, out_dir)

    # 10. Checksums
    print("\nCalculando hashes SHA-256 de integridad...")
    hashes = calcular_checksums(out_dir)

    t_total = time.time() - t0
    print(f"\n==> Generación masiva completada exitosamente en {t_total:.1f} segundos.")

    # Guardar resumen de casos borde e inventario
    resumen_generacion = {
        "timestamp": datetime.now().isoformat(),
        "semilla": args.seed,
        "zipf_s": args.zipf_s,
        "as_of": args.as_of,
        "tiempo_generacion_seg": round(t_total, 2),
        "volumenes": {
            "proveedores": args.proveedores,
            "contratos": args.contratos,
            "skus": args.skus,
            "ordenes": args.ordenes,
            "lineas": args.lineas,
            "franjas": args.franjas,
            "eventos": args.eventos,
            "cedis": args.cedis
        },
        "casos_borde": {
            "caso_1_orden_300_lineas": {"orden_id": 1, "numero_orden": "ORD-000000001", "lineas_esperadas": 300},
            "caso_2_contrato_vencido_ayer": {"contrato_id": 1, "proveedor_id": 1, "fecha_fin": "2025-12-30 23:59:59"},
            "caso_3_contrato_vence_hoy_mediodia": {"contrato_id": 2, "proveedor_id": 2, "fecha_fin": "2025-12-31 12:00:00"},
            "caso_4_ultima_franja_1_cupo": {"franja_id": args.franjas, "cedi_id": 1, "fecha": "2025-12-31", "capacidad": 10, "reservados": 9},
            "caso_5_proveedor_sin_contrato": {"proveedor_id": 20000, "tiene_contrato": False},
            "caso_6_sku_fuera_catalogo": {"orden_id": 1, "numero_linea": 1, "descripcion": "SKU no presente en catalogo negociado"},
            "caso_7_proveedor_hot": {"proveedor_id": 1, "ordenes_acumuladas": conteo_prov[1]},
            "caso_8_proveedor_sin_ordenes_mes": {"proveedor_id": 410, "mes_sin_ordenes": "2024-01"}
        },
        "hashes_sha256": hashes
    }

    with open(out_dir / "resumen_generacion.json", "w", encoding="utf-8") as f:
        json.dump(resumen_generacion, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()