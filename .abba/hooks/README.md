# .abba/hooks/ — Hooks de sesion

Scripts que se ejecutan automaticamente antes/despues de `start` y `end`.
Como git hooks, pero para sesiones FAB.

## Hooks disponibles

| Archivo | Cuando se ejecuta | Si falla |
|---|---|---|
| `pre-start.py` | Antes de abrir sesion | Aborta start |
| `post-start.py` | Despues de abrir sesion | Warn, continua |
| `pre-end.py` | Antes de cerrar sesion | Aborta end |
| `post-end.py` | Despues de cerrar sesion | Warn, continua |

## Extensiones soportadas

- `.py` — ejecutado con Python
- `.bat` — ejecutado con cmd (Windows)
- `.sh` — ejecutado con bash

## Argumentos

Todos los hooks reciben el PROJECT_KEY como primer argumento.

## Ejemplo

```python
# pre-start.py
import sys
project_key = sys.argv[1] if len(sys.argv) > 1 else '?'
print(f'Pre-start hook para {project_key}')
```

## Configuracion

Habilitar/deshabilitar en framework.json:
```json
"hooks": {"enabled": true}
```

Timeout: 60 segundos por hook.
