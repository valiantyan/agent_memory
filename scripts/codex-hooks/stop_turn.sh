#!/usr/bin/env bash
# Codex Stop → 仅当存在完整 turn.json 时 checkpoint（不发明 goal，不冲 Working）
# 标记: # agent-memory-hook stop_turn
# 契约：最终 exit 0；无 turn.json / 字段不全 → no-op
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
TURN_JSON="${CWD}/.agent-memory/turn.json"
PROJECT_ID="${AGENT_MEMORY_PROJECT_ID:-}"

if [[ -z "${PROJECT_ID}" && -f "${CWD}/.agent-memory-project" ]]; then
  PROJECT_ID="$(tr -d '[:space:]' <"${CWD}/.agent-memory-project" 2>/dev/null || true)"
fi

if [[ ! -f "${TURN_JSON}" ]]; then
  am_log "no-op: missing ${TURN_JSON} (will not invent Working)"
  exit 0
fi

# 解析 turn.json；失败则 no-op
PARSE_OUT="$(
  python3 - "${TURN_JSON}" <<'PY' 2>/dev/null
import json, shlex, sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception as e:
    print(f"ERROR={shlex.quote(str(e))}", file=sys.stderr)
    sys.exit(2)

if not isinstance(data, dict):
    sys.exit(2)

goal = (data.get("goal") or data.get("Goal") or "").strip()
next_steps = (data.get("next_steps") or data.get("nextSteps") or "").strip()
decisions = (data.get("decisions") or "").strip()
project_id = (data.get("project_id") or data.get("projectId") or "").strip()

# 完整契约：goal 与 next_steps 都必须非空，否则不写（防半成品冲掉 Working）
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
parse_ec=$?

if [[ ${parse_ec} -eq 3 ]]; then
  am_log "no-op: turn.json incomplete (need non-empty goal and next_steps)"
  exit 0
fi
if [[ ${parse_ec} -ne 0 ]]; then
  am_log "no-op: turn.json parse failed"
  exit 0
fi

goal=""
next_steps=""
decisions=""
project_id=""
eval "${PARSE_OUT}"

if [[ -n "${project_id}" ]]; then
  PROJECT_ID="${project_id}"
fi

if [[ -z "${goal}" || -z "${next_steps}" ]]; then
  am_log "no-op: empty goal/next after parse"
  exit 0
fi

# 先 claim turn.json，再 checkpoint，避免「写了 A、归档了 B」
DONE_DIR="${CWD}/.agent-memory"
mkdir -p "${DONE_DIR}" 2>/dev/null
STAMP="$(date +%Y%m%d%H%M%S 2>/dev/null || echo done)"
STAMP="${STAMP}-$$-${RANDOM}"
PROC="${DONE_DIR}/turn.processing-${STAMP}.json"
DONE="${DONE_DIR}/turn.done-${STAMP}.json"

if ! mv "${TURN_JSON}" "${PROC}" 2>/dev/null; then
  am_log "no-op: could not claim turn.json (already claimed or gone)"
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
  am_log "checkpoint failed exit=${ec} (see ${CACHE}/last-checkpoint.err); restoring turn.json"
  # 失败：尽量把文件还回 turn.json，便于重试（若已被新文件占用则保留 processing）
  if [[ ! -e "${TURN_JSON}" ]]; then
    mv -f "${PROC}" "${TURN_JSON}" 2>/dev/null || true
  fi
  exit 0
fi

mv -f "${PROC}" "${DONE}" 2>/dev/null || true

# 轮转：仅保留最近 5 个 turn.done-*.json
python3 - "${DONE_DIR}" <<'PY' 2>/dev/null || true
import sys
from pathlib import Path
d = Path(sys.argv[1])
files = sorted(d.glob("turn.done-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for old in files[5:]:
    try:
        old.unlink()
    except OSError:
        pass
# 清理残留 processing（异常中断）
for p in d.glob("turn.processing-*.json"):
    # 超过 1 天的 processing 才删，避免误伤并发
    try:
        import time
        if time.time() - p.stat().st_mtime > 86400:
            p.unlink()
    except OSError:
        pass
PY

am_log "checkpoint ok project=${PROJECT_ID:-none}"
exit 0
