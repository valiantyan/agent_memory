"""Pending turn essence under memory root (v2) — not in business repos."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_memory.io_atomic import write_text_atomic
from agent_memory.util import now_iso

_SAFE_ID = re.compile(r"[^a-zA-Z0-9._-]+")


def pending_turn_dir(root: Path) -> Path:
    return root / "meta" / "pending-turn"


def pending_done_dir(root: Path) -> Path:
    return pending_turn_dir(root) / "done"


def sanitize_project_key(project_id: str | None) -> str:
    raw = (project_id or "").strip() or "_global"
    key = _SAFE_ID.sub("_", raw).strip("._") or "_global"
    return key[:80]


def pending_turn_path(root: Path, project_id: str | None) -> Path:
    return pending_turn_dir(root) / f"{sanitize_project_key(project_id)}.json"


def write_pending_turn(
    root: Path,
    *,
    goal: str,
    next_steps: str,
    decisions: str = "",
    project_id: str | None = None,
    force: bool = False,
) -> Path:
    """Write pending turn JSON. goal and next_steps must be non-empty after strip."""
    g = goal.strip()
    n = next_steps.strip()
    if not g or not n:
        raise ValueError("goal and next_steps must be non-empty")
    pending_turn_dir(root).mkdir(parents=True, exist_ok=True)
    path = pending_turn_path(root, project_id)
    payload: dict[str, Any] = {
        "goal": g,
        "next_steps": n,
        "decisions": (decisions or "").strip(),
        "project_id": (project_id or "").strip() or None,
        "force": bool(force),
        "updated_at": now_iso(),
        "schema_version": "1.0.0",
    }
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def read_pending_turn(root: Path, project_id: str | None) -> dict[str, Any] | None:
    path = pending_turn_path(root, project_id)
    if not path.is_file():
        # also try _global if project-specific missing
        if project_id:
            alt = pending_turn_path(root, None)
            if alt.is_file():
                path = alt
            else:
                return None
        else:
            return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


