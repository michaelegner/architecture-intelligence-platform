"""v0.8 I4 E6 gate (owner review of the I4b plan): every configuration and ground-truth verdict of
S4 must say PASSED.

A zero exit code of `capture.sh` is never a pass: its steps record FAILED verdicts on purpose and go
on, so that every verdict is collected. The gate reads the files instead. The expected set comes from
the applied configuration, not from what is on disk, so a pair or a consumer without a verdict is
MISSING:

    applied-mm2.json (P1a, P2, P3), p1b-<source>-to-<target>.json per applied pair,
    applied-helm.json (K7), raw/GT-<pair>-replication.check.json per applied pair,
    raw/GT-<group>-lag.check.json per remaining Redpanda consumer,
    raw/GT-<group>-kafka-lag.check.json per moved group, handoff-after.json, the functional test.
"""

import argparse
import json
import sys
from pathlib import Path

from _i3 import checker

# The lag reads of capture.sh ground-truth: the Redpanda consumers that stay, and the moved groups.
REMAINING_GROUPS = ("ecommerce-product-query-service", "ecommerce-category-query-service")
MOVED_GROUPS = ("ecommerce-catalog-service", "ecommerce-image-service")


def expected(package: Path, functional: Path) -> list[Path]:
    paths = [package / "applied-mm2.json"]
    try:
        pairs = [p["pair"] for p in json.loads(paths[0].read_text())["pairs"]]
    except (OSError, ValueError, KeyError):
        pairs = []
    paths += [package / f"p1b-{pair.replace('->', '-to-')}.json" for pair in pairs]
    paths.append(package / "applied-helm.json")
    paths += [package / "raw" / f"GT-{pair}-replication.check.json" for pair in pairs]
    paths += [package / "raw" / f"GT-{group}-lag.check.json" for group in REMAINING_GROUPS]
    paths += [package / "raw" / f"GT-{group}-kafka-lag.check.json" for group in MOVED_GROUPS]
    return [*paths, package / "handoff-after.json", functional]


def gate(package: Path, functional: Path) -> dict:
    entries = []
    for path in expected(package, functional):
        try:
            result = json.loads(path.read_text()).get("result") or "MISSING"
        except (OSError, ValueError):
            result = "MISSING"
        entries.append({"file": str(path), "result": result})
    applied = package / "applied-mm2.json"
    no_pairs = not any("p1b-" in e["file"] for e in entries)
    problems = [f"{e['file']}: {e['result']}" for e in entries if e["result"] != checker.PASSED]
    if no_pairs:
        problems.append(f"{applied}: no applied pair")
    return checker.verdict(
        "e6-gate",
        "every S4 configuration and ground-truth verdict says PASSED",
        checker.FAILED if problems else checker.PASSED,
        [e["file"] for e in entries],
        verdicts=entries,
        problems=problems,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("package", type=Path)
    parser.add_argument("--functional", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = gate(args.package, args.functional)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"e6-gate: {result['result']}")
    for problem in result["problems"]:
        print(f"  {problem}")
    return checker.EXIT[result["result"]]


if __name__ == "__main__":
    sys.exit(main())
