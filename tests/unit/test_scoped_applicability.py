"""v0.6.0 I2.3a: the pure selected-capture applicability evaluator.

Expected results come from the independently authored, read-only I1 oracle
(`docs/specifications/0.6.0/i1-vectors/conformance-expected.json`, `utc-day-window.json`) and the
decision record's S01-S06 table (D4). This file only *realizes* the oracle's abstract captures as
concrete inputs (D13.1); it never restates an expected disposition or reason for an oracle row.
"""

import itertools
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.architecture_intelligence.scoped_applicability import (
    AdmissionBasis,
    CapturedWorkload,
    LocalityRequest,
    RequestRefusal,
    ScopedDayWindowV1,
    ScopedLimitation,
    ScopedOwner,
    ScopedPod,
    SourceCapture,
    SourceInventory,
    SourceSelector,
    evaluate_candidates,
    preflight,
)
from app.canonical.ids import scoped_observed_call_v2_id
from app.provenance.model import ScopedObservedCall
from app.telemetry.scoped_attribution import LocalityDisposition

_VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.6.0/i1-vectors"
ORACLE = json.loads((_VECTORS / "conformance-expected.json").read_text(encoding="utf-8"))
WINDOW_VECTORS = json.loads((_VECTORS / "utc-day-window.json").read_text(encoding="utf-8"))
KEY_VECTORS = {
    vector["id"]: vector
    for vector in json.loads((_VECTORS / "v2-evidence-id.json").read_text(encoding="utf-8"))[
        "key_vectors"
    ]
}

FIXTURES = ORACLE["fixtures"]
D = FIXTURES["D"]
D1 = FIXTURES["D+1"]
K1 = FIXTURES["clusters"]["K1"]
K2 = FIXTURES["clusters"]["K2"]
P1 = FIXTURES["pods"]["P1"]
P2 = FIXTURES["pods"]["P2"]
CALLER = FIXTURES["caller"]
ENVIRONMENT = FIXTURES["environment"]

P1_NAME = "orders-7d9f8b6c5-abcde"
P2_NAME = "orders-canary-5c4b3a2d1-fghij"


def _workload(name: str, *, namespace: str = "shop", cluster: str = K1, kind: str = "Deployment"):
    return CapturedWorkload(
        workload_id=f"workload:{cluster}:{namespace}:{kind}:{name}",
        kind=kind,
        namespace=namespace,
        name=name,
        cluster_uid=cluster,
    )


W1 = _workload("orders")
W2 = _workload("orders-canary")
WORKLOADS = {"W1": W1, "W2": W2}


def _pod(uid: str, name: str, *owners: CapturedWorkload, namespace="shop", cluster=K1):
    return ScopedPod(
        pod_id=f"pod:{cluster}:{namespace}:{name}",
        name=name,
        namespace=namespace,
        cluster_uid=cluster,
        captured_uid=uid,
        owners=tuple(
            ScopedOwner(workload_id=w.workload_id, workload=w, evidence_refs=(f"ev:{w.name}",))
            for w in owners
        ),
        evidence_refs=(f"ev:{name}",),
    )


def _source(
    source_id: str,
    *pods: ScopedPod,
    cluster: str = K1,
    namespaces=("shop",),
    captured_at: str = f"{D}T12:00:00Z",
    mode: str = "CAPTURED_RESOURCE",
    revision: str = "r1",
) -> SourceInventory:
    return SourceInventory(
        capture=SourceCapture(
            source_instance_id=source_id,
            discovery_scope_id="scope",
            revision=revision,
            cluster_uid=cluster,
            namespaces=tuple(namespaces),
            evidence_mode=mode,
            captured_at=captured_at,
        ),
        pods=pods,
    )


