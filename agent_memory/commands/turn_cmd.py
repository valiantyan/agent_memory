"""agent-memory turn — write pending turn essence into memory root (v2)."""

from __future__ import annotations

from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.errors import UsageError
from agent_memory.intent_draft import clear_intent_draft
from agent_memory.pending_turn import write_pending_turn
from agent_memory.project_detect import detect_project
from agent_memory.security import gate_write_payload
from agent_memory.write_gate import effective_project


def run_turn(
    root: Path,
    *,
    goal: str,
    next_steps: str,
    decisions: str | None = None,
    project_id: str | None = None,
    cwd: str | Path | None = None,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    g = (goal or "").strip()
    n = (next_steps or "").strip()
    if not g or not n:
        raise UsageError("turn requires non-empty --goal and --next-steps")

    warns = gate_write_payload(g, n, decisions or "", force=force, label="turn")
    # security warnings printed by caller if needed — return in result
    pid = project_id
    if pid is None and cwd is not None:
        det_id, conf = detect_project(Path(cwd))
        if conf == "high" and det_id:
            pid = det_id
    if pid is None:
        epid, econf = effective_project(root)
        if econf == "high" and epid:
            pid = epid

    path = write_pending_turn(
        root,
        goal=g,
        next_steps=n,
        decisions=decisions or "",
        project_id=pid,
        force=force,
    )
    # Formal essence supersedes open intent draft
    clear_intent_draft(root, pid)
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = str(path)
    return {
        "path": rel,
        "project_id": pid,
        "goal": g,
        "warnings": warns,
    }
