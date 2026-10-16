"""v0.7.1 I1.3: the Kafka consumer-state source against a real Neo4j - persistence as internal
carriers attached only to already-declared Topics, the conditional `kafka_consumer_state_v1`
snapshot key, replay as a semantic no-op, authoritative replacement, ordering (stale/conflicting
captures), rejected captures leaving prior state untouched, retirement on a changed allow-list and
the duplicate conflict through the real import request. The declared Topic comes from the committed
Kafka pubsub fixture (broker `kafka:cluster-a`, Topic `inventory`)."""

import json
from pathlib import Path

import jsonschema
import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.import_runs import run_all_configured_sources
from app.graph.schema import ensure_schema
from app.ingestion.import_report import build_import_report
from app.settings import SourcesConfig
from app.sources.model import (
    FilesystemSourceConfig,
    IngestionResult,
    KafkaConsumerStateSourceConfig,
)

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
DECLARATIONS = REPO / "tests/fixtures/pubsub/kafka/declarations"
BROKER, ENV = "kafka:cluster-a", "prod"
LABELS = ("KafkaConsumerGroup", "KafkaConsumerAttachment", "KafkaCaptureEvidence")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _member(topic: str, member_id: str = "m1") -> dict:
    return {
        "member_id": member_id,
        "client_id": "projector",
        "host": "/10.0.0.7",
        "assignments": [{"topic": topic, "partitions": [0, 1]}],
    }


def _write(
    root: Path,
    *,
    groups: dict[str, tuple[str, list[dict]]] | None = None,
    captured_at: str = "2026-10-16T09:00:00Z",
    scope: tuple[str, ...] = ("audit-sink", "stock-projector"),
) -> None:
    groups = groups or {"stock-projector": ("Stable", [_member("inventory")])}
    described = {name: groups.get(name, ("Empty", [])) for name in scope}
    document = {
        "schema": "aip-kafka-consumer-state/1",
        "broker_id": BROKER,
        "environment": ENV,
        "captured_at": captured_at,
        "tool_version": "aip-kafka-capture/1",
        "kafka_version": "not-established",
        "complete": True,
        "group_scope": sorted(scope),
        "groups": [
            {"group_id": name, "state": state, "members": members}
            for name, (state, members) in sorted(described.items())
        ],
    }
    root.mkdir(exist_ok=True)
    (root / "kafka-consumer-state.json").write_text(json.dumps(document))


def _kafka(
    tmp_path: Path,
    *,
    source_id: str = "kafka-prod",
    scope: tuple[str, ...] = ("audit-sink", "stock-projector"),
) -> KafkaConsumerStateSourceConfig:
    return KafkaConsumerStateSourceConfig(
        id=source_id,
        root=tmp_path / source_id,
        broker_id=BROKER,
        environment=ENV,
        consumer_groups=list(scope),
    )


def _filesystem() -> FilesystemSourceConfig:
    return FilesystemSourceConfig(id="pubsub-kafka", root=DECLARATIONS)


def _request(driver, *kafka: KafkaConsumerStateSourceConfig, with_topics: bool = True):
    return run_all_configured_sources(
        SourcesConfig(
            directories=[_filesystem()] if with_topics else [],
            kafka_consumer_state=list(kafka),
        ),
        driver=driver,
        database=DATABASE,
    )


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportArgumentType]


