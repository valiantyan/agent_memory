"""agent-memory forget"""

from __future__ import annotations

from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.errors import NotFoundError
from agent_memory.frontmatter import dump
from agent_memory.index import (
    load_episodic_index,
    load_semantic_index,
    save_episodic_index,
    save_semantic_index,
)
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.resolve import resolve_id
from agent_memory.util import now_iso


def run_forget(root: Path, mem_id: str, *, hard: bool = False) -> None:
    require_schema_for_write(root)
    from agent_memory.expiry import run_lazy_expiry

    # forget is not on FM-4 list for expiry, but harmless; skip to match DESIGN
    got = resolve_id(root, mem_id)
    if not got:
        raise NotFoundError(f"memory not found: {mem_id}")

    mid = got.id
    path = got.path
    rel = got.rel_path

    # body first
    if hard:
        try:
            path.unlink()
        except OSError as e:
            raise NotFoundError(f"cannot delete {rel}: {e}") from e
    else:
        meta = dict(got.meta)
        meta["status"] = "deleted"
        meta["updated_at"] = now_iso()
        write_text_atomic(path, dump(meta, got.body))

    # INDEX remove
    sem = load_semantic_index(root)
    new_sem = [r for r in sem if r.id != mid]
    if len(new_sem) != len(sem):
        save_semantic_index(root, new_sem)
    epi = load_episodic_index(root)
    new_epi = [r for r in epi if r.id != mid]
    if len(new_epi) != len(epi):
        save_episodic_index(root, new_epi)

    append_recent(
        root,
        id=mid,
        kind=str(got.meta.get("type") or "semantic"),
        path=rel,
        op="forget_hard" if hard else "forget",
    )
