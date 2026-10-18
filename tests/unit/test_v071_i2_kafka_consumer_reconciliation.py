"""v0.7.1 I2.2: the pure Kafka consumer-group -> Service reconciliation (rule
`kafka-consumer-attribution` / `1`, I2.1 contract §6-§7) against every case of the hand-authored
`docs/specifications/0.7.1/i2-vectors/reconciliation.json`, at group level. Attribution rows are
I2.3; here each expected attribution is checked against the group its attachment joins.

Reading of the vectors: `expected_groups` lists the groups in the vector's own broker and
environment; a group that only another environment's mapping source names (C14's `map-staging`) is
asserted separately. A case without `limitations` expects none."""

import json
from pathlib import Path

import pytest

from app.architecture_intelligence.kafka_consumer_attribution import (
    RULE_ID,
    RULE_VERSION,
    AttributionOutcome,
    AttributionReason,
    GroupReconciliation,
    declared_candidates,
    reconcile_groups,
)
from app.canonical.kafka_service_mapping import KafkaServiceMappingEntry
from app.sources.identity import (
    kafka_consumer_id,
    kafka_service_mapping_entry_id,
    kafka_service_mapping_evidence_id,
    kafka_service_mapping_source_instance_id,
)
from app.telemetry.service_resolver import DeclaredServiceCandidate

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.1/i2-vectors"
DATA = json.loads((VECTORS / "reconciliation.json").read_text())
BROKER, ENV = DATA["broker_id"], DATA["environment"]
SOURCE_ENVIRONMENTS = {"map-a": ENV, "map-b": ENV, "map-staging": "staging"}
CANDIDATES = [
    DeclaredServiceCandidate(c["id"], c["name"], c["namespace"])
    for c in DATA["declared_candidates"]
]
ALIASES = DATA["aliases"]


def _source(name: str) -> str:
    return kafka_service_mapping_source_instance_id(
        configured_source_id=name, broker_id=BROKER, environment=SOURCE_ENVIRONMENTS[name]
    )


def _entry_id(label: str) -> str:
    source, group_id = label.split("/", 1)
    return kafka_service_mapping_entry_id(source_instance_id=_source(source), group_id=group_id)


def _entry(spec: dict) -> KafkaServiceMappingEntry:
    source_id = _source(spec["source"])
    environment = SOURCE_ENVIRONMENTS[spec["source"]]
    return KafkaServiceMappingEntry(
        id=kafka_service_mapping_entry_id(source_instance_id=source_id, group_id=spec["group_id"]),
        source_instance_id=source_id,
        broker_id=BROKER,
        environment=environment,
        group_id=spec["group_id"],
        consumer_id=kafka_consumer_id(
            broker_id=BROKER, environment=environment, group_id=spec["group_id"]
        ),
        service_name=spec["service_name"],
        service_namespace=spec.get("service_namespace"),
        evidence_ids=[kafka_service_mapping_evidence_id(source_id)],
    )


def _consumer(group_id: str, environment: str = ENV) -> str:
    return kafka_consumer_id(broker_id=BROKER, environment=environment, group_id=group_id)


def _reconcile(entries, attachments, candidates=CANDIDATES) -> dict[str, GroupReconciliation]:
    attached = {
        _consumer(DATA["attachments"][a]["group_id"]): DATA["attachments"][a]["group_id"]
        for a in attachments
    }
    groups = reconcile_groups(
        [_entry(spec) for spec in entries],
        attached_groups=attached,
        candidates=candidates,
        aliases=ALIASES,
    )
    assert [g.consumer_id for g in groups] == sorted(g.consumer_id for g in groups)
    return {g.consumer_id: g for g in groups}


def _assert_outcome(group: GroupReconciliation, expected: dict) -> None:
    assert group.outcome is AttributionOutcome(expected["outcome"])
    assert group.reason == (AttributionReason(expected["reason"]) if "reason" in expected else None)
    assert group.service_id == expected.get("service_id")
    if group.outcome is not AttributionOutcome.RESOLVED:
        assert group.service_id is None


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["id"] for c in DATA["cases"]])
def test_reconciliation_vectors(case: dict) -> None:
    groups = _reconcile(case["mapping_entries"], case["attachments"])
    other_scope = {
        _consumer(spec["group_id"], SOURCE_ENVIRONMENTS[spec["source"]])
        for spec in case["mapping_entries"]
        if SOURCE_ENVIRONMENTS[spec["source"]] != ENV
    }
    in_scope = {cid: g for cid, g in groups.items() if cid not in other_scope}
    assert set(in_scope) == {_consumer(g["group_id"]) for g in case["expected_groups"]}
    for expected in case["expected_groups"]:
        group = in_scope[_consumer(expected["group_id"])]
        assert group.group_id == expected["group_id"]
        _assert_outcome(group, expected)
        assert [(r.entry_id, r.reason) for r in group.limitations] == sorted(
            (_entry_id(item["entry"]), AttributionReason(item["reason"]))
            for item in expected.get("limitations", [])
        )
    for expected in case["expected_attributions"]:
        attachment = DATA["attachments"][expected["attachment"]]
        group = groups[_consumer(attachment["group_id"])]
        _assert_outcome(group, expected)
        assert [r.entry_id for r in group.entries] == sorted(
            _entry_id(label) for label in expected["mapping_entries"]
        )


