# Shared memory (agent-memory v2) — user/global rules

Install with: `bash scripts/install_codex_hooks.sh` (writes optional user rules).  
**You do not need to edit business-repo AGENTS.md** for core memory to work.

## Paths

- Memory data root: `$AGENT_MEMORY_ROOT` (only place durable memory is stored)
- CLI: `agent-memory` on PATH, or absolute path from install

## Every session start

Prefer injected SessionStart context. If missing, run:

```bash
agent-memory context --query "<short keywords from the user>"
```

Do not invent “memory says …” without a hit.

## End of each user turn (task state)

```bash
agent-memory turn --goal "<one line>" --next-steps $'- step1\n- step2' --cwd .
```

Codex Stop hook promotes this into `working/` via checkpoint.  
If you skip `turn`, Stop is a **no-op** (does not invent goals).

## Explicit remember / forget

```bash
agent-memory remember --slot <stable> --content "..."
agent-memory forget <id>
```

## Never

- Store secrets/tokens/keys
- Dump full chat as semantic memory
- Write durable memory into the business git tree
