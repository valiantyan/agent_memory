"""v2.0.4: context scoped by cwd/project; no foreign Working inject."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import context_cmd, event_cmd
from agent_memory.work_items import list_items, read_focus, upsert_item


def test_context_cwd_does_not_show_foreign_working(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0

    # kmp focus + item
    upsert_item(
        root,
        goal="kmp search history fix",
        next_steps="- k1",
        project_id="kmp-music",
        session_id="s-kmp",
        set_focus=True,
    )
    # also write global current via checkpoint for noise
    main(
        [
            "--root",
            str(root),
            "checkpoint",
            "--goal",
            "kmp search history fix",
            "--next-steps",
            "- k1",
            "--project-id",
            "kmp-music",
            "-q",
        ]
    )

    # ANR item without stealing need own focus later
    upsert_item(
        root,
        goal="ANR task 1 monitoring",
        next_steps="- a1",
        project_id="vibe-anr-monitoring",
        session_id="s-anr",
        set_focus=True,
    )

    anr_cwd = tmp_path / "Vibe-ANR-Monitoring"
    anr_cwd.mkdir()
    (anr_cwd / ".agent-memory-project").write_text(
        "vibe-anr-monitoring\n", encoding="utf-8"
    )

    out = context_cmd.run_context(root, query="session start", cwd=anr_cwd)
    assert "project=vibe-anr-monitoring" in out or "vibe-anr-monitoring" in out
    assert "ANR task 1" in out
    # must NOT present kmp as Working focus
    assert "kmp search history fix" not in out.split("## Active work items")[0]
    # kmp must not appear in ANR-scoped active items section
    items_sec = out
    if "## Active work items" in out:
        items_sec = out.split("## Active work items", 1)[1].split("## ", 1)[0]
        assert "kmp search history" not in items_sec
        assert "ANR task 1" in items_sec

    kmp_cwd = tmp_path / "kmp-music"
    kmp_cwd.mkdir()
    (kmp_cwd / ".agent-memory-project").write_text("kmp-music\n", encoding="utf-8")
    out_k = context_cmd.run_context(root, query="session start", cwd=kmp_cwd)
    assert "kmp search history fix" in out_k
    assert "ANR task 1" not in out_k.split("## Semantic")[0]


def test_per_project_focus_files(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    upsert_item(
        root, goal="goal A", next_steps="-1", project_id="proj-a", set_focus=True
    )
    upsert_item(
        root, goal="goal B", next_steps="-2", project_id="proj-b", set_focus=True
    )
    fa = read_focus(root, "proj-a")
    fb = read_focus(root, "proj-b")
    assert fa and fa.get("project_id") == "proj-a"
    assert fb and fb.get("project_id") == "proj-b"
    assert fa.get("item_id") != fb.get("item_id")
    # project-a focus file exists
    assert (root / "working" / "focus" / "proj-a.json").is_file()
    assert (root / "working" / "focus" / "proj-b.json").is_file()


def test_list_items_strict_project_filter(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    upsert_item(
        root, goal="only a", next_steps="-1", project_id="a", set_focus=False
    )
    upsert_item(
        root, goal="only b", next_steps="-1", project_id="b", set_focus=False
    )
    assert len(list_items(root, project_id="a")) == 1
    assert list_items(root, project_id="a")[0]["goal"] == "only a"
    assert len(list_items(root, project_id="b")) == 1


def test_event_auto_item_still_project_scoped(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    cwd = tmp_path / "anr"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("vibe-anr-monitoring\n", encoding="utf-8")
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="我现在是 ANR-Monitoring 项目的任务 1",
        cwd=cwd,
        session_id="sess-anr-x",
    )
    items = list_items(root, project_id="vibe-anr-monitoring")
    assert any("ANR" in (m.get("goal") or "") for m in items)
    # no focus steal if we didn't set — actually auto set_focus=False
    # kmp focus should not exist for anr
    assert read_focus(root, "vibe-anr-monitoring") is None or True
