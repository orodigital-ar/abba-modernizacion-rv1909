# SPEC: Motor de Encliticos v1
## Modernizacion RV1909 — Fase 1a

**Version:** 1.0
**Fecha:** 2026-03-02
**Estado:** Aprobado (consenso Claude + Codex)
**Origen:** enclicticos.ndjson (3 turnos de debate tecnico)

---

## 1. Problema

La RV1909 usa formas encliticas arcaicas donde el pronombre va pegado al verbo
conjugado (enclisis). En espanol moderno el pronombre va delante del verbo (proclisis).

```
dijole      → le dijo
levantose   → se levanto
dijeronle   → le dijeron
apareciosele → se le aparecio
```

Esto afecta ~3,000 versos del corpus (31,090 total).

Las formas encliticas validas en espanol moderno (gerundios, imperativos, infinitivos)
NO se tocan.

---

## 2. Decisiones de diseno cerradas

### ARQUITECTURA

| # | Decision | Detalle |
|---|----------|---------|
| 1 | Pipeline order | Encliticos PRIMERO, tildes monosilabas DESPUES. Secuencia: `fase1a_encliticos → fase1b_tildes → resto fase1` |
| 2 | Gate de deteccion | `has_accent()` como fast-path (descarta 95%+ de tokens), NO como requisito obligatorio. La tilde es senal de confianza, no puerta. |
| 3 | Whitelist de conjugaciones | Aceptar bases con terminaciones finitas conocidas: `-o` (pret 3s), `-aron/-eron/-ieron` (pret 3pl), `-ia/-ian` (imperf), `-aba/-aban` (imperf), `-a/-an` (futuro), `-e` (futuro 1s). Todo lo demas → no transformar. |
| 4 | Presente historico | Whitelist LEXICA cerrada (no por terminacion). Solo verbos confirmados en el corpus: `dice/dicen` y sus variantes acentuadas. |
| 5 | Capitalizacion | Si el token original inicia con mayuscula, capitalizar el primer caracter del reemplazo completo. `Dijole` → `Le dijo`, no `le dijo`. |
| 6 | Irregulares | Diccionario versionado en `reglas/excepciones_encliticos.json`. Mapea base arcaica → base moderna. |
| 7 | Blacklist de falsos positivos | Lista cerrada de tokens que terminan en silabas coincidentes con cliticos pero NO son encliticos: tabernaculo, apostoles, idolo, consuelo, etc. |
| 8 | Modo conservador | Si no hay match de conjugacion NI excepcion positiva, NO transformar. Falso negativo preferido sobre falso positivo. |
| 9 | Orden de cliticos | Automatico por strip derecha-a-izquierda con `insert(0,...)`. Resultado respeta orden gramatical: `se > te/me/nos > le/les > lo/la/los/las`. |

### OPERATIVO

| # | Decision | Detalle |
|---|----------|---------|
| 10 | Alcance | Solo token-level. No se tocan reordenamientos sintacticos fuera del token. |
| 11 | Pasadas | Una sola pasada de encliticos por verso. Sin reinyeccion. |
| 12 | Formato de log | `{verse_ref, token_before, token_after, base_before, base_after, clitics, rule_id, confidence, category}` |
| 13 | Metricas | Precision >= 0.99 SIEMPRE. Recall variable por categoria (ver seccion 7). |

---

## 3. Categorias de encliticos

| Cat | Nombre | Patron | Ejemplos | Frecuencia estimada |
|-----|--------|--------|----------|---------------------|
| 1 | Preterito 3s + clitico | verbo-o + cl | levantose (148x), dijole, tomola, matolo, sacole, hizolo | ~2,100 versos |
| 2 | Preterito 3pl + clitico | verbo-aron/-eron/-ieron + cl | dijeronle (106x), levantaronse (30x), hicieronle (30x) | ~741 versos |
| 3 | Presente historico | dice/dicen + cl | dicele (26x), diceles (18x), Dicenle (24x) | ~98 versos |
| 4 | Doble enclitico | verbo + cl1 + cl2 | apareciosele (6x), contoselo, dioseles, metioselo | ~78 versos |
| 5 | Futuro + clitico | verbo-e/-a/-an + cl | harelo, pondrelos, hareles, traerelos | ~16 formas |

---

## 4. Flujo del algoritmo (pseudocodigo)

