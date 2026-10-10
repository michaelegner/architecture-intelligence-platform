"""v0.6.0 I2.4b: the pure Qualified Local Evidence Assessment builder (I2 spec §9-§10, decision
record D9/D14).

Identities must reproduce the independently frozen I2.4a vectors
(`docs/specifications/0.6.0/i2-vectors/local-assessment-id.json`); answer-level expectations come
from the read-only I1 oracle. The fixtures reuse the I2.3a realizations with the vectors' Workload
UIDs.
"""

import dataclasses
import itertools
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.architecture_intelligence import local_assessment
from app.architecture_intelligence.local_assessment import (
    ASSERTION_PREFIX,
    RULES,
    AssessmentLimitation,
    QualifiedLocalEvidenceAssessment,
    assess,
    compute_local_assertion_id,
    compute_local_assessment_id,
)
from app.architecture_intelligence.scoped_applicability import (
    CapturedWorkload,
    LocalityRequest,
    ScopedDayWindowV1,
    evaluate_candidates,
)
from app.architecture_intelligence.scoped_evidence_repository import (
    DeclaredCallEvidence,
    ScopedApplicabilityRead,
)
from app.canonical.ids import scoped_observed_call_v2_id
from app.qualification.declared_observed import CONFIRMED, OBSERVED_ONLY, QualifiedRelation
from app.telemetry.scoped_attribution import LocalityDisposition
from tests.unit.test_scoped_applicability import (
    K1,
    ORACLE,
    P1,
    P1_NAME,
    P2,
    P2_NAME,
    D,
    _pod,
    _record,
    _request,
    _source,
)

_VECTORS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/specifications/0.6.0/i2-vectors/local-assessment-id.json"
    ).read_text(encoding="utf-8")
)
ASSERTION_VECTORS = {v["id"]: v for v in _VECTORS["assertion_vectors"]}
ASSESSMENT_VECTORS = {v["id"]: v for v in _VECTORS["assessment_vectors"]}

O1 = "operation:pricing:GET:/prices"
O2 = "operation:legacy-pricing:GET:/prices"
O3 = "operation:pricing:GET:/prices/{id}"
SNAPSHOT = "aip:snapshot:v1:" + "a" * 64
DECLARED = "evidence:declared:orders-calls-pricing"
V1_OBSERVED = "evidence:otel:production:2026-09-28:v1-bucket"


def _uid_workload(name: str, uid: str) -> CapturedWorkload:
    return CapturedWorkload(
        workload_id=f"workload:{K1}:shop:Deployment:{name}",
        kind="Deployment",
        namespace="shop",
        name=name,
        cluster_uid=K1,
        uid=uid,
    )


W1 = _uid_workload("orders", ASSERTION_VECTORS["A01-v01-w1-o1-day-d"]["fields"]["workload"]["uid"])
W2 = _uid_workload("orders-canary", ASSERTION_VECTORS["A03-w2-o2"]["fields"]["workload"]["uid"])
CAP_A = _source("cap-a", _pod(P1, P1_NAME, W1), _pod(P2, P2_NAME, W2))

DECLARED_ROW = {"id": DECLARED, "evidence_type": "DECLARED", "environment": None, "last_seen": None}
V1_ROW = {
    "id": V1_OBSERVED,
    "evidence_type": "OBSERVED",
    "environment": "production",
    "last_seen": _record("V01-base").last_seen,
}


def _declared(**edges: tuple[str, ...]) -> DeclaredCallEvidence:
    """`edges` maps O1/O2/O3 names to that Operation's legacy CALLS edge evidence ids."""
    operations = {"O1": O1, "O2": O2, "O3": O3}
    return DeclaredCallEvidence(
        edge_evidence_ids={operations[name]: ids for name, ids in edges.items()},
        evidence_rows={DECLARED: DECLARED_ROW, V1_OBSERVED: V1_ROW},
    )


