#!/usr/bin/env bash
# 将 agent-memory 的 Codex hooks 安装到本机（可重复执行，合并已有 hooks.json）
# 用法：
#   bash scripts/install_codex_hooks.sh
#   bash scripts/install_codex_hooks.sh --with-prompt-search
#   bash scripts/install_codex_hooks.sh --no-prompt-search
#   bash scripts/install_codex_hooks.sh --project /path/to/repo
#   AGENT_MEMORY_ROOT=/path bash scripts/install_codex_hooks.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${REPO_ROOT}/scripts/codex-hooks"
DEST="${HOME}/.codex/hooks/agent-memory"
HOOKS_JSON="${HOME}/.codex/hooks.json"
CODEX_DIR="${HOME}/.codex"
# prompt search / L0 user_prompt: auto | on | off
# v2.0.2: with --project, triggers only on project (strip global agent-memory hooks)
#         without --project, install global triggers
#         --global-hooks: also keep/install global triggers (not recommended with --project)
PROMPT_MODE=on
PROJECT_DIR=""
GLOBAL_HOOKS=""  # empty=auto, on, off

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-prompt-search) PROMPT_MODE=on; shift ;;
    --no-prompt-search) PROMPT_MODE=off; shift ;;
    --global-hooks) GLOBAL_HOOKS=on; shift ;;
    --no-global-hooks) GLOBAL_HOOKS=off; shift ;;
    --project)
      PROJECT_DIR="${2:-}"
      if [[ -z "${PROJECT_DIR}" ]]; then
        echo "error: --project 需要目录参数" >&2
        exit 1
      fi
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
用法: bash scripts/install_codex_hooks.sh [选项]

  --with-prompt-search   安装 UserPromptSubmit（L0 event + 启发式检索，默认）
  --no-prompt-search     移除 UserPromptSubmit
  --project DIR          写入 DIR/.codex/hooks.json（推荐；触发只在项目）
  --global-hooks         强制安装/保留全局 ~/.codex/hooks.json 触发（默认：有 --project 则剥离全局）
  --no-global-hooks      强制不写全局触发（仅脚本+user rules）
  （默认无 --project）  安装全局 SessionStart/Stop/UserPrompt
  （默认有 --project）  只装项目触发 + 剥离全局 agent-memory 触发（防双写）

环境变量:
  AGENT_MEMORY_ROOT   记忆数据根（写入 memory-root.path）
  AGENT_MEMORY_BIN    agent-memory 可执行文件绝对路径

注意: 请在 ~/.codex/config.toml 的 [features] 中设置 codex_hooks = true
EOF
      exit 0
      ;;
    *)
      echo "error: unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

# resolve whether to install global *triggers*
# auto: project set → off; else on
if [[ -z "${GLOBAL_HOOKS}" ]]; then
  if [[ -n "${PROJECT_DIR}" ]]; then
    GLOBAL_HOOKS=off
  else
    GLOBAL_HOOKS=on
  fi
fi

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
if [[ -f "${SRC}/agent_rules_v2.md" ]]; then
  cp -f "${SRC}/agent_rules_v2.md" "${DEST}/agent_rules_v2.md"
  cp -f "${SRC}/agent_rules_v2.md" "${CODEX_DIR}/agent-memory-v2.rules.md"
fi
chmod +x "${DEST}/"*.sh

printf '%s\n' "${AM_BIN}" >"${DEST}/agent-memory.path"
printf '%s\n' "${MEM_ROOT}" >"${DEST}/memory-root.path"
chmod 600 "${DEST}/agent-memory.path" "${DEST}/memory-root.path" 2>/dev/null || true

# 可选：把 v2 规则块合并进用户级 ~/.codex/AGENTS.md（不改业务仓）
RULES_SRC="${CODEX_DIR}/agent-memory-v2.rules.md"
USER_AGENTS="${CODEX_DIR}/AGENTS.md"
if [[ -f "${RULES_SRC}" ]]; then
  python3 <<'PY'
from pathlib import Path
codex = Path.home() / ".codex"
rules = (codex / "agent-memory-v2.rules.md").read_text(encoding="utf-8")
begin = "<!-- agent-memory-v2-rules begin -->"
end = "<!-- agent-memory-v2-rules end -->"
block = f"{begin}\n{rules.rstrip()}\n{end}\n"
agents = codex / "AGENTS.md"
if agents.is_file():
    text = agents.read_text(encoding="utf-8")
    if begin in text and end in text:
        import re
        text = re.sub(
            re.escape(begin) + r".*?" + re.escape(end),
            block.strip(),
            text,
            count=1,
            flags=re.S,
        )
    else:
        text = text.rstrip() + "\n\n" + block
    agents.write_text(text, encoding="utf-8")
    print(f"    user rules merged: {agents}")
