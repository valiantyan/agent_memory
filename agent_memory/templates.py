"""Built-in templates for init."""

from __future__ import annotations

from agent_memory import SCHEMA_VERSION

EMPTY_INDEX_SEMANTIC = """# INDEX.semantic

| id | type | content_kind | scope | slot | one_liner | path | updated_at |
|----|------|--------------|-------|------|-----------|------|------------|
"""

EMPTY_INDEX_EPISODIC = """# INDEX.episodic

| id | project_id | one_liner | path | created_at |
|----|------------|-----------|------|------------|
"""

T0_TEMPLATE = """# T0 · Hard constraints & collaboration style

## Hard constraints

- Memory root: `$AGENT_MEMORY_ROOT` (default `~/.agent-memory`); obey PROTOCOL.md
- Never store secrets, API keys, tokens, private keys in memory files
- Do not store full chat transcripts as semantic memory
- Default retrieve excludes staging/, history/, archive/

## Style

- Prefer concise answers; state unknowns explicitly
- Do not invent memory when search/context has no hit
"""

WORKING_TEMPLATE = f"""---
id: working_current
type: working
status: active
project_id: null
session_id: null
goal: ""
updated_at: null
schema_version: "{SCHEMA_VERSION}"
---

# Working · CURRENT

## Goal


## Decisions


## Next steps


## Related memory ids


## Open questions

"""

QUOTAS_MD = """# Quotas (informational + doctor)

```text
INDEX.semantic active rows max: 300
Episode body max chars: 8000
one_liner max chars: 80
T0 context budget: 1600
Semantic details in context: 4800
top_k default: 5
Observation days D: 5
Promote importance: >= 7
Episode archive after: 90 natural days
recent retention: 30 natural days
```
"""

PROTOCOL_MD = f"""# Agent Memory PROTOCOL (L-Protocol)

Schema: {SCHEMA_VERSION}

## Compliance levels

- **L-Core**: CLI behavior (deterministic, tested without LLM)
- **L-Protocol**: when agents should call CLI (this document)
- **L-Ref**: reference integration + AC-1 demo (package `docs/REFERENCE_INTEGRATION.md`, `docs/demo/AC1_script.md`)

## Obligations (mandatory)

1. **Start**: run `agent-memory context` (or equivalent: T0 + working + search).
2. **Every N=8 user messages** (or each turn with work): `agent-memory turn` and/or `checkpoint`.
3. **Milestones / tool switch**: `agent-memory handoff` or `session-end`.
4. **No hit**: do not invent “memory says …”.
5. Do not label model inferences as `user_explicit`.
6. Never write secrets, API keys, tokens, private keys into the memory root.
7. **Single working**: only one active task in `working/current.md`; switch tasks via handoff/session-end first.
8. **v2**: durable memory only under `AGENT_MEMORY_ROOT` (not business repos).

## Milestones (also checkpoint)

- Clear technical decision formed
- Runnable milestone completed
- About to switch agent or project

## Security

- Prefer CLI writes (gates). `--force` never bypasses secrets.
- No full chat transcripts as semantic memory.
- `tool_output` / `web` must not become active facts.

## Commands (FA-2 + v2 turn)

`init`, `doctor`, `reindex`, `context`, `search`, `get`, `checkpoint`, `turn`, `handoff`,
`session-end`, `extract`, `remember`, `forget`, `reject`, `promote`, `recent`,
`gc`, `project-detect`

Root: `AGENT_MEMORY_ROOT` or `~/.agent-memory`.

Handoff demo: `scripts/demo_ac1.sh` (L-Core) then Agent B per AC1_script Part B (L-Ref).
"""

README_ROOT = """# Personal Agent Memory Store

This directory is a **pure-file** memory root for multi-agent use.

- Set `AGENT_MEMORY_ROOT` to this path (or use `--root`).
- CLI: `agent-memory` — start with `context` (see **PROTOCOL.md** in this folder).
- Agent paste rules: package `docs/REFERENCE_INTEGRATION.md` / `docs/接入指南.md`.
- Do not store secrets here.
- **All durable data lives only in this folder.** Copy the whole folder to move machines.
- v2: pending turns at `meta/pending-turn/` (not inside business repos).
"""
