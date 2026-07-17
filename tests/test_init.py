"""PR-1: init + schema safety (DESIGN §6.1) — adversarial hardened."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_memory import SCHEMA_VERSION
from agent_memory.cli import main
from agent_memory.commands.init import run_init
from agent_memory.config import read_schema_version, resolve_root, write_schema_version
from agent_memory.errors import ConflictError
from agent_memory.frontmatter import dump, parse
from agent_memory.io_atomic import write_text_atomic


def test_resolve_root_cli_path(tmp_path):
    root = resolve_root(str(tmp_path / "mem"))
    assert root == (tmp_path / "mem").resolve()


def test_resolve_root_env(tmp_path, monkeypatch):
    p = tmp_path / "envroot"
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(p))
    assert resolve_root(None) == p.resolve()


def test_resolve_root_prefers_cli_over_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_ROOT", str(tmp_path / "env"))
    cli = tmp_path / "cli"
    assert resolve_root(str(cli)) == cli.resolve()


def test_init_creates_tree(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    assert read_schema_version(root) == SCHEMA_VERSION
    assert (root / "profile" / "me.T0.md").is_file()
    assert (root / "working" / "current.md").is_file()
    assert (root / "INDEX.semantic.md").is_file()
    assert (root / "INDEX.episodic.md").is_file()
    assert (root / "PROTOCOL.md").is_file()
    assert (root / "meta" / "quotas.md").is_file()
    assert (root / "meta" / "recent.jsonl").is_file()
    assert (root / "meta" / "rejected.jsonl").is_file()
    assert (root / "staging" / "candidates").is_dir()
    assert (root / "scopes" / "global" / "semantic").is_dir()
    assert (root / "procedural" / "active").is_dir()
    assert (root / "history" / "semantic").is_dir()
    assert "INDEX.semantic" in (root / "INDEX.semantic.md").read_text(encoding="utf-8")


def test_init_refuse_second_without_force(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    with pytest.raises(ConflictError, match="already initialized"):
        run_init(root, force=False)


def test_init_force_without_bodies_rewrites_templates(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    t0 = root / "profile" / "me.T0.md"
    t0.write_text("CUSTOM T0\n", encoding="utf-8")
    run_init(root, force=True)
    assert "Hard constraints" in t0.read_text(encoding="utf-8")
    assert read_schema_version(root) == SCHEMA_VERSION


def test_init_force_with_bodies_refuses(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    body = root / "scopes" / "global" / "semantic" / "sem_x.md"
    body.write_text("---\nid: sem_x\n---\nbody\n", encoding="utf-8")
    with pytest.raises(ConflictError, match="memory body"):
        run_init(root, force=True)
    assert body.is_file()
    assert "sem_x" in body.read_text(encoding="utf-8")


def test_init_bodies_without_schema_refuses(tmp_path):
    root = tmp_path / "mem"
    root.mkdir()
    (root / "scopes" / "global" / "semantic").mkdir(parents=True)
    body = root / "scopes" / "global" / "semantic" / "sem_x.md"
    body.write_text("---\nid: sem_x\n---\nx\n", encoding="utf-8")
    with pytest.raises(ConflictError, match="no schema_version"):
        run_init(root, force=False)
    assert body.is_file()


def test_init_force_preserves_recent_log_if_present(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    recent = root / "meta" / "recent.jsonl"
    recent.write_text('{"id":"keep-me"}\n', encoding="utf-8")
    run_init(root, force=True)
    assert "keep-me" in recent.read_text(encoding="utf-8")


def test_cli_init(tmp_path):
    root = tmp_path / "cli-mem"
    code = main(["--root", str(root), "init"])
    assert code == 0
    assert read_schema_version(root) == SCHEMA_VERSION


def test_cli_init_already_initialized_exit_5(tmp_path):
    root = tmp_path / "cli-mem"
    assert main(["--root", str(root), "init"]) == 0
    assert main(["--root", str(root), "init"]) == 5


def test_cli_init_force_with_bodies_exit_5(tmp_path):
    root = tmp_path / "cli-mem"
    assert main(["--root", str(root), "init"]) == 0
    body = root / "episodes" / "2026" / "07" / "ep.md"
    body.parent.mkdir(parents=True)
    body.write_text("x\n", encoding="utf-8")
    assert main(["--root", str(root), "init", "--force"]) == 5


def test_cli_unknown_command(tmp_path):
    root = tmp_path / "cli-mem"
    main(["--root", str(root), "init"])
    # FA-2 complete: invalid subcommand → argparse exit 2
    assert main(["--root", str(root), "not-a-real-command"]) == 2


def test_cli_quiet_init(tmp_path, capsys):
    root = tmp_path / "q"
    assert main(["--root", str(root), "-q", "init"]) == 0
    out = capsys.readouterr().out
    assert out == ""


def test_write_text_atomic_roundtrip(tmp_path):
    p = tmp_path / "a" / "b.txt"
    write_text_atomic(p, "hello\n")
    assert p.read_text(encoding="utf-8") == "hello\n"


def test_schema_written_atomically_content(tmp_path):
    root = tmp_path / "mem"
    root.mkdir()
    write_schema_version(root)
    assert (root / "schema_version").read_text(encoding="utf-8").strip() == SCHEMA_VERSION


def test_frontmatter_roundtrip():
    meta = {"id": "sem_x", "type": "semantic", "importance": 10}
    text = dump(meta, "喜欢橘子。")
    m2, body = parse(text)
    assert m2["id"] == "sem_x"
    assert "橘子" in body


def test_frontmatter_crlf():
    raw = "---\r\nid: a\r\n---\r\n\r\nbody\r\n"
    meta, body = parse(raw)
    assert meta["id"] == "a"
    assert "body" in body
