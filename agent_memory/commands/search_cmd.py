"""agent-memory search"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from agent_memory.config import TOP_K_DEFAULT, read_schema_version
from agent_memory.errors import SchemaError
from agent_memory import SCHEMA_VERSION
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.index import (
    load_episodic_index,
    load_semantic_index,
    resolve_under_root,
)
from agent_memory.write_gate import effective_project


@dataclass
class Hit:
    id: str
    score: float
    one_liner: str
    path: str
    scope: str
    status: str = "active"


def _tokens(q: str) -> list[str]:
    return [t for t in re.split(r"\s+", q.strip().lower()) if t]


def _score_blob(query: str, blob: str) -> float:
    if not query.strip():
        return 0.0
    b = blob.lower()
    score = 0.0
    for t in _tokens(query):
        if t in b:
            score += 2.0
            if re.search(rf"\b{re.escape(t)}\b", b):
                score += 1.0
    # full substring boost
    if query.strip().lower() in b:
        score += 3.0
    return score


def _scope_ok(row_scope: str, current_project: str | None, project_flag: str | None) -> bool:
    if project_flag is not None:
        # only that project + always include global? DESIGN: --project overrides current
        # default search scope global ∪ project:current
        # with --project ID: global ∪ project:ID
        if row_scope == "global":
            return True
        return row_scope == f"project:{project_flag}"
    # default: global ∪ current project if known
    if row_scope == "global":
        return True
    if current_project and row_scope == f"project:{current_project}":
        return True
    # no current project: only global
    if not current_project and row_scope.startswith("project:"):
        return False
    return row_scope == "global"


def run_search(
    root: Path,
    query: str = "",
    *,
    mode: str = "semantic",
    project: str | None = None,
    top_k: int = TOP_K_DEFAULT,
    include_staging: bool = False,
    history: bool = False,
    as_json: bool = False,
) -> str:
    ver = read_schema_version(root)
    if ver is None:
        raise SchemaError("no schema_version; run init")
    if ver != SCHEMA_VERSION:
        raise SchemaError(f"schema mismatch {ver}")

    run_lazy_expiry(root)

    cur_proj = project
    if cur_proj is None:
        epid, econf = effective_project(root)
        cur_proj = epid if econf == "high" else None

    hits: list[Hit] = []

    if mode == "semantic":
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
        # empty query: sort by updated_at desc
        if not query.strip():
            # reload order from index updated_at
            by_id = {r.id: r for r in load_semantic_index(root)}
            hits.sort(key=lambda h: by_id.get(h.id).updated_at if by_id.get(h.id) else "", reverse=True)
        else:
            hits.sort(key=lambda h: (-h.score, h.id))

    elif mode == "episodic":
        for row in load_episodic_index(root):
            # project filter: episodic project_id
            if project is not None and row.project_id and row.project_id != project:
                continue
            if (
                project is None
                and cur_proj
                and row.project_id
                and row.project_id != cur_proj
            ):
                # still allow empty project_id globals
                if row.project_id not in ("", cur_proj):
                    continue
            blob = f"{row.id} {row.one_liner} {row.project_id}"
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
                    scope=f"project:{row.project_id}" if row.project_id else "global",
                    status="active",
                )
            )
        if not query.strip():
            by_id = {r.id: r for r in load_episodic_index(root)}
            hits.sort(key=lambda h: by_id.get(h.id).created_at if by_id.get(h.id) else "", reverse=True)
        else:
            hits.sort(key=lambda h: (-h.score, h.id))
    else:
        from agent_memory.errors import UsageError

        raise UsageError(f"unknown mode {mode!r}")

    k = max(0, int(top_k))
    hits = hits[:k] if hits else []

    # include staging
    if include_staging and mode == "semantic":
        st_hits = _scan_candidates(
            root,
            root / "staging" / "candidates",
            query,
            cur_proj,
            project,
            status_label="candidate",
        )
        # fill remaining slots
        have = {h.id for h in hits}
        for h in st_hits:
            if h.id not in have and len(hits) < k:
                hits.append(h)
                have.add(h.id)

    if history and mode == "semantic":
        hist = root / "history" / "semantic"
        h_hits = _scan_candidates(
            root, hist, query, cur_proj, project, status_label="superseded"
        )
        have = {h.id for h in hits}
        for h in h_hits:
            if h.id not in have and len(hits) < k:
                hits.append(h)

    if as_json:
        return json.dumps(
            {
                "hits": [
                    {
                        "id": h.id,
                        "score": h.score,
                        "one_liner": h.one_liner,
                        "path": h.path,
                        "scope": h.scope,
                        "status": h.status,
                    }
                    for h in hits
                ],
                "mode": mode,
            },
            ensure_ascii=False,
            indent=2,
        )

    if not hits:
        return "(no hits)\n"
    blocks = []
    for h in hits:
        blocks.append(
            f"id: {h.id}\n"
            f"score: {h.score}\n"
            f"status: {h.status}\n"
            f"scope: {h.scope}\n"
            f"one_liner: {h.one_liner}\n"
            f"path: {h.path}\n"
        )
    return "\n".join(blocks)


def _scan_candidates(
    root: Path,
    directory: Path,
    query: str,
    cur_proj: str | None,
    project_flag: str | None,
    *,
    status_label: str,
) -> list[Hit]:
    hits: list[Hit] = []
    if not directory.is_dir():
        return hits
    for path in sorted(directory.glob("*.md")):
        try:
            meta, body = parse_fm(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        scope = str(meta.get("scope") or "global")
        if not _scope_ok(scope, cur_proj, project_flag):
            continue
        mid = str(meta.get("id") or "")
        one = str(meta.get("one_liner") or meta.get("title") or "")
        slot = str(meta.get("slot") or "")
        first = body.strip().splitlines()[0] if body.strip() else ""
        blob = f"{mid} {slot} {one} {first}"
        if query.strip():
            sc = _score_blob(query, blob)
            if sc <= 0:
                continue
        else:
            sc = 0.0
        try:
            rel = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
        hits.append(
            Hit(
                id=mid,
                score=sc,
                one_liner=one,
                path=rel,
                scope=scope,
                status=status_label,
            )
        )
    hits.sort(key=lambda h: (-h.score, h.id))
    return hits
