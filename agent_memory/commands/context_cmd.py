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
from agent_memory.project_detect import detect_project
from agent_memory.work_items import list_items, load_item, read_focus
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


def resolve_context_project(
    root: Path,
    *,
    project: str | None = None,
    cwd: str | Path | None = None,
) -> tuple[str | None, str]:
    """Resolve project for context inject.

    Priority (v2.0.4):
      1) explicit --project
      2) cwd detect (high) — used by Codex hooks
      3) working/current.md project_id only
    Do **not** call project_detect(os.getcwd()) when cwd is omitted (avoids
    ambient-repo pollution in CLI/tests).
    """
    if project and str(project).strip():
        return str(project).strip(), "flag"
    if cwd is not None:
        try:
            det_id, conf = detect_project(Path(cwd))
        except OSError:
            det_id, conf = None, "low"
        if conf == "high" and det_id:
            return det_id, "cwd"
    from agent_memory.write_gate import read_working_project_id

    wpid = read_working_project_id(root)
    if wpid:
        return wpid, "working"
    return None, "none"


def _item_sections_body(meta: dict, body: str) -> str:
    """Render a work-item body for Working section."""
    goal = meta.get("goal") or ""
    lines = [
        f"# Working · project focus",
        "",
        f"## Goal",
        "",
        str(goal),
        "",
    ]
    # keep decisions/next from item body if present
    if "## Decisions" in body:
        part = body.split("## Decisions", 1)[1]
        dec = part.split("## ", 1)[0].strip() if "## " in part else part.strip()
        lines.extend(["## Decisions", "", dec, ""])
    if "## Next steps" in body:
        part = body.split("## Next steps", 1)[1]
        nxt = part.split("## ", 1)[0].strip() if "## " in part else part.strip()
        lines.extend(["## Next steps", "", nxt, ""])
    return "\n".join(lines).rstrip() + "\n"


def run_context(
    root: Path,
    *,
    query: str = "",
    project: str | None = None,
    cwd: str | Path | None = None,
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

    cur_proj, proj_src = resolve_context_project(root, project=project, cwd=cwd)

    # ## How to answer "当前任务" (v2.0.4)
    parts.append("## Current-task priority (v2.0.4)")
    parts.append(
        f"Context project={cur_proj or '(none)'} (source={proj_src}). "
        "When user asks 当前任务: "
        "(1) open/interrupted intents for THIS project only; "
        "(2) THIS project's focused work item; "
        "(3) other active items for THIS project only. "
        "Never present another project's Working as current."
    )
    parts.append("")

    # ## Working — per-project focus only (never foreign project current.md)
    foc = read_focus(root, cur_proj)
    focus_id = (foc or {}).get("item_id")
    rendered_working = False
    if focus_id:
        loaded = load_item(root, focus_id)
        if loaded:
            meta, body = loaded
            if not cur_proj or meta.get("project_id") == cur_proj:
                title = f"## Working (focus item_id={focus_id}"
                if cur_proj:
                    title += f" project={cur_proj}"
                title += ")"
                parts.append(title)
                parts.append(_item_sections_body(meta, body).rstrip("\n"))
                parts.append("")
                rendered_working = True
    if not rendered_working and not cur_proj and working_path(root).is_file():
        # No project scope: fall back to global current.md
        wb = _working_body(root)
        if wb is not None:
            parts.append("## Working (focus)")
            parts.append(wb.rstrip("\n"))
            parts.append("")
            rendered_working = True
    if not rendered_working and cur_proj:
        parts.append(f"## Working (project={cur_proj}; no focus for this project)")
        parts.append(
            "(No focused work item for this project yet. "
            "UserPrompt may create draft items; use turn/checkpoint or "
            "`work focus --id` to set focus.)"
        )
        parts.append("")

    # ## Active work items — THIS project only
    all_items = list_items(root, project_id=cur_proj)
    if all_items:
        parts.append(
            f"## Active work items (project={cur_proj or 'all'}; multi-session safe)"
        )
        for m in all_items[:12]:
            mark = " [FOCUS]" if m.get("id") == focus_id else ""
            sid = m.get("session_id") or ""
            sess = (
                f" sess={sid[:13]}…"
                if sid and len(str(sid)) > 13
                else (f" sess={sid}" if sid else "")
            )
            parts.append(
                f"- {m.get('id')}{mark}: {m.get('goal')}{sess} "
                f"(updated {m.get('updated_at') or '?'})"
            )
        parts.append(
            "- note: `agent-memory work focus --id <id>` switches focus without deleting others."
        )
        parts.append("")

    # ## Open intents — THIS project only
    drafts = list_intent_drafts(root, project_id=cur_proj, include_interrupted=True)
    if drafts:
        parts.append(
            f"## Open intents (project={cur_proj or 'all'}; per session)"
        )
        for d in drafts[:10]:
            parts.append(
                f"- status={d.get('status') or 'open'} "
                f"sess={d.get('session_id') or 'legacy'}: {d.get('text')}"
            )
        parts.append(
            "- priority: lead with these when answering 当前任务 if they conflict with focus."
        )
        parts.append("")
    else:
        draft = read_intent_draft(root, cur_proj)
        if draft and draft.get("text"):
            parts.append(
                f"## Open intents (project={cur_proj or 'all'}; per session)"
            )
            parts.append(
                f"- status={draft.get('status') or 'open'} "
                f"sess={draft.get('session_id') or 'legacy'}: {draft.get('text')}"
            )
            parts.append("")

    # ## Recent events — prefer same project when scoped
    evs = load_events(root, n=12)
    if evs:
        parts.append("## Recent events (L0)")
        shown = 0
        for e in evs:
            if cur_proj and e.get("project_id") and e.get("project_id") != cur_proj:
                continue
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
            shown += 1
            if shown >= 8:
                break
        parts.append("")

    # ## Semantic — scoped to context project
    k = max(0, int(top_k))
    hits = _semantic_hits(root, query, project=cur_proj, top_k=k)
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
        st_hits = _scan_candidates(
            root,
            root / "staging" / "candidates",
            query,
            cur_proj,
            cur_proj,
            status_label="candidate",
        )
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
