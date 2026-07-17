#!/usr/bin/env bash
# 将 agent-memory 的 Codex hooks 安装到本机（可重复执行，合并已有 hooks.json）
# 用法：
#   bash scripts/install_codex_hooks.sh
#   bash scripts/install_codex_hooks.sh --with-prompt-search
#   bash scripts/install_codex_hooks.sh --no-prompt-search
#   AGENT_MEMORY_ROOT=/path bash scripts/install_codex_hooks.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/scripts/codex-hooks"
DEST="${HOME}/.codex/hooks/agent-memory"
HOOKS_JSON="${HOME}/.codex/hooks.json"
CODEX_DIR="${HOME}/.codex"
# prompt search: auto | on | off
# auto = 若已安装过则保留，否则不装
PROMPT_MODE=auto

for arg in "$@"; do
  case "${arg}" in
    --with-prompt-search) PROMPT_MODE=on ;;
    --no-prompt-search) PROMPT_MODE=off ;;
    -h|--help)
      cat <<'EOF'
用法: bash scripts/install_codex_hooks.sh [选项]

  --with-prompt-search   安装 UserPromptSubmit 条件检索
  --no-prompt-search     移除 UserPromptSubmit 条件检索
  （默认）               若已安装过条件检索则保留，否则不装

环境变量:
  AGENT_MEMORY_ROOT   记忆数据根（写入 memory-root.path）
  AGENT_MEMORY_BIN    agent-memory 可执行文件绝对路径
EOF
      exit 0
      ;;
  esac
done

echo "==> agent-memory · 安装 Codex hooks"

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
chmod 700 "${DEST}" 2>/dev/null || true
cp -f "${SRC}/_common.sh" "${SRC}/session_start.sh" "${SRC}/stop_turn.sh" \
  "${SRC}/user_prompt_maybe_search.sh" "${DEST}/"
chmod +x "${DEST}/"*.sh

printf '%s\n' "${AM_BIN}" >"${DEST}/agent-memory.path"
printf '%s\n' "${MEM_ROOT}" >"${DEST}/memory-root.path"
chmod 600 "${DEST}/agent-memory.path" "${DEST}/memory-root.path" 2>/dev/null || true

echo "    CLI : ${AM_BIN}"
echo "    ROOT: ${MEM_ROOT}"
echo "    hooks scripts → ${DEST}"

export AM_DEST="${DEST}"
export AM_HOOKS_JSON="${HOOKS_JSON}"
export AM_PROMPT_MODE="${PROMPT_MODE}"

python3 <<'PY'
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

dest = Path(os.environ["AM_DEST"])
hooks_path = Path(os.environ["AM_HOOKS_JSON"])
prompt_mode = os.environ.get("AM_PROMPT_MODE", "auto")

MARKER = "agent-memory-hook"
SESSION_CMD = f'bash {dest / "session_start.sh"} # agent-memory-hook session_start'
STOP_CMD = f'bash {dest / "stop_turn.sh"} # agent-memory-hook stop_turn'
PROMPT_CMD = f'bash {dest / "user_prompt_maybe_search.sh"} # agent-memory-hook user_prompt'


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


def cmd_is_ours_relaxed(cmd: str) -> bool:
    c = str(cmd or "")
    return MARKER in c or f"{dest}/" in c or "/hooks/agent-memory/" in c


def strip_ours_list(lst):
    """Strip only our inner commands; keep sibling commands in same block."""
    if not isinstance(lst, list):
        return []
    out = []
    for entry in lst:
        if not isinstance(entry, dict):
            continue
        inner = entry.get("hooks")
        if isinstance(inner, list):
            kept = [
                h
                for h in inner
                if isinstance(h, dict) and not cmd_is_ours_relaxed(h.get("command", ""))
            ]
            if kept:
                new_e = dict(entry)
                new_e["hooks"] = kept
                out.append(new_e)
            continue
        # flat {type, command}
        if not cmd_is_ours_relaxed(entry.get("command", "")):
            out.append(entry)
    return out


def had_prompt(hooks: dict) -> bool:
    for entry in hooks.get("UserPromptSubmit") or []:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks") or []:
            if isinstance(h, dict) and cmd_is_ours_relaxed(h.get("command", "")):
                return True
        if cmd_is_ours_relaxed(entry.get("command", "")):
            return True
    return False


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


def rotate_backups(path: Path, keep: int = 3) -> None:
    parent = path.parent
    pattern = re.compile(re.escape(path.name) + r"\.bak-\d+$")
    baks = sorted(
        [p for p in parent.iterdir() if pattern.match(p.name)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in baks[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


data = load()
hooks = data["hooks"]
had = had_prompt(hooks)

# backup + rotate
if hooks_path.is_file():
    bak = hooks_path.with_suffix(
        hooks_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(hooks_path, bak)
    print(f"    backup: {bak}")
    rotate_backups(hooks_path, keep=3)

for key in ("SessionStart", "Stop", "UserPromptSubmit"):
    hooks[key] = strip_ours_list(hooks.get(key) or [])

hooks["SessionStart"] = [block(SESSION_CMD, 60)] + hooks["SessionStart"]
hooks["Stop"] = [block(STOP_CMD, 60)] + hooks["Stop"]

want_prompt = prompt_mode == "on" or (prompt_mode == "auto" and had)
if want_prompt:
    hooks["UserPromptSubmit"] = [block(PROMPT_CMD, 45)] + hooks.get(
        "UserPromptSubmit", []
    )
else:
    if not hooks.get("UserPromptSubmit"):
        hooks.pop("UserPromptSubmit", None)

for k in list(hooks.keys()):
    if not hooks[k]:
        del hooks[k]

data["hooks"] = hooks
hooks_path.parent.mkdir(parents=True, exist_ok=True)
hooks_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"    wrote: {hooks_path}")
print(f"    UserPromptSubmit search: {want_prompt} (mode={prompt_mode})")
PY

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
echo "    SessionStart: context → stdout 注入会话 + 私有缓存 ~/.codex/memory-cache/"
echo "    Stop: 仅当项目存在完整 .agent-memory/turn.json 时 checkpoint（否则 no-op，不冲 Working）"
echo "    卸载: bash ${REPO_ROOT}/scripts/uninstall_codex_hooks.sh [--purge-cache]"
echo ""
echo "建议验收:"
echo "  agent-memory --root \"${MEM_ROOT}\" doctor"
echo "  echo '{}' | bash ${DEST}/session_start.sh | head -c 200; echo"
echo "  # Stop 无 turn.json 应 no-op："
echo "  printf '%s\\n' \"{\\\"cwd\\\":\\\"${PWD}\\\"}\" | bash ${DEST}/stop_turn.sh"
