"""Operator-run Kafka consumer-state capture (v0.7.1 I1.2). Describes exactly the configured consumer
groups through the Kafka Admin API and writes the normalized `aip-kafka-consumer-state/1` file the
source reads. The AIP server never runs this and never sees Kafka credentials.

confluent-kafka is deliberately not a project dependency:

  uv run --with confluent-kafka==2.16.0 python harness/kafka-capture/capture.py \\
    --broker-id kafka:cluster-a --environment prod --group payment-service --group order-service \\
    --out kafka-consumer-state.json

Bootstrap servers come from $KAFKA_BOOTSTRAP_SERVERS. Security settings (SASL/TLS) come from an
optional JSON object of librdkafka properties named by --client-config; they are used to connect and
are never written to the output.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from confluent_kafka import KafkaException  # type: ignore[import-not-found]
from confluent_kafka import version as client_version
from confluent_kafka.admin import AdminClient  # type: ignore[import-not-found]

from app.kafka_capture.normalize import (
    DescribedGroup,
    DescribedMember,
    normalize_capture,
    serialize,
)

TOOL_VERSION = "aip-kafka-capture/1"
TIMEOUT_SECONDS = 30.0
_STATE_NAMES = {
    "stable": "Stable",
    "empty": "Empty",
    "dead": "Dead",
    "preparingrebalance": "PreparingRebalance",
    "preparingrebalancing": "PreparingRebalance",
    "completingrebalance": "CompletingRebalance",
    "completingrebalancing": "CompletingRebalance",
}


def _state(raw: object) -> str:
    name = getattr(raw, "name", str(raw)).replace("_", "").lower()
    return _STATE_NAMES.get(name, "Unknown")


def _describe(admin: AdminClient, groups: list[str]) -> list[DescribedGroup]:
    described: list[DescribedGroup] = []
    for group_id, future in admin.describe_consumer_groups(
        groups, request_timeout=TIMEOUT_SECONDS
    ).items():
        try:
            result = future.result()
        except KafkaException:
            described.append(DescribedGroup(group_id, failed=True))
            continue
        members = [
            DescribedMember(
                member.member_id,
                member.client_id,
                member.host,
                [(tp.topic, tp.partition) for tp in (member.assignment.topic_partitions or [])],
            )
            for member in result.members
        ]
        described.append(DescribedGroup(group_id, _state(result.state), members))
    return described


def _broker_version(admin: AdminClient) -> str:
    # The Admin API exposes no broker version; record the client library version honestly.
    return f"client-{client_version()}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--broker-id", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--group", action="append", required=True, dest="groups")
    parser.add_argument("--client-config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    if not bootstrap:
        print("KAFKA_BOOTSTRAP_SERVERS is not set", file=sys.stderr)
        return 2
    config: dict[str, object] = {"bootstrap.servers": bootstrap}
    if args.client_config:
        config.update(json.loads(args.client_config.read_text()))
    admin = AdminClient(config)
    document = normalize_capture(
        broker_id=args.broker_id,
        environment=args.environment,
        captured_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tool_version=TOOL_VERSION,
        kafka_version=_broker_version(admin),
        group_scope=args.groups,
        described=_describe(admin, args.groups),
    )
    args.out.write_bytes(serialize(document))
    print(f"wrote {args.out} complete={document['complete']}")
    return 0 if document["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
