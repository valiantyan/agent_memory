# AC-1 demo script (L-Ref + L-Core)

**Goal:** Prove tool-switch continuity via handoff without pasting the full chat.

| Layer | What is proven |
|-------|----------------|
| **L-Core** | Files + CLI produce handoff with `G1MARK` / `STEP1MARK`; `context`/`get` can read them |
| **L-Ref** | A second agent session, following `docs/REFERENCE_INTEGRATION.md`, continues the task |

Automated L-Core subset: `scripts/demo_ac1.sh`

---

## Preconditions

```bash
export AGENT_MEMORY_ROOT="${AGENT_MEMORY_ROOT:-$HOME/.agent-memory-ac1-demo}"
pip install -e ".[dev]"   # from repo root
agent-memory --root "$AGENT_MEMORY_ROOT" init   # ok if already init (or use fresh dir)
```

Use a **fresh** directory for a clean demo:

```bash
export AGENT_MEMORY_ROOT="/tmp/agent-memory-ac1-$$"
agent-memory --root "$AGENT_MEMORY_ROOT" init
```

---

## Part A — Agent A (or human) leaves a handoff (L-Core)

### A1. Checkpoint current work (optional)

```bash
agent-memory --root "$AGENT_MEMORY_ROOT" checkpoint \
  --goal "G1MARK build handoff demo" \
  --next-steps $'- STEP1MARK continue from handoff\n- STEP2 optional'
```

### A2. Write handoff (required)

```bash
agent-memory --root "$AGENT_MEMORY_ROOT" handoff \
  --goal "G1MARK build handoff demo" \
  --next-steps $'- STEP1MARK continue from handoff\n- verify context loads marks'
```

### A3. L-Core verify (no LLM)

```bash
# handoff file exists and contains marks
ls "$AGENT_MEMORY_ROOT"/working/handoff-*.md
grep -E 'G1MARK|STEP1MARK' "$AGENT_MEMORY_ROOT"/working/handoff-*.md

# working updated
agent-memory --root "$AGENT_MEMORY_ROOT" get working_current | grep -E 'G1MARK|STEP1MARK'

# context includes working marks
agent-memory --root "$AGENT_MEMORY_ROOT" context | grep -E 'G1MARK|STEP1MARK'
```

**Pass criteria (L-Core):**

- [ ] At least one `working/handoff-*.md` contains `G1MARK` and `STEP1MARK`  
- [ ] `get working_current` or `context` shows both marks  

---

## Part B — Agent B new session (L-Ref)

### B1. New chat / new agent window

Do **not** paste the previous transcript.

### B2. Agent B startup (must follow integration paste)

Agent B runs:

```bash
agent-memory --root "$AGENT_MEMORY_ROOT" context
# optional: list handoffs
ls "$AGENT_MEMORY_ROOT"/working/handoff-*.md
```

### B3. User asks

> 下一步做什么？

### B4. Pass criteria (L-Ref)

- [ ] Agent B’s first useful reply references **G1MARK** (goal) and **STEP1MARK** (next step)  
- [ ] Agent B did not require the original chat log  

If B fails but Part A passes: fix agent rules / paste block (L-Protocol), not the CLI.

---

## Part C — Cleanup (optional)

```bash
rm -rf "$AGENT_MEMORY_ROOT"   # only if you used a temp root
```

---

## Mapping to REQUIREMENTS

| AC | This script |
|----|-------------|
| AC-1 L-Core subset | Part A |
| AC-1 L-Ref | Part B |
| AC-4 related | checkpoint in A1 |
