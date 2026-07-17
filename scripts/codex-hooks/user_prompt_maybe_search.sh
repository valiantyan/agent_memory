#!/usr/bin/env bash
# Codex UserPromptSubmit → 条件 context（关键词才检索，避免每句全量）
# 标记: # agent-memory-hook user_prompt
set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

AM="$(am_resolve_bin || true)"
if [[ -z "${AM}" ]]; then
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"

PROMPT="${CODEX_USER_PROMPT:-${USER_PROMPT:-}}"
if [[ -z "${PROMPT}" && ! -t 0 ]]; then
  PROMPT="$(cat || true)"
fi
# 限长
PROMPT="$(printf '%s' "${PROMPT}" | head -c 2000)"

if [[ -z "${PROMPT}" ]]; then
  exit 0
fi

if ! printf '%s' "${PROMPT}" | grep -Eiq \
  '上次|之前|以前|怎么做|如何做|坑|决策|还是按|记忆|history|before|last time|how did'; then
  exit 0
fi

OUT="${CACHE}/last-prompt-search.md"
set +e
"${AM}" --root "${ROOT}" context --query "${PROMPT}" \
  >"${OUT}" 2>"${CACHE}/last-prompt-search.err"
set -e
am_log "conditional context → ${OUT}"
exit 0
