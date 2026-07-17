"""agent-memory doctor"""

from __future__ import annotations

import sys
from pathlib import Path

from agent_memory.index import DoctorFinding, doctor_check


def run_doctor(root: Path, *, stream=None) -> int:
    """Print findings. Exit 0 if no errors; non-zero if any error-level finding."""
    out = stream if stream is not None else sys.stdout
    findings = doctor_check(root)
    errors = [f for f in findings if f.level == "error"]
    warns = [f for f in findings if f.level == "warn"]
    infos = [f for f in findings if f.level == "info"]

    if not findings:
        print("doctor: ok (no findings)", file=out)
        return 0

    for f in findings:
        print(f"{f.level.upper()}: [{f.code}] {f.message}", file=out)

    print(
        f"doctor: {len(errors)} error(s), {len(warns)} warning(s), {len(infos)} info",
        file=out,
    )
    return 1 if errors else 0
