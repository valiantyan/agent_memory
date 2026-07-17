"""Parse extract fixture grammar + rules heuristics (DESIGN §6.10)."""

from __future__ import annotations

import re
from dataclasses import dataclass
import yaml

from agent_memory.errors import UsageError


@dataclass
class CandidateDraft:
    type: str  # semantic | procedural
    content_kind: str
    importance: int
    slot: str | None
    scope: str | None  # explicit override or None
    text: str


_CAND_LINE = re.compile(r"(?i)^\s*CANDIDATE:\s*(.+)$")
_HEUR = [
    (
        re.compile(r"(?i)^(记住|remember|prefers?|preference)[:：\s]+(.+)$"),
        "preference",
        7,
    ),
    (
        re.compile(r"(?i)^(决定|decision|decided)[:：\s]+(.+)$"),
        "decision",
        7,
    ),
    (
        re.compile(r"(?i)^(约束|constraint|must not|禁止)[:：\s]+(.+)$"),
        "constraint",
        7,
    ),
]


def _parse_tokens(rest: str) -> CandidateDraft:
    """
    CANDIDATE: [key=value ... | ] kind | importance | slot | text
    or pipe-only: kind | importance | slot | text
    """
    parts = [p.strip() for p in rest.split("|")]
    if len(parts) < 4:
        raise UsageError(f"invalid CANDIDATE line (need ≥4 pipe fields): {rest!r}")

    mem_type = "semantic"
    scope: str | None = None
    # leading key=value tokens before kind
    while parts and "=" in parts[0] and parts[0].split("=", 1)[0].lower() in (
        "type",
        "scope",
    ):
        k, v = parts[0].split("=", 1)
        k, v = k.strip().lower(), v.strip()
        if k == "type":
            mem_type = v
        elif k == "scope":
            scope = v
        parts = parts[1:]

    if len(parts) < 4:
        raise UsageError(f"invalid CANDIDATE fields after kv: {rest!r}")

    kind = parts[0]
    try:
        importance = int(parts[1])
    except ValueError as e:
        raise UsageError(f"invalid importance: {parts[1]!r}") from e
    slot_raw = parts[2]
    slot = None if slot_raw in ("", "_", "-") else slot_raw
    text = "|".join(parts[3:]).strip()
    if not text:
        raise UsageError("CANDIDATE text empty")
    if mem_type not in ("semantic", "procedural"):
        raise UsageError(f"bad type={mem_type!r}")
    return CandidateDraft(
        type=mem_type,
        content_kind=kind,
        importance=importance,
        slot=slot,
        scope=scope,
        text=text,
    )


def parse_fixture_lines(body: str) -> list[CandidateDraft]:
    drafts: list[CandidateDraft] = []
    # YAML block under ## Extract fixtures
    if re.search(r"(?im)^##\s*Extract fixtures\s*$", body):
        m = re.search(
            r"(?is)##\s*Extract fixtures\s*\n(.*?)(?=\n##\s|\Z)",
            body,
        )
        if m:
            block = m.group(1).strip()
            if block:
                data = yaml.safe_load(block)
                if data is None:
                    pass
                elif not isinstance(data, list):
                    raise UsageError("## Extract fixtures must be a YAML list")
                else:
                    for item in data:
                        if not isinstance(item, dict):
                            raise UsageError("fixture items must be mappings")
                        drafts.append(
                            CandidateDraft(
                                type=str(item.get("type") or "semantic"),
                                content_kind=str(item.get("content_kind") or "fact"),
                                importance=int(item.get("importance") or 5),
                                slot=(
                                    None
                                    if item.get("slot") in (None, "", "_")
                                    else str(item.get("slot"))
                                ),
                                scope=(
                                    None
                                    if item.get("scope") in (None, "")
                                    else str(item.get("scope"))
                                ),
                                text=str(item.get("text") or ""),
                            )
                        )
                        if not drafts[-1].text:
                            raise UsageError("fixture text empty")

    for line in body.splitlines():
        m = _CAND_LINE.match(line)
        if not m:
            continue
        drafts.append(_parse_tokens(m.group(1)))
    return drafts


def parse_rules_heuristics(body: str) -> list[CandidateDraft]:
    drafts: list[CandidateDraft] = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        for cre, kind, imp in _HEUR:
            m = cre.match(s)
            if m:
                text = m.group(m.lastindex or 1)
                # last group is content
                if m.lastindex and m.lastindex >= 2:
                    text = m.group(2)
                drafts.append(
                    CandidateDraft(
                        type="semantic",
                        content_kind=kind,
                        importance=imp,
                        slot=None,
                        scope=None,
                        text=text.strip(),
                    )
                )
                break
    return drafts


def extract_candidates(body: str, *, mode: str) -> list[CandidateDraft]:
    mode = (mode or "rules").lower()
    if mode == "fixture":
        drafts = parse_fixture_lines(body)
        # fixture-only: if CANDIDATE grammar present but empty after parse — ok empty
        # if line looks like CANDIDATE but invalid, parse raises
        has_cand = any(_CAND_LINE.match(ln) for ln in body.splitlines())
        has_yaml = bool(re.search(r"(?im)^##\s*Extract fixtures\s*$", body))
        if (has_cand or has_yaml) and not drafts and has_cand:
            # invalid lines would have raised; empty CANDIDATE: is error if only "CANDIDATE:"
            pass
        return drafts

    if mode == "rules":
        # fixture grammar first if present
        if any(_CAND_LINE.match(ln) for ln in body.splitlines()) or re.search(
            r"(?im)^##\s*Extract fixtures\s*$", body
        ):
            return parse_fixture_lines(body)
        return parse_rules_heuristics(body)

    raise UsageError(f"unknown extract mode {mode!r}")


def default_importance(content_kind: str, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    if content_kind in ("constraint", "preference", "decision"):
        return max(7, explicit or 7)
    if content_kind == "fact":
        return 5
    return 4
