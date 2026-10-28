"""v0.8 I4 §6 and report column 4: the offset hand-off, read after the wave (owner decision on the
I4a plan).

The offset that MirrorMaker 2 installed on Kafka, (c), is overwritten as soon as the moved services
commit there, so the operator cannot read it in S4. (c) therefore comes from the agent's transcript,
labelled `agent-reported`, transcribed by the operator into a small file:

    [{"group": ..., "topic": ..., "partition": 0, "c": 1, "transcript": "<session> line <n>"}]

Next to it stand the operator's own S4 reads, each with its source: (a), the final committed offset
on Redpanda; every checkpoint for the group and partition (upstream, downstream); the offset syncs;
and the group's current position on Kafka. The relations that can still be checked are:

- some checkpoint has upstream = (a) and downstream = the agent-reported (c);
- the current Kafka position >= that downstream offset.

Replication progress and consumer lag use the I3 checker unchanged (`replication`, `lag`).
"""

import argparse
import json
import re
import sys
from pathlib import Path

from _i3 import checker

CHECKPOINT = re.compile(
    r"consumerGroupId=([^,]+), topicPartition=([^,]+), upstreamOffset=(\d+), downstreamOffset=(\d+)"
)


def checkpoint_history(text: str) -> dict[tuple[str, str, int], list[tuple[int, int]]]:
    """Every checkpoint per (group, topic, partition), sorted (the I3 parser keeps the latest only)."""
    found: dict[tuple[str, str, int], list[tuple[int, int]]] = {}
    for line in text.splitlines():
        match = CHECKPOINT.search(line)
        if match:
            topic, partition = checker._tp(match[2])
            found.setdefault((match[1], topic, partition), []).append(
                (int(match[3]), int(match[4]))
            )
    return {key: sorted(set(values)) for key, values in found.items()}


def check_handoff_after(
    agent_reported: Path,
    source_groups: Path,
    checkpoint_dump: Path,
    target_groups: Path,
    sync_dump: Path,
) -> dict:
    reported = json.loads(agent_reported.read_text())
    source = checker.group_rows(source_groups.read_text(), "rpk")
    target = checker.group_rows(target_groups.read_text(), "kafka")
    history = checkpoint_history(checkpoint_dump.read_text())
    syncs = checker.offset_syncs(sync_dump.read_text())
    entries = []
    for entry in reported:
        group, topic, partition, c = entry["group"], entry["topic"], entry["partition"], entry["c"]
        a_row = source.get(group, {"rows": {}})["rows"].get((topic, partition))
        a = a_row["current"] if a_row else None
        points = history.get((group, topic, partition), [])
        now_row = target.get(group, {"rows": {}})["rows"].get((topic, partition))
        now = now_row["current"] if now_row else None
        matching = [down for up, down in points if up == a and down == c]
        entries.append(
            {
                "group": group,
                "topic": topic,
                "partition": partition,
                "a": {"value": a, "source": str(source_groups)},
                "c": {"value": c, "source": f"agent-reported ({entry.get('transcript', '?')})"},
                "checkpoints": {"values": points, "source": str(checkpoint_dump)},
                "kafka_position_now": {"value": now, "source": str(target_groups)},
                "checkpoint_matches": bool(matching),
                "position_not_behind": now is not None and now >= c,
                "replay": checker.replay_amount(a, c, syncs.get((topic, partition), []))
                if a is not None
                else {"kind": "NO_BOUND", "reason": "no final upstream offset"},
            }
        )
    passed = bool(entries) and all(
        e["checkpoint_matches"] and e["position_not_behind"] for e in entries
    )
    return checker.verdict(
        "handoff-after",
        "a checkpoint has upstream (a) and downstream = agent-reported (c); Kafka position >= (c)",
        checker.PASSED if passed else checker.FAILED,
        [str(agent_reported), str(source_groups), str(checkpoint_dump), str(target_groups)],
        entries=entries,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--agent-reported", type=Path, required=True)
    parser.add_argument("--source-groups", type=Path, required=True)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--target-groups", type=Path, required=True)
    parser.add_argument("--offset-syncs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = check_handoff_after(
        args.agent_reported,
        args.source_groups,
        args.checkpoints,
        args.target_groups,
        args.offset_syncs,
    )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"handoff-after: {result['result']}")
    return checker.EXIT[result["result"]]


if __name__ == "__main__":
    sys.exit(main())
