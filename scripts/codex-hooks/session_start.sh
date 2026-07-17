#!/usr/bin/env bash
# Codex SessionStart → agent-memory context，并注入会话（stdout）
# 标记: # agent-memory-hook session_start
# 契约：最终 exit 0；成功时 stdout = 可注入的 context 正文（Codex 作 developer context）
set +e
set -u

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_common.sh"

am_load_hook_stdin

AM="$(am_resolve_bin)"
if [[ -z "${AM}" ]]; then
  am_log "skip: agent-memory not found (run scripts/install_codex_hooks.sh)"
  exit 0
fi

ROOT="$(am_resolve_root)"
CACHE="$(am_cache_dir)"
OUT="${CACHE}/last-context.md"
QUERY="${AGENT_MEMORY_CONTEXT_QUERY:-}"
if [[ -z "${QUERY}" ]]; then
  QUERY="${AM_HOOK_SOURCE:-session start}"
fi
# 附带 cwd 项目名帮助召回
CWD="$(am_workdir)"
if [[ -f "${CWD}/.agent-memory-project" ]]; then
  pid="$(tr -d '[:space:]' <"${CWD}/.agent-memory-project" 2>/dev/null || true)"
  if [[ -n "${pid}" ]]; then
    QUERY="${QUERY} ${pid}"
  fi
fi

TMP_OUT="$(mktemp "${CACHE}/ctx.XXXXXX" 2>/dev/null || mktemp)"
TMP_ERR="$(mktemp "${CACHE}/ctx.err.XXXXXX" 2>/dev/null || mktemp)"

"${AM}" --root "${ROOT}" context --query "${QUERY}" >"${TMP_OUT}" 2>"${TMP_ERR}"
ec=$?

if [[ ${ec} -ne 0 ]]; then
  am_log "context failed exit=${ec} root=${ROOT}"
  if [[ -s "${TMP_ERR}" ]]; then
    head -c 500 "${TMP_ERR}" >&2
    echo >&2
  fi
  rm -f "${TMP_OUT}" "${TMP_ERR}" 2>/dev/null
  exit 0
fi

# 私有缓存副本（chmod 已在 am_cache_dir）
cp -f "${TMP_OUT}" "${OUT}" 2>/dev/null
chmod 600 "${OUT}" 2>/dev/null || true

# 注入上限：避免撑爆会话；T0+Working+语义通常远小于此
MAX_INJECT="${AGENT_MEMORY_HOOK_INJECT_CHARS:-12000}"
BODY="$(am_truncate "${MAX_INJECT}" <"${TMP_OUT}")"

# 优先 JSON additionalContext（Codex 文档支持）；失败则纯文本 stdout
python3 -c "
import json, sys
body = sys.stdin.read()
out = {
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': body,
    }
}
print(json.dumps(out, ensure_ascii=False))
" <<<"${BODY}" 2>/dev/null || printf '%s' "${BODY}"

rm -f "${TMP_OUT}" "${TMP_ERR}" 2>/dev/null
am_log "context injected + cache ${OUT}"
exit 0
