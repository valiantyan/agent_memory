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
from agent_memory.intent_draft import list_intent_drafts, read_intent_draft
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

    # ## How to answer "当前任务" (v2.0.3)
    parts.append("## Current-task priority (v2.0.3)")
    parts.append(
        "When user asks 当前任务/what are we doing: "
        "(1) list ALL open/interrupted intents (per session) that conflict with focus; "
        "(2) focused Working goal; "
        "(3) ALL other active work items as parallel (not erased). "
        "Never answer only with a stale single Working goal when multiple intents/items exist."
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

    # ## All active work items (focus marked)
    all_items = list_items(root, project_id=cur_proj)
    foc = read_focus(root)
    focus_id = (foc or {}).get("item_id")
    if all_items:
        parts.append("## Active work items (multi-session safe)")
        for m in all_items[:12]:
            mark = " [FOCUS]" if m.get("id") == focus_id else ""
            sid = m.get("session_id") or ""
            sess = f" sess={sid[:13]}…" if sid and len(str(sid)) > 13 else (f" sess={sid}" if sid else "")
            parts.append(
                f"- {m.get('id')}{mark}: {m.get('goal')}{sess} (updated {m.get('updated_at') or '?'})"
            )
        parts.append(
            "- note: `agent-memory work focus --id <id>` switches focus without deleting others."
        )
        parts.append("")

    # ## Open intents (v2.0.3 per-session; all listed)
    drafts = list_intent_drafts(root, project_id=cur_proj, include_interrupted=True)
    if drafts:
        parts.append("## Open intents (per session; not yet formal Working)")
        for d in drafts[:10]:
            parts.append(
                f"- status={d.get('status') or 'open'} sess={d.get('session_id') or 'legacy'}: "
                f"{d.get('text')}"
            )
        parts.append(
            "- priority: lead with these when answering 当前任务 if they conflict with focus Working."
        )
        parts.append(
            "- note: turn/checkpoint clears only the same session's intent (v2.0.3)."
        )
        parts.append("")
    else:
        # legacy single read fallback already covered by list empty
        draft = read_intent_draft(root, cur_proj)
        if draft and draft.get("text"):
            parts.append("## Open intents (per session; not yet formal Working)")
            parts.append(
                f"- status={draft.get('status') or 'open'} sess={draft.get('session_id') or 'legacy'}: "
                f"{draft.get('text')}"
            )
            parts.append("")

    # ## Recent events (L0 audit, short)
    evs = load_events(root, n=8)
    if evs:
        parts.append("## Recent events (L0)")
        for e in evs:
            ts = e.get("ts") or ""
            kind = e.get("kind") or "event"
            sm = e.get("summary") or ""
            pid = e.get("project_id") or ""
            sid = e.get("session_id") or ""
            line = f"- [{ts}] {kind}"
            if pid:
                line += f" ({pid})"
            if sid:
                line += f" sess={str(sid)[:13]}"
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
