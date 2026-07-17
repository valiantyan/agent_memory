"""agent-memory session-end"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import require_schema_for_write
from agent_memory.errors import UsageError
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import dump
from agent_memory.index import EpisodicRow, load_episodic_index, save_episodic_index
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.security import gate_write_payload
from agent_memory.util import derive_one_liner, now_iso, slug, utc_stamp
from agent_memory.working import update_working_fields


def run_session_end(
    root: Path,
    *,
    title: str,
    body: str,
    one_liner: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    run_lazy_expiry(root)

    if not title or not str(title).strip():
        raise UsageError("--title is required")
    if body is None:
        raise UsageError("--body or --body-file is required")

    # SEC + length before any write
    one = derive_one_liner(body, explicit=one_liner, title=title)
    warns = gate_write_payload(
        title,
        body,
        one,
        force=force,
        episode_body=body,
        one_liner=one,
        label="session-end",
    )
    for w in warns:
        if not quiet:
            print(w, file=sys.stderr)

    ts = now_iso()
    stamp = utc_stamp()
    eid = f"ep_{stamp}_{slug(title, 20)}"

    scope = f"project:{project_id}" if project_id else "global"
    meta = {
        "id": eid,
        "type": "episodic",
        "status": "active",
        "scope": scope,
        "project_id": project_id or "",
        "title": title,
        "one_liner": one,
        "session_id": session_id,
        "importance": 5,
        "source": {"kind": "handoff"},
        "created_at": ts,
        "updated_at": ts,
        "schema_version": SCHEMA_VERSION,
    }

    # path episodes/YYYY/MM/
    yyyy, mm = stamp[:4], stamp[4:6]
    dest = root / "episodes" / yyyy / mm / f"{eid}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    body_out = body if body.endswith("\n") else body + "\n"
    write_text_atomic(dest, dump(meta, body_out))

    try:
        rel = dest.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = f"episodes/{yyyy}/{mm}/{eid}.md"

    rows = load_episodic_index(root)
    rows = [r for r in rows if r.id != eid]
    rows.append(
        EpisodicRow(
            id=eid,
            project_id=str(project_id or ""),
            one_liner=one,
            path=rel,
            created_at=ts,
        )
    )
    save_episodic_index(root, rows)

    # touch working updated_at only (+ optional project/session)
    update_working_fields(
        root,
        touch_only=True,
        project_id=project_id if project_id is not None else ...,
        session_id=session_id if session_id is not None else ...,
    )

    append_recent(root, id=eid, kind="episodic", path=rel, op="session-end")
    return {"episode_id": eid, "path": rel}