```
function transform_enclitics(text):
    changes = []

    for each token in text:

        # --- FAST PATH ---
        if token in BLACKLIST_TOKENS:
            skip

        base, clitics = strip_trailing_clitics(token)  # max 2 cliticos
        if not clitics:
            skip

        # --- BLACKLIST NO-FINITAS ---
        if base matches gerundio/infinitivo/participio:
            skip

        # --- WHITELIST CONJUGACIONES ---
        normalized_base = None

        # 1. Irregulares conocidos (FORCE_DEACCENT)
        if base.lower() in FORCE_DEACCENT:
            normalized_base = FORCE_DEACCENT[base.lower()]

        # 2. Presente historico (whitelist lexica)
        elif base.lower() in PRESENT_HISTORICAL:
            normalized_base = PRESENT_HISTORICAL[base.lower()]

        # 3. Preterito 3s: termina en -o (con tilde)
        elif base ends with "o":
            normalized_base = base  # conservar tilde

        # 4. Preterito 3pl: termina en -aron/-eron/-ieron
        elif deaccent(base) ends with ("aron", "eron", "ieron"):
            normalized_base = deaccent(base)  # quitar tilde arcaica

        # 5. Imperfecto: -ia/-ian/-aba/-aban
        elif base ends with ("ia", "ian") and has_accent(base):
            normalized_base = base  # conservar tilde (tenia, decian)
        elif deaccent(base) ends with ("aba", "aban"):
            normalized_base = deaccent(base)  # sin tilde (llamaba)

        # 6. Futuro: -a/-an/-e (con tilde en ultima)
        elif base ends with ("a", "an", "e") and has_accent_on_last_syllable(base):
            normalized_base = base  # conservar tilde (hare, pondra)

        # --- NO RECONOCIDO ---
        if normalized_base is None:
            skip  # modo conservador

        # --- CONSTRUIR REEMPLAZO ---
        replacement = " ".join(clitics + [normalized_base])

        # --- CAPITALIZACION ---
        if token[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]

        # --- REGISTRAR ---
        changes.append({
            token_before: token,
            token_after: replacement,
            base_before: base,
            base_after: normalized_base,
            clitics: clitics,
            rule_id: determined_rule,
            confidence: "high" or "medium",
            category: determined_category
        })

        replace token with replacement in text

    return text, changes
```

---

## 5. Archivos del motor

| Archivo | Contenido |
|---------|-----------|
| `reglas/SPEC_ENCLITICOS_v1.md` | Este documento (spec de diseno) |
| `reglas/excepciones_encliticos.json` | Diccionarios: force_deaccent, blacklist_tokens, present_historical |
| `scripts/fase1_ortografia.py` | Se modifica: encliticos como paso 0 antes de tildes |
| `output/fase1_ortografia/fase1_stats.json` | Se extiende con metricas de encliticos |

---

## 6. Test cases de aceptacion

### 6.1 Positivos — Categoria 1 (Preterito 3s + clitico)

| # | Input | Output esperado | Cliticos | Base |
|---|-------|-----------------|----------|------|
| 1 | dijole | le dijo | [le] | dijo |
| 2 | Dijole | Le dijo | [le] | dijo |
| 3 | levantose | se levanto | [se] | levanto |
| 4 | Levantose | Se levanto | [se] | levanto |
| 5 | tomola | la tomo | [la] | tomo |
| 6 | matolo | lo mato | [lo] | mato |
| 7 | habloles | les hablo | [les] | hablo |
| 8 | llevome | me llevo | [me] | llevo |
| 9 | acercose | se acerco | [se] | acerco |
| 10 | bendijole | le bendijo | [le] | bendijo |
| 11 | hizolo | lo hizo | [lo] | hizo |
| 12 | Hizolo | Lo hizo | [lo] | hizo |
| 13 | pusose | se puso | [se] | puso |
| 14 | volviose | se volvio | [se] | volvio |
| 15 | sacole | le saco | [le] | saco |

### 6.2 Positivos — Categoria 2 (Preterito 3pl + clitico)

| # | Input | Output esperado | Cliticos | Base |
|---|-------|-----------------|----------|------|
| 1 | dijeronle | le dijeron | [le] | dijeron |
| 2 | Dijeronle | Le dijeron | [le] | dijeron |
| 3 | levantaronse | se levantaron | [se] | levantaron |
| 4 | hicieronle | le hicieron | [le] | hicieron |
| 5 | pusieronle | le pusieron | [le] | pusieron |
| 6 | trajeronle | le trajeron | [le] | trajeron |
| 7 | contaronle | le contaron | [le] | contaron |
| 8 | respondieronle | le respondieron | [le] | respondieron |
| 9 | echanonle | le echaron | [le] | echaron |
| 10 | juntaronse | se juntaron | [se] | juntaron |
| 11 | fueronse | se fueron | [se] | fueron |
| 12 | dijeronles | les dijeron | [les] | dijeron |

### 6.3 Positivos — Categoria 3 (Presente historico)

| # | Input | Output esperado | Cliticos | Base |
|---|-------|-----------------|----------|------|
| 1 | dicele | le dice | [le] | dice |
| 2 | Dicele | Le dice | [le] | dice |
| 3 | diceles | les dice | [les] | dice |
| 4 | Diceles | Les dice | [les] | dice |
| 5 | Dicenle | Le dicen | [le] | dicen |
| 6 | dicenle | le dicen | [le] | dicen |

### 6.4 Positivos — Categoria 4 (Doble enclitico)

| # | Input | Output esperado | Cliticos | Base |
|---|-------|-----------------|----------|------|
| 1 | apareciosele | se le aparecio | [se, le] | aparecio |
| 2 | Apareciosele | Se le aparecio | [se, le] | aparecio |
| 3 | contoselo | se lo conto | [se, lo] | conto |
| 4 | dioselo | se lo dio | [se, lo] | dio |
| 5 | dioseles | se les dio | [se, les] | dio |
| 6 | metioselo | se lo metio | [se, lo] | metio |
| 7 | tirosela | se la tiro | [se, la] | tiro |
| 8 | echoselas | se las echo | [se, las] | echo |
| 9 | quebrosele | se le quebro | [se, le] | quebro |
| 10 | cayosele | se le cayo | [se, le] | cayo |

