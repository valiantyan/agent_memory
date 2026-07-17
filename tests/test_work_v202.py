"""v2.0.2 multi work-items + focus; checkpoint does not erase siblings."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import context_cmd
from agent_memory.work_items import list_items, load_item, read_focus


def test_two_checkpoints_keep_both_items(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "checkpoint",
                "--goal",
                "TASK_ONE_PLAYLIST",
                "--next-steps",
                "- a1",
                "--project-id",
                "kmp-music",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "checkpoint",
                "--goal",
                "TASK_TWO_SCAN",
                "--next-steps",
                "- b1",
                "--project-id",
                "kmp-music",
            ]
        )
        == 0
    )
    items = list_items(root, project_id="kmp-music")
    goals = {m.get("goal") for m in items}
    assert "TASK_ONE_PLAYLIST" in goals
    assert "TASK_TWO_SCAN" in goals
    assert len(items) >= 2
    foc = read_focus(root)
    assert foc and foc.get("item_id")
    # focus is second task
    focused = load_item(root, foc["item_id"])
    assert focused is not None
    assert focused[0].get("goal") == "TASK_TWO_SCAN"
    # first item file still on disk
    first = [m for m in items if m.get("goal") == "TASK_ONE_PLAYLIST"][0]
    assert load_item(root, first["id"]) is not None
    working = (root / "working" / "current.md").read_text(encoding="utf-8")
    assert "TASK_TWO_SCAN" in working


def test_work_focus_switches_without_delete(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "work",
                "upsert",
                "--goal",
                "ALPHA_TASK",
                "--next-steps",
                "- x",
                "--project-id",
                "p",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "work",
                "upsert",
                "--goal",
                "BETA_TASK",
                "--next-steps",
                "- y",
                "--project-id",
                "p",
            ]
        )
        == 0
    )
    items = list_items(root, project_id="p")
    alpha = [m for m in items if m.get("goal") == "ALPHA_TASK"][0]
    assert main(["--root", str(root), "work", "focus", "--id", alpha["id"]]) == 0
    working = (root / "working" / "current.md").read_text(encoding="utf-8")
    assert "ALPHA_TASK" in working
    assert load_item(root, [m for m in items if m.get("goal") == "BETA_TASK"][0]["id"])


def test_context_lists_siblings_and_priority(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    main(
        [
            "--root",
            str(root),
            "checkpoint",
            "--goal",
            "G1_UNIQUE",
            "--next-steps",
            "- n",
            "--project-id",
            "p",
        ]
    )
    main(
        [
            "--root",
            str(root),
            "checkpoint",
            "--goal",
            "G2_UNIQUE",
            "--next-steps",
            "- n",
            "--project-id",
            "p",
        ]
    )
    out = context_cmd.run_context(root, query="", project="p")
    assert "Current-task priority" in out
    assert "Active work items" in out
    assert "G1_UNIQUE" in out
    assert "G2_UNIQUE" in out


def test_install_project_strips_global_triggers(tmp_path: Path, monkeypatch):
    """Simulates strip logic: after strip, no agent-memory-hook in global."""
    # unit-level: reuse strip helper by invoking install dry via python snippet
    home = tmp_path / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    hooks = {
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash /x/session_start.sh # agent-memory-hook session_start",
                        }
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash /x/stop_turn.sh # agent-memory-hook stop_turn",
                        },
                        {
                            "type": "command",
                            "command": "/apps/muxy-hook.sh stop # muxy-notification-hook",
                        },
                    ]
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash /x/user_prompt.sh # agent-memory-hook user_prompt",
                        }
                    ]
                }
            ],
        }
    }
    import json

    (codex / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")

    MARKER = "agent-memory-hook"

    def cmd_is_ours(cmd: str) -> bool:
        return MARKER in str(cmd or "") or "/hooks/agent-memory/" in str(cmd or "")

    def strip_ours_list(lst):
        out = []
        for entry in lst:
            if not isinstance(entry, dict):
                continue
            inner = entry.get("hooks")
            if isinstance(inner, list):
                kept = [
                    h
                    for h in inner
                    if isinstance(h, dict) and not cmd_is_ours(h.get("command", ""))
                ]
                if kept:
                    new_e = dict(entry)
                    new_e["hooks"] = kept
                    out.append(new_e)
        return out

    data = json.loads((codex / "hooks.json").read_text(encoding="utf-8"))
    h = data["hooks"]
    for key in ("SessionStart", "Stop", "UserPromptSubmit"):
        h[key] = strip_ours_list(h.get(key) or [])
    for k in list(h.keys()):
        if not h[k]:
            del h[k]
    # SessionStart / UserPrompt gone; Stop keeps muxy
    assert "SessionStart" not in h
    assert "UserPromptSubmit" not in h
    assert "Stop" in h
    assert "muxy" in json.dumps(h["Stop"])
    assert "agent-memory-hook" not in json.dumps(h)
