# Agent Memory PROTOCOL (L-Protocol)

| Item | Value |
|------|-------|
| Schema | `1.0.0` |
| Requirements | REQ-AGENT-MEMORY v1.2 Frozen |
| Design | DESIGN-AGENT-MEMORY v0.3 Frozen |
| Audience | Any agent (Claude / Cursor / Codex / Grok / Kimi / …) and humans |

This document is the **behavioral contract** for multi-agent shared memory.  
The CLI (`agent-memory`) is **L-Core** (deterministic, tested without LLM).  
This PROTOCOL is **L-Protocol** (agents should follow; models may still slip).

---

## 1. Compliance levels (do not confuse)

| Level | Meaning | Who guarantees |
|-------|---------|----------------|
| **L-Core** | CLI + file rules | This package (pytest) |
| **L-Protocol** | When to call CLI / what not to invent | Agent rules + model |
| **L-Ref** | One reference paste block + AC-1 demo | Docs under `docs/` |

**Never** treat “agent forgot to checkpoint” as a CLI bug.  
**Do** treat failed CLI gates (secrets, project scope, quotas) as L-Core failures.

---

## 2. Root and environment

```bash
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"   # default if unset
# or: agent-memory --root /path/to/store <cmd>
```

- One **shared** root for all agents on this machine.
- **Single active working** file: `working/current.md` (v1).
- Copy the whole directory to migrate (AC-7). No git sync product in v1.

---

## 3. Mandatory agent obligations (REQ §7.12)

1. **Start of session**: run `agent-memory context` (or equivalent: read T0 + working + search). SessionStart hooks may inject this.  
2. **Every N = 8 user messages** (or each turn with real work): update task state via `agent-memory turn` (pending under memory root) and/or `agent-memory checkpoint`.  
3. **Milestones or tool switch / context ~70%**: `agent-memory handoff` and/or `session-end` (and checkpoint) before a new window.  
3b. **v2.0.1 L0**: UserPrompt hooks may log `meta/events.jsonl` + task-like `meta/intent-draft/` (not formal Working). Promote with `turn`. Stop without pending marks intent **interrupted**, does not invent goals.  
3c. **v2.0.2 multi-task**: `checkpoint` upserts `working/items/<id>.md` and sets focus; **does not delete** other items. Answer 当前任务: Open intent > focused Working > other items. Install with `--project` strips global agent-memory triggers by default (no double-fire).  

4. **No retrieval hit**: do **not** invent “memory says …”.  
5. Do **not** label model inferences as `user_explicit` / do not use `remember` for guesses.  
6. **Never** write secrets, API keys, tokens, cookies, private keys into the memory root.  
7. **Single working**: before switching tasks, `handoff` or `session-end` first.  
8. **v2 data boundary**: durable memory **only** under `AGENT_MEMORY_ROOT` (not business-repo trees).

### Milestones (also call checkpoint)

- A clear technical decision was made  
- A runnable milestone completed (tests green, feature closed)  
- About to switch agent, window, or project  

**L-Core does not parse chat streams.** Agents must count turns / recognize milestones themselves.

---

## 4. Command list (v1 FA-2 + v2 `turn`)

| Command | Purpose |
|---------|---------|
| `init` | Create empty legal store |
| `doctor` | Health / INDEX / secret scan |
| `reindex` | Rebuild INDEX from bodies |
| `context` | Pack T0 + working + semantic details |
| `search` | L0 hierarchical search |
| `get` | Load one memory by id |
| `checkpoint` | Update working |
| `turn` | **v2** Write pending turn under `meta/pending-turn/` (Stop hooks consume) |
| `event` | **v2.0.1** L0 audit to `meta/events.jsonl`; optional intent-draft / interrupt |
| `work` | **v2.0.2** list / focus / upsert multi work-items under `working/items/` |
| `handoff` | Snapshot for another agent |
| `session-end` | One episode summary + touch working |
| `extract` | Episode → staging / procedural candidates |
| `remember` | Immediate active semantic (`--slot` required) |
| `forget` | Soft or `--hard` delete |
| `reject` | Candidate never auto-promotes |
| `promote` | Candidate → active |
| `recent` | Recent writes (**read-only**; on-disk prune via `gc`) |
| `gc` | Lazy expiry + archive + prune recent log |
| `project-detect` | Project id + confidence |

