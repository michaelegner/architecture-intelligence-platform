"""v0.7.1 I4.1: the frozen real-Kafka replay (I4 spec §2, §3, and the §4 public boundary).

Inputs are the committed bytes under `docs/specifications/0.7.1/i4-evidence/kafka/`: two real
captures of the ecommerce-system slice (C1 live, C2 after two groups stopped), the reviewed
Service mapping and the AsyncAPI declarations. `expected.json` was authored from the stock Kafka
CLI and the application's configuration and committed before any import, so the answers are
compared with independent ground truth, never with AIP output. The one derived input is
`C1-incomplete` (C1 with `complete: false`), built in a temporary copy at run time.

Everything goes through the production import (`run_all_configured_sources`) and the public
surfaces. With `AIP_I4_REPLAY_OUT` set, the full answers of every step are written as canonical
JSON for the A/B byte comparison (`ab_replay.py`).
"""

import hashlib
import json
import os
from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.model import (
    FilesystemSourceConfig,
    KafkaConsumerStateSourceConfig,
    KafkaServiceMappingSourceConfig,
)

from .test_v071_i3_destination_consumers_surface_parity import _all_surfaces

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "docs/specifications/0.7.1/i4-evidence"
KAFKA = EVIDENCE / "kafka"
EXPECTED_BYTES = (KAFKA / "expected.json").read_bytes()
EXPECTED = json.loads(EXPECTED_BYTES)
BROKER = EXPECTED["broker_id"]
ENV = EXPECTED["environment"]
TOPICS = ("orders.created", "payments.completed", "payments.dlq", "payments.failed")
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.1", build_revision="t")
# Client-supplied member text from the captures; it must never reach a public answer.
MEMBER_TEXT = ("/172.19.", "console-consumer", "segmentio", "consumer-order-service-1")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _kafka_config(root: Path) -> KafkaConsumerStateSourceConfig:
    return KafkaConsumerStateSourceConfig(
        id="ecommerce-kafka",
        root=root,
        broker_id=BROKER,
        environment=ENV,
        consumer_groups=EXPECTED["capture_allow_list"],
    )


MAPPING = KafkaServiceMappingSourceConfig(
    id="ecommerce-mapping", root=KAFKA / "mapping", broker_id=BROKER, environment=ENV
)


def _place(root: Path, capture: str, *, complete: bool = True) -> None:
    """Puts the frozen capture bytes (or the derived incomplete variant) at the source path."""
    root.mkdir(exist_ok=True)
    data = (KAFKA / capture / "kafka-consumer-state.json").read_bytes()
    if not complete:
        document = json.loads(data)
        document["complete"] = False
        data = json.dumps(document).encode()
    (root / "kafka-consumer-state.json").write_bytes(data)


def _import(driver, kafka_root: Path | None, *, mapping: bool, extra: tuple[Path, ...] = ()):
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=[
                FilesystemSourceConfig(id="ecommerce-declarations", root=KAFKA / "declarations"),
                *(FilesystemSourceConfig(id=f"extra-{i}", root=p) for i, p in enumerate(extra)),
            ],
            kafka_consumer_state=[_kafka_config(kafka_root)] if kafka_root else [],
            kafka_service_mappings=[MAPPING] if mapping else [],
        ),
        driver=driver,
        database=DATABASE,
    )
    return runs


def _committed(runs) -> None:
    assert all(run.stats.committed for run in runs)


def _topic_ids(driver) -> dict[str, str]:
    with driver.session(database=DATABASE) as session:
        records = list(session.run("MATCH (t:Topic) RETURN t.name AS name, t.id AS id"))
    return {record["name"]: record["id"] for record in records}


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _context(topic_ids: dict[str, str], topic: str) -> dict:
    return {"destination_id": topic_ids[topic], "broker_id": BROKER, "environment": ENV}


async def _ask_all(service, topic_ids: dict[str, str]) -> dict[str, dict]:
    return {
        topic: await _all_surfaces(service, {"mode": "query", **_context(topic_ids, topic)})
        for topic in TOPICS
    }


