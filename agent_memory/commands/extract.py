"""agent-memory extract"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory import SCHEMA_VERSION
from agent_memory.config import require_schema_for_write
from agent_memory.errors import ConflictError, NotFoundError, UsageError
from agent_memory.extract_rules import default_importance, extract_candidates
from agent_memory.frontmatter import dump
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.resolve import resolve_id
from agent_memory.security import gate_write_payload
from agent_memory.util import derive_one_liner, mint_semantic_id, now_iso, slug, utc_stamp
from agent_memory.write_gate import assert_project_semantic_write


def run_extract(
    root: Path,
    episode_id: str,
    *,
    mode: str = "rules",
    force: bool = False,
    quiet: bool = False,
) -> dict:
    require_schema_for_write(root)
    got = resolve_id(root, episode_id)
    if not got:
        raise NotFoundError(f"episode not found: {episode_id}")
    if str(got.meta.get("type") or "") not in ("episodic", "episode", ""):
        # allow any resolved body but prefer episodic
        pass

    body = got.body
    try:
        drafts = extract_candidates(body, mode=mode)
    except UsageError:
        raise

    ep_scope = str(got.meta.get("scope") or "")
    ep_project = got.meta.get("project_id")
    if not ep_scope or ep_scope == "null":
        if ep_project:
            ep_scope = f"project:{ep_project}"
        else:
            ep_scope = "global"

    written: list[dict] = []
    errors: list[str] = []

    for d in drafts:
        scope = d.scope or ep_scope
        if scope and not scope.startswith("project:") and scope != "global":
            scope = f"project:{scope}" if scope else "global"

        mem_type = d.type
        imp = default_importance(d.content_kind, d.importance)
        slot = d.slot
        text = d.text
        one = derive_one_liner(text)

        try:
            warns = gate_write_payload(
                text,
                one,
                force=force,
                source_kind="extracted",
                for_active=False,
                one_liner=one,
                label="extract",
            )
            for w in warns:
                if not quiet:
                    print(w, file=sys.stderr)
            # project gate for candidates under project scope
            assert_project_semantic_write(root, scope)
        except (ConflictError, Exception) as e:
            # collect and continue
            from agent_memory.errors import MemoryError, SecurityError

            if isinstance(e, (ConflictError, SecurityError, UsageError, MemoryError)):
                errors.append(f"{text[:40]!r}: {e}")
                continue
            raise

        ts = now_iso()
        if mem_type == "procedural":
            mid = f"proc_{utc_stamp()}_{slug(d.content_kind)}_{slug(text)[:8]}"
            dest = root / "procedural" / "candidates" / f"{mid}.md"
        else:
            mid = mint_semantic_id(slot or d.content_kind, text, scope)
            dest = root / "staging" / "candidates" / f"{mid}.md"

        dest.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "id": mid,
            "type": mem_type,
            "content_kind": d.content_kind,
            "status": "candidate",
            "scope": scope,
            "slot": slot,
            "title": "",
            "one_liner": one,
            "importance": imp,
            "source": {
                "kind": "extracted",
                "episode_id": episode_id,
                "agent": None,
            },
            "created_at": ts,
            "updated_at": ts,
            "schema_version": SCHEMA_VERSION,
        }
        write_text_atomic(
            dest, dump(meta, text if text.endswith("\n") else text + "\n")
        )
        try:
            rel = dest.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel = str(dest)
        append_recent(root, id=mid, kind=mem_type, path=rel, op="extract")
        written.append({"id": mid, "type": mem_type, "path": rel})

    if errors and not written:
        raise ConflictError("extract failed for all candidates: " + "; ".join(errors))
    if errors and not quiet:
        for e in errors:
            print(f"warning: {e}", file=sys.stderr)

    return {"candidates": written, "errors": errors}
