"""v2: turn pending under memory root; no business-repo path required."""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import init as init_cmd
from agent_memory.commands import turn_cmd
from agent_memory.pending_turn import pending_turn_path, read_pending_turn


def test_turn_writes_under_meta_pending(tmp_path: Path):
    root = tmp_path / "mem"
    init_cmd.run_init(root)
    result = turn_cmd.run_turn(
        root,
        goal="GOAL_ALPHA_UNIQUE",
        next_steps="- a\n- b",
        decisions="- d",
        project_id="kmp-music",
    )
    path = root / result["path"]
    assert path.is_file()
    assert "meta/pending-turn" in result["path"]
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["goal"] == "GOAL_ALPHA_UNIQUE"
    assert "a" in data["next_steps"]
    assert data["project_id"] == "kmp-music"


def test_turn_cli_and_checkpoint_consume(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "turn",
                "--goal",
                "G1",
                "--next-steps",
                "- n1",
                "--project-id",
                "demo",
            ]
        )
        == 0
    )
    p = pending_turn_path(root, "demo")
    assert p.is_file()
    data = read_pending_turn(root, "demo")
    assert data is not None
    assert (
        main(
            [
                "--root",
                str(root),
                "checkpoint",
                "--goal",
                data["goal"],
                "--next-steps",
                data["next_steps"],
                "--project-id",
                "demo",
            ]
        )
        == 0
    )
    working = (root / "working" / "current.md").read_text(encoding="utf-8")
    assert "G1" in working


def test_turn_requires_goal_and_next(tmp_path: Path):
    root = tmp_path / "mem"
    init_cmd.run_init(root)
    assert main(["--root", str(root), "turn", "--goal", "only", "--next-steps", ""]) != 0
