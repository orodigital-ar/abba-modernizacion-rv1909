# .abba/ — Configuracion interna del framework

Carpeta privada de FAB. Contiene credenciales y
configuracion de conectores. NUNCA va a Git (.gitignored).

## Archivos

| Archivo | Funcion |
|---|---|
| `.env` | Credenciales de todos los conectores |
| `bfa/keys/` | Keyfiles Ethereum para sello BFA |

## Setup BFA

1. Instalar geth: `choco install geth-stable`
2. Generar claves: `geth account new`
3. Copiar keyfile a `.abba/bfa/keys/`
4. Activar en https://bfa.ar/sello (clave publica + firma)
5. Llenar BFA_USER y BFA_PASS en `.abba/.env`
6. Habilitar en framework.json: `bfa.enabled = true`

## Setup Git

Git usa el credential manager del sistema.
No requiere configuracion aqui salvo para CI/CD.