def _counts(driver) -> dict[str, int]:
    return {label: _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") for label in LABELS}


def _state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def _kafka_run(runs):
    [run] = [r for r in runs if r.kind == "kafka-consumer-state"]
    return run


def test_a_live_assignment_to_a_declared_topic_persists_as_internal_carriers(
    driver, tmp_path
) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _, runs = _request(driver, kafka)
    run = _kafka_run(runs)
    assert run.stats.committed
    assert _counts(driver) == {
        "KafkaConsumerGroup": 2, "KafkaConsumerAttachment": 1, "KafkaCaptureEvidence": 1,
    }  # fmt: skip
    for label in LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0
    # nothing is minted: the declared Topic is the only one, there is still no Subscription
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 1
    assert _count(driver, "MATCH (s:Subscription) RETURN count(s) AS c") == 0
    assert (
        _count(driver, "MATCH (e:Evidence) WHERE e.id STARTS WITH 'kafka' RETURN count(e) AS c")
        == 0
    )
    with driver.session(database=DATABASE) as session:
        topic_id = session.run("MATCH (t:Topic) RETURN t.id AS id").single()["id"]  # pyright: ignore[reportOptionalSubscript]
        attached = session.run("MATCH (a:KafkaConsumerAttachment) RETURN a.topic_id AS t").single()[
            "t"
        ]  # pyright: ignore[reportOptionalSubscript]
    assert attached == topic_id


def test_the_import_report_validates_and_names_the_kafka_run(driver, tmp_path) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    import_id, runs = _request(driver, kafka)
    report = build_import_report(import_id, runs)
    schema = json.loads((REPO / "schemas/import/v0.5/import-report.schema.json").read_text())
    jsonschema.validate(json.loads(report.model_dump_json()), schema)
    assert [r.kind for r in report.runs] == ["filesystem", "kafka-consumer-state"]


def test_the_snapshot_gains_the_conditional_key_and_is_otherwise_unchanged(
    driver, tmp_path
) -> None:
    _request(driver)
    before = _state(driver)
    assert "kafka_consumer_state_v1" not in before
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    state = _state(driver)
    block = state["kafka_consumer_state_v1"]
    for name in ("groups", "attachments", "evidence"):
        assert block[name] == sorted(block[name], key=lambda row: row["id"])
    [evidence] = block["evidence"]
    assert json.loads(evidence["group_states_json"]) == {
        "audit-sink": "Empty", "stock-projector": "Stable",
    }  # fmt: skip
    [attachment] = block["attachments"]
    assert attachment["evidence_ids"] == [evidence["id"]]
    assert len(json.loads(attachment["support_json"])) == 1
    without = {k: v for k, v in state.items() if k != "kafka_consumer_state_v1"}
    assert snapshot_fingerprint(without)[0] == snapshot_fingerprint(before)[0]


def test_replay_is_a_semantic_no_op_l01(driver, tmp_path) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    first = snapshot_fingerprint(_state(driver))[0]
    _, runs = _request(driver, kafka)
    run = _kafka_run(runs)
    assert run.stats.committed
    assert all(not s.graph_revision_advanced for s in run.stats.per_source.values())
    assert snapshot_fingerprint(_state(driver))[0] == first


def test_a_later_capture_with_the_same_attachments_refreshes_t_only_l02(driver, tmp_path) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    before = _state(driver)["kafka_consumer_state_v1"]
    _write(kafka.root, captured_at="2026-10-16T10:00:00Z")
    _request(driver, kafka)
    after = _state(driver)["kafka_consumer_state_v1"]
    assert [a["id"] for a in after["attachments"]] == [a["id"] for a in before["attachments"]]
    assert after["attachments"][0]["captured_at"] == "2026-10-16T10:00:00Z"
    assert after["evidence"][0]["captured_at"] == "2026-10-16T10:00:00Z"


def test_a_later_complete_capture_without_the_assignment_removes_it_l03(driver, tmp_path) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    _write(
        kafka.root, groups={"stock-projector": ("Empty", [])}, captured_at="2026-10-16T10:00:00Z"
    )
    _request(driver, kafka)
    assert _counts(driver) == {
        "KafkaConsumerGroup": 2, "KafkaConsumerAttachment": 0, "KafkaCaptureEvidence": 1,
    }  # fmt: skip
    states = json.loads(
        _state(driver)["kafka_consumer_state_v1"]["evidence"][0]["group_states_json"]
    )
    assert states["stock-projector"] == "Empty"  # explicit zero live attachment at T


@pytest.mark.parametrize(
    "bad",
    [
        {"captured_at": "2026-10-16T08:00:00Z"},  # R14 stale
        {
            "groups": {"stock-projector": ("Stable", [_member("inventory", "other")])}
        },  # R15 conflict
        {"groups": {"stock-projector": ("PreparingRebalance", [])}},  # R05
    ],
    ids=["stale", "conflict", "rebalance"],
)
def test_a_rejected_capture_commits_nothing_and_removes_nothing_l04(driver, tmp_path, bad) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    before = (_counts(driver), snapshot_fingerprint(_state(driver))[0])
    _write(kafka.root, **bad)
    _, runs = _request(driver, kafka)
    run = _kafka_run(runs)
    assert not run.stats.committed
    assert {s.result for s in run.stats.source_results} <= {
        IngestionResult.REJECTED_CONFLICT,
        IngestionResult.REJECTED_INVALID,
    }
    assert (_counts(driver), snapshot_fingerprint(_state(driver))[0]) == before


def test_an_undeclared_topic_is_not_minted_and_attaches_once_it_is_declared(
    driver, tmp_path
) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _, runs = _request(driver, kafka, with_topics=False)
    run = _kafka_run(runs)
    assert {s.result for s in run.stats.source_results} == {
        IngestionResult.ACCEPTED_WITH_LIMITATIONS
    }
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 0
    assert _counts(driver)["KafkaConsumerAttachment"] == 0
    _request(driver, kafka)  # the same capture, now with the declaring source configured
    assert _counts(driver)["KafkaConsumerAttachment"] == 1


def test_a_changed_allow_list_retires_the_old_source_and_never_infers_detachment_l06(
    driver, tmp_path
) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    old_evidence = _state(driver)["kafka_consumer_state_v1"]["evidence"][0]["id"]
    narrower = _kafka(tmp_path, scope=("stock-projector",))
    _write(narrower.root, scope=("stock-projector",))
    _request(driver, narrower)
    block = _state(driver)["kafka_consumer_state_v1"]
    assert [g["group_id"] for g in block["groups"]] == ["stock-projector"]
    assert block["evidence"][0]["id"] != old_evidence
    assert _counts(driver) == {
        "KafkaConsumerGroup": 1, "KafkaConsumerAttachment": 1, "KafkaCaptureEvidence": 1,
    }  # fmt: skip


def test_dropping_the_registration_retires_everything_l05(driver, tmp_path) -> None:
    kafka = _kafka(tmp_path)
    _write(kafka.root)
    _request(driver, kafka)
    _request(driver)
    assert _counts(driver) == dict.fromkeys(LABELS, 0)
    assert "kafka_consumer_state_v1" not in _state(driver)


def test_duplicate_registrations_are_both_rejected_through_the_request(driver, tmp_path) -> None:
    first, second = _kafka(tmp_path, source_id="kafka-a"), _kafka(tmp_path, source_id="kafka-b")
    _write(first.root)
    _write(second.root)
    _, runs = _request(driver, first, second)
    kafka_runs = [r for r in runs if r.kind == "kafka-consumer-state"]
    assert len(kafka_runs) == 2
    for run in kafka_runs:
        assert not run.stats.committed
        assert {s.result for s in run.stats.source_results} == {IngestionResult.REJECTED_CONFLICT}
    assert _counts(driver) == dict.fromkeys(LABELS, 0)


def test_the_carrier_labels_stay_outside_the_natural_language_allowlist() -> None:
    from app.graph.labels import NODE_LABELS

    assert set(LABELS).isdisjoint(NODE_LABELS)
