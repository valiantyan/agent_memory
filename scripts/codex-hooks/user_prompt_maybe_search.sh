#!/usr/bin/env bash
# Codex UserPromptSubmit (v2.0.3):
#   1) L0 event + per-session intent-draft + auto work item (no focus steal)
#   2) Heuristic context retrieve/inject when task-like
# 标记: # agent-memory-hook user_prompt
set +e
set -u

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

am_load_hook_stdin

AM="$(am_resolve_bin)"
if [[ -z "${AM}" ]]; then
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"
CWD="$(am_workdir)"

PROMPT="${AM_HOOK_PROMPT:-}"
if [[ -z "${PROMPT}" ]]; then
  PROMPT="${CODEX_USER_PROMPT:-${USER_PROMPT:-}}"
fi

PROMPT="$(printf '%s' "${PROMPT}" | head -c 2000)"

if [[ -z "${PROMPT}" ]]; then
  exit 0
fi

ev_args=(
  --root "${ROOT}" event
  --kind user_prompt
  --summary "${PROMPT}"
  --cwd "${CWD}"
)
if [[ -n "${AM_HOOK_SESSION_ID:-}" ]]; then
  ev_args+=(--session-id "${AM_HOOK_SESSION_ID}")
fi

"${AM}" "${ev_args[@]}" \
  >"${CACHE}/last-event.out" 2>"${CACHE}/last-event.err"
chmod 600 "${CACHE}/last-event.out" "${CACHE}/last-event.err" 2>/dev/null || true

WANT_CTX=0
if printf '%s' "${PROMPT}" | grep -Eiq \
  'BUG|缺陷|修复|修一下|实现|添加|新增|重构|继续|断点|handoff|播放|列表|点击|报错|失败|卡住|不能|无法|搜索|fix|implement|feature|refactor|continue|resume|playlist|click|search|todo|任务|issue|crash|error|上次|之前|以前|怎么做|如何做|坑|决策|还是按|记忆|history|before|last time|how did'; then
  WANT_CTX=1
fi
PLEN=${#PROMPT}
if [[ "${PLEN}" -ge 48 ]]; then
  WANT_CTX=1
fi

if [[ "${WANT_CTX}" -ne 1 ]]; then
  am_log "user_prompt: event only (no context inject)"
  exit 0
fi

TMP_OUT="$(mktemp "${CACHE}/ps.XXXXXX" 2>/dev/null || mktemp)"
"${AM}" --root "${ROOT}" context --query "${PROMPT}" \
  >"${TMP_OUT}" 2>"${CACHE}/last-prompt-search.err"
ec=$?
chmod 600 "${CACHE}/last-prompt-search.err" 2>/dev/null || true

if [[ ${ec} -ne 0 || ! -s "${TMP_OUT}" ]]; then
  rm -f "${TMP_OUT}" 2>/dev/null
  am_log "user_prompt: context failed or empty"
  exit 0
fi

cp -f "${TMP_OUT}" "${CACHE}/last-prompt-search.md" 2>/dev/null
chmod 600 "${CACHE}/last-prompt-search.md" 2>/dev/null || true

MAX_INJECT="${AGENT_MEMORY_HOOK_INJECT_CHARS:-8000}"
BODY="$(am_truncate "${MAX_INJECT}" <"${TMP_OUT}")"

python3 -c "
import json, sys
body = sys.stdin.read()
out = {
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': body,
    }
}
print(json.dumps(out, ensure_ascii=False))
" <<<"${BODY}" 2>/dev/null || printf '%s' "${BODY}"

rm -f "${TMP_OUT}" 2>/dev/null
am_log "user_prompt: event+context injected sess=${AM_HOOK_SESSION_ID:-none}"
exit 0
