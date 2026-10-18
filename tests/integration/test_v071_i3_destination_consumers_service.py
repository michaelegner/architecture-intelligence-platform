"""v0.7.1 I3.1: `ArchitectureIntelligenceService.get_destination_consumers` against a real Neo4j,
after the real import request: the Kafka declarations fixture (broker `kafka:cluster-a`, Topic
`inventory`, Services `stock-projector` and `warehouse`), I1 captures for two environments and an
I2 mapping. The broker check reads the Topic's real declaration carriers."""

import json
from pathlib import Path

import jsonschema
import pytest

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersQueryRequest,
)
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.schema_export import DESTINATION_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.import_runs import run_all_configured_sources
from app.graph.schema import ensure_schema
from app.settings import SourcesConfig
from app.sources.model import (
    FilesystemSourceConfig,
    KafkaConsumerStateSourceConfig,
    KafkaServiceMappingSourceConfig,
)

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
DECLARATIONS = REPO / "tests/fixtures/pubsub/kafka/declarations"
ANSWER_SCHEMA = json.loads(Path(DESTINATION_ANSWER_SCHEMA_PATH).read_text())
BROKER = "kafka:cluster-a"
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.1", build_revision="t")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _kafka(tmp_path: Path, environment: str, *, attached: bool = True):
    config = KafkaConsumerStateSourceConfig(
        id=f"kafka-{environment}",
        root=tmp_path / f"kafka-{environment}",
        broker_id=BROKER,
        environment=environment,
        consumer_groups=["audit-sink", "stock-projector"],
    )
    member = {
        "member_id": "m1",
        "client_id": "c",
        "host": "/10.0.0.7",
        "assignments": [{"topic": "inventory", "partitions": [0]}],
    }
    document = {
        "schema": "aip-kafka-consumer-state/1",
        "broker_id": BROKER,
        "environment": environment,
        "captured_at": "2026-10-18T09:00:00Z",
        "tool_version": "aip-kafka-capture/1",
        "kafka_version": "not-established",
        "complete": True,
        "group_scope": ["audit-sink", "stock-projector"],
        "groups": [
            {"group_id": "audit-sink", "state": "Empty", "members": []},
            {
                "group_id": "stock-projector",
                "state": "Stable" if attached else "Empty",
                "members": [member] if attached else [],
            },
        ],
    }
    config.root.mkdir()
    (config.root / "kafka-consumer-state.json").write_text(json.dumps(document))
    return config


def _mapping(tmp_path: Path, environment: str = "prod", service_name: str = "stock-projector"):
    config = KafkaServiceMappingSourceConfig(
        id=f"map-{environment}",
        root=tmp_path / f"map-{environment}",
        broker_id=BROKER,
        environment=environment,
    )
    config.root.mkdir()
    (config.root / "kafka-service-mapping.json").write_text(
        json.dumps(
            {
                "schema": "aip-kafka-consumer-service-mapping/1",
                "broker_id": BROKER,
                "environment": environment,
                "mappings": [{"group_id": "stock-projector", "service_name": service_name}],
            }
        )
    )
    return config


def _import(driver, *, kafka=(), mappings=()) -> None:
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=[FilesystemSourceConfig(id="pubsub-kafka", root=DECLARATIONS)],
            kafka_consumer_state=list(kafka),
            kafka_service_mappings=list(mappings),
        ),
        driver=driver,
        database=DATABASE,
    )
    assert all(run.stats.committed for run in runs)


def _topic_id(driver) -> str:
    with driver.session(database=DATABASE) as session:
        record = session.run("MATCH (t:Topic {name: 'inventory'}) RETURN t.id AS id").single()
    assert record is not None
    return record["id"]


def _ask(driver, aliases: dict[str, str] | None = None, **overrides) -> dict:
    payload = {
        "mode": "query",
        "destination_id": _topic_id(driver),
        "broker_id": BROKER,
        "environment": "prod",
        **overrides,
    }
    service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=PRODUCER, service_aliases=aliases
    )
    answer = service.get_destination_consumers(
        DestinationConsumersQueryRequest.model_validate(payload)
    )
    wire = json.loads(answer.model_dump_json())
    jsonschema.validate(wire, ANSWER_SCHEMA)
    return wire


def _codes(answer: dict) -> list[str]:
    return [item["code"] for item in answer["limitations"]]


