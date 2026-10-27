"""v0.8 I3 (spec §4-§5): turns the recorded raw/ output of the preflight and the runbook into verdicts.

Standard library only. Every rule returns one verdict - PASSED, PENDING or FAILED - with its inputs,
the rule text and the raw/ files it read. A rule that waits on MirrorMaker 2 (replication, a
checkpoint, an installed group offset) is PENDING until its deadline and FAILED after it, so a
pending sync never reads as a failed one. Offsets are compared only inside one cluster's coordinate
system; identities (group, topic, partition) are matched exactly, never by position.

Exit code: 0 PASSED, 3 PENDING, 2 FAILED. `collect` merges the verdict files into checks.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PASSED, PENDING, FAILED = "PASSED", "PENDING", "FAILED"
EXIT = {PASSED: 0, PENDING: 3, FAILED: 2}
INTERVAL_KEYS = (
    "refresh.topics.interval.seconds",
    "refresh.groups.interval.seconds",
    "emit.checkpoints.interval.seconds",
    "sync.group.offsets.interval.seconds",
)
RF_KEYS = (
    "replication.factor",
    "checkpoints.topic.replication.factor",
    "offset-syncs.topic.replication.factor",
    "heartbeats.topic.replication.factor",
    "config.storage.replication.factor",
    "offset.storage.replication.factor",
    "status.storage.replication.factor",
)
MAX_INTERVAL_SECONDS = 30
# Kafka Connect commits the source offsets that the replication checks read every
# offset.flush.interval.ms (default 60 000 ms, past the 40 s deadline), so each flow sets it. The
# dedicated MM2 worker takes it only target-prefixed (`<target>.offset.flush.interval.ms`): at
# 4.1.2, MirrorMakerConfig.workerConfig forwards a bare top-level key only for a fixed prefix list.
FLUSH_KEY = "offset.flush.interval.ms"
FLUSH_MS = "10000"

# I3 spec §3 Connect worker-state table: flow -> (source alias, target alias, internal topics on the
# target, offset-syncs topic on the source). The checkpoints topic is "<source>.checkpoints.internal".
WORKER_STATE = {
    "mm2-flow-a": ("redpanda", "kafka"),
    "mm2-flow-b": ("kafka", "redpanda"),
    "mm2-probe": ("rpprobe", "kprobe"),
}
SYNCING_FLOWS = {"mm2-flow-a", "mm2-probe"}


def internal_topics(flow: str) -> dict[str, list[str]]:
    """The internal topics of one flow, by the cluster role that holds them."""
    source, target = WORKER_STATE[flow]
    return {
        "target": [
            f"{flow}-configs",
            f"{flow}-offsets",
            f"{flow}-status",
            f"{source}.checkpoints.internal",
        ],
        "source": [f"mm2-offset-syncs.{target}.internal"],
    }


def read_properties(path: Path) -> dict[str, str]:
    props = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        props[key.strip()] = value.strip().replace("\\\\", "\\")
    return props


def topic_list(value: str) -> list[str]:
    """A MirrorMaker 2 topic allow-list: comma-separated, regex-escaped dots."""
    return sorted(item.strip().replace("\\.", ".") for item in value.split(",") if item.strip())


def verdict(kind: str, rule: str, result: str, sources: list[str], **details) -> dict:
    return {"kind": kind, "rule": rule, "result": result, "sources": sorted(sources), **details}


def timed(all_passed: bool, failed_now: bool, elapsed: int | None, deadline: int | None) -> str:
    """PASSED; FAILED on a definite failure; otherwise PENDING until the deadline, then FAILED."""
    if all_passed:
        return PASSED
    if failed_now or elapsed is None or deadline is None or elapsed >= deadline:
        return FAILED
    return PENDING


# --- Preflight -------------------------------------------------------------------------------------


def check_p1a(paths: list[Path]) -> dict:
    """P1a/P2: every flow file sets the worker state of the §3 table, RF 1 everywhere (mirrored data
    topics included), the identity policy, checkpoints and offset-syncs on, heartbeats off, and short
    explicit intervals; flow A and the probe sync group offsets, flow B does not."""
    problems = []
    for path in paths:
        flow = path.stem
        props = read_properties(path)
        source, target = WORKER_STATE[flow]
        expected = {
            "clusters": f"{source}, {target}",
            f"{source}->{target}.enabled": "true",
            f"{target}->{source}.enabled": "false",
            f"{target}.group.id": flow,
            "config.storage.topic": f"{flow}-configs",
            "offset.storage.topic": f"{flow}-offsets",
            "status.storage.topic": f"{flow}-status",
            "replication.policy.class": (
                "org.apache.kafka.connect.mirror.IdentityReplicationPolicy"
            ),
            "emit.checkpoints.enabled": "true",
            "emit.offset-syncs.enabled": "true",
            "emit.heartbeats.enabled": "false",
            "sync.group.offsets.enabled": "true" if flow in SYNCING_FLOWS else "false",
            **dict.fromkeys(RF_KEYS, "1"),
            f"{target}.{FLUSH_KEY}": FLUSH_MS,
        }
        for key, value in expected.items():
            if props.get(key) != value:
                problems.append(f"{flow}: {key} must be {value!r}")
        if FLUSH_KEY in props:
            problems.append(
                f"{flow}: a bare {FLUSH_KEY} never reaches the worker; set {target}.{FLUSH_KEY}"
            )
        for key in INTERVAL_KEYS:
            if not props.get(key, "").isdigit() or not 0 < int(props[key]) <= MAX_INTERVAL_SECONDS:
                problems.append(f"{flow}: {key} must be set explicitly, 1-{MAX_INTERVAL_SECONDS} s")
    return verdict(
        "p1a",
        "worker state, replication factor 1, identity policy, flags and intervals per §3",
        FAILED if problems else PASSED,
        [str(p) for p in paths],
        problems=problems,
    )


def check_p3(flow_a: Path, flow_b: Path) -> dict:
    """P3: the flow A and flow B topic allow-lists are disjoint (no loops, parent §4.1)."""
    a = topic_list(read_properties(flow_a)["redpanda->kafka.topics"])
    b = topic_list(read_properties(flow_b)["kafka->redpanda.topics"])
    overlap = sorted(set(a) & set(b))
    return verdict(
        "p3",
        "flow A and flow B topic allow-lists are disjoint",
        FAILED if overlap else PASSED,
        [str(flow_a), str(flow_b)],
        flow_a_topics=a,
        flow_b_topics=b,
        overlap=overlap,
    )


def kafka_topic_rf(text: str) -> dict[str, int]:
    """`kafka-topics.sh --describe` summary lines: Topic: X ... ReplicationFactor: N."""
    found = {}
    for line in text.splitlines():
        match = re.search(r"Topic:\s*(\S+).*?ReplicationFactor:\s*(\d+)", line)
        if match and "Partition:" not in line:
            found[match[1]] = int(match[2])
    return found


def rpk_topic_rf(text: str) -> dict[str, int]:
    """`rpk topic list` table: NAME PARTITIONS REPLICAS."""
    found = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 3 and parts[2].isdigit():
            found[parts[0]] = int(parts[2])
    return found


def check_p1b(
    flow: str,
    target_listing: Path,
    source_listing: Path,
    target_kind: str,
    elapsed: int | None = None,
    deadline: int | None = None,
) -> dict:
    """P1b: after the flow's first start, every internal topic of the flow exists on its cluster with
    replication factor 1. MirrorMaker 2 creates the topics after the worker starts, so a missing
    topic is PENDING until the deadline; an observed wrong replication factor fails at once."""
    parse = {"kafka": kafka_topic_rf, "redpanda": rpk_topic_rf}
    source_kind = "redpanda" if target_kind == "kafka" else "kafka"
    on_target = parse[target_kind](target_listing.read_text())
    on_source = parse[source_kind](source_listing.read_text())
    topics = internal_topics(flow)
    problems = [
        f"{topic} on the {role}: {'missing' if topic not in listing else 'RF ' + str(listing[topic])}"
        for role, listing in (("target", on_target), ("source", on_source))
        for topic in topics[role]
        if listing.get(topic) != 1
    ]
    wrong_rf = any("RF " in problem for problem in problems)
    return verdict(
        "p1b",
        "every internal topic of the flow exists with replication factor 1",
        timed(not problems, wrong_rf, elapsed, deadline),
        [str(target_listing), str(source_listing)],
        flow=flow,
        problems=problems,
    )


# --- Runbook checks ---------------------------------------------------------------------------------


def connect_offsets(text: str) -> dict[tuple[str, int], int]:
    """The last replicated source offset per (topic, partition) from a dump of the flow's Connect
    offsets topic (`print.key=true`, tab-separated). The latest record per key wins."""
    found: dict[tuple[str, int], int] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("\t")
        if not sep or not value.strip() or value.strip() == "null":
            continue
        try:
            connector, partition = json.loads(key)
            offset = json.loads(value)["offset"]
        except (ValueError, KeyError, TypeError):
            continue
        if connector == "MirrorSourceConnector":
            found[(partition["topic"], int(partition["partition"]))] = int(offset)
    return found


def end_offsets(text: str, fmt: str) -> dict[tuple[str, int], int]:
    """Source end offsets: `rpk topic describe -p <topic>` (per partition HIGH-WATERMARK, with the
    topic given in a leading `# topic: X` line written by the step) or `kafka-get-offsets.sh`
    (`topic:partition:offset`)."""
    found = {}
    if fmt == "kafka":
        for line in text.splitlines():
            parts = line.strip().rsplit(":", 2)
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                found[(parts[0], int(parts[1]))] = int(parts[2])
        return found
    topic, header = None, None
    for line in text.splitlines():
        if line.startswith("# topic:"):
            topic, header = line.split(":", 1)[1].strip(), None
            continue
        cells = line.split()
        if cells and cells[0] == "PARTITION":
            header = cells
            continue
        if topic and header and cells and cells[0].isdigit():
            row = dict(zip(header, cells, strict=False))
            found[(topic, int(row["PARTITION"]))] = int(row["HIGH-WATERMARK"])
    return found


def check_replication(
    offsets: Path, source_end: Path, fmt: str, topics: list[str], elapsed, deadline
) -> dict:
    """Replication caught up: for every source partition of the topics, the flow's last replicated
    source offset + 1 equals the source end offset (or the partition is empty). Source side only."""
    replicated = connect_offsets(offsets.read_text())
    ends = end_offsets(source_end.read_text(), fmt)
    partitions = []
    for (topic, partition), end in sorted(ends.items()):
        if topic not in topics:
            continue
        last = replicated.get((topic, partition))
        caught_up = end == 0 or (last is not None and last + 1 == end)
        partitions.append(
            {
                "topic": topic,
                "partition": partition,
                "end": end,
                "last_replicated": last,
                "caught_up": caught_up,
            }
        )
    missing = sorted(set(topics) - {p["topic"] for p in partitions})
    result = timed(
        bool(partitions) and not missing and all(p["caught_up"] for p in partitions),
        bool(missing),
        elapsed,
        deadline,
    )
    return verdict(
        "replication",
        "last replicated source offset + 1 = source end offset, per source partition",
        result,
        [str(offsets), str(source_end)],
        partitions=partitions,
        missing_topics=missing,
        elapsed=elapsed,
        deadline=deadline,
    )


def group_sections(text: str) -> dict[str, list[str]]:
    """Split a describe output into per-group sections (`GROUP <name>` headers for rpk; the GROUP
    column for kafka-consumer-groups)."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        cells = line.split()
        if len(cells) >= 2 and cells[0] == "GROUP" and cells[1] != "TOPIC":
            current = cells[1]
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def group_rows(text: str, fmt: str) -> dict[str, dict]:
    """{group: {"state": str | None, "rows": {(topic, partition): {"current": int|None, "lag": int|None}}}}"""
    groups: dict[str, dict] = {}
    if fmt == "kafka":
        header = None
        state_header = None
        for line in text.splitlines():
            cells = line.split()
            if cells[:2] == ["GROUP", "TOPIC"]:
                header, state_header = cells, None
                continue
            if cells[:2] == ["GROUP", "COORDINATOR"] and "STATE" in cells:
                # `kafka-consumer-groups.sh --describe --state`: one row per group.
                state_header, header = cells, None
                continue
            if state_header and len(cells) >= 3 and cells[-1].isdigit():
                # STATE and #MEMBERS are always the last two cells; an Empty group's blank
                # assignment strategy makes the row shorter than the header.
                groups.setdefault(cells[0], {"state": None, "rows": {}})["state"] = cells[-2]
                continue
            if header and len(cells) >= len(header) - 3 and cells[2].isdigit():
                row = dict(zip(header, cells, strict=False))
                entry = groups.setdefault(row["GROUP"], {"state": None, "rows": {}})
                entry["rows"][(row["TOPIC"], int(row["PARTITION"]))] = {
                    "current": _int(row.get("CURRENT-OFFSET")),
                    "lag": _int(row.get("LAG")),
                }
            match = re.search(r"Consumer group '([^']+)' has no active members", line)
            if match:
                groups.setdefault(match[1], {"state": None, "rows": {}})["state"] = "Empty"
        return groups
    for group, lines in group_sections(text).items():
        entry = {"state": None, "rows": {}}
        header = None
        for line in lines:
            cells = line.split()
            if cells and cells[0] == "STATE" and len(cells) > 1:
                entry["state"] = cells[1]
            elif cells and cells[0] == "TOPIC":
                header = cells
            elif header and len(cells) >= 2 and cells[1].isdigit():
                row = dict(zip(header, cells, strict=False))
                entry["rows"][(row["TOPIC"], int(row["PARTITION"]))] = {
                    "current": _int(row.get("CURRENT-OFFSET")),
                    "lag": _int(row.get("LAG")),
                }
        groups[group] = entry
    return groups