def test_c14_the_other_environment_entry_is_its_own_group() -> None:
    [case] = [c for c in DATA["cases"] if c["id"] == "C14"]
    groups = _reconcile(case["mapping_entries"], case["attachments"])
    staging = groups[_consumer("payment-service", "staging")]
    assert staging.outcome is AttributionOutcome.RESOLVED  # a mapping without attachment (C03)
    assert staging.service_id == "service:payment-service"
    assert groups[_consumer("payment-service")].outcome is AttributionOutcome.UNRESOLVED


def test_rule_identity() -> None:
    assert (RULE_ID, RULE_VERSION) == (DATA["rule"]["id"], DATA["rule"]["version"])


# ---- candidate rule (contract §6) -----------------------------------------------------------


def _service_rows() -> list[dict]:
    declared = [{**c, "owner_source_ids": ["urn:aip:source:filesystem:x"]} for c in DATA["declared_candidates"]]  # fmt: skip
    stub = DATA["runtime_stub"]
    return [*declared, {"id": stub["id"], "name": stub["name"], "namespace": stub["namespace"], "owner_source_ids": []}]  # fmt: skip


def test_c04_a_runtime_stub_is_never_a_candidate_and_no_service_id_leaks() -> None:
    candidates = declared_candidates(_service_rows())
    assert {c.id for c in candidates} == {c["id"] for c in DATA["declared_candidates"]}
    entry = {"source": "map-a", "group_id": "payment-service", "service_name": "not-declared-svc"}
    group = _reconcile([entry], ["A1"], candidates)[_consumer("payment-service")]
    assert (group.outcome, group.reason) == (
        AttributionOutcome.UNRESOLVED, AttributionReason.SERVICE_NOT_DECLARED,
    )  # fmt: skip
    assert group.service_id is None
    assert all(reading.service_id is None for reading in group.entries)
    # The filter is what decides it: were the stub a candidate, the same entry would resolve.
    with_stub = [*candidates, DeclaredServiceCandidate(DATA["runtime_stub"]["id"], "not-declared-svc", None)]  # fmt: skip
    resolved = _reconcile([entry], ["A1"], with_stub)[_consumer("payment-service")]
    assert resolved.outcome is AttributionOutcome.RESOLVED


# ---- rules without a dedicated vector -------------------------------------------------------


def _group(*specs: tuple[str, str]) -> GroupReconciliation:
    entries = [
        {"source": source, "group_id": "payment-service", "service_name": name}
        for source, name in specs
    ]
    return _reconcile(entries, ["A1"])[_consumer("payment-service")]


@pytest.mark.parametrize(
    "specs",
    [
        (("map-a", "not-declared-svc"), ("map-b", "unknown")),
        (("map-a", "unknown"), ("map-b", "not-declared-svc")),
    ],
)
def test_mixed_unresolved_reasons_pick_not_declared_first(specs) -> None:
    group = _group(*specs)
    assert (group.outcome, group.reason) == (
        AttributionOutcome.UNRESOLVED, AttributionReason.SERVICE_NOT_DECLARED,
    )  # fmt: skip
    assert {r.reason for r in group.entries} == {
        AttributionReason.SERVICE_NOT_DECLARED, AttributionReason.SERVICE_IDENTITY_PLACEHOLDER,
    }  # fmt: skip


def test_two_placeholders_are_unresolved_placeholder() -> None:
    group = _group(("map-a", "unknown"), ("map-b", "unknown-service"))
    assert group.reason is AttributionReason.SERVICE_IDENTITY_PLACEHOLDER


def test_ambiguous_wins_over_not_declared_when_nothing_resolves() -> None:
    group = _group(("map-a", "dup"), ("map-b", "not-declared-svc"))
    assert (group.outcome, group.reason) == (
        AttributionOutcome.AMBIGUOUS, AttributionReason.SERVICE_IDENTITY_AMBIGUOUS,
    )  # fmt: skip


def test_a_placeholder_entry_is_a_limitation_of_a_resolved_group() -> None:
    group = _group(("map-a", "payment-service"), ("map-b", "unknown"))
    assert group.outcome is AttributionOutcome.RESOLVED
    assert [(r.entry_id, r.reason) for r in group.limitations] == [
        (_entry_id("map-b/payment-service"), AttributionReason.SERVICE_IDENTITY_PLACEHOLDER)
    ]


def test_an_alias_and_a_direct_name_for_the_same_service_agree() -> None:
    group = _group(("map-a", "pay"), ("map-b", "payment-service"))
    assert (group.outcome, group.service_id) == (
        AttributionOutcome.RESOLVED, "service:payment-service",
    )  # fmt: skip
    assert group.limitations == ()
