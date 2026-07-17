"""v2.0.3: per-session intents, session_id on events/items, parallel no-clobber."""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import context_cmd, event_cmd
from agent_memory.events import load_events
from agent_memory.intent_draft import intent_draft_path, list_intent_drafts, read_intent_draft
from agent_memory.work_items import list_items


def test_two_sessions_intents_not_clobber(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG：播放列表点击后当前曲消失",
        project_id="kmp-music",
        session_id="019f6fdd-21c3-aaaa-aaaa-aaaaaaaaaaaa",
    )
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG：搜索成功后再写搜索历史",
        project_id="kmp-music",
        session_id="019f6fdd-6e9e-bbbb-bbbb-bbbbbbbbbbbb",
    )
    drafts = list_intent_drafts(root, project_id="kmp-music")
    texts = " ".join(d.get("text") or "" for d in drafts)
    assert "播放列表" in texts
    assert "搜索" in texts
    assert len(drafts) >= 2
    # both session files exist
    p1 = intent_draft_path(root, "kmp-music", "019f6fdd-21c3-aaaa-aaaa-aaaaaaaaaaaa")
    p2 = intent_draft_path(root, "kmp-music", "019f6fdd-6e9e-bbbb-bbbb-bbbbbbbbbbbb")
    assert p1.is_file() and p2.is_file()
    d1 = read_intent_draft(root, "kmp-music", "019f6fdd-21c3-aaaa-aaaa-aaaaaaaaaaaa")
    assert d1 and "播放列表" in (d1.get("text") or "")


def test_events_and_items_have_session_id(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    r = event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG fix the playlist disappear issue now",
        project_id="kmp-music",
        session_id="sess-playlist-1",
    )
    assert r.get("session_id") == "sess-playlist-1"
    assert r.get("item_id")
    evs = load_events(root, n=1)
    assert evs[0].get("session_id") == "sess-playlist-1"
    items = list_items(root, project_id="kmp-music")
    assert any(m.get("session_id") == "sess-playlist-1" for m in items)
    # auto item must not steal focus if none set — focus may be unset
    # second session item also kept
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG search history should write after results",
        project_id="kmp-music",
        session_id="sess-search-2",
    )
    items = list_items(root, project_id="kmp-music")
    assert len(items) >= 2


def test_turn_clears_only_same_session_intent(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG A playlist",
        project_id="p",
        session_id="s-a",
        auto_item=False,
    )
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG B search",
        project_id="p",
        session_id="s-b",
        auto_item=False,
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "turn",
                "--goal",
                "fix A",
                "--next-steps",
                "- n",
                "--project-id",
                "p",
                "--session-id",
                "s-a",
            ]
        )
        == 0
    )
    assert read_intent_draft(root, "p", "s-a") is None
    assert read_intent_draft(root, "p", "s-b") is not None


def test_context_lists_multiple_intents_and_items(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG playlist disappear on click",
        project_id="p",
        session_id="s1",
    )
    event_cmd.run_event(
        root,
        kind="user_prompt",
        summary="BUG search history write timing wrong",
        project_id="p",
        session_id="s2",
    )
    out = context_cmd.run_context(root, project="p")
    assert "Open intents" in out
    assert "Active work items" in out
    assert "playlist" in out.lower() or "播放" in out or "disappear" in out.lower()
    assert "search" in out.lower() or "历史" in out
    assert "Current-task priority (v2.0.3)" in out


def test_pending_turn_stores_session_id(tmp_path: Path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "turn",
                "--goal",
                "G",
                "--next-steps",
                "- n",
                "--project-id",
                "p",
                "--session-id",
                "sess-xyz",
            ]
        )
        == 0
    )
    data = json.loads((root / "meta/pending-turn/p.json").read_text(encoding="utf-8"))
    assert data.get("session_id") == "sess-xyz"
