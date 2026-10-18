"""v0.7.1 I2.3: the `kafka_consumer_attribution_v1` snapshot block against a real Neo4j, through the
real import request - Kafka attachment (I1) plus Service mapping (I2) attributed to a declared
Service with both evidence paths and capture time T, the lifecycle cases L01-L03, L05 and L06, and
one snapshot id across every read path when aliases are configured. The declared Services and Topic
come from the committed Kafka pubsub fixture (broker `kafka:cluster-a`, Topic `inventory`, Services
`stock-projector` and `warehouse`)."""

import json
from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersQueryRequest,
)
from app.architecture_intelligence.locality_contracts import (
    LocalityEvidenceRequest,
    LocalityQueryRequest,
)
from app.architecture_intelligence.locality_projection import internal_request
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.architecture_intelligence.request import ServiceDependenciesRequest
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
BROKER, ENV = "kafka:cluster-a", "prod"
KEY = "kafka_consumer_attribution_v1"
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.1", build_revision="t")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _kafka(tmp_path: Path) -> KafkaConsumerStateSourceConfig:
    return KafkaConsumerStateSourceConfig(
        id="kafka-prod",
        root=tmp_path / "kafka",
        broker_id=BROKER,
        environment=ENV,
        consumer_groups=["audit-sink", "stock-projector"],
    )


def _capture(config: KafkaConsumerStateSourceConfig, *, attached: bool = True) -> None:
    members = (
        [
            {
                "member_id": "m1",
                "client_id": "c",
                "host": "/10.0.0.7",
                "assignments": [{"topic": "inventory", "partitions": [0]}],
            }
        ]
        if attached
        else []
    )
    document = {
        "schema": "aip-kafka-consumer-state/1",
        "broker_id": BROKER,
        "environment": ENV,
        "captured_at": "2026-10-18T09:00:00Z" if attached else "2026-10-18T10:00:00Z",
        "tool_version": "aip-kafka-capture/1",
        "kafka_version": "not-established",
        "complete": True,
        "group_scope": ["audit-sink", "stock-projector"],
        "groups": [
            {"group_id": "audit-sink", "state": "Empty", "members": []},
            {
                "group_id": "stock-projector",
                "state": "Stable" if attached else "Empty",
                "members": members,
            },
        ],
    }
    config.root.mkdir(exist_ok=True)
    (config.root / "kafka-consumer-state.json").write_text(json.dumps(document))


def _mapping(tmp_path: Path, source_id: str = "map-a") -> KafkaServiceMappingSourceConfig:
    return KafkaServiceMappingSourceConfig(
        id=source_id, root=tmp_path / source_id, broker_id=BROKER, environment=ENV
    )


def _write_mapping(config: KafkaServiceMappingSourceConfig, mappings: list[dict]) -> None:
    config.root.mkdir(exist_ok=True)
    (config.root / config.artifact_relative_path).write_text(
        json.dumps(
            {
                "schema": "aip-kafka-consumer-service-mapping/1",
                "broker_id": BROKER,
                "environment": ENV,
                "mappings": mappings,
            }
        )
    )


def _request(driver, *, kafka=(), mappings=(), with_declarations: bool = True) -> None:
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=(
                [FilesystemSourceConfig(id="pubsub-kafka", root=DECLARATIONS)]
                if with_declarations
                else []
            ),
            kafka_consumer_state=list(kafka),
            kafka_service_mappings=list(mappings),
        ),
        driver=driver,
        database=DATABASE,
    )
    assert all(run.stats.committed for run in runs)


def _state(driver, aliases: dict[str, str] | None = None) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(
            session, coverage_qualification_enabled=True, service_aliases=aliases
        )


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportOptionalSubscript]


STOCK = {"group_id": "stock-projector", "service_name": "stock-projector"}