else:
    agents.write_text(block, encoding="utf-8")
    print(f"    user rules created: {agents}")
PY
fi

echo "    CLI : ${AM_BIN}"
echo "    ROOT: ${MEM_ROOT}"
echo "    hooks scripts → ${DEST}"
echo "    user rules → ${CODEX_DIR}/agent-memory-v2.rules.md (+ ~/.codex/AGENTS.md block)"
echo "    v2: pending turn under \$ROOT/meta/pending-turn/ (not business repos)"

export AM_DEST="${DEST}"
export AM_HOOKS_JSON="${HOOKS_JSON}"
export AM_PROMPT_MODE="${PROMPT_MODE}"
export AM_GLOBAL_HOOKS="${GLOBAL_HOOKS}"

python3 <<'PY'
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

dest = Path(os.environ["AM_DEST"])
hooks_path = Path(os.environ["AM_HOOKS_JSON"])
prompt_mode = os.environ.get("AM_PROMPT_MODE", "on")
global_hooks = os.environ.get("AM_GLOBAL_HOOKS", "on")

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

# backup + rotate
if hooks_path.is_file():
    bak = hooks_path.with_suffix(
        hooks_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
    shutil.copy2(hooks_path, bak)
    print(f"    backup: {bak}")
    rotate_backups(hooks_path, keep=3)

# always strip our triggers first
for key in ("SessionStart", "Stop", "UserPromptSubmit"):
    hooks[key] = strip_ours_list(hooks.get(key) or [])

want_prompt = prompt_mode != "off"
if global_hooks == "on":
    hooks["SessionStart"] = [block(SESSION_CMD, 60)] + hooks["SessionStart"]
    hooks["Stop"] = [block(STOP_CMD, 60)] + hooks["Stop"]
    if want_prompt:
        hooks["UserPromptSubmit"] = [block(PROMPT_CMD, 45)] + hooks.get(
            "UserPromptSubmit", []
        )
    print(f"    global triggers: INSTALLED (UserPrompt={want_prompt})")
else:
    # leave stripped — no agent-memory global triggers (Muxy etc. preserved)
    print("    global triggers: STRIPPED (project-only mode; no double-fire)")

for k in list(hooks.keys()):
    if not hooks[k]:
        del hooks[k]

data["hooks"] = hooks
hooks_path.parent.mkdir(parents=True, exist_ok=True)
hooks_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"    wrote: {hooks_path}")
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

# 可选：合并业务仓 .codex/hooks.json（不整文件覆盖，保留其它项目 hooks）
if [[ -n "${PROJECT_DIR}" ]]; then
  PROJECT_DIR="$(cd "${PROJECT_DIR}" && pwd)"
  mkdir -p "${PROJECT_DIR}/.codex"
  export AM_PROJECT_HOOKS="${PROJECT_DIR}/.codex/hooks.json"
  export AM_PROMPT_MODE_FOR_PROJECT="${PROMPT_MODE}"
  export AM_DEST="${DEST}"
  python3 <<'PY'
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

path = Path(os.environ["AM_PROJECT_HOOKS"])
dest = Path(os.environ["AM_DEST"])
prompt_mode = os.environ.get("AM_PROMPT_MODE_FOR_PROJECT", "auto")
MARKER = "agent-memory-hook"
session = 'bash "$HOME/.codex/hooks/agent-memory/session_start.sh" # agent-memory-hook session_start'
stop = 'bash "$HOME/.codex/hooks/agent-memory/stop_turn.sh" # agent-memory-hook stop_turn'
prompt = 'bash "$HOME/.codex/hooks/agent-memory/user_prompt_maybe_search.sh" # agent-memory-hook user_prompt'

def cmd_is_ours(cmd: str) -> bool:
    c = str(cmd or "")
    return MARKER in c or "/hooks/agent-memory/" in c

