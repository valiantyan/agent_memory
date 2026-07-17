# Reference integration (L-Ref)

How to attach **agent-memory** to any coding agent without vendor lock-in.

Related: root `PROTOCOL.md`, `docs/demo/AC1_script.md`, `scripts/demo_ac1.sh`.

**中文完整版：** [`docs/接入指南.md`](接入指南.md) · [`docs/使用手册.md`](使用手册.md) · 根目录 [`README.md`](../README.md)。

---

## 1. Prerequisites

```bash
pip install -e "/path/to/this/repo[dev]"   # provides `agent-memory` on PATH
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"   # or your custom data root
export PATH="/path/to/this/repo/.venv/bin:$PATH"  # if not installed globally
agent-memory init    # once
```

Agents need:

1. Ability to run shell commands (`agent-memory …`), **or**  
2. Ability to read/write files under `$AGENT_MEMORY_ROOT` **and** still prefer CLI for writes (gates).

**Sandbox / workspace-write tools (Codex, some Cursor modes):** if the memory root is **outside** the project workspace, **read** commands (`context`, `search`, `get`, `recent`, `doctor`, `project-detect`) work; **write** commands (`checkpoint`, `remember`, `handoff`, `session-end`, `gc`, …) need escalated permissions or `writable_roots` that include `$AGENT_MEMORY_ROOT`. Prefer exporting `AGENT_MEMORY_ROOT` in the agent environment so bare commands work without per-call `--root`.

**`--root` placement:** global option; may appear **before or after** the subcommand (CLI ≥1.0.1). Preferred:

```bash
agent-memory --root "$AGENT_MEMORY_ROOT" context --query "..."
# also accepted:
agent-memory context --query "..." --root "$AGENT_MEMORY_ROOT"
```

---

## 2. Paste block (AGENTS.md / system rules / Cursor rules)

Copy the following into the agent’s standing instructions (adjust root path if needed):

```markdown
## Shared memory (agent-memory)

You share a pure-file memory store with other tools.

- Root: `$AGENT_MEMORY_ROOT` (default `~/.agent-memory`)
- Full contract: read `PROTOCOL.md` in that root (or the package repo `PROTOCOL.md`)
- Prefer CLI over hand-editing files.
- CLI on PATH or use absolute path to the binary.
- If env is unset: pass `--root <absolute data root>` (before or after subcommand).

### Every session start
Run:
```bash
agent-memory context --query "<short keywords from the user message>"
# without env:
# agent-memory --root "$AGENT_MEMORY_ROOT" context --query "..."
```
Use T0 + Working + Semantic sections. If Semantic is empty, do **not** invent prior facts.

### During work
- Every ~8 user messages:  
  `agent-memory checkpoint --goal "..." --next-steps "- ..."`
- On clear decisions / green tests / before switching tools:  
  `agent-memory checkpoint` and/or `agent-memory handoff --goal "..." --next-steps "- ..."`
- Writes need permission to the memory root when it is outside the workspace sandbox.

### Explicit remember / forget
- User says 记住 / always:  
  `agent-memory remember --slot <stable-slot> --content "..."`
- User says 忘掉:  
  `agent-memory forget <id>` (use `recent` or `search` to find id)
- `recent` is **read-only** (safe under sandbox); pruning is `gc`.

### Project conventions
```bash
agent-memory checkpoint --project-id <id> --goal "..."
agent-memory remember --slot <slot> --content "..." --project <id>
```
Do not apply project A conventions when working on project B.

### Session end / tool switch
```bash
agent-memory session-end --title "..." --body "intent / actions / outcome / lessons"
agent-memory extract --from <episode_id> --mode rules
agent-memory handoff --goal "..." --next-steps "- STEP1"
```

### Never
- Store API keys, tokens, PEM private keys, cookies
- Dump full chat transcripts as semantic memory
- Claim “memory says X” without a context/search hit
- Label guesses as user_explicit
```

---

## 3. Tool-specific notes

| Tool | Suggestion |
|------|------------|
| Claude Code | Project or user `CLAUDE.md` / skill pointing at PROTOCOL + paste block |
| Cursor | User Rules or `.cursorrules` with paste block |
| Codex | `AGENTS.md` with paste block; allow write to memory root (or escalate) for checkpoint/handoff |
| Grok / others | System prompt or skill file with paste block |

Do **not** remove project `AGENTS.md` / README conventions; memory **coexists** (FA-3).

---

## 4. Minimal smoke checklist (after paste)

1. `agent-memory context` prints `## T0`  
2. `agent-memory checkpoint --goal "smoke"` then `context` shows goal  
3. `agent-memory handoff --goal "G1" --next-steps "- next"` creates `working/handoff-*.md`  
4. New session: `context` or `get` handoff id recovers goal/next  
5. `agent-memory recent` works **without** write permission to the root  

Automated L-Core subset: `bash scripts/demo_ac1.sh`

---

## 5. Troubleshooting

| Symptom | Action |
|---------|--------|
| `no schema_version` | `agent-memory init` or wrong root (export `AGENT_MEMORY_ROOT` / pass `--root`) |
| `unrecognized arguments: --root` | Upgrade CLI ≥1.0.1, or put `--root` **before** the subcommand |
| `Operation not permitted` / sandbox write fail | Escalate shell for write cmds, or add memory root to writable roots; `recent`/`context` should not need write |
| `agent-memory: command not found` | Use absolute path to `.venv/bin/agent-memory` or fix PATH |
| project write denied | `checkpoint --project-id X` or marker file / correct cwd |
| secret blocked | remove keys; never use `--force` for secrets |
| stale INDEX | `agent-memory reindex` then `doctor` |