def _assert_expected(answers: dict[str, dict], expected: dict[str, dict], capture: str) -> None:
    captured_at = json.loads((KAFKA / capture / "kafka-consumer-state.json").read_text())[
        "captured_at"
    ]
    for topic, want in expected.items():
        answer = answers[topic]
        assert answer["outcome"] == "PARTIAL", topic
        assert [item["code"] for item in answer["limitations"]] == want["limitations"], topic
        got = {}
        for row in answer["data"]["rows"]:
            assert row["captured_at"] == captured_at
            assert row["attachment_evidence_refs"], row
            got[row["group_id"]] = row
        assert sorted(got) == sorted(r["group_id"] for r in want["rows"]), topic
        for expected_row in want["rows"]:
            row = got[expected_row["group_id"]]
            assert row["outcome"] == expected_row["outcome"], (topic, row)
            if "service" in expected_row:
                assert row["service_id"] == f"service:{expected_row['service']}"
                assert row["mapping_evidence_refs"], row
            else:
                assert row.get("service_id") is None
                assert row["reason"] == expected_row["reason"]
        text = json.dumps(answer)
        for group in want["never_named"]:
            assert f'"{group}"' not in text, (topic, group)
        for fragment in MEMBER_TEXT:
            assert fragment not in text, (topic, fragment)


def _refs(answer: dict) -> list[str]:
    rows = answer["data"]["rows"]
    return sorted(
        {
            ref
            for row in rows
            for ref in [*row["attachment_evidence_refs"], *row["mapping_evidence_refs"]]
        }
    )


def _dump(steps: dict) -> None:
    out = os.environ.get("AIP_I4_REPLAY_OUT")
    if out:
        Path(out).write_text(json.dumps(steps, sort_keys=True, indent=1) + "\n")


def test_the_expectations_are_the_committed_ones() -> None:
    [line] = (KAFKA / "EXPECTED.sha256").read_text().splitlines()
    assert line.split() == [hashlib.sha256(EXPECTED_BYTES).hexdigest(), "expected.json"]


