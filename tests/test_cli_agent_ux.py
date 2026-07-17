"""Agent UX fixes: --root after subcommand; recent is read-only."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from agent_memory.cli import hoist_global_options, main
from agent_memory.commands import init as init_cmd
from agent_memory.commands import recent_cmd
from agent_memory.commands import remember
from agent_memory.config import RECENT_RETENTION_DAYS
from agent_memory.recent import load_recent, prune_recent, recent_path


def test_hoist_root_after_subcommand():
    out = hoist_global_options(
        ["context", "--query", "kmp", "--root", "/tmp/mem"]
    )
    assert out[:2] == ["--root", "/tmp/mem"]
    assert "context" in out
    assert "--query" in out


def test_hoist_root_equals_form():
    out = hoist_global_options(["recent", "--root=/tmp/mem", "--n", "5"])
    assert out[0] == "--root=/tmp/mem"
    assert out[1:] == ["recent", "--n", "5"]


def test_hoist_preserves_leading_globals():
    out = hoist_global_options(["--root", "/a", "context", "--query", "x"])
    assert out == ["--root", "/a", "context", "--query", "x"]


def test_main_accepts_root_after_subcommand(tmp_path, capsys):
    init_cmd.run_init(tmp_path)
    code = main(
        [
            "context",
            "--query",
            "test",
            "--root",
            str(tmp_path),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "T0" in out or "Working" in out or "Hard constraints" in out


def test_recent_is_read_only(tmp_path):
    init_cmd.run_init(tmp_path)
    remember.run_remember(
        tmp_path,
        slot="fruit",
        content="likes mango",
        content_kind="preference",
    )
    path = recent_path(tmp_path)
    before = path.read_text(encoding="utf-8")
    mtime_before = path.stat().st_mtime_ns

    text = recent_cmd.run_recent(tmp_path, n=10)
    assert "remember" in text or "fruit" in text or "sem_" in text

    after = path.read_text(encoding="utf-8")
    assert after == before
    assert path.stat().st_mtime_ns == mtime_before


def test_load_recent_filters_expired_without_writing(tmp_path):
    init_cmd.run_init(tmp_path)
    path = recent_path(tmp_path)
    old_ts = (
        datetime.now().astimezone() - timedelta(days=RECENT_RETENTION_DAYS + 5)
    ).isoformat(timespec="seconds")
    new_ts = datetime.now().astimezone().isoformat(timespec="seconds")
    lines = [
        json.dumps(
            {
                "ts": old_ts,
                "id": "old_id",
                "kind": "semantic",
                "path": "x",
                "op": "remember",
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "ts": new_ts,
                "id": "new_id",
                "kind": "semantic",
                "path": "y",
                "op": "remember",
            },
            ensure_ascii=False,
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtime_before = path.stat().st_mtime_ns

    entries = load_recent(tmp_path, n=20)
    ids = [e["id"] for e in entries]
    assert "new_id" in ids
    assert "old_id" not in ids
    assert path.stat().st_mtime_ns == mtime_before

    # prune (gc path) does rewrite and drop old
    kept = prune_recent(tmp_path)
    assert kept == 1
    body = path.read_text(encoding="utf-8")
    assert "new_id" in body
    assert "old_id" not in body
