"""Id → path resolution (DESIGN §6.6)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_memory.frontmatter import parse as parse_fm
from agent_memory.index import (
    load_episodic_index,
    load_semantic_index,
    resolve_under_root,
)


@dataclass
class Resolved:
    id: str
    path: Path
    meta: dict[str, Any]
    body: str
    rel_path: str


def _try_file(root: Path, path: Path, want_id: str) -> Resolved | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_fm(text)
    except (OSError, ValueError, UnicodeError):
        return None
    mid = str(meta.get("id") or "")
    if mid and mid != want_id:
        return None
    # allow missing id in file only for working_current special path
    if not mid and want_id != "working_current":
        return None
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None
    return Resolved(id=want_id, path=path, meta=meta, body=body, rel_path=rel)


def _scan_dir(root: Path, directory: Path, want_id: str, pattern: str = "*.md") -> Resolved | None:
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob(pattern)):
        got = _try_file(root, path, want_id)
        if got:
            return got
    return None


def _scan_rglob(
    root: Path, directory: Path, want_id: str, *, exclude_parts: frozenset[str] | None = None
) -> Resolved | None:
    if not directory.is_dir():
        return None
    exclude_parts = exclude_parts or frozenset()
    for path in sorted(directory.rglob("*.md")):
        if exclude_parts and exclude_parts.intersection(path.parts):
            continue
        got = _try_file(root, path, want_id)
        if got:
            return got
    return None


def resolve_id(root: Path, mem_id: str) -> Resolved | None:
    """First match wins per DESIGN §6.6 order."""
    root = root.resolve()
    mid = mem_id.strip()
    if not mid:
        return None

    # 9 special first for speed / clarity when id is working_current
    if mid == "working_current":
        wp = root / "working" / "current.md"
        got = _try_file(root, wp, mid)
        if got:
            if not got.meta.get("id"):
                got.meta = {**got.meta, "id": "working_current"}
            return got

    # 1 INDEX.semantic
    for row in load_semantic_index(root):
        if row.id == mid:
            p = resolve_under_root(root, row.path)
            if p:
                got = _try_file(root, p, mid)
                if got:
                    return got

    # 2 INDEX.episodic
    for row in load_episodic_index(root):
        if row.id == mid:
            p = resolve_under_root(root, row.path)
            if p:
                got = _try_file(root, p, mid)
                if got:
                    return got

    # 3 staging/candidates
    got = _scan_dir(root, root / "staging" / "candidates", mid)
    if got:
        return got

    # 4 procedural/candidates
    got = _scan_dir(root, root / "procedural" / "candidates", mid)
    if got:
        return got

    # 5 history
    got = _scan_dir(root, root / "history" / "semantic", mid)
    if got:
        return got
    got = _scan_dir(root, root / "history" / "procedural", mid)
    if got:
        return got

    # 6 orphan active under scopes + procedural/active
    scopes = root / "scopes"
    if scopes.is_dir():
        for path in sorted(scopes.glob("**/semantic/*.md")):
            got = _try_file(root, path, mid)
            if got:
                return got
    got = _scan_dir(root, root / "procedural" / "active", mid)
    if got:
        return got

    # 7 episodes (non-archive then archive)
    got = _scan_rglob(
        root, root / "episodes", mid, exclude_parts=frozenset({"archive"})
    )
    if got:
        return got
    got = _scan_rglob(root, root / "archive" / "episodes", mid)
    if got:
        return got

    # 8 handoffs
    working = root / "working"
    if working.is_dir():
        for path in sorted(working.glob("handoff-*.md")):
            got = _try_file(root, path, mid)
            if got:
                return got

    return None
