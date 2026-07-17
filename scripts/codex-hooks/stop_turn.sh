#!/usr/bin/env bash
# Codex Stop → claim then checkpoint from MEMORY ROOT pending-turn (v2)
# 标记: # agent-memory-hook stop_turn
set +e
set -u

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

am_load_hook_stdin

AM="$(am_resolve_bin)"
if [[ -z "${AM}" ]]; then
  am_log "skip: agent-memory not found"
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"
CWD="$(am_workdir)"
PENDING_DIR="${ROOT}/meta/pending-turn"
mkdir -p "${PENDING_DIR}/done" "${PENDING_DIR}/failed" 2>/dev/null

# --- resolve project id (env / marker / detect) ---
PROJECT_ID="${AGENT_MEMORY_PROJECT_ID:-}"
if [[ -z "${PROJECT_ID}" && -f "${CWD}/.agent-memory-project" ]]; then
  PROJECT_ID="$(tr -d '[:space:]' <"${CWD}/.agent-memory-project" 2>/dev/null || true)"
fi
if [[ -z "${PROJECT_ID}" ]]; then
  DET="$("${AM}" --root "${ROOT}" project-detect "${CWD}" --json 2>/dev/null)"
  PROJECT_ID="$(
    DET_JSON="${DET}" python3 - <<'PY' 2>/dev/null || true
import json, os
try:
    d = json.loads(os.environ.get("DET_JSON") or "")
except Exception:
    raise SystemExit(0)
if d.get("confidence") == "high" and d.get("project_id"):
    print(d["project_id"])
PY
  )"
fi

# sanitize key via env (no shell interpolation into Python source)
KEY="$(
  PROJECT_ID="${PROJECT_ID}" python3 - <<'PY' 2>/dev/null || echo "_global"
import os, re
raw = (os.environ.get("PROJECT_ID") or "").strip() or "_global"
key = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._") or "_global"
print(key[:80])
PY
)"

PENDING="${PENDING_DIR}/${KEY}.json"
# only use _global when we did not resolve a concrete project
if [[ ! -f "${PENDING}" && -z "${PROJECT_ID}" && -f "${PENDING_DIR}/_global.json" ]]; then
  PENDING="${PENDING_DIR}/_global.json"
  KEY="_global"
fi

if [[ ! -f "${PENDING}" ]]; then
  # v2.0.3: L0 stop + interrupt this session's intent only (if session known)
  ev_args=(--root "${ROOT}" event --kind stop_no_turn --summary "stop without pending turn" --cwd "${CWD}" --interrupt-intent)
  if [[ -n "${PROJECT_ID:-}" ]]; then
    ev_args+=(--project-id "${PROJECT_ID}")
  fi
  if [[ -n "${AM_HOOK_SESSION_ID:-}" ]]; then
    ev_args+=(--session-id "${AM_HOOK_SESSION_ID}")
  fi
  "${AM}" "${ev_args[@]}" \
    >"${CACHE}/last-stop-event.out" 2>"${CACHE}/last-stop-event.err" || true
  chmod 600 "${CACHE}/last-stop-event.out" "${CACHE}/last-stop-event.err" 2>/dev/null || true
  am_log "no-op: no pending turn meta/pending-turn/${KEY}.json (event+interrupt-intent)"
  exit 0
fi

# --- claim FIRST, then parse claimed file only ---
STAMP="$(date +%Y%m%d%H%M%S 2>/dev/null || echo t)-$$-${RANDOM}"
PROC="${PENDING_DIR}/${KEY}.processing-${STAMP}.json"
if ! mv "${PENDING}" "${PROC}" 2>/dev/null; then
  am_log "no-op: could not claim pending turn"
  exit 0
fi

PARSE="$(
  PROC_PATH="${PROC}" python3 - <<'PY' 2>/dev/null
import json, os, shlex, sys
from pathlib import Path
path = Path(os.environ["PROC_PATH"])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    sys.exit(2)
if not isinstance(data, dict):
    sys.exit(2)
goal = (data.get("goal") or "").strip()
next_steps = (data.get("next_steps") or data.get("nextSteps") or "").strip()
decisions = (data.get("decisions") or "").strip()
project_id = (data.get("project_id") or "").strip()
session_id = (data.get("session_id") or "").strip()
force = bool(data.get("force"))
if not goal or not next_steps:
    sys.exit(3)