def test_attachment_plus_mapping_attributes_a_declared_service_with_both_paths(
    driver, tmp_path
) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _request(driver, kafka=[kafka])
    before = _state(driver)
    relations = _count(driver, "MATCH ()-[r]->() RETURN count(r) AS c")
    _write_mapping(mapping, [STOCK])
    _request(driver, kafka=[kafka], mappings=[mapping])
    state = _state(driver)
    block = state[KEY]
    [row] = block["attributions"]
    [attachment] = state["kafka_consumer_state_v1"]["attachments"]
    [entry] = block["mapping_entries"]
    assert row["outcome"] == "RESOLVED"
    assert row["service_id"] == "service:stock-projector"
    assert (row["id"], row["topic_id"], row["captured_at"]) == (
        attachment["id"], attachment["topic_id"], "2026-10-18T09:00:00Z",
    )  # fmt: skip
    assert row["attachment_evidence_ids"] == attachment["evidence_ids"]
    assert row["mapping_entries"] == [{"id": entry["id"], "evidence_ids": entry["evidence_ids"]}]
    # Every evidence id resolves to an evidence row of the same snapshot.
    capture_evidence = {e["id"] for e in state["kafka_consumer_state_v1"]["evidence"]}
    mapping_evidence = {s["id"] for s in block["mapping_sources"]}
    assert set(row["attachment_evidence_ids"]) <= capture_evidence
    for mapping_entry in row["mapping_entries"]:
        assert set(mapping_entry["evidence_ids"]) <= mapping_evidence
    # Attribution is derived, never persisted as a relationship, Service or Subscription.
    assert _count(driver, "MATCH ()-[r]->() RETURN count(r) AS c") == relations
    without = {k: v for k, v in state.items() if k != KEY}
    assert snapshot_fingerprint(without) == snapshot_fingerprint(before)


def test_l01_the_attachment_disappears_and_the_mapping_remains(driver, tmp_path) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _write_mapping(mapping, [STOCK])
    _request(driver, kafka=[kafka], mappings=[mapping])
    _capture(kafka, attached=False)
    _request(driver, kafka=[kafka], mappings=[mapping])
    block = _state(driver)[KEY]
    assert block["attributions"] == []
    [group] = block["groups"]
    assert (group["group_id"], group["outcome"]) == ("stock-projector", "RESOLVED")
    assert len(block["mapping_entries"]) == 1


def test_l02_the_mapping_entry_disappears_and_the_attachment_remains(driver, tmp_path) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _write_mapping(mapping, [STOCK])
    _request(driver, kafka=[kafka], mappings=[mapping])
    _write_mapping(mapping, [{"group_id": "audit-sink", "service_name": "warehouse"}])
    _request(driver, kafka=[kafka], mappings=[mapping])
    [row] = _state(driver)[KEY]["attributions"]
    assert (row["outcome"], row["reason"], row["mapping_entries"]) == (
        "UNRESOLVED", "NO_MAPPING", [],
    )  # fmt: skip
    assert row["attachment_evidence_ids"]


def test_l03_removing_the_last_mapping_source_restores_the_i1_bytes(driver, tmp_path) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _request(driver, kafka=[kafka])
    before = snapshot_fingerprint(_state(driver))
    _write_mapping(mapping, [STOCK])
    _request(driver, kafka=[kafka], mappings=[mapping])
    assert KEY in _state(driver)
    _request(driver, kafka=[kafka])
    assert snapshot_fingerprint(_state(driver)) == before


def test_l05_l06_no_mapping_source_means_no_block(driver, tmp_path) -> None:
    _request(driver)
    state = _state(driver, {"stock-projector": "service:warehouse"})
    assert KEY not in state and "kafka_consumer_state_v1" not in state  # L06
    kafka = _kafka(tmp_path)
    _capture(kafka)
    _request(driver, kafka=[kafka])
    state = _state(driver, {"stock-projector": "service:warehouse"})
    assert KEY not in state and "kafka_consumer_state_v1" in state  # L05
    # Configured aliases change nothing while no mapping uses them.
    assert snapshot_fingerprint(state) == snapshot_fingerprint(_state(driver))


