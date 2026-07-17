"""YAML front matter parse/dump (PyYAML)."""

from __future__ import annotations

import re
from typing import Any

import yaml

_FM_RE = re.compile(
    r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z",
    re.DOTALL,
)


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Return (meta, body). If no front matter, meta={} and body=text."""
    # Normalize newlines for robust matching; preserve body content as-is after split
    m = _FM_RE.match(text)
    if not m:
        return {}, text
    raw_yaml, body = m.group(1), m.group(2)
    data = yaml.safe_load(raw_yaml) or {}
    if not isinstance(data, dict):
        raise ValueError("front matter must be a YAML mapping")
    return data, body


def dump(meta: dict[str, Any], body: str) -> str:
    """Serialize front matter + body."""
    yaml_str = yaml.safe_dump(
        meta,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).rstrip()
    body = body if body is not None else ""
    if body and not body.endswith("\n"):
        body = body + "\n"
    return f"---\n{yaml_str}\n---\n\n{body}"


def char_len(s: str) -> int:
    """REQ §9.1: Unicode code points = Python len(str)."""
    return len(s)
