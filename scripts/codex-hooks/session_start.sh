#!/usr/bin/env bash
# Codex SessionStart → agent-memory context（读路径）
# 标记: # agent-memory-hook session_start
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

AM="$(am_resolve_bin || true)"
if [[ -z "${AM}" ]]; then
  am_log "skip: agent-memory not found (run install_codex_hooks.sh after pip install)"
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"
OUT="${CACHE}/last-context.md"
QUERY="${AGENT_MEMORY_CONTEXT_QUERY:-session start resume}"

set +e
"${AM}" --root "${ROOT}" context --query "${QUERY}" \
  >"${OUT}" 2>"${CACHE}/last-context.err"
ec=$?
set -e

if [[ ${ec} -ne 0 ]]; then
  am_log "context failed exit=${ec} root=${ROOT} (see ${CACHE}/last-context.err)"
  exit 0
fi

am_log "context ok → ${OUT}"
exit 0
