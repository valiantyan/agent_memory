#!/usr/bin/env bash
# agent-memory Codex hooks · 公共环境
# shellcheck disable=SC2034

# 永不因 hook 失败打断 Codex：调用方应 exit 0
am_log() { echo "agent-memory-hook: $*" >&2; }

am_resolve_bin() {
  if [[ -n "${AGENT_MEMORY_BIN:-}" && -x "${AGENT_MEMORY_BIN}" ]]; then
    echo "${AGENT_MEMORY_BIN}"
    return 0
  fi
  if command -v agent-memory >/dev/null 2>&1; then
    command -v agent-memory
    return 0
  fi
  # 安装器写入的指针
  local ptr="${HOME}/.codex/hooks/agent-memory/agent-memory.path"
  if [[ -f "${ptr}" ]]; then
    local p
    p="$(tr -d '[:space:]' <"${ptr}")"
    if [[ -n "${p}" && -x "${p}" ]]; then
      echo "${p}"
      return 0
    fi
  fi
  # 常见可编辑安装位置
  local c
  for c in \
    "${HOME}/.local/bin/agent-memory" \
    "/Users/yanhao/Downloads/grok/.venv/bin/agent-memory"
  do
    if [[ -x "${c}" ]]; then
      echo "${c}"
      return 0
    fi
  done
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
  echo "${d}"
}
