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


def claim_pending_turn(root: Path, project_id: str | None) -> Path | None:
    """Atomically move pending file to processing path. Returns processing path or None."""
    path = pending_turn_path(root, project_id)
    if not path.is_file() and project_id:
        path = pending_turn_path(root, None)
    if not path.is_file():
        return None
    pending_turn_dir(root).mkdir(parents=True, exist_ok=True)
    stamp = now_iso().replace(":", "").replace("+", "p")
    proc = path.with_name(f"{path.stem}.processing-{stamp}{path.suffix}")
    try:
        path.rename(proc)
    except OSError:
        return None
    return proc


def finalize_pending_turn(processing: Path, *, ok: bool, restore_to: Path | None) -> None:
    """On ok → done/; on fail → restore to pending path if free."""
    if ok:
        done = processing.parent / "done"
        done.mkdir(parents=True, exist_ok=True)
        dest = done / processing.name.replace(".processing-", ".done-", 1)
        try:
            processing.rename(dest)
        except OSError:
            try:
                processing.unlink()
            except OSError:
                pass
        # keep last 10 done
        files = sorted(done.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[10:]:
            try:
                old.unlink()
            except OSError:
                pass
        return
    if restore_to is not None and not restore_to.exists():
        try:
            processing.rename(restore_to)
            return
        except OSError:
            pass
