"""v2.0.1: L0 events, intent-draft, context sections, stop interrupt."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from agent_memory.cli import main
from agent_memory.commands import context_cmd, event_cmd, init as init_cmd
from agent_memory.events import load_events
from agent_memory.intent_draft import intent_draft_path, read_intent_draft

REPO = Path(__file__).resolve().parents[1]
STOP = REPO / "scripts" / "codex-hooks" / "stop_turn.sh"
USER_PROMPT = REPO / "scripts" / "codex-hooks" / "user_prompt_maybe_search.sh"


@pytest.fixture()
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(root))
    return root


def _am_bin(root: Path) -> Path:
    am = root / "_am.sh"
    am.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{sys.executable}" -m agent_memory "$@"\n',
        encoding="utf-8",
    )
    am.chmod(0o755)
    return am


def test_event_user_prompt_drafts_intent(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("kmp-music\n", encoding="utf-8")
    bug = "BUG：macos 版本播放页【播放列表】数据不能点击播放"
    r = event_cmd.run_event(
        mem_root,
        kind="user_prompt",
        summary=bug,
        cwd=cwd,
        session_id="sess-test-1",
    )
    assert r["intent"] == "open"
    assert r["project_id"] == "kmp-music"
    draft = read_intent_draft(mem_root, "kmp-music", "sess-test-1")
    assert draft is not None
    assert "播放列表" in draft["text"]
    assert draft["status"] == "open"
    evs = load_events(mem_root, n=3)
    assert evs
    assert evs[0]["kind"] == "user_prompt"


def test_event_redacts_secrets(mem_root: Path):
    event_cmd.run_event(
        mem_root,
        kind="user_prompt",
        summary="please use api_key=sk-test-forbidden-value-here",
    )
    evs = load_events(mem_root, n=1)
    assert evs[0]["summary"] == "[redacted-secret]"


def test_context_includes_intent_and_events(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "p"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("demo\n", encoding="utf-8")
    event_cmd.run_event(
        mem_root,
        kind="user_prompt",
        summary="BUG: playlist click broken on desktop",
        cwd=cwd,
    )
    out = context_cmd.run_context(mem_root, query="playlist", project="demo")
    assert "## Open intent" in out
    assert "playlist" in out.lower()
    assert "## Recent events" in out


def test_turn_clears_intent(mem_root: Path):
    event_cmd.run_event(
        mem_root,
        kind="user_prompt",
        summary="BUG fix the player",
        project_id="x",
        session_id="turn-sess",
        draft_intent=True,
        auto_item=False,
    )
    assert read_intent_draft(mem_root, "x", "turn-sess") is not None
    assert (
        main(
            [
                "--root",
                str(mem_root),
                "turn",
                "--goal",
                "fix player",
                "--next-steps",
                "- a",
                "--project-id",
                "x",
                "--session-id",
                "turn-sess",
            ]
        )
        == 0
    )
    assert read_intent_draft(mem_root, "x", "turn-sess") is None


def test_stop_no_pending_marks_interrupted(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("demoapp\n", encoding="utf-8")
    event_cmd.run_event(
        mem_root,
        kind="user_prompt",
        summary="BUG: macos playlist cannot click play",
        cwd=cwd,
        session_id="stop-sess-1",
    )
    assert read_intent_draft(mem_root, "demoapp", "stop-sess-1")["status"] == "open"

    am = _am_bin(mem_root)
    env = os.environ.copy()
    env["AGENT_MEMORY_ROOT"] = str(mem_root)
    env["AGENT_MEMORY_BIN"] = str(am)
    payload = json.dumps(
        {
            "cwd": str(cwd),
            "hook_event_name": "Stop",
            "session_id": "stop-sess-1",
        }
    )
    r = subprocess.run(
        ["bash", str(STOP)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        cwd=str(cwd),
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "no-op" in (r.stderr or "")
    draft = read_intent_draft(mem_root, "demoapp", "stop-sess-1")
    assert draft is not None
    assert draft["status"] == "interrupted"
    # Working must NOT invent the BUG as goal
    working = (mem_root / "working" / "current.md").read_text(encoding="utf-8")
    assert "macos playlist" not in working.lower()


def test_user_prompt_hook_writes_event(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("hookproj\n", encoding="utf-8")
    am = _am_bin(mem_root)
    env = os.environ.copy()
    env["AGENT_MEMORY_ROOT"] = str(mem_root)
    env["AGENT_MEMORY_BIN"] = str(am)
    prompt = "BUG：macos 版本播放页【播放列表】数据不能点击播放"
    payload = json.dumps(
        {
            "cwd": str(cwd),
            "prompt": prompt,
            "hook_event_name": "UserPromptSubmit",
            "session_id": "hook-sess-99",
        }
    )
    r = subprocess.run(
        ["bash", str(USER_PROMPT)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        cwd=str(cwd),
        check=False,
    )
    assert r.returncode == 0, r.stderr
    evs = load_events(mem_root, n=1)
    assert evs and evs[0]["kind"] == "user_prompt"
    assert "播放列表" in (evs[0].get("summary") or "")
    assert evs[0].get("session_id") == "hook-sess-99"
    draft = read_intent_draft(mem_root, "hookproj", "hook-sess-99")
    assert draft is not None
    # Should inject context JSON or text
    out = r.stdout or ""
    assert "Open intent" in out or "Working" in out or "T0" in out or "work items" in out.lower()
