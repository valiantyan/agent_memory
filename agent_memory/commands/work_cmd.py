"""agent-memory work — list / focus multi work-items (v2.0.2)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.errors import UsageError
from agent_memory.work_items import (
    list_items,
    load_item,
    read_focus,
    upsert_item,
    write_focus,
)
from agent_memory.working import update_working_fields


def run_work_list(
    root: Path,
    *,
    project_id: str | None = None,
    as_json: bool = False,
) -> str:
    foc = read_focus(root)
    focus_id = (foc or {}).get("item_id")
    items = list_items(root, project_id=project_id)
    if as_json:
        return json.dumps(
            {"focus": foc, "items": items},
            ensure_ascii=False,
            indent=2,
        )
    lines: list[str] = []
    if foc:
        lines.append(
            f"focus: {foc.get('item_id')} project={foc.get('project_id')}"
        )
    else:
        lines.append("focus: (none)")
    if not items:
        lines.append("(no work items)")
    for m in items:
        mark = "*" if m.get("id") == focus_id else " "
        lines.append(
            f"{mark} {m.get('id')}  [{m.get('status')}]  {m.get('goal')}"
        )
    return "\n".join(lines) + "\n"


def run_work_focus(
    root: Path,
    item_id: str,
    *,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    iid = (item_id or "").strip()
    if not iid:
        raise UsageError("--id required")
    loaded = load_item(root, iid)
    if not loaded:
        raise UsageError(f"work item not found: {iid}")
    meta, body = loaded
    write_focus(root, item_id=iid, project_id=meta.get("project_id"))
    # sync working/current.md from this item (compat)
    goal = meta.get("goal") or ""
    # parse sections roughly from body
    decisions = ""
    next_steps = ""
    if "## Decisions" in body:
        part = body.split("## Decisions", 1)[1]
        if "## " in part:
            decisions = part.split("## ", 1)[0].strip()
        else:
            decisions = part.strip()
    if "## Next steps" in body:
        part = body.split("## Next steps", 1)[1]
        if "## " in part:
            next_steps = part.split("## ", 1)[0].strip()
        else:
            next_steps = part.strip()
    update_working_fields(
        root,
        goal=goal,
        decisions=decisions or None,
        next_steps=next_steps or None,
        project_id=meta.get("project_id"),
        session_id=meta.get("session_id"),
    )
    return {"item_id": iid, "goal": goal, "project_id": meta.get("project_id")}


def run_work_upsert(
    root: Path,
    *,
    goal: str,
    next_steps: str = "",
    decisions: str = "",
    project_id: str | None = None,
    item_id: str | None = None,
    set_focus: bool = True,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    meta = upsert_item(
        root,
        goal=goal,
        next_steps=next_steps,
        decisions=decisions,
        project_id=project_id,
        item_id=item_id,
        set_focus=set_focus,
    )
    if set_focus:
        update_working_fields(
            root,
            goal=goal,
            decisions=decisions or None,
            next_steps=next_steps or None,
            project_id=project_id,
        )
    return {
        "item_id": meta["id"],
        "goal": meta.get("goal"),
        "project_id": meta.get("project_id"),
        "focus": set_focus,
    }
