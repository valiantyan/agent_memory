"""PR-5: checkpoint / handoff / session-end (AC-4 + handoff files)."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import checkpoint, handoff_cmd, session_end
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.security import AC8_SECRET_FIXTURE
from agent_memory.working import load_working


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


def test_ac4_checkpoint_goal(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    r = checkpoint.run_checkpoint(root, goal="G2MARK")
    assert r["goal"] == "G2MARK"
    meta, body = load_working(root)
    assert meta["goal"] == "G2MARK"
    assert "G2MARK" in body
    assert meta.get("updated_at")
    # CLI
    assert main(["--root", str(root), "checkpoint", "--goal", "G3"]) == 0


def test_checkpoint_partial_merge(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    checkpoint.run_checkpoint(
        root, goal="G1", decisions="- d1", next_steps="- s1", project_id="app"
    )
    checkpoint.run_checkpoint(root, goal="G2")
    meta, body = load_working(root)
    assert meta["goal"] == "G2"
    assert meta.get("project_id") == "app"
    assert "d1" in body
    assert "s1" in body


def test_checkpoint_runs_lazy_expiry(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import checkpoint as cp

    calls = []
    orig = cp.run_lazy_expiry

    def wrap(r):
        calls.append(1)
        return orig(r)

    cp.run_lazy_expiry = wrap  # type: ignore[assignment]
    try:
        checkpoint.run_checkpoint(root, goal="x")
    finally:
        cp.run_lazy_expiry = orig  # type: ignore[assignment]
    assert calls == [1]


def test_handoff_writes_file_and_working(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    r = handoff_cmd.run_handoff(
        root,
        goal="G1MARK",
        next_steps="- STEP1MARK\n- STEP2",
        project_id="proj1",
    )
    path = root / r["path"]
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "G1MARK" in text
    assert "STEP1MARK" in text
    meta, body = load_working(root)
    assert meta["goal"] == "G1MARK"
    assert meta.get("project_id") == "proj1"
    assert "STEP1MARK" in body
    # resolve by id
    assert main(["--root", str(root), "get", r["id"]]) == 0


def test_handoff_requires_goal(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert main(["--root", str(root), "handoff"]) == 2


def test_session_end_writes_episode(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    checkpoint.run_checkpoint(root, goal="keep-me", decisions="- stay")
    r = session_end.run_session_end(
        root,
        title="summary",
        body="Did the work.\n",
        project_id="p1",
    )
    assert r["episode_id"].startswith("ep_")
    ep_path = root / r["path"]
    assert ep_path.is_file()
    meta, body = parse_fm(ep_path.read_text(encoding="utf-8"))
    assert meta["type"] == "episodic"
    assert "Did the work" in body
    # working goal preserved (touch only)
    wmeta, wbody = load_working(root)
    assert wmeta["goal"] == "keep-me"
    assert "stay" in wbody
    assert wmeta.get("project_id") == "p1"
    # index
    idx = (root / "INDEX.episodic.md").read_text(encoding="utf-8")
    assert r["episode_id"] in idx
    # search episodic
    assert main(["--root", str(root), "search", "--mode", "episodic", "work"]) == 0


def test_session_end_body_too_long(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    code = main(
        [
            "--root",
            str(root),
            "session-end",
            "--title",
            "t",
            "--body",
            "x" * 8001,
        ]
    )
    assert code == 4
    # no episode written
    eps = list((root / "episodes").rglob("*.md")) if (root / "episodes").exists() else []
    assert eps == []


def test_session_end_secret_blocked(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    code = main(
        [
            "--root",
            str(root),
            "session-end",
            "--title",
            "t",
            "--body",
            AC8_SECRET_FIXTURE,
        ]
    )
    assert code == 4


def test_session_end_body_file(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    bf = tmp_path / "body.md"
    bf.write_text("from file body MARK\n", encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(root),
                "session-end",
                "--title",
                "tf",
                "--body-file",
                str(bf),
            ]
        )
        == 0
    )


def test_handoff_no_lazy_expiry(tmp_path):
    """handoff must NOT call run_lazy_expiry (not on FM-4 list)."""
    root = tmp_path / "mem"
    _init(root)
    import agent_memory.commands.handoff_cmd as ho

    # ensure module does not import/call expiry — if it did, monkeypatch would catch
    assert not hasattr(ho, "run_lazy_expiry")