Root selection: `AGENT_MEMORY_ROOT`, or `--root` **before or after** the subcommand (CLI ≥1.0.1).

**v2 integration:** install Codex hooks + optional user rules; **do not require** editing business-repo `AGENTS.md`. Durable data never lives in the business tree.

Optional later: `dream`, `touch`.

---

## 5. Read path (typical turn)

```bash
agent-memory context --query "<user topic keywords>"
# or with explicit root (either position):
# agent-memory --root "$AGENT_MEMORY_ROOT" context --query "..."
# agent-memory context --query "..." --root "$AGENT_MEMORY_ROOT"
# or: context without query (recency-ranked semantic top_k)
```

Wire format (stable for parsers):

```text
## T0
...
## Working
...
## Semantic (top_k=N)
### <id> — <one_liner>
<body>
```

Rules:

- Default search/context **excludes** `staging/`, `history/`, `archive/`.  
- Scope = `global` ∪ current project (working / detect / `--project`).  
- Empty hits → say you have no memory hit; do not fabricate.

---

## 6. Write path (typical session end)

```bash
# Per-turn essence (v2; lives under memory root only)
agent-memory turn --goal "..." --next-steps "- ..." --cwd .
# Stop hook → checkpoint from meta/pending-turn/

# Or direct working update
agent-memory checkpoint --goal "..." --next-steps "- ..."
agent-memory session-end --title "..." --body "..."
agent-memory extract --from <episode_id> --mode rules   # or fixture in tests
agent-memory handoff --goal "..." --next-steps "- STEP1"
```

### Remember vs extract

| Intent | Command |
|--------|---------|
| User said “记住 / always …” | `remember --slot <slot> --content "..."` |
| Distill from episode | `extract` → candidates → `promote` / `reject` |
| How-to playbook | procedural candidate; promote only with `--user-confirmed` or ≥2 episodes |

### Project isolation

```bash
agent-memory checkpoint --project-id my-app --goal "..."
agent-memory remember --slot test --content "use MockK" --project my-app
```

Writes to `project:X` require **high confidence** and **matching** effective project (working id or detect). Global always allowed.

---

## 7. Security (agents + CLI)

- CLI **rejects** secret patterns (e.g. `api_key=…`, `sk-…`, PEM keys). **`--force` cannot bypass secrets.**  
- Do not paste full chat logs as semantic memory.  
- Prefer CLI over hand-editing files; if you edit files, run `doctor` / `reindex`.  
- `tool_output` / `web` sources must not become **active** facts.

---

## 8. Product limits (honest)

- Killing a process **without** checkpoint may lose the last turns.  
- Arbitrary commercial agents are **not** forced to obey this protocol.  
- Keyword search is hierarchical L0, not a vector DB.  
- Single `working/current.md` — two agents editing it may clobber each other.

---

## 9. Quick install

```bash
cd /path/to/repo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export AGENT_MEMORY_ROOT="$HOME/.agent-memory"
agent-memory init
agent-memory context
```

See also:

- `docs/REFERENCE_INTEGRATION.md` — paste blocks for AGENTS.md / system prompts  
- `docs/demo/AC1_script.md` — L-Ref handoff demo  
- `scripts/demo_ac1.sh` — automated L-Core subset of AC-1  

---

## 10. Obligation checklist (for agents)

- [ ] Called `context` (or equivalent) at session start  
- [ ] Checkpointed every ~8 user turns  
- [ ] Handoff / session-end before tool switch  
- [ ] Did not invent memory on empty search  
- [ ] Did not store secrets  
- [ ] Used `remember` only for explicit user durable facts  
- [ ] Single-task working discipline  
