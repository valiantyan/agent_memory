"""agent-memory project-detect"""

from __future__ import annotations

import json
from pathlib import Path

from agent_memory.project_detect import detect_project
from agent_memory.write_gate import effective_project, read_working_project_id


def run_project_detect(
    root: Path,
    path: str | None = None,
    *,
    force_confidence: str | None = None,
    as_json: bool = False,
    show_effective: bool = False,
) -> str:
    """
    Detect project for PATH (default cwd).
    Does not require schema (read-only heuristic).
    """
    pid, conf = detect_project(path, force_confidence=force_confidence)
    payload = {"project_id": pid, "confidence": conf}
    if show_effective:
        epid, econf = effective_project(
            root, cwd=path, force_confidence=force_confidence
        )
        payload["effective_project_id"] = epid
        payload["effective_confidence"] = econf
        payload["working_project_id"] = read_working_project_id(root)

    if as_json:
        return json.dumps(payload, ensure_ascii=False) + "\n"
    lines = [f"project_id: {pid}", f"confidence: {conf}"]
    if show_effective:
        lines.append(f"effective_project_id: {payload['effective_project_id']}")
        lines.append(f"effective_confidence: {payload['effective_confidence']}")
        lines.append(f"working_project_id: {payload['working_project_id']}")
    return "\n".join(lines) + "\n"
