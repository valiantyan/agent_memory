#!/usr/bin/env bash
# 仅移除 agent-memory 相关 Codex hooks，保留 Muxy 等其它 hook
set -euo pipefail

DEST="${HOME}/.codex/hooks/agent-memory"
HOOKS_JSON="${HOME}/.codex/hooks.json"

echo "==> 卸载 agent-memory Codex hooks"

if [[ -f "${HOOKS_JSON}" ]]; then
  python3 <<'PY'
import json
import shutil
from datetime import datetime
from pathlib import Path

hooks_path = Path.home() / ".codex" / "hooks.json"
MARKER = "agent-memory-hook"

def is_ours(entry: dict) -> bool:
    if "hooks" in entry and isinstance(entry["hooks"], list):
        for h in entry["hooks"]:
            cmd = str(h.get("command") or "")
            if MARKER in cmd or "hooks/agent-memory/" in cmd:
                return True
        return False
    cmd = str(entry.get("command") or "")
    return MARKER in cmd or "hooks/agent-memory/" in cmd

if not hooks_path.is_file():
    raise SystemExit(0)

raw = hooks_path.read_text(encoding="utf-8")
data = json.loads(raw) if raw.strip() else {"hooks": {}}
hooks = data.get("hooks") or {}
bak = hooks_path.with_suffix(
    hooks_path.suffix + f".bak-uninstall-{datetime.now().strftime('%Y%m%d%H%M%S')}"
)
shutil.copy2(hooks_path, bak)
print(f"    backup: {bak}")

for key in list(hooks.keys()):
    lst = hooks[key]
    if not isinstance(lst, list):
        continue
    hooks[key] = [e for e in lst if not is_ours(e)]
    if not hooks[key]:
        del hooks[key]

data["hooks"] = hooks
hooks_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(f"    cleaned: {hooks_path}")
PY
fi

if [[ -d "${DEST}" ]]; then
  rm -rf "${DEST}"
  echo "    removed: ${DEST}"
fi

echo "==> 完成（其它 hooks 已保留）"
