"""agent-memory event — L0 audit log (+ session intent draft + auto work item)."""

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
from agent_memory.work_items import upsert_item


def run_event(
    root: Path,
    *,
    kind: str,
    summary: str = "",
    project_id: str | None = None,
    session_id: str | None = None,
    cwd: str | Path | None = None,
    draft_intent: bool = False,
    interrupt_intent: bool = False,
    clear_intent: bool = False,
    auto_item: bool = True,
) -> dict:
    require_schema_for_write(root)
    pid = (project_id or "").strip() or None
    sid = (session_id or "").strip() or None
    if pid is None and cwd is not None:
        det_id, conf = detect_project(Path(cwd))
        if conf == "high" and det_id:
            pid = det_id

    if clear_intent:
        clear_intent_draft(root, pid, sid)
        rec = append_event(
            root,
            kind=kind or "intent_cleared",
            summary=summary or "cleared",
            project_id=pid,
            session_id=sid,
        )
        return {"event": rec, "intent": "cleared", "project_id": pid, "session_id": sid}

    rec = append_event(
        root, kind=kind, summary=summary, project_id=pid, session_id=sid
    )
    intent_action = None
    item_id = None

    if interrupt_intent:
        n = mark_intent_interrupted(root, pid, sid)
        intent_action = f"interrupted:{n}" if n else None
    else:
        should_draft = bool(draft_intent) or (
            kind == "user_prompt" and looks_like_task(summary)
        )
        if should_draft and (summary or "").strip():
            try:
                write_intent_draft(
                    root,
                    text=summary,
                    project_id=pid,
                    session_id=sid,
                    status="open",
                )
                intent_action = "open"
            except ValueError:
                pass
            # P1: auto draft work item without stealing focus (parallel-safe)
            if auto_item and kind == "user_prompt":
                goal = (summary or "").strip()
                if len(goal) > 120:
                    goal = goal[:119] + "…"
                try:
                    meta = upsert_item(
                        root,
                        goal=goal,
                        next_steps="- (auto from user prompt; refine with turn)",
                        decisions="",
                        project_id=pid,
                        session_id=sid,
                        set_focus=False,
                        status="active",
                    )
                    item_id = meta.get("id")
                except ValueError:
                    pass

    return {
        "event": rec,
        "intent": intent_action,
        "project_id": pid,
        "session_id": sid,
        "item_id": item_id,
    }
