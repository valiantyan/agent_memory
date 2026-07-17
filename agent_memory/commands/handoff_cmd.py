"""agent-memory handoff"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import require_schema_for_write
from agent_memory.errors import UsageError
from agent_memory.frontmatter import dump
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.security import gate_write_payload
from agent_memory.util import now_iso
from agent_memory.working import update_working_fields


def run_handoff(
    root: Path,
    *,
    goal: str,
    decisions: str | None = None,
    next_steps: str | None = None,
    related_ids: list[str] | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    # FM-4: handoff does NOT run lazy expiry (DESIGN)

    if not goal or not str(goal).strip():
        raise UsageError("--goal is required")

    parts = [goal]
    if decisions:
        parts.append(decisions)
    if next_steps:
        parts.append(next_steps)
    warns = gate_write_payload(*parts, force=force, label="handoff")
    for w in warns:
        if not quiet:
            print(w, file=sys.stderr)

    ts = now_iso()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    hid = f"handoff_{stamp.replace('-', '')}"

    dec_list: list[str] = []
    if decisions:
        dec_list = [ln.strip().lstrip("-* ").strip() for ln in decisions.splitlines() if ln.strip()]
    steps_list: list[str] = []
    if next_steps:
        steps_list = [
            ln.strip().lstrip("-* ").strip() for ln in next_steps.splitlines() if ln.strip()
        ]
    rel_ids = list(related_ids or [])

    meta = {
        "id": hid,
        "type": "handoff",
        "goal": goal,
        "decisions": dec_list,
        "next_steps": steps_list,
        "related_ids": rel_ids,
        "project_id": project_id,
        "session_id": session_id,
        "created_at": ts,
        "updated_at": ts,
        "source": {"kind": "handoff"},
        "schema_version": SCHEMA_VERSION,
    }
    body_lines = [
        f"# Handoff {stamp}",
        "",
        f"## Goal\n\n{goal}\n",
    ]
    if steps_list:
        body_lines.append("## Next steps\n")
        for s in steps_list:
            body_lines.append(f"- {s}")
        body_lines.append("")
    if dec_list:
        body_lines.append("## Decisions\n")
        for d in dec_list:
            body_lines.append(f"- {d}")
        body_lines.append("")
    body = "\n".join(body_lines) + "\n"

    dest = root / "working" / f"handoff-{stamp}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(dest, dump(meta, body))

    # Always overwrite provided fields onto working (KD-27)
    update_working_fields(
        root,
        goal=goal,
        decisions=decisions if decisions is not None else None,
        next_steps=next_steps if next_steps is not None else None,
        related_ids=rel_ids if related_ids is not None else None,
        project_id=project_id if project_id is not None else ...,
        session_id=session_id if session_id is not None else ...,
    )

    try:
        rel = dest.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = f"working/handoff-{stamp}.md"

    append_recent(root, id=hid, kind="handoff", path=rel, op="handoff")
    return {"id": hid, "path": rel, "goal": goal}
