#!/usr/bin/env bash
# 仅移除 agent-memory 相关 Codex hooks，保留 Muxy 等其它 hook
# 用法: bash scripts/uninstall_codex_hooks.sh [--purge-cache]
set -euo pipefail

DEST="${HOME}/.codex/hooks/agent-memory"
HOOKS_JSON="${HOME}/.codex/hooks.json"
PURGE_CACHE=0
for arg in "$@"; do
  case "${arg}" in
    --purge-cache) PURGE_CACHE=1 ;;
  esac
done

echo "==> 卸载 agent-memory Codex hooks"

if [[ -f "${HOOKS_JSON}" ]]; then
  export AM_DEST="${DEST}"
  python3 <<'PY'
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

hooks_path = Path.home() / ".codex" / "hooks.json"
dest = Path(os.environ.get("AM_DEST", Path.home() / ".codex" / "hooks" / "agent-memory"))
MARKER = "agent-memory-hook"


def cmd_is_ours(cmd: str) -> bool:
    c = str(cmd or "")
    return MARKER in c or f"{dest}/" in c or "/hooks/agent-memory/" in c


def strip_ours_list(lst):
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
                if isinstance(h, dict) and not cmd_is_ours(h.get("command", ""))
            ]
            if kept:
                new_e = dict(entry)
                new_e["hooks"] = kept
                out.append(new_e)
            continue
        if not cmd_is_ours(entry.get("command", "")):
            out.append(entry)
    return out


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

# rotate uninstall backups keep 3
pattern = re.compile(re.escape(hooks_path.name) + r"\.bak-uninstall-\d+$")
baks = sorted(
    [p for p in hooks_path.parent.iterdir() if pattern.match(p.name)],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
for old in baks[3:]:
    try:
        old.unlink()
    except OSError:
        pass

for key in list(hooks.keys()):
    hooks[key] = strip_ours_list(hooks.get(key) or [])
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

if [[ "${PURGE_CACHE}" -eq 1 ]]; then
  CACHE="${HOME}/.codex/memory-cache"
  if [[ -d "${CACHE}" ]]; then
    rm -rf "${CACHE}"
    echo "    purged: ${CACHE}"
  fi
else
  echo "    保留缓存 ~/.codex/memory-cache/（清理请加 --purge-cache）"
fi

echo "==> 完成（其它 hooks 已保留）"
