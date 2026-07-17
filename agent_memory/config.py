"""Root resolution, schema, quotas."""

from __future__ import annotations

import os
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.errors import SchemaError

DEFAULT_ROOT = Path.home() / ".agent-memory"
SCHEMA_FILENAME = "schema_version"

# REQ §9 / DESIGN §11
TOP_K_DEFAULT = 5
T0_BUDGET = 1600
SEMANTIC_DETAILS_BUDGET = 4800
ONE_LINER_MAX = 80
EPISODE_BODY_MAX = 8000
INDEX_SEMANTIC_MAX_ACTIVE = 300
OBSERVATION_DAYS = 5
PROMOTE_IMPORTANCE_MIN = 7
EPISODE_TTL_DAYS = 90
RECENT_DEFAULT_N = 20
RECENT_RETENTION_DAYS = 30
CHECKPOINT_EVERY_N = 8


def resolve_root(cli_root: str | None = None) -> Path:
    """Resolve memory root: --root > AGENT_MEMORY_ROOT > ~/.agent-memory."""
    if cli_root:
        return Path(cli_root).expanduser().resolve()
    env = os.environ.get("AGENT_MEMORY_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_ROOT.expanduser().resolve()


def schema_path(root: Path) -> Path:
    return root / SCHEMA_FILENAME


def read_schema_version(root: Path) -> str | None:
    path = schema_path(root)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip()


def require_schema_for_write(root: Path) -> None:
    """FC0-2: writes require exact schema match."""
    ver = read_schema_version(root)
    if ver is None:
        raise SchemaError(
            f"No {SCHEMA_FILENAME} under {root}; run `agent-memory init` first"
        )
    if ver != SCHEMA_VERSION:
        raise SchemaError(
            f"Incompatible schema_version {ver!r}; this CLI requires {SCHEMA_VERSION!r}"
        )


def write_schema_version(root: Path) -> None:
    from agent_memory.io_atomic import write_text_atomic

    write_text_atomic(schema_path(root), SCHEMA_VERSION + "\n")