def emit(k, v):
    print(f"{k}={shlex.quote(str(v))}")
emit("goal", goal)
emit("next_steps", next_steps)
emit("decisions", decisions)
emit("project_id", project_id)
emit("session_id", session_id)
emit("force_flag", "1" if force else "0")
sys.exit(0)
PY
)"
pec=$?

quarantine_proc() {
  local reason="$1"
  local dest="${PENDING_DIR}/failed/${KEY}.failed-${STAMP}.json"
  mv -f "${PROC}" "${dest}" 2>/dev/null || rm -f "${PROC}" 2>/dev/null
  am_log "quarantined pending (${reason}) → failed/"
}

if [[ ${pec} -eq 3 ]]; then
  quarantine_proc "incomplete"
  exit 0
fi
if [[ ${pec} -ne 0 ]]; then
  quarantine_proc "parse-failed"
  exit 0
fi

goal=""
next_steps=""
decisions=""
project_id=""
session_id=""
force_flag="0"
eval "${PARSE}"
if [[ -n "${project_id}" ]]; then
  PROJECT_ID="${project_id}"
fi
# prefer pending session_id; fall back to hook stdin
if [[ -z "${session_id}" && -n "${AM_HOOK_SESSION_ID:-}" ]]; then
  session_id="${AM_HOOK_SESSION_ID}"
fi
if [[ -z "${goal}" || -z "${next_steps}" ]]; then
  quarantine_proc "empty-fields"
  exit 0
fi

args=(--root "${ROOT}" checkpoint --goal "${goal}" --next-steps "${next_steps}")
if [[ -n "${decisions}" ]]; then
  args+=(--decisions "${decisions}")
fi
if [[ -n "${PROJECT_ID}" ]]; then
  args+=(--project-id "${PROJECT_ID}")
fi
if [[ -n "${session_id}" ]]; then
  args+=(--session-id "${session_id}")
fi
if [[ "${force_flag}" == "1" ]]; then
  args+=(--force)
fi

"${AM}" "${args[@]}" \
  >"${CACHE}/last-checkpoint.out" 2>"${CACHE}/last-checkpoint.err"
ec=$?
chmod 600 "${CACHE}/last-checkpoint.out" "${CACHE}/last-checkpoint.err" 2>/dev/null || true

if [[ ${ec} -ne 0 ]]; then
  # do not restore non-promotable loops: quarantine
  quarantine_proc "checkpoint-exit-${ec}"
  am_log "checkpoint failed exit=${ec} (see ${CACHE}/last-checkpoint.err)"
  exit 0
fi

DONE="${PENDING_DIR}/done/${KEY}.done-${STAMP}.json"
mv -f "${PROC}" "${DONE}" 2>/dev/null || rm -f "${PROC}" 2>/dev/null

# rotate done (10) + GC stale processing (>1 day) + failed (20)
python3 - "${PENDING_DIR}" <<'PY' 2>/dev/null || true
import sys, time
from pathlib import Path
base = Path(sys.argv[1])
now = time.time()
done = base / "done"
if done.is_dir():
    files = sorted(done.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[10:]:
        try:
            old.unlink()
        except OSError:
            pass
failed = base / "failed"
if failed.is_dir():
    files = sorted(failed.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[20:]:
        try:
            old.unlink()
        except OSError:
            pass
for p in base.glob("*.processing-*.json"):
    try:
        if now - p.stat().st_mtime > 86400:
            p.unlink()
    except OSError:
        pass
PY

ok_args=(--root "${ROOT}" event --kind stop_ok --summary "checkpoint from pending turn" --cwd "${CWD}" --no-auto-item)
if [[ -n "${PROJECT_ID:-}" ]]; then
  ok_args+=(--project-id "${PROJECT_ID}")
fi
if [[ -n "${session_id:-}" ]]; then
  ok_args+=(--session-id "${session_id}")
elif [[ -n "${AM_HOOK_SESSION_ID:-}" ]]; then
  ok_args+=(--session-id "${AM_HOOK_SESSION_ID}")
fi
"${AM}" "${ok_args[@]}" \
  >"${CACHE}/last-stop-event.out" 2>"${CACHE}/last-stop-event.err" || true

am_log "checkpoint ok project=${PROJECT_ID:-none} sess=${session_id:-${AM_HOOK_SESSION_ID:-none}}"
exit 0
