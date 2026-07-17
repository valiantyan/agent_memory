"""agent-memory reject"""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.errors import NotFoundError, UsageError
from agent_memory.frontmatter import dump
from agent_memory.io_atomic import append_line, write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.resolve import resolve_id
from agent_memory.util import now_iso


def run_reject(root: Path, mem_id: str) -> dict:
    require_schema_for_write(root)
    got = resolve_id(root, mem_id)
    if not got:
        raise NotFoundError(f"not found: {mem_id}")

    status = str(got.meta.get("status") or "").lower()
    # allow reject on candidate paths primarily
    rel = got.rel_path
    if "candidates" not in rel.replace("\\", "/").split("/"):
        if status != "candidate":
            raise UsageError(
                f"reject expects a candidate (staging/procedural candidates), got path={rel}"
            )

    meta = dict(got.meta)
    meta["status"] = "rejected"
    meta["updated_at"] = now_iso()
    write_text_atomic(
        got.path, dump(meta, got.body if got.body.endswith("\n") else got.body + "\n")
    )

    reg = root / "meta" / "rejected.jsonl"
    append_line(
        reg,
        json.dumps({"id": mem_id, "ts": now_iso()}, ensure_ascii=False),
    )
    append_recent(
        root,
        id=mem_id,
        kind=str(meta.get("type") or "semantic"),
        path=rel,
        op="reject",
    )
    return {"id": mem_id, "path": rel}