# The oracle's abstract captures (dossier §2), realized per D13.1.
CAPTURES = {
    "CAP-A": _source("cap-a", _pod(P1, P1_NAME, W1), _pod(P2, P2_NAME, W2)),
    "CAP-B": _source("cap-a", _pod(P2, P2_NAME, W2), captured_at=f"{D}T18:00:00Z", revision="r2"),
    "CAP-A-D1": _source(
        "cap-a", _pod(P1, P1_NAME, W1), _pod(P2, P2_NAME, W2), captured_at=f"{D1}T12:00:00Z"
    ),
    "CAP-A-NOTIME": _source(
        "cap-a", _pod(P1, P1_NAME, W1), _pod(P2, P2_NAME, W2), captured_at=f"{D}T12:00:00"
    ),
    # A manifest carries no captured UID; its contradictory owner data must never be looked at.
    "CAP-DM": _source("cap-dm", _pod(P1, P1_NAME, W1, W2), mode="DECLARED_MANIFEST"),
    # D13.1: two distinct captured Pods sharing UID P1, owned by W1 and W2.
    "CAP-AMB": _source("cap-amb", _pod(P1, "orders-a", W1), _pod(P1, "orders-b", W2)),
    # D13.1: P1 captured under W2, while the CLIENT named Deployment `orders`.
    "CAP-CONF": _source("cap-conf", _pod(P1, P1_NAME, W2)),
    "CAP-CONF-D1": _source("cap-conf", _pod(P1, P1_NAME, W2), captured_at=f"{D1}T12:00:00Z"),
}

_POD_ATTRIBUTES = {
    P1: {"k8s_namespace_name": "shop", "k8s_pod_name": P1_NAME, "k8s_deployment_name": "orders"},
    P2: {
        "k8s_namespace_name": "shop",
        "k8s_pod_name": P2_NAME,
        "k8s_deployment_name": "orders-canary",
    },
}


def _record(vector_id: str, *, attributes: bool = True, **overrides) -> ScopedObservedCall:
    """The v2 record of an independent key vector, with the optional CLIENT attributes the
    snapshot fragment gives V01 (or none), and `last_seen` inside the vector's own day."""
    vector = KEY_VECTORS[vector_id]
    key = vector["input"]
    day = key["bucket_utc_day"]
    fields = {
        "environment": key["environment"],
        "bucket_utc_day": day,
        "subject_id": key["subject_id"],
        "object_id": key["object_id"],
        "caller_cluster_uid": key["caller_cluster_uid"],
        "caller_pod_uid": key["caller_pod_uid"],
    }
    record_id = scoped_observed_call_v2_id(**fields)
    assert record_id == vector["evidence_id"]
    values = {
        **fields,
        "id": record_id,
        "first_seen": datetime.fromisoformat(f"{day}T10:00:00.200000+00:00"),
        "last_seen": datetime.fromisoformat(f"{day}T16:45:12.000001+00:00"),
        "observation_count": 3,
        "correlation_mode": "CLIENT_SERVER",
        **(_POD_ATTRIBUTES[key["caller_pod_uid"]] if attributes else {}),
        **overrides,
    }
    return ScopedObservedCall(**values)


def _request(**overrides) -> LocalityRequest:
    values = {
        "subject_service_id": CALLER,
        "environment": ENVIRONMENT,
        "first_day": D,
        "last_day": D,
    }
    return LocalityRequest(**{**values, **overrides})


def _selector(capture: str) -> SourceSelector:
    source = CAPTURES[capture].capture
    return SourceSelector(source.source_instance_id, source.revision)


# --- Oracle rows -------------------------------------------------------------------------------

# How each oracle variant's inputs are realized (never its expected result). Keyed by
# (case, variant, candidate, capture): request overrides and record overrides.
_REALIZATION = {
    ("L10", "b"): {"request": {"environment": "staging"}},
    ("L17", "d"): {"request": {"first_day": D1, "last_day": D1}},
    ("L34", "a"): {"record": {"k8s_namespace_name": "shop-old"}},
}
# D13.1: CAP-AMB is evaluated for a V01 without optional CLIENT attributes.
_CAPTURE_RECORD = {"CAP-AMB": {"attributes": False}}

