#!/usr/bin/env bash
# Codex UserPromptSubmit → 仅关键词时 context，并尝试注入 stdout
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

PROMPT="${AM_HOOK_PROMPT:-}"
if [[ -z "${PROMPT}" ]]; then
  # 兼容错误配置的 env（非首选）
  PROMPT="${CODEX_USER_PROMPT:-${USER_PROMPT:-}}"
fi

# 仅用用户 prompt 文本；勿把整段 stdin JSON 当 query
PROMPT="$(printf '%s' "${PROMPT}" | head -c 2000)"

if [[ -z "${PROMPT}" ]]; then
  exit 0
fi

if ! printf '%s' "${PROMPT}" | grep -Eiq \
  '上次|之前|以前|怎么做|如何做|坑|决策|还是按|记忆|history|before|last time|how did'; then
  exit 0
fi

TMP_OUT="$(mktemp "${CACHE}/ps.XXXXXX" 2>/dev/null || mktemp)"
"${AM}" --root "${ROOT}" context --query "${PROMPT}" \
  >"${TMP_OUT}" 2>"${CACHE}/last-prompt-search.err"
ec=$?
chmod 600 "${CACHE}/last-prompt-search.err" 2>/dev/null || true

if [[ ${ec} -ne 0 || ! -s "${TMP_OUT}" ]]; then
  rm -f "${TMP_OUT}" 2>/dev/null
  exit 0
fi

cp -f "${TMP_OUT}" "${CACHE}/last-prompt-search.md" 2>/dev/null
chmod 600 "${CACHE}/last-prompt-search.md" 2>/dev/null || true

MAX_INJECT="${AGENT_MEMORY_HOOK_INJECT_CHARS:-8000}"
BODY="$(am_truncate "${MAX_INJECT}" <"${TMP_OUT}")"

# 与 SessionStart 一致：优先 JSON additionalContext，失败再纯文本
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
am_log "conditional context injected"
exit 0
