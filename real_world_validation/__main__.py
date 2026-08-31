"""CLI entry point for the real-world validation comparator (I1 §32-33).

    uv run python -m real_world_validation compare --expected <path> --actual <path>

Fully generic: no `--system` flag or system-specific branch in this module (parent spec §24 forbids
production `if system == "..."` hacks). System-specific dossier paths are a caller/shell concern.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from real_world_validation.comparator import compare
from real_world_validation.loader import load_actual, load_expected
from real_world_validation.model import ExpectedValidationError
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

    args = parser.parse_args(argv)
    return _compare(args.expected, args.actual)


if __name__ == "__main__":
    sys.exit(main())
