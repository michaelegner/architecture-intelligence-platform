"""v0.7.1 I2.3: the `kafka_consumer_attribution_v1` block (I2.1 contract §8-§9) built from plain
snapshot rows, against the hand-authored `docs/specifications/0.7.1/i2-vectors/reconciliation.json`.
Expected attributions (one row per I1 attachment, C16/C17) come from the vectors, not from the
production formulas."""

import json
import random
from pathlib import Path

import pytest

from app.architecture_intelligence.kafka_consumer_attribution import attribution_block
from app.canonical.kafka_consumer_state import kafka_capture_evidence_id
from app.sources.identity import (
    kafka_attachment_id,
    kafka_consumer_id,
    kafka_service_mapping_entry_id,
    kafka_service_mapping_evidence_id,
    kafka_service_mapping_source_instance_id,
)
from app.sources.owner_ids import topic_owned_id

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.1/i2-vectors"
DATA = json.loads((VECTORS / "reconciliation.json").read_text())
BROKER, ENV = DATA["broker_id"], DATA["environment"]
SOURCE_ENVIRONMENTS = {"map-a": ENV, "map-b": ENV, "map-staging": "staging"}
I1_SOURCE = "urn:aip:source:kafka-consumer-state:" + "0" * 64
I1_EVIDENCE = kafka_capture_evidence_id(I1_SOURCE)
CAPTURED_AT = "2026-10-18T09:00:00Z"


def _source(name: str) -> str:
    return kafka_service_mapping_source_instance_id(
        configured_source_id=name, broker_id=BROKER, environment=SOURCE_ENVIRONMENTS[name]
    )


def _entry_id(label: str) -> str:
    source, group_id = label.split("/", 1)
    return kafka_service_mapping_entry_id(source_instance_id=_source(source), group_id=group_id)


def _consumer(group_id: str, environment: str = ENV) -> str:
    return kafka_consumer_id(broker_id=BROKER, environment=environment, group_id=group_id)


def _attachment_id(name: str) -> str:
    attachment = DATA["attachments"][name]
    return kafka_attachment_id(
        consumer_id=_consumer(attachment["group_id"]),
        topic_id=topic_owned_id(
            stable_broker_id=BROKER,
            normalized_namespace_or_empty="",
            exact_topic_address=attachment["topic"],
        ),
    )


def _rows(case: dict) -> dict:
    """The snapshot rows a case describes: mapping evidence and entries, I1 attachments and groups,
    and the Service rows (declared candidates plus the runtime-only stub, which has no owner)."""
    entries = []
    for spec in case["mapping_entries"]:
        source_id = _source(spec["source"])
        environment = SOURCE_ENVIRONMENTS[spec["source"]]
        row = {
            "id": kafka_service_mapping_entry_id(
                source_instance_id=source_id, group_id=spec["group_id"]
            ),
            "source_instance_id": source_id,
            "broker_id": BROKER,
            "environment": environment,
            "group_id": spec["group_id"],
            "consumer_id": _consumer(spec["group_id"], environment),
            "service_name": spec["service_name"],
            "evidence_ids": [kafka_service_mapping_evidence_id(source_id)],
        }
        if "service_namespace" in spec:
            row["service_namespace"] = spec["service_namespace"]
        entries.append(row)
    sources = [
        {
            "id": kafka_service_mapping_evidence_id(_source(name)),
            "source_instance_id": _source(name),
            "configured_source_id": name,
            "broker_id": BROKER,
            "environment": SOURCE_ENVIRONMENTS[name],
            "artifact_sha256": "a" * 64,
            "source_revision": "artifact-sha256:" + "a" * 64,
        }
        for name in sorted({spec["source"] for spec in case["mapping_entries"]})
    ]
    attachments = []
    for name in case["attachments"]:
        attachment = DATA["attachments"][name]
        attachments.append(
            {
                "id": _attachment_id(name),
                "consumer_id": _consumer(attachment["group_id"]),
                "topic_id": topic_owned_id(
                    stable_broker_id=BROKER,
                    normalized_namespace_or_empty="",
                    exact_topic_address=attachment["topic"],
                ),
                "captured_at": CAPTURED_AT,
                "evidence_ids": [I1_EVIDENCE],
            }
        )
    groups = [
        {"id": _consumer(a["group_id"]), "group_id": a["group_id"]}
        for a in DATA["attachments"].values()
    ]
    stub = DATA["runtime_stub"]
    services = [
        {**c, "owner_source_ids": ["urn:aip:source:filesystem:" + "1" * 64]}
        for c in DATA["declared_candidates"]
    ] + [{"id": stub["id"], "name": stub["name"], "namespace": None, "owner_source_ids": []}]
    return {
        "sources": sources,
        "entries": entries,
        "attachments": attachments,
        "consumer_groups": groups,
        "service_rows": services,
    }


