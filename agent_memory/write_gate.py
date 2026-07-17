"""Project semantic write gate (DESIGN §7 / KD-22)."""

from __future__ import annotations

import os
from pathlib import Path

from agent_memory.errors import ConflictError
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.project_detect import detect_project, normalize_project_id


def read_working_project_id(root: Path) -> str | None:
    wp = root / "working" / "current.md"
    if not wp.is_file():
        return None
    try:
        meta, _ = parse_fm(wp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    pid = meta.get("project_id")
    if pid is None or pid == "" or pid == "null":
        return None
    return normalize_project_id(str(pid))


def effective_project(
    root: Path,
    *,
    cwd: str | Path | None = None,
    force_confidence: str | None = None,
) -> tuple[str | None, str]:
    """
    Effective current project for search defaults + write gates:

    1. Test env AGENT_MEMORY_FORCE_PROJECT (+ FORCE_CONFIDENCE)
    2. working.project_id → high (FJ-3)
    3. project_detect(cwd) heuristics
    """
    force_p = os.environ.get("AGENT_MEMORY_FORCE_PROJECT")
    force_c = os.environ.get("AGENT_MEMORY_FORCE_CONFIDENCE", "high").lower()
    if force_p:
        conf = "high" if force_c == "high" else "low"
        if force_confidence is not None:
            conf = force_confidence.lower()
        return normalize_project_id(force_p.strip()), conf

    wpid = read_working_project_id(root)
    if wpid:
        return wpid, "high"

    detect_cwd = cwd if cwd is not None else os.getcwd()
    pid, conf = detect_project(detect_cwd, force_confidence=force_confidence)
    return pid, conf


def assert_project_semantic_write(
    root: Path,
    scope: str,
    *,
    cwd: str | Path | None = None,
) -> None:
    """Allow project-scope semantic write iff conf==high AND pid==target."""
    if not scope.startswith("project:"):
        return
    raw_target = scope.split(":", 1)[1].strip()
    if not raw_target:
        raise ConflictError("empty project id in scope")
    target = normalize_project_id(raw_target)

    pid, conf = effective_project(root, cwd=cwd)
    if conf != "high" or pid != target:
        raise ConflictError(
            f"project semantic write denied for scope={scope!r}: "
            f"effective project={pid!r} confidence={conf!r} "
            f"(need high confidence and matching project id)"
        )