def test_a_mapping_alone_is_a_group_row_without_an_attribution(driver, tmp_path) -> None:
    mapping = _mapping(tmp_path)
    _write_mapping(mapping, [STOCK])
    _request(driver, mappings=[mapping])
    block = _state(driver)[KEY]
    assert block["attributions"] == []
    assert [g["outcome"] for g in block["groups"]] == ["RESOLVED"]
    assert _count(driver, "MATCH (g:KafkaConsumerGroup) RETURN count(g) AS c") == 0


def test_a_runtime_stub_service_is_not_declared(driver, tmp_path) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _write_mapping(mapping, [{"group_id": "stock-projector", "service_name": "runtime-only"}])
    _request(driver, kafka=[kafka], mappings=[mapping])
    with driver.session(database=DATABASE) as session:  # what the trace aggregator would create
        session.run(
            "CREATE (:Service {id: 'service:runtime-only', name: 'runtime-only', "
            "discovery_status: 'OBSERVED_ONLY'})"
        )
    block = _state(driver)[KEY]
    [row] = block["attributions"]
    assert (row["outcome"], row["reason"]) == ("UNRESOLVED", "SERVICE_NOT_DECLARED")
    assert "service:runtime-only" not in json.dumps(block)


def _snapshot_ids(service: ArchitectureIntelligenceService, expected: str) -> set[str]:
    """The snapshot id every read path that takes a snapshot reports for the same graph."""
    dependencies = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate({"service_id": "service:stock-projector"})
    )
    evidence_snapshot, _ = service.list_public_evidence()
    usage = service._read_api_usage_snapshot()
    query = LocalityQueryRequest.model_validate(
        {
            "mode": "query",
            "subject_service_id": "service:stock-projector",
            "environment": ENV,
            "first_day": "2026-10-18",
            "last_day": "2026-10-18",
        }
    )
    locality = service.get_service_dependencies_by_locality(query)
    assessment = service.assess_local_calls(internal_request(query))
    scoped_evidence = service.resolve_scoped_locality_evidence(
        LocalityEvidenceRequest.model_validate(
            {
                "mode": "evidence",
                "subject_service_id": "service:stock-projector",
                "snapshot_id": expected,
                "refs": ["unknown-ref"],
            }
        )
    )
    with service._driver.session(database=DATABASE) as session:
        record = session.run("MATCH (t:Topic {name: 'inventory'}) RETURN t.id AS id").single()
    assert record is not None
    destination = service.get_destination_consumers(
        DestinationConsumersQueryRequest.model_validate(
            {
                "mode": "query",
                "destination_id": record["id"],
                "broker_id": BROKER,
                "environment": ENV,
            }
        )
    )
    assert destination.snapshot is not None
    assert usage is not None and dependencies.snapshot is not None
    assert locality.snapshot is not None and scoped_evidence.snapshot is not None
    return {
        dependencies.snapshot.snapshot_id,
        evidence_snapshot,
        usage[0].snapshot_id,
        locality.snapshot.snapshot_id,
        assessment.snapshot_id,
        scoped_evidence.snapshot.snapshot_id,
        destination.snapshot.snapshot_id,
    }


def test_every_read_path_binds_the_same_configured_aliases(driver, tmp_path) -> None:
    kafka, mapping = _kafka(tmp_path), _mapping(tmp_path)
    _capture(kafka)
    _write_mapping(mapping, [{"group_id": "stock-projector", "service_name": "projector"}])
    _request(driver, kafka=[kafka], mappings=[mapping])
    aliases = {"projector": "service:stock-projector", "unused": "service:warehouse"}
    with_aliases = _state(driver, aliases)
    assert with_aliases[KEY]["aliases_applied"] == [
        {"alias": "projector", "service_id": "service:stock-projector"}
    ]
    assert with_aliases[KEY]["attributions"][0]["outcome"] == "RESOLVED"
    expected = snapshot_fingerprint(with_aliases)[0]
    assert expected != snapshot_fingerprint(_state(driver))[0]
    service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=PRODUCER, service_aliases=aliases
    )
    assert _snapshot_ids(service, expected) == {expected}
