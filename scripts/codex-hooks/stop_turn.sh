#!/usr/bin/env bash
# Codex Stop → agent-memory checkpoint（写路径：任务态精华，非全文）
# 优先读 $CWD/.agent-memory/turn.json；否则保底 Working
# 标记: # agent-memory-hook stop_turn
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

AM="$(am_resolve_bin || true)"
if [[ -z "${AM}" ]]; then
  am_log "skip: agent-memory not found"
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"
CWD="${CODEX_CWD:-${PWD:-.}}"
TURN_JSON="${CWD}/.agent-memory/turn.json"
PROJECT_ID="${AGENT_MEMORY_PROJECT_ID:-}"

# 项目标记文件
if [[ -z "${PROJECT_ID}" && -f "${CWD}/.agent-memory-project" ]]; then
  PROJECT_ID="$(tr -d '[:space:]' <"${CWD}/.agent-memory-project")"
fi

goal=""
next_steps=""
decisions=""
project_id=""

if [[ -f "${TURN_JSON}" ]]; then
  eval "$(
    python3 - "${TURN_JSON}" <<'PY'
import json, shlex, sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

def emit(k, v):
    if v is None:
        v = ""
    print(f"{k}={shlex.quote(str(v))}")

emit("goal", data.get("goal") or data.get("Goal") or "")
emit("next_steps", data.get("next_steps") or data.get("nextSteps") or "")
emit("decisions", data.get("decisions") or "")
emit("project_id", data.get("project_id") or data.get("projectId") or "")
PY
  )"
  if [[ -n "${project_id}" ]]; then
    PROJECT_ID="${project_id}"
  fi
fi

if [[ -z "${goal}" ]]; then
  goal="（回合结束未提供 turn.json）请开聊先 context 确认任务态"
fi
if [[ -z "${next_steps}" ]]; then
  next_steps=$'- 确认 working/current.md\n- 继续未完成项或更新 goal'
fi

args=(--root "${ROOT}" checkpoint --goal "${goal}" --next-steps "${next_steps}")
if [[ -n "${decisions}" ]]; then
  args+=(--decisions "${decisions}")
fi
if [[ -n "${PROJECT_ID}" ]]; then
  args+=(--project-id "${PROJECT_ID}")
fi

set +e
"${AM}" "${args[@]}" \
  >"${CACHE}/last-checkpoint.out" 2>"${CACHE}/last-checkpoint.err"
ec=$?
set -e

if [[ ${ec} -ne 0 ]]; then
  am_log "checkpoint failed exit=${ec} (see ${CACHE}/last-checkpoint.err)"
  exit 0
fi

if [[ -f "${TURN_JSON}" ]]; then
  rm -f "${TURN_JSON}"
fi

am_log "checkpoint ok project=${PROJECT_ID:-none}"
exit 0
