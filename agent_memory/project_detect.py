"""project-detect heuristics (DESIGN §7)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

_MARKER_NAMES = (".agent-memory-project", "AGENT_PROJECT")
_MANIFEST_NAMES = (
    "package.json",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
    "Package.swift",
    "pom.xml",
)
_SAFE = re.compile(r"[^a-z0-9-]+")


def normalize_project_id(raw: str) -> str:
    s = raw.strip().lower().replace("_", "-").replace(" ", "-")
    s = _SAFE.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unknown"


def _read_marker_id(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    # YAML-ish id: value
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("id:"):
            return normalize_project_id(line.split(":", 1)[1].strip().strip("\"'"))
        if line.lower().startswith("project_id:"):
            return normalize_project_id(line.split(":", 1)[1].strip().strip("\"'"))
        # first non-empty line as bare id
        return normalize_project_id(line)
    return None


def _walk_markers(start: Path, max_levels: int = 40) -> tuple[str, str] | None:
    cur = start.resolve()
    for _ in range(max_levels):
        for name in _MARKER_NAMES:
            p = cur / name
            if p.is_file():
                pid = _read_marker_id(p)
                if pid:
                    return pid, "high"
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    return None


def _git_toplevel(start: Path) -> Path | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    top = proc.stdout.strip()
    if not top:
        return None
    return Path(top).resolve()


def _looks_like_project_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    for name in _MANIFEST_NAMES:
        if (path / name).is_file():
            return True
    return False


def detect_project(
    path: str | Path | None = None,
    *,
    force_confidence: str | None = None,
) -> tuple[str, str]:
    """
    Returns (project_id, confidence) with confidence in {high, low}.
    force_confidence: override confidence only (still runs heuristics for id).
    """
    start = Path(path or os.getcwd()).expanduser().resolve()
    if not start.exists():
        # fall back to cwd
        start = Path(os.getcwd()).resolve()
    if start.is_file():
        start = start.parent

    pid = "unknown"
    conf = "low"

    # 1 markers
    hit = _walk_markers(start)
    if hit:
        pid, conf = hit
    else:
        # 2 git root
        top = _git_toplevel(start)
        if top is not None:
            home = Path.home().resolve()
            if top != home:
                cand = normalize_project_id(top.name)
                if cand and cand != "unknown":
                    pid, conf = cand, "high"
        # 3 manifest in start dir
        if conf != "high" and _looks_like_project_dir(start):
            pid, conf = normalize_project_id(start.name), "high"
        # 4 else basename low
        if conf != "high":
            pid = normalize_project_id(start.name)
            conf = "low"

    if force_confidence is not None:
        fc = force_confidence.lower().strip()
        if fc not in ("high", "low"):
            from agent_memory.errors import UsageError

            raise UsageError("--force-confidence must be high or low")
        conf = fc

    return pid, conf