def test_attached_and_mapped_group_resolves_with_both_paths_on_the_current_snapshot(
    driver, tmp_path
) -> None:
    _import(driver, kafka=[_kafka(tmp_path, "prod")], mappings=[_mapping(tmp_path)])
    answer = _ask(driver)
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        expected_snapshot = snapshot_fingerprint(
            canonical_snapshot_state(session, coverage_qualification_enabled=True)
        )[0]
    assert answer["snapshot"]["snapshot_id"] == expected_snapshot
    assert (answer["outcome"], _codes(answer)) == ("PARTIAL", ["CAPTURE_SCOPE_LIMITED"])
    [row] = answer["data"]["rows"]
    assert (row["group_id"], row["outcome"], row["service_id"]) == (
        "stock-projector", "RESOLVED", "service:stock-projector",
    )  # fmt: skip
    assert row["captured_at"] == "2026-10-18T09:00:00Z"
    assert len(row["attachment_evidence_refs"]) == 1 and len(row["mapping_evidence_refs"]) == 1
    # No internal carrier id reaches the public answer.
    text = json.dumps(answer)
    assert "kafka-attachment:owned:" not in text and "kafka-service-mapping:owned:" not in text


def test_without_a_mapping_source_the_attachment_is_unresolved_no_mapping(driver, tmp_path) -> None:
    _import(driver, kafka=[_kafka(tmp_path, "prod")])
    answer = _ask(driver)
    assert _codes(answer) == ["CAPTURE_SCOPE_LIMITED", "NO_MAPPING_SOURCE"]
    [row] = answer["data"]["rows"]
    assert (row["outcome"], row["reason"]) == ("UNRESOLVED", "NO_MAPPING")


def test_one_topic_in_two_environments_returns_only_the_requested_one(driver, tmp_path) -> None:
    _import(
        driver,
        kafka=[_kafka(tmp_path, "prod"), _kafka(tmp_path, "staging", attached=False)],
        mappings=[_mapping(tmp_path)],
    )
    assert len(_ask(driver)["data"]["rows"]) == 1
    staging = _ask(driver, environment="staging")
    assert staging["data"]["rows"] == []
    assert _codes(staging) == ["CAPTURE_SCOPE_LIMITED", "NO_MAPPING_SOURCE"]


def test_refusals_through_the_service(driver, tmp_path) -> None:
    _import(driver, kafka=[_kafka(tmp_path, "prod")])
    assert _codes(_ask(driver, environment="dev")) == ["NO_ACCEPTED_CAPTURE"]
    assert _codes(_ask(driver, broker_id="kafka:cluster-b")) == ["BROKER_MISMATCH"]
    stale = "aip:snapshot:v1:" + "0" * 64
    assert _codes(_ask(driver, snapshot_id=stale)) == ["SNAPSHOT_NOT_AVAILABLE"]
    unknown = _ask(driver, destination_id="topic:owned:" + "0" * 64)
    assert (unknown["outcome"], unknown["data"], _codes(unknown)) == (
        "NOT_ANSWERED", None, ["UNKNOWN_DESTINATION"],
    )  # fmt: skip


def test_a_configured_alias_decides_the_attribution(driver, tmp_path) -> None:
    _import(
        driver,
        kafka=[_kafka(tmp_path, "prod")],
        mappings=[_mapping(tmp_path, service_name="projector")],
    )
    [without] = _ask(driver)["data"]["rows"]
    assert (without["outcome"], without["reason"]) == ("UNRESOLVED", "SERVICE_NOT_DECLARED")
    answer = _ask(driver, aliases={"projector": "service:stock-projector"})
    [row] = answer["data"]["rows"]
    assert (row["outcome"], row["service_id"]) == ("RESOLVED", "service:stock-projector")


def test_a_changed_topic_broker_association_changes_the_snapshot_id(driver, tmp_path) -> None:
    """Review of #592: the broker check reads only fingerprinted state. A re-import that removes a
    Topic's broker association (possible for a configured Topic id) changes the snapshot id, so one
    snapshot id never carries two answers."""
    _import(driver, kafka=[_kafka(tmp_path, "prod")])
    before = _ask(driver)
    assert before["outcome"] == "PARTIAL"
    with driver.session(database=DATABASE) as session:  # what such a re-import leaves behind
        session.run(
            "MATCH (d:PubSubDeclaration {entity_kind: 'TOPIC'}) REMOVE d.broker_id"
        ).consume()
    after = _ask(driver)
    assert _codes(after) == ["BROKER_MISMATCH"]
    assert after["snapshot"]["snapshot_id"] != before["snapshot"]["snapshot_id"]
