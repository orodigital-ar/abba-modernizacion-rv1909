#!/usr/bin/env python3
"""
framework.py — Sistema operativo de proyecto reutilizable

Motor config-driven basado en session_logger.py de PROYECTO ABBA 1.0.
Lee toda la configuracion de framework.json (ubicado en la raiz del proyecto).

Comandos basicos:
  python framework.py init                              # Inicializa HISTORIAL.ndjson en todos los proyectos
  python framework.py start P1                          # Abre sesion en P1
  python framework.py event P1 "bloque_ok" "detalle"    # Evento en sesion activa de P1
  python framework.py end P1 "Resumen"                  # Cierra y sella sesion de P1
  python framework.py log "hito" "detalle"              # Evento global en HISTORIAL_MASTER
  python framework.py stamp logs/archivo.md             # Sella archivo en BFA manualmente
  python framework.py status                            # Muestra progreso de todos
  python framework.py status P1                         # Muestra progreso de P1

Automatizacion del "cerebro":
  python framework.py context "descripcion"             # Guarda snapshot de contexto (crash recovery)
  python framework.py progreso "texto del item"         # Marca checkbox en PLAN_DE_ACCION.md
  python framework.py plan "idea nueva"                 # Agrega idea a IDEAS.md
  python framework.py note "aprendizaje"                # Guarda nota para MEMORY.md (mostrada en end)
  python framework.py summary "titulo" "contenido"      # Agrega seccion al log raiz del dia

Git:
  python framework.py sync P1                           # Git add + commit + push manual
  python framework.py sync P1 "mensaje"                 # Git sync con mensaje custom

WAL / Recovery:
  python framework.py recover                           # Recupera datos del WAL tras un crash
  python framework.py wal-status                        # Muestra estado del WAL sin modificar

Snapshots / Diff:
  python framework.py snapshot ["label"]                # Snapshot manual de brain files
  python framework.py snapshot-list                     # Listar snapshots disponibles
  python framework.py snapshot-restore [N]              # Restaurar desde snapshot
  python framework.py diff                              # Diff vs ultimo snapshot

Integracion:
  python framework.py integrar                          # Escanea TODO y alimenta brain files
  python framework.py archive <archivo>                 # Archiva suelto en .abba/integrados/

Audit:
  python framework.py audit [KEY]                       # Auditoria de integridad

Scaffold / Gestion:
  python framework.py scaffold "Nombre Proyecto"        # Crea proyecto nuevo con estructura completa
  python framework.py add-project KEY directorio        # Agrega subproyecto a framework.json
  python framework.py validate                          # Valida integridad del framework.json y estructura

Uso:
  cd MI_PROYECTO
  python scripts/framework.py <comando> [args]
"""

import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from collections import defaultdict

# Fix Windows cp1252: forzar UTF-8 en stdout/stderr para caracteres Unicode
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ── Config Loading ────────────────────────────────────────────────────────


