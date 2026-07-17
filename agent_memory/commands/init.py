"""agent-memory init [--force]"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from agent_memory.config import read_schema_version, schema_path, write_schema_version
from agent_memory.errors import ConflictError
from agent_memory.io_atomic import write_text_atomic
from agent_memory.templates import (
    EMPTY_INDEX_EPISODIC,
    EMPTY_INDEX_SEMANTIC,
    PROTOCOL_MD,
    QUOTAS_MD,
    README_ROOT,
    T0_TEMPLATE,
    WORKING_TEMPLATE,
)

# Globs that indicate real memory bodies (DESIGN init safety)
_BODY_GLOBS = (
    "scopes/**/semantic/*.md",
    "episodes/**/*.md",
    "staging/candidates/*.md",
    "procedural/**/*.md",
    "history/**/*.md",
    "working/handoff-*.md",
)


def _has_memory_bodies(root: Path) -> bool:
    if not root.is_dir():
        return False
    for pattern in _BODY_GLOBS:
        if any(root.glob(pattern)):
            return True
    return False


def _dirs(root: Path) -> list[Path]:
    return [
        root / "profile",
        root / "working",
        root / "scopes" / "global" / "semantic",
        root / "scopes" / "projects",
        root / "staging" / "candidates",
        root / "history" / "semantic",
        root / "history" / "procedural",
        root / "episodes",
        root / "procedural" / "candidates",
        root / "procedural" / "active",
        root / "archive" / "episodes",
        root / "meta",
        root / "meta" / "pending-turn",
        root / "meta" / "pending-turn" / "done",
    ]


def _restrict_root_permissions(root: Path) -> None:
    """DESIGN security: recommend 0700 on init (best-effort; may no-op on some FS)."""
    try:
        os.chmod(root, stat.S_IRWXU)  # 0o700
    except OSError:
        pass


def run_init(root: Path, force: bool = False) -> None:
    """Create empty legal store. See DESIGN §6.1 safety policy.

    Write order: directories and templates first, **schema_version last** so a crash
    mid-init does not look like a complete store (second init can finish).
    """
    root = root.resolve()
    existing = read_schema_version(root)
    has_bodies = _has_memory_bodies(root)

    if existing is not None and not force:
        raise ConflictError(
            f"already initialized (schema_version={existing!r} at {schema_path(root)}); "
            "refusing without a non-destructive path. "
            "Use --force only when no memory bodies exist (never wipes data)."
        )

    if force and has_bodies:
        raise ConflictError(
            "refusing --force: memory body files exist under root "
            "(scopes/episodes/staging/procedural/history/handoffs). "
            "v1 does not support destructive wipe."
        )

    if not force and existing is None and has_bodies:
        raise ConflictError(
            "memory-like .md files exist but no schema_version; "
            "refusing init to avoid clobber. Move files or create schema manually."
        )

    root.mkdir(parents=True, exist_ok=True)
    _restrict_root_permissions(root)
    for d in _dirs(root):
        d.mkdir(parents=True, exist_ok=True)

    # Templates / indexes first
    write_text_atomic(root / "profile" / "me.T0.md", T0_TEMPLATE)
    write_text_atomic(root / "working" / "current.md", WORKING_TEMPLATE)
    write_text_atomic(root / "INDEX.semantic.md", EMPTY_INDEX_SEMANTIC)
    write_text_atomic(root / "INDEX.episodic.md", EMPTY_INDEX_EPISODIC)
    write_text_atomic(root / "PROTOCOL.md", PROTOCOL_MD)
    write_text_atomic(root / "README.md", README_ROOT)
    write_text_atomic(root / "meta" / "quotas.md", QUOTAS_MD)

    # Logs: create if missing; on --force do not wipe existing log lines
    recent = root / "meta" / "recent.jsonl"
    if not recent.exists():
        write_text_atomic(recent, "")
    rejected = root / "meta" / "rejected.jsonl"
    if not rejected.exists():
        write_text_atomic(rejected, "")

    # schema_version LAST — marks store as complete
    write_schema_version(root)
