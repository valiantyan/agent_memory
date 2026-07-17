"""agent-memory checkpoint"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.expiry import run_lazy_expiry
from agent_memory.intent_draft import clear_intent_draft
from agent_memory.recent import append_recent
from agent_memory.security import gate_write_payload
from agent_memory.working import update_working_fields, working_path


def run_checkpoint(
    root: Path,
    *,
    goal: str | None = None,
    decisions: str | None = None,
    next_steps: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    related_ids: list[str] | None = None,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    run_lazy_expiry(root)

    parts = [p for p in (goal, decisions, next_steps) if p]
    warns = gate_write_payload(
        *parts,
        force=force,
        label="checkpoint",
    )
    for w in warns:
        if not quiet:
            print(w, file=sys.stderr)

    meta = update_working_fields(
        root,
        goal=goal,
        decisions=decisions,
        next_steps=next_steps,
        related_ids=related_ids,
        project_id=project_id if project_id is not None else ...,
        session_id=session_id if session_id is not None else ...,
    )
    try:
        rel = working_path(root).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = "working/current.md"
    append_recent(
        root,
        id="working_current",
        kind="working",
        path=rel,
        op="checkpoint",
    )
    # Working update means intent draft is no longer needed
    clear_intent_draft(root, meta.get("project_id") or project_id)
    return {
        "path": rel,
        "goal": meta.get("goal"),
        "updated_at": meta.get("updated_at"),
        "project_id": meta.get("project_id"),
    }