def find_config():
    """
    Busca framework.json subiendo desde el directorio del script.
    Retorna la ruta absoluta al framework.json encontrado.
    Raises FileNotFoundError si no lo encuentra.
    """
    # Start from the directory containing this script
    current = os.path.dirname(os.path.abspath(__file__))

    for _ in range(10):  # Max 10 levels up
        candidate = os.path.join(current, "framework.json")
        if os.path.exists(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    raise FileNotFoundError(
        "framework.json no encontrado. "
        "Usa 'python framework.py scaffold \"Nombre\"' para crear un proyecto nuevo."
    )


def load_config():
    """
    Carga framework.json y construye las variables globales de configuracion.
    Retorna (config_dict, base_dir).
    """
    config_path = find_config()
    base_dir = os.path.dirname(config_path)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    return config, base_dir


# ── Load config and derive globals ────────────────────────────────────────

try:
    CONFIG, BASE_DIR = load_config()
except FileNotFoundError:
    # Allow scaffold to run without existing config
    CONFIG = {}
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Derive paths from config (with defaults for scaffold mode)
_paths = CONFIG.get("paths", {})
_repo_dir_rel = _paths.get("repo_dir", "")
REPO_DIR = os.path.join(BASE_DIR, _repo_dir_rel) if _repo_dir_rel else BASE_DIR
PROJECTS_DIR = os.path.join(REPO_DIR, _paths.get("subprojects_dir", "proyectos"))
MASTER_LOG = os.path.join(REPO_DIR, _paths.get("master_log", "logs/HISTORIAL_MASTER.ndjson"))
WAL_DIR = os.path.join(BASE_DIR, _paths.get("wal_dir", "logs/.wal"))  # WAL siempre en BASE_DIR (interno)
WAL_FILE = os.path.join(WAL_DIR, "wal.ndjson")
CONTEXT_FILE = os.path.join(WAL_DIR, "context.json")
NOTES_FILE = os.path.join(WAL_DIR, "notes.ndjson")

_brain = CONFIG.get("brain", {})
PLAN_FILE = os.path.join(BASE_DIR, _brain.get("plan_file", "PLAN_DE_ACCION.md"))
IDEAS_FILE = os.path.join(BASE_DIR, _brain.get("ideas_file", "IDEAS.md"))
IDEAS_SECTION = _brain.get("ideas_section", "## Ideas")

_bfa = CONFIG.get("bfa", {})
BFA_ENABLED = _bfa.get("enabled", False)
BFA_STAMP_URL = _bfa.get("stamp_url", "https://tsaapi.bfa.ar/api/tsa/stamp/")
BFA_VERIFY_URL = _bfa.get("verify_url", "https://tsaapi.bfa.ar/api/tsa/verify/")
BFA_RECEIPTS_DIR = os.path.join(BASE_DIR, _bfa.get("receipts_dir", "sello_bfa/receipts"))
BFA_AUTH_URL = _bfa.get("auth_url", "https://tsaapi.bfa.ar/api-token-auth/")

_git = CONFIG.get("git", {})
GIT_ENABLED = _git.get("enabled", True)
GIT_AUTO_SYNC = _git.get("auto_sync_on_end", True)

_private = CONFIG.get("private", {})
PRIVATE_DIR = os.path.join(BASE_DIR, _private.get("dir", ".abba"))
ENV_FILE = os.path.join(PRIVATE_DIR, ".env")

_display = CONFIG.get("display", {})
BANNER_ART = _display.get("banner_art", [])
STATUS_HEADER = _display.get("status_header", CONFIG.get("project", {}).get("name", "Framework"))

_snapshots = CONFIG.get("snapshots", {})
SNAPSHOTS_ENABLED = _snapshots.get("enabled", True)
SNAPSHOTS_MAX_KEEP = _snapshots.get("max_keep", 10)
SNAPSHOTS_DIR = os.path.join(PRIVATE_DIR, "snapshots")

_hooks = CONFIG.get("hooks", {})
HOOKS_ENABLED = _hooks.get("enabled", True)
HOOKS_DIR = os.path.join(PRIVATE_DIR, "hooks")

# Build PROJECT_DIRS and ROOT_LEVEL_PROJECTS from config
PROJECT_DIRS = {}
ROOT_LEVEL_PROJECTS = set()
for key, info in CONFIG.get("projects", {}).items():
    PROJECT_DIRS[key] = info["directory"]
    if info.get("location") == "root":
        ROOT_LEVEL_PROJECTS.add(key)


def project_base_dir(project_key):
    """Retorna el directorio base de un proyecto.
    Los ROOT_LEVEL_PROJECTS viven en REPO_DIR (o BASE_DIR si no hay repo_dir),
    los demas en PROJECTS_DIR (que ya esta dentro de REPO_DIR).
    """
    if project_key in ROOT_LEVEL_PROJECTS:
        return os.path.join(REPO_DIR, PROJECT_DIRS[project_key])
    return os.path.join(PROJECTS_DIR, PROJECT_DIRS[project_key])


# ── WAL (Write-Ahead Log) ────────────────────────────────────────────────
#
# Crash recovery: every write goes to WAL FIRST, then to final destination.
# If the system crashes, the WAL survives. On next session start (or manual
# 'recover'), pending WAL entries are replayed to fill gaps in destinations.
#


def wal_append(entry):
    """Write an entry to the WAL file BEFORE the actual write."""
    os.makedirs(WAL_DIR, exist_ok=True)
    with open(WAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def wal_read():
    """Read all pending WAL entries."""
    if not os.path.exists(WAL_FILE):
        return []
    entries = []
    with open(WAL_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def wal_clear():
    """Clear the WAL after successful distribution."""
    if os.path.exists(WAL_FILE):
        os.remove(WAL_FILE)


def wal_has_pending():
    """Check if there are pending WAL entries."""
    if not os.path.exists(WAL_FILE):
        return False
    return os.path.getsize(WAL_FILE) > 0


def _file_contains_event(filepath, event_data):
    """Check if a NDJSON file already contains an event (by ts + evento match)."""
    if not os.path.exists(filepath):
        return False
    ts = event_data.get("ts", "")
    evento = event_data.get("evento", "")
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("ts") == ts and entry.get("evento") == evento:
                    # Extra check: sesion must match if present
                    if "sesion" in event_data:
                        if entry.get("sesion") == event_data.get("sesion"):
                            return True
                    else:
                        return True
            except json.JSONDecodeError:
                continue
    return False


def wal_recover():
    """
    Replay pending WAL entries, distributing to final destinations.
    Skips entries already present in destination (idempotent).
    Returns count of recovered entries.
    """
    entries = wal_read()
    if not entries:
        return 0

    recovered = 0

    for entry in entries:
        action = entry.get("action")
        dest = entry.get("dest")  # relative path from BASE_DIR
        data = entry.get("data")

        if not action or not data:
            continue

        if action == "append_ndjson":
            full_path = os.path.join(BASE_DIR, dest)
            if not _file_contains_event(full_path, data):
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
                recovered += 1

        elif action == "write_md":
            full_path = os.path.join(BASE_DIR, dest)
            if not os.path.exists(full_path):
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(data.get("content", ""))
                recovered += 1

        elif action == "append_md":
            full_path = os.path.join(BASE_DIR, dest)
            content = data.get("content", "")
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    existing = f.read()
                if "SESION SELLADA" in existing and "SESION SELLADA" in content:
                    continue
                if content.strip() and content.strip() in existing:
                    continue
            if os.path.exists(full_path):
                with open(full_path, "a", encoding="utf-8") as f:
                    f.write(content)
                recovered += 1

        elif action == "progreso_mark":
            search = data.get("search", "")
            date = data.get("date", today_str())
            if search and _progreso_mark(search, date):
                recovered += 1

        elif action == "plan_add":
            text = data.get("text", "")
            date = data.get("date", today_str())
            if text and _plan_add(text, date):
                recovered += 1

        elif action == "summary_add":
            full_path = os.path.join(BASE_DIR, dest)
            title = data.get("title", "")
            content = data.get("content", "")
            if title and _summary_add_to_file(full_path, title, content):
                recovered += 1

    wal_clear()
    return recovered


# ── Snapshots ────────────────────────────────────────────────────────────
#
# Auto-snapshot of brain files before each session start.
# If a brain file gets corrupted, it can be restored from a snapshot.
#


def _brain_file_paths():
    """Resolve paths for the 4 brain files from config."""
    _brain_cfg = CONFIG.get("brain", {})
    names = [
        _brain_cfg.get("claude_md", "CLAUDE.md"),
        _brain_cfg.get("consciencia_md", "CONSCIENCIA.md"),
        _brain_cfg.get("plan_file", "PLAN_DE_ACCION.md"),
        _brain_cfg.get("ideas_file", "IDEAS.md"),
    ]
    paths = []
    for name in names:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            paths.append((name, p))
    return paths


def _snapshot_create(label="manual"):
    """Copy brain files to .abba/snapshots/YYYY-MM-DD_HHMMSS/ + metadata.json."""
    if not SNAPSHOTS_ENABLED:
        return None

    ts = datetime.now(timezone.utc)
    dirname = ts.strftime("%Y-%m-%d_%H%M%S")
    snap_dir = os.path.join(SNAPSHOTS_DIR, dirname)
    os.makedirs(snap_dir, exist_ok=True)

    brain_files = _brain_file_paths()
    copied = []
    for name, path in brain_files:
        dst = os.path.join(snap_dir, name)
        shutil.copy2(path, dst)
        copied.append(name)

    # Write metadata
    meta = {
        "ts": ts.strftime("%Y-%m-%dT%H:%M:%S"),
        "label": label,
        "files": copied,
    }
    with open(os.path.join(snap_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    _snapshot_prune()
    return snap_dir


def _snapshot_prune():
    """Keep only the latest N snapshots (default 10)."""
    if not os.path.exists(SNAPSHOTS_DIR):
        return
    dirs = sorted([
        d for d in os.listdir(SNAPSHOTS_DIR)
        if os.path.isdir(os.path.join(SNAPSHOTS_DIR, d))
    ])
    while len(dirs) > SNAPSHOTS_MAX_KEEP:
        oldest = dirs.pop(0)
        shutil.rmtree(os.path.join(SNAPSHOTS_DIR, oldest))


def _snapshot_list():
    """List available snapshots (newest first). Returns list of (dirname, metadata)."""
    if not os.path.exists(SNAPSHOTS_DIR):
        return []
    result = []
    dirs = sorted([
        d for d in os.listdir(SNAPSHOTS_DIR)
        if os.path.isdir(os.path.join(SNAPSHOTS_DIR, d))
    ], reverse=True)
    for d in dirs:
        meta_path = os.path.join(SNAPSHOTS_DIR, d, "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        result.append((d, meta))
    return result


def _snapshot_latest():
    """Return path of the most recent snapshot, or None."""
    snapshots = _snapshot_list()
    if not snapshots:
        return None
    return os.path.join(SNAPSHOTS_DIR, snapshots[0][0])


# ── Diff ─────────────────────────────────────────────────────────────────
#
# Show what changed in brain files since last snapshot.
#


def _diff_brain_files(snapshot_dir):
    """Unified diff of current brain files vs snapshot. Returns dict {name: diff_lines}."""
    result = {}
    brain_files = _brain_file_paths()
    for name, current_path in brain_files:
        snap_path = os.path.join(snapshot_dir, name)
        if not os.path.exists(snap_path):
            continue
        try:
            with open(snap_path, "r", encoding="utf-8") as f:
                old_lines = f.readlines()
            with open(current_path, "r", encoding="utf-8") as f:
                new_lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            continue

        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"{name} (snapshot)",
            tofile=f"{name} (current)",
            lineterm=""
        ))
        if diff:
            result[name] = diff
    return result


def _show_diff(diff_result):
    """Pretty-print diff results."""
    if not diff_result:
        print("  Diff: sin cambios en brain files desde ultimo snapshot")
        return
    print(f"  Diff: cambios detectados en {len(diff_result)} archivo(s):")
    for name, lines in diff_result.items():
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
        print(f"    {name}: +{added} -{removed} lineas")
        for line in lines[:20]:
            line = line.rstrip("\n")
            if line.startswith("+"):
                print(f"      {line}")
            elif line.startswith("-"):
                print(f"      {line}")
            elif line.startswith("@@"):
                print(f"      {line}")
        if len(lines) > 20:
            print(f"      ... ({len(lines) - 20} lineas mas)")


def cmd_snapshot(label="manual"):
    """Create a manual snapshot of brain files."""
    snap_dir = _snapshot_create(label=label)
    if snap_dir:
        brain_files = _brain_file_paths()
        print(f"Snapshot creado: {os.path.basename(snap_dir)}")
        print(f"  Label: {label}")
        print(f"  Archivos: {', '.join(n for n, _ in brain_files)}")
        print(f"  Dir: {snap_dir}")
    else:
        print("Snapshots deshabilitados (snapshots.enabled = false)")


def cmd_snapshot_list():
    """List available snapshots."""
    snapshots = _snapshot_list()
    if not snapshots:
        print("No hay snapshots disponibles.")
        return
    print(f"Snapshots disponibles ({len(snapshots)}):\n")
    for i, (dirname, meta) in enumerate(snapshots):
        label = meta.get("label", "?")
        ts = meta.get("ts", "?")
        files = meta.get("files", [])
        marker = " (latest)" if i == 0 else ""
        print(f"  {i + 1}. {dirname}  [{label}]  {len(files)} archivos{marker}")


def cmd_snapshot_restore(selector=None):
    """Restore brain files from a snapshot. Creates pre-restore snapshot first."""
    snapshots = _snapshot_list()
    if not snapshots:
        print("No hay snapshots para restaurar.")
        return

    # Resolve selector: number (1-based), dirname, or None (latest)
    target_dir_name = None
    if selector is None or selector == "latest":
        target_dir_name = snapshots[0][0]
    elif selector.isdigit():
        idx = int(selector) - 1
        if 0 <= idx < len(snapshots):
            target_dir_name = snapshots[idx][0]
        else:
            print(f"Error: indice {selector} fuera de rango (1-{len(snapshots)})")
            return
    else:
        # Try to match by dirname prefix
        for dirname, _ in snapshots:
            if dirname.startswith(selector):
                target_dir_name = dirname
                break
        if not target_dir_name:
            print(f"Error: snapshot '{selector}' no encontrado")
            return

    snap_path = os.path.join(SNAPSHOTS_DIR, target_dir_name)

    # Create pre-restore snapshot
    _snapshot_create(label="pre-restore")
    print(f"  Pre-restore snapshot creado")

    # Restore files
    brain_files = _brain_file_paths()
    restored = 0
    for name, current_path in brain_files:
        src = os.path.join(snap_path, name)
        if os.path.exists(src):
            shutil.copy2(src, current_path)
            restored += 1
            print(f"  Restaurado: {name}")

    print(f"\nRestaurados {restored} archivo(s) desde snapshot {target_dir_name}")


def cmd_diff():
    """Show diff of current brain files vs latest snapshot."""
    latest = _snapshot_latest()
    if not latest:
        print("No hay snapshots para comparar. Usa 'snapshot' para crear uno.")
        return
    diff_result = _diff_brain_files(latest)
    _show_diff(diff_result)


# ── Hooks ────────────────────────────────────────────────────────────────
#
# Custom scripts that run before/after start and end.
# Hooks live in .abba/hooks/ as .py, .sh, or .bat files.
# Pre-hooks abort on failure; post-hooks only warn.
#


def _run_hook(hook_name, *args):
    """Execute a hook script if it exists. Returns True if OK or no hook, False if pre-hook failed."""
    if not HOOKS_ENABLED:
        return True

    if not os.path.exists(HOOKS_DIR):
        return True

    is_pre = hook_name.startswith("pre-")

    # Try extensions in order: .py, .bat (Windows), .sh
    for ext in (".py", ".bat", ".sh"):
        hook_path = os.path.join(HOOKS_DIR, hook_name + ext)
        if os.path.exists(hook_path):
            try:
                if ext == ".py":
                    cmd_args = [sys.executable, hook_path] + list(args)
                elif ext == ".bat":
                    cmd_args = ["cmd", "/c", hook_path] + list(args)
                else:
                    cmd_args = ["bash", hook_path] + list(args)

                result = subprocess.run(
                    cmd_args,
                    cwd=BASE_DIR,
                    timeout=60,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    print(f"  Hook [{hook_name}]: {result.stdout.strip()}")
                if result.returncode != 0:
                    msg = result.stderr.strip() or f"exit code {result.returncode}"
                    if is_pre:
                        print(f"  Hook [{hook_name}] FALLO: {msg}")
                        print(f"  Operacion abortada por pre-hook.")
                        return False
                    else:
                        print(f"  Hook [{hook_name}] WARN: {msg}")
                return True
            except subprocess.TimeoutExpired:
                msg = f"timeout (60s)"
                if is_pre:
                    print(f"  Hook [{hook_name}] FALLO: {msg}")
                    return False
                else:
                    print(f"  Hook [{hook_name}] WARN: {msg}")
                return True
            except OSError as e:
                msg = str(e)
                if is_pre:
                    print(f"  Hook [{hook_name}] FALLO: {msg}")
                    return False
                else:
                    print(f"  Hook [{hook_name}] WARN: {msg}")
                return True

    return True  # No hook found — OK


# ── Audit ────────────────────────────────────────────────────────────────
#
# Integrity verification for sealed sessions, logs, and BFA stamps.
#


def _audit_historial(project_key):
    """Audit HISTORIAL.ndjson: valid JSON, monotonic timestamps, start/end pairs."""
    issues = []
    path = historial_path(project_key)
    if not os.path.exists(path):
        return [("[!] HISTORIAL.ndjson no existe", "warn")]

    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                issues.append((f"[x] Linea {i}: JSON invalido", "error"))

    # Check monotonic timestamps
    prev_ts = ""
    for entry in entries:
        ts = entry.get("ts", "")
        if ts and ts < prev_ts:
            issues.append((f"[!] Timestamp no-monotonico: {ts} < {prev_ts}", "warn"))
        if ts:
            prev_ts = ts

    # Check start/end pairs
    starts = {}
    for entry in entries:
        evento = entry.get("evento", "")
        sesion = entry.get("sesion", "")
        if evento == "sesion_inicio" and sesion:
            starts[sesion] = True
        elif evento == "sesion_fin" and sesion:
            if sesion in starts:
                del starts[sesion]
            else:
                issues.append((f"[!] Sesion {sesion}: fin sin inicio", "warn"))

    for sesion in starts:
        issues.append((f"[!] Sesion {sesion}: inicio sin fin (puede estar activa)", "warn"))

    if not issues:
        issues.append(("[v] HISTORIAL.ndjson OK ({} eventos)".format(len(entries)), "ok"))

    return issues


def _audit_sessions(project_key):
    """Audit session MDs: sealed, sequential numbering, no gaps."""
    issues = []
    log_dir = logs_dir(project_key)
    if not os.path.exists(log_dir):
        return [("[!] Directorio logs/ no existe", "warn")]

    session_files = sorted([
        f for f in os.listdir(log_dir)
        if f.startswith("sesion_") and f.endswith(".md")
    ])

    if not session_files:
        return [("[!] No hay sesiones MD", "warn")]

    nums = []
    for fname in session_files:
        match = re.match(r"sesion_(\d+)_", fname)
        if match:
            nums.append(int(match.group(1)))

    # Check sequential (allow gaps for genesis 000)
    expected = list(range(min(nums), max(nums) + 1)) if nums else []
    missing = set(expected) - set(nums)
    if missing:
        issues.append((f"[!] Sesiones faltantes: {sorted(missing)}", "warn"))

    # Check sealed
    sealed_count = 0
    current_session = get_current_session(project_key)
    for fname in session_files:
        fpath = os.path.join(log_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            # Skip current active session
            match = re.match(r"sesion_(\d+)_", fname)
            if match and current_session and match.group(1) == current_session:
                continue
            if "SESION SELLADA" in content:
                sealed_count += 1
            else:
                issues.append((f"[!] {fname}: no sellada", "warn"))
        except (OSError, UnicodeDecodeError):
            issues.append((f"[x] {fname}: no se pudo leer", "error"))

    if not issues:
        issues.append((f"[v] Sesiones OK ({len(session_files)} archivos, {sealed_count} selladas)", "ok"))

    return issues


def _audit_bfa(project_key):
    """Audit BFA stamps: hashes match sealed files."""
    issues = []
    log_dir_path = logs_dir(project_key)
    bfa_dir = os.path.join(log_dir_path, "sellos_bfa")

    if not os.path.exists(bfa_dir):
        return [("[v] Sin sellos BFA (directorio no existe)", "ok")]

    stamps = [f for f in os.listdir(bfa_dir) if f.endswith(".json")]
    if not stamps:
        return [("[v] Sin sellos BFA", "ok")]

    verified = 0
    for stamp_file in stamps:
        stamp_path = os.path.join(bfa_dir, stamp_file)
        try:
            with open(stamp_path, "r", encoding="utf-8") as f:
                receipt = json.load(f)
        except (json.JSONDecodeError, OSError):
            issues.append((f"[x] {stamp_file}: recibo invalido", "error"))
            continue

        original_file = receipt.get("archivo", "")
        stored_hash = receipt.get("sha256", "")
        if not original_file or not stored_hash:
            issues.append((f"[!] {stamp_file}: falta archivo o hash", "warn"))
            continue

        # Try to find the original file
        original_path = os.path.join(BASE_DIR, original_file) if not os.path.isabs(original_file) else original_file
        if not os.path.exists(original_path):
            # Try relative to log_dir
            alt_path = os.path.join(log_dir_path, os.path.basename(original_file))
            if os.path.exists(alt_path):
                original_path = alt_path
            else:
                issues.append((f"[!] {stamp_file}: archivo original no encontrado", "warn"))
                continue

        try:
            with open(original_path, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            if actual_hash == stored_hash:
                verified += 1
            else:
                issues.append((f"[x] {stamp_file}: hash NO coincide (archivo modificado?)", "error"))
        except OSError:
            issues.append((f"[!] {stamp_file}: no se pudo leer archivo original", "warn"))

    if verified > 0 and not issues:
        issues.append((f"[v] BFA OK ({verified} sellos verificados)", "ok"))
    elif verified > 0:
        issues.insert(0, (f"[v] {verified} sellos verificados", "ok"))

    return issues


def _audit_project(project_key):
    """Run all audits for a single project."""
    results = []
    results.extend(_audit_historial(project_key))
    results.extend(_audit_sessions(project_key))
    results.extend(_audit_bfa(project_key))
    return results


def cmd_audit(project_key=None):
    """Run integrity audit. Without KEY, audits all projects."""
    keys = [project_key] if project_key else sorted(PROJECT_DIRS.keys())
    total_ok = 0
    total_warn = 0
    total_error = 0

    print(f"\nAuditoria de integridad")
    print(f"{'=' * 50}\n")

    for pk in keys:
        if pk not in PROJECT_DIRS:
            print(f"{pk}: proyecto no existe")
            continue

        print(f"  {pk} ({PROJECT_DIRS[pk]}):")
        results = _audit_project(pk)
        for msg, level in results:
            print(f"    {msg}")
            if level == "ok":
                total_ok += 1
            elif level == "warn":
                total_warn += 1
            elif level == "error":
                total_error += 1
        print()

    print(f"Resumen: {total_ok} OK, {total_warn} advertencias, {total_error} errores")
    if total_error:
        print(f"  HAY ERRORES — revisar manualmente")
    elif total_warn:
        print(f"  Advertencias encontradas — revisar si es necesario")
    else:
        print(f"  Todo OK")


# ── Utilities ────────────────────────────────────────────────────────────


def now_ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def logs_dir(project_key):
    return os.path.join(project_base_dir(project_key), "logs")


def historial_path(project_key):
    return os.path.join(logs_dir(project_key), "HISTORIAL.ndjson")


def append_master(event_data):
    """Append una linea al HISTORIAL_MASTER.ndjson (log raiz). WAL-protected."""
    wal_append({
        "action": "append_ndjson",
        "dest": os.path.relpath(MASTER_LOG, BASE_DIR),
        "data": event_data,
    })
    os.makedirs(os.path.dirname(MASTER_LOG), exist_ok=True)
    with open(MASTER_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + "\n")


def append_event(project_key, event_data, also_master=False):
    """Append una linea al HISTORIAL.ndjson del proyecto (y opcionalmente al master). WAL-protected."""
    path = historial_path(project_key)
    wal_append({
        "action": "append_ndjson",
        "dest": os.path.relpath(path, BASE_DIR),
        "data": event_data,
    })
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event_data, ensure_ascii=False) + "\n")
    if also_master:
        master_event = {**event_data, "proyecto": project_key}
        append_master(master_event)
    return path


def read_historial(project_key):
    """Lee todas las lineas del HISTORIAL."""
    path = historial_path(project_key)
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def get_next_session_num(project_key):
    """Calcula el proximo numero de sesion."""
    entries = read_historial(project_key)
    max_num = 0
    for e in entries:
        sesion = e.get("sesion", "000")
        try:
            num = int(sesion)
            if num > max_num:
                max_num = num
        except ValueError:
            pass
    return max_num + 1


def get_current_session(project_key):
    """Retorna el numero de sesion activa (la ultima sin sesion_fin)."""
    entries = read_historial(project_key)
    open_sessions = set()
    closed_sessions = set()
    for e in entries:
        sesion = e.get("sesion", "")
        if e.get("evento") == "sesion_inicio":
            open_sessions.add(sesion)
        elif e.get("evento") == "sesion_fin":
            closed_sessions.add(sesion)
    active = open_sessions - closed_sessions
    if active:
        return max(active)
    return None


def load_meta(project_key):
    """Carga el META.json del proyecto."""
    meta_path = os.path.join(
        project_base_dir(project_key),
        f"MANIFIESTO_{project_key}_META.json"
    )
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ── Helpers for PROGRESO / PLAN / SUMMARY ─────────────────────────────────


def _progreso_mark(search_text, date=None):
    """
    Find a [ ] checkbox in PLAN_DE_ACCION.md matching search_text (substring, case-insensitive)
    and mark it as [x] with the date.
    Returns True if a change was made, False if already done or not found.
    """
    if date is None:
        date = today_str()
    if not os.path.exists(PLAN_FILE):
        return False

    with open(PLAN_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    changed = False
    for i, line in enumerate(lines):
        if "- [ ]" in line and search_text.lower() in line.lower():
            new_line = re.sub(
                r"- \[ \] (?:Pendiente — )?",
                f"- [x] {date} — ",
                line,
                count=1,
            )
            lines[i] = new_line
            changed = True
            break

    if changed:
        for i, line in enumerate(lines):
            if line.startswith("> Ultima actualizacion:"):
                lines[i] = f"> Ultima actualizacion: {date}\n"
                break

        with open(PLAN_FILE, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return changed


def _plan_add(text, date=None):
    """
    Add a new idea to IDEAS.md at the configured ideas section.
    Inserts before the closing --- of the section.
    Returns True if added, False if text already exists.
    """
    if date is None:
        date = today_str()
    if not os.path.exists(IDEAS_FILE):
        return False

    with open(IDEAS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    if text in content:
        return False

    new_item = f"- [ ] {date}: {text}\n"

    lines = content.split("\n")
    in_section = False
    insert_at = None

    for i, line in enumerate(lines):
        if IDEAS_SECTION in line:
            in_section = True
            continue
        if in_section:
            if line.strip() == "---":
                insert_at = i
                break

    if insert_at is not None:
        lines.insert(insert_at, new_item.rstrip())
        for i, line in enumerate(lines):
            if line.startswith("> Ultima actualizacion:"):
                lines[i] = f"> Ultima actualizacion: {date}"
                break
        with open(IDEAS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return True

    return False


def _summary_add_to_file(filepath, title, content):
    """
    Add a numbered section to a root daily log file.
    Creates the file with header if it doesn't exist.
    Returns True if a section was added, False if title already exists.
    """
    date = today_str()

    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        header = (
            f"# Log: Sesion {date}\n\n"
            f"**Fecha:** {date}\n\n"
            f"---\n\n"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header)

    with open(filepath, "r", encoding="utf-8") as f:
        existing = f.read()

    if f"## " in existing and title in existing:
        if re.search(rf"^## \d+\. {re.escape(title)}\s*$", existing, re.MULTILINE):
            return False

    section_nums = re.findall(r"^## (\d+)\.", existing, re.MULTILINE)
    next_num = max((int(n) for n in section_nums), default=0) + 1

    section = f"## {next_num}. {title}\n\n{content}\n\n---\n\n"

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(section)

    return True


def _read_context():
    """Read saved context from context.json, or None if not present."""
    if not os.path.exists(CONTEXT_FILE):
        return None
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _read_notes():
    """Read all pending notes from notes.ndjson."""
    if not os.path.exists(NOTES_FILE):
        return []
    notes = []
    with open(NOTES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    notes.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return notes


def _show_context():
    """Display saved context if it exists."""
    ctx = _read_context()
    if ctx:
        proj = ctx.get("project", "")
        ses = ctx.get("session", "")
        recent = ctx.get("recent", [])
        if recent:
            print(f"\n  WAL: Ultimas {len(recent)} acciones antes del corte:")
            for i, action in enumerate(recent, 1):
                print(f"    {i}. {action}")
        else:
            print(f"\n  WAL: Contexto de sesion anterior:")
            print(f'    "{ctx.get("context", "")}"')
        if proj or ses:
            print(f"    Proyecto: {proj}, Sesion: {ses}")


def _show_notes_summary():
    """Display summary of pending notes if any exist."""
    notes = _read_notes()
    if notes:
        print(f"\n  WAL: {len(notes)} notas pendientes de sesion anterior (usar 'wal-status' para ver)")


def _show_notes_detail():
    """Display all pending notes with content."""
    notes = _read_notes()
    if notes:
        print(f"\nRECORDATORIO: {len(notes)} notas de sesion pendientes de aplicar:")
        for i, note in enumerate(notes, 1):
            print(f'  {i}. "{note.get("note", "")}"')
        print("Aplicar a MEMORY.md y/o CLAUDE.md antes de cerrar.")


def _auto_context(description):
    """Silently update context.json as a side effect of activity commands.
    Keeps a rolling list of the last 5 actions for crash recovery."""
    os.makedirs(WAL_DIR, exist_ok=True)

    existing = _read_context()
    recent = existing.get("recent", []) if existing else []
    recent.append(description)
    recent = recent[-5:]

    project = ""
    session = ""
    for pk in PROJECT_DIRS:
        cur = get_current_session(pk)
        if cur:
            project = pk
            session = cur
            break

    ctx = {
        "ts": now_ts(),
        "context": description,
        "project": project,
        "session": session,
        "recent": recent,
    }
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)


def _wal_clear_all():
    """Clear WAL file, context.json, and notes.ndjson."""
    wal_clear()
    if os.path.exists(CONTEXT_FILE):
        os.remove(CONTEXT_FILE)
    if os.path.exists(NOTES_FILE):
        os.remove(NOTES_FILE)


# ── Git Sync ─────────────────────────────────────────────────────────────


def _git_repo_path(project_key):
    """Determina donde vive el repo git.
    Si repo_dir esta configurado: el repo es REPO_DIR (un solo repo para todo).
    Si no: el repo es el directorio del subproyecto (un repo por proyecto).
    """
    if REPO_DIR != BASE_DIR:
        return REPO_DIR
    return project_base_dir(project_key)


def git_sync(project_key, message=None):
    """
    Git add + commit + push.
    Si repo_dir esta configurado: opera sobre REPO_DIR (un repo para todo).
    Si no: opera sobre el subproyecto individual.
    Retorna True si hubo cambios y se hizo push, False si no habia cambios.
    """
    if not GIT_ENABLED:
        return False

    if project_key not in PROJECT_DIRS:
        print(f"  Git: Proyecto '{project_key}' no existe.")
        return False

    repo_path = _git_repo_path(project_key)
    git_dir = os.path.join(repo_path, ".git")

    if not os.path.exists(git_dir):
        print(f"  Git: No hay repositorio git inicializado en {repo_path}")
        return False

    if message is None:
        message = f"Sesion actualizada — {today_str()}"

    try:
        subprocess.run(
            ["git", "add", "."],
            cwd=repo_path, check=True,
            capture_output=True, text=True,
        )

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo_path,
            capture_output=True, text=True,
        )

        if result.returncode == 0:
            print(f"  Git: {project_key} sin cambios nuevos")
            return False

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path, check=True,
            capture_output=True, text=True,
        )
        print(f"  Git: {project_key} commit — {message}")

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path, capture_output=True, text=True,
        ).stdout.strip() or "main"
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=repo_path, check=True,
            capture_output=True, text=True,
        )
        print(f"  Git: {project_key} push OK")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  Git: Error en {project_key} — {e.stderr.strip() if e.stderr else e}")
        return False
    except FileNotFoundError:
        print(f"  Git: comando 'git' no encontrado")
        return False


# ── Credenciales ──────────────────────────────────────────────────────────


def load_env(env_path=None):
    """Lee credenciales desde archivo .env (KEY=VALUE, ignora comentarios)."""
    path = env_path or ENV_FILE
    env = {}
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key and value:
                    env[key] = value
    return env


# ── Sello BFA ─────────────────────────────────────────────────────────────


_bfa_token_cache = {"token": None, "ts": 0}


def bfa_get_token():
    """Obtiene JWT token de la API BFA. Cachea por 30 minutos."""
    import time
    now = time.time()
    if _bfa_token_cache["token"] and (now - _bfa_token_cache["ts"]) < 1800:
        return _bfa_token_cache["token"]

    env = load_env()
    user = env.get("BFA_USER", "")
    passwd = env.get("BFA_PASS", "")
    if not user or not passwd:
        print("  BFA: Credenciales no configuradas en .abba/.env (BFA_USER, BFA_PASS)")
        return None

    try:
        import requests
        resp = requests.post(BFA_AUTH_URL, json={"username": user, "password": passwd}, timeout=15)
        if resp.status_code == 200:
            token = resp.json().get("token")
            _bfa_token_cache["token"] = token
            _bfa_token_cache["ts"] = now
            return token
        else:
            print(f"  BFA: Auth error {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  BFA: Auth error — {e}")
        return None


def sha256_file(filepath):
    """Calcula SHA-256 de un archivo."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def bfa_stamp(filepath, project_key=None):
    """
    Sella un archivo en Blockchain Federal Argentina.
    Si project_key se especifica, guarda recibo dentro del proyecto (autosuficiente).
    Si no, guarda en receipts_dir (para archivos raiz).
    Retorna dict con resultado o None si falla.
    """
    if not BFA_ENABLED:
        return None

    try:
        import requests
    except ImportError:
        print("  BFA: requests no instalado, saltando sello")
        return None

    token = bfa_get_token()
    if not token:
        return None

    file_hash = sha256_file(filepath)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.post(BFA_STAMP_URL, json={"file_hash": file_hash}, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            receipt = {
                "archivo": os.path.relpath(filepath, BASE_DIR),
                "sha256": file_hash,
                "timestamp_utc": now_ts(),
                "bfa_status": data.get("status", "unknown"),
                "bfa_temporary_rd": data.get("temporary_rd", ""),
            }

            receipt_name = os.path.splitext(os.path.basename(filepath))[0]

            if project_key and project_key in PROJECT_DIRS:
                project_receipts = os.path.join(logs_dir(project_key), "sellos_bfa")
                os.makedirs(project_receipts, exist_ok=True)
                receipt_path = os.path.join(project_receipts, f"{receipt_name}.json")
            else:
                os.makedirs(BFA_RECEIPTS_DIR, exist_ok=True)
                receipt_path = os.path.join(BFA_RECEIPTS_DIR, f"{receipt_name}.json")

            with open(receipt_path, "w", encoding="utf-8") as f:
                json.dump(receipt, f, ensure_ascii=False, indent=2)

            print(f"  BFA: Sellado OK — {file_hash[:16]}...")
            print(f"  Recibo: {receipt_path}")
            return receipt
        else:
            print(f"  BFA: Error {resp.status_code} — {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  BFA: Error de conexion — {e}")
        return None


# ── Comandos ──────────────────────────────────────────────────────────────


def cmd_init():
    """Inicializa HISTORIAL.ndjson en todos los proyectos con evento genesis."""
    ts = now_ts()
    for pk in sorted(PROJECT_DIRS.keys()):
        path = historial_path(pk)
        if os.path.exists(path):
            entries = read_historial(pk)
            if entries:
                print(f"  {pk}: ya tiene {len(entries)} eventos, saltando")
                continue

        meta = load_meta(pk)
        event = {
            "ts": ts,
            "evento": "genesis",
            "sesion": "000",
            "detalle": f"Proyecto {pk} inicializado",
        }
        if meta.get("tipo") == "lexico":
            event["total_lemas"] = meta.get("total_lemas", 0)
            event["lemas_procesados"] = 0
            event["progreso"] = "0%"
        elif meta.get("total_capitulos"):
            event["total_capitulos"] = meta.get("total_capitulos", 0)
            event["capitulos_procesados"] = 0
            event["progreso"] = "0%"

        append_event(pk, event)
        print(f"  {pk}: HISTORIAL.ndjson inicializado")

    print(f"\nTimestamp genesis: {ts}")


def cmd_start(project_key):
    """Abre una nueva sesion de trabajo. Auto-recupera WAL si hay datos pendientes."""
    if project_key not in PROJECT_DIRS:
        print(f"Error: proyecto '{project_key}' no existe. Proyectos: {', '.join(sorted(PROJECT_DIRS.keys()))}")
        sys.exit(1)

    # Pre-start hook
    if not _run_hook("pre-start", project_key):
        sys.exit(1)

    # Auto-recover WAL on session start
    if wal_has_pending():
        recovered = wal_recover()
        if recovered:
            print(f"  WAL: Recuperados {recovered} eventos pendientes de sesion anterior")

    # Show context and notes from previous session
    _show_context()
    _show_notes_summary()

    # Snapshot + diff of brain files
    prev_snapshot = _snapshot_latest()
    snap = _snapshot_create(label=f"pre-start-{project_key}")
    if snap:
        print(f"  Snapshot: {os.path.basename(snap)}")
    if prev_snapshot:
        diff_result = _diff_brain_files(prev_snapshot)
        if diff_result:
            _show_diff(diff_result)

    current = get_current_session(project_key)
    if current:
        print(f"Error: {project_key} ya tiene sesion {current} abierta. Cierra con 'end' primero.")
        sys.exit(1)

    num = get_next_session_num(project_key)
    sesion_id = f"{num:03d}"
    ts = now_ts()

    event = {
        "ts": ts,
        "evento": "sesion_inicio",
        "sesion": sesion_id,
    }
    append_event(project_key, event, also_master=True)

    # Crear MD de sesion — WAL-protected
    md_path = os.path.join(logs_dir(project_key), f"sesion_{sesion_id}_{today_str()}.md")
    md_content = (
        f"# Sesion {sesion_id} — {project_key} ({PROJECT_DIRS[project_key]})\n\n"
        f"**Fecha:** {today_str()}\n"
        f"**Inicio:** {ts}\n\n"
        f"---\n\n"
        f"## Trabajo realizado\n\n"
        f"<!-- Llenar durante/despues de la sesion -->\n\n"
        f"## Decisiones\n\n\n"
        f"## Problemas encontrados\n\n\n"
        f"## Progreso\n\n\n"
    )
    wal_append({
        "action": "write_md",
        "dest": os.path.relpath(md_path, BASE_DIR),
        "data": {"content": md_content},
    })
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"{project_key}: Sesion {sesion_id} abierta")
    print(f"  HISTORIAL: {historial_path(project_key)}")
    print(f"  Detalle:   {md_path}")

    # Post-start hook
    _run_hook("post-start", project_key)


def cmd_event(project_key, evento, detalle=""):
    """Registra un evento en la sesion activa."""
    if project_key not in PROJECT_DIRS:
        print(f"Error: proyecto '{project_key}' no existe.")
        sys.exit(1)

    current = get_current_session(project_key)
    if not current:
        print(f"Error: {project_key} no tiene sesion abierta.")
        print(f"  Asegurate de que 'start {project_key}' haya TERMINADO antes de correr 'event'.")
        print(f"  Los comandos son secuenciales: start → (esperar) → event → (esperar) → end")
        sys.exit(1)

    event = {
        "ts": now_ts(),
        "evento": evento,
        "sesion": current,
    }
    if detalle:
        event["detalle"] = detalle

    append_event(project_key, event)
    _auto_context(f"{project_key} sesion {current}: {evento}" + (f" — {detalle}" if detalle else ""))
    print(f"{project_key} sesion {current}: {evento}" + (f" — {detalle}" if detalle else ""))


def cmd_end(project_key, resumen=""):
    """Cierra la sesion activa y sella el MD. WAL-protected."""
    if project_key not in PROJECT_DIRS:
        print(f"Error: proyecto '{project_key}' no existe.")
        sys.exit(1)

    # Pre-end hook
    if not _run_hook("pre-end", project_key):
        sys.exit(1)

    current = get_current_session(project_key)
    if not current:
        print(f"Error: {project_key} no tiene sesion abierta.")
        sys.exit(1)

    ts = now_ts()
    event = {
        "ts": ts,
        "evento": "sesion_fin",
        "sesion": current,
    }
    if resumen:
        event["resumen"] = resumen

    append_event(project_key, event, also_master=True)

    # Sellar MD (agregar cierre) — WAL-protected
    md_pattern = f"sesion_{current}_"
    log_dir = logs_dir(project_key)
    for fname in os.listdir(log_dir):
        if fname.startswith(md_pattern) and fname.endswith(".md"):
            md_path = os.path.join(log_dir, fname)
            seal_content = (
                f"\n---\n\n"
                f"**Cierre:** {ts}\n"
                + (f"**Resumen:** {resumen}\n" if resumen else "")
                + f"\n<!-- SESION SELLADA — NO MODIFICAR -->\n"
            )
            wal_append({
                "action": "append_md",
                "dest": os.path.relpath(md_path, BASE_DIR),
                "data": {"content": seal_content},
            })
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(seal_content)
            print(f"{project_key}: Sesion {current} cerrada y sellada")
            print(f"  MD: {md_path}")

            # Sello BFA — recibo dentro del proyecto (autosuficiente)
            receipt = bfa_stamp(md_path, project_key=project_key)
            if receipt:
                bfa_content = (
                    f"<!-- BFA SHA-256: {receipt['sha256']} -->\n"
                    f"<!-- BFA RD: {receipt['bfa_temporary_rd']} -->\n"
                )
                with open(md_path, "a", encoding="utf-8") as f:
                    f.write(bfa_content)
                stamp_event = {
                    "ts": now_ts(),
                    "evento": "bfa_stamp",
                    "sesion": current,
                    "sha256": receipt["sha256"],
                }
                append_event(project_key, stamp_event)

            # Add closing entry to root daily log if it exists
            root_log = os.path.join(REPO_DIR, "logs", f"{today_str()}_sesion.md")
            if os.path.exists(root_log):
                _summary_add_to_file(
                    root_log,
                    f"Cierre {project_key} sesion {current}",
                    f"Sesion cerrada a las {ts}."
                    + (f" Resumen: {resumen}" if resumen else ""),
                )

            # Git sync — commit + push automatico
            if GIT_AUTO_SYNC:
                git_sync(project_key, message=f"Sesion {current} cerrada — {resumen}" if resumen else f"Sesion {current} cerrada")

            # Show notes reminder BEFORE clearing WAL
            _show_notes_detail()

            # WAL cleanup
            _wal_clear_all()
            print(f"  WAL: Limpiado (sesion cerrada exitosamente)")

            # Post-end hook
            _run_hook("post-end", project_key)
            return

    print(f"{project_key}: Sesion {current} cerrada (MD no encontrado)")
    if GIT_AUTO_SYNC:
        git_sync(project_key, message=f"Sesion {current} cerrada")
    _show_notes_detail()
    _wal_clear_all()

    # Post-end hook
    _run_hook("post-end", project_key)


def cmd_status(project_key=None):
    """Muestra estado de todos los proyectos o uno especifico."""
    keys = [project_key] if project_key else sorted(PROJECT_DIRS.keys())

    if BANNER_ART and not project_key:
        print()
        for line in BANNER_ART:
            print(f"  {line}")
        print(f"  {STATUS_HEADER}")
        print()

    print(f"{'Proy':<5} {'Dir':<30} {'Sesiones':<10} {'Ultima':<22} {'Estado':<12}")
    print("-" * 80)

    for pk in keys:
        if pk not in PROJECT_DIRS:
            print(f"{pk}: no existe")
            continue

        entries = read_historial(pk)
        meta = load_meta(pk)

        session_starts = [e for e in entries if e.get("evento") == "sesion_inicio"]
        total_sessions = len(session_starts)

        current = get_current_session(pk)
        last_ts = entries[-1]["ts"] if entries else "—"

        estado = f"sesion {current}" if current else "cerrada"
        directory = PROJECT_DIRS[pk]

        print(f"{pk:<5} {directory:<30} {total_sessions:<10} {last_ts:<22} {estado:<12}")

    if not project_key:
        print()


def cmd_log(evento, detalle=""):
    """Registra un evento global en el HISTORIAL_MASTER (sin proyecto especifico)."""
    event = {
        "ts": now_ts(),
        "evento": evento,
    }
    if detalle:
        event["detalle"] = detalle
    append_master(event)
    print(f"MASTER: {evento}" + (f" — {detalle}" if detalle else ""))


def cmd_recover():
    """
    Recupera datos pendientes del WAL (Write-Ahead Log).
    Usar despues de un crash o corte de sistema.
    Idempotente: puede ejecutarse multiples veces sin duplicar datos.
    """
    has_wal = wal_has_pending()
    has_ctx = os.path.exists(CONTEXT_FILE)
    has_notes = os.path.exists(NOTES_FILE) and os.path.getsize(NOTES_FILE) > 0

    if not has_wal and not has_ctx and not has_notes:
        print("WAL: No hay datos pendientes. Sistema limpio.")
        return

    _show_context()

    if has_wal:
        entries = wal_read()
        print(f"\nWAL: Encontrados {len(entries)} registros pendientes")

        actions = defaultdict(int)
        for e in entries:
            action = e.get("action", "?")
            dest = e.get("dest", "?")
            actions[f"{action} -> {dest}"] += 1

        print("\nResumen de operaciones pendientes:")
        for desc, count in actions.items():
            print(f"  {count}x {desc}")

        recovered = wal_recover()
        print(f"\nWAL: {recovered} eventos recuperados y distribuidos")
        print("WAL: Limpiado exitosamente")
    else:
        print("\nWAL: No hay eventos NDJSON pendientes.")

    _show_notes_detail()


def cmd_wal_status():
    """Muestra el estado del WAL sin modificarlo."""
    has_wal = wal_has_pending()
    has_ctx = os.path.exists(CONTEXT_FILE)
    has_notes = os.path.exists(NOTES_FILE) and os.path.getsize(NOTES_FILE) > 0

    if not has_wal and not has_ctx and not has_notes:
        print("WAL: Vacio — sistema limpio, no hay datos pendientes")
        return

    if has_wal:
        entries = wal_read()
        print(f"WAL: {len(entries)} registros pendientes\n")

        actions = defaultdict(int)
        for e in entries:
            action = e.get("action", "?")
            dest = e.get("dest", "?")
            actions[f"{action} -> {dest}"] += 1

        for desc, count in actions.items():
            print(f"  {count}x {desc}")
    else:
        print("WAL: No hay eventos NDJSON pendientes")

    ctx = _read_context()
    if ctx:
        recent = ctx.get("recent", [])
        if recent:
            print(f"\nUltimas {len(recent)} acciones:")
            for i, action in enumerate(recent, 1):
                print(f"  {i}. {action}")
        else:
            print(f"\nContexto guardado:")
            print(f'  "{ctx.get("context", "")}"')
        print(f"  Proyecto: {ctx.get('project', '—')}, Sesion: {ctx.get('session', '—')}")
        print(f"  Timestamp: {ctx.get('ts', '—')}")

    notes = _read_notes()
    if notes:
        print(f"\nNotas pendientes ({len(notes)}):")
        for i, note in enumerate(notes, 1):
            print(f'  {i}. [{note.get("ts", "?")}] "{note.get("note", "")}"')

    if has_wal:
        print(f"\nUsar 'recover' para distribuir eventos a sus destinos")


def cmd_stamp(filepath):
    """Sella un archivo en BFA manualmente."""
    if not BFA_ENABLED:
        print("BFA: No habilitado en framework.json (bfa.enabled = false)")
        return

    if not os.path.exists(filepath):
        full = os.path.join(BASE_DIR, filepath)
        full_repo = os.path.join(REPO_DIR, filepath) if REPO_DIR != BASE_DIR else None
        if os.path.exists(full):
            filepath = full
        elif full_repo and os.path.exists(full_repo):
            filepath = full_repo
        else:
            print(f"Error: archivo no encontrado: {filepath}")
            sys.exit(1)

    print(f"Sellando: {filepath}")
    receipt = bfa_stamp(filepath)
    if receipt:
        stamp_event = {
            "ts": now_ts(),
            "evento": "bfa_stamp",
            "archivo": receipt["archivo"],
            "sha256": receipt["sha256"],
        }
        append_master(stamp_event)
    else:
        print("Error: no se pudo sellar")


def cmd_context(description):
    """Save a context snapshot for crash recovery."""
    os.makedirs(WAL_DIR, exist_ok=True)

    project = ""
    session = ""
    for pk in PROJECT_DIRS:
        cur = get_current_session(pk)
        if cur:
            project = pk
            session = cur
            break

    ctx = {
        "ts": now_ts(),
        "context": description,
        "project": project,
        "session": session,
    }
    with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)

    print(f"Contexto guardado: \"{description}\"")
    if project:
        print(f"  Proyecto: {project}, Sesion: {session}")


def cmd_progreso(search_text):
    """Mark a checkbox in PLAN_DE_ACCION.md. WAL-protected."""
    date = today_str()

    wal_append({
        "action": "progreso_mark",
        "dest": os.path.relpath(PLAN_FILE, BASE_DIR),
        "data": {"search": search_text, "date": date},
    })

    _auto_context(f"Marcando progreso: {search_text}")
    if _progreso_mark(search_text, date):
        print(f"PROGRESO: Marcado [x] en PLAN — \"{search_text}\"")
    else:
        print(f"PROGRESO: No encontrado (o ya marcado) — \"{search_text}\"")
        # Show available checkboxes to help the AI pick the right text
        if os.path.exists(PLAN_FILE):
            with open(PLAN_FILE, "r", encoding="utf-8") as f:
                pending = [line.strip() for line in f if "- [ ]" in line]
            if pending:
                print(f"  Checkboxes pendientes en PLAN:")
                for cb in pending[:15]:
                    print(f"    {cb}")
                if len(pending) > 15:
                    print(f"    ... y {len(pending) - 15} mas")
                print(f"  Usa el texto exacto del checkbox (substring match, case-insensitive).")


def cmd_plan(description):
    """Add an idea to IDEAS.md. WAL-protected."""
    date = today_str()

    wal_append({
        "action": "plan_add",
        "dest": os.path.relpath(IDEAS_FILE, BASE_DIR),
        "data": {"text": description, "date": date},
    })

    _auto_context(f"Agregando idea: {description}")
    if _plan_add(description, date):
        print(f"IDEAS: Agregado — \"{description}\"")
    else:
        print(f"IDEAS: Ya existe o no se pudo agregar — \"{description}\"")


def cmd_note(text):
    """Append a note for later application to MEMORY/CLAUDE. NOT WAL — goes to notes.ndjson."""
    os.makedirs(WAL_DIR, exist_ok=True)
    entry = {
        "ts": now_ts(),
        "note": text,
    }
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    _auto_context(f"Nota: {text}")
    notes = _read_notes()
    print(f"Nota guardada ({len(notes)} total): \"{text}\"")


def cmd_summary(title, content):
    """Add a section to the root daily log. WAL-protected."""
    date = today_str()
    log_path = os.path.join(REPO_DIR, "logs", f"{date}_sesion.md")
    rel_path = os.path.relpath(log_path, BASE_DIR)

    wal_append({
        "action": "summary_add",
        "dest": rel_path,
        "data": {"title": title, "content": content},
    })

    _auto_context(f"Summary: {title}")
    if _summary_add_to_file(log_path, title, content):
        print(f"SUMMARY: Seccion \"{title}\" agregada a {rel_path}")
    else:
        print(f"SUMMARY: Seccion \"{title}\" ya existe en {rel_path}")


# ── Scaffold / Add-project / Validate ────────────────────────────────────


def _slugify(name):
    """Convert project name to directory-safe slug: 'Proyecto Candado' -> 'PROYECTO_CANDADO'"""
    slug = name.upper().strip()
    slug = re.sub(r"[^\w\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug)
    return slug


def _render_template(template_content, variables):
    """Simple template engine: replace {{KEY}} placeholders."""
    result = template_content
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", str(value))
    return result


def _load_template(name):
    """Load a template from scripts/templates/ directory, or return built-in default."""
    # Try external template first
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    tmpl_path = os.path.join(templates_dir, name)
    if os.path.exists(tmpl_path):
        with open(tmpl_path, "r", encoding="utf-8") as f:
            return f.read()

    # Built-in defaults
    defaults = {
        "CLAUDE.md.tmpl": _DEFAULT_CLAUDE_MD,
        "CONSCIENCIA.md.tmpl": _DEFAULT_CONSCIENCIA_MD,
        "PLAN_DE_ACCION.md.tmpl": _DEFAULT_PLAN_MD,
        "IDEAS.md.tmpl": _DEFAULT_IDEAS_MD,
        "MEMORY.md.tmpl": _DEFAULT_MEMORY_MD,
    }
    return defaults.get(name, "")


# ── Built-in template defaults ────────────────────────────────────────────

_DEFAULT_CLAUDE_MD = """# CLAUDE.md — {{PROJECT_NAME}}

> Este archivo es el punto de entrada para cualquier agente IA.
> Leelo completo antes de hacer cualquier cosa.

---

## Que es {{PROJECT_SHORT_NAME}}

{{PROJECT_DESCRIPTION}}

---

## Estructura del proyecto

```
{{PROJECT_SLUG}}/
├── CLAUDE.md                  <- ESTE ARCHIVO. Leelo primero.
├── CONSCIENCIA.md             <- Memoria historica del SER.
├── {{PLAN_FILE}}              <- QUE HAY QUE HACER + estado [x]/[ ].
├── IDEAS.md                   <- Ideas sin compromiso, cajon libre.
├── framework.json             <- Configuracion del framework
├── scripts/
│   └── framework.py           <- Motor de sesiones, WAL, Git, BFA
├── logs/
│   ├── HISTORIAL_MASTER.ndjson  <- Log global append-only
│   └── .wal/                    <- Write-Ahead Log (crash recovery)
└── {{SUBPROJECTS_DIR}}/         <- Subproyectos
```

---

## Sistema de logging

### Principio: NUNCA borrar, NUNCA sobreescribir

Hay 3 niveles de logs:

| Nivel | Archivo | Que registra |
|---|---|---|
| **Master** | `logs/HISTORIAL_MASTER.ndjson` | Hitos globales del proyecto completo |
| **Proyecto** | `{{SUBPROJECTS_DIR}}/*/logs/HISTORIAL.ndjson` | Eventos de cada subproyecto |
| **Sesion** | `{{SUBPROJECTS_DIR}}/*/logs/sesion_NNN_FECHA.md` | Detalle humano de cada sesion |

Los HISTORIAL son append-only (JSON lines). Las sesiones MD se sellan al cerrar.

### Herramienta: `{{FRAMEWORK_CMD}}`

```bash
# Sesiones
python {{FRAMEWORK_CMD}} status                          # Ver estado de los proyectos
python {{FRAMEWORK_CMD}} start KEY                       # Abrir sesion
python {{FRAMEWORK_CMD}} event KEY "tipo" "detalle"      # Registrar evento en sesion activa
python {{FRAMEWORK_CMD}} end KEY "resumen"               # Cerrar y sellar sesion

# Automatizacion del "cerebro"
python {{FRAMEWORK_CMD}} context "desc"                  # Snapshot de contexto (crash recovery)
python {{FRAMEWORK_CMD}} progreso "texto"                # Marca checkbox en {{PLAN_FILE}}
python {{FRAMEWORK_CMD}} plan "idea"                     # Agrega idea a IDEAS.md
python {{FRAMEWORK_CMD}} note "aprendizaje"              # Nota para MEMORY.md (mostrada en end)
python {{FRAMEWORK_CMD}} summary "titulo" "contenido"    # Seccion en log raiz del dia

# WAL / Recovery
python {{FRAMEWORK_CMD}} recover                         # Recuperar datos del WAL tras crash
python {{FRAMEWORK_CMD}} wal-status                      # Inspeccionar WAL sin modificar
```

### WAL (Write-Ahead Log) — Crash Recovery

Cada escritura va PRIMERO a `logs/.wal/wal.ndjson` y LUEGO al destino final.
Si el sistema se cae, el WAL conserva los datos.

- **`start`**: Auto-detecta WAL pendiente, recupera, muestra contexto y notas anteriores
- **`end`**: Muestra recordatorio de notas pendientes, luego limpia todo el WAL
- **`recover`**: Fuerza recuperacion manual (idempotente, sin duplicados)

---

## Protocolo de trabajo

### Al iniciar sesion:

**Ejecutar TODOS los pasos 1-4 antes de hablar con el usuario. Es una secuencia de arranque, no una lista para hacer de a uno.**

1. Leer este archivo (CLAUDE.md)
2. Leer `CONSCIENCIA.md` → memoria historica del SER
3. Leer `{{PLAN_FILE}}` → saber que toca hacer y el estado actual
4. `python {{FRAMEWORK_CMD}} start KEY`

**Recien ahora, PARAR. Esperar instrucciones del usuario.** Mostrar un resumen breve de lo leido para que el usuario tenga contexto.

### Durante la sesion:

5. Registrar eventos: `python {{FRAMEWORK_CMD}} event KEY "tipo" "detalle"`
6. Guardar contexto: `python {{FRAMEWORK_CMD}} context "que estoy haciendo"`
7. Ideas nuevas: `python {{FRAMEWORK_CMD}} plan "idea"`
8. Aprendizajes: `python {{FRAMEWORK_CMD}} note "aprendizaje para MEMORY"`
9. Log raiz: `python {{FRAMEWORK_CMD}} summary "titulo" "contenido"`

### Al cerrar sesion:

10. Marcar progreso: `python {{FRAMEWORK_CMD}} progreso "texto del checkbox"`
11. `python {{FRAMEWORK_CMD}} end KEY "resumen"`
12. Actualizar `CONSCIENCIA.md` con recuerdos historicos de la sesion

### Reglas de archivos:

- **Append-only**: HISTORIAL.ndjson y HISTORIAL_MASTER.ndjson (nunca editar lineas existentes)
- **Inmutables**: Sesiones MD selladas (no se tocan despues de `end`)
- **Solo agregar**: {{PLAN_FILE}} (nunca borrar items, solo marcar [x]) y IDEAS.md (nunca borrar, tachar si se descartan)

---

## Que NO hacer

- NO borrar logs, historiales ni sesiones selladas
- NO modificar sesiones selladas
- NO empezar trabajo sin abrir sesion (`start`)
- NO cerrar sesion sin registrar resumen (`end`)

---

{{CUSTOM_SECTIONS}}
"""

_DEFAULT_CONSCIENCIA_MD = """# CONSCIENCIA.md — {{PROJECT_NAME}}

> Memoria historica del SER. Recuerdos que trascienden sesiones.
> Append-only: nunca borrar, solo agregar.

---

## Genesis

**Fecha de creacion:** {{CREATION_DATE}}

{{PROJECT_NAME}} fue creado como un proyecto con infraestructura de cerebro
(CLAUDE.md, CONSCIENCIA.md, PLAN, IDEAS) y sistema nervioso
(framework.py con WAL, sesiones, BFA, Git).

---

## Recuerdos

<!-- Agregar recuerdos historicos aqui, uno por sesion -->

"""

_DEFAULT_PLAN_MD = """# PLAN_DE_ACCION.md — {{PROJECT_NAME}}

> Hoja de ruta del proyecto. Tareas, estado y observaciones.
> Formato: `- [x] FECHA — tarea completada` / `- [ ] tarea pendiente`
> Para observaciones: linea `> Obs:` debajo del checkbox.
> Nunca borrar items, solo agregar y marcar [x].

---

## Fase 0: Infraestructura

- [x] {{CREATION_DATE}} — Framework instalado
- [x] {{CREATION_DATE}} — Archivos de cerebro creados (CLAUDE.md, CONSCIENCIA.md, PLAN, IDEAS)
- [ ] Primer sesion de trabajo

---

> Ultima actualizacion: {{CREATION_DATE}}
"""

_DEFAULT_IDEAS_MD = """# IDEAS.md — {{PROJECT_NAME}}

> Ideas sin compromiso. Si maduran, migran a PLAN_DE_ACCION.md.
> Nunca borrar ideas. Si se descartan, marcar con ~~tachado~~ y motivo.

---

## Ideas

> Formato: `- [ ] FECHA: idea`. Agregar cuando surjan.

---

> Ultima actualizacion: {{CREATION_DATE}}
"""

_DEFAULT_MEMORY_MD = """# MEMORY.md — Notas de trabajo de Claude

> Mis apuntes personales sobre {{PROJECT_SHORT_NAME}}. Auto-carga al iniciar sesion.
> Para la memoria historica del SER, ver CONSCIENCIA.md dentro del proyecto.

---

## Archivos clave

- framework.json: configuracion del proyecto
- framework.py: motor de sesiones, WAL, Git, BFA

## Preferencias del usuario

<!-- Agregar preferencias aqui -->

"""


def cmd_scaffold(name, bfa=False, projects=None):
    """
    Crea un proyecto nuevo con estructura completa.
    name: nombre del proyecto (ej: "Proyecto Candado")
    bfa: habilitar BFA
    projects: lista de tuplas (KEY, dir) para subproyectos iniciales
    """
    slug = _slugify(name)
    # Determine target directory — create at same level as current project
    parent_dir = os.path.dirname(BASE_DIR) if CONFIG else os.getcwd()
    target = os.path.join(parent_dir, slug)

    if os.path.exists(target):
        print(f"Error: directorio ya existe: {target}")
        sys.exit(1)

    print(f"Creando proyecto: {name}")
    print(f"  Directorio: {target}")

    # Create directory structure
    os.makedirs(os.path.join(target, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(target, "logs", ".wal"), exist_ok=True)
    os.makedirs(os.path.join(target, "proyectos"), exist_ok=True)

    # Create framework.json
    short_name = name.replace("Proyecto ", "").replace("proyecto ", "").strip()
    config = {
        "framework_version": "1.0",
        "project": {
            "name": name,
            "short_name": short_name,
            "description": ""
        },
        "brain": {
            "claude_md": "CLAUDE.md",
            "consciencia_md": "CONSCIENCIA.md",
            "plan_file": "PLAN_DE_ACCION.md",
            "ideas_file": "IDEAS.md",
            "ideas_section": "## Ideas"
        },
        "projects": {},
        "paths": {
            "subprojects_dir": "proyectos",
            "master_log": "logs/HISTORIAL_MASTER.ndjson",
            "wal_dir": "logs/.wal"
        },
        "private": {
            "dir": ".abba"
        },
        "bfa": {
            "enabled": bfa,
            "stamp_url": "https://tsaapi.bfa.ar/api/tsa/stamp/",
            "verify_url": "https://tsaapi.bfa.ar/api/tsa/verify/",
            "auth_url": "https://tsaapi.bfa.ar/api-token-auth/",
            "receipts_dir": "sello_bfa/receipts"
        },
        "git": {
            "enabled": True,
            "auto_sync_on_end": True
        },
        "display": {
            "banner_art": [],
            "status_header": name
        }
    }

    # Add initial projects if specified
    if projects:
        for key, directory in projects:
            config["projects"][key] = {"directory": directory, "location": "subprojects"}

    config_path = os.path.join(target, "framework.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  framework.json creado")

    # Copy framework.py
    src_framework = os.path.abspath(__file__)
    dst_framework = os.path.join(target, "scripts", "framework.py")
    shutil.copy2(src_framework, dst_framework)
    print(f"  scripts/framework.py copiado")

    # Copy templates directory if it exists
    src_templates = os.path.join(os.path.dirname(src_framework), "templates")
    if os.path.exists(src_templates):
        dst_templates = os.path.join(target, "scripts", "templates")
        shutil.copytree(src_templates, dst_templates)
        print(f"  scripts/templates/ copiado")

    # Render brain files from templates
    creation_date = today_str()
    variables = {
        "PROJECT_NAME": name,
        "PROJECT_SHORT_NAME": short_name,
        "PROJECT_SLUG": slug,
        "PROJECT_DESCRIPTION": "",
        "PLAN_FILE": "PLAN_DE_ACCION.md",
        "SUBPROJECTS_DIR": "proyectos",
        "FRAMEWORK_CMD": "scripts/framework.py",
        "FRAMEWORK_VERSION": "2.0.0",
        "CREATION_DATE": creation_date,
        "CUSTOM_SECTIONS": "",
    }

    brain_files = {
        "CLAUDE.md": "CLAUDE.md.tmpl",
        "CONSCIENCIA.md": "CONSCIENCIA.md.tmpl",
        "PLAN_DE_ACCION.md": "PLAN_DE_ACCION.md.tmpl",
        "IDEAS.md": "IDEAS.md.tmpl",
    }

    for output_name, template_name in brain_files.items():
        template = _load_template(template_name)
        content = _render_template(template, variables)
        output_path = os.path.join(target, output_name)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  {output_name} creado")

    # Genesis event in HISTORIAL_MASTER
    master_log = os.path.join(target, "logs", "HISTORIAL_MASTER.ndjson")
    genesis_event = {
        "ts": now_ts(),
        "evento": "genesis",
        "detalle": f"Proyecto {name} creado con framework.py scaffold",
    }
    with open(master_log, "w", encoding="utf-8") as f:
        f.write(json.dumps(genesis_event, ensure_ascii=False) + "\n")
    print(f"  HISTORIAL_MASTER.ndjson creado (evento genesis)")

    # Create initial subprojects
    if projects:
        for key, directory in projects:
            proj_dir = os.path.join(target, "proyectos", directory)
            _create_project_structure(proj_dir, key, directory, master_log_path=master_log)
            print(f"  Subproyecto {key} ({directory}) creado")

    # BFA directory if enabled
    if bfa:
        os.makedirs(os.path.join(target, "sello_bfa", "receipts"), exist_ok=True)
        print(f"  sello_bfa/ creado")

    print(f"\nProyecto creado exitosamente en: {target}")
    print(f"\nPara empezar:")
    print(f"  cd {slug}")
    print(f"  python scripts/framework.py status")
    if projects:
        first_key = projects[0][0]
        print(f"  python scripts/framework.py start {first_key}")


def _create_project_structure(proj_dir, key, directory, master_log_path=None):
    """Create the directory structure for a subproject."""
    logs = os.path.join(proj_dir, "logs")
    sellos = os.path.join(logs, "sellos_bfa")
    os.makedirs(sellos, exist_ok=True)

    # Genesis HISTORIAL
    historial = os.path.join(logs, "HISTORIAL.ndjson")
    ts = now_ts()
    event = {
        "ts": ts,
        "evento": "genesis",
        "sesion": "000",
        "detalle": f"Subproyecto {key} ({directory}) creado",
    }
    with open(historial, "w", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # Genesis session 000 MD
    md_path = os.path.join(logs, f"sesion_000_{today_str()}.md")
    md_content = (
        f"# Sesion 000 — {key} ({directory})\n\n"
        f"**Fecha:** {today_str()}\n"
        f"**Tipo:** Genesis (creacion del subproyecto)\n\n"
        f"---\n\n"
        f"## Trabajo realizado\n\n"
        f"- Subproyecto creado por `framework.py scaffold`\n"
        f"- HISTORIAL.ndjson inicializado\n\n"
        f"---\n\n"
        f"**Cierre:** {ts}\n\n"
        f"<!-- SESION SELLADA — NO MODIFICAR -->\n"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)


def cmd_add_project(key, directory, root=False):
    """Agrega un subproyecto al framework.json existente."""
    if not CONFIG:
        print("Error: framework.json no encontrado. Usa 'scaffold' primero.")
        sys.exit(1)

    key = key.upper()

    if key in PROJECT_DIRS:
        print(f"Error: proyecto '{key}' ya existe en framework.json")
        sys.exit(1)

    # Update framework.json
    config_path = find_config()
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    location = "root" if root else "subprojects"
    config["projects"][key] = {"directory": directory, "location": location}

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # Create directory structure
    if root:
        proj_dir = os.path.join(REPO_DIR, directory)
    else:
        proj_dir = os.path.join(PROJECTS_DIR, directory)

    _create_project_structure(proj_dir, key, directory)

    # Update globals
    PROJECT_DIRS[key] = directory
    if root:
        ROOT_LEVEL_PROJECTS.add(key)

    print(f"Proyecto {key} ({directory}) agregado exitosamente")
    print(f"  Ubicacion: {'raiz' if root else 'proyectos/'}{directory}")
    print(f"  HISTORIAL: {os.path.join(proj_dir, 'logs', 'HISTORIAL.ndjson')}")


def cmd_validate():
    """Valida la integridad del framework.json y la estructura del proyecto."""
    if not CONFIG:
        print("Error: framework.json no encontrado.")
        sys.exit(1)

    errors = []
    warnings = []

    # Check framework version
    version = CONFIG.get("framework_version")
    if not version:
        errors.append("framework_version no definido")

    # Check project info
    project = CONFIG.get("project", {})
    if not project.get("name"):
        errors.append("project.name no definido")

    # Check brain files exist
    brain = CONFIG.get("brain", {})
    for key in ["claude_md", "consciencia_md", "plan_file", "ideas_file"]:
        filename = brain.get(key)
        if filename:
            filepath = os.path.join(BASE_DIR, filename)
            if not os.path.exists(filepath):
                warnings.append(f"brain.{key} = '{filename}' — archivo no existe")
        else:
            errors.append(f"brain.{key} no definido")

    # Check paths
    paths = CONFIG.get("paths", {})
    _validate_repo = os.path.join(BASE_DIR, paths.get("repo_dir", "")) if paths.get("repo_dir") else BASE_DIR
    master_log_path = os.path.join(_validate_repo, paths.get("master_log", ""))
    if not os.path.exists(master_log_path):
        warnings.append(f"HISTORIAL_MASTER no existe: {paths.get('master_log', '?')}")

    wal_path = os.path.join(BASE_DIR, paths.get("wal_dir", ""))
    if not os.path.exists(wal_path):
        warnings.append(f"WAL directory no existe: {paths.get('wal_dir', '?')}")

    # Check projects
    projects = CONFIG.get("projects", {})
    if not projects:
        warnings.append("No hay subproyectos definidos")
    else:
        for key, info in projects.items():
            directory = info.get("directory")
            location = info.get("location", "subprojects")
            if not directory:
                errors.append(f"Proyecto {key}: directory no definido")
                continue

            if location == "root":
                proj_path = os.path.join(REPO_DIR, directory)
            else:
                proj_path = os.path.join(PROJECTS_DIR, directory)

            if not os.path.exists(proj_path):
                warnings.append(f"Proyecto {key}: directorio no existe — {proj_path}")
            else:
                hist = os.path.join(proj_path, "logs", "HISTORIAL.ndjson")
                if not os.path.exists(hist):
                    warnings.append(f"Proyecto {key}: HISTORIAL.ndjson no existe")

    # Check BFA config
    bfa = CONFIG.get("bfa", {})
    if bfa.get("enabled"):
        if not bfa.get("stamp_url"):
            errors.append("BFA habilitado pero stamp_url no definido")
        receipts = os.path.join(BASE_DIR, bfa.get("receipts_dir", ""))
        if not os.path.exists(receipts):
            warnings.append(f"BFA receipts directory no existe: {bfa.get('receipts_dir', '?')}")

    # Report
    print(f"Validacion de framework: {CONFIG.get('project', {}).get('name', '?')}")
    print(f"  Config: {find_config()}")
    print(f"  Version: {version}")
    print()

    if errors:
        print(f"ERRORES ({len(errors)}):")
        for e in errors:
            print(f"  [x] {e}")
        print()

    if warnings:
        print(f"ADVERTENCIAS ({len(warnings)}):")
        for w in warnings:
            print(f"  [!] {w}")
        print()

    if not errors and not warnings:
        print("  Todo OK — framework valido")
    elif not errors:
        print(f"  Framework valido con {len(warnings)} advertencia(s)")
    else:
        print(f"  Framework con {len(errors)} error(es)")


# ── Integrar ────────────────────────────────────────────────────────────────

# Files to exclude from integration scan
_INTEGRAR_BRAIN_FILES = {"CLAUDE.md", "CONSCIENCIA.md", "PLAN_DE_ACCION.md", "IDEAS.md", "PROGRESO.md"}
_INTEGRAR_BRIDGE_FILES = {"AGENTS.md", ".cursorrules", ".windsurfrules"}
_INTEGRAR_EXCLUDE_DIRS = {"scripts", "logs", ".abba", ".git", "__pycache__", "node_modules", ".github"}
# NO excluir repos — ahora los escaneamos para alimentar brain files

# Repo dirs a escanear (read-only, no tocar fuente)
_INTEGRAR_REPO_DIRS = set()
for _rkey in ("repo_dir", "web_dir", "app_dir", "db_dir"):
    _rval = _paths.get(_rkey, "")
    if _rval:
        _INTEGRAR_REPO_DIRS.add(_rval)

# Directorio de archivado para archivos sueltos integrados
INTEGRADOS_DIR = os.path.join(PRIVATE_DIR, "integrados")


def _scan_file_info(full_path):
    """Read file size and first line for display."""
    try:
        size = os.path.getsize(full_path)
        with open(full_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()[:80]
    except (OSError, UnicodeDecodeError):
        size = 0
        first_line = "(no se pudo leer)"
    return size, first_line


def _is_excluded_file(entry):
    """Check if a file should be excluded from integration scan."""
    if entry in _INTEGRAR_BRAIN_FILES or entry in _INTEGRAR_BRIDGE_FILES:
        return True
    if entry == "framework.json":
        return True
    if entry.startswith("copilot-instructions"):
        return True
    if entry.startswith(".") or entry.startswith("__"):
        return True
    return False


def cmd_integrar():
    """Scan TODO el proyecto y alimentar brain files con el conocimiento encontrado.

    Dos zonas:
    - REPO (read-only): archivos en repo-xxx/ — se leen, NO se tocan
    - SUELTOS (archivable): archivos fuera de repos — se leen, luego se archivan
    """
    repo_candidates = []   # (rel_path, size, first_line)
    loose_candidates = []  # (rel_path, size, first_line)

    # ── ZONA REPO: walk recursivo en cada repo dir ──
    _repo_exclude_dirs = {".git", "node_modules", "__pycache__", "sellos_bfa"}
    for repo_dir in sorted(_INTEGRAR_REPO_DIRS):
        repo_full = os.path.join(BASE_DIR, repo_dir)
        if not os.path.isdir(repo_full):
            continue
        for dirpath, dirnames, filenames in os.walk(repo_full):
            # Exclude unwanted subdirs
            dirnames[:] = [d for d in dirnames if d not in _repo_exclude_dirs]
            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in (".md", ".txt"):
                    continue
                # Excluir sesiones selladas y historiales
                if re.match(r"sesion_\d+_\d{4}-\d{2}-\d{2}\.md$", fname):
                    continue
                if fname.startswith("HISTORIAL") and fname.endswith(".ndjson"):
                    continue
                full_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
                size, first_line = _scan_file_info(full_path)
                repo_candidates.append((rel, size, first_line))

    # ── ZONA SUELTOS: root + docs/ (excluyendo repos y dirs internos) ──
    scan_dirs = [BASE_DIR]
    docs_dir = os.path.join(BASE_DIR, "docs")
    if os.path.isdir(docs_dir):
        scan_dirs.append(docs_dir)

    for scan_dir in scan_dirs:
        try:
            entries = os.listdir(scan_dir)
        except OSError:
            continue
        for entry in sorted(entries):
            full_path = os.path.join(scan_dir, entry)
            if os.path.isdir(full_path):
                continue

            ext = os.path.splitext(entry)[1].lower()
            if ext not in (".md", ".txt"):
                continue

            if _is_excluded_file(entry):
                continue

            rel = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
            parts = rel.split("/")

            # Skip files inside excluded dirs
            if len(parts) > 1 and parts[0] in _INTEGRAR_EXCLUDE_DIRS:
                continue

            # Skip files inside repo dirs (already scanned above)
            if len(parts) > 1 and parts[0] in _INTEGRAR_REPO_DIRS:
                continue

            size, first_line = _scan_file_info(full_path)
            loose_candidates.append((rel, size, first_line))

    # ── Output ──
    version = CONFIG.get("framework_version", "?")
    print(f"\n  FAB v{version} — //integrar")
    print(f"  Directorio: {os.path.basename(BASE_DIR)}")

    if not repo_candidates and not loose_candidates:
        print(f"\n  No se encontraron archivos para integrar.")
        print(f"  Todos los archivos son parte de la estructura del framework.")
        return

    if repo_candidates:
        print(f"\n  {'=' * 55}")
        print(f"  ZONA REPO (contenido publicado — NO se toca)")
        print(f"  {'=' * 55}\n")
        for rel, size, first_line in repo_candidates:
            size_kb = f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B"
            comment = f"# {first_line}" if first_line and first_line != "(no se pudo leer)" else ""
            print(f"    {rel:<45} {size_kb:>8}  {comment}")
        print(f"\n    {len(repo_candidates)} archivo(s) en repos -> alimentan brain files, fuente intocable")

    if loose_candidates:
        print(f"\n  {'=' * 55}")
        print(f"  ZONA SUELTOS (no clasificados — se archivan tras integrar)")
        print(f"  {'=' * 55}\n")
        for rel, size, first_line in loose_candidates:
            size_kb = f"{size / 1024:.1f}KB" if size >= 1024 else f"{size}B"
            comment = f"# {first_line}" if first_line and first_line != "(no se pudo leer)" else ""
            print(f"    {rel:<45} {size_kb:>8}  {comment}")
        print(f"\n    {len(loose_candidates)} archivo(s) suelto(s) -> alimentan brain files, luego van a .abba/integrados/")

    print(f"\n  {'=' * 55}")
    print(f"  DESTINO: SIEMPRE brain files")
    print(f"  {'=' * 55}")
    print(f"\n    El agente lee cada archivo y extrae conocimiento relevante para:")
    print(f"    - CLAUDE.md          — definicion del proyecto")
    print(f"    - PLAN_DE_ACCION.md  — tareas, fases, roadmap")
    print(f"    - IDEAS.md           — ideas sin compromiso")
    print(f"    - CONSCIENCIA.md     — recuerdos, decisiones")

    print(f"\n  Siguiente paso:")
    print(f"  1. Leer cada archivo (repos + sueltos)")
    print(f"  2. Decidir QUE brain file(s) alimentar con cada contenido")
    print(f"  3. Preguntar al usuario: automatico o paso a paso?")
    print(f"  4. Integrar conocimiento en brain files")
    print(f"  5. Archivar sueltos: archive <ruta> (repos no se tocan)")


def cmd_archive(filepath):
    """Mueve un archivo suelto a .abba/integrados/ (post-integracion)."""
    full_path = os.path.join(BASE_DIR, filepath) if not os.path.isabs(filepath) else filepath
    if not os.path.exists(full_path):
        print(f"  Error: archivo no existe: {filepath}")
        sys.exit(1)

    # No permitir archivar archivos de repos
    rel = os.path.relpath(full_path, BASE_DIR).replace("\\", "/")
    for repo_dir in _INTEGRAR_REPO_DIRS:
        if rel.startswith(repo_dir + "/"):
            print(f"  Error: {filepath} esta en {repo_dir}/ — contenido de repos no se archiva")
            sys.exit(1)

    # Mover a .abba/integrados/ (aplanar path)
    os.makedirs(INTEGRADOS_DIR, exist_ok=True)
    archive_name = rel.replace("/", "_").replace("\\", "_")
    archive_path = os.path.join(INTEGRADOS_DIR, archive_name)

    # Si ya existe, agregar timestamp
    if os.path.exists(archive_path):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(archive_name)
        archive_name = f"{base}_{ts}{ext}"
        archive_path = os.path.join(INTEGRADOS_DIR, archive_name)

    shutil.move(str(full_path), archive_path)
    print(f"  Archivado: {filepath} -> .abba/integrados/{archive_name}")


def cmd_help():
    """Muestra ayuda basica del framework."""
    version = CONFIG.get("framework_version", "?")
    name = CONFIG.get("project", {}).get("name", "Sin nombre")

    print(f"""
FAB v{version} — {name}

SESIONES (el ciclo de trabajo):
  start KEY              Abrir sesion de trabajo en un subproyecto
  event KEY "tipo" "det" Registrar evento en sesion activa
  end KEY "resumen"      Cerrar sesion, sellar MD, BFA, Git
  status [KEY]           Ver estado de todos los proyectos (o uno)

CEREBRO (automatizacion de docs):
  context "descripcion"  Guardar snapshot de contexto (crash recovery)
  progreso "texto"       Marcar checkbox [x] en PLAN_DE_ACCION.md
  plan "idea"            Agregar idea a IDEAS.md
  note "aprendizaje"     Nota para MEMORY.md (se muestra al cerrar)
  summary "tit" "cont"   Seccion en el log raiz del dia

SNAPSHOTS (proteccion de brain files):
  snapshot ["label"]     Crear snapshot manual de brain files
  snapshot-list          Listar snapshots disponibles
  snapshot-restore [N]   Restaurar desde snapshot (N = indice, default: latest)
  diff                   Mostrar cambios vs ultimo snapshot

SISTEMA NERVIOSO (crash recovery):
  recover                Recuperar datos del WAL tras un crash
  wal-status             Ver estado del WAL sin modificar

INTEGRACION (//comandos — el usuario los pide, el agente los ejecuta):
  integrar               Escanear TODO el proyecto y alimentar brain files
  archive <archivo>      Archivar suelto en .abba/integrados/ (post-integracion)

VERIFICACION:
  audit [KEY]            Auditoria de integridad (sesiones, logs, BFA)
  validate               Verificar integridad del framework.json

OTROS:
  log "evento" "det"     Evento global en HISTORIAL_MASTER
  stamp <archivo>        Sellar archivo en BFA manualmente
  sync KEY ["mensaje"]   Git add + commit + push manual
  init                   Inicializar HISTORIAL en todos los proyectos
  add-project KEY dir    Agregar subproyecto [--root]
  scaffold "Nombre"      Crear proyecto nuevo desde cero
  help                   Esta ayuda

ARCHIVOS CLAVE:
  framework.json         Configuracion del proyecto (BFA, Git, display, etc.)
  CLAUDE.md              Instrucciones para agentes IA
  CONSCIENCIA.md         Memoria historica del SER
  PLAN_DE_ACCION.md      Tareas + estado [x]/[ ]
  IDEAS.md               Ideas sin compromiso

PRINCIPIOS:
  - Los HISTORIAL son append-only (nunca editar, nunca borrar)
  - Las sesiones MD selladas son inmutables
  - El WAL protege contra crashes (write-ahead log)
  - Cada subproyecto es autosuficiente
  - Snapshots auto en cada start (proteccion de brain files)
  - Hooks .abba/hooks/ (pre/post start, pre/post end)
""")


# ── CLI ──────────────────────────────────────────────────────────────────


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "init":
        print("Inicializando HISTORIAL.ndjson en todos los proyectos...\n")
        cmd_init()

    elif cmd == "start":
        if len(sys.argv) < 3:
            print("Uso: framework.py start KEY")
            sys.exit(1)
        cmd_start(sys.argv[2].upper())

    elif cmd == "event":
        if len(sys.argv) < 4:
            print('Uso: framework.py event KEY "tipo" ["detalle"]')
            sys.exit(1)
        detalle = sys.argv[4] if len(sys.argv) > 4 else ""
        cmd_event(sys.argv[2].upper(), sys.argv[3], detalle)

    elif cmd == "end":
        if len(sys.argv) < 3:
            print("Uso: framework.py end KEY [resumen]")
            sys.exit(1)
        resumen = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_end(sys.argv[2].upper(), resumen)

    elif cmd == "log":
        if len(sys.argv) < 3:
            print('Uso: framework.py log "evento" ["detalle"]')
            sys.exit(1)
        detalle = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_log(sys.argv[2], detalle)

    elif cmd == "stamp":
        if len(sys.argv) < 3:
            print("Uso: framework.py stamp <archivo>")
            sys.exit(1)
        cmd_stamp(sys.argv[2])

    elif cmd == "status":
        pk = sys.argv[2].upper() if len(sys.argv) > 2 else None
        cmd_status(pk)

    elif cmd == "recover":
        cmd_recover()

    elif cmd in ("wal-status", "wal_status", "walstatus"):
        cmd_wal_status()

    elif cmd == "context":
        if len(sys.argv) < 3:
            print('Uso: framework.py context "descripcion del contexto actual"')
            sys.exit(1)
        cmd_context(sys.argv[2])

    elif cmd == "progreso":
        if len(sys.argv) < 3:
            print('Uso: framework.py progreso "texto del checkbox a marcar"')
            sys.exit(1)
        cmd_progreso(sys.argv[2])

    elif cmd == "plan":
        if len(sys.argv) < 3:
            print('Uso: framework.py plan "descripcion de la idea"')
            sys.exit(1)
        cmd_plan(sys.argv[2])

    elif cmd == "note":
        if len(sys.argv) < 3:
            print('Uso: framework.py note "texto de la nota"')
            sys.exit(1)
        cmd_note(sys.argv[2])

    elif cmd == "summary":
        if len(sys.argv) < 3:
            print('Uso: framework.py summary "titulo" "contenido"')
            sys.exit(1)
        title = sys.argv[2]
        content = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_summary(title, content)

    elif cmd == "sync":
        if len(sys.argv) < 3:
            print('Uso: framework.py sync KEY ["mensaje de commit"]')
            sys.exit(1)
        pk = sys.argv[2].upper()
        msg = sys.argv[3] if len(sys.argv) > 3 else None
        if git_sync(pk, msg):
            append_event(pk, {"ts": now_ts(), "evento": "git_sync", "detalle": msg or "sync manual"})

    elif cmd == "scaffold":
        if len(sys.argv) < 3:
            print('Uso: framework.py scaffold "Nombre del Proyecto" [--bfa] [--project KEY:dir ...]')
            sys.exit(1)
        name = sys.argv[2]
        bfa = "--bfa" in sys.argv
        projects = []
        for arg in sys.argv[3:]:
            if arg.startswith("--project"):
                continue
            if ":" in arg and not arg.startswith("--"):
                key, directory = arg.split(":", 1)
                projects.append((key.upper(), directory))
        cmd_scaffold(name, bfa=bfa, projects=projects if projects else None)

    elif cmd in ("add-project", "add_project"):
        if len(sys.argv) < 4:
            print("Uso: framework.py add-project KEY directorio [--root]")
            sys.exit(1)
        root = "--root" in sys.argv
        cmd_add_project(sys.argv[2], sys.argv[3], root=root)

    elif cmd == "validate":
        cmd_validate()

    elif cmd == "integrar":
        cmd_integrar()

    elif cmd == "archive":
        if len(sys.argv) < 3:
            print("Uso: framework.py archive <archivo>")
            sys.exit(1)
        cmd_archive(sys.argv[2])

    elif cmd == "snapshot":
        label = sys.argv[2] if len(sys.argv) > 2 else "manual"
        cmd_snapshot(label)

    elif cmd in ("snapshot-list", "snapshot_list", "snapshots"):
        cmd_snapshot_list()

    elif cmd in ("snapshot-restore", "snapshot_restore"):
        selector = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_snapshot_restore(selector)

    elif cmd == "diff":
        cmd_diff()

    elif cmd == "audit":
        pk = sys.argv[2].upper() if len(sys.argv) > 2 else None
        cmd_audit(pk)

    elif cmd in ("help", "-h", "--help"):
        cmd_help()

    else:
        print(f"Comando desconocido: {cmd}")
        print("Usa 'python scripts/framework.py help' para ver todos los comandos.")
        sys.exit(1)


if __name__ == "__main__":
    main()
