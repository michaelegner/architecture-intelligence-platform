"""v0.7.1 I2.2: the Kafka Service-mapping source against a real Neo4j, through the real import request
- persistence as internal carriers only (no Service, no `KafkaConsumerGroup`), replay as a semantic
no-op (L07), a rejected update keeping the previous entries (L04), replacement of one source's
entries only (L08), retirement of a dropped registration, and the duplicate-id conflict (Q09)."""

import json
from pathlib import Path

import jsonschema
import pytest

from app.graph.import_runs import run_all_configured_sources
from app.graph.labels import NODE_LABELS
from app.ingestion.import_report import build_import_report
from app.settings import SourcesConfig
from app.sources.model import DiagnosticCode, IngestionResult, KafkaServiceMappingSourceConfig

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO / "schemas/import/v0.5/import-report.schema.json").read_text())
BROKER, ENV = "kafka:cluster-a", "prod"
LABELS = ("KafkaServiceMappingEntry", "KafkaServiceMappingEvidence")
EXAMPLE = [
    {"group_id": "order-service", "service_name": "billing"},
    {"group_id": "payment-service", "service_name": "not-declared-svc"},
]


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _mapping(
    tmp_path: Path, source_id: str = "map-a", *, environment: str = ENV, folder: str | None = None
) -> KafkaServiceMappingSourceConfig:
    return KafkaServiceMappingSourceConfig(
        id=source_id,
        root=tmp_path / (folder or source_id),
        broker_id=BROKER,
        environment=environment,
    )


def _write(config: KafkaServiceMappingSourceConfig, mappings=EXAMPLE, **overrides) -> None:
    document = {
        "schema": "aip-kafka-consumer-service-mapping/1",
        "broker_id": BROKER,
        "environment": config.environment,
        "mappings": mappings,
        **overrides,
    }
    config.root.mkdir(parents=True, exist_ok=True)
    (config.root / config.artifact_relative_path).write_text(json.dumps(document))


def _request(driver, *mappings: KafkaServiceMappingSourceConfig):
    import_id, runs = run_all_configured_sources(
        SourcesConfig(directories=[], kafka_service_mappings=list(mappings)),
        driver=driver,
        database=DATABASE,
    )
    report = build_import_report(import_id, runs)
    jsonschema.validate(json.loads(report.model_dump_json()), SCHEMA)
    return [r for r in runs if r.kind == "kafka-service-mapping"]


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportOptionalSubscript]


def _carriers(driver) -> list[dict]:
    """Every mapping carrier with all its properties, sorted: the full persisted state to compare."""
    with driver.session(database=DATABASE) as session:
        rows = session.run(
            "MATCH (n) WHERE n:KafkaServiceMappingEntry OR n:KafkaServiceMappingEvidence "
            "RETURN labels(n) AS labels, properties(n) AS props"
        )
        return sorted(
            ({"labels": r["labels"], **r["props"]} for r in rows), key=lambda row: row["id"]
        )


def _entries_by_source(driver) -> dict[str, set[tuple[str, str]]]:
    with driver.session(database=DATABASE) as session:
        rows = session.run(
            "MATCH (e:KafkaServiceMappingEvidence) "
            "OPTIONAL MATCH (m:KafkaServiceMappingEntry {source_instance_id: e.source_instance_id}) "
            "RETURN e.configured_source_id AS source, e.environment AS env, "
            "m.group_id AS group, m.service_name AS service"
        )
        found: dict[str, set[tuple[str, str]]] = {}
        for r in rows:
            entries = found.setdefault(f"{r['source']}@{r['env']}", set())
            if r["group"] is not None:
                entries.add((r["group"], r["service"]))
        return found


def _rejected(run, code: DiagnosticCode, result: IngestionResult) -> None:
    assert not run.stats.committed
    assert {s.result for s in run.stats.source_results} == {result}
    assert {d.code for s in run.stats.source_results for d in s.diagnostics} == {code}


def test_an_accepted_artifact_persists_only_internal_carriers(driver, tmp_path) -> None:
    config = _mapping(tmp_path)
    _write(config)
    [run] = _request(driver, config)
    assert run.stats.committed
    assert {s.result for s in run.stats.source_results} == {IngestionResult.ACCEPTED}
    carriers = _carriers(driver)
    assert [row["labels"] for row in carriers].count(["KafkaServiceMappingEntry"]) == 2
    assert [row["labels"] for row in carriers].count(["KafkaServiceMappingEvidence"]) == 1
    source_id = run.stats.source_results[0].source_instance_id
    assert all(row["owner_source_ids"] == [source_id] for row in carriers)
    for label in LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0
    # The mapping names an undeclared Service: nothing is minted, no consumer group appears.
    assert _count(driver, "MATCH (s:Service) RETURN count(s) AS c") == 0
    assert _count(driver, "MATCH (g:KafkaConsumerGroup) RETURN count(g) AS c") == 0
    assert _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c") == 0
    assert set(LABELS).isdisjoint(NODE_LABELS)


