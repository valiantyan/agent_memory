"""agent-memory gc"""

from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path

from agent_memory.config import EPISODE_TTL_DAYS, require_schema_for_write
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.index import (
    load_episodic_index,
    reindex,
    save_episodic_index,
)
from agent_memory.recent import prune_recent
def _parse_date(ts: str) -> date | None:
    try:
        return datetime.fromisoformat(ts).date()
    except ValueError:
        return None


def run_gc(root: Path, *, dry_run: bool = False) -> dict:
    require_schema_for_write(root)

    stats = {
        "expiry": {},
        "episodes_archived": 0,
        "recent_kept": 0,
        "dry_run": dry_run,
    }

    if not dry_run:
        stats["expiry"] = run_lazy_expiry(root)
    else:
        stats["expiry"] = {"note": "skipped on dry-run"}

    # Episode TTL archive
    today = datetime.now().astimezone().date()
    archived = 0
    episodes_root = root / "episodes"
    if episodes_root.is_dir():
        for path in list(episodes_root.rglob("*.md")):
            if "archive" in path.parts:
                continue
            try:
                meta, body = parse_fm(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            created = str(meta.get("created_at") or "")
            d = _parse_date(created)
            if d is None:
                continue
            if (today - d).days < EPISODE_TTL_DAYS:
                continue
            # archive
            try:
                rel = path.resolve().relative_to(episodes_root.resolve())
            except ValueError:
                rel = Path(path.name)
            dest = root / "archive" / "episodes" / rel
            if dry_run:
                archived += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(dest))
            archived += 1

    stats["episodes_archived"] = archived

    if not dry_run:
        # rebuild episodic index without archived
        reindex(root)
        stats["recent_kept"] = prune_recent(root)
    else:
        stats["recent_kept"] = -1

    return stats
