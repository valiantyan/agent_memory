"""Open / interrupted intent draft (v2.0.1) — not Working, not Semantic.

Written from user_prompt hooks when the message looks like a task.
Cleared when turn/checkpoint succeeds. Marked interrupted on Stop without turn.
Surfaced in context so a new session can resume even if Working is stale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_memory.events import sanitize_summary
from agent_memory.io_atomic import write_text_atomic
from agent_memory.pending_turn import sanitize_project_key
from agent_memory.util import now_iso

# Task-ish user text → keep a draft (hooks + CLI).
TASK_HINT = re.compile(
    r"(?i)"
    r"("
    r"BUG|缺陷|修复|修一下|实现|添加|新增|重构|继续|断点|handoff|"
    r"播放|列表|点击|报错|失败|卡住|不能|无法|"
    r"fix|implement|feature|refactor|continue|resume|playlist|click|"
    r"todo|任务|issue|crash|error"
    r")"
)


def intent_draft_dir(root: Path) -> Path:
    return root / "meta" / "intent-draft"


def intent_draft_path(root: Path, project_id: str | None) -> Path:
    return intent_draft_dir(root) / f"{sanitize_project_key(project_id)}.json"


def looks_like_task(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if TASK_HINT.search(s):
        return True
    # Longer free-form requests often are tasks even without keywords
    return len(s) >= 48


def write_intent_draft(
    root: Path,
    *,
    text: str,
    project_id: str | None = None,
    status: str = "open",
) -> Path:
    summary = sanitize_summary(text, max_len=400)
    if not summary:
        raise ValueError("intent text empty after sanitize")
    st = (status or "open").strip() or "open"
    if st not in ("open", "interrupted", "cleared"):
        st = "open"
    intent_draft_dir(root).mkdir(parents=True, exist_ok=True)
    path = intent_draft_path(root, project_id)
    payload: dict[str, Any] = {
        "text": summary,
        "project_id": (project_id or "").strip() or None,
        "status": st,
        "updated_at": now_iso(),
        "schema_version": "1.0.0",
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def read_intent_draft(root: Path, project_id: str | None = None) -> dict[str, Any] | None:
    path = intent_draft_path(root, project_id)
    if not path.is_file() and project_id:
        path = intent_draft_path(root, None)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("status") == "cleared":
        return None
    return data


def mark_intent_interrupted(root: Path, project_id: str | None = None) -> bool:
    data = read_intent_draft(root, project_id)
    if not data:
        # try project-specific path even if empty read via global
        path = intent_draft_path(root, project_id)
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
    if not isinstance(data, dict) or not data.get("text"):
        return False
    if data.get("status") == "cleared":
        return False
    data["status"] = "interrupted"
    data["updated_at"] = now_iso()
    path = intent_draft_path(root, data.get("project_id") or project_id)
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return True


def clear_intent_draft(root: Path, project_id: str | None = None) -> bool:
    """Remove draft files for project and _global if present."""
    removed = False
    for pid in {project_id, None}:
        path = intent_draft_path(root, pid)
        if path.is_file():
            try:
                path.unlink()
                removed = True
            except OSError:
                pass
    return removed
