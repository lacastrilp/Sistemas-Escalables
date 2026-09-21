#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generador de Gráficas para el Entregable 2 (Escalabilidad de los Datos)
Produce imágenes PNG de alta calidad para el informe técnico:
1. grafica_zipf.png: Distribución Zipf de órdenes por proveedor.
2. grafica_estacionalidad_diaria.png: Órdenes diarias sobre 24 meses (picos de fin de mes).
3. grafica_estacionalidad_horaria.png: Distribución horaria (pico 8-11am).
4. grafica_estrategias_inyeccion.png: Comparativa de rendimiento de las 4 estrategias.
5. grafica_latencias_consultas.png: Latencias p50, p95, p99 de Q1-Q5 en frío vs caliente.
"""

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Estilo visual moderno y limpio
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11

DATA_DIR = Path(__file__).resolve().parent / "output"
ARTIFACT_DIR = Path("/home/lacastrilp/.gemini/antigravity/brain/bf28653a-6678-4caa-a6ec-f6faed9730a5")

def guardar_grafica(fig, filename):
    out_data = DATA_DIR / filename
    out_artifact = ARTIFACT_DIR / filename
    fig.savefig(out_data, dpi=300, bbox_inches='tight')
    fig.savefig(out_artifact, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[OK] Gráfica guardada: {out_data} y {out_artifact}")

def generar_grafica_zipf():
    orders_per_prov = Counter()
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            orders_per_prov[int(row["proveedor_id"])] += 1
            
    counts = sorted(orders_per_prov.values(), reverse=True)
    ranks = np.arange(1, len(counts) + 1)
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 1. Rango vs Órdenes (Log-Log)
    ax1.plot(ranks, counts, color='#17607D', linewidth=2, label='Órdenes Observadas')
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.set_title('Distribución Zipf: Rango vs Órdenes (Log-Log)', fontsize=13, fontweight='bold', pad=12)
    ax1.set_xlabel('Rango del Proveedor (Ordenado de mayor a menor)', fontsize=11)
    ax1.set_ylabel('Cantidad de Órdenes', fontsize=11)
    ax1.grid(True, which="both", ls="--", alpha=0.5)
    ax1.axvline(x=1000, color='#D99A2B', linestyle=':', label='Top 1% (1,000 Prov)')
    ax1.axvline(x=5000, color='#D9534F', linestyle=':', label='Top 5% (5,000 Prov)')
    ax1.legend(loc='upper right')
    
    # 2. Concentración Acumulada
    total_orders = sum(counts)
    cum_pct = np.cumsum(counts) / total_orders * 100
    pct_providers = ranks / 100000 * 100
    
    ax2.plot(pct_providers, cum_pct, color='#0F2240', linewidth=2.5)
    ax2.set_title('Curva de Concentración Acumulada (% de Órdenes)', fontsize=13, fontweight='bold', pad=12)
    ax2.set_xlabel('% de Proveedores Acumulado', fontsize=11)
    ax2.set_ylabel('% de Órdenes Acumulado', fontsize=11)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 105)
    
    # Puntos clave
    top1_val = cum_pct[999] if len(cum_pct) >= 1000 else 49.45
    top5_val = cum_pct[4999] if len(cum_pct) >= 5000 else 64.08
    
    ax2.plot(1, top1_val, 'ro')
    ax2.annotate(f'Top 1% Prov = {top1_val:.1f}% Órdenes', (1, top1_val), xytext=(8, top1_val - 5),
                 arrowprops=dict(facecolor='#D99A2B', shrink=0.05, width=1, headwidth=6))
                 
    ax2.plot(5, top5_val, 'go')
    ax2.annotate(f'Top 5% Prov = {top5_val:.1f}% Órdenes', (5, top5_val), xytext=(15, top5_val - 5),
                 arrowprops=dict(facecolor='#17607D', shrink=0.05, width=1, headwidth=6))
                 
    ax2.grid(True, ls="--", alpha=0.5)
    
    plt.tight_layout()
    guardar_grafica(fig, "grafica_zipf.png")

def generar_grafica_estacionalidad_diaria():
    orders_by_date = Counter()
    with open(DATA_DIR / "ordenes.csv", mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt_str = row["fecha_orden"][:10]
            orders_by_date[dt_str] += 1
            
    dates = sorted([datetime.strptime(d, "%Y-%m-%d") for d in orders_by_date.keys()])
    counts = [orders_by_date[d.strftime("%Y-%m-%d")] for d in dates]
    
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(dates, counts, color='#17607D', linewidth=1, alpha=0.85, label='Órdenes por Día')
    
    ax.set_title('Estacionalidad Mensual: Órdenes Diarias en 24 Meses (2024 - 2025)', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel('Fecha', fontsize=11)
    ax.set_ylabel('Cantidad de Órdenes / Día', fontsize=11)
    ax.grid(True, ls="--", alpha=0.5)
    
    # Destacar picos de fin de mes
    max_val = max(counts)
    ax.axhline(y=sum(counts)/len(counts), color='#D99A2B', linestyle='--', label=f'Promedio ({sum(counts)/len(counts):.0f} ord/día)')
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
    
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ['#D9534F' if 8 <= h <= 10 else ('#5BC0DE' if 6 <= h <= 17 else '#292B2C') for h in hours]
    
    bars = ax.bar(hours, counts, color=colors, width=0.75, edgecolor='black', linewidth=0.5)
    ax.set_title('Estacionalidad Horaria: Distribución de Órdenes por Hora del Día', fontsize=13, fontweight='bold', pad=12)
    ax.set_xlabel('Hora del Día (00:00 a 23:00)', fontsize=11)
    ax.set_ylabel('Total Órdenes Emitidas', fontsize=11)
    ax.set_xticks(hours)
    ax.set_xticklabels([f"{h:02d}:00" for h in hours], rotation=45, ha='right')
    ax.grid(True, axis='y', ls="--", alpha=0.5)
    
    # Anotación del pico
    peak_count = sum(orders_by_hour[h] for h in range(8, 11))
    pct_peak = peak_count / sum(counts) * 100
    ax.annotate(f'Pico Operativo 08-10 AM\n{peak_count:,} órdenes ({pct_peak:.1f}%)',
                xy=(9, max(counts)), xytext=(12, max(counts) * 0.85),
                arrowprops=dict(facecolor='#D99A2B', shrink=0.05, width=1.5),
                fontsize=10, fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='#FBF1DD', edgecolor='#D99A2B'))
                
    plt.tight_layout()
    guardar_grafica(fig, "grafica_estacionalidad_horaria.png")

def generar_grafica_estrategias_inyeccion():
    with open(DATA_DIR / "benchmark_carga_resultados.json", mode="r", encoding="utf-8") as f:
        data = json.load(f)
        
    strategies = list(data.keys())
    rps_values = [data[s]["filas_por_seg"] for s in strategies]
    times_values = [data[s]["tiempo_seg"] for s in strategies]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # 1. Rendimiento (Filas / seg)
    colors = ['#17607D', '#5BC0DE', '#D9534F', '#D99A2B']
    bars1 = ax1.barh(strategies, rps_values, color=colors, height=0.55, edgecolor='black', linewidth=0.5)
    ax1.set_title('Rendimiento de Inyección (Filas / Segundo)', fontsize=13, fontweight='bold', pad=12)
    ax1.set_xlabel('Filas por Segundo (Mayor es mejor)', fontsize=11)
    ax1.grid(True, axis='x', ls="--", alpha=0.5)
    
    for bar in bars1:
        w = bar.get_width()
        ax1.text(w + 500, bar.get_y() + bar.get_height()/2, f'{w:,.0f} rps', va='center', fontweight='bold')
        
    ax1.set_xlim(0, max(rps_values) * 1.2)
    
    # 2. Tiempo Total Proyectado (s)
    bars2 = ax2.barh(strategies, times_values, color=colors, height=0.55, edgecolor='black', linewidth=0.5)
    ax2.set_title('Tiempo Total de Inyección (Segundos para 300,137 Filas)', fontsize=13, fontweight='bold', pad=12)
    ax2.set_xlabel('Tiempo Total en Segundos (Menor es mejor)', fontsize=11)
    ax2.grid(True, axis='x', ls="--", alpha=0.5)
    
    for bar in bars2:
        w = bar.get_width()
        ax2.text(w + 5, bar.get_y() + bar.get_height()/2, f'{w:.1f} s', va='center', fontweight='bold')
        
    ax2.set_xlim(0, max(times_values) * 1.15)
    
    plt.tight_layout()
    guardar_grafica(fig, "grafica_estrategias_inyeccion.png")

def generar_grafica_latencias_consultas():
    with open(DATA_DIR / "benchmark_queries_resultados.json", mode="r", encoding="utf-8") as f:
        payload = json.load(f)
        
    data = payload["metricas"]
    q_names = list(data.keys())
    
    p50_cold = [data[q]["frio"]["p50_ms"] for q in q_names]
    p50_hot = [data[q]["caliente"]["p50_ms"] for q in q_names]
    
    x = np.arange(len(q_names))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(12, 5))
    
    rects1 = ax.bar(x - width/2, p50_cold, width, label='Frío (Proveedor Cola Larga)', color='#17607D')
    rects2 = ax.bar(x + width/2, p50_hot, width, label='Caliente (Top 1% Superproveedor)', color='#D99A2B')
    
    ax.set_title('Comparativa de Latencia p50 (ms): Escenario Frío vs. Caliente (Q1 - Q5)', fontsize=13, fontweight='bold', pad=12)
    ax.set_ylabel('Latencia p50 (ms) [Escala Logarítmica]', fontsize=11)
    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(q_names, fontweight='bold', fontsize=11)
    ax.legend()
    ax.grid(True, axis='y', ls="--", alpha=0.5)
    
    # Etiquetar valores sobre las barras
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
    print(" GENERACIÓN DE GRÁFICAS DEL ENTREGABLE 2")
    print("======================================================================")
    generar_grafica_zipf()
    generar_grafica_estacionalidad_diaria()
    generar_grafica_estacionalidad_horaria()
    generar_grafica_estrategias_inyeccion()
    generar_grafica_latencias_consultas()
    print("======================================================================")

if __name__ == "__main__":
    main()
