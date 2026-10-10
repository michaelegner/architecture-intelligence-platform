"""v0.6.0 I3.3a: the pure evidence-mode projection (I3 decision record D11, D16.1, D16.7).

The inputs are synthetic resolver rows. Every answer is validated against the `LocalityAnswer`
model **and** the published 0.6 answer schema.
"""

import json
from datetime import UTC, datetime

import jsonschema
import pytest

from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityEvidenceRequest,
    ScopedLocalityEvidenceData,
)
from app.architecture_intelligence.locality_projection import is_v2_ref, project_scoped_evidence
from app.architecture_intelligence.schema_export import LOCALITY_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.scoped_evidence_repository import ScopedEvidenceRows
from app.provenance.model import ScopedObservedCall

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
ANSWER_SCHEMA = json.loads(LOCALITY_ANSWER_SCHEMA_PATH.read_text())
V2_OWN = "evidence:otel:calls-scoped:v2:" + "1" * 64
V2_ABSENT = "evidence:otel:calls-scoped:v2:" + "2" * 64
POD_REF = "evidence:kubernetes:urn:aip:k8s-resource:pod#resources.yaml:rev-a-1"
OWNER_REF = "evidence:kubernetes:urn:aip:k8s-resource:owner#resources.yaml:rev-a-1"
OTHER_REF = "evidence:kubernetes:urn:aip:k8s-resource:other#resources.yaml:rev-a-1"
DECLARED_REF = "evidence:declared:orders-calls-pricing"


def _v2(record_id: str = V2_OWN) -> ScopedObservedCall:
    return ScopedObservedCall(
        id=record_id,
        environment="production",
        bucket_utc_day="2026-09-28",
        subject_id="service:orders",
        object_id="operation:service:pricing:GET:/prices",
        caller_cluster_uid="cluster-1",
        caller_pod_uid="pod-1",
        first_seen=datetime(2026, 9, 28, 9, tzinfo=UTC),
        last_seen=datetime(2026, 9, 28, 9, 30, tzinfo=UTC),
        observation_count=2,
        correlation_mode="CLIENT_SERVER",
        sample_trace_ids=["b" * 32, "a" * 32],
        k8s_namespace_name="shop",
        k8s_pod_name="orders-p1",
        k8s_deployment_name="orders",
    )


def _row(ref: str, source_type: str = "KUBERNETES") -> dict:
    return {
        "id": ref,
        "source_type": source_type,
        "source_file": "resources.yaml",
        "source_revision": "rev-a-1",
        "evidence_type": "DECLARED",
    }


def _rows(*, v2=(), pod=(), owner=(), evidence=()) -> ScopedEvidenceRows:
    return ScopedEvidenceRows(
        v2={record.id: record for record in v2},
        pod_refs=frozenset(pod),
        owner_refs=frozenset(owner),
        evidence_rows={"evidence": {row["id"]: row for row in evidence}, "relations": []},
    )


def _answer(refs: list[str], rows: ScopedEvidenceRows) -> LocalityAnswer:
    request = LocalityEvidenceRequest(
        mode="evidence",
        subject_service_id="service:orders",
        snapshot_id=SNAPSHOT.snapshot_id,
        refs=sorted(refs),
    )
    answer = project_scoped_evidence(request, rows, snapshot=SNAPSHOT, producer=PRODUCER)
    payload = json.loads(answer.model_dump_json())
    LocalityAnswer.model_validate(payload)
    validator = jsonschema.Draft202012Validator(ANSWER_SCHEMA)
    assert [error.message for error in validator.iter_errors(payload)] == []
    return answer


def _entries(answer: LocalityAnswer) -> dict:
    assert isinstance(answer.data, ScopedLocalityEvidenceData)
    return {entry.ref: entry for entry in answer.data.entries}