_ORACLE_CASES = {
    "L10", "L15", "L16", "L17", "L18", "L19", "L20", "L27", "L29", "L31", "L34", "L35", "L36",
    "L37",
}  # fmt: skip


def _oracle_rows():
    for case in ORACLE["cases"]:
        if case["id"] not in _ORACLE_CASES:
            continue
        for variant in case["variants"]:
            for index, expected in enumerate(variant["expected"].get("query", [])):
                yield pytest.param(
                    case["id"],
                    variant["id"],
                    expected,
                    id=f"{case['id']}{variant['id']}-{index}-{expected['candidate']}",
                )


def _evaluate_oracle_row(case_id, variant_id, expected, *, explicit: bool):
    realization = _REALIZATION.get((case_id, variant_id), {})
    capture = expected["selected_capture"]
    record = _record(
        expected["candidate"],
        **_CAPTURE_RECORD.get(capture, {}),
        **realization.get("record", {}),
    )
    request = _request(
        selector=_selector(capture) if explicit else None, **realization.get("request", {})
    )
    result = evaluate_candidates(request, [record], [CAPTURES[capture]])
    [candidate] = result.candidates
    return candidate


@pytest.mark.parametrize("explicit", [True, False], ids=["explicit", "implicit"])
@pytest.mark.parametrize(("case_id", "variant_id", "expected"), list(_oracle_rows()))
def test_every_single_capture_oracle_row(case_id, variant_id, expected, explicit):
    candidate = _evaluate_oracle_row(case_id, variant_id, expected, explicit=explicit)
    [pair] = candidate.pairs
    assert pair.phase == expected["phase"]
    assert pair.disposition == expected["disposition"]
    assert list(pair.reasons) == expected["reasons"]
    assert candidate.disposition == expected["disposition"]
    assert list(candidate.reasons) == expected["reasons"]
    if "workload" in expected:
        want = WORKLOADS[expected["workload"]]
        assert (pair.workload.kind, pair.workload.namespace, pair.workload.name) == (
            want.kind,
            want.namespace,
            want.name,
        )
    else:
        assert pair.workload is None and candidate.workload is None
    assert pair.admission == ((AdmissionBasis.EXPLICIT,) if explicit else pair.admission)


def test_the_oracle_rows_cover_every_i2_3_query_case():
    covered = {param.values[0] for param in _oracle_rows()}
    assert covered == _ORACLE_CASES


def test_l10b_carries_the_internal_environment_limitation_and_no_locality_code():
    [expected] = next(
        v["expected"]["query"]
        for c in ORACLE["cases"]
        if c["id"] == "L10"
        for v in c["variants"]
        if v["id"] == "b"
    )
    candidate = _evaluate_oracle_row("L10", "b", expected, explicit=True)
    assert candidate.limitations == (ScopedLimitation.REQUEST_ENVIRONMENT_MISMATCH,)
    assert candidate.pairs[0].limitations == (ScopedLimitation.REQUEST_ENVIRONMENT_MISMATCH,)


@pytest.mark.parametrize(("capture", "phase"), [("CAP-CONF-D1", 3), ("CAP-DM", 2)])
def test_later_phases_are_never_evaluated_after_a_terminating_one(capture, phase):
    """L36/L37: the contradictory owner data would otherwise yield CONFLICT/AMBIGUOUS."""
    record = _record("V01-base")
    result = evaluate_candidates(
        _request(selector=_selector(capture)), [record], [CAPTURES[capture]]
    )
    [pair] = result.candidates[0].pairs
    assert pair.phase == phase
    assert pair.disposition not in (LocalityDisposition.CONFLICT, LocalityDisposition.AMBIGUOUS)
    assert pair.workload is None and pair.evidence_refs == ()


def test_l27a_two_localities_coexist_for_one_caller_service():
    records = [_record("V01-base"), _record("V06-other-operation")]
    result = evaluate_candidates(_request(), records, [CAPTURES["CAP-A"]])
    assert [c.disposition for c in result.candidates] == [LocalityDisposition.APPLICABLE] * 2
    assert {c.workload.workload_id for c in result.candidates if c.workload} == {
        W1.workload_id,
        W2.workload_id,
    }


