"""CLI entry point for the real-world validation comparator and capture tool (I1 §32-33/§31).

    uv run python -m real_world_validation compare --expected <path> --actual <path>
    uv run python -m real_world_validation capture --neo4j-uri ... --out <path>

Fully generic: no `--system` flag or system-specific branch in this module (parent spec §24 forbids
production `if system == "..."` hacks). System-specific dossier paths/scope are a caller/shell
concern, passed in as plain arguments.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import neo4j

from app.graph.repository import build_driver, open_session
from real_world_validation.capture import capture_actual_facts, write_actual_facts
from real_world_validation.comparator import compare
from real_world_validation.loader import load_actual, load_expected
from real_world_validation.model import ExpectedValidationError, ScopeDeclaration
from real_world_validation.reporter import has_release_blocking_finding, render

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_INVALID = 2


def _compare(expected_path: Path, actual_path: Path) -> int:
    try:
        expected = load_expected(expected_path)
        actual = load_actual(actual_path)
    except ExpectedValidationError as exc:
        print(f"invalid validation configuration: {exc}", file=sys.stderr)
        return EXIT_INVALID

    findings = compare(expected, actual)
    print(render(findings))
    return EXIT_FAILURES if has_release_blocking_finding(findings) else EXIT_OK


def _capture(args: argparse.Namespace) -> int:
    scope = ScopeDeclaration(
        entities=tuple(args.scope_entities.split(",")),
        relation_types=tuple(args.scope_relation_types.split(","))
        if args.scope_relation_types
        else None,
    )

    driver = build_driver(args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    try:
        with open_session(driver, database=args.database, read_only=True) as session:
            facts = capture_actual_facts(
                session,
                scope=scope,
                environment=args.environment,
                since=args.since,
                until=args.until,
            )
    except (neo4j.exceptions.Neo4jError, neo4j.exceptions.DriverError) as exc:
        print(f"capture failed: {exc}", file=sys.stderr)
        return EXIT_INVALID
    finally:
        driver.close()

    write_actual_facts(args.out, facts)
    print(f"captured {len(facts)} facts to {args.out}")
    return EXIT_OK


def _iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m real_world_validation")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_parser = subparsers.add_parser("compare", help="compare expected vs. actual facts")
    compare_parser.add_argument(
        "--expected", required=True, type=Path, help="path to expected.yaml"
    )
    compare_parser.add_argument(
        "--actual", required=True, type=Path, help="path to an actual-facts capture"
    )

    capture_parser = subparsers.add_parser(
        "capture", help="capture AIP's actual canonical facts from a live Neo4j graph"
    )
    capture_parser.add_argument("--neo4j-uri", required=True)
    capture_parser.add_argument("--neo4j-user", required=True)
    capture_parser.add_argument("--neo4j-password", required=True)
    capture_parser.add_argument("--database", default="neo4j")
    capture_parser.add_argument("--environment", required=True)
    capture_parser.add_argument("--since", required=True, type=_iso_datetime)
    capture_parser.add_argument("--until", default=None, type=_iso_datetime)
    capture_parser.add_argument(
        "--scope-entities", required=True, help="comma-separated canonical entity ids"
    )
    capture_parser.add_argument(
        "--scope-relation-types",
        default=None,
        help="comma-separated relation types, or omit for any",
    )
    capture_parser.add_argument("--out", required=True, type=Path)

    args = parser.parse_args(argv)
    if args.command == "capture":
        return _capture(args)
    return _compare(args.expected, args.actual)


if __name__ == "__main__":
    sys.exit(main())