def _read(
    records,
    sources=(CAP_A,),
    *,
    declared=None,
    request=None,
    truncated=False,
    snapshot=SNAPSHOT,
) -> tuple[ScopedApplicabilityRead, LocalityRequest]:
    request = request or _request()
    return (
        ScopedApplicabilityRead(
            snapshot_id=snapshot,
            model_revision="sha256:" + snapshot.rsplit(":", 1)[1],
            result=evaluate_candidates(request, records, list(sources), truncated=truncated),
            declared=declared or DeclaredCallEvidence({}, {}),
        ),
        request,
    )


def _assess(records, sources=(CAP_A,), **kwargs):
    read, request = _read(records, sources, **kwargs)
    return assess(read, request)


def _v2(pod_uid: str, operation_id: str, *, pod_attributes: dict | None = None):
    """A v2 record for any Operation (the key vectors only cover O1/O2)."""
    base = _record("V01-base" if pod_uid == P1 else "V03-distinct-pod")
    fields = {
        "environment": base.environment,
        "bucket_utc_day": base.bucket_utc_day,
        "subject_id": base.subject_id,
        "object_id": operation_id,
        "caller_cluster_uid": base.caller_cluster_uid,
        "caller_pod_uid": pod_uid,
    }
    return base.model_copy(
        update={
            **fields,
            "id": scoped_observed_call_v2_id(**fields),
            **(pod_attributes or {}),
        }
    )


def _by_operation(result):
    return {a.object_operation_id: a for a in result.assertions}


# --- The frozen I2.4a vectors ------------------------------------------------------------------


@pytest.mark.parametrize("vector", list(ASSERTION_VECTORS.values()), ids=lambda v: v["id"])
def test_the_assertion_id_reproduces_every_frozen_vector(vector):
    fields = vector["fields"]
    workload = fields["workload"]
    assertion_id = compute_local_assertion_id(
        subject_service_id=fields["subject_service_id"],
        object_operation_id=fields["object_operation_id"],
        environment=fields["environment"],
        window=ScopedDayWindowV1.parse(fields["first_utc_day"], fields["last_utc_day"]),
        workload=CapturedWorkload(
            workload_id="any-logical-id",
            kind=workload["kind"],
            namespace=workload["namespace"],
            name="any-name",
            cluster_uid=workload["cluster_uid"],
            uid=workload["uid"],
        ),
    )
    assert assertion_id == vector["expected_id"]


@pytest.mark.parametrize("vector", list(ASSESSMENT_VECTORS.values()), ids=lambda v: v["id"])
def test_the_assessment_id_reproduces_every_frozen_vector(vector):
    fields = vector["fields"]
    assessment_id = compute_local_assessment_id(
        assertion_id=fields["assertion_id"],
        snapshot_id=fields["snapshot_id"],
        capture_revisions=[
            (c["source_instance_id"], c["revision"]) for c in fields["capture_revisions"]
        ],
        rules=[(r["id"], r["version"]) for r in fields["rules"]],
    )
    assert assessment_id == vector["expected_id"]


def test_the_default_rules_are_exactly_the_frozen_four():
    [vector] = [v for v in ASSESSMENT_VECTORS.values() if "same_id_as" not in v][:1]
    assert RULES == tuple(sorted((r["id"], r["version"]) for r in vector["fields"]["rules"]))


def test_a_workload_without_a_captured_uid_has_no_assertion_id():
    with pytest.raises(ValueError):
        compute_local_assertion_id(
            subject_service_id="service:orders",
            object_operation_id=O1,
            environment="production",
            window=ScopedDayWindowV1(date(2026, 9, 28), date(2026, 9, 28)),
            workload=replace(W1, uid=None),
        )


# --- Qualification through the shared kernel (I2 §10, D14.4) ----------------------------------


