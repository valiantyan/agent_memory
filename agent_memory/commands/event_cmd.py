"""agent-memory event — L0 audit log (+ optional intent draft)."""

from __future__ import annotations

from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.events import append_event
from agent_memory.intent_draft import (
    clear_intent_draft,
    looks_like_task,
    mark_intent_interrupted,
    write_intent_draft,
)
from agent_memory.project_detect import detect_project


def run_event(
    root: Path,
    *,
    kind: str,
    summary: str = "",
    project_id: str | None = None,
    cwd: str | Path | None = None,
    draft_intent: bool = False,
    interrupt_intent: bool = False,
    clear_intent: bool = False,
) -> dict:
    require_schema_for_write(root)
    pid = (project_id or "").strip() or None
    if pid is None and cwd is not None:
        det_id, conf = detect_project(Path(cwd))
        if conf == "high" and det_id:
            pid = det_id

    if clear_intent:
        clear_intent_draft(root, pid)
        rec = append_event(
            root, kind=kind or "intent_cleared", summary=summary or "cleared", project_id=pid
        )
        return {"event": rec, "intent": "cleared", "project_id": pid}

    rec = append_event(root, kind=kind, summary=summary, project_id=pid)
    intent_action = None

    if interrupt_intent:
        if mark_intent_interrupted(root, pid):
            intent_action = "interrupted"
    else:
        should_draft = bool(draft_intent) or (
            kind == "user_prompt" and looks_like_task(summary)
        )
        if should_draft and (summary or "").strip():
            try:
                write_intent_draft(root, text=summary, project_id=pid, status="open")
                intent_action = "open"
            except ValueError:
                pass

    return {"event": rec, "intent": intent_action, "project_id": pid}
