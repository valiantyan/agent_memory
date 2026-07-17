"""agent-memory promote"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory.config import INDEX_SEMANTIC_MAX_ACTIVE, require_schema_for_write
from agent_memory.errors import ConflictError, NotFoundError, UsageError
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import dump
from agent_memory.index import (
    SemanticRow,
    active_semantic_count,
    load_semantic_index,
    save_semantic_index,
)
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.resolve import resolve_id
from agent_memory.security import assert_source_for_active, gate_write_payload
from agent_memory.util import now_iso, rel_to_root
from agent_memory.write_gate import assert_project_semantic_write


def run_promote(
    root: Path,
    mem_id: str,
    *,
    user_confirmed: bool = False,
    related_episodes: list[str] | None = None,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    run_lazy_expiry(root)

    got = resolve_id(root, mem_id)
    if not got:
        raise NotFoundError(f"not found: {mem_id}")

    status = str(got.meta.get("status") or "").lower()
    if status not in ("candidate",):
        raise NotFoundError(
            f"promote expects status=candidate, got {status!r} for {mem_id}"
        )

    mem_type = str(got.meta.get("type") or "semantic")
    if mem_type == "procedural":
        rels = related_episodes or []
        if not user_confirmed and len(rels) < 2:
            raise UsageError(
                "procedural promote requires --user-confirmed or "
                "≥2 --related-episode ids"
            )
    elif mem_type != "semantic":
        raise UsageError(f"cannot promote type={mem_type!r}")

    source = got.meta.get("source") or {}
    source_kind = source.get("kind") if isinstance(source, dict) else None
    assert_source_for_active(str(source_kind or "extracted"))

    scope = str(got.meta.get("scope") or "global")
    assert_project_semantic_write(root, scope)

    one = str(got.meta.get("one_liner") or "")
    warns = gate_write_payload(
        got.body,
        one,
        force=force,
        source_kind=str(source_kind or "extracted"),
        for_active=True,
        one_liner=one,
        label="promote",
    )
    for w in warns:
        if not quiet:
            print(w, file=sys.stderr)

    if active_semantic_count(root) >= INDEX_SEMANTIC_MAX_ACTIVE:
        raise ConflictError(f"INDEX.semantic at cap {INDEX_SEMANTIC_MAX_ACTIVE}")

    # destination
    mid = got.id
    if mem_type == "procedural":
        dest = root / "procedural" / "active" / f"{mid}.md"
    elif scope.startswith("project:"):
        pid = scope.split(":", 1)[1]
        dest = root / "scopes" / "projects" / pid / "semantic" / f"{mid}.md"
    else:
        dest = root / "scopes" / "global" / "semantic" / f"{mid}.md"

    dest.parent.mkdir(parents=True, exist_ok=True)
    meta = dict(got.meta)
    meta["status"] = "active"
    meta["updated_at"] = now_iso()
    if related_episodes:
        meta["related_episodes"] = list(related_episodes)

    # body first
    write_text_atomic(
        dest, dump(meta, got.body if got.body.endswith("\n") else got.body + "\n")
    )
    # remove candidate
    try:
        if got.path.resolve() != dest.resolve():
            got.path.unlink()
    except OSError:
        pass

    rel = rel_to_root(root, dest)
    rows = load_semantic_index(root)
    rows = [r for r in rows if r.id != mid]
    rows.append(
        SemanticRow(
            id=mid,
            type=mem_type,
            content_kind=str(meta.get("content_kind") or ""),
            scope=scope,
            slot=str(meta.get("slot") or ""),
            one_liner=one[:80],
            path=rel,
            updated_at=str(meta["updated_at"]),
        )
    )
    save_semantic_index(root, rows)
    append_recent(root, id=mid, kind=mem_type, path=rel, op="promote")
    return {"id": mid, "path": rel, "type": mem_type}