def test_replay_is_a_semantic_no_op_l07(driver, tmp_path) -> None:
    config = _mapping(tmp_path)
    _write(config)
    _request(driver, config)
    before = _carriers(driver)
    [run] = _request(driver, config)
    assert run.stats.committed
    assert all(not s.graph_revision_advanced for s in run.stats.per_source.values())
    assert _carriers(driver) == before


@pytest.mark.parametrize(
    ("overrides", "code", "result"),
    [
        ({"broker_id": "kafka:cluster-b"}, DiagnosticCode.KSM_BROKER_MISMATCH, IngestionResult.REJECTED_INVALID),
        ({"schema": "aip-kafka-consumer-service-mapping/2"}, DiagnosticCode.KSM_UNSUPPORTED_SCHEMA, IngestionResult.REJECTED_UNSUPPORTED),
        ({"client_id": "x"}, DiagnosticCode.KSM_ARTIFACT_INVALID, IngestionResult.REJECTED_INVALID),
    ],
)  # fmt: skip
def test_a_rejected_update_keeps_the_previous_entries_l04(
    driver, tmp_path, overrides, code, result
) -> None:
    config = _mapping(tmp_path)
    _write(config)
    _request(driver, config)
    before = _carriers(driver)
    _write(config, [{"group_id": "order-service", "service_name": "other"}], **overrides)
    [run] = _request(driver, config)
    _rejected(run, code, result)
    assert _carriers(driver) == before


def test_a_later_valid_artifact_replaces_only_that_sources_entries_l08(driver, tmp_path) -> None:
    map_a, map_b = _mapping(tmp_path, "map-a"), _mapping(tmp_path, "map-b")
    _write(map_a)
    _write(map_b, [{"group_id": "order-service", "service_name": "billing"}])
    _request(driver, map_a, map_b)
    _write(map_a, [{"group_id": "order-service", "service_name": "payment-service"}])
    runs = _request(driver, map_a, map_b)
    assert all(run.stats.committed for run in runs)
    assert _entries_by_source(driver) == {
        f"map-a@{ENV}": {("order-service", "payment-service")},
        f"map-b@{ENV}": {("order-service", "billing")},
    }


def test_an_empty_artifact_is_a_source_with_no_entries(driver, tmp_path) -> None:
    config = _mapping(tmp_path)
    _write(config)
    _request(driver, config)
    _write(config, [])
    [run] = _request(driver, config)
    assert run.stats.committed
    assert _entries_by_source(driver) == {f"map-a@{ENV}": set()}


def test_dropping_a_registration_retires_only_its_carriers(driver, tmp_path) -> None:
    map_a, map_b = _mapping(tmp_path, "map-a"), _mapping(tmp_path, "map-b")
    _write(map_a)
    _write(map_b)
    _request(driver, map_a, map_b)
    _request(driver, map_b)
    assert set(_entries_by_source(driver)) == {f"map-b@{ENV}"}
    _request(driver)
    assert _carriers(driver) == []


def test_a_rejected_artifact_after_an_environment_change_keeps_the_previous_source(
    driver, tmp_path
) -> None:
    prod = _mapping(tmp_path, folder="prod")
    _write(prod)
    _request(driver, prod)
    before = _carriers(driver)
    staging = _mapping(tmp_path, environment="staging", folder="staging")
    _write(staging, environment="prod")  # does not match the changed registration
    [run] = _request(driver, staging)
    _rejected(run, DiagnosticCode.KSM_ENVIRONMENT_MISMATCH, IngestionResult.REJECTED_INVALID)
    assert _carriers(driver) == before
    _write(staging)
    [run] = _request(driver, staging)
    assert run.stats.committed
    assert set(_entries_by_source(driver)) == {"map-a@staging"}


def test_q09_registrations_sharing_an_id_are_all_rejected_and_keep_prior_state(
    driver, tmp_path
) -> None:
    first = _mapping(tmp_path, folder="first")
    _write(first)
    _request(driver, first)
    before = _carriers(driver)
    second = _mapping(tmp_path, folder="second")
    _write(second, [{"group_id": "order-service", "service_name": "other"}])
    runs = _request(driver, first, second)
    assert len(runs) == 2
    for run in runs:
        _rejected(run, DiagnosticCode.KSM_DUPLICATE_SOURCE, IngestionResult.REJECTED_CONFLICT)
    assert _carriers(driver) == before
