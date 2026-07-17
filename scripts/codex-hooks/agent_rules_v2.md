# Shared memory (agent-memory v2.0.3) — user/global rules

Install: `bash scripts/install_codex_hooks.sh --project /path/to/repo`  
(Project triggers only by default — no global double-fire.)

## Paths

- Data: `$AGENT_MEMORY_ROOT` only  
- Multi tasks: `working/items/` + `focus.json`; `current.md` = focus mirror  
- Per-session intents: `meta/intent-draft/<project>__sess_<session>.json`

## 当前任务 / what are we doing

1. List **all** open/interrupted intents (each session)  
2. Focused Working goal  
3. **All** other active work items (parallel, not erased)  
Never answer with only a stale single Working goal when multiple lines exist.

## UserPrompt (automatic)

Hooks write: event (+ session_id) → session intent-draft → auto work item (**set_focus=false**).

## End of turn with real work

```bash
agent-memory turn --goal "<one line>" --next-steps $'- s1\n- s2' --cwd . --session-id "<if known>"
```

Stop promotes pending → checkpoint (item + focus) → clears **this session's** intent only.

## Parallel sessions

- Different goals → different `wi_*` items (auto or turn)  
- `agent-memory work list` / `work focus --id …`  
- Never expect second session to erase the first

## Never

- Secrets in memory  
- Full chat as semantic  
- Durable data in business git tree  
- Global + project double hooks  
