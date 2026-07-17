"""Append-only event log under meta/events.jsonl (L0 · v2.0.1).

Not semantic memory: durable audit of user prompts / stop outcomes so
"something happened" is never identical to "nothing happened".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent_memory.io_atomic import append_line, write_text_atomic
from agent_memory.security import find_secrets
from agent_memory.util import now_iso

EVENTS_MAX_LINES = 500
SUMMARY_MAX = 300
_WS = re.compile(r"\s+")


def events_path(root: Path) -> Path:
    return root / "meta" / "events.jsonl"


def sanitize_summary(text: str, *, max_len: int = SUMMARY_MAX) -> str:
    """Truncate and redact secrets; never store full chat dumps."""
    s = _WS.sub(" ", (text or "").strip())
    if not s:
        return ""
    if find_secrets(s):
        return "[redacted-secret]"
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def append_event(
    root: Path,
    *,
    kind: str,
    summary: str = "",
    project_id: str | None = None,
    session_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one event line. Best-effort; returns the record written."""
    kind_s = (kind or "event").strip()[:64] or "event"
    rec: dict[str, Any] = {
        "ts": now_iso(),
        "kind": kind_s,
        "summary": sanitize_summary(summary),
        "project_id": (project_id or "").strip() or None,
        "session_id": (session_id or "").strip() or None,
    }
    if extra:
        for k, v in extra.items():
            if k in rec:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                rec[k] = v
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        append_line(path, json.dumps(rec, ensure_ascii=False))
    except OSError:
        return rec
    _maybe_trim(path)
    return rec


def load_events(root: Path, *, n: int = 10) -> list[dict[str, Any]]:
    """Newest first."""
    path = events_path(root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            rows.append(o)
        if len(rows) >= max(0, n):
            break
    return rows


def _maybe_trim(path: Path, *, max_lines: int = EVENTS_MAX_LINES) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= max_lines:
        return
    keep = lines[-max_lines:]
    try:
        write_text_atomic(path, "\n".join(keep) + "\n")
    except OSError:
        pass
