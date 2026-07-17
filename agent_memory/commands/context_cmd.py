"""agent-memory context — T0 + working + semantic details (DESIGN §6.4)."""

from __future__ import annotations

import re
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import (
    SEMANTIC_DETAILS_BUDGET,
    T0_BUDGET,
    TOP_K_DEFAULT,
    read_schema_version,
)
from agent_memory.errors import SchemaError
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.index import load_semantic_index, resolve_under_root
from agent_memory.security import assert_t0_budget
from agent_memory.events import load_events
from agent_memory.intent_draft import read_intent_draft
from agent_memory.work_items import list_items, read_focus
from agent_memory.working import load_working, working_path
from agent_memory.write_gate import effective_project

# Reuse search scoring/scoping without circular CLI deps
from agent_memory.commands.search_cmd import (
    Hit,
    _scan_candidates,
    _scope_ok,
    _score_blob,
)


def _t0_body(root: Path) -> str:
    path = root / "profile" / "me.T0.md"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    meta, body = parse_fm(text)
    raw = body if meta else text
    return assert_t0_budget(raw)


def _working_body(root: Path) -> str | None:
    """Return working body if file exists; None if missing (omit section)."""
    if not working_path(root).is_file():
        return None
    try:
        _meta, body = load_working(root)
    except (OSError, ValueError):
        return None
    return body


def _semantic_hits(
    root: Path,
    query: str,
    *,
    project: str | None,
    top_k: int,
) -> list[Hit]:
    cur_proj = project
    if cur_proj is None:
        epid, econf = effective_project(root)
        cur_proj = epid if econf == "high" else None

    hits: list[Hit] = []
    for row in load_semantic_index(root):
        if row.type != "semantic":
            continue
        if not _scope_ok(row.scope, cur_proj, project):
            continue
        blob = f"{row.id} {row.slot} {row.one_liner} {row.content_kind}"
        if query.strip():
            sc = _score_blob(query, blob)
            if sc <= 0:
                continue
        else:
            sc = 0.0
        hits.append(
            Hit(
                id=row.id,
                score=sc,
                one_liner=row.one_liner,
                path=row.path,
                scope=row.scope,
                status="active",
            )
        )
    if not query.strip():
        by_id = {r.id: r for r in load_semantic_index(root)}
        hits.sort(
            key=lambda h: (by_id.get(h.id).updated_at if by_id.get(h.id) else ""),
            reverse=True,
        )
    else:
        hits.sort(key=lambda h: (-h.score, h.id))
    return hits[: max(0, top_k)]


