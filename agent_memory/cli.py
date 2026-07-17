"""argparse entry — FA-2 commands."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from agent_memory import SCHEMA_VERSION, __version__
from agent_memory.commands import checkpoint as checkpoint_cmd
from agent_memory.commands import context_cmd
from agent_memory.commands import doctor as doctor_cmd
from agent_memory.commands import extract as extract_cmd
from agent_memory.commands import forget as forget_cmd
from agent_memory.commands import gc as gc_cmd
from agent_memory.commands import get_cmd
from agent_memory.commands import handoff_cmd
from agent_memory.commands import init as init_cmd
from agent_memory.commands import project_detect_cmd
from agent_memory.commands import promote as promote_cmd
from agent_memory.commands import recent_cmd
from agent_memory.commands import reindex as reindex_cmd
from agent_memory.commands import reject as reject_cmd
from agent_memory.commands import remember as remember_cmd
from agent_memory.commands import search_cmd
from agent_memory.commands import session_end as session_end_cmd
from agent_memory.commands import turn_cmd
from agent_memory.config import DEFAULT_ROOT, RECENT_DEFAULT_N, TOP_K_DEFAULT, resolve_root
from agent_memory.errors import MemoryError

# Global flags that agents often place after the subcommand.
# argparse only accepts them before the subcommand unless we hoist them.
_GLOBAL_BOOL_FLAGS = frozenset({"-q", "--quiet", "--json"})


def hoist_global_options(argv: list[str]) -> list[str]:
    """Hoist ``--root`` / ``-q`` / ``--quiet`` / ``--json`` to the front of argv.

    Accepts both of these forms:
      agent-memory --root /path context --query x
      agent-memory context --query x --root /path
    """
    if not argv:
        return argv
    globals_out: list[str] = []
    rest: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--root" and i + 1 < len(argv):
            globals_out.extend([a, argv[i + 1]])
            i += 2
            continue
        if a.startswith("--root="):
            globals_out.append(a)
            i += 1
            continue
        if a in _GLOBAL_BOOL_FLAGS:
            globals_out.append(a)
            i += 1
            continue
        rest.append(a)
        i += 1
    if not globals_out:
        return argv
    return globals_out + rest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-memory",
        description=(
            "Pure-file personal agent memory CLI. "
            f"Default root: {DEFAULT_ROOT} (override with --root or AGENT_MEMORY_ROOT). "
            "``--root`` may appear before or after the subcommand. "
            f"schema_version required for writes: {SCHEMA_VERSION}."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__} (schema {SCHEMA_VERSION})",
    )
    parser.add_argument(
        "--root",
        default=None,
        help=(
            f"Memory root (default: $AGENT_MEMORY_ROOT or {DEFAULT_ROOT}). "
            "May be placed before or after the subcommand."
        ),
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Less stderr")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable stdout where supported",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create empty legal memory store")
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Rewrite empty templates only if no memory bodies exist (never wipe data)",
    )

    sub.add_parser("doctor", help="Health checks (INDEX, schema, orphans)")
    sub.add_parser("reindex", help="Rebuild INDEX from body files")

    p_search = sub.add_parser("search", help="L0 hierarchical search")
    p_search.add_argument("query", nargs="?", default="", help="Search query")
    p_search.add_argument(
        "--mode",
        choices=("semantic", "episodic"),
        default="semantic",
    )
    p_search.add_argument("--project", default=None)
    p_search.add_argument("--top-k", type=int, default=TOP_K_DEFAULT)
    p_search.add_argument("--include-staging", action="store_true")
    p_search.add_argument("--history", action="store_true")

    p_get = sub.add_parser("get", help="Get one memory by id")
    p_get.add_argument("id", help="Memory id")

    p_remember = sub.add_parser("remember", help="Immediate active semantic")
    p_remember.add_argument("--slot", required=True)
    p_remember.add_argument("--content", required=True)
    p_remember.add_argument("--title", default=None)
    p_remember.add_argument("--one-liner", default=None)
    p_remember.add_argument("--scope", default="global")
    p_remember.add_argument("--project", default=None)
    p_remember.add_argument("--content-kind", default="preference")
    p_remember.add_argument(
        "--force",
        action="store_true",
        help="Allow forceable PII false positives (never secrets)",
    )

    p_forget = sub.add_parser("forget", help="Soft or hard delete")
    p_forget.add_argument("id", help="Memory id")
    p_forget.add_argument("--hard", action="store_true")

    p_recent = sub.add_parser(
        "recent",
        help="Recent writes (read-only; prune via gc)",
    )
    p_recent.add_argument("--n", type=int, default=RECENT_DEFAULT_N)

    p_cp = sub.add_parser("checkpoint", help="Update working/current.md")
    p_cp.add_argument("--goal", default=None)
    p_cp.add_argument("--decisions", default=None)
    p_cp.add_argument("--decisions-file", default=None)
    p_cp.add_argument("--next-steps", default=None)
    p_cp.add_argument("--project-id", default=None)
    p_cp.add_argument("--session-id", default=None)
    p_cp.add_argument("--related-id", action="append", default=None)
    p_cp.add_argument("--force", action="store_true")

    p_turn = sub.add_parser(
        "turn",
        help="Write pending turn essence under memory root (v2; for Stop hooks)",
    )
    p_turn.add_argument("--goal", required=True)
    p_turn.add_argument("--next-steps", required=True)
    p_turn.add_argument("--decisions", default=None)
    p_turn.add_argument("--project-id", default=None)
    p_turn.add_argument(
        "--cwd",
        default=None,
        help="Detect project id from this path when --project-id omitted",
    )
    p_turn.add_argument("--force", action="store_true")

    p_ho = sub.add_parser("handoff", help="Write handoff snapshot")
    p_ho.add_argument("--goal", required=True)
    p_ho.add_argument("--decisions", default=None)
    p_ho.add_argument("--next-steps", default=None)
    p_ho.add_argument("--related-id", action="append", default=None)
    p_ho.add_argument("--project-id", default=None)
    p_ho.add_argument("--session-id", default=None)
    p_ho.add_argument("--force", action="store_true")

    p_se = sub.add_parser("session-end", help="Write one episode + touch working")
    p_se.add_argument("--title", required=True)
    p_se.add_argument("--body", default=None)
    p_se.add_argument("--body-file", default=None)
    p_se.add_argument("--one-liner", default=None)
    p_se.add_argument("--project-id", default=None)
    p_se.add_argument("--session-id", default=None)
    p_se.add_argument("--force", action="store_true")

    p_pd = sub.add_parser("project-detect", help="Detect project id + confidence")
    p_pd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to inspect (default: cwd)",
    )
    p_pd.add_argument(
        "--force-confidence",
        choices=("high", "low"),
        default=None,
        help="Test/debug: override confidence only",
    )
    p_pd.add_argument(
        "--effective",
        action="store_true",
        help="Also show effective project (working override / env)",
    )

    p_ex = sub.add_parser("extract", help="Extract candidates from episode")
    p_ex.add_argument("--from", dest="from_id", required=True, help="Episode id")
    p_ex.add_argument(
        "--mode",
        choices=("rules", "fixture"),
        default="rules",
    )
    p_ex.add_argument("--force", action="store_true")

    p_pr = sub.add_parser("promote", help="Promote candidate to active")
    p_pr.add_argument("id", help="Candidate id")
    p_pr.add_argument("--user-confirmed", action="store_true")
    p_pr.add_argument("--related-episode", action="append", default=None)
    p_pr.add_argument("--force", action="store_true")

    p_rj = sub.add_parser("reject", help="Reject candidate forever")
    p_rj.add_argument("id", help="Candidate id")

    p_gc = sub.add_parser("gc", help="Expiry + archive + prune")
    p_gc.add_argument("--dry-run", action="store_true")

    p_ctx = sub.add_parser("context", help="Pack T0 + working + semantic hits")
    p_ctx.add_argument("--query", default="", help="Semantic search query")
    p_ctx.add_argument("--project", default=None)
    p_ctx.add_argument("--top-k", type=int, default=TOP_K_DEFAULT)
    p_ctx.add_argument("--include-staging", action="store_true")

    return parser


def _not_implemented(cmd: str) -> int:
    print(f"error: command {cmd!r} is not implemented yet", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    argv = hoist_global_options(list(argv))
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return int(code) if isinstance(code, int) else (1 if code else 0)

    quiet = getattr(args, "quiet", False)
    as_json = getattr(args, "json", False)
    root = resolve_root(getattr(args, "root", None))

    try:
        if args.command == "init":
            init_cmd.run_init(root, force=bool(getattr(args, "force", False)))
            if not quiet:
                print(f"initialized memory root: {root}")
                print(f"schema_version: {SCHEMA_VERSION}")
            return 0

        if args.command == "reindex":
            n_sem, n_epi = reindex_cmd.run_reindex(root)
            if not quiet:
                print(f"reindex ok: semantic={n_sem} episodic={n_epi}")
            return 0

        if args.command == "doctor":
            return doctor_cmd.run_doctor(root)

        if args.command == "remember":
            result = remember_cmd.run_remember(
                root,
                slot=args.slot,
                content=args.content,
                title=args.title,
                one_liner=args.one_liner,
                scope=args.scope,
                project=args.project,
                content_kind=args.content_kind,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"remembered id={result['id']} path={result['path']}")
                if result.get("superseded"):
                    print(f"superseded: {', '.join(result['superseded'])}")
            return 0

        if args.command == "search":
            out = search_cmd.run_search(
                root,
                args.query or "",
                mode=args.mode,
                project=args.project,
                top_k=args.top_k,
                include_staging=bool(args.include_staging),
                history=bool(args.history),
                as_json=as_json,
            )
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
            return 0

        if args.command == "get":
            out = get_cmd.run_get(root, args.id, as_json=as_json)
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
            return 0

        if args.command == "forget":
            forget_cmd.run_forget(root, args.id, hard=bool(args.hard))
            if not quiet:
                print(f"forgot {args.id}" + (" (hard)" if args.hard else ""))
            return 0

        if args.command == "recent":
            out = recent_cmd.run_recent(root, n=args.n, as_json=as_json)
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
            return 0

        if args.command == "checkpoint":
            decisions = args.decisions
            if args.decisions_file:
                decisions = Path(args.decisions_file).read_text(encoding="utf-8")
            result = checkpoint_cmd.run_checkpoint(
                root,
                goal=args.goal,
                decisions=decisions,
                next_steps=args.next_steps,
                project_id=args.project_id,
                session_id=args.session_id,
                related_ids=args.related_id,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"checkpoint ok updated_at={result.get('updated_at')} path={result.get('path')}")
            return 0

        if args.command == "turn":
            result = turn_cmd.run_turn(
                root,
                goal=args.goal,
                next_steps=args.next_steps,
                decisions=args.decisions,
                project_id=args.project_id,
                cwd=args.cwd or Path.cwd(),
                force=bool(args.force),
                quiet=quiet,
            )
            for w in result.get("warnings") or []:
                if not quiet:
                    print(w, file=sys.stderr)
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(
                    f"turn pending path={result.get('path')} "
                    f"project_id={result.get('project_id')}"
                )
            return 0

        if args.command == "handoff":
            result = handoff_cmd.run_handoff(
                root,
                goal=args.goal,
                decisions=args.decisions,
                next_steps=args.next_steps,
                related_ids=args.related_id,
                project_id=args.project_id,
                session_id=args.session_id,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"handoff id={result['id']} path={result['path']}")
            return 0

        if args.command == "session-end":
            body = args.body
            if args.body_file:
                body = Path(args.body_file).read_text(encoding="utf-8")
            if body is None:
                print("error: --body or --body-file required", file=sys.stderr)
                return 2
            result = session_end_cmd.run_session_end(
                root,
                title=args.title,
                body=body,
                one_liner=args.one_liner,
                project_id=args.project_id,
                session_id=args.session_id,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(
                    f"session-end episode_id={result['episode_id']} path={result['path']}"
                )
            return 0

        if args.command == "project-detect":
            out = project_detect_cmd.run_project_detect(
                root,
                args.path,
                force_confidence=args.force_confidence,
                as_json=as_json,
                show_effective=bool(args.effective),
            )
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
            return 0

        if args.command == "extract":
            result = extract_cmd.run_extract(
                root,
                args.from_id,
                mode=args.mode,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"extract: {len(result.get('candidates', []))} candidate(s)")
                for c in result.get("candidates", []):
                    print(f"  {c['type']} {c['id']} -> {c['path']}")
            return 0

        if args.command == "promote":
            result = promote_cmd.run_promote(
                root,
                args.id,
                user_confirmed=bool(args.user_confirmed),
                related_episodes=args.related_episode,
                force=bool(args.force),
                quiet=quiet,
            )
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"promoted id={result['id']} path={result['path']}")
            return 0

        if args.command == "reject":
            result = reject_cmd.run_reject(root, args.id)
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"rejected id={result['id']}")
            return 0

        if args.command == "gc":
            result = gc_cmd.run_gc(root, dry_run=bool(args.dry_run))
            if as_json:
                print(json.dumps(result, ensure_ascii=False))
            elif not quiet:
                print(f"gc ok: {result}")
            return 0

        if args.command == "context":
            out = context_cmd.run_context(
                root,
                query=args.query or "",
                project=args.project,
                top_k=args.top_k,
                include_staging=bool(args.include_staging),
            )
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
            return 0

        return _not_implemented(args.command)
    except MemoryError as e:
        print(f"error: {e.message}", file=sys.stderr)
        return e.exit_code
    except Exception as e:  # noqa: BLE001
        if not quiet:
            print(f"error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
