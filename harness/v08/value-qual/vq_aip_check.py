"""v0.8 value qualification (spec §6.1): AIP's before-wave answer (on stdin) gives the nine I2 §8.1
rows, and its snapshot id equals the recorded one. The first check records the id.

    vq_aip_check.py SNAPSHOT_FILE < answer.json
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
C1 = REPO / "docs/specifications/0.8.0/i2-vectors/c1-expected.json"
FIELDS = ("broker_id", "topic_name", "consumer_service_id", "crossing", "status")


def rows(listed: list[dict]) -> list[tuple]:
    return sorted(tuple(row.get(f) for f in FIELDS) for row in listed)


def check(answer: dict, recorded: str | None) -> tuple[str, list[str]]:
    """(snapshot id, problems)."""
    problems = []
    snapshot = (answer.get("snapshot") or {}).get("snapshot_id")
    if not snapshot or not answer.get("data"):
        return "", ["the answer has no snapshot or no data"]
    if rows(answer["data"]["rows"]) != rows(json.loads(C1.read_text())["rows"]):
        problems.append("the rows differ from the nine I2 §8.1 rows")
    if recorded is not None and snapshot != recorded:
        problems.append(f"snapshot {snapshot} differs from the recorded {recorded}")
    return snapshot, problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0])
    recorded = path.read_text().strip() if path.exists() else None
    snapshot, problems = check(json.load(sys.stdin), recorded)
    for problem in problems:
        print(f"STOP: {problem}", file=sys.stderr)
    if problems:
        return 2
    if recorded is None:
        path.write_text(snapshot + "\n")
        print(f"AIP: nine rows; snapshot {snapshot} recorded")
    else:
        print(f"AIP: nine rows; snapshot {snapshot} unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
