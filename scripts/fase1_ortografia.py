#!/usr/bin/env python3
"""
fase1_ortografia.py — Modernizacion ortografica automatica de la RV1909

Fase 1: Aplica reglas deterministas (tildes, preposiciones, disambiguation por Strong's)
a los 31,090 versos de rv1909_strongs_full.ndjson.

Uso:
  python scripts/fase1_ortografia.py                    # Procesa todo
  python scripts/fase1_ortografia.py --libro GEN        # Solo Genesis
  python scripts/fase1_ortografia.py --dry-run          # Solo estadisticas, no escribe
  python scripts/fase1_ortografia.py --stats             # Muestra stats del ultimo run
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timezone

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "datos")
RULES_DIR = os.path.join(PROJECT_DIR, "reglas")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "fase1_ortografia")

INPUT_FILE = os.path.join(DATA_DIR, "rv1909_strongs_full.ndjson")
RULES_FILE = os.path.join(RULES_DIR, "reglas_ortograficas.json")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "fase1_output.ndjson")
STATS_FILE = os.path.join(OUTPUT_DIR, "fase1_stats.json")


def load_rules(rules_path):
    """Carga reglas ortograficas desde JSON."""
    with open(rules_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_verses(input_path, libro_filter=None):
    """Carga versos desde NDJSON. Opcionalmente filtra por libro."""
    verses = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            verse = json.loads(line)
            if libro_filter and verse.get("book") != libro_filter:
                continue
            verses.append(verse)
    return verses


def get_word_strongs(verse):
    """Extrae mapeo palabra→strongs del verso."""
    mapping = {}
    for w in verse.get("words", []):
        word = w.get("word", "").strip().rstrip(".,;:!?")
        strongs = w.get("strongs", [])
        if word and strongs:
            mapping[word.lower()] = strongs
    return mapping


def apply_simple_rules(text, rules_list):
    """Aplica reglas simples de reemplazo. Retorna (texto, lista_cambios)."""
    changes = []
    for rule in rules_list:
        old = rule["antiguo"]
        new = rule["moderno"]
        if old in text:
            text = text.replace(old, new)
            changes.append({"tipo": "simple", "de": old, "a": new})
    return text, changes


def apply_preposicion_arcaica(text):
    """Reemplaza la preposicion arcaica 'a' con tilde."""
    changes = []
    # Pattern: word boundary + á + word boundary (standalone)
    pattern = r'(?<=\s)á(?=\s)'
    if re.search(pattern, text):
        text = re.sub(pattern, 'a', text)
        changes.append({"tipo": "preposicion", "de": "á", "a": "a"})

    # Al inicio de linea
    if text.startswith("Á "):
        text = "A " + text[2:]
        changes.append({"tipo": "preposicion", "de": "Á", "a": "A"})

    return text, changes


def apply_disambiguation(text, word_strongs, rules):
    """Aplica reglas de disambiguation basadas en Strong's."""
    changes = []
    for rule in rules:
        palabra = rule["palabra"]
        if palabra not in text:
            continue

        # Buscar strongs asociados a esta palabra
        strongs_found = None
        for w_text, w_strongs in word_strongs.items():
            if palabra.lower() in w_text.lower():
                strongs_found = w_strongs
                break

        if strongs_found is None:
            # Sin Strong's, usar default si existe
            default = rule.get("default")
            if default and default != palabra:
                text = text.replace(palabra, default, 1)
                changes.append({
                    "tipo": "disambiguation_default",
                    "de": palabra,
                    "a": default,
                    "razon": "sin Strong's, usando default"
                })
            continue

        # Buscar match en casos
        matched = False
        for caso in rule["casos"]:
            caso_strongs = caso["strongs"]
            if any(s in strongs_found for s in caso_strongs):
                moderno = caso["moderno"]
                if moderno != palabra:
                    text = text.replace(palabra, moderno, 1)
                    changes.append({
                        "tipo": "disambiguation_strongs",
                        "de": palabra,
                        "a": moderno,
                        "strongs": caso_strongs,
                        "razon": caso["razon"]
                    })
                matched = True
                break

        if not matched:
            default = rule.get("default")
            if default and default != palabra:
                text = text.replace(palabra, default, 1)
                changes.append({
                    "tipo": "disambiguation_default",
                    "de": palabra,
                    "a": default,
                    "strongs": strongs_found,
                    "razon": "Strong's no coincide con casos, usando default"
                })

    return text, changes


def needs_fase2(text, original_text, changes):
    """Determina si un verso necesita fase 2 (semantica)."""
    # Heuristicas para detectar vocabulario arcaico no cubierto por reglas
    arcaicas = [
        "vosotros", "tú", "vuestro", "vuestra", "vuestros", "vuestras",
        "empero", "aqueste", "aquesto", "aquesa", "ansí", "asaz",
        "plugo", "pluguiere", "maguer", "ca ", "otrosí",
        "parió", "allegó", "allegaron",
    ]
    for arc in arcaicas:
        if arc.lower() in text.lower():
            return True
    return False


