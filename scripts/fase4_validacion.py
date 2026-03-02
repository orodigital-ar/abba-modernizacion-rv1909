#!/usr/bin/env python3
"""
fase4_validacion.py — Validacion de consistencia (Fase 4)

Verifica que la modernizacion completa es consistente:
- Mismo Strong's → misma traduccion en contextos equivalentes
- No se perdieron versos
- Formato NDJSON valido
- Estadisticas comparativas

Estado: SKELETON — pendiente implementacion completa.

Uso futuro:
  python scripts/fase4_validacion.py                     # Validacion completa
  python scripts/fase4_validacion.py --check-strongs     # Solo consistencia Strong's
  python scripts/fase4_validacion.py --check-coverage    # Solo cobertura de versos
"""

import json
import os
import sys
import argparse
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
DATA_DIR = os.path.join(PROJECT_DIR, "datos")
INPUT_FILE = os.path.join(DATA_DIR, "rv1909_strongs_full.ndjson")


def check_coverage(final_path, input_path):
    """Verifica que no se perdieron versos."""
    input_refs = set()
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            v = json.loads(line)
            ref = f"{v['book']}_{v['chapter']}_{v['verse']}"
            input_refs.add(ref)

    final_refs = set()
    with open(final_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            v = json.loads(line)
            ref = f"{v['book']}_{v['chapter']}_{v['verse']}"
            final_refs.add(ref)

    missing = input_refs - final_refs
    extra = final_refs - input_refs

    return {
        "input_total": len(input_refs),
        "final_total": len(final_refs),
        "missing": len(missing),
        "extra": len(extra),
        "missing_refs": sorted(list(missing))[:20],
        "ok": len(missing) == 0 and len(extra) == 0,
    }


def check_strongs_consistency(final_path):
    """Verifica consistencia: mismo Strong's → traduccion coherente."""
    # TODO: Implementar analisis de consistencia
    # - Extraer palabra modernizada por Strong's
    # - Agrupar por Strong's
    # - Detectar variaciones excesivas
    pass


def main():
    parser = argparse.ArgumentParser(description="Fase 4: Validacion de consistencia")
    parser.add_argument("--check-strongs", action="store_true")
    parser.add_argument("--check-coverage", action="store_true")
    args = parser.parse_args()

    final_file = os.path.join(FINAL_DIR, "rv1909_modernizada.ndjson")

    if not os.path.exists(final_file):
        print("No existe output final. Completa las fases 1-3 primero.")
        print(f"  Esperado: {final_file}")
        sys.exit(1)

    if args.check_coverage or not args.check_strongs:
        print("Verificando cobertura...")
        result = check_coverage(final_file, INPUT_FILE)
        print(f"  Input:   {result['input_total']:,} versos")
        print(f"  Final:   {result['final_total']:,} versos")
        print(f"  Missing: {result['missing']:,}")
        if result["missing_refs"]:
            print(f"  Ejemplos: {result['missing_refs'][:5]}")
        print(f"  Estado:  {'OK' if result['ok'] else 'FALLO'}")

    if args.check_strongs or not args.check_coverage:
        print("\nSKELETON: Validacion de consistencia Strong's pendiente.")


if __name__ == "__main__":
    main()
