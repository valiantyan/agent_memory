# v1 Sign-off checklist (PR-10)

| Item | Value |
|------|-------|
| Requirements | v1.2 Frozen |
| Design | v0.3 Frozen |
| FA-2 | All 17 commands implemented |

## Automated (must be green)

```bash
pip install -e ".[dev]"
pytest -q
bash scripts/demo_ac1.sh
```

| Gate | Maps to |
|------|---------|
| `tests/test_ac_signoff.py` | AC-1 L-Core, T0, AC-2…AC-11, AC-P, AC-X, doctor |
| `tests/test_ac_8_security.py` | AC-8 detail |
| `tests/test_ac_11_index_atomic.py` | AC-11 parallel |
| `scripts/demo_ac1.sh` | AC-1 L-Core handoff marks |
| CI `.github/workflows/ci.yml` | pytest + demo on PR |

## Manual L-Ref (AC-1 Part B)

Follow `docs/demo/AC1_script.md` Part B with a second agent after paste from `docs/REFERENCE_INTEGRATION.md`.

- [ ] Agent B recovers G1MARK / STEP1MARK without chat paste  

## Product residual risks (accepted)

See REQUIREMENTS §12 / DESIGN residuals: model may skip checkpoint; regex security is heuristic; single working race.

## Sign-off

| Role | Name | Date | Result |
|------|------|------|--------|
| Implementer | | | |
| Reviewer | | | L-Core pytest green / L-Ref demo done |
