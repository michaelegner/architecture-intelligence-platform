"""v0.7.2 I2.1: the frozen Sokol111 replay (v0.7.2 spec §4).

Inputs are the committed bytes under `docs/specifications/0.7.2/i2-evidence/sokol111/`: two real
captures of the Sokol111 local environment (C1 with every deployed consumer attached, C2 after the
Image service was stopped), the Service mapping and the AsyncAPI declarations authored from the
protobuf contract and the environment configuration. `expected.json` was authored from source and
configuration and committed before the environment was started, so the answers are compared with
independent expectations, never with AIP output. The stock Redpanda CLI output (`raw/`) is the
broker ground truth.

Everything goes through the production import (`run_all_configured_sources`) and every public
surface (service, REST, negotiated MCP).
"""

import hashlib
import json
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
PACKAGE = REPO / "docs/specifications/0.7.2/i2-evidence/sokol111"
EXPECTED_BYTES = (PACKAGE / "expected.json").read_bytes()
EXPECTED = json.loads(EXPECTED_BYTES)
BROKER = EXPECTED["broker_id"]
ENV = EXPECTED["environment"]
TOPIC = EXPECTED["topic"]
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.1", build_revision="t")
# Client-supplied member text from the captures; it must never reach a public answer.
MEMBER_TEXT = ("kgo-", "172.20.")
MAPPING = KafkaServiceMappingSourceConfig(
    id="sokol111-mapping", root=PACKAGE / "mapping", broker_id=BROKER, environment=ENV
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _import(driver, kafka_root: Path) -> None:
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=[
                FilesystemSourceConfig(id="sokol111-declarations", root=PACKAGE / "declarations")
            ],
            kafka_consumer_state=[
                KafkaConsumerStateSourceConfig(
                    id="sokol111-kafka",
                    root=kafka_root,
                    broker_id=BROKER,
                    environment=ENV,
                    consumer_groups=EXPECTED["capture_allow_list"],
                )
            ],
            kafka_service_mappings=[MAPPING],
        ),
        driver=driver,
        database=DATABASE,
    )
    assert all(run.stats.committed for run in runs)


def _place(root: Path, capture: str) -> None:
    root.mkdir(exist_ok=True)
    (root / "kafka-consumer-state.json").write_bytes(
        (PACKAGE / capture / "kafka-consumer-state.json").read_bytes()
    )


def _topic_id(driver) -> str:
    with driver.session(database=DATABASE) as session:
        [record] = list(session.run("MATCH (t:Topic {name: $name}) RETURN t.id AS id", name=TOPIC))
    return record["id"]


def _context(topic_id: str) -> dict:
    return {"destination_id": topic_id, "broker_id": BROKER, "environment": ENV}


def _assert_expected(answer: dict, capture: str) -> None:
    want = EXPECTED[capture]["with_mapping"][TOPIC]
    captured_at = json.loads((PACKAGE / capture / "kafka-consumer-state.json").read_text())[
        "captured_at"
    ]
    assert answer["outcome"] == "PARTIAL"
    assert [item["code"] for item in answer["limitations"]] == want["limitations"]
    rows = answer["data"]["rows"]
    # Exactly one row per expected group: a duplicate must fail, not overwrite.
    assert sorted(r["group_id"] for r in rows) == sorted(r["group_id"] for r in want["rows"])
    got = {row["group_id"]: row for row in rows}
    for expected_row in want["rows"]:
        row = got[expected_row["group_id"]]
        assert row["captured_at"] == captured_at
        assert row["outcome"] == expected_row["outcome"]
        assert row["service_id"] == f"service:{expected_row['service']}"
        assert row["attachment_evidence_refs"] and row["mapping_evidence_refs"]
    text = json.dumps(answer)
    for group in want["never_named"]:
        assert f'"{group}"' not in text, group
    for fragment in MEMBER_TEXT:
        assert fragment not in text, fragment


