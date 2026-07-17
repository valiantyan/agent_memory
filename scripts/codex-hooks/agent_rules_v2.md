# Shared memory (agent-memory v2.0.2) — user/global rules

Install with: `bash scripts/install_codex_hooks.sh --project /path/to/repo`  
(Recommended: **project triggers only** — avoids double-firing with global hooks.)  
**You do not need to edit business-repo AGENTS.md** for core memory to work.

## Paths

- Memory data root: `$AGENT_MEMORY_ROOT` (only place durable memory is stored)
- CLI: `agent-memory` on PATH
- Multi tasks: `working/items/` + `working/focus.json`; `working/current.md` = **focus mirror only**

## Answering「当前任务」/ what are we doing (priority)

1. **Open intent** (if present and newer/conflicts with Working) — lead with this  
2. Else **focused Working** goal (`working/current.md` / focus item)  
3. Mention **other active work items** as parallel (not erased)  
4. Never answer with only a stale Working goal when Open intent is clearly the user request  

## Every session start

Prefer injected SessionStart context. If missing:

```bash
agent-memory context --query "<short keywords from the user>"
```

Do not invent “memory says …” without a hit.

## UserPrompt (automatic L0)

Hooks log `meta/events.jsonl` and task-like **intent-draft**.  
That is **not** formal Working — promote with `turn` / `checkpoint`.

## End of each user turn with real work

```bash
agent-memory turn --goal "<one line>" --next-steps $'- step1\n- step2' --cwd .
```

Stop promotes pending → checkpoint → **upserts work item** (siblings kept) + updates focus/`current.md`.

## Parallel tasks (same project, multiple sessions)

- Second task must **not erase** the first: use different goals → different `working/items/wi_*.md`  
- Switch focus without delete:

```bash
agent-memory work list
agent-memory work focus --id wi_...
```

- Or checkpoint with explicit `--item-id` for stable ids

## Context ~70% / new window

```bash
agent-memory checkpoint --goal "..." --next-steps "..." --project-id <id>
agent-memory handoff --goal "..." --next-steps "..." --project-id <id>
```

## Explicit remember / forget

```bash
agent-memory remember --slot <stable> --content "..."
agent-memory forget <id>
```

## Never

- Store secrets/tokens/keys  
- Dump full chat as semantic memory  
- Write durable memory into the business git tree  
- Install **both** global and project SessionStart/Stop/UserPrompt (double-fire)  
