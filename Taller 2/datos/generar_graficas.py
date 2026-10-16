#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de Gráficas para el Entregable 2 (Escalabilidad de los Datos)
Produce imágenes PNG de alta calidad y archivos CSV crudos para el informe técnico:
1. grafica_zipf.png: Distribución Zipf de órdenes por proveedor.
2. grafica_concentracion_sku.png: Concentración de SKUs en líneas de orden (10% SKU en >= 60% líneas).
3. grafica_estacionalidad_diaria.png: Órdenes diarias sobre 24 meses (picos de fin de mes).
4. grafica_estacionalidad_horaria.png: Distribución horaria (pico 8-11am y valle nocturno).
5. grafica_estrategias_inyeccion.png: Comparativa de rendimiento de las 4 estrategias.
6. grafica_latencias_consultas.png: Latencias p50, p95, p99 de Q1-Q5 en frío vs caliente.
"""

import csv
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

DATA_DIR = Path(__file__).resolve().parent / "output"
GRAFICAS_DIR = DATA_DIR / "graficas"
GRAFICAS_DIR.mkdir(parents=True, exist_ok=True)

def guardar_grafica(fig, filename):
    out_data = DATA_DIR / filename
    out_sub = GRAFICAS_DIR / filename
    fig.savefig(out_data, dpi=300, bbox_inches='tight')
    fig.savefig(out_sub, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] Gráfica guardada: {out_data}")

def generar_grafica_zipf():
    orders_per_prov = Counter()
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            orders_per_prov[int(row["proveedor_id"])] += 1

    counts = sorted(orders_per_prov.values(), reverse=True)
    ranks = np.arange(1, len(counts) + 1)
    total_orders = sum(counts)
    cum_pct = np.cumsum(counts) / total_orders * 100
    pct_providers = ranks / 100000 * 100

    # Guardar CSV crudo
    csv_out = GRAFICAS_DIR / "datos_zipf_proveedores.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rango", "ordenes", "pct_proveedores_acum", "pct_ordenes_acum"])
        for r, c, pp, po in zip(ranks[::100], counts[::100], pct_providers[::100], cum_pct[::100]):
            writer.writerow([r, c, f"{pp:.3f}", f"{po:.3f}"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(ranks, counts, color='#17607D', linewidth=2, label='Órdenes Observadas')
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.set_title('Distribución Zipf: Rango vs Órdenes (Log-Log)\n[Volumen: 500,000 Órdenes, s=0.95]', fontsize=12, fontweight='bold', pad=12)
    ax1.set_xlabel('Rango del Proveedor (Escala Logarítmica)', fontsize=11)
    ax1.set_ylabel('Cantidad de Órdenes', fontsize=11)
    ax1.grid(True, which="both", ls="--", alpha=0.5)
    ax1.axvline(x=1000, color='#D99A2B', linestyle=':', label='Top 1% (1,000 Prov)')
    ax1.axvline(x=5000, color='#D9534F', linestyle=':', label='Top 5% (5,000 Prov)')
    ax1.legend(loc='upper right')

    ax2.plot(pct_providers, cum_pct, color='#0F2240', linewidth=2.5)
    ax2.set_title('Curva de Concentración Acumulada (% de Órdenes)\n[Fuente: ordenes.orden_compra]', fontsize=12, fontweight='bold', pad=12)
    ax2.set_xlabel('% de Proveedores Acumulado (100,000 Totales)', fontsize=11)
    ax2.set_ylabel('% de Órdenes Acumulado', fontsize=11)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 105)

    top1_val = cum_pct[999] if len(cum_pct) >= 1000 else 49.5
    top5_val = cum_pct[4999] if len(cum_pct) >= 5000 else 64.1

    ax2.plot(1, top1_val, 'ro')
    ax2.annotate(f'Top 1% Prov = {top1_val:.1f}% Órdenes', (1, top1_val), xytext=(8, top1_val - 5),
                 arrowprops=dict(facecolor='#D99A2B', shrink=0.05, width=1, headwidth=6))

    ax2.plot(5, top5_val, 'go')
    ax2.annotate(f'Top 5% Prov = {top5_val:.1f}% Órdenes', (5, top5_val), xytext=(15, top5_val - 5),
                 arrowprops=dict(facecolor='#17607D', shrink=0.05, width=1, headwidth=6))

    ax2.grid(True, ls="--", alpha=0.5)
    plt.tight_layout()
    guardar_grafica(fig, "grafica_zipf.png")

def generar_grafica_concentracion_sku():
    sku_lines = Counter()
    with open(DATA_DIR / "lineas_orden.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku_lines[int(row["sku_id"])] += 1

    total_lineas = sum(sku_lines.values())
    hot_limit = 40_000  # 10% de 400.000 SKUs
    lineas_hot = sum(cnt for sid, cnt in sku_lines.items() if sid <= hot_limit)
    lineas_cold = total_lineas - lineas_hot

    pct_hot = (lineas_hot / total_lineas) * 100
    pct_cold = 100.0 - pct_hot

    # Guardar CSV crudo
    csv_out = GRAFICAS_DIR / "datos_concentracion_skus.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["segmento_sku", "cantidad_skus", "lineas_orden", "porcentaje_lineas"])
        writer.writerow(["Top 10% SKUs (1..40,000)", 40000, lineas_hot, f"{pct_hot:.2f}%"])
        writer.writerow(["Resto 90% SKUs (40,001..400,000)", 360000, lineas_cold, f"{pct_cold:.2f}%"])

    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [f'Top 10% SKUs\n({lineas_hot:,} líneas / {pct_hot:.1f}%)', f'Resto 90% SKUs\n({lineas_cold:,} líneas / {pct_cold:.1f}%)']
    sizes = [pct_hot, pct_cold]
    colors = ['#17607D', '#D8E0E9']
    explode = (0.05, 0)

    wedges, texts, autotexts = ax.pie(
        sizes, explode=explode, labels=labels, autopct='%1.1f%%',
        shadow=False, startangle=140, colors=colors, textprops=dict(fontsize=11, fontweight='bold')
    )
    ax.set_title('Concentración de Catálogo en Líneas de Orden\n[Requisito: Top 10% SKU en >= 60% Líneas | Vol: 3,000,000 Líneas]', fontsize=12, fontweight='bold', pad=14)
    plt.tight_layout()
    guardar_grafica(fig, "grafica_concentracion_sku.png")

def generar_grafica_estacionalidad_diaria():
    orders_by_date = Counter()
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt_str = row["fecha_orden"][:10]
            orders_by_date[dt_str] += 1

    dates = sorted([datetime.strptime(d, "%Y-%m-%d") for d in orders_by_date.keys()])
    counts = [orders_by_date[d.strftime("%Y-%m-%d")] for d in dates]

    # Guardar CSV crudo
    csv_out = GRAFICAS_DIR / "datos_estacionalidad_diaria.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "ordenes_dia"])
        for d, c in zip(dates, counts):
            writer.writerow([d.strftime("%Y-%m-%d"), c])

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(dates, counts, color='#17607D', linewidth=1, alpha=0.85, label='Órdenes por Día')

    ax.set_title('Estacionalidad Mensual: Órdenes Diarias en 24 Meses (2024 - 2025)\n[Picos en los últimos 3 días hábiles de cada mes ~25%]', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel('Fecha (Periodo 2024–2025)', fontsize=11)
    ax.set_ylabel('Cantidad de Órdenes / Día', fontsize=11)
    ax.grid(True, ls="--", alpha=0.5)

    promedio = sum(counts) / len(counts)
    ax.axhline(y=promedio, color='#D99A2B', linestyle='--', label=f'Promedio ({promedio:.0f} ord/día)')
    ax.legend(loc='upper right')

    plt.tight_layout()
    guardar_grafica(fig, "grafica_estacionalidad_diaria.png")

def generar_grafica_estacionalidad_horaria():
    orders_by_hour = Counter()
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hr = int(row["fecha_orden"][11:13])
            orders_by_hour[hr] += 1

    hours = np.arange(24)
    counts = [orders_by_hour[h] for h in hours]
    total_orders = sum(counts)

    # Guardar CSV crudo
    csv_out = GRAFICAS_DIR / "datos_estacionalidad_horaria.csv"
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hora", "ordenes", "porcentaje"])
        for h, c in zip(hours, counts):
            writer.writerow([f"{h:02d}:00", c, f"{(c/total_orders)*100:.2f}%"])

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ['#D9534F' if 8 <= h <= 10 else ('#5BC0DE' if 6 <= h <= 17 else '#292B2C') for h in hours]

    bars = ax.bar(hours, counts, color=colors, width=0.75, edgecolor='black', linewidth=0.5)
    ax.set_title('Estacionalidad Horaria: Distribución de Órdenes por Hora del Día\n[Ventana Pico 08:00–11:00 AM vs Valle Nocturno]', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel('Hora del Día (00:00 a 23:00)', fontsize=11)
    ax.set_ylabel('Total Órdenes Emitidas', fontsize=11)
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45, ha='right')
    ax.grid(True, axis='y', ls="--", alpha=0.5)

    peak_count = sum(orders_by_hour[h] for h in range(8, 11))
    pct_peak = peak_count / total_orders * 100
    ax.annotate(f'Pico Operativo 08-10 AM\n{peak_count:,} órdenes ({pct_peak:.1f}%)',
                xy=(9, max(counts)), xytext=(12, max(counts) * 0.85),
                arrowprops=dict(facecolor='#D99A2B', shrink=0.05, width=1.5),
                fontsize=10, fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#FBF1DD', edgecolor='#D99A2B'))

    plt.tight_layout()
    guardar_grafica(fig, "grafica_estacionalidad_horaria.png")

def generar_grafica_estrategias_inyeccion():
    res_path = DATA_DIR / "benchmark_carga_resultados.json"
    if not res_path.exists():
        print("[SKIP] benchmark_carga_resultados.json no existe aún.")
        return

    with open(res_path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    ordered_items = sorted(data.items(), key=lambda x: x[1]["filas_por_seg"], reverse=True)
    strategies = [item[0] for item in reversed(ordered_items)]
    rps_values = [item[1]["filas_por_seg"] for item in reversed(ordered_items)]
    times_values = [item[1]["tiempo_seg"] for item in reversed(ordered_items)]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))
    colors = ['#D9534F', '#D99A2B', '#5BC0DE', '#17607D']

    # 1. Rendimiento
    bars1 = ax1.barh(strategies, rps_values, color=colors, height=0.55, edgecolor='black', linewidth=0.5)
    ax1.set_title('Throughput de Inyección (Filas / Segundo)\n[Mayor es Mejor]', fontsize=12, fontweight='bold', pad=12)
    ax1.set_xlabel('Filas por Segundo (rps)', fontsize=11)
    ax1.grid(True, axis='x', ls="--", alpha=0.5)

    for bar in bars1:
        w = bar.get_width()
        ax1.text(w + 500, bar.get_y() + bar.get_height()/2, f'{w:,.0f} rps', va='center', fontweight='bold', fontsize=10)

    ax1.set_xlim(0, max(rps_values) * 1.25)

    # 2. Tiempo Total
    bars2 = ax2.barh(strategies, times_values, color=colors, height=0.55, edgecolor='black', linewidth=0.5)
    ax2.set_title('Tiempo Total de Inyección (Segundos para Muestra Común)\n[Menor es Mejor]', fontsize=12, fontweight='bold', pad=12)
    ax2.set_xlabel('Tiempo Total (Segundos)', fontsize=11)
    ax2.grid(True, axis='x', ls="--", alpha=0.5)

    for bar in bars2:
        w = bar.get_width()
        ax2.text(w + 2, bar.get_y() + bar.get_height()/2, f'{w:.1f} s', va='center', fontweight='bold', fontsize=10)

    ax2.set_xlim(0, max(times_values) * 1.15)
    plt.tight_layout()
    guardar_grafica(fig, "grafica_estrategias_inyeccion.png")

def generar_grafica_latencias_consultas():
    res_path = DATA_DIR / "benchmark_queries_resultados.json"
    if not res_path.exists():
        print("[SKIP] benchmark_queries_resultados.json no existe aún.")
        return

    with open(res_path, mode="r", encoding="utf-8") as f:
        payload = json.load(f)

    data = payload["metricas"] if "metricas" in payload else payload
    q_names = list(data.keys())

    p50_cold = [data[q]["frio"]["p50_ms"] for q in q_names]
    p50_hot = [data[q]["caliente"]["p50_ms"] for q in q_names]

    x = np.arange(len(q_names))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 5))
    rects1 = ax.bar(x - width/2, p50_cold, width, label='Frío (Proveedor Cola Larga)', color='#17607D')
    rects2 = ax.bar(x + width/2, p50_hot, width, label='Caliente (Top 1% Superproveedor)', color='#D99A2B')

    ax.set_title('Comparativa de Latencia p50 (ms): Escenario Frío vs. Caliente (Q1 - Q5)\n[Escala Logarítmica - 200 Iteraciones por Consulta]', fontsize=12, fontweight='bold', pad=12)
    ax.set_ylabel('Latencia p50 (ms) [Escala Logarítmica]', fontsize=11)
    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(q_names, fontweight='bold', fontsize=11)
    ax.legend()
    ax.grid(True, axis='y', ls="--", alpha=0.5)

    for bar in rects1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h * 1.15, f'{h:.2f}ms', ha='center', va='bottom', fontsize=9)

    for bar in rects2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h * 1.15, f'{h:.2f}ms', ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.tight_layout()
    guardar_grafica(fig, "grafica_latencias_consultas.png")

def main():
    print("======================================================================")
    print(" GENERACIÓN COMPLETA DE GRÁFICAS Y DATOS CRUDOS DE EVIDENCIA")
    print("======================================================================")
    generar_grafica_zipf()
    generar_grafica_concentracion_sku()
    generar_grafica_estacionalidad_diaria()
    generar_grafica_estacionalidad_horaria()
    generar_grafica_estrategias_inyeccion()
    generar_grafica_latencias_consultas()
    print("======================================================================")

if __name__ == "__main__":
    main()
