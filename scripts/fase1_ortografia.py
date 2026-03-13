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
import unicodedata
from datetime import datetime, timezone

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_DIR, "datos")
RULES_DIR = os.path.join(PROJECT_DIR, "reglas")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "fase1_ortografia")

INPUT_FILE = os.path.join(DATA_DIR, "rv1909_strongs_full.ndjson")
RULES_FILE = os.path.join(RULES_DIR, "reglas_ortograficas.json")
ENCLITICS_FILE = os.path.join(RULES_DIR, "excepciones_encliticos.json")
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


# ---------------------------------------------------------------------------
# Motor de encliticos v2 (SPEC_ENCLITICOS_v1.md)
# Paso 0 del pipeline: corre ANTES de tildes monosilabicas
# ---------------------------------------------------------------------------

CLITIC_RE = re.compile(r"(?i)(les|las|los|nos|se|le|la|lo|me|te)$")
TOKEN_RE = re.compile(r"(?u)\b[\wáéíóúüñÁÉÍÓÚÜÑ]+\b")
NO_FINITE_RE = re.compile(
    r"(?iu)(?:ando|iendo|yendo|ándo|iéndo|yéndo|ar|er|ir|arse|erse|irse|ado|ido)$"
)


def _deaccent(s):
    """Quita todas las tildes de una cadena."""
    n = unicodedata.normalize("NFD", s)
    n = "".join(ch for ch in n if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", n)


def _has_accent(s):
    return any(c in "áéíóúÁÉÍÓÚ" for c in s)


def _split_clitics(word):
    """Extrae 1 o 2 cliticos del final. Retorna (base, [cliticos])."""
    w = word
    out = []
    for _ in range(2):
        m = CLITIC_RE.search(w)
        if not m:
            break
        out.insert(0, m.group(1).lower())
        w = w[: m.start()]
    return w, out


def _classify_and_normalize(base, enc_data):
    """Clasifica la base verbal y retorna (normalized_base, category, confidence)
    o (None, None, None) si no se reconoce."""
    low = base.lower()
    da = _deaccent(base)
    dal = da.lower()

    # 1. Force deaccent (irregulares conocidos)
    fd = enc_data["force_deaccent"]
    if low in fd:
        return fd[low], "cat1_pret3s", "high"

    # 2. Present historical (whitelist lexica cerrada)
    ph = enc_data["present_historical"]
    if base in ph:
        return ph[base], "cat3_presente", "high"
    if low in {k.lower(): k for k in ph}:
        for k, v in ph.items():
            if k.lower() == low:
                return v, "cat3_presente", "high"

    # 3. Preterito 3s: termina en -ó
    if base.endswith("ó"):
        return base.lower(), "cat1_pret3s", "high"

    # 4. Preterito 3pl: -aron/-eron/-ieron (con o sin tilde arcaica)
    if dal.endswith(("aron", "eron", "ieron")):
        return dal, "cat2_pret3pl", "high"

    # 5. Imperfecto -ía/-ían
    if base.endswith(("ía", "ían")):
        return low, "cat1_imperfecto", "high"

    # 6. Imperfecto -aba/-aban (con o sin tilde arcaica)
    if dal.endswith(("aba", "aban")):
        return dal, "cat1_imperfecto", "high"

    # 7. Futuro: -á, -án, -é (tilde en ultima silaba)
    if base.endswith(("á", "án", "é")) and len(da) >= 3:
        return low, "cat5_futuro", "high"

    # No reconocido → modo conservador
    return None, None, None


def load_enclitic_data(path):
    """Carga excepciones_encliticos.json y prepara sets de lookup."""
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Limpiar claves que empiezan con _
    fd = {k: v for k, v in raw.get("force_deaccent", {}).items() if not k.startswith("_")}
    ph = {k: v for k, v in raw.get("present_historical", {}).items() if not k.startswith("_")}

    blacklist_tokens = set()
    for token in raw.get("blacklist_flat", {}).get("tokens", []):
        blacklist_tokens.add(token)
        blacklist_tokens.add(token.lower())

    return {
        "force_deaccent": fd,
        "present_historical": ph,
        "blacklist": blacklist_tokens,
    }


def transform_enclitics(text, enc_data):
    """Transforma formas encliticas arcaicas a espanol moderno.
    Paso 0 del pipeline — corre ANTES de tildes monosilabicas.
    Returns: (texto_transformado, lista_de_cambios)
    """
    changes = []
    blacklist = enc_data["blacklist"]

    def _repl(m):
        token = m.group(0)

        # Fast-path: blacklist
        if token in blacklist or token.lower() in blacklist:
            return token

        # Fast-path: sin tilde → muy probablemente no es enclitico arcaico
        if not _has_accent(token):
            return token

        base, clitics = _split_clitics(token)
        if not clitics:
            return token

        # Si la base queda vacia o muy corta, no es verbo
        if len(base) < 2:
            return token

        # Blacklist de formas no finitas (gerundios, infinitivos, participios)
        if NO_FINITE_RE.search(base):
            return token

        normalized, category, confidence = _classify_and_normalize(base, enc_data)
        if normalized is None:
            return token  # modo conservador

        # Construir reemplazo: cliticos + verbo normalizado
        replacement = " ".join(clitics + [normalized])

        # Preservar mayuscula inicial
        if token[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]

        if replacement != token:
            changes.append({
                "tipo": f"enclitico_{category}",
                "de": token,
                "a": replacement,
                "base_antes": base,
                "base_despues": normalized,
                "cliticos": clitics,
                "confidence": confidence,
            })

        return replacement

    out = TOKEN_RE.sub(_repl, text)
    return out, changes


# ---------------------------------------------------------------------------
# Fin motor de encliticos
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Motor de futuro perifrástico
# Transforma formas arcaicas "infinitivo + haber" → futuro sintético moderno
# Ej: "bendecirte he" → "te bendeciré", "allegarse ha" → "se allegará"
# ---------------------------------------------------------------------------

# Haber form → future ending mapping
_HABER_TO_FUTURE = {"he": "é", "has": "ás", "ha": "á", "hemos": "emos", "han": "án"}

# Irregular future stems (infinitive → contracted stem)
_IRREGULAR_FUTURE = {
    "hacer": "har", "decir": "dir", "poder": "podr", "poner": "pondr",
    "tener": "tendr", "venir": "vendr", "salir": "saldr", "valer": "valdr",
    "saber": "sabr", "haber": "habr", "caber": "cabr", "querer": "querr",
}

# Words that look like infinitive+clitic but are nouns/proper nouns
_PERIF_BLACKLIST = {
    "césar", "ner", "esther", "altar", "lagar", "muerte", "mujer",
    "parte", "suerte", "arte", "norte", "corte", "fuerte", "mente",
}

_PERIF_RE = re.compile(
    r'\b([\wáéíóúüñ]+(?:ar|er|ir)(se|le|les|lo|la|los|las|me|te|nos)?)'
    r'\s+(ha|han|has|he|hemos)\b',
    re.IGNORECASE
)


def _build_future(infinitive, haber_form):
    """Build synthetic future from infinitive + haber form."""
    ending = _HABER_TO_FUTURE.get(haber_form.lower())
    if not ending:
        return None
    inf_lower = infinitive.lower()
    if inf_lower in _IRREGULAR_FUTURE:
        return _IRREGULAR_FUTURE[inf_lower] + ending
    # Regular: infinitive + ending
    return inf_lower + ending


def transform_periphrastic_future(text):
    """Transform archaic periphrastic future to modern synthetic future.
    'bendecirte he' → 'te bendeciré', 'allegarse ha' → 'se allegará'
    Returns: (text, changes)
    """
    changes = []
    original = text

    # Process all matches from right to left to preserve positions
    matches = list(_PERIF_RE.finditer(text))
    for m in reversed(matches):
        full_word = m.group(1)
        clitic = m.group(2) or ""
        haber = m.group(3)

        # Extract infinitive (word without clitic)
        if clitic:
            infinitive = full_word[:-len(clitic)]
        else:
            infinitive = full_word

        # Blacklist check
        if full_word.lower() in _PERIF_BLACKLIST or infinitive.lower() in _PERIF_BLACKLIST:
            continue

        # Check that what follows is NOT a past participle (present perfect false positive)
        rest = original[m.end():m.end() + 40].strip()
        if re.match(r'\w+(ado|ido|cho|to|so)\b', rest):
            continue

        # Build future form
        future = _build_future(infinitive, haber)
        if not future:
            continue

        # Construct replacement: clitic(s) + future verb
        if clitic:
            replacement = f"{clitic.lower()} {future}"
        else:
            replacement = future

        # Preserve capitalization
        if full_word[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]

        changes.append({
            "tipo": "futuro_perifrastico",
            "de": m.group(0),
            "a": replacement,
            "infinitivo": infinitive,
            "clitico": clitic or None,
        })
        text = text[:m.start()] + replacement + text[m.end():]

    return text, changes


# ---------------------------------------------------------------------------
# Fin motor de futuro perifrástico
# ---------------------------------------------------------------------------


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
    """Aplica reglas simples de reemplazo con word boundaries. Retorna (texto, lista_cambios)."""
    changes = []
    for rule in rules_list:
        old = rule["antiguo"]
        new = rule["moderno"]
        # Usar word boundaries para evitar substring matches
        # (ej: "dió"→"dio" no debe matchear dentro de "respondió")
        if old.startswith(" ") or old.startswith(",") or old.startswith(";"):
            # Reglas con contexto (ej: " ó ", ", ó ") → usar replace literal
            if old in text:
                text = text.replace(old, new)
                changes.append({"tipo": "simple", "de": old, "a": new})
        else:
            # Reglas de palabra → usar word boundary regex
            pattern = r'\b' + re.escape(old) + r'\b'
            if re.search(pattern, text):
                text = re.sub(pattern, new, text)
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
    text_lower = text.lower()

    # Pronombres de tratamiento (decision editorial pendiente)
    pronombres = [
        "vosotros", "vuestro", "vuestra", "vuestros", "vuestras",
    ]
    for p in pronombres:
        if p in text_lower:
            return True

    # "tú" con word boundary (evita falsos: túnica, betún)
    if re.search(r'\btú\b', text):
        return True

    # Vocabulario arcaico no cubierto por reglas
    arcaismos_regex = [
        r'\ballegó\b', r'\ballegaron\b', r'\ballegarse\b',
        r'\bholgar\b', r'\bholgarse\b', r'\bholgó\b',
        r'\bmenester\b',
    ]
    for pattern in arcaismos_regex:
        if re.search(pattern, text_lower):
            return True

    # Encliticos residuales (los que el motor v2 no pudo transformar)
    # Solo marca fase2 si queda algun enclitico sin resolver
    if re.search(r'\b\w+[óéí](?:le|les|lo|la|los|las|se|me|te|nos)\b', text):
        match = re.search(r'\b(\w+[óéí](?:le|les|lo|la|los|las|se|me|te|nos))\b', text)
        if match:
            word = match.group(1).lower()
            # Excluir gerundios e infinitivos (validos en moderno)
            if not re.search(r'(?:ando|iendo|yendo|ar|er|ir)', word):
                return True

    return False


def process_verse(verse, rules, enc_data):
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

    # 0. Encliticos (ANTES de tildes monosilabicas — SPEC_ENCLITICOS_v1)
    text, changes = transform_enclitics(text, enc_data)
    all_changes.extend(changes)

    # 1. Tildes monosilabicas
    text, changes = apply_simple_rules(text, rules.get("tildes_monosilabicas", {}).get("reglas", []))
    all_changes.extend(changes)

    # 2. Preposicion arcaica
    text, changes = apply_preposicion_arcaica(text)
    all_changes.extend(changes)

    # 3. Disambiguation por Strong's
    text, changes = apply_disambiguation(text, word_strongs, rules.get("disambiguation_strongs", {}).get("reglas", []))
    all_changes.extend(changes)

    # 4. Conjunciones con tilde (ó, é)
    text, changes = apply_simple_rules(text, rules.get("conjuncion_o_tilde", {}).get("reglas", []))
    all_changes.extend(changes)
    text, changes = apply_simple_rules(text, rules.get("conjuncion_e_tilde", {}).get("reglas", []))
    all_changes.extend(changes)

    # 5. Demostrativos sin tilde (RAE 2010)
    text, changes = apply_simple_rules(text, rules.get("demostrativos_sin_tilde", {}).get("reglas", []))
    all_changes.extend(changes)

    # 6. Solo sin tilde
    text, changes = apply_simple_rules(text, rules.get("solo_sin_tilde", {}).get("reglas", []))
    all_changes.extend(changes)

    # 7. Diptongo ui sin tilde
    text, changes = apply_simple_rules(text, rules.get("diptongo_ui_sin_tilde", {}).get("reglas", []))
    all_changes.extend(changes)

    # 8. Mas adversativo (inicio de verso y despues de ;)
    mas_rules = rules.get("mas_adversativo", {}).get("reglas", [])
    text, changes = apply_simple_rules(text, mas_rules)
    all_changes.extend(changes)
    # "Mas " al inicio de verso (semi-determinista: excluir comparaciones)
    if text.startswith("Mas ") and not re.match(r'Mas (?:que |de |del )', text):
        text = "Pero " + text[4:]
        all_changes.append({"tipo": "mas_adversativo", "de": "Mas", "a": "Pero"})

    # 9. Ortografia general
    text, changes = apply_simple_rules(text, rules.get("ortografia_general", {}).get("reglas", []))
    all_changes.extend(changes)

    # 10. Palabras arcaicas simples
    text, changes = apply_simple_rules(text, rules.get("palabras_arcaicas_simples", {}).get("reglas", []))
    all_changes.extend(changes)

    # 11. Nombre divino (Jehová → YHWH)
    text, changes = apply_simple_rules(text, rules.get("nombre_divino", {}).get("reglas", []))
    all_changes.extend(changes)

    # 12. Futuro perifrástico (allegarse ha → se allegará)
    text, changes = transform_periphrastic_future(text)
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

    print("Cargando excepciones de encliticos...")
    enc_data = load_enclitic_data(ENCLITICS_FILE)
    print(f"  {len(enc_data['force_deaccent'])} irregulares, {len(enc_data['blacklist'])} blacklist")

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
        result = process_verse(verse, rules, enc_data)
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
