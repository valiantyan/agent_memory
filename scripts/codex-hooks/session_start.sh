#!/usr/bin/env bash
# Codex SessionStart → context inject + v2 protocol (no business AGENTS required)
# 标记: # agent-memory-hook session_start
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

cp -f "${TMP_OUT}" "${OUT}" 2>/dev/null
chmod 600 "${OUT}" 2>/dev/null || true

V2_HINT=$(
  cat <<EOF

## Agent Memory v2 protocol (auto-injected; do not invent memory)
- All durable memory lives only under AGENT_MEMORY_ROOT (never business-repo data dirs).
- After each user turn with real work, write task essence:
  agent-memory turn --goal "..." --next-steps "- ..." --cwd .
  (Stop hook will checkpoint from meta/pending-turn/; no-op if missing.)
- User says 记住 / always: agent-memory remember --slot <slot> --content "..."
- No retrieval hit: do not claim memory says X. No secrets in memory.
- Switch tools: handoff / session-end when appropriate.
EOF
)

MAX_INJECT="${AGENT_MEMORY_HOOK_INJECT_CHARS:-12000}"
{
  cat "${TMP_OUT}"
  printf '%s\n' "${V2_HINT}"
} | am_truncate "${MAX_INJECT}" >"${CACHE}/inject.body" 2>/dev/null
BODY="$(cat "${CACHE}/inject.body" 2>/dev/null || cat "${TMP_OUT}")"
chmod 600 "${CACHE}/inject.body" 2>/dev/null || true

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
am_log "context+v2-protocol injected root=${ROOT}"
exit 0
