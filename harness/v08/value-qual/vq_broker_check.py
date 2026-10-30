"""v0.8 value qualification (spec §6.1): the broker state check. The live consumer groups, their
topics and their member counts must equal the frozen capture `catalogue/R1.txt` (the v0.8
`S1-13-groups-describe.txt`). Offsets are not compared. It runs after the bring-up and before each F
session, so what an F session sees live is what a T session gets through R1.

    vq_broker_check.py --out RESULT.json        (runs the R1 command against the live Redpanda)
    vq_broker_check.py --live FILE --out RESULT.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "i4"))

from _i3 import checker

R1 = (
    HERE.parents[2]
    / "docs/specifications/evaluation/v08-value-qualification-evidence/catalogue/R1.txt"
)
GROUPS = (
    "ecommerce-catalog-service",
    "ecommerce-category-query-service",
    "ecommerce-image-service",
    "ecommerce-product-query-service",
)
COMMAND = ["docker", "exec", "redpanda", "rpk", "group", "describe", *GROUPS]


def groups(text: str) -> dict[str, dict]:
    """{group: {"members": int | None, "topics": [topic, ...]}} from `rpk group describe`."""
    found = {}
    for group, lines in checker.group_sections(text).items():
        members, topics, in_table = None, set(), False
        for line in lines:
            cells = line.split()
            if cells[:1] == ["MEMBERS"] and len(cells) > 1 and cells[1].isdigit():
                members = int(cells[1])
            elif cells[:2] == ["TOPIC", "PARTITION"]:
                in_table = True
            elif in_table and len(cells) >= 2 and cells[1].isdigit():
                topics.add(cells[0])
            elif not cells:
                in_table = False
        found[group] = {"members": members, "topics": sorted(topics)}
    return found


def compare(live: str, frozen: str) -> dict:
    want, got = groups(frozen), groups(live)
    problems = []
    for group in sorted(set(want) | set(got)):
        if group not in got:
            problems.append(f"{group}: missing")
        elif group not in want:
            problems.append(f"{group}: not in the frozen capture")
        elif got[group] != want[group]:
            problems.append(f"{group}: {got[group]} != frozen {want[group]}")
    return {"result": "FAILED" if problems else "PASSED", "problems": problems, "live": got}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", type=Path, help="a saved describe output (default: run it)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.live:
        live = args.live.read_text()
    else:
        live = subprocess.run(COMMAND, check=True, capture_output=True, text=True).stdout
    result = compare(live, R1.read_text())
    args.out.write_text(json.dumps(result, indent=2) + "\n")
    print(f"broker state check: {result['result']}")
    for problem in result["problems"]:
        print(f"  {problem}")
    return 0 if result["result"] == "PASSED" else 2


if __name__ == "__main__":
    sys.exit(main())
