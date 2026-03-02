# Modernizacion RV1909 al Espanol Contemporaneo

Proyecto de modernizacion sistematica de la Reina-Valera 1909 (dominio publico)
al espanol contemporaneo, manteniendo fidelidad al texto original hebreo y griego
mediante validacion con numeros Strong's.

---

## Metodologia

La modernizacion procede en 4 fases:

1. **Ortografia automatica** (~70% de versos): Reglas deterministas para tildes
   arcaicas, preposiciones obsoletas y ortografia desactualizada.
2. **Semantica con IA** (~25%): Analisis contextual con numeros Strong's para
   actualizar vocabulario arcaico preservando precision teologica.
3. **Revision humana** (~5%): Versos con ambiguedad teologica o poetica que
   requieren juicio humano.
4. **Validacion de consistencia**: Verificacion de toda la Biblia para asegurar
   coherencia en traduccion de terminos clave.

## Fuentes de datos

- **RV1909** (dominio publico): 31,090 versos con alineamiento Strong's
- **Glosses Strong's**: 14,198 entradas hebreo/griego con definiciones en espanol
- **Textos de comparacion**: BJ3, BTX3, NBJ, RV1960 (uso privado, no distribuidos)

## Licencia

El texto modernizado se publica bajo **CC-BY-SA 4.0**.
Ver [LICENSE.md](LICENSE.md) para el texto completo.

## Atribuciones

- Texto base: Reina-Valera 1909, dominio publico
- Numeracion Strong's: alineamiento derivado de fuentes publicas
- Glosses Strong's en espanol: basados en la obra de James Strong (dominio publico)
- Traducciones de comparacion: uso privado bajo fair use academico

## Estructura

```
modernizacion_rv1909/
├── datos/                    # Datos fuente
│   ├── rv1909_strongs_full.ndjson   # 31,090 versos con Strong's
│   ├── strongs_es.ndjson            # 14,198 glosses
│   └── comparaciones/               # No distribuidas (copyright)
├── reglas/                   # Reglas de transformacion
├── scripts/                  # Herramientas de produccion
├── prompts/                  # Prompts para fase semantica
├── output/                   # Resultados por fase
│   ├── fase1_ortografia/
│   ├── fase2_semantica/
│   ├── fase3_revision/
│   └── final/
└── logs/                     # Historial y sellos BFA
```

---

> Proyecto ABBA 1.0 — Modernizacion RV1909