def _int(value: str | None) -> int | None:
    return int(value) if value is not None and value.lstrip("-").isdigit() else None


def check_lag(describe: Path, fmt: str, group: str, topics: list[str], elapsed, deadline) -> dict:
    """Consumer caught up: the named group has lag 0 on every partition of each named topic."""
    rows = group_rows(describe.read_text(), fmt).get(group, {"rows": {}})["rows"]
    partitions = [
        {"topic": t, "partition": p, **values}
        for (t, p), values in sorted(rows.items())
        if t in topics
    ]
    missing = sorted(set(topics) - {p["topic"] for p in partitions})
    result = timed(
        bool(partitions) and not missing and all(p["lag"] == 0 for p in partitions),
        False,
        elapsed,
        deadline,
    )
    return verdict(
        "lag",
        "lag 0 for the group on every partition of each topic",
        result,
        [str(describe)],
        group=group,
        partitions=partitions,
        missing_topics=missing,
        elapsed=elapsed,
        deadline=deadline,
    )


def check_state(
    describe: Path,
    fmt: str,
    groups: list[str],
    allowed: list[str],
    elapsed: int | None = None,
    deadline: int | None = None,
) -> dict:
    """Group state: each group reads one of the allowed states (e.g. Empty or Dead after the move).
    A state change takes time (session timeout, rebalance), so another reading is PENDING until the
    deadline; a group missing from the describe output fails at once."""
    found = group_rows(describe.read_text(), fmt)
    states = {g: found.get(g, {}).get("state") for g in groups}
    bad = sorted(g for g, s in states.items() if s not in allowed)
    missing = any(states[g] is None for g in bad)
    return verdict(
        "state",
        f"each group's state is one of {allowed}",
        timed(not bad, missing, elapsed, deadline),
        [str(describe)],
        states=states,
        not_allowed=bad,
    )


