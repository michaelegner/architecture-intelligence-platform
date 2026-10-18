"""Pure normalization of described consumer groups into the `aip-kafka-consumer-state/1` envelope
(I1.1 contract §3, §4). No Kafka client and no I/O here, so it is testable without a broker. Only
schema fields are ever copied, so a credential or security property cannot enter the capture, and
an acquisition failure is recorded as a constant code, never as the raw error text."""

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.sources.kafka_consumer_state_contract import SCHEMA_ID, unredacted_secret_paths

DESCRIBE_FAILED = "DESCRIBE_FAILED"
UNKNOWN_STATE = "Unknown"
_BROKER_STATES = frozenset({"Stable", "Empty", "Dead", "PreparingRebalance", "CompletingRebalance"})


@dataclass(frozen=True)
class DescribedMember:
    member_id: str
    client_id: str
    host: str
    assigned: Sequence[tuple[str, int]] = ()  # (topic, partition)


@dataclass(frozen=True)
class DescribedGroup:
    group_id: str
    state: str | None = None
    members: Sequence[DescribedMember] = ()
    failed: bool = False  # lookup, permission or any other acquisition error


def _member(member: DescribedMember) -> dict[str, Any]:
    by_topic: dict[str, set[int]] = defaultdict(set)
    for topic, partition in member.assigned:
        by_topic[topic].add(partition)
    return {
        "member_id": member.member_id,
        "client_id": member.client_id,
        "host": member.host,
        "assignments": [
            {"topic": topic, "partitions": sorted(by_topic[topic])} for topic in sorted(by_topic)
        ],
    }


def _group(group: DescribedGroup) -> dict[str, Any]:
    if group.failed or group.state is None:
        return {"group_id": group.group_id, "error": DESCRIBE_FAILED, "members": []}
    state = group.state if group.state in _BROKER_STATES else UNKNOWN_STATE
    members = sorted((_member(member) for member in group.members), key=lambda m: m["member_id"])
    return {"group_id": group.group_id, "state": state, "members": members}


def normalize_capture(
    *,
    broker_id: str,
    environment: str,
    captured_at: str,
    tool_version: str,
    kafka_version: str,
    group_scope: Iterable[str],
    described: Iterable[DescribedGroup],
) -> dict[str, Any]:
    """`complete` is true only when every scope group was described exactly once, none failed, and
    none is outside the scope. The state of a group is passed through for the source to judge: a
    rebalance or unknown state is not hidden here, it rejects the capture at load time."""
    scope = sorted(set(group_scope))
    groups = sorted((_group(group) for group in described), key=lambda g: g["group_id"])
    ids = [group["group_id"] for group in groups]
    complete = ids == scope and all("error" not in group for group in groups)
    return {
        "schema": SCHEMA_ID,
        "broker_id": broker_id,
        "environment": environment,
        "captured_at": captured_at,
        "tool_version": tool_version,
        "kafka_version": kafka_version,
        "complete": complete,
        "group_scope": scope,
        "groups": groups,
    }


def secret_findings(document: dict[str, Any], secret_values: Iterable[str]) -> list[str]:
    """JSON paths where the finished capture holds a secret-named key or any of the secret values the
    capture client was configured with. The caller refuses to write the file when this is non-empty."""
    return unredacted_secret_paths(document, list(secret_values))


def serialize(document: dict[str, Any]) -> bytes:
    """The deterministic file form: fixed key order as built above, two-space indent, one trailing
    newline, UTF-8."""
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
