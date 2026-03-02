# Documento Fundacional
## Proyecto de Modernizacion de la RV1909

**Version:** 1.0
**Fecha:** 2026-03-02
**Estado:** Vigente
**Sello BFA:** Pendiente (se sellara con la sesion de formalizacion)

---

## 1. Identidad del proyecto

El Proyecto de Modernizacion de la RV1909 tiene como finalidad producir una
**actualizacion sistematica** del texto biblico Reina-Valera 1909 (dominio publico)
al espanol contemporaneo, preservando la fidelidad al texto original hebreo y griego
mediante validacion con numeros Strong.

No se trata de una nueva traduccion, sino de una **modernizacion linguistica**:
actualizar ortografia, vocabulario arcaico y estructuras en desuso, manteniendo
la precision teologica verificable a traves de los codigos Strong vinculados a
cada palabra.

El proyecto opera como submodulo del Proyecto ABBA 1.0, pero es **autosuficiente**:
contiene sus propios datos, scripts, documentacion, historial y sellos de evidencia
temporal. Se publica de forma independiente.

---

## 2. Fundadores y liderazgo

Los creadores y responsables fundacionales del proyecto son:

- **Rodolfo Miranda** — Direccion tecnica, arquitectura de datos, desarrollo de scripts
  y pipeline de modernizacion, administracion del repositorio y sellos BFA.
- **Daniel Miranda** — Co-fundador. [Rol a definir por acuerdo entre fundadores.]

Ambos ejercen la **direccion fundadora** y definen conjuntamente los lineamientos
estrategicos, tecnicos, editoriales y de publicacion.

---

## 3. Declaracion de autoria y metodo

### 3.1 El dataset RV1909 + Strong

La anotacion Strong de este proyecto es **trabajo propio** de los fundadores,
construida mediante metodologia tecnica de alineacion y similitud lexica.

El proceso utilizo como referencias tecnicas de comparacion:
- **OSHB** (Open Scriptures Hebrew Bible) — CC BY 4.0 — para alineamiento AT
- **SBLGNT** (SBL Greek New Testament) — CC BY 4.0 — para alineamiento NT
- Traducciones modernas como referencia de verificacion (uso privado, no redistribuidas)

Esta metodologia utiliza estas referencias para comparacion y validacion, pero el
resultado es una elaboracion tecnica propia. No implica reproduccion textual ni copia
directa de modulos o bases de datos de terceros.

### 3.2 La modernizacion

La modernizacion del texto se realiza en 4 fases:

1. **Fase 1 — Ortografia automatica** (~70% de versos): Reglas deterministas para
   tildes arcaicas, preposiciones obsoletas y ortografia desactualizada. Incluye
   desambiguacion por codigos Strong (ej: "crio" con H1254 = "creo" [crear],
   con H7311 = "crio" [criar]).

2. **Fase 2 — Semantica con IA** (~25%): Modernizacion de vocabulario arcaico
   usando analisis contextual con numeros Strong y glosses como referencia de
   significado. Asistido por inteligencia artificial, revisado por los fundadores.

3. **Fase 3 — Revision humana** (~5%): Versos con ambiguedad teologica o poetica
   que requieren juicio humano directo de los fundadores.

4. **Fase 4 — Validacion de consistencia**: Verificacion de toda la Biblia para
   asegurar que un mismo termino Strong se traduce coherentemente en contextos
   equivalentes.

### 3.3 Datos del proyecto

| Elemento | Descripcion | Versos/Entradas | Licencia |
|---|---|---|---|
| rv1909_strongs_full.ndjson | RV1909 con alineamiento Strong (AT+NT) | 31,090 versos | Trabajo propio |
| strongs_es.ndjson | Glosses Strong en espanol | 14,198 entradas | Dominio publico |
| Texto base RV1909 | Reina-Valera 1909 | — | Dominio publico |
| Comparaciones (BJ3, BTX3, NBJ, RV1960) | Referencia privada | — | Copyright (no distribuidas) |

---

## 4. Declaracion de no copia

Se establece expresamente que el proyecto:

- **No copia** la RV1960 con Strong como fuente de salida.
- **No copia** la RV1909 con Strong del modulo de e-Sword.
- **No incorpora**, de forma intencional, contenido Strong de terceros con derechos
  para su redistribucion.
- Las traducciones modernas (BJ3, BTX3, NBJ, RV1960) se usan **exclusivamente** como
  referencia privada de verificacion y **no se distribuyen** con el proyecto.

La salida publicada corresponde a una elaboracion tecnica propia sobre RV1909, con
trazabilidad completa del proceso.

---

## 5. Procedencia y trazabilidad (Provenance)

### 5.1 Antiguo Testamento (23,134 versos)

