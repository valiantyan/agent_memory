#!/usr/bin/env bash
# Codex Stop → consume pending turn from MEMORY ROOT only (v2)
# Path: $AGENT_MEMORY_ROOT/meta/pending-turn/<project>.json
# No business-repo .agent-memory/ required.
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

PROJECT_ID="${AGENT_MEMORY_PROJECT_ID:-}"
if [[ -z "${PROJECT_ID}" && -f "${CWD}/.agent-memory-project" ]]; then
  PROJECT_ID="$(tr -d '[:space:]' <"${CWD}/.agent-memory-project" 2>/dev/null || true)"
fi
if [[ -z "${PROJECT_ID}" ]]; then
  # high confidence only
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

# Resolve pending path key (same sanitize as CLI)
KEY="$(
  python3 - <<PY 2>/dev/null || echo "_global"
import re
raw = """${PROJECT_ID}""".strip() or "_global"
key = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._") or "_global"
print(key[:80])
PY
)"

PENDING_DIR="${ROOT}/meta/pending-turn"
PENDING="${PENDING_DIR}/${KEY}.json"
if [[ ! -f "${PENDING}" && -n "${PROJECT_ID}" && -f "${PENDING_DIR}/_global.json" ]]; then
  PENDING="${PENDING_DIR}/_global.json"
  KEY="_global"
fi

if [[ ! -f "${PENDING}" ]]; then
  am_log "no-op: no pending turn at meta/pending-turn/${KEY}.json (use: agent-memory turn ...)"
  exit 0
fi

PARSE="$(
  python3 - "${PENDING}" <<'PY' 2>/dev/null
import json, shlex, sys
from pathlib import Path
try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    sys.exit(2)
if not isinstance(data, dict):
    sys.exit(2)
goal = (data.get("goal") or "").strip()
next_steps = (data.get("next_steps") or data.get("nextSteps") or "").strip()
decisions = (data.get("decisions") or "").strip()
project_id = (data.get("project_id") or "").strip()
if not goal or not next_steps:
    sys.exit(3)

def emit(k, v):
    print(f"{k}={shlex.quote(v)}")
emit("goal", goal)
emit("next_steps", next_steps)
emit("decisions", decisions)
emit("project_id", project_id)
sys.exit(0)
PY
)"
pec=$?
if [[ ${pec} -eq 3 ]]; then
  am_log "no-op: pending turn incomplete (need goal + next_steps)"
  exit 0
fi
if [[ ${pec} -ne 0 ]]; then
  am_log "no-op: pending turn parse failed"
  exit 0
fi

goal=""
next_steps=""
decisions=""
project_id=""
eval "${PARSE}"
if [[ -n "${project_id}" ]]; then
  PROJECT_ID="${project_id}"
fi
if [[ -z "${goal}" || -z "${next_steps}" ]]; then
  am_log "no-op: empty goal/next"
  exit 0
fi

# claim before checkpoint
STAMP="$(date +%Y%m%d%H%M%S 2>/dev/null || echo t)-$$-${RANDOM}"
PROC="${PENDING_DIR}/${KEY}.processing-${STAMP}.json"
if ! mv "${PENDING}" "${PROC}" 2>/dev/null; then
  am_log "no-op: could not claim pending turn"
  exit 0
fi

args=(--root "${ROOT}" checkpoint --goal "${goal}" --next-steps "${next_steps}")
if [[ -n "${decisions}" ]]; then
  args+=(--decisions "${decisions}")
fi
if [[ -n "${PROJECT_ID}" ]]; then
  args+=(--project-id "${PROJECT_ID}")
fi

"${AM}" "${args[@]}" \
  >"${CACHE}/last-checkpoint.out" 2>"${CACHE}/last-checkpoint.err"
ec=$?
chmod 600 "${CACHE}/last-checkpoint.out" "${CACHE}/last-checkpoint.err" 2>/dev/null || true

if [[ ${ec} -ne 0 ]]; then
  am_log "checkpoint failed exit=${ec}; restoring pending"
  if [[ ! -e "${PENDING}" ]]; then
    mv -f "${PROC}" "${PENDING}" 2>/dev/null || true
  fi
  exit 0
fi

DONE_DIR="${PENDING_DIR}/done"
mkdir -p "${DONE_DIR}" 2>/dev/null
mv -f "${PROC}" "${DONE_DIR}/${KEY}.done-${STAMP}.json" 2>/dev/null || rm -f "${PROC}" 2>/dev/null

python3 - "${DONE_DIR}" <<'PY' 2>/dev/null || true
import sys
from pathlib import Path
d = Path(sys.argv[1])
files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for old in files[10:]:
    try:
        old.unlink()
    except OSError:
        pass
PY

am_log "checkpoint ok project=${PROJECT_ID:-none} from pending-turn"
exit 0
