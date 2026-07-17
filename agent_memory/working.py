"""Load/save working/current.md with section sync."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from agent_memory import SCHEMA_VERSION
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.io_atomic import write_text_atomic
from agent_memory.util import now_iso

WORKING_REL = Path("working") / "current.md"

_SECTION_ORDER = (
    "Goal",
    "Decisions",
    "Next steps",
    "Related memory ids",
    "Open questions",
)


def working_path(root: Path) -> Path:
    return root / WORKING_REL


def load_working(root: Path) -> tuple[dict[str, Any], str]:
    path = working_path(root)
    if not path.is_file():
        meta = {
            "id": "working_current",
            "type": "working",
            "status": "active",
            "project_id": None,
            "session_id": None,
            "goal": "",
            "updated_at": None,
            "schema_version": SCHEMA_VERSION,
        }
        return meta, _body_from_sections({})
    text = path.read_text(encoding="utf-8")
    meta, body = parse_fm(text)
    if not meta.get("id"):
        meta["id"] = "working_current"
    meta.setdefault("type", "working")
    return meta, body


def _parse_sections(body: str) -> dict[str, str]:
    sections: dict[str, str] = {k: "" for k in _SECTION_ORDER}
    current: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                sections[current] = "\n".join(buf).strip("\n")
            title = m.group(1).strip()
            # normalize common titles
            for key in _SECTION_ORDER:
                if title.lower() == key.lower():
                    current = key
                    break
            else:
                current = title
                if current not in sections:
                    sections[current] = ""
            buf = []
            continue
        if current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip("\n")
    return sections


def _body_from_sections(sections: dict[str, str]) -> str:
    parts = ["# Working · CURRENT", ""]
    for key in _SECTION_ORDER:
        parts.append(f"## {key}")
        parts.append("")
        val = sections.get(key, "") or ""
        if val:
            parts.append(val.rstrip())
            parts.append("")
        else:
            parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _list_to_md(items: list[str] | str | None) -> str:
    if items is None:
        return ""
    if isinstance(items, str):
        return items.strip()
    lines = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        if s.startswith("-") or s.startswith("*"):
            lines.append(s)
        else:
            lines.append(f"- {s}")
    return "\n".join(lines)


def save_working(root: Path, meta: dict[str, Any], body: str) -> None:
    path = working_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(meta)
    meta["id"] = "working_current"
    meta["type"] = "working"
    meta["status"] = "active"
    meta["schema_version"] = SCHEMA_VERSION
    meta["updated_at"] = now_iso()
    write_text_atomic(path, dump(meta, body if body.endswith("\n") else body + "\n"))


def update_working_fields(
    root: Path,
    *,
    goal: str | None = None,
    decisions: str | list[str] | None = None,
    next_steps: str | list[str] | None = None,
    related_ids: list[str] | None = None,
    project_id: str | None = ...,  # type: ignore[assignment]
    session_id: str | None = ...,  # type: ignore[assignment]
    open_questions: str | None = None,
    touch_only: bool = False,
) -> dict[str, Any]:
    """
    Merge provided fields into working.
    Use ellipsis (...) to mean "leave unchanged" for project_id/session_id.
    touch_only: only bump updated_at (and optional project/session if provided).
    """
    meta, body = load_working(root)
    sections = _parse_sections(body)

    if not touch_only:
        if goal is not None:
            meta["goal"] = goal
            sections["Goal"] = goal
        if decisions is not None:
            sections["Decisions"] = _list_to_md(decisions)
        if next_steps is not None:
            sections["Next steps"] = _list_to_md(next_steps)
        if related_ids is not None:
            sections["Related memory ids"] = _list_to_md(related_ids)
        if open_questions is not None:
            sections["Open questions"] = open_questions

    if project_id is not ...:
        meta["project_id"] = project_id
    if session_id is not ...:
        meta["session_id"] = session_id

    new_body = _body_from_sections(sections)
    save_working(root, meta, new_body)
    return meta
