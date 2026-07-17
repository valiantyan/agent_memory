"""agent-memory reindex"""

from __future__ import annotations

from pathlib import Path

from agent_memory.config import require_schema_for_write
from agent_memory.index import reindex as do_reindex


def run_reindex(root: Path) -> tuple[int, int]:
    require_schema_for_write(root)
    return do_reindex(root)
