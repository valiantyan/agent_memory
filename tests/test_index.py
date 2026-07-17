"""PR-2: INDEX parse/serialize, escape, reindex, doctor."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands.init import run_init
from agent_memory.frontmatter import dump
from agent_memory.index import (
    EpisodicRow,
    SemanticRow,
    doctor_check,
    escape_cell,
    load_semantic_index,
    parse_semantic_index,
    reindex,
    save_semantic_index,
    serialize_semantic_index,
    unescape_cell,
)
from agent_memory.io_atomic import write_text_atomic


def _write_semantic(
    root: Path,
    *,
    mid: str,
    scope: str = "global",
    status: str = "active",
    slot: str = "",
    one_liner: str = "line",
    mem_type: str = "semantic",
    rel_dir: str | None = None,
) -> Path:
    if rel_dir is None:
        if scope.startswith("project:"):
            pid = scope.split(":", 1)[1]
            rel_dir = f"scopes/projects/{pid}/semantic"
        else:
            rel_dir = "scopes/global/semantic"
    path = root / rel_dir / f"{mid}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": mid,
        "type": mem_type,
        "content_kind": "fact",
        "status": status,
        "scope": scope,
        "slot": slot or None,
        "one_liner": one_liner,
        "importance": 5,
        "source": {"kind": "user_explicit"},
        "created_at": "2026-07-17T00:00:00+08:00",
        "updated_at": "2026-07-17T00:00:00+08:00",
        "schema_version": "1.0.0",
    }
    write_text_atomic(path, dump(meta, f"body of {mid}\n"))
    return path


def test_escape_pipe_roundtrip():
    s = "a|b\\c"
    assert unescape_cell(escape_cell(s)) == s


def test_parse_serialize_roundtrip():
    rows = [
        SemanticRow(
            id="sem_a",
            type="semantic",
            content_kind="preference",
            scope="global",
            slot="fruit",
            one_liner="likes oranges|maybe",
            path="scopes/global/semantic/sem_a.md",
            updated_at="2026-07-17T00:00:00+08:00",
        )
    ]
    text = serialize_semantic_index(rows)
    parsed = parse_semantic_index(text)
    assert len(parsed) == 1
    assert parsed[0].id == "sem_a"
    assert parsed[0].one_liner == "likes oranges|maybe"
    assert parsed[0].slot == "fruit"


def test_reindex_from_bodies(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    _write_semantic(root, mid="sem_a", one_liner="A")
    _write_semantic(root, mid="sem_b", status="candidate")  # should not index if not under staging path
    # candidate status under scopes still skipped by status filter
    n_sem, n_epi = reindex(root)
    assert n_sem == 1
    rows = load_semantic_index(root)
    assert [r.id for r in rows] == ["sem_a"]


def test_reindex_ignores_staging_and_history(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    _write_semantic(root, mid="sem_active")
    st = root / "staging" / "candidates" / "sem_stg.md"
    st.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        st,
        dump(
            {
                "id": "sem_stg",
                "type": "semantic",
                "status": "active",  # malicious active in staging
                "scope": "global",
                "one_liner": "nope",
                "content_kind": "fact",
            },
            "x",
        ),
    )
    hist = root / "history" / "semantic" / "sem_old.md"
    hist.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        hist,
        dump(
            {
                "id": "sem_old",
                "type": "semantic",
                "status": "active",
                "scope": "global",
                "one_liner": "old",
                "content_kind": "fact",
            },
            "x",
        ),
    )
    reindex(root)
    ids = {r.id for r in load_semantic_index(root)}
    assert ids == {"sem_active"}


def test_reindex_procedural_active(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    path = root / "procedural" / "active" / "proc_x.md"
    write_text_atomic(
        path,
        dump(
            {
                "id": "proc_x",
                "type": "procedural",
                "status": "active",
                "scope": "global",
                "content_kind": "other",
                "one_liner": "how to handoff",
            },
            "steps",
        ),
    )
    reindex(root)
    rows = load_semantic_index(root)
    assert any(r.id == "proc_x" and r.type == "procedural" for r in rows)


def test_reindex_episodic(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    ep = root / "episodes" / "2026" / "07" / "ep_1.md"
    ep.parent.mkdir(parents=True)
    write_text_atomic(
        ep,
        dump(
            {
                "id": "ep_1",
                "type": "episodic",
                "status": "active",
                "scope": "project:app",
                "project_id": "app",
                "one_liner": "did stuff",
                "created_at": "2026-07-17T00:00:00+08:00",
            },
            "body",
        ),
    )
    n_sem, n_epi = reindex(root)
    assert n_epi == 1
    assert n_sem == 0


def test_doctor_orphan_and_missing(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    _write_semantic(root, mid="sem_orphan")
    # INDEX empty → orphan
    findings = doctor_check(root)
    assert any(f.code == "orphan_active" for f in findings)

    reindex(root)
    findings2 = doctor_check(root)
    assert not any(f.level == "error" for f in findings2)

    # break path
    rows = load_semantic_index(root)
    rows[0].path = "scopes/global/semantic/missing.md"
    save_semantic_index(root, rows)
    findings3 = doctor_check(root)
    assert any(f.code == "index_missing_file" for f in findings3)


def test_doctor_id_mismatch(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    path = _write_semantic(root, mid="sem_a")
    reindex(root)
    # corrupt body id
    write_text_atomic(
        path,
        dump(
            {
                "id": "sem_OTHER",
                "type": "semantic",
                "status": "active",
                "scope": "global",
                "content_kind": "fact",
                "one_liner": "x",
            },
            "b",
        ),
    )
    findings = doctor_check(root)
    assert any(f.code == "id_mismatch" for f in findings)


def test_cli_reindex_and_doctor(tmp_path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init"]) == 0
    _write_semantic(root, mid="sem_z")
    assert main(["--root", str(root), "reindex"]) == 0
    assert main(["--root", str(root), "doctor"]) == 0


def test_cli_doctor_fails_on_error(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    _write_semantic(root, mid="sem_o")
    # orphan → doctor non-zero
    assert main(["--root", str(root), "doctor"]) == 1


def test_doctor_path_escape(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    _write_semantic(root, mid="sem_a")
    reindex(root)
    rows = load_semantic_index(root)
    rows[0].path = "../outside.md"
    save_semantic_index(root, rows)
    findings = doctor_check(root)
    assert any(f.code == "path_escape" for f in findings)


def test_reindex_requires_schema(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    code = main(["--root", str(root), "reindex"])
    assert code == 3