El alineamiento Strong del AT se construyo mediante:
- Texto base: RV1909 (dominio publico)
- Referencia morfologica: OSHB (CC BY 4.0) — Westminster Leningrad Codex
- Metodo: alineacion por similitud lexica y posicional
- Calidad: alignment_score promedio registrado por verso
- Fuente de alineamiento registrada en campo `source` de cada verso

### 5.2 Nuevo Testamento (7,956 versos)

- Texto base: RV1909 (dominio publico)
- Referencia morfologica: SBLGNT (CC BY 4.0)
- Anotacion Strong: trabajo propio a partir de rv1909_word_strongs (128,177 mapeos)

### 5.3 Metricas de calidad conocidas

A la fecha de este documento:
- 6 versos con texto vacio (pendientes de correccion)
- 38,234 tokens sin Strong asignado (de 400,679 totales)
- 9,762 versos OT con alignment_score < 0.90
- Estos datos alimentan la Fase 4 de validacion

---

## 6. Principios rectores

El proyecto se rige por:

- **Fidelidad textual**: preservar RV1909 como texto base, no reescribir.
- **Precision teologica**: toda modernizacion verificable contra codigos Strong.
- **Trazabilidad**: cada cambio documentado con regla aplicada, Strong consultado y razon.
- **Reproducibilidad**: scripts abiertos, datos versionados, proceso repetible.
- **Transparencia legal**: declaracion explicita de que es referencia y que es dato propio.
- **Evidencia temporal**: sellos BFA (Blockchain Federal Argentina) en cada sesion de trabajo.
- **Mejora continua**: revision y correccion versionada con changelog semantico.

---

## 7. Gobernanza

- Las decisiones de alto impacto (publicacion, licencias, metodologia, estructura de datos)
  seran acordadas por la **direccion fundadora** (Rodolfo y Daniel Miranda).
- Toda version oficial del dataset incluira fecha, version y notas de cambios.
- Los agentes de IA (Claude, GPT, otros) participan como **herramientas** del proceso,
  no como autores. La autoria es de los fundadores.
- El historial de trabajo se registra en `logs/HISTORIAL.ndjson` (append-only, inmutable).
- Cada sesion de trabajo se sella en blockchain (BFA) como evidencia temporal.

---

## 8. Licencias y publicacion

### 8.1 Texto modernizado (output del proyecto)
**CC-BY-SA 4.0** (Creative Commons Atribucion-CompartirIgual 4.0 Internacional)

### 8.2 Codigo fuente (scripts, pipeline)
Publicado en el repositorio Git. Licencia a definir por los fundadores (MIT o Apache-2.0).

### 8.3 Atribuciones obligatorias
Por uso de fuentes CC BY 4.0:

> **Open Scriptures Hebrew Bible (OSHB)**
> Based on the Westminster Leningrad Codex.
> Licensed under CC BY 4.0. https://hb.openscriptures.org/
>
> **SBL Greek New Testament (SBLGNT)**
> Copyright 2010 by the Society of Biblical Literature and Logos Bible Software.
> Licensed under CC BY 4.0. https://sblgnt.com/

### 8.4 Datos no distribuidos
Las traducciones de comparacion (BJ3, BTX3, NBJ, RV1960) son propiedad de sus
respectivos editores. Se usan bajo fair use academico y **no se distribuyen**.

---

## 9. Sistema de evidencia temporal

El proyecto utiliza **BFA** (Blockchain Federal Argentina) para sellar
criptograficamente cada sesion de trabajo:

1. Se calcula SHA-256 del archivo de sesion sellada
2. Se envia el hash a la TSA (Time Stamp Authority) de BFA
3. El recibo se almacena en `logs/sellos_bfa/` dentro del proyecto
4. El sello es verificable publicamente e independiente del proyecto

Esto provee evidencia temporal inmutable de cuando se realizo cada trabajo,
reforzando la autoria de los fundadores.

---

## 10. Repositorio y publicacion

- **Repositorio**: https://github.com/orodigital-ar/abba-modernizacion-rv1909
- **Branch principal**: master
- **Contenido publico**: texto RV1909, strongs_es, reglas, scripts, output, logs, sellos BFA
- **Contenido privado**: traducciones de comparacion (excluidas via .gitignore)

---

## 11. Estado de conocimiento

A la fecha de esta version fundacional, y segun el conocimiento de los fundadores,
no se identifica otra edicion publica ampliamente disponible de RV1909 con anotacion
Strong equivalente en alcance al presente trabajo, ni un proyecto sistematico de
modernizacion con trazabilidad por codigos Strong.

---

## 12. Declaracion fundacional

Rodolfo Miranda y Daniel Miranda declaran formalmente constituido el **Proyecto de
Modernizacion de la RV1909**, comprometiendose a su desarrollo con rigor tecnico,
transparencia metodologica, responsabilidad documental y evidencia temporal verificable.

---

**Firmantes fundadores:**

Rodolfo Miranda
Daniel Miranda

**Fecha:** 2026-03-02
**Sello BFA:** [Se agregara hash y recibo al sellar]
