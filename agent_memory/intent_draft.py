"""Open / interrupted intent drafts (v2.0.3 session-scoped).

Per-session files so two Codex sessions in the same project do not overwrite
each other. Legacy project-only files still readable.
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

TASK_HINT = re.compile(
    r"(?i)"
    r"("
    r"BUG|缺陷|修复|修一下|实现|添加|新增|重构|继续|断点|handoff|"
    r"播放|列表|点击|报错|失败|卡住|不能|无法|搜索|历史|"
    r"fix|implement|feature|refactor|continue|resume|playlist|click|search|"
    r"todo|任务|issue|crash|error"
    r")"
)
_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def intent_draft_dir(root: Path) -> Path:
    return root / "meta" / "intent-draft"


def sanitize_session_key(session_id: str | None) -> str | None:
    raw = (session_id or "").strip()
    if not raw:
        return None
    key = _SAFE.sub("_", raw).strip("._")
    return (key[:64] or None)


def intent_draft_path(
    root: Path,
    project_id: str | None,
    session_id: str | None = None,
) -> Path:
    proj = sanitize_project_key(project_id)
    sess = sanitize_session_key(session_id)
    if sess:
        return intent_draft_dir(root) / f"{proj}__sess_{sess}.json"
    return intent_draft_dir(root) / f"{proj}.json"


def looks_like_task(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if TASK_HINT.search(s):
        return True
    return len(s) >= 48


def write_intent_draft(
    root: Path,
    *,
    text: str,
    project_id: str | None = None,
    session_id: str | None = None,
    status: str = "open",
) -> Path:
    summary = sanitize_summary(text, max_len=400)
    if not summary:
        raise ValueError("intent text empty after sanitize")
    st = (status or "open").strip() or "open"
    if st not in ("open", "interrupted", "cleared"):
        st = "open"
    intent_draft_dir(root).mkdir(parents=True, exist_ok=True)
    path = intent_draft_path(root, project_id, session_id)
    payload: dict[str, Any] = {
        "text": summary,
        "project_id": (project_id or "").strip() or None,
        "session_id": (session_id or "").strip() or None,
        "status": st,
        "updated_at": now_iso(),
        "schema_version": "1.0.0",
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def _load_path(path: Path) -> dict[str, Any] | None:
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


def read_intent_draft(
    root: Path,
    project_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    """Prefer session-specific draft; fall back to legacy project file."""
    if session_id:
        data = _load_path(intent_draft_path(root, project_id, session_id))
        if data:
            return data
    data = _load_path(intent_draft_path(root, project_id, None))
    if data:
        return data
    if project_id:
        return _load_path(intent_draft_path(root, None, session_id))
    return None


def list_intent_drafts(
    root: Path,
    *,
    project_id: str | None = None,
    include_interrupted: bool = True,
) -> list[dict[str, Any]]:
    """All open/interrupted drafts for project (or all projects). Newest first."""
    d = intent_draft_dir(root)
    if not d.is_dir():
        return []
    proj_key = sanitize_project_key(project_id) if project_id else None
    out: list[dict[str, Any]] = []
    for path in d.glob("*.json"):
        data = _load_path(path)
        if not data:
            continue
        st = data.get("status") or "open"
        if st == "open":
            pass
        elif include_interrupted and st == "interrupted":
            pass
        else:
            continue
        if proj_key:
            pid = data.get("project_id")
            # match project or files named with project prefix
            if pid and sanitize_project_key(str(pid)) != proj_key:
                if not path.name.startswith(proj_key):
                    continue
            elif not pid and not path.name.startswith(proj_key):
                continue
        data = dict(data)
        data["_path"] = path.name
        out.append(data)
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return out


def mark_intent_interrupted(
    root: Path,
    project_id: str | None = None,
    session_id: str | None = None,
) -> int:
    """Mark matching draft(s) interrupted. Returns count updated."""
    n = 0
    if session_id:
        path = intent_draft_path(root, project_id, session_id)
        data = _load_path(path)
        if data and data.get("text"):
            data["status"] = "interrupted"
            data["updated_at"] = now_iso()
            write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            n += 1
        return n
    # no session: interrupt open drafts for this project (incl. session files)
    for data in list_intent_drafts(root, project_id=project_id, include_interrupted=False):
        name = data.get("_path")
        if not name:
            continue
        path = intent_draft_dir(root) / name
        data = {k: v for k, v in data.items() if k != "_path"}
        data["status"] = "interrupted"
        data["updated_at"] = now_iso()
        write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        n += 1
    # legacy project file if still open
    path = intent_draft_path(root, project_id, None)
    data = _load_path(path)
    if data and data.get("status") == "open":
        data["status"] = "interrupted"
        data["updated_at"] = now_iso()
        write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        n += 1
    return n


def clear_intent_draft(
    root: Path,
    project_id: str | None = None,
    session_id: str | None = None,
) -> bool:
    """Clear session draft if session_id set; else clear project-scoped drafts only
    (legacy project file + not all sessions — when session known prefer session)."""
    removed = False
    if session_id:
        for pid in {project_id, None}:
            path = intent_draft_path(root, pid, session_id)
            if path.is_file():
                try:
                    path.unlink()
                    removed = True
                except OSError:
                    pass
        return removed
    # no session: remove legacy project files only (do not wipe all sessions)
    for pid in {project_id, None}:
        path = intent_draft_path(root, pid, None)
        if path.is_file():
            try:
                path.unlink()
                removed = True
            except OSError:
                pass
    return removed