def test_l21_an_applicable_declaration_confirms_the_local_call():
    result = _assess([_record("V01-base")], declared=_declared(O1=(DECLARED,)))
    [assertion] = result.assertions
    assert assertion.qualification == CONFIRMED
    assert assertion.declared_evidence_ids == (DECLARED,)
    assert assertion.assertion_id == ASSERTION_VECTORS["A01-v01-w1-o1-day-d"]["expected_id"]
    assert assertion.caller_workload == W1
    assert result.disposition is LocalityDisposition.APPLICABLE and result.reasons == ()


@pytest.mark.parametrize("with_o1_declaration", [False, True], ids=["L22a", "L22b"])
def test_l22_without_its_own_declaration_the_call_is_observed_only(with_o1_declaration):
    declared = _declared(O1=(DECLARED,)) if with_o1_declaration else None
    result = _assess([_record("V06-other-operation")], declared=declared)
    [assertion] = result.assertions
    assert assertion.qualification == OBSERVED_ONLY
    assert assertion.declared_evidence_ids == ()
    assert assertion.assertion_id == ASSERTION_VECTORS["A03-w2-o2"]["expected_id"]


def test_l32a_each_operation_is_qualified_on_its_own():
    records = [_record("V01-base"), _v2(P1, O3)]
    result = _assess(records, declared=_declared(O1=(DECLARED,)))
    qualification = {op: a.qualification for op, a in _by_operation(result).items()}
    assert qualification == {O1: CONFIRMED, O3: OBSERVED_ONLY}


def test_v1_observed_evidence_never_pools_into_a_local_answer():
    only_v1 = _assess([_record("V01-base")], declared=_declared(O1=(V1_OBSERVED,)))
    [assertion] = only_v1.assertions
    assert assertion.qualification == OBSERVED_ONLY
    assert assertion.declared_evidence_ids == ()
    assert V1_OBSERVED not in assertion.observation.evidence_ids

    mixed = _assess([_record("V01-base")], declared=_declared(O1=(DECLARED, V1_OBSERVED)))
    [assertion] = mixed.assertions
    assert (assertion.qualification, assertion.declared_evidence_ids) == (CONFIRMED, (DECLARED,))
    assert assertion.observation.evidence_ids == (_record("V01-base").id,)


def test_the_kernel_is_the_only_qualification_owner(monkeypatch):
    calls = []
    real = local_assessment.qualify_relation

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(local_assessment, "qualify_relation", spy)
    _assess([_record("V01-base")], declared=_declared(O1=(DECLARED,)))
    [(args, kwargs)] = calls
    assert sorted(args[0]) == sorted([DECLARED, _record("V01-base").id])
    assert kwargs["relation_type"] == "CALLS"


def test_a_local_not_observed_in_window_can_never_be_emitted(monkeypatch):
    monkeypatch.setattr(
        local_assessment,
        "qualify_relation",
        lambda *a, **k: QualifiedRelation("NOT_OBSERVED_IN_WINDOW", "UNKNOWN", [DECLARED]),
    )
    with pytest.raises(AssertionError):
        _assess([_record("V01-base")], declared=_declared(O1=(DECLARED,)))


@settings(max_examples=60, deadline=None)
@given(
    edges=st.dictionaries(
        st.sampled_from(["O1", "O2", "O3"]),
        st.lists(st.sampled_from([DECLARED, V1_OBSERVED, "evidence:dangling"]), max_size=3).map(
            tuple
        ),
    ),
    vectors=st.sets(
        st.sampled_from(["V01-base", "V03-distinct-pod", "V06-other-operation"]), min_size=1
    ),
)
def test_every_assertion_is_confirmed_or_observed_only(edges, vectors):
    result = _assess([_record(v) for v in sorted(vectors)], declared=_declared(**edges))
    assert result.assertions
    assert {a.qualification for a in result.assertions} <= {CONFIRMED, OBSERVED_ONLY}


# --- Answer level (I1 §10.2, D14.5) ------------------------------------------------------------