@pytest.mark.parametrize(
    ("ref", "v2"),
    [
        (V2_OWN, True),
        ("evidence:otel:calls-scoped:v2:" + "A" * 64, False),
        ("evidence:otel:calls-scoped:v2:" + "1" * 63, False),
        (POD_REF, False),
        (DECLARED_REF, False),
    ],
)
def test_only_the_exact_v2_pattern_is_a_v2_ref(ref, v2):
    assert is_v2_ref(ref) is v2


def test_a_v2_ref_resolves_to_exactly_the_admitted_fields():
    answer = _answer([V2_OWN], _rows(v2=[_v2()]))
    entry = _entries(answer)[V2_OWN]

    assert answer.outcome is Outcome.ANSWERED and answer.limitations == []
    assert entry.ref_kind is not None and entry.ref_kind.value == "SCOPED_V2"
    assert entry.scoped_record is not None
    record = entry.scoped_record.model_dump(mode="json")
    assert sorted(record) == sorted(
        [
            "id",
            "subject_id",
            "object_id",
            "environment",
            "bucket_utc_day",
            "caller_cluster_uid",
            "caller_pod_uid",
            "first_seen",
            "last_seen",
            "observation_count",
            "correlation_mode",
            "sample_trace_ids",
            "key_rule_id",
            "key_rule_version",
            "normalization_rule_id",
            "normalization_rule_version",
        ]
    )
    # No CLIENT Resource attribute and no Workload is published (D11).
    assert "orders-p1" not in json.dumps(record) and "shop" not in json.dumps(record)
    assert record["sample_trace_ids"] == ["a" * 32, "b" * 32]


def test_capture_refs_resolve_only_through_the_authority_and_as_kubernetes_evidence():
    rows = _rows(
        pod=[POD_REF],
        owner=[OWNER_REF],
        evidence=[_row(POD_REF), _row(OWNER_REF), _row(OTHER_REF)],
    )
    entries = _entries(_answer([POD_REF, OWNER_REF, OTHER_REF], rows))

    assert (
        entries[POD_REF].ref_kind is not None and entries[POD_REF].ref_kind.value == "POD_CAPTURE"
    )
    assert entries[OWNER_REF].ref_kind is not None
    assert entries[OWNER_REF].ref_kind.value == "OWNER_CAPTURE"
    # A Kubernetes evidence row the authority did not admit stays NOT_FOUND.
    assert entries[OTHER_REF].status.value == "NOT_FOUND"


def test_an_admitted_ref_that_is_not_kubernetes_evidence_is_not_found():
    rows = _rows(pod=[DECLARED_REF], evidence=[_row(DECLARED_REF, source_type="MANIFEST")])
    answer = _answer([DECLARED_REF], rows)

    assert _entries(answer)[DECLARED_REF].status.value == "NOT_FOUND"
    assert answer.outcome is Outcome.NOT_ANSWERED


def test_every_not_found_entry_is_identical_but_for_its_ref():
    """Absent, another caller's v2 (filtered by the reader), unadmitted capture, declared: no
    entry says which (D11)."""
    answer = _answer([V2_ABSENT, OTHER_REF, DECLARED_REF], _rows(evidence=[_row(OTHER_REF)]))
    shapes = {
        json.dumps({**entry.model_dump(mode="json"), "ref": None}, sort_keys=True)
        for entry in _entries(answer).values()
    }
    assert len(shapes) == 1


@pytest.mark.parametrize(
    ("refs", "outcome", "codes"),
    [
        ([V2_OWN, POD_REF], Outcome.ANSWERED, []),
        ([V2_OWN, V2_ABSENT], Outcome.PARTIAL, ["INSUFFICIENT_EVIDENCE"]),
        ([V2_ABSENT, OTHER_REF], Outcome.NOT_ANSWERED, ["INSUFFICIENT_EVIDENCE"]),
    ],
)
def test_the_outcome_follows_d16_1(refs, outcome, codes):
    rows = _rows(v2=[_v2()], pod=[POD_REF], evidence=[_row(POD_REF)])
    answer = _answer(refs, rows)

    assert answer.outcome is outcome
    assert [item.code.value for item in answer.limitations] == codes
    assert answer.mode == "evidence"
