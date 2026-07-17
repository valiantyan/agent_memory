#!/usr/bin/env bash
# agent-memory Codex hooks · 公共环境
# Codex 将事件 JSON 写入 stdin（cwd / prompt / session_id / …）
# shellcheck disable=SC2034

# 永不因 hook 失败打断 Codex：各脚本最终 exit 0
am_log() { echo "agent-memory-hook: $*" >&2; }

# 解析一次 stdin JSON → 导出 AM_HOOK_CWD / AM_HOOK_PROMPT / AM_HOOK_EVENT /
# AM_HOOK_SOURCE / AM_HOOK_SESSION_ID
# 若 stdin 非 JSON 或为空，不报错。
am_load_hook_stdin() {
  AM_HOOK_CWD=""
  AM_HOOK_PROMPT=""
  AM_HOOK_EVENT=""
  AM_HOOK_SOURCE=""
  AM_HOOK_SESSION_ID=""
  local raw
  raw="$(cat || true)"
  if [[ -z "${raw//[[:space:]]/}" ]]; then
    return 0
  fi
  # 将解析结果写成 eval 安全的 export 行
  local parsed
  parsed="$(
    HOOK_RAW="${raw}" python3 - <<'PY' 2>/dev/null || true
import json, os, shlex, sys
raw = os.environ.get("HOOK_RAW", "")
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)

def emit(k, v):
    if v is None:
        v = ""
    print(f"export {k}={shlex.quote(str(v))}")

emit("AM_HOOK_CWD", data.get("cwd") or data.get("CWD") or "")
# prompt 字段名随事件可能不同
prompt = (
    data.get("prompt")
    or data.get("user_prompt")
    or data.get("message")
    or data.get("text")
    or ""
)
emit("AM_HOOK_PROMPT", prompt)
emit("AM_HOOK_EVENT", data.get("hook_event_name") or data.get("hookEventName") or "")
emit("AM_HOOK_SOURCE", data.get("source") or "")
# session id (Codex / various hosts)
sess = (
    data.get("session_id")
    or data.get("sessionId")
    or data.get("conversation_id")
    or data.get("thread_id")
    or data.get("threadId")
    or ""
)
if not sess and isinstance(data.get("session"), dict):
    sess = data["session"].get("id") or data["session"].get("session_id") or ""
emit("AM_HOOK_SESSION_ID", sess)
PY
  )"
  if [[ -n "${parsed}" ]]; then
    # shellcheck disable=SC1090
    eval "${parsed}"
  fi
}

am_resolve_bin() {
  if [[ -n "${AGENT_MEMORY_BIN:-}" && -x "${AGENT_MEMORY_BIN}" ]]; then
    echo "${AGENT_MEMORY_BIN}"
    return 0
  fi
  if command -v agent-memory >/dev/null 2>&1; then
    command -v agent-memory
    return 0
  fi
  local ptr="${HOME}/.codex/hooks/agent-memory/agent-memory.path"
  if [[ -f "${ptr}" ]]; then
    local p
    p="$(tr -d '[:space:]' <"${ptr}")"
    if [[ -n "${p}" && -x "${p}" ]]; then
      echo "${p}"
      return 0
    fi
  fi
  # 仅相对用户本机常见位置，无开发者机器硬编码路径
  if [[ -x "${HOME}/.local/bin/agent-memory" ]]; then
    echo "${HOME}/.local/bin/agent-memory"
    return 0
  fi
  return 1
}

am_resolve_root() {
  if [[ -n "${AGENT_MEMORY_ROOT:-}" ]]; then
    echo "${AGENT_MEMORY_ROOT}"
    return 0
  fi
  local ptr="${HOME}/.codex/hooks/agent-memory/memory-root.path"
  if [[ -f "${ptr}" ]]; then
    local p
    p="$(tr -d '[:space:]' <"${ptr}")"
    if [[ -n "${p}" ]]; then
      echo "${p}"
      return 0
    fi
  fi
  echo "${HOME}/.agent-memory"
}

am_cache_dir() {
  local d="${HOME}/.codex/memory-cache"
  mkdir -p "${d}"
  chmod 700 "${d}" 2>/dev/null || true
  echo "${d}"
}

# 工作目录：stdin cwd > 环境 > PWD
am_workdir() {
  if [[ -n "${AM_HOOK_CWD:-}" && -d "${AM_HOOK_CWD}" ]]; then
    echo "${AM_HOOK_CWD}"
    return 0
  fi
  if [[ -n "${CODEX_CWD:-}" && -d "${CODEX_CWD}" ]]; then
    echo "${CODEX_CWD}"
    return 0
  fi
  echo "${PWD:-.}"
}

# 截断注入文本（字符数，Python len）
am_truncate() {
  local max="${1:-12000}"
  python3 -c "
import sys
max_n = int(sys.argv[1])
text = sys.stdin.read()
if len(text) <= max_n:
    sys.stdout.write(text)
else:
    sys.stdout.write(text[:max_n] + '\n…[truncated by agent-memory-hook]\n')
" "${max}" 2>/dev/null || head -c "${max}"
}