BROKERS_CHANGE = ('brokers: "redpanda:29092"', 'brokers: "kafka:29092"')


def check_configmap(live: Path, rendered: Path) -> dict:
    """Step 8: the rendered ConfigMap replaces the one the deployment mounts (same name and
    namespace), and the only changed line is kafka.brokers redpanda:29092 -> kafka:29092. Both
    inputs are kubectl JSON (`get -o json`; `create --dry-run=client -o json`)."""
    problems = []
    try:
        old, new = json.loads(live.read_text()), json.loads(rendered.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        old, new = {}, {}
        problems.append(f"unreadable input: {type(exc).__name__}")
    changed = []
    if not problems:
        for key in ("name", "namespace"):
            if old.get("metadata", {}).get(key) != new.get("metadata", {}).get(key):
                problems.append(f"metadata.{key} differs")
        old_data, new_data = old.get("data") or {}, new.get("data") or {}
        if set(old_data) != set(new_data):
            problems.append("the data keys differ")
        for key in sorted(set(old_data) & set(new_data)):
            before, after = old_data[key].splitlines(), new_data[key].splitlines()
            if len(before) != len(after):
                problems.append(f"{key}: the line count differs")
                continue
            changed += [
                (b.strip(), a.strip()) for b, a in zip(before, after, strict=True) if b != a
            ]
        if changed != [BROKERS_CHANGE]:
            problems.append(f"changed lines {changed}, expected only {list(BROKERS_CHANGE)}")
    return verdict(
        "configmap",
        "same ConfigMap identity; the only changed line is kafka.brokers -> kafka:29092",
        FAILED if problems else PASSED,
        [str(live), str(rendered)],
        problems=problems,
    )


def _tp(value: str) -> tuple[str, int]:
    topic, _, partition = value.rpartition("-")
    return topic, int(partition)


def checkpoints(text: str) -> dict[tuple[str, str, int], tuple[int, int]]:
    """The latest checkpoint per (group, topic, partition): CheckpointFormatter lines."""
    found = {}
    pattern = re.compile(
        r"consumerGroupId=([^,]+), topicPartition=([^,]+), upstreamOffset=(\d+), "
        r"downstreamOffset=(\d+)"
    )
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            topic, partition = _tp(match[2])
            found[(match[1], topic, partition)] = (int(match[3]), int(match[4]))
    return found


def offset_syncs(text: str) -> dict[tuple[str, int], list[tuple[int, int]]]:
    """All offset syncs per (topic, partition), sorted by upstream offset: OffsetSyncFormatter."""
    found: dict[tuple[str, int], list[tuple[int, int]]] = {}
    pattern = re.compile(r"topicPartition=([^,]+), upstreamOffset=(\d+), downstreamOffset=(\d+)")
    for line in text.splitlines():
        match = pattern.search(line)
        if match:
            found.setdefault(_tp(match[1]), []).append((int(match[2]), int(match[3])))
    return {key: sorted(set(values)) for key, values in found.items()}


def replay_amount(a: int, c: int | None, syncs: list[tuple[int, int]]) -> dict:
    """Records that may be reprocessed: between the installed downstream offset (c) and the downstream
    position that corresponds to the final upstream offset (a). Measured when a sync has upstream
    exactly (a); an upper estimate from the next sync above (a); otherwise no bound (I3 §5)."""
    if c is None:
        return {"kind": "NO_BOUND", "reason": "no installed downstream offset"}
    exact = [down for up, down in syncs if up == a]
    if exact:
        return {"kind": "MEASURED", "records": max(exact[-1] - c, 0)}
    above = [down for up, down in syncs if up > a]
    if above:
        return {"kind": "UPPER_ESTIMATE", "records": max(min(above) - c, 0)}
    return {"kind": "NO_BOUND", "reason": "no offset sync at or above the final upstream offset"}


def check_handoff(
    source_groups: Path,
    checkpoint_dump: Path,
    target_groups: Path,
    sync_dump: Path,
    groups: list[str],
    topic: str,
    elapsed,
    deadline,
) -> dict:
    """Step 6, per group and partition of the topic: the checkpoint's upstream offset equals (a), the
    final committed offset on the source, and (c), the committed offset installed on the target,
    equals the checkpoint's downstream offset. Only an exact (group, topic, partition) match counts."""
    source = group_rows(source_groups.read_text(), "rpk")
    target = group_rows(target_groups.read_text(), "kafka")
    points = checkpoints(checkpoint_dump.read_text())
    syncs = offset_syncs(sync_dump.read_text())
    entries = []
    definite_failure = False
    for group in groups:
        rows = {k: v for k, v in source.get(group, {"rows": {}})["rows"].items() if k[0] == topic}
        if not rows:
            definite_failure = True
            entries.append({"group": group, "problem": "no committed source offset for the topic"})
        for (t, partition), values in sorted(rows.items()):
            a = values["current"]
            cp = points.get((group, t, partition))
            c_row = target.get(group, {"rows": {}})["rows"].get((t, partition))
            c = c_row["current"] if c_row else None
            ok = cp is not None and a is not None and cp[0] == a and c is not None and c == cp[1]
            if cp is not None and c is not None and c != cp[1] and cp[0] == a:
                definite_failure = True  # an installed offset that differs could skip records
            entries.append(
                {
                    "group": group,
                    "topic": t,
                    "partition": partition,
                    "a": a,
                    "checkpoint": {"upstream": cp[0], "downstream": cp[1]} if cp else None,
                    "c": c,
                    "passed": ok,
                    "replay": replay_amount(a, c, syncs.get((t, partition), []))
                    if a is not None
                    else {"kind": "NO_BOUND", "reason": "no final upstream offset"},
                }
            )
    result = timed(
        bool(entries) and all(e.get("passed") for e in entries),
        definite_failure,
        elapsed,
        deadline,
    )
    return verdict(
        "handoff",
        "checkpoint upstream = (a) and (c) = checkpoint downstream, per group and partition",
        result,
        [str(source_groups), str(checkpoint_dump), str(target_groups), str(sync_dump)],
        topic=topic,
        entries=entries,
        elapsed=elapsed,
        deadline=deadline,
    )


def collect(raw: Path) -> dict:
    checks = []
    for path in sorted(raw.glob("*.check.json")):
        checks.append({"id": path.name.removesuffix(".check.json"), **json.loads(path.read_text())})
    return {"schema": "aip-v08-i3-checks/1", "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="rule", required=True)

    def add(name: str, timed_rule: bool = False):
        cmd = sub.add_parser(name)
        cmd.add_argument("--out", type=Path)
        cmd.add_argument("--elapsed", type=int)
        cmd.add_argument("--deadline", type=int)
        return cmd

    p = add("p1a")
    p.add_argument("properties", nargs="+", type=Path)
    p = add("p3")
    p.add_argument("flow_a", type=Path)
    p.add_argument("flow_b", type=Path)
    p = add("p1b")
    p.add_argument("--flow", required=True, choices=sorted(WORKER_STATE))
    p.add_argument("--target-listing", required=True, type=Path)
    p.add_argument("--source-listing", required=True, type=Path)
    p.add_argument("--target-kind", required=True, choices=["kafka", "redpanda"])
    p = add("replication")
    p.add_argument("--offsets", required=True, type=Path)
    p.add_argument("--source-end", required=True, type=Path)
    p.add_argument("--format", required=True, choices=["rpk", "kafka"])
    p.add_argument("--topic", action="append", required=True)
    p = add("lag")
    p.add_argument("--describe", required=True, type=Path)
    p.add_argument("--format", required=True, choices=["rpk", "kafka"])
    p.add_argument("--group", required=True)
    p.add_argument("--topic", action="append", required=True)
    p = add("state")
    p.add_argument("--describe", required=True, type=Path)
    p.add_argument("--format", required=True, choices=["rpk", "kafka"])
    p.add_argument("--group", action="append", required=True)
    p.add_argument("--allow", action="append", required=True)
    p = add("handoff")
    p.add_argument("--source-groups", required=True, type=Path)
    p.add_argument("--checkpoints", required=True, type=Path)
    p.add_argument("--target-groups", required=True, type=Path)
    p.add_argument("--offset-syncs", required=True, type=Path)
    p.add_argument("--group", action="append", required=True)
    p.add_argument("--topic", required=True)
    p = add("configmap")
    p.add_argument("--live", required=True, type=Path)
    p.add_argument("--rendered", required=True, type=Path)
    p = sub.add_parser("collect")
    p.add_argument("raw", type=Path)
    p.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.rule == "collect":
        args.out.write_text(json.dumps(collect(args.raw), indent=2, sort_keys=True) + "\n")
        return 0
    result = {
        "p1a": lambda: check_p1a(args.properties),
        "p3": lambda: check_p3(args.flow_a, args.flow_b),
        "p1b": lambda: check_p1b(
            args.flow,
            args.target_listing,
            args.source_listing,
            args.target_kind,
            args.elapsed,
            args.deadline,
        ),
        "replication": lambda: check_replication(
            args.offsets, args.source_end, args.format, args.topic, args.elapsed, args.deadline
        ),
        "lag": lambda: check_lag(
            args.describe, args.format, args.group, args.topic, args.elapsed, args.deadline
        ),
        "configmap": lambda: check_configmap(args.live, args.rendered),
        "state": lambda: check_state(
            args.describe, args.format, args.group, args.allow, args.elapsed, args.deadline
        ),
        "handoff": lambda: check_handoff(
            args.source_groups,
            args.checkpoints,
            args.target_groups,
            args.offset_syncs,
            args.group,
            args.topic,
            args.elapsed,
            args.deadline,
        ),
    }[args.rule]()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        sys.stdout.write(text)
    return EXIT[result["result"]]


if __name__ == "__main__":
    raise SystemExit(main())
