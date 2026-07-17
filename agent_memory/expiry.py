"""Lazy expiry FM-3/FM-4 (staging semantic only)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from agent_memory.config import (
    INDEX_SEMANTIC_MAX_ACTIVE,
    OBSERVATION_DAYS,
    PROMOTE_IMPORTANCE_MIN,
)
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.index import (
    SemanticRow,
    active_semantic_count,
    load_semantic_index,
    save_semantic_index,
)
from agent_memory.io_atomic import write_text_atomic
from agent_memory.recent import append_recent
from agent_memory.security import SOURCE_BANNED_ACTIVE
from agent_memory.util import now_iso, rel_to_root
from agent_memory.write_gate import assert_project_semantic_write


def _parse_date(ts: str) -> date | None:
    try:
        return datetime.fromisoformat(ts).date()
    except ValueError:
        return None


def _rejected_ids(root: Path) -> set[str]:
    path = root / "meta" / "rejected.jsonl"
    ids: set[str] = set()
    if not path.is_file():
        return ids
    import json

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("id"):
                ids.add(str(obj["id"]))
        except json.JSONDecodeError:
            continue
    return ids


def _scope_path(root: Path, scope: str, mid: str) -> Path:
    if scope.startswith("project:"):
        pid = scope.split(":", 1)[1]
        return root / "scopes" / "projects" / pid / "semantic" / f"{mid}.md"
    return root / "scopes" / "global" / "semantic" / f"{mid}.md"


def run_lazy_expiry(root: Path) -> dict[str, int]:
    """
    Process staging/candidates. Returns counts: promoted, discarded, skipped.
    Called from search/remember (and later checkpoint/session-end/...).
    """
    root = root.resolve()
    staging = root / "staging" / "candidates"
    stats = {"promoted": 0, "discarded": 0, "skipped": 0}
    if not staging.is_dir():
        return stats

    rejected = _rejected_ids(root)
    today = datetime.now().astimezone().date()
    index_rows = load_semantic_index(root)
    index_by_id = {r.id: r for r in index_rows}

    for path in sorted(staging.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            meta, body = parse_fm(text)
        except (OSError, ValueError):
            stats["skipped"] += 1
            continue

        status = str(meta.get("status") or "candidate").lower()
        if status in ("rejected", "discarded", "deleted"):
            continue
        mid = str(meta.get("id") or "")
        if not mid or mid in rejected:
            continue
        if str(meta.get("type") or "semantic") == "procedural":
            continue

        created = str(meta.get("created_at") or "")
        d = _parse_date(created)
        if d is None:
            stats["skipped"] += 1
            continue
        age = (today - d).days
        if age < OBSERVATION_DAYS:
            continue

        importance = int(meta.get("importance") or 0)
        source = meta.get("source") or {}
        source_kind = ""
        if isinstance(source, dict):
            source_kind = str(source.get("kind") or "")

        if importance >= PROMOTE_IMPORTANCE_MIN:
            if source_kind in SOURCE_BANNED_ACTIVE:
                meta["status"] = "discarded"
                write_text_atomic(path, dump(meta, body))
                stats["discarded"] += 1
                continue
            scope = str(meta.get("scope") or "global")
            try:
                assert_project_semantic_write(root, scope)
            except Exception:
                stats["skipped"] += 1
                continue
            if active_semantic_count(root) >= INDEX_SEMANTIC_MAX_ACTIVE:
                stats["skipped"] += 1
                continue

            # supersede same slot
            slot = meta.get("slot")
            slot_s = "" if slot is None else str(slot)
            if slot_s:
                for r in list(index_rows):
                    if (
                        r.scope == scope
                        and r.slot == slot_s
                        and r.type == "semantic"
                        and r.id != mid
                    ):
                        _supersede_row(root, r, index_rows, index_by_id)

            dest = _scope_path(root, scope, mid)
            dest.parent.mkdir(parents=True, exist_ok=True)
            meta["status"] = "active"
            meta["updated_at"] = now_iso()
            write_text_atomic(dest, dump(meta, body))
            try:
                path.unlink()
            except OSError:
                pass
            rel = rel_to_root(root, dest)
            row = SemanticRow(
                id=mid,
                type="semantic",
                content_kind=str(meta.get("content_kind") or ""),
                scope=scope,
                slot=slot_s,
                one_liner=str(meta.get("one_liner") or "")[:80],
                path=rel,
                updated_at=str(meta.get("updated_at") or ""),
            )
            index_rows = [r for r in index_rows if r.id != mid]
            index_rows.append(row)
            index_by_id[mid] = row
            save_semantic_index(root, index_rows)
            append_recent(root, id=mid, kind="semantic", path=rel, op="expiry_promote")
            stats["promoted"] += 1
        else:
            meta["status"] = "discarded"
            write_text_atomic(path, dump(meta, body))
            stats["discarded"] += 1

    return stats


def _supersede_row(
    root: Path,
    row: SemanticRow,
    index_rows: list[SemanticRow],
    index_by_id: dict[str, SemanticRow],
) -> None:
    src = resolve_under_root_safe(root, row.path)
    if src and src.is_file():
        try:
            meta, body = parse_fm(src.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta, body = {"id": row.id}, ""
        meta["status"] = "superseded"
        meta["updated_at"] = now_iso()
        hist = root / "history" / "semantic" / f"{row.id}.md"
        hist.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(hist, dump(meta, body))
        try:
            src.unlink()
        except OSError:
            pass
    index_rows[:] = [r for r in index_rows if r.id != row.id]
    index_by_id.pop(row.id, None)


def resolve_under_root_safe(root: Path, rel: str) -> Path | None:
    from agent_memory.index import resolve_under_root

    return resolve_under_root(root, rel)
