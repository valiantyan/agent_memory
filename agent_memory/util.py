"""Shared helpers: time, ids, one_liner."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from agent_memory.config import ONE_LINER_MAX

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def now_iso() -> str:
    """Local-aware ISO-8601 with offset when possible."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def slug(text: str, max_len: int = 24) -> str:
    s = text.strip().lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return (s or "x")[:max_len]


def derive_one_liner(
    content: str,
    explicit: str | None = None,
    title: str | None = None,
) -> str:
    """DESIGN §4.3."""
    if explicit is not None:
        raw = explicit
    else:
        raw = ""
        for line in content.splitlines():
            if line.strip():
                raw = line.strip()
                break
        if not raw:
            raw = title or ""
    raw = raw.strip().replace("\n", " ")
    if len(raw) <= ONE_LINER_MAX:
        return raw
    marker = "…[truncated]"
    keep = ONE_LINER_MAX - len(marker)
    if keep < 0:
        return marker[:ONE_LINER_MAX]
    return raw[:keep] + marker


def mint_semantic_id(slot: str, content: str, scope: str) -> str:
    """sem_YYYYMMDD_HHMMSS_slug_hex8"""
    ts = utc_stamp()
    h = hashlib.sha256(
        f"{content}\0{slot}\0{scope}\0{ts}".encode("utf-8")
    ).hexdigest()[:8]
    return f"sem_{ts}_{slug(slot)}_{h}"


def rel_to_root(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()
