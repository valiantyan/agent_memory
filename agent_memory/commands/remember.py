"""agent-memory remember"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import INDEX_SEMANTIC_MAX_ACTIVE, require_schema_for_write
from agent_memory.errors import ConflictError
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.index import (
    SemanticRow,
    active_semantic_count,
    load_semantic_index,
    save_semantic_index,
)
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.security import gate_write_payload
from agent_memory.util import derive_one_liner, mint_semantic_id, now_iso, rel_to_root
from agent_memory.write_gate import assert_project_semantic_write


def _normalize_scope(scope: str | None, project: str | None) -> str:
    if project:
        return f"project:{project.strip()}"
    if not scope or scope == "global":
        return "global"
    if scope.startswith("project:"):
        return scope
    return scope


def run_remember(
    root: Path,
    *,
    slot: str,
    content: str,
    title: str | None = None,
    one_liner: str | None = None,
    scope: str | None = None,
    project: str | None = None,
    content_kind: str = "preference",
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    run_lazy_expiry(root)

    if not slot or not slot.strip():
        from agent_memory.errors import UsageError

        raise UsageError("--slot is required")
    if content is None or content == "":
        from agent_memory.errors import UsageError

        raise UsageError("--content is required")

    scope_n = _normalize_scope(scope, project)
    assert_project_semantic_write(root, scope_n)

    one = derive_one_liner(content, explicit=one_liner, title=title)
    warns = gate_write_payload(
        content,
        title or "",
        one,
        force=force,
        source_kind="user_explicit",
        for_active=True,
        one_liner=one,
        label="remember",
    )
    for w in warns:
        if not quiet:
            print(w, file=sys.stderr)

    if active_semantic_count(root) >= INDEX_SEMANTIC_MAX_ACTIVE:
        # if superseding same slot, net zero — allow if we will remove one
        rows = load_semantic_index(root)
        same = [
            r
            for r in rows
            if r.scope == scope_n and r.slot == slot and r.type == "semantic"
        ]
        if not same and active_semantic_count(root) >= INDEX_SEMANTIC_MAX_ACTIVE:
            raise ConflictError(
                f"INDEX.semantic active rows at cap {INDEX_SEMANTIC_MAX_ACTIVE}"
            )

    mid = mint_semantic_id(slot, content, scope_n)
    # id conflict check
    if (root / "scopes").exists():
        from agent_memory.resolve import resolve_id

        if resolve_id(root, mid) is not None:
            raise ConflictError(f"id already exists: {mid}")

    ts = now_iso()
    meta = {
        "id": mid,
        "type": "semantic",
        "content_kind": content_kind,
        "status": "active",
        "scope": scope_n,
        "title": title or "",
        "one_liner": one,
        "tags": [],
        "slot": slot,
        "importance": 10,
        "source": {"kind": "user_explicit", "agent": None, "episode_id": None},
        "created_at": ts,
        "updated_at": ts,
        "supersedes": None,
        "schema_version": SCHEMA_VERSION,
    }

    if scope_n.startswith("project:"):
        pid = scope_n.split(":", 1)[1]
        dest = root / "scopes" / "projects" / pid / "semantic" / f"{mid}.md"
    else:
        dest = root / "scopes" / "global" / "semantic" / f"{mid}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)

    # supersede old same slot
    rows = load_semantic_index(root)
    superseded: list[str] = []
    for r in list(rows):
        if r.scope == scope_n and r.slot == slot and r.type == "semantic":
            _move_to_history(root, r)
            rows = [x for x in rows if x.id != r.id]
            superseded.append(r.id)
            meta["supersedes"] = r.id

    write_text_atomic(dest, dump(meta, content if content.endswith("\n") else content + "\n"))
    rel = rel_to_root(root, dest)
    rows.append(
        SemanticRow(
            id=mid,
            type="semantic",
            content_kind=content_kind,
            scope=scope_n,
            slot=slot,
            one_liner=one,
            path=rel,
            updated_at=ts,
        )
    )
    save_semantic_index(root, rows)
    append_recent(root, id=mid, kind="semantic", path=rel, op="remember")
    return {"id": mid, "path": rel, "superseded": superseded}


def _move_to_history(root: Path, row: SemanticRow) -> None:
    from agent_memory.index import resolve_under_root

    src = resolve_under_root(root, row.path)
    if not src or not src.is_file():
        return
    try:
        meta, body = parse_fm(src.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    meta["status"] = "superseded"
    meta["updated_at"] = now_iso()
    hist = root / "history" / "semantic" / f"{row.id}.md"
    hist.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(hist, dump(meta, body))
    try:
        src.unlink()
    except OSError:
        pass
