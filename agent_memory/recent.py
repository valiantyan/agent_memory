"""meta/recent.jsonl helpers."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from agent_memory.config import RECENT_DEFAULT_N, RECENT_RETENTION_DAYS
from agent_memory.io_atomic import append_line, write_text_atomic
from agent_memory.util import now_iso


def recent_path(root: Path) -> Path:
    return root / "meta" / "recent.jsonl"


def append_recent(
    root: Path,
    *,
    id: str,
    kind: str,
    path: str,
    op: str,
) -> None:
    rec = {
        "ts": now_iso(),
        "id": id,
        "kind": kind,
        "path": path,
        "op": op,
    }
    try:
        append_line(recent_path(root), json.dumps(rec, ensure_ascii=False))
    except OSError:
        pass  # best-effort


def _parse_ts(ts: str) -> date | None:
    try:
        # handle offset ISO
        dt = datetime.fromisoformat(ts)
        return dt.date()
    except ValueError:
        return None


def _within_retention(ts: str, *, today: date | None = None) -> bool:
    """True if ts is missing/unparseable or age ≤ RECENT_RETENTION_DAYS."""
    d = _parse_ts(ts)
    if d is None:
        return True
    if today is None:
        today = datetime.now().astimezone().date()
    return (today - d).days <= RECENT_RETENTION_DAYS


def load_recent(root: Path, *, n: int = RECENT_DEFAULT_N) -> list[dict[str, Any]]:
    """Load recent entries (newest first). Read-only; does not prune the file.

    Entries older than RECENT_RETENTION_DAYS are omitted from the result so
    ``recent`` stays useful without writing. On-disk prune is ``prune_recent``
    (called from ``gc`` only).
    """
    path = recent_path(root)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                entries.append(obj)
        except json.JSONDecodeError:
            continue
    # newest first
    entries.reverse()
    today = datetime.now().astimezone().date()
    entries = [
        e
        for e in entries
        if _within_retention(str(e.get("ts") or ""), today=today)
    ]
    return entries[: max(0, n)]


def prune_recent(root: Path) -> int:
    """Drop entries older than RECENT_RETENTION_DAYS natural days. Returns kept count.

    Call from ``gc`` (write path) only — not from the read-only ``recent`` command.
    """
    path = recent_path(root)
    if not path.is_file():
        return 0
    today = datetime.now().astimezone().date()
    kept: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ts = str(obj.get("ts") or "")
        if _within_retention(ts, today=today):
            kept.append(raw)
    write_text_atomic(path, ("\n".join(kept) + ("\n" if kept else "")))
    return len(kept)