def _answer_expectation(case_id: str, variant_id: str) -> dict:
    [case] = [c for c in ORACLE["cases"] if c["id"] == case_id]
    [variant] = [v for v in case["variants"] if v["id"] == variant_id]
    return variant["expected"]["answer"]


@pytest.mark.parametrize(
    ("case_id", "variant_id"),
    [("L05", "a"), ("L06", "d"), ("L23", "a"), ("L26", "a"), ("L35", "h")],
)
def test_without_eligible_v2_the_answer_abstains(case_id, variant_id):
    """Declared-only, v1-only, name/DEPLOYED_AS-only or refused-only: no v2 candidate exists."""
    expected = _answer_expectation(case_id, variant_id)
    result = _assess([], declared=_declared(O1=(DECLARED, V1_OBSERVED)))
    assert result.assertions == () and result.candidate_limitations == ()
    assert result.disposition == expected["disposition"]
    assert list(result.reasons) == expected["reasons"]


def test_a_non_positive_candidate_is_a_limitation_without_an_assertion_id():
    cap_b = _source("cap-a", _pod(P2, P2_NAME, W2), captured_at=f"{D}T18:00:00Z", revision="r2")
    result = _assess([_record("V01-base")], [cap_b], declared=_declared(O1=(DECLARED,)))
    assert result.assertions == ()
    [limitation] = result.candidate_limitations
    assert limitation.v2_evidence_id == _record("V01-base").id
    assert limitation.snapshot_id == SNAPSHOT
    assert limitation.disposition is LocalityDisposition.UNRESOLVED
    assert limitation.reasons == ("LOCALITY_CAPTURE_MISSING_POD",)
    assert result.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert not any(ASSERTION_PREFIX in str(v) for v in dataclasses.astuple(limitation))


def test_a_workload_without_a_captured_uid_becomes_a_limitation():
    source = _source("cap", _pod(P1, P1_NAME, replace(W1, uid=None)))
    result = _assess([_record("V01-base")], [source])
    assert result.assertions == ()
    [limitation] = result.candidate_limitations
    assert limitation.disposition is LocalityDisposition.APPLICABLE
    assert limitation.limitations == (AssessmentLimitation.WORKLOAD_UID_UNAVAILABLE,)


def test_a_phase_one_refusal_passes_through():
    read, request = _read([], request=_request(relation_type="SENDS"))
    result = assess(read, request)
    assert result.disposition is LocalityDisposition.UNSUPPORTED
    assert result.reasons == ("LOCALITY_UNSUPPORTED_RELATION",)


# --- Grouping, lineage and determinism (D14.3, D14.7, D14.8) ----------------------------------


def test_l33a_two_pods_of_one_workload_are_one_assertion():
    source = _source("cap", _pod(P1, "orders-rs1-a", W1), _pod(P2, "orders-rs2-b", W1))
    records = [
        _record("V01-base", attributes=False),
        _record("V03-distinct-pod", attributes=False),
    ]
    [assertion] = _assess(records, [source]).assertions
    assert assertion.assertion_id == ASSERTION_VECTORS["A02-other-pod-same-workload"]["expected_id"]
    assert assertion.observation.evidence_ids == tuple(sorted(r.id for r in records))
    assert assertion.observation.first_seen == min(r.first_seen for r in records)
    assert assertion.observation.last_seen == max(r.last_seen for r in records)


def test_l33b_two_workloads_are_two_assertions():
    records = [_record("V01-base"), _v2(P2, O1, pod_attributes={"k8s_deployment_name": None})]
    result = _assess(records)
    assert {a.caller_workload for a in result.assertions} == {W1, W2}


