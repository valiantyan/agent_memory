#!/usr/bin/env bash
# AC-1 L-Core automated subset (docs/demo/AC1_script.md Part A)
# Portable for macOS bash 3.2+
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "${ROOT}/.venv/bin/agent-memory" ]]; then
  AM="${ROOT}/.venv/bin/agent-memory"
elif command -v agent-memory >/dev/null 2>&1; then
  AM="agent-memory"
else
  echo "error: agent-memory not found; run: pip install -e \"${ROOT}[dev]\"" >&2
  exit 1
fi

# Always use an isolated temp root — never inherit ambient AGENT_MEMORY_ROOT
# (avoids writing into a production store during the demo).
MEM_ROOT="${AGENT_MEMORY_AC1_ROOT:-/tmp/agent-memory-ac1-demo-$$}"
export AGENT_MEMORY_ROOT="$MEM_ROOT"

echo "==> Using memory root: $MEM_ROOT"
"$AM" --root "$MEM_ROOT" init -q 2>/dev/null || "$AM" --root "$MEM_ROOT" init

"$AM" --root "$MEM_ROOT" handoff \
  --goal "G1MARK build handoff demo" \
  --next-steps "$(printf '%s\n%s\n' '- STEP1MARK continue from handoff' '- verify context loads marks')"

# shellcheck disable=SC2012
HAND="$(ls -1t "$MEM_ROOT"/working/handoff-*.md 2>/dev/null | head -n 1 || true)"
if [[ -z "${HAND}" || ! -f "${HAND}" ]]; then
  echo "FAIL: no handoff file written" >&2
  exit 1
fi

if ! grep -q 'G1MARK' "$HAND"; then
  echo "FAIL: G1MARK missing in handoff ($HAND)" >&2
  exit 1
fi
if ! grep -q 'STEP1MARK' "$HAND"; then
  echo "FAIL: STEP1MARK missing in handoff ($HAND)" >&2
  exit 1
fi

CTX="$("$AM" --root "$MEM_ROOT" context)"
echo "$CTX" | grep -q 'G1MARK' || { echo "FAIL: G1MARK missing in context" >&2; exit 1; }
echo "$CTX" | grep -q 'STEP1MARK' || { echo "FAIL: STEP1MARK missing in context" >&2; exit 1; }
echo "$CTX" | grep -q '## T0' || { echo "FAIL: ## T0 missing" >&2; exit 1; }
echo "$CTX" | grep -q '## Working' || { echo "FAIL: ## Working missing" >&2; exit 1; }
echo "$CTX" | grep -q '## Semantic' || { echo "FAIL: ## Semantic missing" >&2; exit 1; }

echo "PASS: AC-1 L-Core subset (handoff + context marks)"
echo "Handoff file: $HAND"
echo "For L-Ref (Agent B), follow docs/demo/AC1_script.md Part B"
echo "  export AGENT_MEMORY_ROOT=$MEM_ROOT"
