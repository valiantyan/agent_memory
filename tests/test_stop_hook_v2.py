"""v2 Stop hook: claim-before-checkpoint against memory-root pending-turn."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from agent_memory.cli import main

REPO = Path(__file__).resolve().parents[1]
STOP = REPO / "scripts" / "codex-hooks" / "stop_turn.sh"


@pytest.fixture()
def mem_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init", "-q"]) == 0
    # point hook at this root + this repo's scripts via PATH to agent-memory
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(root))
    # use installed package entry
    return root


def _run_stop(root: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    import sys

    env = os.environ.copy()
    env["AGENT_MEMORY_ROOT"] = str(root)
    am = root / "_am.sh"
    am.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{sys.executable}" -m agent_memory "$@"\n',
        encoding="utf-8",
    )
    am.chmod(0o755)
    env["AGENT_MEMORY_BIN"] = str(am)
    payload = json.dumps({"cwd": str(cwd), "hook_event_name": "Stop"})
    return subprocess.run(
        ["bash", str(STOP)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        cwd=str(cwd),
        check=False,
    )


def test_stop_noop_without_pending(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    r = _run_stop(mem_root, cwd)
    assert r.returncode == 0
    assert "no-op" in (r.stderr or "")
    working = (mem_root / "working" / "current.md").read_text(encoding="utf-8")
    # default template goal should remain-ish; at least not crash
    assert "Working" in working or "CURRENT" in working or "goal" in working.lower()


def test_stop_claim_and_checkpoint(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / ".agent-memory-project").write_text("demoapp\n", encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(mem_root),
                "turn",
                "--goal",
                "STOP_HOOK_GOAL",
                "--next-steps",
                "- n1",
                "--project-id",
                "demoapp",
            ]
        )
        == 0
    )
    pending = mem_root / "meta" / "pending-turn" / "demoapp.json"
    assert pending.is_file()
    r = _run_stop(mem_root, cwd)
    assert r.returncode == 0, r.stderr
    assert not pending.is_file()
    working = (mem_root / "working" / "current.md").read_text(encoding="utf-8")
    assert "STOP_HOOK_GOAL" in working
    done = list((mem_root / "meta" / "pending-turn" / "done").glob("*.json"))
    assert done


def test_stop_incomplete_quarantine(mem_root: Path, tmp_path: Path):
    cwd = tmp_path / "proj"
    cwd.mkdir()
    pdir = mem_root / "meta" / "pending-turn"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "_global.json").write_text(
        json.dumps({"goal": "only-goal", "next_steps": ""}),
        encoding="utf-8",
    )
    r = _run_stop(mem_root, cwd)
    assert r.returncode == 0
    assert "quarantine" in (r.stderr or "") or "incomplete" in (r.stderr or "")
    assert not (pdir / "_global.json").is_file()