@pytest.mark.asyncio
async def test_the_frozen_real_capture_replays_to_the_independent_expectations(
    driver, tmp_path
) -> None:
    steps: dict[str, dict] = {}
    kafka_root = tmp_path / "kafka"

    # Declarations only: the real discoverer finds the four declared Topics; no capture yet.
    _committed(_import(driver, None, mapping=False))
    topic_ids = _topic_ids(driver)
    assert sorted(topic_ids) == sorted(TOPICS)
    service = _service(driver)
    no_capture = await _all_surfaces(
        service, {"mode": "query", **_context(topic_ids, "orders.created")}
    )
    assert [item["code"] for item in no_capture["limitations"]] == ["NO_ACCEPTED_CAPTURE"]
    steps["0-no-capture"] = no_capture

    # C1 without any mapping source: attachments only, nothing named.
    _place(kafka_root, "c1")
    _committed(_import(driver, kafka_root, mapping=False))
    answers = await _ask_all(service, topic_ids)
    _assert_expected(answers, EXPECTED["c1"]["without_mapping_source"], "c1")
    steps["1-c1-without-mapping"] = answers

    # C1 with the reviewed mapping.
    _committed(_import(driver, kafka_root, mapping=True))
    answers = await _ask_all(service, topic_ids)
    _assert_expected(answers, EXPECTED["c1"]["with_mapping"], "c1")
    c1_snapshot = answers["orders.created"]["snapshot"]["snapshot_id"]
    steps["2-c1-with-mapping"] = answers

    # Same-snapshot evidence drill-down on every surface, bound to the frozen artifact hashes.
    context = _context(topic_ids, "orders.created")
    refs = _refs(answers["orders.created"])
    evidence = await _all_surfaces(
        service, {"mode": "evidence", "snapshot_id": c1_snapshot, "evidence_refs": refs, **context}
    )
    assert evidence["outcome"] == "ANSWERED"
    entries = evidence["data"]["entries"]
    assert {entry["status"] for entry in entries} == {"RESOLVED"}
    for entry in entries:
        payload = entry["evidence"]
        if entry["kind"] == "KAFKA_ATTACHMENT":
            assert payload["capture_content_sha256"] == _sha256(
                KAFKA / "c1/kafka-consumer-state.json"
            )
        else:
            assert entry["kind"] == "KAFKA_SERVICE_MAPPING"
            assert payload["artifact_sha256"] == _sha256(
                MAPPING.root / "kafka-service-mapping.json"
            )
    assert {(e["kind"], e["evidence"]["group_id"]) for e in entries} == {
        ("KAFKA_ATTACHMENT", "ops-tail"),
        ("KAFKA_ATTACHMENT", "payment-service"),
        ("KAFKA_SERVICE_MAPPING", "payment-service"),
    }
    forged = "destination-evidence:" + "0" * 64
    partial = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": c1_snapshot,
            "evidence_refs": sorted([forged, refs[0]]),
            **context,
        },
    )
    assert partial["outcome"] == "PARTIAL"
    assert {e["ref"]: e["status"] for e in partial["data"]["entries"]}[forged] == "NOT_RESOLVED"
    steps["3-c1-evidence"] = {"answered": evidence, "partial": partial}

    # A paged query: one row per page, the cursor followed on every surface.
    first = await _all_surfaces(service, {"mode": "query", **context, "limit": 1})
    cursor = first["data"]["page"]["next_cursor"]
    second = await _all_surfaces(
        service,
        {"mode": "query", **context, "limit": 1, "cursor": cursor, "snapshot_id": c1_snapshot},
    )
    paged = [*first["data"]["rows"], *second["data"]["rows"]]
    assert paged == answers["orders.created"]["data"]["rows"]
    assert "next_cursor" not in second["data"]["page"]
    steps["4-c1-paged"] = {"first": first, "second": second}

    # Refusals on the real world.
    refusals = {
        "BROKER_MISMATCH": {**context, "broker_id": "kafka:other"},
        "UNKNOWN_DESTINATION": {**context, "destination_id": "topic:owned:" + "0" * 64},
    }
    for code, request in refusals.items():
        answer = await _all_surfaces(service, {"mode": "query", **request})
        assert answer["outcome"] == "NOT_ANSWERED"
        assert [item["code"] for item in answer["limitations"]] == [code]
        steps[f"5-refusal-{code}"] = answer

    # Derived C1-incomplete: rejected, the accepted C1 state is kept.
    _place(kafka_root, "c1", complete=False)
    runs = _import(driver, kafka_root, mapping=True)
    [kafka_run] = [r for r in runs if r.kind == "kafka-consumer-state"]
    assert not kafka_run.stats.committed
    assert await _ask_all(service, topic_ids) == answers

    # C2, a second real capture: payment-service and ops-tail are Empty with committed offsets.
    _place(kafka_root, "c2")
    _committed(_import(driver, kafka_root, mapping=True))
    c2_answers = await _ask_all(service, topic_ids)
    _assert_expected(c2_answers, EXPECTED["c2"]["with_mapping"], "c2")
    c2_snapshot = c2_answers["orders.created"]["snapshot"]["snapshot_id"]
    assert c2_snapshot != c1_snapshot
    with driver.session(database=DATABASE) as session:
        groups = session.run("MATCH (m:KafkaServiceMappingEntry) RETURN m.group_id AS g").value()
    assert sorted(groups) == EXPECTED["c2"]["mapping_entries_still_accepted"]
    steps["6-c2-with-mapping"] = c2_answers

    # The C1 snapshot is stale now; its refs never resolve under C2.
    stale = await _all_surfaces(service, {"mode": "query", **context, "snapshot_id": c1_snapshot})
    assert [item["code"] for item in stale["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
    stale_evidence = await _all_surfaces(
        service, {"mode": "evidence", "snapshot_id": c1_snapshot, "evidence_refs": refs, **context}
    )
    assert [item["code"] for item in stale_evidence["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
    cross = await _all_surfaces(
        service, {"mode": "evidence", "snapshot_id": c2_snapshot, "evidence_refs": refs, **context}
    )
    assert {entry["status"] for entry in cross["data"]["entries"]} == {"NOT_RESOLVED"}
    steps["7-c1-refs-after-c2"] = {
        "stale_query": stale,
        "stale_evidence": stale_evidence,
        "cross": cross,
    }

    # An identical C2 replay is a no-op.
    _committed(_import(driver, kafka_root, mapping=True))
    assert await _ask_all(service, topic_ids) == c2_answers

    _dump(steps)


@pytest.mark.asyncio
async def test_a_rabbitmq_queue_is_not_a_kafka_topic_on_every_surface(driver, tmp_path) -> None:
    rabbit = EVIDENCE / "rabbitmq/declarations"
    kafka_root = tmp_path / "kafka"
    _place(kafka_root, "c1")
    _committed(_import(driver, kafka_root, mapping=True, extra=(rabbit,)))
    with driver.session(database=DATABASE) as session:
        queue_id = session.run("MATCH (q:Queue {name: 'q.s1'}) RETURN q.id AS id").single()["id"]  # pyright: ignore[reportOptionalSubscript]
    answer = await _all_surfaces(
        _service(driver),
        {
            "mode": "query",
            "destination_id": queue_id,
            "broker_id": "rabbitmq:i0-spike",
            "environment": ENV,
        },
    )
    assert answer["outcome"] == "NOT_ANSWERED"
    assert [item["code"] for item in answer["limitations"]] == ["DESTINATION_NOT_KAFKA_TOPIC"]
