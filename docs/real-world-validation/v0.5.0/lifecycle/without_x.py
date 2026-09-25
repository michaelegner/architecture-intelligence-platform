"""Compute Without_X(P) for one frozen owned-graph query output (I5 §10; README.md).

    uv run python without_x.py <Q-SVC or Q-REL output of step P> <X source instance id>

It reads a `cypher-shell --format plain` output whose last column is the sorted owner list. It
removes X from every owner list, drops each row whose owner list becomes empty, and prints the
result in the same format (nothing at all when no row is left, as `cypher-shell` prints for an
empty result). For a removal step, this is the exact expected owned graph: diff it
against the step's own Q-SVC or Q-REL output. Row order and owner order are kept, because both are
already frozen by the queries' ORDER BY.
"""

import json
import sys
from pathlib import Path


def _split_row(line: str) -> tuple[str, list[str]]:
    """Split `"a", "b", ["o1", "o2"]` into its leading columns and its owner list."""
    prefix, _, owners = line.rpartition(", [")
    if not owners.endswith("]"):
        raise SystemExit(f"row does not end with an owner list: {line!r}")
    return prefix, json.loads("[" + owners)


def without_x(text: str, x: str) -> str:
    """The projection, formatted as `cypher-shell --format plain` would print it. For an empty
    result that means nothing at all, not even the header (finding F6, #253)."""
    if not text.strip():
        return ""
    lines = text.rstrip("\n").split("\n")
    header, rows = lines[0], lines[1:]
    kept = []
    for row in rows:
        prefix, owners = _split_row(row)
        remaining = [o for o in owners if o != x]
        if remaining:
            kept.append(f"{prefix}, {json.dumps(remaining, separators=(', ', ': '))}")
    if not kept:
        return ""
    return "\n".join([header, *kept]) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.write(without_x(Path(argv[0]).read_text(), argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