def strip_ours_list(lst):
    if not isinstance(lst, list):
        return []
    out = []
    for entry in lst:
        if not isinstance(entry, dict):
            continue
        inner = entry.get("hooks")
        if isinstance(inner, list):
            kept = [h for h in inner if isinstance(h, dict) and not cmd_is_ours(h.get("command", ""))]
            if kept:
                new_e = dict(entry)
                new_e["hooks"] = kept
                out.append(new_e)
            continue
        if not cmd_is_ours(entry.get("command", "")):
            out.append(entry)
    return out

def block(cmd, timeout=60):
    return {"hooks": [{"type": "command", "command": cmd, "timeout": timeout}]}

def had_prompt(hooks: dict) -> bool:
    for entry in hooks.get("UserPromptSubmit") or []:
        if not isinstance(entry, dict):
            continue
        for h in entry.get("hooks") or []:
            if isinstance(h, dict) and cmd_is_ours(h.get("command", "")):
                return True
        if cmd_is_ours(entry.get("command", "")):
            return True
    return False

if path.is_file():
    bak = path.with_suffix(path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(path, bak)
    print(f"    project backup: {bak}")
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        data = {"hooks": {}}
else:
    data = {"hooks": {}}
if "hooks" not in data or not isinstance(data["hooks"], dict):
    data["hooks"] = {}
hooks = data["hooks"]
had = had_prompt(hooks)
for key in ("SessionStart", "Stop", "UserPromptSubmit"):
    hooks[key] = strip_ours_list(hooks.get(key) or [])
hooks["SessionStart"] = [block(session, 60)] + hooks["SessionStart"]
hooks["Stop"] = [block(stop, 60)] + hooks["Stop"]
if prompt_mode == "off":
    want_prompt = False
else:
    want_prompt = True
if want_prompt:
    hooks["UserPromptSubmit"] = [block(prompt, 45)] + hooks.get("UserPromptSubmit", [])
elif not hooks.get("UserPromptSubmit"):
    hooks.pop("UserPromptSubmit", None)
for k in list(hooks.keys()):
    if not hooks[k]:
        del hooks[k]
data["hooks"] = hooks
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"    project hooks merged: {path}")
PY
fi

# 尽量确保 features.codex_hooks = true（不覆盖其它 features）
CFG="${CODEX_DIR}/config.toml"
if [[ -f "${CFG}" ]]; then
  if ! grep -Eq 'codex_hooks\s*=\s*true' "${CFG}" 2>/dev/null; then
    python3 <<'PY'
from pathlib import Path
p = Path.home() / ".codex" / "config.toml"
text = p.read_text(encoding="utf-8")
if "[features]" in text and "codex_hooks" not in text:
    text = text.replace("[features]\n", "[features]\ncodex_hooks = true\n", 1)
    p.write_text(text, encoding="utf-8")
    print("    enabled: [features] codex_hooks = true")
elif "codex_hooks" not in text:
    text += "\n[features]\ncodex_hooks = true\n"
    p.write_text(text, encoding="utf-8")
    print("    added: [features] codex_hooks = true")
else:
    print("    features.codex_hooks already configured")
PY
  else
    echo "    features.codex_hooks = true (already)"
  fi
fi

echo ""
echo "==> 安装完成 (v2.0.2)"
echo "    脚本: ${DEST}（实现始终在用户目录）"
echo "    全局触发: ${GLOBAL_HOOKS}（on=挂 ~/.codex/hooks.json；off=剥离 agent-memory 触发）"
if [[ -n "${PROJECT_DIR}" ]]; then
  echo "    项目触发: ${PROJECT_DIR}/.codex/hooks.json"
  echo "    推荐: --project 时默认 off 全局触发，避免双写"
fi
echo "    SessionStart: context + 当前任务优先级 + work items"
echo "    UserPrompt: L0 event + intent-draft + 启发式 context"
echo "    Stop: pending-turn→checkpoint（+ work item）；无则 interrupt intent"
echo "    数据: 只写 AGENT_MEMORY_ROOT；多任务见 working/items/"
echo "    卸载: bash ${REPO_ROOT}/scripts/uninstall_codex_hooks.sh [--purge-cache]"
echo ""
echo "建议验收:"
echo "  agent-memory --version   # 2.0.2"
echo "  agent-memory work list"
echo "  agent-memory checkpoint --goal 'A' --next-steps '- a' --project-id demo"
echo "  agent-memory checkpoint --goal 'B' --next-steps '- b' --project-id demo"
echo "  agent-memory work list   # 应同时有 A 与 B，focus=B"
