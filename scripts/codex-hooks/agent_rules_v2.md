# Shared memory (agent-memory v2.0.1) — user/global rules

Install with: `bash scripts/install_codex_hooks.sh` (writes optional user rules).  
**You do not need to edit business-repo AGENTS.md** for core memory to work.

## Paths

- Memory data root: `$AGENT_MEMORY_ROOT` (only place durable memory is stored)
- CLI: `agent-memory` on PATH, or absolute path from install

## Every session start

Prefer injected SessionStart context (T0 + Working + Open intent + Recent events + Semantic).  
If missing, run:

```bash
agent-memory context --query "<short keywords from the user>"
```

Do not invent “memory says …” without a hit.  
If **Open intent** is present and Working goal looks stale, treat Open intent as the user-requested task until you `turn`/checkpoint.

## UserPrompt (automatic L0)

Hooks may log `meta/events.jsonl` and task-like **intent-draft**.  
That is **not** formal Working — you must still promote essence with `turn`.

## End of each user turn with real work (required)

Real work includes: BUG/fix, implement, multi-step diagnosis, continue/resume after handoff.

```bash
agent-memory turn --goal "<one line>" --next-steps $'- step1\n- step2' --cwd .
```

Codex Stop hook promotes this into `working/` via checkpoint.  
If you skip `turn`, Stop does **not** invent goals (may mark intent interrupted).

## Context ~70% or new window (breakpoint resume)

Before leaving the session:

```bash
agent-memory checkpoint --goal "..." --next-steps "..." --project-id <id>
agent-memory handoff --goal "..." --next-steps "..." --project-id <id>
```

New window: trust injected Working/Open intent + `git status`, continue from next steps.

## Explicit remember / forget

```bash
agent-memory remember --slot <stable> --content "..."
agent-memory forget <id>
```

## Never

- Store secrets/tokens/keys
- Dump full chat as semantic memory
- Write durable memory into the business git tree
- Claim Working was updated when you only saw Open intent / events
