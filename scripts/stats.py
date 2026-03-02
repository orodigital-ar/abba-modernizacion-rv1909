#!/usr/bin/env python3
"""
stats.py — Estadisticas de progreso del proyecto de modernizacion

Muestra el estado actual de cada fase y estadisticas generales.

Uso:
  python scripts/stats.py              # Resumen completo
  python scripts/stats.py --detalle    # Con breakdown por libro
"""

import json
import os
import sys
import argparse
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "datos")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

INPUT_FILE = os.path.join(DATA_DIR, "rv1909_strongs_full.ndjson")
FASE1_OUTPUT = os.path.join(OUTPUT_DIR, "fase1_ortografia", "fase1_output.ndjson")
FASE1_STATS = os.path.join(OUTPUT_DIR, "fase1_ortografia", "fase1_stats.json")
FASE2_OUTPUT = os.path.join(OUTPUT_DIR, "fase2_semantica")
FINAL_OUTPUT = os.path.join(OUTPUT_DIR, "final", "rv1909_modernizada.ndjson")


def count_lines(path):
    """Cuenta lineas no vacias en un NDJSON."""
    if not os.path.exists(path):
        return 0
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def count_by_book(path):
    """Cuenta versos por libro."""
    books = defaultdict(int)
    if not os.path.exists(path):
        return books
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            v = json.loads(line)
            books[v.get("book", "?")] += 1
    return books


def main():
    parser = argparse.ArgumentParser(description="Stats de modernizacion RV1909")
    parser.add_argument("--detalle", action="store_true", help="Breakdown por libro")
    args = parser.parse_args()

    print("=" * 55)
    print("  MODERNIZACION RV1909 — Estadisticas de progreso")
    print("=" * 55)

    # Input
    total_input = count_lines(INPUT_FILE)
    print(f"\n  Input: {total_input:,} versos en rv1909_strongs_full.ndjson")

    if total_input == 0:
        print("  ERROR: No se encontro archivo de input")
        return

    # Fase 1
    print(f"\n  --- Fase 1: Ortografia ---")
    if os.path.exists(FASE1_STATS):
        with open(FASE1_STATS, "r", encoding="utf-8") as f:
            stats = json.load(f)
        total = stats.get("total", 0)
        cambiados = stats.get("cambiados", 0)
        necesitan = stats.get("necesitan_fase2", 0)
        print(f"  Procesados:        {total:,}")
        print(f"  Cambiados:         {cambiados:,} ({cambiados/total*100:.1f}%)" if total else "")
        print(f"  Necesitan fase 2:  {necesitan:,} ({necesitan/total*100:.1f}%)" if total else "")
    elif os.path.exists(FASE1_OUTPUT):
        total = count_lines(FASE1_OUTPUT)
        print(f"  Output existe: {total:,} versos (sin stats detalladas)")
    else:
        print(f"  Pendiente ({total_input:,} versos)")

    # Fase 2
    print(f"\n  --- Fase 2: Semantica ---")
    fase2_files = []
    if os.path.exists(FASE2_OUTPUT):
        fase2_files = [f for f in os.listdir(FASE2_OUTPUT) if f.endswith(".ndjson")]
    if fase2_files:
        total_f2 = sum(count_lines(os.path.join(FASE2_OUTPUT, f)) for f in fase2_files)
        print(f"  {len(fase2_files)} archivos, {total_f2:,} versos procesados")
    else:
        print(f"  Pendiente")

    # Fase 3
    print(f"\n  --- Fase 3: Revision humana ---")
    print(f"  Pendiente")

    # Fase 4 / Final
    print(f"\n  --- Fase 4: Validacion / Final ---")
    if os.path.exists(FINAL_OUTPUT):
        total_final = count_lines(FINAL_OUTPUT)
        print(f"  Output final: {total_final:,} versos")
    else:
        print(f"  Pendiente")

    # Detalle por libro
    if args.detalle:
        print(f"\n  --- Detalle por libro ---")
        books = count_by_book(INPUT_FILE)
        for book in sorted(books.keys(), key=lambda b: books[b], reverse=True):
            print(f"    {book:6s}: {books[book]:5,} versos")

    print(f"\n{'='*55}")


if __name__ == "__main__":
    main()
