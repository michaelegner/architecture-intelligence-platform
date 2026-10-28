"""v0.8 I4 §7: Proof C. The recorded after-wave answer (A-R and A-K, with the after-wave
declarations) gives exactly the rows and limitations of `i3-evidence/expected-after.json`, compared
on the semantic fields only, as the I3 replay test does. The reference must first hash to its
pinned digest (§3)."""

import argparse
import json
import sys
from pathlib import Path

from _i3 import checker
from plan_format import EXPECTED_AFTER
from score import check_reference_digest

FIELDS = (
    "broker_id",
    "topic_name",
    "consumer_service_id",
    "crossing",
    "status",
    "reason",
    "cross_broker_producers",
)


def essentials(rows: list[dict]) -> list[dict]:
    picked = [{k: row[k] for k in FIELDS if row.get(k) is not None} for row in rows]
    return sorted(
        picked, key=lambda r: (r["broker_id"], r["topic_name"], r.get("consumer_service_id", ""))
    )


def check(recording: dict, expected: dict) -> dict:
    answer = recording["report_request"]["answer"]
    rows = essentials((answer.get("data") or {}).get("rows", []))
    want = essentials(expected["rows"])
    codes = sorted(item["code"] for item in answer.get("limitations", []))
    problems = []
    if rows != want:
        problems.append("the rows differ from expected-after.json")
    if codes != sorted(expected["limitations"]):
        problems.append(f"the limitations {codes} differ from {sorted(expected['limitations'])}")
    return checker.verdict(
        "proof-c",
        "the after-wave answer equals expected-after.json (rows and limitations)",
        checker.FAILED if problems else checker.PASSED,
        [str(EXPECTED_AFTER)],
        problems=problems,
        missing=[r for r in want if r not in rows],
        unexpected=[r for r in rows if r not in want],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--recording", type=Path, required=True, help="the after-wave answers")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    check_reference_digest()
    result = check(json.loads(args.recording.read_text()), json.loads(EXPECTED_AFTER.read_text()))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"proof-c: {result['result']}")
    return checker.EXIT[result["result"]]


if __name__ == "__main__":
    sys.exit(main())
