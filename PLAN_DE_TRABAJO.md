# Plan de Trabajo — Modernizacion RV1909

> Documento vivo. 4 fases de modernizacion con milestones claros.

---

## Fase 1: Ortografia automatica

**Alcance:** ~70% de los 31,090 versos (cambios deterministas, sin ambiguedad)

**Script:** `scripts/fase1_ortografia.py`

### Reglas:
- Tildes monosilabicas arcaicas: fue→fue, vio→vio, dio→dio, fui→fui
- Preposicion arcaica: a→a (con acento obsoleto)
- Ortografia modernizada con desambiguacion Strong's:
  - crio+H1254→creo (crear), crio+H7311→crio (criar/elevar)
  - haz+H6440→faz (rostro) cuando Strong's lo indica
- Formas verbales arcaicas deterministas

### Milestones:
- [ ] Reglas ortograficas completas en JSON
- [ ] Script fase1 funcional y testeado
- [ ] Output: 31,090 versos procesados
- [ ] Estadisticas: % cambiados, % sin cambios, % necesitan fase 2

---

## Fase 2: Semantica con IA

**Alcance:** ~25% de versos (vocabulario arcaico que requiere contexto)

**Script:** `scripts/fase2_semantica.py`

### Metodologia:
- Batches de versos con contexto Strong's
- Claude API para modernizacion contextual
- Glosses Strong's como referencia de significado
- Comparacion con traducciones modernas (privado)

### Milestones:
- [ ] Prompt de modernizacion semantica v1
- [ ] Pipeline de batches funcional
- [ ] Output: versos modernizados con justificacion
- [ ] Revision de calidad por muestreo

---

## Fase 3: Revision humana

**Alcance:** ~5% de versos (ambiguedad teologica/poetica)

### Criterios para revision humana:
- Versos con multiples interpretaciones teologicas
- Poesia hebrea (Salmos, Proverbios, Cantar)
- Pasajes doctrinalmente sensibles
- Casos donde ninguna modernizacion preserva el matiz original

### Milestones:
- [ ] Lista de versos para revision humana generada
- [ ] Interfaz o formato de revision definido
- [ ] Revision completada por Rodolfo
- [ ] Versos finalizados integrados al output

---

## Fase 4: Validacion de consistencia

**Alcance:** Toda la Biblia (31,090 versos)

**Script:** `scripts/fase4_validacion.py`

### Verificaciones:
- Mismo termino Strong's → misma traduccion en contextos equivalentes
- No se perdieron versos en el proceso
- Formato NDJSON valido en output final
- Comparacion estadistica con traducciones modernas

### Milestones:
- [ ] Script de validacion funcional
- [ ] Reporte de inconsistencias generado
- [ ] Inconsistencias resueltas
- [ ] Output final: Biblia completa modernizada

---

## Resumen de progreso

| Fase | Versos | Estado | Output |
|---|---|---|---|
| Fase 1: Ortografia | ~21,763 (70%) | Pendiente | `output/fase1_ortografia/` |
| Fase 2: Semantica | ~7,773 (25%) | Pendiente | `output/fase2_semantica/` |
| Fase 3: Revision | ~1,555 (5%) | Pendiente | `output/fase3_revision/` |
| Fase 4: Validacion | 31,090 (100%) | Pendiente | `output/final/` |

---

> Ultima actualizacion: 2026-03-02
