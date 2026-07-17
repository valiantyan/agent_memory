"""Multi work-items + focus (v2.0.2).

Second task must not erase the first: each goal maps to a stable item file under
``working/items/``. ``working/current.md`` mirrors the *focused* item only.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from agent_memory import SCHEMA_VERSION
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.io_atomic import write_text_atomic
from agent_memory.util import now_iso

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")
_WS = re.compile(r"\s+")


def items_dir(root: Path) -> Path:
    return root / "working" / "items"


def focus_path(root: Path) -> Path:
    return root / "working" / "focus.json"


def normalize_goal(goal: str) -> str:
    return _WS.sub(" ", (goal or "").strip()).lower()


def make_item_id(goal: str, project_id: str | None = None, *, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        raw = _SAFE.sub("_", explicit.strip()).strip("._")[:64]
        return raw if raw.startswith("wi_") else f"wi_{raw}"
    g = normalize_goal(goal)
    if not g:
        g = "untitled"
    slug = _SAFE.sub("-", g).strip("-")[:36] or "item"
    h = hashlib.sha1(f"{project_id or ''}:{g}".encode("utf-8")).hexdigest()[:8]
    return f"wi_{slug}_{h}"


def item_path(root: Path, item_id: str) -> Path:
    safe = _SAFE.sub("_", item_id).strip("._") or "wi_unknown"
    return items_dir(root) / f"{safe}.md"


def read_focus(root: Path) -> dict[str, Any] | None:
    path = focus_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_focus(root: Path, *, item_id: str, project_id: str | None = None) -> None:
    payload = {
        "item_id": item_id,
        "project_id": (project_id or "").strip() or None,
        "updated_at": now_iso(),
        "schema_version": SCHEMA_VERSION,
    }
    focus_path(root).parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(focus_path(root), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def load_item(root: Path, item_id: str) -> tuple[dict[str, Any], str] | None:
    path = item_path(root, item_id)
    if not path.is_file():
        return None
    try:
        meta, body = parse_fm(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return meta, body


def list_items(root: Path, *, project_id: str | None = None) -> list[dict[str, Any]]:
    d = items_dir(root)
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(d.glob("wi_*.md")):
        try:
            meta, _body = parse_fm(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if meta.get("status") == "archived":
            continue
        if project_id and meta.get("project_id") and meta.get("project_id") != project_id:
            continue
        out.append(meta)
    # newest first
    out.sort(key=lambda m: m.get("updated_at") or "", reverse=True)
    return out


def upsert_item(
    root: Path,
    *,
    goal: str,
    next_steps: str = "",
    decisions: str = "",
    project_id: str | None = None,
    session_id: str | None = None,
    item_id: str | None = None,
    status: str = "active",
    set_focus: bool = True,
) -> dict[str, Any]:
    """Create or update a work item; optionally set focus. Does not delete siblings."""
    g = (goal or "").strip()
    if not g:
        raise ValueError("goal required")
    iid = make_item_id(g, project_id, explicit=item_id)
    path = item_path(root, iid)
    prev_meta: dict[str, Any] = {}
    if path.is_file():
        try:
            prev_meta, _ = parse_fm(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prev_meta = {}

    ts = now_iso()
    # Preserve prior session_id if new write omits it; allow explicit set.
    sid = (session_id or "").strip() or None
    if sid is None:
        sid = prev_meta.get("session_id")
    meta: dict[str, Any] = {
        "id": iid,
        "type": "work_item",
        "status": status or "active",
        "goal": g,
        "project_id": (project_id or prev_meta.get("project_id") or None),
        "session_id": sid,
        "created_at": prev_meta.get("created_at") or ts,
        "updated_at": ts,
        "schema_version": SCHEMA_VERSION,
    }
    body = (
        f"# Work item · {iid}\n\n"
        f"## Goal\n\n{g}\n\n"
        f"## Decisions\n\n{(decisions or '').strip()}\n\n"
        f"## Next steps\n\n{(next_steps or '').strip()}\n"
    )
    items_dir(root).mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, dump(meta, body if body.endswith("\n") else body + "\n"))
    if set_focus:
        write_focus(root, item_id=iid, project_id=meta.get("project_id"))
    return meta


def archive_item(root: Path, item_id: str) -> bool:
    loaded = load_item(root, item_id)
    if not loaded:
        return False
    meta, body = loaded
    meta["status"] = "archived"
    meta["updated_at"] = now_iso()
    write_text_atomic(item_path(root, item_id), dump(meta, body))
    foc = read_focus(root)
    if foc and foc.get("item_id") == item_id:
        # clear focus if archived current
        try:
            focus_path(root).unlink()
        except OSError:
            pass
    return True
