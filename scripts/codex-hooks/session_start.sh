#!/usr/bin/env bash
# Codex SessionStart → context inject + v2 protocol (protocol budget reserved)
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

# v2.0.4: pass --cwd so context scopes to this workspace project (not foreign Working)
"${AM}" --root "${ROOT}" context --query "${QUERY}" --cwd "${CWD}" \
  >"${TMP_OUT}" 2>"${TMP_ERR}"
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
  cat <<'EOF'

## Agent Memory v2.0.4 protocol (auto-injected; do not invent memory)
- Durable memory ONLY under AGENT_MEMORY_ROOT.
- Context is scoped to THIS workspace project (cwd); never treat another project's Working as current.
- 当前任务: THIS project's open intents + focused item + other items for THIS project only.
- L0: UserPrompt → event(session_id) + per-session intent-draft + auto work item (no focus steal).
- turn → Stop → checkpoint (per-project focus). Parallel sessions/projects do not clobber.
- work list --project-id <id> | work focus --id <id>. No invent memory; no secrets.
EOF
)

# Reserve protocol at end: truncate CONTEXT only, always append full V2_HINT
MAX_INJECT="${AGENT_MEMORY_HOOK_INJECT_CHARS:-12000}"
BODY="$(
  CTX_FILE="${TMP_OUT}" HINT="${V2_HINT}" MAXN="${MAX_INJECT}" python3 - <<'PY' 2>/dev/null
import os
from pathlib import Path
ctx = Path(os.environ["CTX_FILE"]).read_text(encoding="utf-8", errors="replace")
hint = os.environ.get("HINT") or ""
max_n = int(os.environ.get("MAXN") or "12000")
# always keep full hint; truncate context head
budget = max(0, max_n - len(hint))
if len(ctx) > budget:
    ctx = ctx[:budget] + "\n…[truncated context by agent-memory-hook]\n"
print(ctx + hint, end="")
PY
)"
if [[ -z "${BODY}" ]]; then
  BODY="$(cat "${TMP_OUT}")${V2_HINT}"
fi

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
