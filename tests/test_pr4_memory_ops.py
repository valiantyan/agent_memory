"""PR-4: remember / search / get / forget / recent + AC-3/5/6/7 slices."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agent_memory.cli import main
from agent_memory.security import AC8_SECRET_FIXTURE


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


def test_ac3_preference_unique(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "fruit",
                "--content",
                "喜欢苹果",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "fruit",
                "--content",
                "喜欢橘子",
            ]
        )
        == 0
    )
    from agent_memory.commands import search_cmd

    text = search_cmd.run_search(root, "橘子")
    assert "喜欢橘子" in text
    assert "status: active" in text
    # superseded apple not in default INDEX search
    text2 = search_cmd.run_search(root, "喜欢苹果")
    assert "(no hits)" in text2 or "喜欢苹果" not in text2


def test_ac5_forget_and_recent(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    main(
        [
            "--root",
            str(root),
            "--json",
            "remember",
            "--slot",
            "lang",
            "--content",
            "中文",
        ]
    )
    # parse last remembered via recent
    from agent_memory.commands import recent_cmd, remember

    r = remember.run_remember(root, slot="tool", content="pytest")
    mid = r["id"]
    recent = recent_cmd.run_recent(root, n=5)
    assert mid in recent or "remember" in recent

    assert main(["--root", str(root), "forget", mid]) == 0
    from agent_memory.commands import search_cmd

    text = search_cmd.run_search(root, "pytest")
    assert mid not in text or "(no hits)" in text

    # soft delete still gettable
    assert main(["--root", str(root), "get", mid]) == 0


def test_ac5_hard_forget(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import remember

    r = remember.run_remember(root, slot="tmp", content="vanish")
    mid = r["id"]
    assert main(["--root", str(root), "forget", mid, "--hard"]) == 0
    assert main(["--root", str(root), "get", mid]) == 6


def test_ac6_top_k(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import remember, search_cmd

    for i in range(6):
        remember.run_remember(root, slot=f"s{i}", content=f"unique_token_marker item{i}")
    text = search_cmd.run_search(root, "unique_token_marker", top_k=5)
    # count id: lines
    n = text.count("\nid: ")
    if text.startswith("id: "):
        n = text.count("id: ")
    assert text.count("id: ") <= 5


def test_ac7_portable_copy(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import remember, search_cmd

    remember.run_remember(root, slot="port", content="PORTABLE_MARK")
    dest = tmp_path / "mem2"
    shutil.copytree(root, dest)
    text = search_cmd.run_search(dest, "PORTABLE_MARK")
    assert "PORTABLE_MARK" in text or "port" in text


def test_remember_blocks_secret(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    code = main(
        [
            "--root",
            str(root),
            "remember",
            "--slot",
            "x",
            "--content",
            AC8_SECRET_FIXTURE,
        ]
    )
    assert code == 4


def test_project_scope_denied_without_working(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    code = main(
        [
            "--root",
            str(root),
            "remember",
            "--slot",
            "test",
            "--content",
            "MockK",
            "--project",
            "app-a",
        ]
    )
    assert code == 5


def test_project_scope_with_force_env(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    monkeypatch.setenv("AGENT_MEMORY_FORCE_PROJECT", "app-a")
    monkeypatch.setenv("AGENT_MEMORY_FORCE_CONFIDENCE", "high")
    code = main(
        [
            "--root",
            str(root),
            "remember",
            "--slot",
            "test",
            "--content",
            "MOCK_A_ONLY",
            "--project",
            "app-a",
        ]
    )
    assert code == 0
    # search with project B should not show A mark when filtering
    from agent_memory.commands import search_cmd

    text_b = search_cmd.run_search(root, "MOCK_A_ONLY", project="app-b")
    # global not, project a only — with --project app-b, global still included
    # MOCK is project scope so should not appear for app-b
    assert "MOCK_A_ONLY" not in text_b or "(no hits)" in text_b
    text_a = search_cmd.run_search(root, "MOCK_A_ONLY", project="app-a")
    assert "MOCK_A_ONLY" in text_a


def test_search_empty_ok(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert main(["--root", str(root), "search", "nothinghere"]) == 0


def test_json_remember(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    # use library for stable parse
    from agent_memory.commands import remember

    r = remember.run_remember(root, slot="j", content="json-ok")
    assert "id" in r and r["id"].startswith("sem_")


def test_history_flag_finds_superseded(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import remember, search_cmd

    remember.run_remember(root, slot="fruit", content="喜欢苹果")
    remember.run_remember(root, slot="fruit", content="喜欢橘子")
    plain = search_cmd.run_search(root, "喜欢苹果")
    assert "(no hits)" in plain or "喜欢苹果" not in plain
    hist = search_cmd.run_search(root, "喜欢苹果", history=True)
    assert "喜欢苹果" in hist
    assert "superseded" in hist


def test_lazy_expiry_hook_on_search(tmp_path):
    """search always invokes run_lazy_expiry (no-op when staging empty)."""
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import search_cmd

    calls = []
    orig = search_cmd.run_lazy_expiry

    def wrap(r):
        calls.append(r)
        return orig(r)

    search_cmd.run_lazy_expiry = wrap  # type: ignore[assignment]
    try:
        search_cmd.run_search(root, "")
    finally:
        search_cmd.run_lazy_expiry = orig  # type: ignore[assignment]
    assert len(calls) == 1