def test_l18_the_replaced_pod_stays_attributed_to_its_own_record():
    records = [_record("V01-base"), _record("V03-distinct-pod")]
    result = evaluate_candidates(_request(), records, [CAPTURES["CAP-B"]])
    by_id = {c.record.caller_pod_uid: c for c in result.candidates}
    assert by_id[P1].disposition is LocalityDisposition.UNRESOLVED
    assert by_id[P1].record == records[0]
    assert by_id[P2].workload == W2


def test_l33_two_replica_sets_of_one_deployment_are_one_workload():
    source = _source("cap", _pod(P1, "orders-rs1-a", W1), _pod(P2, "orders-rs2-b", W1))
    records = [
        _record("V01-base", attributes=False),
        _record("V03-distinct-pod", attributes=False),
    ]
    result = evaluate_candidates(_request(), records, [source])
    assert {c.record.id for c in result.candidates} == {r.id for r in records}
    assert {c.workload.workload_id for c in result.candidates if c.workload} == {W1.workload_id}


# --- Decision record D4: S01-S06 ---------------------------------------------------------------

A = _source("a", _pod(P1, P1_NAME, W1))


def _s(sources, *, record=None):
    record = record or _record("V01-base")
    [candidate] = evaluate_candidates(_request(), [record], sources).candidates
    return candidate


def _pairs(candidate):
    return {
        pair.source.source_instance_id: (pair.disposition, list(pair.reasons))
        for pair in candidate.pairs
    }


def test_s01_an_unrelated_namespace_is_omitted():
    candidate = _s([A, _source("b", namespaces=("billing",))])
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert candidate.workload == W1
    assert _pairs(candidate) == {"a": (LocalityDisposition.APPLICABLE, [])}


def test_s02_an_unrelated_cluster_is_omitted():
    candidate = _s([A, _source("b", cluster=K2)])
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert _pairs(candidate) == {"a": (LocalityDisposition.APPLICABLE, [])}


def test_s03_a_covering_source_keeps_its_missing_pod_limitation():
    candidate = _s([A, _source("b")])
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert candidate.workload == W1
    assert candidate.supporting_sources == (("a", "r1"),)
    assert _pairs(candidate) == {
        "a": (LocalityDisposition.APPLICABLE, []),
        "b": (LocalityDisposition.UNRESOLVED, ["LOCALITY_CAPTURE_MISSING_POD"]),
    }


def test_s04_the_same_pod_uid_in_another_cluster_is_a_conflict():
    b = _source("b", _pod(P1, P1_NAME, _workload("orders", cluster=K2), cluster=K2), cluster=K2)
    candidate = _s([A, b])
    assert candidate.disposition is LocalityDisposition.CONFLICT
    assert candidate.workload is None
    assert _pairs(candidate) == {
        "a": (LocalityDisposition.APPLICABLE, []),
        "b": (LocalityDisposition.CONFLICT, ["LOCALITY_CLUSTER_UID_CONFLICT"]),
    }


def test_s05_only_the_later_capture_without_the_pod():
    candidate = _s([_source("c2", captured_at=f"{D}T18:00:00Z")])
    assert candidate.disposition is LocalityDisposition.UNRESOLVED
    assert list(candidate.reasons) == ["LOCALITY_CAPTURE_MISSING_POD"]
    assert _pairs(candidate) == {
        "c2": (LocalityDisposition.UNRESOLVED, ["LOCALITY_CAPTURE_MISSING_POD"])
    }


def test_s06_no_covering_source_is_insufficient_evidence_never_a_missing_pod():
    record = _record("V01-base", k8s_namespace_name=None)
    candidate = _s([_source("a"), _source("b", namespaces=("billing",))], record=record)
    assert candidate.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert list(candidate.reasons) == ["LOCALITY_LOCAL_COVERAGE_UNAVAILABLE"]
    assert candidate.limitations == (ScopedLimitation.NO_SELECTABLE_COVERING_SOURCE,)
    assert candidate.pairs == ()
    assert candidate.record == record


