#!/usr/bin/env python3
"""
fase2_semantica.py — Modernizacion semantica con IA (Fase 2)

Procesa versos marcados como necesita_fase2 por fase1, usando Claude API
para modernizar vocabulario arcaico con contexto de Strong's y glosses.

Estado: SKELETON — pendiente implementacion del pipeline API.

Uso futuro:
  python scripts/fase2_semantica.py                      # Procesa todos los pendientes
  python scripts/fase2_semantica.py --batch-size 50      # Batches de 50 versos
  python scripts/fase2_semantica.py --libro PSA           # Solo Salmos
"""

import json
import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "datos")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "fase2_semantica")
FASE1_OUTPUT = os.path.join(PROJECT_DIR, "output", "fase1_ortografia", "fase1_output.ndjson")
STRONGS_FILE = os.path.join(DATA_DIR, "strongs_es.ndjson")
PROMPT_FILE = os.path.join(PROJECT_DIR, "prompts", "modernizacion_prompt_v1.md")


def load_strongs_glosses(path):
    """Carga glosses Strong's como diccionario strong_num→entry."""
    glosses = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            glosses[entry["strong_num"]] = entry
    return glosses


def load_fase1_pendientes(path):
    """Carga versos que necesitan fase 2 desde output de fase 1."""
    pendientes = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            verse = json.loads(line)
            if verse.get("necesita_fase2"):
                pendientes.append(verse)
    return pendientes


def build_batch_context(verses, glosses, batch_size=50):
    """Construye contexto para un batch de versos."""
    # TODO: Implementar construccion de contexto con glosses
    # Cada batch incluye:
    # - Versos con texto original y modernizado (fase 1)
    # - Glosses de los Strong's presentes
    # - Instrucciones de modernizacion
    pass


def call_claude_api(batch_context, prompt):
    """Llama a Claude API para modernizacion semantica."""
    # TODO: Implementar llamada API
    # - Usar anthropic SDK
    # - Batch processing
    # - Rate limiting
    # - Error handling y retry
    raise NotImplementedError("Pipeline API pendiente de implementacion")


def main():
    parser = argparse.ArgumentParser(description="Fase 2: Modernizacion semantica RV1909")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--libro", type=str)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(FASE1_OUTPUT):
        print("ERROR: No existe output de fase 1. Ejecuta fase1_ortografia.py primero.")
        sys.exit(1)

    print("Cargando glosses Strong's...")
    glosses = load_strongs_glosses(STRONGS_FILE)
    print(f"  {len(glosses):,} glosses cargados")

    print("Cargando versos pendientes de fase 1...")
    pendientes = load_fase1_pendientes(FASE1_OUTPUT)
    print(f"  {len(pendientes):,} versos necesitan fase 2")

    if args.libro:
        pendientes = [v for v in pendientes if v.get("book") == args.libro]
        print(f"  {len(pendientes):,} del libro {args.libro}")

    if args.dry_run:
        print("\n  (dry-run: pipeline API no implementado aun)")
        return

    print("\n  SKELETON: Pipeline API pendiente de implementacion.")
    print("  Cuando este listo, procesara batches de versos con Claude API.")


if __name__ == "__main__":
    main()