def _capture_assignments(capture: str) -> set[tuple[str, str, str, int]]:
    document = json.loads((PACKAGE / capture / "kafka-consumer-state.json").read_text())
    return {
        (group["group_id"], member["member_id"], item["topic"], partition)
        for group in document["groups"]
        for member in group["members"]
        for item in member["assignments"]
        for partition in item["partitions"]
    }


def _cli_assignments(pattern: str) -> set[tuple[str, str, str, int]]:
    """Member rows of the stock `rpk group describe <group>` output."""
    rows = set()
    for path in sorted((PACKAGE / "raw").glob(pattern)):
        lines = path.read_text().splitlines()
        group = lines[0].split()[1]
        header = next(i for i, line in enumerate(lines) if line.startswith("TOPIC "))
        for line in lines[header + 1 :]:
            fields = line.split()
            if len(fields) >= 7:
                rows.add((group, fields[6], fields[0], int(fields[1])))
    return rows


def _states(pattern: str) -> dict[str, str]:
    states = {}
    for path in sorted((PACKAGE / "raw").glob(pattern)):
        lines = path.read_text().splitlines()
        states[lines[0].split()[1]] = next(
            line.split()[1] for line in lines if line.startswith("STATE")
        )
    return states


def test_the_frozen_inputs_match_the_committed_ground_truth() -> None:
    [line] = (PACKAGE / "EXPECTED.sha256").read_text().splitlines()
    assert line.split() == [hashlib.sha256(EXPECTED_BYTES).hexdigest(), "expected.json"]
    # C1 holds exactly the member assignments the stock CLI reported before and after it (G1, G1').
    assert _capture_assignments("c1") == _cli_assignments("0[2-5]-g1-describe-*.txt")
    assert _cli_assignments("1[1-4]-g1b-describe-*.txt") == _cli_assignments(
        "0[2-5]-g1-describe-*.txt"
    )
    # C2: the stopped Image group is Empty with no member; the others are as G2 reports them.
    c2 = json.loads((PACKAGE / "c2/kafka-consumer-state.json").read_text())
    c2_states = {g["group_id"]: g["state"] for g in c2["groups"]}
    assert c2_states == _states("2[2-5]-g2-describe-*.txt")
    for group, state in EXPECTED["c2"]["group_states"].items():
        assert c2_states[group] == state
    assert _capture_assignments("c2") == _cli_assignments("2[2-5]-g2-describe-*.txt")


@pytest.mark.asyncio
async def test_the_frozen_sokol111_captures_replay_to_the_independent_expectations(
    driver, tmp_path
) -> None:
    kafka_root = tmp_path / "kafka"
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)

    _place(kafka_root, "c1")
    _import(driver, kafka_root)
    context = _context(_topic_id(driver))
    c1 = await _all_surfaces(service, {"mode": "query", **context})
    _assert_expected(c1, "c1")

    # Same-snapshot evidence drill-down, bound to the frozen capture and mapping bytes.
    refs = sorted(
        {
            r
            for row in c1["data"]["rows"]
            for r in [*row["attachment_evidence_refs"], *row["mapping_evidence_refs"]]
        }
    )
    evidence = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": c1["snapshot"]["snapshot_id"],
            "evidence_refs": refs,
            **context,
        },
    )
    assert evidence["outcome"] == "ANSWERED"
    entries = evidence["data"]["entries"]
    assert {entry["status"] for entry in entries} == {"RESOLVED"}
    for entry in entries:
        payload = entry["evidence"]
        if entry["kind"] == "KAFKA_ATTACHMENT":
            assert payload["capture_content_sha256"] == _sha256(
                PACKAGE / "c1/kafka-consumer-state.json"
            )
        else:
            assert payload["artifact_sha256"] == _sha256(
                PACKAGE / "mapping/kafka-service-mapping.json"
            )

    # C2 replaces C1 as one source updated in place; replaying it again changes nothing.
    _place(kafka_root, "c2")
    _import(driver, kafka_root)
    c2 = await _all_surfaces(service, {"mode": "query", **context})
    _assert_expected(c2, "c2")
    _import(driver, kafka_root)
    again = await _all_surfaces(service, {"mode": "query", **context})
    assert again == c2
