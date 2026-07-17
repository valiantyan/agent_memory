"""INDEX.semantic / INDEX.episodic parse, serialize, rebuild, atomic write."""

from __future__ import annotations

import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Iterable

from agent_memory.config import INDEX_SEMANTIC_MAX_ACTIVE
from agent_memory.frontmatter import parse as parse_fm
from agent_memory.io_atomic import write_text_atomic

SEMANTIC_HEADER = (
    "| id | type | content_kind | scope | slot | one_liner | path | updated_at |"
)
EPISODIC_HEADER = "| id | project_id | one_liner | path | created_at |"

SEMANTIC_COLUMNS = (
    "id",
    "type",
    "content_kind",
    "scope",
    "slot",
    "one_liner",
    "path",
    "updated_at",
)
EPISODIC_COLUMNS = ("id", "project_id", "one_liner", "path", "created_at")

_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")


def escape_cell(value: str | None) -> str:
    if value is None:
        return ""
    s = str(value).replace("\n", " ").replace("\r", " ")
    return s.replace("\\", "\\\\").replace("|", "\\|")


def unescape_cell(value: str) -> str:
    # Unescape \| and \\
    out: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            out.append(value[i + 1])
            i += 2
            continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _split_row(line: str) -> list[str]:
    """Split markdown table row into cells (handles \\|)."""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            buf.append(ch)
            buf.append(line[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append(unescape_cell("".join(buf).strip()))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    cells.append(unescape_cell("".join(buf).strip()))
    return cells


@dataclass
class SemanticRow:
    id: str
    type: str
    content_kind: str
    scope: str
    slot: str
    one_liner: str
    path: str
    updated_at: str

    def as_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class EpisodicRow:
    id: str
    project_id: str
    one_liner: str
    path: str
    created_at: str

    def as_dict(self) -> dict[str, str]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


def parse_semantic_index(text: str) -> list[SemanticRow]:
    rows: list[SemanticRow] = []
    for line in text.splitlines():
        line_st = line.strip()
        if not line_st.startswith("|"):
            continue
        if _SEP_RE.match(line_st):
            continue
        cells = _split_row(line_st)
        if len(cells) < len(SEMANTIC_COLUMNS):
            continue
        # header row
        if cells[0].lower() == "id" and len(cells) > 1 and cells[1].lower() == "type":
            continue
        row = SemanticRow(
            id=cells[0],
            type=cells[1],
            content_kind=cells[2],
            scope=cells[3],
            slot=cells[4],
            one_liner=cells[5],
            path=cells[6],
            updated_at=cells[7] if len(cells) > 7 else "",
        )
        if row.id:
            rows.append(row)
    return rows


def parse_episodic_index(text: str) -> list[EpisodicRow]:
    rows: list[EpisodicRow] = []
    for line in text.splitlines():
        line_st = line.strip()
        if not line_st.startswith("|"):
            continue
        if _SEP_RE.match(line_st):
            continue
        cells = _split_row(line_st)
        if len(cells) < len(EPISODIC_COLUMNS):
            continue
        if cells[0].lower() == "id" and cells[1].lower() in ("project_id", "project id"):
            continue
        row = EpisodicRow(
            id=cells[0],
            project_id=cells[1],
            one_liner=cells[2],
            path=cells[3],
            created_at=cells[4] if len(cells) > 4 else "",
        )
        if row.id:
            rows.append(row)
    return rows


def serialize_semantic_index(rows: Iterable[SemanticRow]) -> str:
    lines = [
        "# INDEX.semantic",
        "",
        SEMANTIC_HEADER,
        "|----|------|--------------|-------|------|-----------|------|------------|",
    ]
    for r in rows:
        cells = [
            escape_cell(r.id),
            escape_cell(r.type),
            escape_cell(r.content_kind),
            escape_cell(r.scope),
            escape_cell(r.slot),
            escape_cell(r.one_liner),
            escape_cell(r.path),
            escape_cell(r.updated_at),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def serialize_episodic_index(rows: Iterable[EpisodicRow]) -> str:
    lines = [
        "# INDEX.episodic",
        "",
        EPISODIC_HEADER,
        "|----|------------|-----------|------|------------|",
    ]
    for r in rows:
        cells = [
            escape_cell(r.id),
            escape_cell(r.project_id),
            escape_cell(r.one_liner),
            escape_cell(r.path),
            escape_cell(r.created_at),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def semantic_index_path(root: Path) -> Path:
    return root / "INDEX.semantic.md"


def episodic_index_path(root: Path) -> Path:
    return root / "INDEX.episodic.md"


def load_semantic_index(root: Path) -> list[SemanticRow]:
    path = semantic_index_path(root)
    if not path.is_file():
        return []
    return parse_semantic_index(path.read_text(encoding="utf-8"))


def load_episodic_index(root: Path) -> list[EpisodicRow]:
    path = episodic_index_path(root)
    if not path.is_file():
        return []
    return parse_episodic_index(path.read_text(encoding="utf-8"))


def save_semantic_index(root: Path, rows: Iterable[SemanticRow]) -> None:
    write_text_atomic(semantic_index_path(root), serialize_semantic_index(rows))


def save_episodic_index(root: Path, rows: Iterable[EpisodicRow]) -> None:
    write_text_atomic(episodic_index_path(root), serialize_episodic_index(rows))


def active_semantic_count(root: Path) -> int:
    return len(load_semantic_index(root))


def would_exceed_semantic_quota(root: Path, additional: int = 1) -> bool:
    return active_semantic_count(root) + additional > INDEX_SEMANTIC_MAX_ACTIVE


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_under_root(root: Path, rel: str) -> Path | None:
    """Resolve relative INDEX path; return None if escapes root (path traversal)."""
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        return None
    # reject .. segments
    parts = Path(rel).parts
    if any(p == ".." for p in parts):
        return None
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def _read_meta(path: Path) -> tuple[dict, str] | None:
    try:
        text = path.read_text(encoding="utf-8")
        return parse_fm(text)
    except (OSError, ValueError, UnicodeError):
        return None


def rebuild_semantic_rows(root: Path) -> list[SemanticRow]:
    """Scan bodies for status=active semantic + procedural active."""
    rows: list[SemanticRow] = []
    seen: set[str] = set()

    candidates: list[Path] = []
    scopes = root / "scopes"
    if scopes.is_dir():
        candidates.extend(scopes.glob("**/semantic/*.md"))
    proc_active = root / "procedural" / "active"
    if proc_active.is_dir():
        candidates.extend(proc_active.glob("*.md"))

    for path in sorted(candidates, key=lambda p: str(p)):
        # skip history/staging/archive if ever nested under scopes oddly
        parts = set(path.parts)
        if "history" in parts or "staging" in parts or "archive" in parts:
            continue
        if "candidates" in parts:
            continue
        parsed = _read_meta(path)
        if not parsed:
            continue
        meta, _body = parsed
        status = str(meta.get("status") or "").lower()
        if status != "active":
            continue
        mem_type = str(meta.get("type") or "semantic")
        if mem_type not in ("semantic", "procedural"):
            continue
        mid = str(meta.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        scope = str(meta.get("scope") or "global")
        slot = meta.get("slot")
        slot_s = "" if slot is None else str(slot)
        one = str(meta.get("one_liner") or meta.get("title") or "")[:80]
        updated = str(meta.get("updated_at") or meta.get("created_at") or "")
        kind = str(meta.get("content_kind") or "")
        rows.append(
            SemanticRow(
                id=mid,
                type=mem_type,
                content_kind=kind,
                scope=scope,
                slot=slot_s,
                one_liner=one,
                path=_rel(root, path),
                updated_at=updated,
            )
        )
    rows.sort(key=lambda r: r.id)
    return rows


def rebuild_episodic_rows(root: Path) -> list[EpisodicRow]:
    rows: list[EpisodicRow] = []
    seen: set[str] = set()
    episodes = root / "episodes"
    if not episodes.is_dir():
        return rows
    for path in sorted(episodes.rglob("*.md"), key=lambda p: str(p)):
        if "archive" in path.parts:
            continue
        parsed = _read_meta(path)
        if not parsed:
            continue
        meta, _body = parsed
        status = str(meta.get("status") or "active").lower()
        if status in ("deleted", "discarded"):
            continue
        mid = str(meta.get("id") or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        project_id = meta.get("project_id")
        if project_id is None:
            scope = str(meta.get("scope") or "")
            if scope.startswith("project:"):
                project_id = scope.split(":", 1)[1]
            else:
                project_id = ""
        one = str(meta.get("one_liner") or meta.get("title") or "")[:80]
        created = str(meta.get("created_at") or meta.get("updated_at") or "")
        rows.append(
            EpisodicRow(
                id=mid,
                project_id=str(project_id or ""),
                one_liner=one,
                path=_rel(root, path),
                created_at=created,
            )
        )
    rows.sort(key=lambda r: r.id)
    return rows


def reindex(root: Path) -> tuple[int, int]:
    """Rebuild both indexes from bodies. Returns (semantic_count, episodic_count)."""
    sem = rebuild_semantic_rows(root)
    epi = rebuild_episodic_rows(root)
    save_semantic_index(root, sem)
    save_episodic_index(root, epi)
    return len(sem), len(epi)


@dataclass
class DoctorFinding:
    level: str  # error | warn | info
    code: str
    message: str


def doctor_check(root: Path) -> list[DoctorFinding]:
    """PR-2 doctor: INDEX vs files, bad front matter, quota, schema."""
    findings: list[DoctorFinding] = []

    schema = root / "schema_version"
    if not schema.is_file():
        findings.append(
            DoctorFinding("error", "schema_missing", f"missing {schema}")
        )
    else:
        ver = schema.read_text(encoding="utf-8").strip()
        from agent_memory import SCHEMA_VERSION

        if ver != SCHEMA_VERSION:
            findings.append(
                DoctorFinding(
                    "error",
                    "schema_mismatch",
                    f"schema_version={ver!r} expected {SCHEMA_VERSION!r}",
                )
            )

    # Unparseable active bodies
    for pattern in ("scopes/**/semantic/*.md", "procedural/active/*.md"):
        for path in root.glob(pattern):
            if _read_meta(path) is None:
                findings.append(
                    DoctorFinding(
                        "error",
                        "bad_frontmatter",
                        f"unparseable front matter: {_rel(root, path)}",
                    )
                )

    for path in (root / "episodes").rglob("*.md") if (root / "episodes").is_dir() else []:
        if "archive" in path.parts:
            continue
        if _read_meta(path) is None:
            findings.append(
                DoctorFinding(
                    "error",
                    "bad_frontmatter",
                    f"unparseable episode: {_rel(root, path)}",
                )
            )

    # INDEX.semantic consistency
    try:
        index_rows = load_semantic_index(root)
    except Exception as e:  # noqa: BLE001
        findings.append(
            DoctorFinding("error", "index_unparseable", f"INDEX.semantic: {e}")
        )
        index_rows = []

    if len(index_rows) > INDEX_SEMANTIC_MAX_ACTIVE:
        findings.append(
            DoctorFinding(
                "error",
                "quota_exceeded",
                f"INDEX.semantic active rows {len(index_rows)} > {INDEX_SEMANTIC_MAX_ACTIVE}",
            )
        )
    elif len(index_rows) >= INDEX_SEMANTIC_MAX_ACTIVE:
        findings.append(
            DoctorFinding(
                "warn",
                "quota_full",
                f"INDEX.semantic at capacity ({INDEX_SEMANTIC_MAX_ACTIVE})",
            )
        )

    index_by_id = {r.id: r for r in index_rows}
    body_active = {r.id: r for r in rebuild_semantic_rows(root)}

    for mid, row in index_by_id.items():
        abs_path = resolve_under_root(root, row.path)
        if abs_path is None:
            findings.append(
                DoctorFinding(
                    "error",
                    "path_escape",
                    f"INDEX id={mid} path escapes root or invalid: {row.path!r}",
                )
            )
            continue
        if not abs_path.is_file():
            findings.append(
                DoctorFinding(
                    "error",
                    "index_missing_file",
                    f"INDEX id={mid} path missing: {row.path}",
                )
            )
            continue
        parsed = _read_meta(abs_path)
        if not parsed:
            findings.append(
                DoctorFinding(
                    "error",
                    "index_bad_body",
                    f"INDEX id={mid} body unparseable: {row.path}",
                )
            )
            continue
        meta, _ = parsed
        body_id = str(meta.get("id") or "")
        if body_id and body_id != mid:
            findings.append(
                DoctorFinding(
                    "error",
                    "id_mismatch",
                    f"INDEX id={mid} but file id={body_id} at {row.path}",
                )
            )
        status = str(meta.get("status") or "").lower()
        if status != "active":
            findings.append(
                DoctorFinding(
                    "error",
                    "index_stale_status",
                    f"INDEX id={mid} but file status={status!r}",
                )
            )

    for mid, brow in body_active.items():
        if mid not in index_by_id:
            findings.append(
                DoctorFinding(
                    "error",
                    "orphan_active",
                    f"active body not in INDEX: id={mid} path={brow.path}",
                )
            )

    # Episodic INDEX
    try:
        epi_rows = load_episodic_index(root)
    except Exception as e:  # noqa: BLE001
        findings.append(
            DoctorFinding("error", "index_unparseable", f"INDEX.episodic: {e}")
        )
        epi_rows = []

    epi_by_id = {r.id: r for r in epi_rows}
    epi_bodies = {r.id: r for r in rebuild_episodic_rows(root)}
    for mid, row in epi_by_id.items():
        abs_path = resolve_under_root(root, row.path)
        if abs_path is None:
            findings.append(
                DoctorFinding(
                    "error",
                    "path_escape",
                    f"INDEX.episodic id={mid} path escapes root: {row.path!r}",
                )
            )
            continue
        if not abs_path.is_file():
            findings.append(
                DoctorFinding(
                    "error",
                    "index_missing_file",
                    f"INDEX.episodic id={mid} path missing: {row.path}",
                )
            )
    for mid, brow in epi_bodies.items():
        if mid not in epi_by_id:
            findings.append(
                DoctorFinding(
                    "warn",
                    "orphan_episode",
                    f"episode not in INDEX: id={mid} path={brow.path}",
                )
            )

    # recent.jsonl malformed lines (skip — warn)
    recent = root / "meta" / "recent.jsonl"
    if recent.is_file():
        for i, line in enumerate(recent.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                import json

                json.loads(line)
            except json.JSONDecodeError:
                findings.append(
                    DoctorFinding(
                        "warn",
                        "recent_bad_line",
                        f"meta/recent.jsonl line {i} not JSON",
                    )
                )

    # SEC-7 best-effort secret scan on memory bodies (not meta logs)
    from agent_memory.security import find_secrets

    scan_globs = (
        "scopes/**/semantic/*.md",
        "procedural/active/*.md",
        "procedural/candidates/*.md",
        "staging/candidates/*.md",
        "working/*.md",
        "profile/*.md",
    )
    for pattern in scan_globs:
        for path in root.glob(pattern):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for hit in find_secrets(text):
                findings.append(
                    DoctorFinding(
                        "error",
                        "secret_in_store",
                        f"{_rel(root, path)} matches {hit.pattern_id} "
                        f"(snippet={hit.snippet!r})",
                    )
                )
    if (root / "episodes").is_dir():
        for path in (root / "episodes").rglob("*.md"):
            if "archive" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for hit in find_secrets(text):
                findings.append(
                    DoctorFinding(
                        "error",
                        "secret_in_store",
                        f"{_rel(root, path)} matches {hit.pattern_id} "
                        f"(snippet={hit.snippet!r})",
                    )
                )

    return findings
