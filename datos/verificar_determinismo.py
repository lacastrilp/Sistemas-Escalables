#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Taller 2 - Demostración Automatizada de Determinismo (C3)
Ejecuta dos generaciones independientes con la misma semilla (seed=42) y configuración idéntica.
Calcula y compara los hashes SHA-256 archivo por archivo para demostrar determinismo estricto.
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "determinismo"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def calcular_hashes_directorio(dir_path: Path) -> dict:
    hashes = {}
    for p in sorted(dir_path.glob("*.csv")):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        hashes[p.name] = h.hexdigest()
    return hashes

def main():
    print("======================================================================")
    print(" DEMOSTRACIÓN DE DETERMINISMO: 2 CORRIDAS INDEPENDIENTES (--seed 42)")
    print("======================================================================")

    # Creamos dos directorios temporales aislados
    dir1 = Path(tempfile.mkdtemp(prefix="det_run1_"))
    dir2 = Path(tempfile.mkdtemp(prefix="det_run2_"))

    # Configuración de prueba de determinismo
    params = [
        "--proveedores", "2000",
        "--contratos", "500",
        "--skus", "5000",
        "--ordenes", "5000",
        "--lineas", "25000",
        "--franjas", "2000",
        "--eventos", "5000",
        "--seed", "42",
        "--as-of", "2025-12-31T12:00:00"
    ]

    try:
        print("\n[Ejecutando Corrida 1 con seed=42...]")
        cmd1 = [sys.executable, str(ROOT_DIR / "datos" / "generar.py"), "--output-dir", str(dir1)] + params
        subprocess.run(cmd1, check=True, stdout=subprocess.DEVNULL)
        hashes1 = calcular_hashes_directorio(dir1)

        print("[Ejecutando Corrida 2 con seed=42...]")
        cmd2 = [sys.executable, str(ROOT_DIR / "datos" / "generar.py"), "--output-dir", str(dir2)] + params
        subprocess.run(cmd2, check=True, stdout=subprocess.DEVNULL)
        hashes2 = calcular_hashes_directorio(dir2)

        print("\nComparando hashes SHA-256 de ambas corridas:")
        print(f"{'Archivo CSV':<22} | {'Hash Corrida 1':<24} | {'Hash Corrida 2':<24} | {'Igualdad':<8}")
        print("-" * 86)

        todos_iguales = True
        comparacion = {}

        for fname in sorted(hashes1.keys()):
            h1 = hashes1[fname]
            h2 = hashes2.get(fname, "")
            igual = (h1 == h2)
            if not igual:
                todos_iguales = False
            h1_short = h1[:16] + "..."
            h2_short = h2[:16] + "..."
            print(f"{fname:<22} | {h1_short:<24} | {h2_short:<24} | {'PASA' if igual else 'FALLA'}")
            comparacion[fname] = {
                "hash_corrida_1": h1,
                "hash_corrida_2": h2,
                "identicos": igual
            }

        resultado_json = {
            "semilla": 42,
            "determinismo_demostrado": todos_iguales,
            "archivos_comparados": comparacion
        }

        with open(OUTPUT_DIR / "hashes_comparacion.json", "w", encoding="utf-8") as f:
            json.dump(resultado_json, f, indent=2)

        print("=" * 86)
        if todos_iguales:
            print("==> RESULTADO: DETERMINISMO DEMOSTRADO AL 100% (Todos los hashes coinciden).")
        else:
            print("==> RESULTADO: FALLA EN DETERMINISMO (Hashes discrepantes).")
            sys.exit(1)

    finally:
        shutil.rmtree(dir1, ignore_errors=True)
        shutil.rmtree(dir2, ignore_errors=True)

if __name__ == "__main__":
    main()
