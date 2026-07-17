"""PR-9: PROTOCOL / L-Ref docs / AC-1 demo consistency."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from agent_memory.cli import main
from agent_memory.templates import PROTOCOL_MD

REPO = Path(__file__).resolve().parents[1]

FA2 = [
    "init",
    "doctor",
    "reindex",
    "context",
    "search",
    "get",
    "checkpoint",
    "turn",
    "handoff",
    "session-end",
    "extract",
    "remember",
    "forget",
    "reject",
    "promote",
    "recent",
    "gc",
    "project-detect",
]

def test_repo_protocol_exists_and_has_obligations():
    p = REPO / "PROTOCOL.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "context" in text
    assert re.search(r"N\s*=\s*8", text), "PROTOCOL must state N=8 checkpoint cadence"
    assert "checkpoint" in text
    assert "handoff" in text
    assert "session-end" in text
    assert "user_explicit" in text
    assert "secret" in text.lower()
    assert re.search(r"[Ss]ingle working", text)
    for cmd in FA2:
        assert cmd in text, f"PROTOCOL missing FA-2 command {cmd}"


def test_init_protocol_copy_has_seven_obligations(tmp_path):
    root = tmp_path / "mem"
    assert main(["--root", str(root), "init"]) == 0
    text = (root / "PROTOCOL.md").read_text(encoding="utf-8")
    # numbered obligations 1-7
    for i in range(1, 8):
        assert re.search(rf"^{i}\.", text, re.M), f"missing obligation {i}"
    assert "N=8" in text or "N = 8" in text or "Every N=8" in text
    # v2 adds obligation 8 in package PROTOCOL; init template includes v2 boundary
    assert "AGENT_MEMORY_ROOT" in text or "memory root" in text.lower()


def test_template_protocol_matches_fa2():
    for cmd in FA2:
        assert cmd in PROTOCOL_MD


def test_reference_integration_exists():
    p = REPO / "docs" / "REFERENCE_INTEGRATION.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "agent-memory context" in text
    assert "remember" in text
    assert "handoff" in text
    assert "AGENTS.md" in text or "paste" in text.lower()


def test_ac1_script_marks():
    p = REPO / "docs" / "demo" / "AC1_script.md"
    assert p.is_file()
    text = p.read_text(encoding="utf-8")
    assert "G1MARK" in text
    assert "STEP1MARK" in text
    assert "L-Core" in text
    assert "L-Ref" in text
    assert "Part B" in text


def test_demo_ac1_sh_pass():
    script = REPO / "scripts" / "demo_ac1.sh"
    assert script.is_file()
    # ensure executable bit not strictly required; bash it
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "PASS" in proc.stdout
    assert "G1MARK" in proc.stdout or "handoff" in proc.stdout.lower()
