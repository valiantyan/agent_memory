#!/usr/bin/env bash
# 将 agent-memory 的 Codex hooks 安装到本机（可重复执行，合并已有 hooks.json）
# 用法：
#   bash scripts/install_codex_hooks.sh
#   bash scripts/install_codex_hooks.sh --with-prompt-search
#   AGENT_MEMORY_ROOT=/path bash scripts/install_codex_hooks.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/scripts/codex-hooks"
DEST="${HOME}/.codex/hooks/agent-memory"
HOOKS_JSON="${HOME}/.codex/hooks.json"
CODEX_DIR="${HOME}/.codex"
WITH_PROMPT_SEARCH=0

for arg in "$@"; do
  case "${arg}" in
    --with-prompt-search) WITH_PROMPT_SEARCH=1 ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
  esac
done

echo "==> agent-memory · 安装 Codex hooks"

# --- 解析 agent-memory 可执行文件 ---
AM_BIN="${AGENT_MEMORY_BIN:-}"
if [[ -z "${AM_BIN}" ]]; then
  if command -v agent-memory >/dev/null 2>&1; then
    AM_BIN="$(command -v agent-memory)"
  elif [[ -x "${REPO_ROOT}/.venv/bin/agent-memory" ]]; then
    AM_BIN="${REPO_ROOT}/.venv/bin/agent-memory"
  fi
fi
if [[ -z "${AM_BIN}" || ! -x "${AM_BIN}" ]]; then
  echo "error: 找不到 agent-memory。请先：" >&2
  echo "  cd ${REPO_ROOT} && python3 -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
  exit 1
fi

MEM_ROOT="${AGENT_MEMORY_ROOT:-${HOME}/.agent-memory}"

mkdir -p "${DEST}" "${CODEX_DIR}"
cp -f "${SRC}/_common.sh" "${SRC}/session_start.sh" "${SRC}/stop_turn.sh" \
  "${SRC}/user_prompt_maybe_search.sh" "${DEST}/"
chmod +x "${DEST}/"*.sh

printf '%s\n' "${AM_BIN}" >"${DEST}/agent-memory.path"
printf '%s\n' "${MEM_ROOT}" >"${DEST}/memory-root.path"

echo "    CLI : ${AM_BIN}"
echo "    ROOT: ${MEM_ROOT}"
echo "    hooks scripts → ${DEST}"

# --- 合并 hooks.json（Python，保留用户已有 hook，如 Muxy）---
export AM_DEST="${DEST}"
export AM_HOOKS_JSON="${HOOKS_JSON}"
export AM_WITH_PROMPT="${WITH_PROMPT_SEARCH}"

python3 <<'PY'
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

dest = Path(os.environ["AM_DEST"])
hooks_path = Path(os.environ["AM_HOOKS_JSON"])
with_prompt = os.environ.get("AM_WITH_PROMPT") == "1"

MARKER = "agent-memory-hook"
SESSION = f'bash {dest / "session_start.sh"} # agent-memory-hook session_start'
STOP = f'bash {dest / "stop_turn.sh"} # agent-memory-hook stop_turn'
PROMPT = f'bash {dest / "user_prompt_maybe_search.sh"} # agent-memory-hook user_prompt'

def load():
    if not hooks_path.is_file():
        return {"hooks": {}}
    raw = hooks_path.read_text(encoding="utf-8")
    if not raw.strip():
        return {"hooks": {}}
    data = json.loads(raw)
    if "hooks" not in data or not isinstance(data["hooks"], dict):
        data["hooks"] = {}
    return data

def is_ours(entry: dict) -> bool:
    """entry is a top-level list item: {hooks: [{command, type}, ...]} or flat."""
    # Codex shape: list of { "hooks": [ { "type", "command", ... } ] }
    if "hooks" in entry and isinstance(entry["hooks"], list):
        for h in entry["hooks"]:
            cmd = str(h.get("command") or "")
            if MARKER in cmd or "hooks/agent-memory/" in cmd:
                return True
        return False
    cmd = str(entry.get("command") or "")
    return MARKER in cmd or "hooks/agent-memory/" in cmd

def strip_ours(lst):
    if not isinstance(lst, list):
        return []
    return [e for e in lst if not is_ours(e)]

def block(command: str, timeout: int = 60) -> dict:
    return {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "timeout": timeout,
            }
        ]
    }

data = load()
hooks = data["hooks"]

# backup
if hooks_path.is_file():
    bak = hooks_path.with_suffix(
        hooks_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(hooks_path, bak)
    print(f"    backup: {bak}")

for key in ("SessionStart", "Stop", "UserPromptSubmit"):
    hooks[key] = strip_ours(hooks.get(key) or [])

# SessionStart: ours first
hooks["SessionStart"] = [block(SESSION, 60)] + hooks["SessionStart"]

# Stop: ours first, then existing (Muxy etc.)
hooks["Stop"] = [block(STOP, 60)] + hooks["Stop"]

if with_prompt:
    hooks["UserPromptSubmit"] = [block(PROMPT, 45)] + hooks.get(
        "UserPromptSubmit", []
    )
else:
    # leave other tools' UserPromptSubmit; only strip ours
    hooks["UserPromptSubmit"] = hooks.get("UserPromptSubmit") or []
    if not hooks["UserPromptSubmit"]:
        hooks.pop("UserPromptSubmit", None)

# drop empty lists
for k in list(hooks.keys()):
    if not hooks[k]:
        del hooks[k]

data["hooks"] = hooks
hooks_path.parent.mkdir(parents=True, exist_ok=True)
hooks_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"    wrote: {hooks_path}")
print(f"    with UserPromptSubmit search: {with_prompt}")
PY

# 尝试提示启用 features（不强制改用户 config，只检测）
CFG="${CODEX_DIR}/config.toml"
if [[ -f "${CFG}" ]]; then
  if ! grep -Eq 'codex_hooks\s*=\s*true' "${CFG}" 2>/dev/null; then
    echo ""
    echo "注意: 未在 ${CFG} 检测到 codex_hooks = true"
    echo "      若 hooks 不生效，请在 config.toml 中启用（以你本机 Codex 文档为准），例如："
    echo "      [features]"
    echo "      codex_hooks = true"
  fi
fi

echo ""
echo "==> 安装完成"
echo "    开聊: SessionStart → context → ~/.codex/memory-cache/last-context.md"
echo "    结束: Stop → checkpoint（读项目 .agent-memory/turn.json 或保底）"
echo "    卸载: bash ${REPO_ROOT}/scripts/uninstall_codex_hooks.sh"
echo ""
echo "建议验收:"
echo "  agent-memory --root \"${MEM_ROOT}\" doctor"
echo "  bash ${DEST}/session_start.sh && head -20 ~/.codex/memory-cache/last-context.md"