def process_verse(verse, rules):
    """Procesa un verso aplicando todas las reglas. Retorna resultado."""
    original_text = verse.get("text", "")
    if not original_text:
        return {
            "book": verse.get("book"),
            "chapter": verse.get("chapter"),
            "verse": verse.get("verse"),
            "texto_original": "",
            "texto_modernizado": "",
            "cambios": [],
            "fase": 1,
            "necesita_fase2": False,
            "sin_cambios": True,
        }

    text = original_text
    all_changes = []
    word_strongs = get_word_strongs(verse)

    # 1. Tildes monosilabicas
    text, changes = apply_simple_rules(text, rules.get("tildes_monosilabicas", {}).get("reglas", []))
    all_changes.extend(changes)

    # 2. Preposicion arcaica
    text, changes = apply_preposicion_arcaica(text)
    all_changes.extend(changes)

    # 3. Disambiguation por Strong's
    text, changes = apply_disambiguation(text, word_strongs, rules.get("disambiguation_strongs", {}).get("reglas", []))
    all_changes.extend(changes)

    # 4. Ortografia general
    text, changes = apply_simple_rules(text, rules.get("ortografia_general", {}).get("reglas", []))
    all_changes.extend(changes)

    # 5. Palabras arcaicas simples
    text, changes = apply_simple_rules(text, rules.get("palabras_arcaicas_simples", {}).get("reglas", []))
    all_changes.extend(changes)

    sin_cambios = (text == original_text)
    necesita_f2 = needs_fase2(text, original_text, all_changes)

    return {
        "book": verse.get("book"),
        "book_num": verse.get("book_num"),
        "chapter": verse.get("chapter"),
        "verse": verse.get("verse"),
        "texto_original": original_text,
        "texto_modernizado": text,
        "cambios": all_changes,
        "fase": 1,
        "necesita_fase2": necesita_f2,
        "sin_cambios": sin_cambios,
    }


def main():
    parser = argparse.ArgumentParser(description="Fase 1: Modernizacion ortografica RV1909")
    parser.add_argument("--libro", type=str, help="Filtrar por libro (e.g. GEN, MAT)")
    parser.add_argument("--dry-run", action="store_true", help="Solo estadisticas, no escribe output")
    parser.add_argument("--stats", action="store_true", help="Muestra stats del ultimo run")
    args = parser.parse_args()

    if args.stats:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print("No hay stats disponibles. Ejecuta el script primero.")
        return

    # Cargar reglas y datos
    print("Cargando reglas ortograficas...")
    rules = load_rules(RULES_FILE)

    print(f"Cargando versos{' (' + args.libro + ')' if args.libro else ''}...")
    verses = load_verses(INPUT_FILE, libro_filter=args.libro)
    print(f"  {len(verses)} versos cargados")

    # Procesar
    print("Procesando...")
    results = []
    stats = {
        "total": len(verses),
        "cambiados": 0,
        "sin_cambios": 0,
        "necesitan_fase2": 0,
        "vacios": 0,
        "cambios_por_tipo": {},
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    }

    for verse in verses:
        result = process_verse(verse, rules)
        results.append(result)

        if not result["texto_original"]:
            stats["vacios"] += 1
        elif result["sin_cambios"]:
            stats["sin_cambios"] += 1
        else:
            stats["cambiados"] += 1

        if result["necesita_fase2"]:
            stats["necesitan_fase2"] += 1

        for cambio in result["cambios"]:
            tipo = cambio["tipo"]
            stats["cambios_por_tipo"][tipo] = stats["cambios_por_tipo"].get(tipo, 0) + 1

    # Estadisticas
    pct_cambiados = (stats["cambiados"] / stats["total"] * 100) if stats["total"] else 0
    pct_fase2 = (stats["necesitan_fase2"] / stats["total"] * 100) if stats["total"] else 0

    print(f"\n{'='*50}")
    print(f"  FASE 1 — Estadisticas")
    print(f"{'='*50}")
    print(f"  Total versos:      {stats['total']:,}")
    print(f"  Cambiados:         {stats['cambiados']:,} ({pct_cambiados:.1f}%)")
    print(f"  Sin cambios:       {stats['sin_cambios']:,}")
    print(f"  Vacios:            {stats['vacios']:,}")
    print(f"  Necesitan fase 2:  {stats['necesitan_fase2']:,} ({pct_fase2:.1f}%)")
    print(f"\n  Cambios por tipo:")
    for tipo, count in sorted(stats["cambios_por_tipo"].items(), key=lambda x: -x[1]):
        print(f"    {tipo}: {count:,}")

    if args.dry_run:
        print("\n  (dry-run: no se escribio output)")
        return

    # Escribir output
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = OUTPUT_FILE
    if args.libro:
        output_path = os.path.join(OUTPUT_DIR, f"fase1_{args.libro.lower()}.ndjson")

    with open(output_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + "\n")

    print(f"\n  Output: {output_path}")
    print(f"  {len(results):,} versos escritos")

    # Guardar stats
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