# --- Roll-up and selection details (D13) -------------------------------------------------------


@pytest.mark.parametrize(
    "sources",
    [
        [A, _source("b")],
        [A, _source("b", _pod(P1, P1_NAME, _workload("x", cluster=K2), cluster=K2), cluster=K2)],
        [A, _source("b"), _source("c", namespaces=("billing",)), _source("d", cluster=K2)],
    ],
)
def test_the_result_is_independent_of_source_order(sources):
    results = [_s(list(order)) for order in itertools.permutations(sources)]
    assert all(result == results[0] for result in results)
    keys = [pair.source.sort_key for pair in results[0].pairs]
    assert keys == sorted(keys)


def test_two_applicable_pairs_naming_different_workloads_conflict():
    other = _workload("orders-shadow", namespace="shop2")
    record = _record("V01-base", attributes=False)
    candidate = _s(
        [A, _source("c", _pod(P1, "orders-x", other, namespace="shop2"), namespaces=("shop2",))],
        record=record,
    )
    assert [pair.disposition for pair in candidate.pairs] == [LocalityDisposition.APPLICABLE] * 2
    assert candidate.disposition is LocalityDisposition.CONFLICT
    assert list(candidate.reasons) == ["LOCALITY_POD_OWNER_CONFLICT"]
    assert candidate.workload is None


def test_two_sources_capturing_the_same_workload_support_it_together():
    a2 = replace(A, capture=replace(A.capture, source_instance_id="a2"))
    candidate = _s([A, a2])
    assert candidate.disposition is LocalityDisposition.APPLICABLE
    assert candidate.supporting_sources == (("a", "r1"), ("a2", "r1"))


def test_disagreeing_non_positive_pairs_invent_no_combined_cause():
    late = _source("late", captured_at=f"{D1}T12:00:00Z")
    candidate = _s([_source("c2"), late])
    assert _pairs(candidate) == {
        "c2": (LocalityDisposition.UNRESOLVED, ["LOCALITY_CAPTURE_MISSING_POD"]),
        "late": (LocalityDisposition.INAPPLICABLE, ["LOCALITY_CAPTURE_TEMPORAL_MISMATCH"]),
    }
    assert candidate.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert candidate.reasons == () and candidate.limitations == ()


def test_agreeing_non_positive_pairs_keep_their_common_disposition():
    candidate = _s([_source("c2"), _source("c3")])
    assert candidate.disposition is LocalityDisposition.UNRESOLVED
    assert list(candidate.reasons) == ["LOCALITY_CAPTURE_MISSING_POD"]


@pytest.mark.parametrize(
    "selector",
    [SourceSelector("nowhere", "r1"), SourceSelector("a", "r0")],
    ids=["absent", "stale"],
)
def test_an_absent_or_stale_explicit_selector_selects_nothing(selector):
    [candidate] = evaluate_candidates(
        _request(selector=selector), [_record("V01-base")], [A]
    ).candidates
    assert candidate.pairs == ()
    assert candidate.disposition is LocalityDisposition.INSUFFICIENT_EVIDENCE
    assert list(candidate.reasons) == ["LOCALITY_LOCAL_COVERAGE_UNAVAILABLE"]
    assert candidate.limitations == (ScopedLimitation.NO_SELECTABLE_COVERING_SOURCE,)


def test_an_explicit_selector_ignores_the_implicit_coverage_predicate():
    billing = _source("b", namespaces=("billing",))
    [candidate] = evaluate_candidates(
        _request(selector=SourceSelector("b", "r1")), [_record("V01-base")], [A, billing]
    ).candidates
    assert _pairs(candidate) == {
        "b": (LocalityDisposition.UNRESOLVED, ["LOCALITY_CAPTURE_MISSING_POD"])
    }


