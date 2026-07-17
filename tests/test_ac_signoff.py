"""
PR-10: Consolidated L-Core acceptance suite (REQUIREMENTS §10.2).

Each test name maps to an AC-*. Prefer CLI where possible.
L-Ref Part B (human agent) is documented in docs/demo/AC1_script.md — not automated here.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import (
    context_cmd,
    extract,
    promote,
    reject,
    remember,
    search_cmd,
    session_end,
)
from agent_memory.commands.context_cmd import parse_t0_section
from agent_memory.config import SEMANTIC_DETAILS_BUDGET, T0_BUDGET
from agent_memory.expiry import run_lazy_expiry
from agent_memory.frontmatter import dump, parse as parse_fm
from agent_memory.index import load_semantic_index, parse_semantic_index
from agent_memory.io_atomic import write_text_atomic
from agent_memory.security import AC8_SECRET_FIXTURE
from agent_memory.working import load_working


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


# --- AC-1 L-Core subset ---


def test_ac1_lcore_handoff_context_marks(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert (
        main(
            [
                "--root",
                str(root),
                "handoff",
                "--goal",
                "G1MARK task",
                "--next-steps",
                "- STEP1MARK do next",
            ]
        )
        == 0
    )
    hands = list((root / "working").glob("handoff-*.md"))
    assert hands
    text = hands[0].read_text(encoding="utf-8")
    assert "G1MARK" in text and "STEP1MARK" in text
    ctx = context_cmd.run_context(root)
    assert "G1MARK" in ctx and "STEP1MARK" in ctx
    assert main(["--root", str(root), "get", "working_current"]) == 0


# --- AC-T0 ---


def test_ac_t0(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    t0 = root / "profile" / "me.T0.md"
    t0.write_text(t0.read_text(encoding="utf-8") + "\nT0MARK\n", encoding="utf-8")
    out = context_cmd.run_context(root)
    body = parse_t0_section(out)
    assert "T0MARK" in body
    assert len(body) <= T0_BUDGET


# --- AC-2 ---


def test_ac2_project_isolation(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    main(
        [
            "--root",
            str(root),
            "checkpoint",
            "--project-id",
            "app-a",
            "--goal",
            "A",
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
    ta = search_cmd.run_search(root, "MOCK_A_ONLY", project="app-a")
    tb = search_cmd.run_search(root, "MOCK_A_ONLY", project="app-b")
    assert "MOCK_A_ONLY" in ta
    assert "MOCK_A_ONLY" not in tb


# --- AC-3 ---


def test_ac3_preference_unique(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    remember.run_remember(root, slot="fruit", content="喜欢苹果")
    remember.run_remember(root, slot="fruit", content="喜欢橘子")
    cur = search_cmd.run_search(root, "喜欢橘子")
    assert "喜欢橘子" in cur
    old = search_cmd.run_search(root, "喜欢苹果")
    assert "喜欢苹果" not in old or "(no hits)" in old


# --- AC-4 ---


def test_ac4_checkpoint(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    meta0, _ = load_working(root)
    t0 = meta0.get("updated_at")
    assert main(["--root", str(root), "checkpoint", "--goal", "G2MARK"]) == 0
    meta, body = load_working(root)
    assert meta.get("goal") == "G2MARK"
    assert "G2MARK" in body
    assert meta.get("updated_at") != t0


# --- AC-5 ---


def test_ac5_forget_recent(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    r = remember.run_remember(root, slot="k", content="VISIBLE_RECENT")
    mid = r["id"]
    from agent_memory.commands import recent_cmd

    rec = recent_cmd.run_recent(root)
    assert mid in rec
    assert main(["--root", str(root), "forget", mid]) == 0
    assert mid not in search_cmd.run_search(root, "VISIBLE_RECENT")
    assert main(["--root", str(root), "get", mid]) == 0  # soft still gettable


# --- AC-6 ---


def test_ac6_topk_budget_empty(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert "(no hits)" in search_cmd.run_search(root, "nothing-xyz")
    for i in range(6):
        remember.run_remember(root, slot=f"s{i}", content=f"TOKENMARK item{i}")
    text = search_cmd.run_search(root, "TOKENMARK", top_k=5)
    assert text.count("id: ") <= 5
    huge = "Z" * (SEMANTIC_DETAILS_BUDGET + 1000)
    remember.run_remember(root, slot="huge", content=huge)
    ctx = context_cmd.run_context(root, query="huge")
    import re

    bodies = re.findall(r"(?ms)^### .+\n(.*?)(?=^### |^## |\Z)", ctx)
    total = sum(len(b.rstrip("\n")) for b in bodies)
    assert total <= SEMANTIC_DETAILS_BUDGET


# --- AC-7 ---


def test_ac7_portable(tmp_path):
    root = tmp_path / "a"
    _init(root)
    remember.run_remember(root, slot="p", content="PORT_MARK")
    dest = tmp_path / "b"
    shutil.copytree(root, dest)
    assert "PORT_MARK" in search_cmd.run_search(dest, "PORT_MARK")


# --- AC-8 ---


def test_ac8_security_trio(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "x",
                "--content",
                AC8_SECRET_FIXTURE,
            ]
        )
        == 4
    )
    assert load_semantic_index(root) == []
    assert (
        main(
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
        == 4
    )
    recent = datetime.now().astimezone().isoformat(timespec="seconds")
    p = root / "staging" / "candidates" / "sem_to.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p,
        dump(
            {
                "id": "sem_to",
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
    assert main(["--root", str(root), "promote", "sem_to"]) == 4


# --- AC-9 ---


def test_ac9_expiry_reject(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    old = (datetime.now().astimezone() - timedelta(days=6)).isoformat(timespec="seconds")
    for mid, imp in (("sem_hi", 8), ("sem_lo", 4)):
        write_text_atomic(
            root / "staging" / "candidates" / f"{mid}.md",
            dump(
                {
                    "id": mid,
                    "type": "semantic",
                    "status": "candidate",
                    "scope": "global",
                    "content_kind": "preference" if imp >= 7 else "fact",
                    "one_liner": mid,
                    "importance": imp,
                    "source": {"kind": "extracted"},
                    "created_at": old,
                    "schema_version": "1.0.0",
                },
                f"body {mid}",
            ),
        )
    assert main(["--root", str(root), "gc"]) == 0
    ids = {r.id for r in load_semantic_index(root)}
    assert "sem_hi" in ids
    assert "sem_lo" not in ids

    write_text_atomic(
        root / "staging" / "candidates" / "sem_rj.md",
        dump(
            {
                "id": "sem_rj",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "content_kind": "preference",
                "one_liner": "rj",
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
    assert "sem_rj" not in {r.id for r in load_semantic_index(root)}


# --- AC-10 ---


def test_ac10_low_conf_project_write(tmp_path, monkeypatch):
    root = tmp_path / "mem"
    _init(root)
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    assert (
        main(
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
        == 0
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "remember",
                "--slot",
                "t",
                "--content",
                "x",
                "--project",
                "nope",
            ]
        )
        == 5
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "session-end",
                "--title",
                "ok",
                "--body",
                "episode ok",
            ]
        )
        == 0
    )


# --- AC-11 covered in test_ac_11_index_atomic.py; re-assert parse ---


def test_ac11_index_still_parseable_after_writes(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    for i in range(5):
        remember.run_remember(root, slot=f"i{i}", content=f"c{i}")
    text = (root / "INDEX.semantic.md").read_text(encoding="utf-8")
    rows = parse_semantic_index(text)
    assert len(rows) == 5
    for line in text.splitlines():
        st = line.strip()
        if st.startswith("|") and "one_liner" not in st and not st.startswith("|----"):
            if st.lower().startswith("| id |"):
                continue
            assert st.endswith("|")


# --- AC-P ---


def test_ac_p_procedural(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = session_end.run_session_end(
        root,
        title="p",
        body="CANDIDATE: type=procedural | other | 5 | _ | runbook steps\n",
    )["episode_id"]
    extract.run_extract(root, eid, mode="fixture")
    assert list((root / "procedural" / "active").glob("*.md")) == []
    cands = list((root / "procedural" / "candidates").glob("*.md"))
    mid = parse_fm(cands[0].read_text(encoding="utf-8"))[0]["id"]
    assert main(["--root", str(root), "promote", mid]) == 2
    assert main(["--root", str(root), "promote", mid, "--user-confirmed"]) == 0
    assert (root / "procedural" / "active" / f"{mid}.md").is_file()


# --- AC-X ---


def test_ac_x_extract(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    eid = session_end.run_session_end(
        root,
        title="x",
        body="CANDIDATE: fact | 5 | _ | EXTRACT_ONLY_MARK\n",
    )["episode_id"]
    r = extract.run_extract(root, eid, mode="fixture")
    assert r["candidates"]
    assert "EXTRACT_ONLY_MARK" not in search_cmd.run_search(root, "EXTRACT_ONLY_MARK")
    assert list((root / "staging" / "candidates").glob("*.md"))


# --- Doctor hardening ---


def test_doctor_ok_after_healthy_store(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    remember.run_remember(root, slot="d", content="doctor-ok")
    assert main(["--root", str(root), "doctor"]) == 0


def test_doctor_fails_on_secret_and_orphan(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    p = root / "scopes" / "global" / "semantic" / "sem_leak.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p,
        dump(
            {
                "id": "sem_leak",
                "type": "semantic",
                "status": "active",
                "scope": "global",
                "content_kind": "fact",
                "one_liner": "leak",
            },
            f"secret {AC8_SECRET_FIXTURE}\n",
        ),
    )
    # orphan + secret
    assert main(["--root", str(root), "doctor"]) == 1
