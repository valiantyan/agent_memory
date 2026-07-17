"""agent-memory recent — read-only listing of recent writes.

Retention prune of ``meta/recent.jsonl`` is done by ``gc`` (and is a write).
This command never mutates the memory root so sandboxed agents can audit
history without write access to the store.
"""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.config import RECENT_DEFAULT_N, read_schema_version
from agent_memory import SCHEMA_VERSION
from agent_memory.errors import SchemaError
from agent_memory.recent import load_recent


def run_recent(root: Path, *, n: int = RECENT_DEFAULT_N, as_json: bool = False) -> str:
    ver = read_schema_version(root)
    if ver is None:
        raise SchemaError("no schema_version; run init")
    if ver != SCHEMA_VERSION:
        raise SchemaError(f"schema mismatch {ver}")

    entries = load_recent(root, n=n)
    if as_json:
        return json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
    if not entries:
        return "(no recent entries)\n"
    lines = []
    for e in entries:
        lines.append(
            f"{e.get('ts')}  {e.get('op')}  id={e.get('id')}  "
            f"kind={e.get('kind')}  path={e.get('path')}"
        )
    return "\n".join(lines) + "\n"
