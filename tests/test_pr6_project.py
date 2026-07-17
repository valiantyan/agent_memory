"""PR-6: project-detect + AC-2 / AC-10 write gates."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import remember, search_cmd
from agent_memory.project_detect import detect_project, normalize_project_id
from agent_memory.write_gate import assert_project_semantic_write, effective_project


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


def test_normalize():
    assert normalize_project_id("My_App Name") == "my-app-name"


def test_marker_file_high(tmp_path):
    proj = tmp_path / "cool-app"
    proj.mkdir()
    (proj / ".agent-memory-project").write_text("cool-app\n", encoding="utf-8")
    pid, conf = detect_project(proj)
    assert pid == "cool-app"
    assert conf == "high"


def test_marker_yaml_id(tmp_path):
    proj = tmp_path / "x"
    proj.mkdir()
    (proj / "AGENT_PROJECT").write_text("id: from-yaml\n", encoding="utf-8")
    pid, conf = detect_project(proj)
    assert pid == "from-yaml"
    assert conf == "high"


def test_manifest_dir_high(tmp_path):
    proj = tmp_path / "pkg-demo"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    pid, conf = detect_project(proj)
    assert pid == "pkg-demo"
    assert conf == "high"


def test_force_confidence_low(tmp_path):
    proj = tmp_path / "marked"
    proj.mkdir()
    (proj / ".agent-memory-project").write_text("marked\n", encoding="utf-8")
    pid, conf = detect_project(proj, force_confidence="low")
    assert pid == "marked"
    assert conf == "low"


def test_working_overrides_detect(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    proj = tmp_path / "disk-proj"
    proj.mkdir()
    (proj / ".agent-memory-project").write_text("disk-proj\n", encoding="utf-8")
    # checkpoint sets working project
    assert (
        main(
            [
                "--root",
                str(root),
                "checkpoint",
                "--project-id",
                "work-proj",
                "--goal",
                "g",
            ]
        )
        == 0
    )
    pid, conf = effective_project(root, cwd=proj)
    assert pid == "work-proj"
    assert conf == "high"


def test_ac10_force_confidence_low_denies_project_write(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    # Isolate cwd from the workspace (which has pyproject.toml → high confidence)
    bare = tmp_path / "bare-cwd"
    bare.mkdir()
    monkeypatch.chdir(bare)

    # low confidence cwd → project semantic write denied (AC-10)
    code = main(
        [
            "--root",
            str(root),
            "remember",
            "--slot",
            "t",
            "--content",
            "x",
            "--project",
            "anything",
        ]
    )
    assert code == 5

    # CLI project-detect force low (--json is global flag before subcommand)
    out_code = main(
        [
            "--root",
            str(root),
            "--json",
            "project-detect",
            str(bare),
            "--force-confidence",
            "low",
        ]
    )
    assert out_code == 0


def test_ac10_explicit_low_gate(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    monkeypatch.setenv("AGENT_MEMORY_FORCE_PROJECT", "app-a")
    monkeypatch.setenv("AGENT_MEMORY_FORCE_CONFIDENCE", "low")
    code = main(
        [
            "--root",
            str(root),
            "remember",
            "--slot",
            "t",
            "--content",
            "x",
            "--project",
            "app-a",
        ]
    )
    assert code == 5


def test_ac2_project_isolation(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    # set working to A
    main(
        [
            "--root",
            str(root),
            "checkpoint",
            "--project-id",
            "app-a",
            "--goal",
            "work on A",
        ]
    )
    assert (
        main(
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
        == 0
    )
    # default search with working A should find it
    text_a = search_cmd.run_search(root, "MOCK_A_ONLY")
    assert "MOCK_A_ONLY" in text_a
    # search as project B only — not in B, not global
    text_b = search_cmd.run_search(root, "MOCK_A_ONLY", project="app-b")
    assert "MOCK_A_ONLY" not in text_b or "(no hits)" in text_b
    # cannot write project B while working is A
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "t",
                "--content",
                "b-stuff",
                "--project",
                "app-b",
            ]
        )
        == 5
    )


def test_detect_high_allows_matching_write(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    # clear working project
    proj = tmp_path / "real-app"
    proj.mkdir()
    (proj / ".agent-memory-project").write_text("real-app\n", encoding="utf-8")
    monkeypatch.chdir(proj)
    # no working project_id
    pid, conf = effective_project(root, cwd=proj)
    assert pid == "real-app" and conf == "high"
    assert_project_semantic_write(root, "project:real-app", cwd=proj)
    r = remember.run_remember(
        root, slot="x", content="ok", project="real-app"
    )
    assert r["id"].startswith("sem_")


def test_mismatch_high_denies(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    proj = tmp_path / "proj-b"
    proj.mkdir()
    (proj / ".agent-memory-project").write_text("proj-b\n", encoding="utf-8")
    monkeypatch.chdir(proj)
    from agent_memory.errors import ConflictError
    import pytest

    with pytest.raises(ConflictError):
        assert_project_semantic_write(root, "project:proj-a", cwd=proj)


def test_cli_project_detect_json(tmp_path):
    proj = tmp_path / "z"
    proj.mkdir()
    (proj / "package.json").write_text("{}", encoding="utf-8")
    root = tmp_path / "mem"
    _init(root)
    assert (
        main(
            [
                "--root",
                str(root),
                "--json",
                "project-detect",
                str(proj),
            ]
        )
        == 0
    )


def test_global_write_always_ok(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "lang",
                "--content",
                "中文",
            ]
        )
        == 0
    )