def _block(case: dict, aliases=None) -> dict:
    return attribution_block(**_rows(case), aliases=DATA["aliases"] if aliases is None else aliases)


def _case(case_id: str) -> dict:
    return next(c for c in DATA["cases"] if c["id"] == case_id)


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["id"] for c in DATA["cases"]])
def test_attribution_rows_match_the_vectors(case: dict) -> None:
    block = _block(case)
    rows = {row["id"]: row for row in block["attributions"]}
    assert set(rows) == {_attachment_id(a["attachment"]) for a in case["expected_attributions"]}
    for expected in case["expected_attributions"]:
        row = rows[_attachment_id(expected["attachment"])]
        assert row["outcome"] == expected["outcome"]
        assert row.get("reason") == expected.get("reason")
        assert row.get("service_id") == expected.get("service_id")
        if row["outcome"] != "RESOLVED":
            assert "service_id" not in row
        # Both evidence paths and the broker capture time T, for every outcome (I2 §5).
        assert row["attachment_evidence_ids"] == [I1_EVIDENCE]
        assert row["captured_at"] == CAPTURED_AT
        assert row["mapping_entries"] == sorted(
            (
                {
                    "id": _entry_id(label),
                    "evidence_ids": [
                        kafka_service_mapping_evidence_id(_source(label.split("/")[0]))
                    ],
                }
                for label in expected["mapping_entries"]
            ),
            key=lambda mapping: mapping["id"],
        )


def test_c16_c17_one_row_per_attachment_one_service_per_group() -> None:
    c17 = _block(_case("C17"))
    assert len(c17["attributions"]) == 2
    assert {row["service_id"] for row in c17["attributions"]} == {"service:billing"}
    assert len(c17["groups"]) == 1
    assert len(_block(_case("C16"))["attributions"]) == 1  # several members, one attachment


def test_c03_a_mapping_without_attachment_has_a_group_row_and_no_attribution() -> None:
    block = _block(_case("C03"))
    assert block["attributions"] == []
    [group] = block["groups"]
    assert (group["outcome"], group["service_id"]) == ("RESOLVED", "service:payment-service")


def test_no_mapping_row_keeps_the_attachment_evidence() -> None:
    [row] = _block(_case("C02"))["attributions"]
    assert (row["outcome"], row["reason"]) == ("UNRESOLVED", "NO_MAPPING")
    assert row["mapping_entries"] == []
    assert row["attachment_evidence_ids"] == [I1_EVIDENCE]


def test_entry_readings_and_limitations_are_kept_per_entry() -> None:
    [group] = _block(_case("C11"))["groups"]
    assert group["limitations"] == [
        {"entry_id": _entry_id("map-b/payment-service"), "reason": "SERVICE_NOT_DECLARED"}
    ]
    readings = {e["id"]: e for e in group["entries"]}
    assert readings[_entry_id("map-a/payment-service")]["service_id"] == "service:payment-service"
    assert readings[_entry_id("map-b/payment-service")] == {
        "id": _entry_id("map-b/payment-service"),
        "evidence_ids": [kafka_service_mapping_evidence_id(_source("map-b"))],
        "reason": "SERVICE_NOT_DECLARED",
    }  # the stub's id never appears


def test_aliases_applied_holds_only_the_aliases_a_mapping_uses() -> None:
    assert _block(_case("C18"))["aliases_applied"] == [
        {"alias": "pay", "service_id": "service:payment-service"}
    ]
    assert _block(_case("C07"))["aliases_applied"] == [{"alias": "ghost", "service_id": "service:nope"}]  # fmt: skip
    assert _block(_case("C01"))["aliases_applied"] == []
    # An alias nobody uses cannot change the block.
    assert _block(_case("C01"), aliases={}) == _block(_case("C01"))


def test_the_rule_identity_and_null_rule() -> None:
    block = _block(_case("C04"))
    assert block["rule"] == DATA["rule"]
    assert all("service_namespace" not in row for row in block["mapping_entries"])
    text = json.dumps(block)
    assert "null" not in text
    assert DATA["runtime_stub"]["id"] not in text


def test_the_block_does_not_depend_on_input_order() -> None:
    case = {
        "attachments": ["A1", "A2", "A3"],
        "mapping_entries": [
            *_case("C10")["mapping_entries"],
            *_case("C17")["mapping_entries"],
            {"source": "map-staging", "group_id": "payment-service", "service_name": "billing"},
        ],
    }
    rows = _rows(case)
    expected = attribution_block(**rows, aliases=DATA["aliases"])
    shuffler = random.Random(7)
    for _ in range(5):
        shuffled = {key: shuffler.sample(value, len(value)) for key, value in rows.items()}
        assert attribution_block(**shuffled, aliases=DATA["aliases"]) == expected
