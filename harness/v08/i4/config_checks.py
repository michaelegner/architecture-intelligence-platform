"""v0.8 I4 §5: checks on the MirrorMaker 2 configuration that the agent applied, in place of the I3
preflight. The agent is not told about them. The operator reads each flow's properties file from
its running container in S4 (dedicated mode, `connect-mirror-maker.sh <file>`).

- `static FILE...`: per enabled replication pair (`A->B.enabled=true`):
  - P1a: every internal topic the pair creates gets replication factor 1. MirrorMaker 2's defaults
    are 2 or 3, which a single-node cluster cannot hold, so an unset key fails;
  - P2: checkpoints and offset-syncs are on, and the replication policy keeps topic names;
  - P3: no topic is mirrored in both directions (an allow-list that is a pattern overlaps any topic);
  - it writes the applied allow-lists for Proof A (K5) and the derived internal topics for `p1b`.
- `p1b --static OUT --pair A->B KAFKA_LISTING REDPANDA_LISTING`: the pair's internal topics exist
  with replication factor 1 on the live clusters.

A key is looked up as MirrorMaker 2 does: `A->B.<key>`, then `<target>.<key>` (worker keys are
target-prefixed in dedicated mode), then `<key>`. A file this script cannot read as dedicated-mode
properties stops it: the operator then records the verdicts by hand, and the owner is asked.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from _i3 import checker

IDENTITY = "org.apache.kafka.connect.mirror.IdentityReplicationPolicy"
DEFAULTS = {"emit.checkpoints.enabled": "true", "emit.offset-syncs.enabled": "true"}
RF_ALWAYS = (
    "replication.factor",
    "checkpoints.topic.replication.factor",
    "offset-syncs.topic.replication.factor",
    "config.storage.replication.factor",
    "offset.storage.replication.factor",
    "status.storage.replication.factor",
)
HEARTBEATS_RF = "heartbeats.topic.replication.factor"
PATTERN = re.compile(r"[*?+\[\]()|^$]")


class NotDedicatedMode(SystemExit):
    def __init__(self, path: Path, why: str):
        super().__init__(f"STOP: {path}: {why}; record the verdicts by hand and ask the owner")


# The task card's addresses of the two brokers (in-network and from the host).
ADDRESSES = {
    "redpanda": {"redpanda:29092", "localhost:9092", "127.0.0.1:9092"},
    "kafka": {"kafka:29092", "localhost:19092", "127.0.0.1:19092"},
}


def broker_of(bootstrap: str) -> str | None:
    addresses = {part.strip() for part in bootstrap.split(",") if part.strip()}
    for broker, known in ADDRESSES.items():
        if addresses and addresses <= known:
            return broker
    return None


def lookup(props: dict[str, str], source: str, target: str, key: str) -> str | None:
    for candidate in (f"{source}->{target}.{key}", f"{target}.{key}", key):
        if candidate in props:
            return props[candidate]
    return DEFAULTS.get(key)


def pairs(path: Path) -> list[dict]:
    props = checker.read_properties(path)
    if "clusters" not in props:
        raise NotDedicatedMode(path, "no clusters= line")
    aliases = [a.strip() for a in props["clusters"].split(",") if a.strip()]
    brokers = {}
    for alias in aliases:
        bootstrap = props.get(f"{alias}.bootstrap.servers")
        broker = broker_of(bootstrap) if bootstrap else None
        if broker is None:
            raise NotDedicatedMode(path, f"cluster {alias!r} has no recognised bootstrap address")
        brokers[alias] = broker
    found = []
    for source in aliases:
        for target in aliases:
            if source == target or props.get(f"{source}->{target}.enabled") != "true":
                continue
            found.append(
                {
                    "file": str(path),
                    "props": props,
                    "source_alias": source,
                    "target_alias": target,
                    "source": brokers[source],
                    "target": brokers[target],
                }
            )
    return found


def named_topics(pair: dict) -> dict[str, str]:
    """The internal topics a pair creates, by role (MirrorMaker 2 defaults, or the names the file
    sets), and where the offset syncs live."""
    props, source, target = pair["props"], pair["source_alias"], pair["target_alias"]

    def named(key: str, default: str) -> str:
        return lookup(props, source, target, key) or default

    return {
        "configs": named("config.storage.topic", f"mm2-configs.{source}.internal"),
        "offsets": named("offset.storage.topic", f"mm2-offsets.{source}.internal"),
        "status": named("status.storage.topic", f"mm2-status.{source}.internal"),
        "checkpoints": f"{source}.checkpoints.internal",
        "offset_syncs": f"mm2-offset-syncs.{target}.internal",
        "offset_syncs_on": lookup(props, source, target, "offset-syncs.topic.location") or "source",
    }


def internal_topics(pair: dict) -> dict[str, list[str]]:
    """The internal topics a pair creates, by the cluster that holds them."""
    names = named_topics(pair)
    on_target = [names[k] for k in ("configs", "offsets", "status", "checkpoints")]
    if (
        lookup(pair["props"], pair["source_alias"], pair["target_alias"], "emit.heartbeats.enabled")
        != "false"
    ):
        on_target.append("heartbeats")
    syncs_on_source = names["offset_syncs_on"] == "source"
    return {
        "target": sorted(on_target + ([] if syncs_on_source else [names["offset_syncs"]])),
        "source": [names["offset_syncs"]] if syncs_on_source else [],
    }


def check_pair(pair: dict) -> list[str]:
    props, source, target = pair["props"], pair["source_alias"], pair["target_alias"]
    problems = []
    rf_keys = list(RF_ALWAYS)
    if lookup(props, source, target, "emit.heartbeats.enabled") != "false":
        rf_keys.append(HEARTBEATS_RF)
    for key in rf_keys:
        value = lookup(props, source, target, key)
        if value != "1":
            problems.append(f"P1a {source}->{target}: {key} is {value or 'unset (default > 1)'}")
    for key in DEFAULTS:
        if lookup(props, source, target, key) != "true":
            problems.append(f"P2 {source}->{target}: {key} is not true")
    if lookup(props, source, target, "replication.policy.class") != IDENTITY:
        problems.append(f"P2 {source}->{target}: the replication policy renames topics")
    return problems


def allow_list(pair: dict) -> list[str]:
    value = lookup(pair["props"], pair["source_alias"], pair["target_alias"], "topics") or ".*"
    return checker.topic_list(value)


def check_static(paths: list[Path]) -> dict:
    found = [pair for path in paths for pair in pairs(path)]
    problems = [problem for pair in found for problem in check_pair(pair)]
    lists = [
        {
            "flow": f"{Path(p['file']).name}:{p['source_alias']}->{p['target_alias']}",
            "source": p["source"],
            "target": p["target"],
            "topics": allow_list(p),
        }
        for p in found
    ]
    there = [
        t for f in lists if (f["source"], f["target"]) == ("redpanda", "kafka") for t in f["topics"]
    ]
    back = [
        t for f in lists if (f["source"], f["target"]) == ("kafka", "redpanda") for t in f["topics"]
    ]
    patterns = [t for t in there + back if PATTERN.search(t)]
    overlap = sorted(set(there) & set(back))
    if overlap or (patterns and there and back):
        problems.append(f"P3: mirrored in both directions: {overlap or patterns}")
    if not found:
        problems.append("no enabled replication pair")
    return checker.verdict(
        "applied-mm2",
        "P1a replication factor 1, P2 checkpoints/offset-syncs/identity policy, P3 disjoint",
        checker.FAILED if problems else checker.PASSED,
        [str(p) for p in paths],
        problems=problems,
        allow_lists=lists,
        internal_topics={
            f"{p['source_alias']}->{p['target_alias']}": internal_topics(p) for p in found
        },
        pairs=[
            {
                "pair": f"{p['source_alias']}->{p['target_alias']}",
                "source": p["source"],
                "target": p["target"],
                "topics": allow_list(p),
                **named_topics(p),
            }
            for p in found
        ],
    )


def check_p1b(static: dict, pair: str, kafka_listing: Path, redpanda_listing: Path) -> dict:
    flow = next(f for f in static["allow_lists"] if f["flow"].endswith(f":{pair}"))
    topics = static["internal_topics"][pair]
    listings = {
        "kafka": checker.kafka_topic_rf(kafka_listing.read_text()),
        "redpanda": checker.rpk_topic_rf(redpanda_listing.read_text()),
    }
    problems = [
        f"{topic} on {flow[role]}: "
        + ("missing" if topic not in listings[flow[role]] else f"RF {listings[flow[role]][topic]}")
        for role in ("target", "source")
        for topic in topics[role]
        if listings[flow[role]].get(topic) != 1
    ]
    return checker.verdict(
        "applied-p1b",
        "every internal topic of the pair exists with replication factor 1",
        checker.FAILED if problems else checker.PASSED,
        [str(kafka_listing), str(redpanda_listing)],
        pair=pair,
        problems=problems,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    static = sub.add_parser("static")
    static.add_argument("files", type=Path, nargs="+")
    p1b = sub.add_parser("p1b")
    p1b.add_argument("--static", type=Path, required=True)
    p1b.add_argument("--pair", required=True)
    p1b.add_argument("kafka_listing", type=Path)
    p1b.add_argument("redpanda_listing", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "static":
        result = check_static(args.files)
    else:
        result = check_p1b(
            json.loads(args.static.read_text()),
            args.pair,
            args.kafka_listing,
            args.redpanda_listing,
        )
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"{result['kind']}: {result['result']}")
    return checker.EXIT[result["result"]]


if __name__ == "__main__":
    sys.exit(main())