def test_the_assessment_carries_its_capture_lineage_and_source_limitations():
    other = _source("zz-b")  # covers P1's cluster and namespace but lacks the Pod
    [assertion] = _assess([_record("V01-base")], [CAP_A, other]).assertions
    assert [c.source_instance_id for c in assertion.selected_captures] == ["cap-a"]
    assert assertion.selected_captures[0].captured_at == CAP_A.capture.captured_at
    [(v2_id, pair)] = assertion.source_limitations
    assert (v2_id, pair.source.source_instance_id) == (_record("V01-base").id, "zz-b")
    assert pair.reasons == ("LOCALITY_CAPTURE_MISSING_POD",)
    assert assertion.target_runtime_scope == "UNKNOWN"
    assert assertion.coverage == "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"


def test_the_instance_id_is_bound_to_the_snapshot_and_the_assertion_id_is_not():
    records = [_record("V01-base")]
    [a] = _assess(records).assertions
    [b] = _assess(records, snapshot="aip:snapshot:v1:" + "b" * 64).assertions
    assert a.assertion_id == b.assertion_id
    assert a.assessment_id != b.assessment_id
    assert a.assessment_id == compute_local_assessment_id(
        assertion_id=a.assertion_id, snapshot_id=SNAPSHOT, capture_revisions=[("cap-a", "r1")]
    )


def test_the_result_is_independent_of_every_input_order():
    records = [_record("V01-base"), _record("V06-other-operation"), _v2(P1, O3)]
    other = _source("zz-b")
    results = [
        _assess(
            list(record_order),
            list(source_order),
            declared=DeclaredCallEvidence({O1: ids}, {DECLARED: DECLARED_ROW, V1_OBSERVED: V1_ROW}),
        )
        for record_order in itertools.permutations(records)
        for source_order in itertools.permutations([CAP_A, other])
        for ids in [(DECLARED, V1_OBSERVED), (V1_OBSERVED, DECLARED)]
    ]
    assert all(result == results[0] for result in results)


def test_a_truncated_page_marks_the_lineage_incomplete():
    result = _assess([_record("V01-base")], truncated=True)
    [assertion] = result.assertions
    assert assertion.observation.lineage_complete is False
    assert result.truncated and result.next_after_id == _record("V01-base").id


def test_l30_no_narrative_or_intent_input_exists():
    """D14.6: Current State only - neither the request nor the assessment has a narrative field."""
    names = {f.name for f in dataclasses.fields(LocalityRequest)} | {
        f.name for f in dataclasses.fields(QualifiedLocalEvidenceAssessment)
    }
    assert not {n for n in names if any(w in n for w in ("intent", "narrative", "description"))}


def test_two_incarnations_of_one_logical_workload_are_two_assertions():
    """PR #365 review: the captured UID is part of the assertion identity (D9, D14.1), so two
    incarnations of one logical Workload (same cluster/kind/namespace/name, different captured
    UID) are never merged, and each keeps only its own lineage and capture."""
    recreated = replace(W1, uid="22222222-bbbb-4ccc-8ddd-0000000000ff")
    assert recreated.workload_id == W1.workload_id
    first = _source("cap-a", _pod(P1, P1_NAME, W1))
    second = _source("cap-b", _pod(P2, "orders-new-x", recreated))
    records = [_record("V01-base", attributes=False), _record("V03-distinct-pod", attributes=False)]

    result = _assess(records, [first, second])

    by_uid = {a.caller_workload.uid: a for a in result.assertions}
    assert set(by_uid) == {W1.uid, recreated.uid}
    assert len({a.assertion_id for a in result.assertions}) == 2
    assert by_uid[W1.uid].assertion_id == ASSERTION_VECTORS["A01-v01-w1-o1-day-d"]["expected_id"]
    assert by_uid[W1.uid].observation.evidence_ids == (records[0].id,)
    assert by_uid[recreated.uid].observation.evidence_ids == (records[1].id,)
    assert [c.source_instance_id for c in by_uid[W1.uid].selected_captures] == ["cap-a"]
    assert [c.source_instance_id for c in by_uid[recreated.uid].selected_captures] == ["cap-b"]