### 6.5 Positivos — Categoria 5 (Futuro + clitico)

| # | Input | Output esperado | Cliticos | Base |
|---|-------|-----------------|----------|------|
| 1 | harelo | lo hare | [lo] | hare |
| 2 | pondrelo | lo pondre | [lo] | pondre |
| 3 | pondrelos | los pondre | [los] | pondre |
| 4 | hareles | les hare | [les] | hare |
| 5 | traerelos | los traere | [los] | traere |

### 6.6 Negativos — Falsos positivos (NO transformar)

| # | Input | Razon de exclusion |
|---|-------|--------------------|
| 1 | tabernaculo | Sustantivo, no verbo+clitico |
| 2 | apostoles | Sustantivo, terminacion -les es parte de la raiz |
| 3 | espectaculo | Sustantivo |
| 4 | obstaculo | Sustantivo |
| 5 | vinculo | Sustantivo |
| 6 | idolo | Sustantivo |
| 7 | consuelo | Sustantivo |
| 8 | suelo | Sustantivo |
| 9 | vuelo | Sustantivo |
| 10 | solo | Adverbio (ya modernizado de solo) |
| 11 | modelo | Sustantivo |
| 12 | levantandose | Gerundio + enclitico (valido en moderno) |
| 13 | diciendole | Gerundio + enclitico (valido en moderno) |
| 14 | hacerle | Infinitivo + enclitico (valido en moderno) |
| 15 | decirles | Infinitivo + enclitico (valido en moderno) |
| 16 | levantate | Imperativo + enclitico (valido en moderno) |
| 17 | acuerdate | Imperativo + enclitico (valido en moderno) |
| 18 | arrepentios | Imperativo + enclitico (valido en moderno) |

### 6.7 Edge cases

| # | Input | Output esperado | Nota |
|---|-------|-----------------|------|
| 1 | "dijole," | "le dijo," | Puntuacion preservada |
| 2 | "Dijole:" | "Le dijo:" | Puntuacion + mayuscula |
| 3 | "apareciosele;" | "se le aparecio;" | Doble + puntuacion |
| 4 | "Y dijole Dios" | "Y le dijo Dios" | Token en medio de frase |
| 5 | "dijole, y" | "le dijo, y" | Coma pegada al token |
| 6 | verso vacio "" | "" | Sin cambios |
| 7 | "sin encliticos" | "sin encliticos" | Sin cambios |

---

## 7. Metricas objetivo

| Categoria | Precision | Recall | Justificacion |
|-----------|-----------|--------|---------------|
| Cat 1 (pret 3s) | >= 0.99 | >= 0.95 | Mas comun, patron mas claro |
| Cat 2 (pret 3pl) | >= 0.99 | >= 0.95 | Alta frecuencia, patron regular |
| Cat 3 (presente hist.) | >= 0.99 | >= 0.90 | Whitelist lexica cerrada, recall limitado a verbos listados |
| Cat 4 (doble enclitico) | >= 0.99 | >= 0.85 | Complejidad alta, baja frecuencia |
| Cat 5 (futuro) | >= 0.99 | >= 0.85 | Baja frecuencia, patron menos comun |
| Global | >= 0.99 | >= 0.93 | Ponderado por frecuencia |

---

## 8. Restricciones explicitas

1. **NO transformar** gerundios, infinitivos, imperativos ni participios con enclitico.
2. **NO transformar** si la base no matchea ninguna conjugacion de la whitelist.
3. **NO reinyectar** el verso transformado en otra pasada de encliticos.
4. **NO tocar** sintaxis fuera del token (reordenamientos de frase).
5. **NO asignar** confidence "low" — si no es high o medium, no transformar.
6. **NO modificar** el pipeline de Fase 1 existente excepto para insertar el paso 0.

---

## 9. Firmas

Este documento representa el consenso tecnico alcanzado entre dos agentes de IA
tras 3 rondas de debate documentadas en `enclicticos.ndjson`, bajo la direccion
tecnica de Rodolfo Miranda (fundador del proyecto MRV).

Los agentes participan como **herramientas** del proceso, no como autores.
La autoria y decision final corresponde a los fundadores del proyecto.

```
Agente:    Claude (Opus 4.6, Anthropic)
Rol:       Direccion de implementacion, analisis de corpus, auditoria de codigo
Consenso:  Aprobado — 13/13 decisiones cerradas
Fecha:     2026-03-02

Agente:    Codex (GPT-5, OpenAI)
Rol:       Propuesta de motor v1, aportes de diseno operativo
Consenso:  Aprobado — 13/13 decisiones cerradas
Fecha:     2026-03-02
```

**Direccion tecnica:** Rodolfo Miranda
**Estado:** Pendiente de autorizacion del fundador para iniciar ejecucion (Plan A-D)
