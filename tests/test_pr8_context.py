"""PR-8: context wire format, AC-T0, budgets, FM-4."""

from __future__ import annotations

from pathlib import Path

from agent_memory.cli import main
from agent_memory.commands import context_cmd, remember
from agent_memory.commands.context_cmd import parse_t0_section
from agent_memory.config import SEMANTIC_DETAILS_BUDGET, T0_BUDGET


def _init(root: Path) -> None:
    assert main(["--root", str(root), "init"]) == 0


def test_ac_t0_mark_in_section(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    t0 = root / "profile" / "me.T0.md"
    t0.write_text(
        t0.read_text(encoding="utf-8") + "\nT0MARK unique marker\n",
        encoding="utf-8",
    )
    out = context_cmd.run_context(root)
    assert out.startswith("## T0\n")
    t0_body = parse_t0_section(out)
    assert "T0MARK" in t0_body
    assert len(t0_body) <= T0_BUDGET
    assert "## Semantic (top_k=" in out


def test_t0_truncation(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    big = "字" * (T0_BUDGET + 500)
    (root / "profile" / "me.T0.md").write_text(big, encoding="utf-8")
    out = context_cmd.run_context(root)
    t0_body = parse_t0_section(out)
    assert len(t0_body) <= T0_BUDGET
    assert "…[truncated]" in t0_body


def test_working_section_present_after_checkpoint(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    main(["--root", str(root), "checkpoint", "--goal", "G2MARK"])
    out = context_cmd.run_context(root)
    assert "## Working" in out
    assert "G2MARK" in out


def test_semantic_hits_and_empty_section(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    remember.run_remember(root, slot="a", content="ALPHA_UNIQUE_TOKEN")
    out = context_cmd.run_context(root, query="ALPHA_UNIQUE_TOKEN")
    assert "## Semantic (top_k=5)" in out
    assert "### " in out
    assert "ALPHA_UNIQUE_TOKEN" in out

    out2 = context_cmd.run_context(root, query="ZZZNOMATCH999")
    assert "## Semantic (top_k=5)" in out2
    # no ### hits
    assert "### " not in out2


def test_semantic_body_budget(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    # one huge memory body
    body = "B" * (SEMANTIC_DETAILS_BUDGET + 2000)
    remember.run_remember(root, slot="huge", content=body)
    out = context_cmd.run_context(root, query="huge")
    # extract bodies under ### lines
    import re

    bodies = re.findall(r"(?ms)^### .+\n(.*?)(?=^### |^## |\Z)", out)
    total = sum(len(b.rstrip("\n")) for b in bodies)
    assert total <= SEMANTIC_DETAILS_BUDGET
    assert "…[truncated]" in out


def test_include_staging_section(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.frontmatter import dump
    from agent_memory.io_atomic import write_text_atomic

    p = root / "staging" / "candidates" / "sem_st.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        p,
        dump(
            {
                "id": "sem_st",
                "type": "semantic",
                "status": "candidate",
                "scope": "global",
                "one_liner": "staged",
                "content_kind": "fact",
                "importance": 5,
                "source": {"kind": "extracted"},
                "created_at": "2026-07-01T00:00:00+00:00",
                "schema_version": "1.0.0",
            },
            "STAGING_BODY_MARK",
        ),
    )
    out_default = context_cmd.run_context(root)
    assert "## Staging" not in out_default
    out = context_cmd.run_context(root, include_staging=True)
    assert "## Staging (candidates)" in out
    assert "STAGING_BODY_MARK" in out or "sem_st" in out


def test_context_runs_lazy_expiry(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    from agent_memory.commands import context_cmd as cc

    calls = []
    orig = cc.run_lazy_expiry

    def wrap(r):
        calls.append(1)
        return orig(r)

    cc.run_lazy_expiry = wrap  # type: ignore[assignment]
    try:
        context_cmd.run_context(root)
    finally:
        cc.run_lazy_expiry = orig  # type: ignore[assignment]
    assert calls == [1]


def test_cli_context(tmp_path):
    root = tmp_path / "mem"
    _init(root)
    assert main(["--root", str(root), "context"]) == 0
    assert main(["--root", str(root), "context", "--query", "x", "--top-k", "3"]) == 0


def test_fa2_surface_complete():
    """PR-8 completes FA-2: context no longer stub."""
    from agent_memory.cli import build_parser

    p = build_parser()
    # ensure context subparser has query
    # parse should work
    ns = p.parse_args(["context", "--query", "hi"])
    assert ns.command == "context"
