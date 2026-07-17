"""agent-memory get"""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import read_schema_version
from agent_memory.errors import NotFoundError, SchemaError
from agent_memory.resolve import resolve_id


def run_get(root: Path, mem_id: str, *, as_json: bool = False) -> str:
    ver = read_schema_version(root)
    if ver is None:
        raise SchemaError("no schema_version; run init")
    if ver != SCHEMA_VERSION:
        raise SchemaError(f"schema mismatch {ver}")

    got = resolve_id(root, mem_id)
    if not got:
        raise NotFoundError(f"memory not found: {mem_id}")
    if as_json:
        return json.dumps(
            {
                "id": got.id,
                "path": got.rel_path,
                "meta": got.meta,
                "body": got.body,
            },
            ensure_ascii=False,
            indent=2,
        )
    lines = [
        f"id: {got.id}",
        f"path: {got.rel_path}",
        f"status: {got.meta.get('status')}",
        f"type: {got.meta.get('type')}",
        f"scope: {got.meta.get('scope')}",
        "---",
        got.body.rstrip(),
        "",
    ]
    return "\n".join(lines)