def test_a_source_admitted_by_both_rules_is_paired_once():
    [candidate] = evaluate_candidates(_request(), [_record("V01-base")], [A]).candidates
    [pair] = candidate.pairs
    assert pair.admission == (AdmissionBasis.POD_UID, AdmissionBasis.CLUSTER_NAMESPACE)


def test_rule_two_needs_the_client_namespace():
    record = _record("V01-base", k8s_namespace_name=None)
    [candidate] = evaluate_candidates(_request(), [record], [_source("c2")]).candidates
    assert candidate.pairs == ()


# --- Within-phase collection (D13.2) -----------------------------------------------------------


def _one_pair(record, source):
    [candidate] = evaluate_candidates(_request(), [record], [source]).candidates
    [pair] = candidate.pairs
    return pair


def test_phase_three_keeps_every_established_cause():
    record = _record("V07-next-day")
    pair = _one_pair(record, _source("a", _pod(P1, P1_NAME, W1), captured_at="bad"))
    assert pair.phase == 3
    assert pair.disposition is LocalityDisposition.INAPPLICABLE
    assert list(pair.reasons) == [
        "LOCALITY_CAPTURE_TIMESTAMP_MISSING",
        "LOCALITY_OBSERVATION_TEMPORAL_MISMATCH",
    ]


def test_phase_four_unions_identity_and_owner_causes():
    pod = replace(_pod(P1, P1_NAME, W1), owners=())
    pair = _one_pair(_record("V04-same-pod-uid-other-cluster"), _source("a", pod))
    assert pair.disposition is LocalityDisposition.CONFLICT
    assert list(pair.reasons) == ["LOCALITY_CLUSTER_UID_CONFLICT", "LOCALITY_POD_OWNER_UNRESOLVED"]
    assert pair.workload is None


@pytest.mark.parametrize(
    ("owner", "reason"),
    [
        (ScopedOwner(workload_id="gone", workload=None), "LOCALITY_POD_OWNER_UNRESOLVED"),
        (
            ScopedOwner(workload_id="job", workload=_workload("batch", kind="Job")),
            "LOCALITY_POD_OWNER_UNRESOLVED",
        ),
    ],
    ids=["workload-not-current", "unsupported-kind"],
)
def test_an_unresolvable_owner_is_unresolved(owner, reason):
    pod = replace(_pod(P1, P1_NAME), owners=(owner,))
    pair = _one_pair(_record("V01-base", attributes=False), _source("a", pod))
    assert (pair.disposition, list(pair.reasons)) == (LocalityDisposition.UNRESOLVED, [reason])


@pytest.mark.parametrize(
    "overrides",
    [
        {"k8s_pod_name": "someone-else"},
        {"k8s_deployment_name": None, "k8s_statefulset_name": "orders"},
        {"conflicting_consistency_attributes": ["k8s_pod_name"], "k8s_pod_name": None},
    ],
    ids=["pod-name", "other-workload-kind", "flagged-attribute"],
)
def test_a_contradicting_client_attribute_is_an_owner_conflict(overrides):
    pair = _one_pair(_record("V01-base", **overrides), A)
    assert (pair.disposition, list(pair.reasons)) == (
        LocalityDisposition.CONFLICT,
        ["LOCALITY_POD_OWNER_CONFLICT"],
    )


def test_an_applicable_pair_carries_its_capture_lineage():
    pair = _one_pair(_record("V01-base"), A)
    assert pair.workload == W1
    assert pair.evidence_refs == ("ev:orders", f"ev:{P1_NAME}")
    assert pair.source == A.capture


# --- Phase 1 and the window (matrix §13) -------------------------------------------------------


@pytest.mark.parametrize("vector", WINDOW_VECTORS["windows"], ids=lambda v: v["id"])
def test_every_window_vector(vector):
    if not vector["valid"]:
        with pytest.raises(ValueError):
            ScopedDayWindowV1.parse(vector["first_day"], vector["last_day"])
        return
    window = ScopedDayWindowV1.parse(vector["first_day"], vector["last_day"])
    assert window.start == datetime.fromisoformat(vector["start"])
    assert window.end == datetime.fromisoformat(vector["end"])


