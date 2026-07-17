"""Security gates: secrets, PII, source bans, size limits (DESIGN §10)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from agent_memory.config import EPISODE_BODY_MAX, ONE_LINER_MAX, T0_BUDGET
from agent_memory.errors import SecurityError, UsageError

# --- Pattern tables (DESIGN §10.2 / §10.3) ---

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("S-API-KEY-ASSIGN", re.compile(r"(?i)api[_-]?key\s*=\s*\S+")),
    ("S-SK-PREFIX", re.compile(r"(?i)(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{8,}")),
    ("S-BEARER", re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*")),
    ("S-PEM-KEY", re.compile(r"-----BEGIN[ A-Z0-9]*PRIVATE KEY-----")),
    ("S-AWS-KEY", re.compile(r"(?i)AKIA[0-9A-Z]{16}")),
    ("S-GENERIC-TOKEN", re.compile(r"(?i)(xox[baprs]-)[0-9A-Za-z\-]{10,}")),
]

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "P-CN-ID",
        re.compile(
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
    ),
    (
        "P-BANK-16",
        re.compile(r"(?<!\d)(?:\d[ -]*?){16,19}(?!\d)"),
    ),
]

# AC-8 fixture (must always reject)
AC8_SECRET_FIXTURE = "api_key=sk-test-forbidden"

# source.kind for active semantic / promote target
SOURCE_ALLOWED_ACTIVE = frozenset({"user_explicit", "extracted", "handoff"})
SOURCE_BANNED_ACTIVE = frozenset({"tool_output", "web"})

SOURCE_ALLOWED_ANY = frozenset(
    {"user_explicit", "extracted", "handoff", "tool_output", "web"}
)


@dataclass(frozen=True)
class PatternHit:
    pattern_id: str
    kind: str  # secret | pii
    snippet: str


def _snippet(text: str, start: int, end: int, width: int = 40) -> str:
    a = max(0, start - 8)
    b = min(len(text), end + 8)
    s = text[a:b].replace("\n", " ")
    if len(s) > width:
        s = s[: width - 1] + "…"
    return s


def find_secrets(text: str) -> list[PatternHit]:
    hits: list[PatternHit] = []
    if not text:
        return hits
    for pid, cre in SECRET_PATTERNS:
        for m in cre.finditer(text):
            hits.append(
                PatternHit(
                    pattern_id=pid,
                    kind="secret",
                    snippet=_snippet(text, m.start(), m.end()),
                )
            )
    return hits


def find_pii(text: str) -> list[PatternHit]:
    hits: list[PatternHit] = []
    if not text:
        return hits
    for pid, cre in PII_PATTERNS:
        for m in cre.finditer(text):
            # Weak Luhn skip for bank: still report; force allowed
            hits.append(
                PatternHit(
                    pattern_id=pid,
                    kind="pii",
                    snippet=_snippet(text, m.start(), m.end()),
                )
            )
    return hits


def scan_text(text: str) -> list[PatternHit]:
    return find_secrets(text) + find_pii(text)


def assert_no_secrets(text: str, *, label: str = "content") -> None:
    """Raise SecurityError if any secret pattern matches. Not forceable."""
    hits = find_secrets(text)
    if hits:
        ids = ", ".join(sorted({h.pattern_id for h in hits}))
        raise SecurityError(
            f"secret pattern blocked in {label}: {ids} "
            f"(example snippet: {hits[0].snippet!r}); "
            f"--force cannot bypass secrets"
        )


def assert_content_allowed(
    text: str,
    *,
    force: bool = False,
    label: str = "content",
    warnings: list[str] | None = None,
) -> list[str]:
    """
    Full content gate: secrets always fail; PII fails unless force.
    Returns warning messages (e.g. PII forced).
    """
    warns: list[str] = [] if warnings is None else warnings
    assert_no_secrets(text, label=label)
    pii = find_pii(text)
    if pii:
        ids = ", ".join(sorted({h.pattern_id for h in pii}))
        if not force:
            raise SecurityError(
                f"sensitive pattern blocked in {label}: {ids} "
                f"(snippet: {pii[0].snippet!r}); re-run with --force if intentional non-secret"
            )
        msg = f"warning: forcing write despite PII patterns in {label}: {ids}"
        warns.append(msg)
    return warns


def assert_source_for_active(source_kind: str | None) -> None:
    """FW-8 / SEC-4: tool_output/web must not become semantic active."""
    kind = (source_kind or "").strip()
    if not kind:
        raise UsageError("source.kind is required for active semantic writes")
    if kind in SOURCE_BANNED_ACTIVE:
        raise SecurityError(
            f"source.kind={kind!r} cannot become active semantic "
            f"(banned: {sorted(SOURCE_BANNED_ACTIVE)})"
        )
    if kind not in SOURCE_ALLOWED_ACTIVE:
        raise SecurityError(
            f"source.kind={kind!r} not allowed for active; "
            f"allowed={sorted(SOURCE_ALLOWED_ACTIVE)}"
        )


def assert_source_known(source_kind: str | None) -> None:
    kind = (source_kind or "").strip()
    if kind not in SOURCE_ALLOWED_ANY:
        raise UsageError(
            f"unknown source.kind={kind!r}; allowed={sorted(SOURCE_ALLOWED_ANY)}"
        )


def assert_one_liner_len(one_liner: str) -> None:
    if len(one_liner) > ONE_LINER_MAX:
        raise SecurityError(
            f"one_liner length {len(one_liner)} > {ONE_LINER_MAX} characters"
        )


def assert_episode_body_len(body: str) -> None:
    if len(body) > EPISODE_BODY_MAX:
        raise SecurityError(
            f"episode body length {len(body)} > {EPISODE_BODY_MAX} characters "
            f"(fail, no truncate)"
        )


def assert_t0_budget(body: str) -> str:
    """Return body truncated for context emit; not a write gate."""
    if len(body) <= T0_BUDGET:
        return body
    marker = "…[truncated]"
    keep = T0_BUDGET - len(marker)
    if keep < 0:
        return marker[:T0_BUDGET]
    return body[:keep] + marker


def gate_write_payload(
    *parts: str,
    force: bool = False,
    source_kind: str | None = None,
    for_active: bool = False,
    one_liner: str | None = None,
    episode_body: str | None = None,
    label: str = "payload",
) -> list[str]:
    """
    Combined write gate used by future CLI writers.
    Returns list of warning strings.
    """
    warns: list[str] = []
    if source_kind is not None:
        assert_source_known(source_kind)
        if for_active:
            assert_source_for_active(source_kind)
    if one_liner is not None:
        assert_one_liner_len(one_liner)
        assert_content_allowed(one_liner, force=force, label=f"{label}.one_liner", warnings=warns)
    if episode_body is not None:
        assert_episode_body_len(episode_body)
        assert_content_allowed(
            episode_body, force=force, label=f"{label}.episode_body", warnings=warns
        )
    for i, part in enumerate(parts):
        if part:
            assert_content_allowed(
                part, force=force, label=f"{label}[{i}]", warnings=warns
            )
    return warns


def scan_paths_for_secrets(texts: Iterable[tuple[str, str]]) -> list[tuple[str, PatternHit]]:
    """For doctor: list of (path_label, hit)."""
    out: list[tuple[str, PatternHit]] = []
    for label, text in texts:
        for h in find_secrets(text):
            out.append((label, h))
    return out
