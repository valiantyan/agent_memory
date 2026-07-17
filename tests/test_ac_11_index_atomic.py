"""AC-11: parallel INDEX writes leave a fully parseable file (no half-line truncate)."""

from __future__ import annotations

import concurrent.futures
from pathlib import Path

from agent_memory.commands.init import run_init
from agent_memory.index import (
    SemanticRow,
    load_semantic_index,
    parse_semantic_index,
    save_semantic_index,
)


def _row(i: int) -> SemanticRow:
    return SemanticRow(
        id=f"sem_{i:04d}",
        type="semantic",
        content_kind="fact",
        scope="global",
        slot="",
        one_liner=f"line {i}",
        path=f"scopes/global/semantic/sem_{i:04d}.md",
        updated_at="2026-07-17T00:00:00+08:00",
    )


def _write_batch(root_s: str, worker_id: int) -> None:
    root = Path(root_s)
    base = worker_id * 100
    rows = [_row(base + j) for j in range(20)]
    for _ in range(40):
        save_semantic_index(root, rows)


def test_ac_11_parallel_index_writes_parseable(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    root_s = str(root.resolve())

    # Threads (same process) + processes for stronger replace stress
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda w: _write_batch(root_s, w), range(8)))

    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as ex:
        list(ex.map(_write_batch, [root_s] * 4, range(4)))

    text = (root / "INDEX.semantic.md").read_text(encoding="utf-8")
    rows = parse_semantic_index(text)
    assert isinstance(rows, list)
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("|") and not st.startswith("|----") and "one_liner" not in st:
            if st.lower().startswith("| id |"):
                continue
            assert st.endswith("|"), f"truncated row: {line!r}"
            assert st.count("|") >= 9, f"incomplete cells: {line!r}"
    loaded = load_semantic_index(root)
    assert len(loaded) == 20
    assert all(r.id.startswith("sem_") for r in loaded)