@pytest.mark.parametrize("vector", WINDOW_VECTORS["membership"], ids=lambda v: v["id"])
def test_every_membership_vector(vector):
    [window_vector] = [w for w in WINDOW_VECTORS["windows"] if w["id"] == vector["window"]]
    window = ScopedDayWindowV1.parse(window_vector["first_day"], window_vector["last_day"])
    assert window.contains(datetime.fromisoformat(vector["instant"])) is vector["included"]


def _request_expectation(case_id, variant_id):
    [case] = [c for c in ORACLE["cases"] if c["id"] == case_id]
    [variant] = [v for v in case["variants"] if v["id"] == variant_id]
    return variant["expected"]["request"]


@pytest.mark.parametrize(
    ("case_id", "variant_id", "overrides"),
    [
        ("L24", "a", {"dimensions": frozenset({"region"})}),
        ("L24", "a", {"dimensions": frozenset({"tenant", "cluster"})}),
        ("L24", "a", {"dimensions": frozenset({"service.version"})}),
        ("L24", "b", {"relation_type": "SENDS"}),
        ("L24", "b", {"relation_type": "PUBLISHES_TO"}),
        ("L25", "a", {"first_day": f"{D}T08:00:00Z", "last_day": f"{D}T17:00:00Z"}),
    ],
)
def test_phase_one_terminates_the_request(case_id, variant_id, overrides):
    expected = _request_expectation(case_id, variant_id)
    result = evaluate_candidates(_request(**overrides), [_record("V01-base")], [A])
    assert result.candidates == ()
    assert result.refusal == RequestRefusal(
        LocalityDisposition(expected["disposition"]), tuple(expected["reasons"]), expected["phase"]
    )


@pytest.mark.parametrize(
    ("first_day", "last_day"),
    [("20260928", D), (D, "2026-9-28"), ("2026-02-29", "2026-02-29"), (D1, D), (f"{D}T08", "x")],
)
def test_a_malformed_window_is_a_validation_refusal(first_day, last_day):
    with pytest.raises(ValueError):
        preflight(_request(first_day=first_day, last_day=last_day))


def test_a_supported_request_yields_its_window():
    assert preflight(_request(dimensions=frozenset({"cluster", "namespace", "workload"}))) == (
        ScopedDayWindowV1.parse(D, D)
    )


def test_a_truncated_page_names_its_continuation():
    records = [_record("V01-base"), _record("V03-distinct-pod")]
    result = evaluate_candidates(_request(), records, [A], truncated=True)
    assert result.truncated
    assert result.next_after_id == max(r.id for r in records)
    assert [c.record.id for c in result.candidates] == sorted(r.id for r in records)


def test_the_window_end_is_the_last_representable_microsecond():
    window = ScopedDayWindowV1.parse("9999-12-31", "9999-12-31")
    assert window.end == datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)


def test_one_pod_resolved_to_two_incarnations_of_one_logical_workload_conflicts():
    """PR #365 review: D4 deduplicates only exactly identical Workload identities, and the
    captured UID is part of that identity (D14.1)."""
    first = replace(W1, uid="uid-first")
    second = replace(W1, uid="uid-second")
    assert first.workload_id == second.workload_id
    record = _record("V01-base", attributes=False)
    candidate = _s(
        [_source("a", _pod(P1, P1_NAME, first)), _source("b", _pod(P1, P1_NAME, second))],
        record=record,
    )
    assert [pair.disposition for pair in candidate.pairs] == [LocalityDisposition.APPLICABLE] * 2
    assert candidate.disposition is LocalityDisposition.CONFLICT
    assert list(candidate.reasons) == ["LOCALITY_POD_OWNER_CONFLICT"]
    assert candidate.workload is None
