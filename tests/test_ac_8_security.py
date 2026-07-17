"""AC-8 + security module (PR-3). Writers not landed yet — gate CLI surface via library."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_memory.cli import main
from agent_memory.commands.init import run_init
from agent_memory.errors import SecurityError, UsageError
from agent_memory.frontmatter import dump
from agent_memory.index import doctor_check
from agent_memory.io_atomic import write_text_atomic
from agent_memory.security import (
    AC8_SECRET_FIXTURE,
    assert_content_allowed,
    assert_episode_body_len,
    assert_no_secrets,
    assert_one_liner_len,
    assert_source_for_active,
    find_secrets,
    gate_write_payload,
)


FIXTURES = Path(__file__).parent / "fixtures" / "secrets"


def test_ac8_fixture_string_blocked():
    assert find_secrets(AC8_SECRET_FIXTURE)
    with pytest.raises(SecurityError, match="secret"):
        assert_no_secrets(AC8_SECRET_FIXTURE)


def test_ac8_fixture_file_blocked():
    text = (FIXTURES / "ac8_fixture.txt").read_text(encoding="utf-8")
    with pytest.raises(SecurityError):
        assert_content_allowed(text)


def test_secret_patterns_table():
    samples = {
        "S-API-KEY-ASSIGN": "api_key=abc123xyz",
        "S-SK-PREFIX": "token sk-abcdefghijklmnop",
        "S-BEARER": "Authorization: Bearer abcdefghijklmnop",
        "S-PEM-KEY": "-----BEGIN RSA PRIVATE KEY-----\nxx",
        "S-AWS-KEY": "AKIAIOSFODNN7EXAMPLE",
        "S-GENERIC-TOKEN": "xoxb-1234567890-abcdefghij",
    }
    for pid, sample in samples.items():
        hits = find_secrets(sample)
        assert any(h.pattern_id == pid for h in hits), f"expected {pid} in {hits}"


def test_secrets_cannot_force():
    with pytest.raises(SecurityError, match="cannot bypass secrets"):
        assert_content_allowed(AC8_SECRET_FIXTURE, force=True)


def test_pem_fixture_file():
    text = (FIXTURES / "pem_sample.txt").read_text(encoding="utf-8")
    assert any(h.pattern_id == "S-PEM-KEY" for h in find_secrets(text))
    with pytest.raises(SecurityError):
        assert_no_secrets(text)


def test_pii_requires_force_then_warns():
    # synthetic CN ID-shaped string (format only)
    cn = "110101199001011234"
    with pytest.raises(SecurityError, match="sensitive"):
        assert_content_allowed(cn, force=False)
    warns = assert_content_allowed(cn, force=True)
    assert any("forcing" in w for w in warns)


def test_source_ban_tool_output_and_web():
    with pytest.raises(SecurityError, match="tool_output"):
        assert_source_for_active("tool_output")
    with pytest.raises(SecurityError, match="web"):
        assert_source_for_active("web")
    assert_source_for_active("user_explicit")
    assert_source_for_active("extracted")
    assert_source_for_active("handoff")


def test_source_unknown():
    with pytest.raises(UsageError):
        from agent_memory.security import assert_source_known

        assert_source_known("alien")


def test_episode_body_limit():
    body = "x" * 8001
    with pytest.raises(SecurityError, match="8000"):
        assert_episode_body_len(body)
    assert_episode_body_len("x" * 8000)


def test_one_liner_limit():
    with pytest.raises(SecurityError, match="one_liner"):
        assert_one_liner_len("字" * 81)
    assert_one_liner_len("字" * 80)


def test_gate_write_payload_combines():
    with pytest.raises(SecurityError):
        gate_write_payload(
            "ok text",
            AC8_SECRET_FIXTURE,
            for_active=True,
            source_kind="user_explicit",
        )
    with pytest.raises(SecurityError):
        gate_write_payload(
            "clean",
            for_active=True,
            source_kind="tool_output",
        )
    warns = gate_write_payload(
        "clean preference",
        for_active=True,
        source_kind="user_explicit",
        one_liner="short",
    )
    assert warns == []


def test_doctor_flags_secret_in_store(tmp_path):
    root = tmp_path / "mem"
    run_init(root)
    path = root / "scopes" / "global" / "semantic" / "sem_bad.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(
        path,
        dump(
            {
                "id": "sem_bad",
                "type": "semantic",
                "status": "active",
                "scope": "global",
                "content_kind": "fact",
                "one_liner": "leak",
            },
            f"note {AC8_SECRET_FIXTURE}\n",
        ),
    )
    findings = doctor_check(root)
    assert any(f.code == "secret_in_store" for f in findings)
    assert main(["--root", str(root), "doctor"]) == 1


def test_clean_text_ok():
    assert_content_allowed("喜欢橘子；使用 MockK 做单元测试。")