def _load_body(root: Path, rel: str) -> str:
    p = resolve_under_root(root, rel)
    if not p or not p.is_file():
        return ""
    try:
        meta, body = parse_fm(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return body


def _truncate_to_budget(text: str, remaining: int) -> tuple[str, int]:
    """Return (possibly truncated text, new remaining). Marker counts in budget."""
    if remaining <= 0:
        return "", 0
    if len(text) <= remaining:
        return text, remaining - len(text)
    marker = "…[truncated]"
    if remaining <= len(marker):
        return marker[:remaining], 0
    keep = remaining - len(marker)
    return text[:keep] + marker, 0


def run_context(
    root: Path,
    *,
    query: str = "",
    project: str | None = None,
    top_k: int = TOP_K_DEFAULT,
    include_staging: bool = False,
) -> str:
    ver = read_schema_version(root)
    if ver is None:
        raise SchemaError("no schema_version; run init")
    if ver != SCHEMA_VERSION:
        raise SchemaError(f"schema mismatch {ver}")

    run_lazy_expiry(root)

    parts: list[str] = []

    # ## T0
    t0 = _t0_body(root)
    parts.append("## T0")
    parts.append(t0.rstrip("\n"))
    parts.append("")

    cur_proj = project
    if cur_proj is None:
        epid, econf = effective_project(root)
        cur_proj = epid if econf == "high" else None

    # ## How to answer "当前任务" (v2.0.2)
    parts.append("## Current-task priority (v2.0.2)")
    parts.append(
        "When user asks 当前任务/what are we doing: "
        "(1) prefer latest Open intent if present and conflicts with Working; "
        "(2) else focused Working goal; "
        "(3) mention other active work items as parallel, not erased. "
        "Do not answer only with a stale Working goal when Open intent is newer."
    )
    parts.append("")

    # ## Working (focus mirror)
    if working_path(root).is_file():
        wb = _working_body(root)
        if wb is not None:
            foc = read_focus(root)
            title = "## Working (focus)"
            if foc and foc.get("item_id"):
                title = f"## Working (focus item_id={foc.get('item_id')})"
            parts.append(title)
            parts.append(wb.rstrip("\n"))
            parts.append("")

    # ## Other work items (not erased by focus switch)
    others = list_items(root, project_id=cur_proj)
    foc = read_focus(root)
    focus_id = (foc or {}).get("item_id")
    siblings = [m for m in others if m.get("id") != focus_id]
    if siblings:
        parts.append("## Other active work items (not erased)")
        for m in siblings[:8]:
            parts.append(
                f"- {m.get('id')}: {m.get('goal')} (updated {m.get('updated_at') or '?'})"
            )
        parts.append(
            "- note: use `agent-memory work focus --id <id>` to switch focus without deleting others."
        )
        parts.append("")

    # ## Open intent (v2.0.1) — not formal Working; resume hint after interrupt
    draft = read_intent_draft(root, cur_proj)
    if draft and draft.get("text"):
        parts.append("## Open intent (not yet checkpointed Working)")
        parts.append(f"- status: {draft.get('status') or 'open'}")
        parts.append(f"- text: {draft.get('text')}")
        if draft.get("updated_at"):
            parts.append(f"- updated_at: {draft.get('updated_at')}")
        parts.append(
            "- priority: if user asks 当前任务 and this conflicts with Working, lead with this intent."
        )
        parts.append(
            "- note: run `agent-memory turn` / checkpoint to promote; do not invent beyond this text."
        )
        parts.append("")

    # ## Recent events (L0 audit, short)
    evs = load_events(root, n=5)
    if evs:
        parts.append("## Recent events (L0)")
        for e in evs:
            ts = e.get("ts") or ""
            kind = e.get("kind") or "event"
            sm = e.get("summary") or ""
            pid = e.get("project_id") or ""
            line = f"- [{ts}] {kind}"
            if pid:
                line += f" ({pid})"
            if sm:
                line += f": {sm}"
            parts.append(line)
        parts.append("")

    # ## Semantic
    k = max(0, int(top_k))
    hits = _semantic_hits(root, query, project=project, top_k=k)
    parts.append(f"## Semantic (top_k={k})")
    budget = SEMANTIC_DETAILS_BUDGET
    for h in hits:
        body = _load_body(root, h.path)
        body_out, budget = _truncate_to_budget(body, budget)
        parts.append(f"### {h.id} — {h.one_liner}")
        parts.append(body_out.rstrip("\n"))
        parts.append("")
        if budget <= 0:
            break

    # ## Staging (optional)
    if include_staging:
        cur_proj = project
        if cur_proj is None:
            epid, econf = effective_project(root)
            cur_proj = epid if econf == "high" else None
        st_hits = _scan_candidates(
            root,
            root / "staging" / "candidates",
            query,
            cur_proj,
            project,
            status_label="candidate",
        )
        # fill remaining hit slots conceptually; still share body budget
        parts.append("## Staging (candidates)")
        for h in st_hits:
            if budget <= 0:
                break
            body = _load_body(root, h.path)
            body_out, budget = _truncate_to_budget(body, budget)
            parts.append(f"### {h.id} — {h.one_liner}")
            parts.append(body_out.rstrip("\n"))
            parts.append("")

    text = "\n".join(parts).rstrip() + "\n"
    return text


def parse_t0_section(context_out: str) -> str:
    """Helper for tests: extract T0 body between ## T0 and next wire section."""
    # Only stop at wire-format section headers, not ## inside T0 template body
    m = re.search(
        r"(?ms)^## T0\n(.*?)(?=^## (?:Current-task|Working|Other active|Open intent|Recent events|Semantic|Staging)|\Z)",
        context_out,
    )
    if not m:
        return ""
    return m.group(1).rstrip("\n")
