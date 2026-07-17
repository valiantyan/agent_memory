"""PR-7: extract / promote / reject / gc / AC-9 / AC-X / AC-P."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import extract, promote, reject, session_end
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.io_atomic import write_text_atomic
from agent_memory.security import AC8_SECRET_FIXTURE


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


def _episode_with_body(root: Path, body: str) -> str:
    r = session_end.run_session_end(root, title="ep", body=body)
    return r["episode_id"]


def test_ac_x_extract_fixture(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    body = """
Notes.

CANDIDATE: preference | 8 | fruit | 喜欢苹果
CANDIDATE: type=procedural | other | 5 | _ | how to handoff
"""
    eid = _episode_with_body(root, body)
    result = extract.run_extract(root, eid, mode="fixture")
    types = {c["type"] for c in result["candidates"]}
    assert "semantic" in types
    assert "procedural" in types
    # not in default search
    from agent_memory.commands import search_cmd

    text = search_cmd.run_search(root, "喜欢苹果")
    assert "(no hits)" in text or "喜欢苹果" not in text
    # staging file exists
    st = list((root / "staging" / "candidates").glob("*.md"))
    assert st
    proc = list((root / "procedural" / "candidates").glob("*.md"))
    assert proc


def test_extract_rules_heuristics(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = _episode_with_body(root, "记住: 使用 pnpm\n决定: 采用 monorepo\n")
    r = extract.run_extract(root, eid, mode="rules")
    assert len(r["candidates"]) >= 2


def test_ac9_expiry_promote_and_discard(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    old = (datetime.now().astimezone() - timedelta(days=6)).isoformat(timespec="seconds")
    # high importance → promote
    p1 = root / "staging" / "candidates" / "sem_hi.md"
    p1.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p1,
        dump(
            {
                "id": "sem_hi",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "content_kind": "preference",
                "one_liner": "hi imp",
                "importance": 8,
                "source": {"kind": "extracted"},
                "created_at": old,
                "updated_at": old,
                "schema_version": "1.0.0",
            },
            "high body",
        ),
    )
    # low importance → discard
    p2 = root / "staging" / "candidates" / "sem_lo.md"
    write_text_atomic(
        p2,
        dump(
            {
                "id": "sem_lo",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "content_kind": "fact",
                "one_liner": "lo imp",
                "importance": 4,
                "source": {"kind": "extracted"},
                "created_at": old,
                "updated_at": old,
                "schema_version": "1.0.0",
            },
            "low body",
        ),
    )
    stats = run_lazy_expiry(root)
    assert stats["promoted"] >= 1
    assert stats["discarded"] >= 1
    assert (root / "scopes" / "global" / "semantic" / "sem_hi.md").is_file()
    meta_lo, _ = parse_fm(p2.read_text(encoding="utf-8"))
    assert meta_lo["status"] == "discarded"
    idx = (root / "INDEX.semantic.md").read_text(encoding="utf-8")
    assert "sem_hi" in idx
    assert "sem_lo" not in idx


def test_ac9_reject_never_promotes(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    old = (datetime.now().astimezone() - timedelta(days=10)).isoformat(timespec="seconds")
    p = root / "staging" / "candidates" / "sem_rj.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p,
        dump(
            {
                "id": "sem_rj",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "content_kind": "preference",
                "one_liner": "nope",
                "importance": 9,
                "source": {"kind": "extracted"},
                "created_at": old,
                "schema_version": "1.0.0",
            },
            "x",
        ),
    )
    reject.run_reject(root, "sem_rj")
    run_lazy_expiry(root)
    assert not (root / "scopes" / "global" / "semantic" / "sem_rj.md").exists()
    meta, _ = parse_fm(p.read_text(encoding="utf-8"))
    assert meta["status"] == "rejected"


def test_promote_semantic(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = _episode_with_body(
        root, "CANDIDATE: fact | 6 | _ | promote-me-please\n"
    )
    extract.run_extract(root, eid, mode="fixture")
    # find candidate id
    cands = list((root / "staging" / "candidates").glob("*.md"))
    assert cands
    meta, _ = parse_fm(cands[0].read_text(encoding="utf-8"))
    mid = meta["id"]
    r = promote.run_promote(root, mid)
    assert r["id"] == mid
    assert (root / "scopes" / "global" / "semantic" / f"{mid}.md").is_file()
    from agent_memory.commands import search_cmd

    assert "promote-me-please" in search_cmd.run_search(root, "promote-me")


def test_ac_p_procedural_needs_confirm(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = _episode_with_body(
        root, "CANDIDATE: type=procedural | other | 5 | _ | do the thing\n"
    )
    extract.run_extract(root, eid, mode="fixture")
    cands = list((root / "procedural" / "candidates").glob("*.md"))
    mid = parse_fm(cands[0].read_text(encoding="utf-8"))[0]["id"]
    code = main(["--root", str(root), "promote", mid])
    assert code == 2  # UsageError
    assert (
        main(
            [
                "--root",
                str(root),
                "promote",
                mid,
                "--user-confirmed",
            ]
        )
        == 0
    )
    assert (root / "procedural" / "active" / f"{mid}.md").is_file()


def test_promote_blocks_tool_output_source(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    # recent created_at so lazy expiry does not discard first
    recent = datetime.now().astimezone().isoformat(timespec="seconds")
    p = root / "staging" / "candidates" / "sem_bad.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p,
        dump(
            {
                "id": "sem_bad",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "content_kind": "fact",
                "one_liner": "x",
                "importance": 8,
                "source": {"kind": "tool_output"},
                "created_at": recent,
                "schema_version": "1.0.0",
            },
            "body",
        ),
    )
    code = main(["--root", str(root), "promote", "sem_bad"])
    assert code == 4


def test_gc_archives_old_episodes(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    old = (datetime.now().astimezone() - timedelta(days=100)).isoformat(
        timespec="seconds"
    )
    ep = root / "episodes" / "2020" / "01" / "ep_old.md"
    ep.parent.mkdir(parents=True)
    write_text_atomic(
        ep,
        dump(
            {
                "id": "ep_old",
                "type": "episodic",
                "status": "active",
                "scope": "global",
                "one_liner": "ancient",
                "created_at": old,
                "schema_version": "1.0.0",
            },
            "old body",
        ),
    )
    main(["--root", str(root), "reindex"])
    assert main(["--root", str(root), "gc"]) == 0
    assert not ep.exists()
    arch = list((root / "archive" / "episodes").rglob("ep_old.md"))
    assert arch


def test_extract_secret_blocked(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    # Episode body must not be rejected by session-end; put secret only in candidate text
    # written directly for extract unit path
    from agent_memory.commands import session_end as se

    # clean episode first
    eid = se.run_session_end(
        root,
        title="clean",
        body="CANDIDATE: fact | 5 | _ | normal-text-only\n",
    )["episode_id"]
    # overwrite episode body with secret candidate (bypass session-end gate for this unit)
    from agent_memory.resolve import resolve_id

    got = resolve_id(root, eid)
    assert got
    write_text_atomic(
        got.path,
        dump(got.meta, f"CANDIDATE: fact | 5 | _ | {AC8_SECRET_FIXTURE}\n"),
    )
    import pytest
    from agent_memory.errors import ConflictError

    with pytest.raises(ConflictError):
        extract.run_extract(root, eid, mode="fixture")
    for p in (root / "staging" / "candidates").glob("*.md"):
        assert AC8_SECRET_FIXTURE not in p.read_text(encoding="utf-8")


def test_cli_extract_json(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = _episode_with_body(root, "CANDIDATE: fact | 5 | _ | hello-extract\n")
    assert (
        main(
            [
                "--root",
                str(root),
                "--json",
                "extract",
                "--from",
                eid,
                "--mode",
                "fixture",
            ]
        )
        == 0
    )
