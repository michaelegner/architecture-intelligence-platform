"""v0.6.0 I3.2b: the pure locality projection and the service's refusal order (I3 decision record
D4, D5, D7-D10, D16, D17).

The inputs are synthetic I2 reads built with the I2 unit fixtures, so each test states the I2
outcome it starts from. Expectations are written from the decision record, not read back from the
projection. Every answer is also validated against the `LocalityAnswer` model **and** the published
0.6 answer schema, which re-derive the D9/D10 rules independently of this code.
"""

import contextlib
import json
from dataclasses import replace

import jsonschema
import pytest

from app.architecture_intelligence import service as service_module
from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityCursor,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityData,
    WorkloadIdentity,
    decode_cursor,
    encode_cursor,
)
from app.architecture_intelligence.locality_projection import (
    internal_request,
    project_locality_answer,
    query_digest,
)
from app.architecture_intelligence.repository import SnapshotUnstable
from app.architecture_intelligence.schema_export import LOCALITY_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.scoped_applicability import ApplicabilityResult
from app.architecture_intelligence.scoped_evidence_repository import (
    ApplicabilityPage,
    DeclaredCallEvidence,
    LocalityInventoryRead,
    ProviderOwnerRows,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from tests.unit.test_local_assessment import (
    CAP_A,
    DECLARED,
    O1,
    O2,
    O3,
    SNAPSHOT,
    W1,
    W2,
    _declared,
    _read,
    _uid_workload,
    _v2,
)
from tests.unit.test_scoped_applicability import (
    CALLER,
    ENVIRONMENT,
    P1,
    P1_NAME,
    P2,
    D,
    _pod,
    _source,
)

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
ANSWER_SCHEMA = json.loads(LOCALITY_ANSWER_SCHEMA_PATH.read_text())
OTHER_SNAPSHOT = "aip:snapshot:v1:" + "b" * 64

PRICING, LEGACY = "service:pricing", "service:legacy-pricing"
EV_PRICING, EV_LEGACY = "evidence:declared:pricing-provides", "evidence:otel:legacy-provides"


def _query(**overrides) -> LocalityQueryRequest:
    return LocalityQueryRequest.model_validate(
        {
            "mode": "query",
            "subject_service_id": CALLER,
            "environment": ENVIRONMENT,
            "first_day": D,
            "last_day": D,
            **overrides,
        }
    )


def _identity(workload) -> WorkloadIdentity:
    return WorkloadIdentity(
        cluster_uid=workload.cluster_uid,
        namespace=workload.namespace,
        kind=workload.kind,
        uid=workload.uid,
    )


def _owners(*rows: tuple[str, str, str]) -> ProviderOwnerRows:
    """`(operation, provider, evidence id)` rows; an evidence id starting with `dangling` is not
    an accepted Evidence row."""
    return ProviderOwnerRows(
        provides=tuple(
            {
                "operation_id": operation,
                "provider_id": provider,
                "provider_name": provider.removeprefix("service:"),
                "evidence_ids": [evidence],
            }
            for operation, provider, evidence in rows
        ),
        evidence_rows={
            evidence: {"id": evidence, "evidence_type": "DECLARED"}
            for _o, _p, evidence in rows
            if not evidence.startswith("dangling")
        },
    )


STANDARD_OWNERS = _owners(
    (O1, PRICING, EV_PRICING), (O2, LEGACY, EV_LEGACY), (O3, PRICING, EV_PRICING)
)


def _answer(
    records,
    query=None,
    *,
    sources=(CAP_A,),
    owners=STANDARD_OWNERS,
    declared=None,
    truncated=False,
    considered=1,
) -> LocalityAnswer:
    query = query or _query()
    read, _ = _read(
        records,
        sources,
        declared=declared if declared is not None else _declared(O1=(DECLARED,)),
        request=internal_request(query),
        truncated=truncated,
    )
    answer = project_locality_answer(
        query, read, owners, considered_sources=considered, producer=PRODUCER
    )
    _assert_valid(answer)
    return answer


def _assert_valid(answer: LocalityAnswer) -> None:
    payload = json.loads(answer.model_dump_json())
    LocalityAnswer.model_validate(payload)
    errors = [
        e.message for e in jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(payload)
    ]
    assert errors == []


def _data(answer: LocalityAnswer) -> ServiceDependenciesByLocalityData:
    assert isinstance(answer.data, ServiceDependenciesByLocalityData)
    return answer.data


def _codes(answer: LocalityAnswer) -> list[str]:
    return [item.code.value for item in answer.limitations]


def _by_name(data: ServiceDependenciesByLocalityData) -> dict:
    return {locality.workload.name: locality for locality in data.localities}


# --- Positive localities and the D8 provider projection ----------------------------------------


def test_two_caller_workloads_of_one_service_are_two_localities():
    answer = _answer([_v2(P1, O1), _v2(P2, O2)])
    data = _data(answer)

    assert (answer.outcome, _codes(answer)) == (Outcome.ANSWERED, [])
    localities = _by_name(data)
    assert sorted(localities) == ["orders", "orders-canary"]
    w1, w2 = localities["orders"], localities["orders-canary"]
    assert [(a.object_operation_id, a.qualification.value) for a in w1.assessments] == [
        (O1, "CONFIRMED")
    ]
    assert [(a.object_operation_id, a.qualification.value) for a in w2.assessments] == [
        (O2, "OBSERVED_ONLY")
    ]
    assert [g.provider_service_id for g in w1.provider_groups] == [PRICING]
    assert [g.provider_service_id for g in w2.provider_groups] == [LEGACY]
    assert all(item.target_runtime_scope == "UNKNOWN" for item in data.localities)
    assert data.coverage == "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"
    assert data.inventory.completeness.value == "COMPLETE"
    assert data.inventory.next_cursor is None
    # Every evaluated candidate is listed, positive ones included (D10).
    assert len(data.candidates) == 2 and data.inventory.admitted_pair_count == 2


def test_one_provider_with_two_operations_is_one_group_without_a_pooled_label():
    data = _data(_answer([_v2(P1, O1), _v2(P1, O3)]))

    [locality] = data.localities
    [group] = locality.provider_groups
    assert group.provider_service_id == PRICING
    assert group.operation_ids == sorted([O1, O3])
    assert [q.value for q in group.member_qualifications] == ["CONFIRMED", "OBSERVED_ONLY"]
    assert {a.object_operation_id: a.qualification.value for a in locality.assessments} == {
        O1: "CONFIRMED",
        O3: "OBSERVED_ONLY",
    }


@pytest.mark.parametrize(
    ("owners", "reason"),
    [
        (_owners((O2, LEGACY, EV_LEGACY)), "PROVIDER_OWNER_MISSING"),
        (_owners((O1, PRICING, "dangling:1")), "PROVIDER_OWNER_MISSING"),
        (_owners((O1, PRICING, EV_PRICING), (O1, LEGACY, EV_LEGACY)), "PROVIDER_OWNER_AMBIGUOUS"),
    ],
    ids=["no-provides", "dangling-evidence", "two-evidenced-providers"],
)
def test_an_unresolved_owner_keeps_the_operation_and_mints_no_provider(owners, reason):
    answer = _answer([_v2(P1, O1)], owners=owners)
    [locality] = _data(answer).localities

    assert locality.provider_groups == []
    assert [
        (item.operation_id, item.reason.value) for item in locality.unresolved_owner_operations
    ] == [(O1, reason)]
    assert (answer.outcome, _codes(answer)) == (Outcome.PARTIAL, ["PROVIDER_OWNER_UNRESOLVED"])


def test_no_v2_is_not_answered_with_the_empty_inventory():
    answer = _answer([])
    data = _data(answer)

    assert (answer.outcome, _codes(answer)) == (Outcome.NOT_ANSWERED, ["INSUFFICIENT_EVIDENCE"])
    assert data.candidates == [] and data.localities == []
    assert data.inventory.completeness.value == "COMPLETE"


def test_a_non_positive_candidate_stays_in_the_inventory_unchanged():
    no_owner = replace(CAP_A, pods=(_pod(P1, P1_NAME),))
    answer = _answer([_v2(P1, O1)], sources=(no_owner,))
    [candidate] = _data(answer).candidates

    assert candidate.disposition.value == "UNRESOLVED"
    assert candidate.reasons == ["LOCALITY_POD_OWNER_UNRESOLVED"]
    assert [pair.disposition.value for pair in candidate.pairs] == ["UNRESOLVED"]
    assert answer.outcome is Outcome.NOT_ANSWERED


def test_a_workload_without_a_captured_uid_is_listed_with_i2_s_limitation():
    uidless = replace(W1, uid=None)
    source = _source("cap-a", _pod(P1, P1_NAME, uidless))
    [candidate] = _data(_answer([_v2(P1, O1)], sources=(source,))).candidates

    assert candidate.disposition.value == "APPLICABLE"
    assert [code.value for code in candidate.limitations] == ["WORKLOAD_UID_UNAVAILABLE"]


# --- Filters, selection and comparison (D10, D16.4) ---------------------------------------------


def test_the_provider_filter_narrows_localities_but_never_the_inventory():
    answer = _answer([_v2(P1, O1), _v2(P2, O2)], _query(provider_service_id=PRICING))
    data = _data(answer)

    assert [item.workload.name for item in data.localities] == ["orders"]
    assert len(data.candidates) == 2
    assert answer.outcome is Outcome.ANSWERED


def test_the_provider_filter_keeps_unresolved_owner_operations():
    owners = _owners((O2, LEGACY, EV_LEGACY))  # O1 has no owner
    answer = _answer([_v2(P1, O1), _v2(P2, O2)], _query(provider_service_id=PRICING), owners=owners)

    [locality] = _data(answer).localities
    assert locality.workload.name == "orders"
    assert [item.operation_id for item in locality.unresolved_owner_operations] == [O1]


def test_caller_localities_filter_the_localities_and_report_each_selection():
    invented = WorkloadIdentity(
        cluster_uid=W1.cluster_uid, namespace="shop", kind="Deployment", uid="no-such"
    )
    selected = sorted(
        [_identity(W2), invented], key=lambda i: (i.cluster_uid, i.namespace, i.kind, i.uid)
    )
    answer = _answer(
        [_v2(P1, O1), _v2(P2, O2)], _query(caller_localities=[i.model_dump() for i in selected])
    )
    data = _data(answer)

    assert [item.workload.name for item in data.localities] == ["orders-canary"]
    assert len(data.candidates) == 2
    assert data.selection is not None
    assert {item.workload.uid: item.evaluation.value for item in data.selection} == {
        W2.uid: "POSITIVE",
        "no-such": "UNKNOWN",
    }
    assert (answer.outcome, _codes(answer)) == (Outcome.PARTIAL, ["SELECTION_NOT_ESTABLISHED"])


def test_a_comparison_lists_positive_memberships_per_side():
    query = _query(compare=[_identity(W1).model_dump(), _identity(W2).model_dump()])
    answer = _answer([_v2(P1, O1), _v2(P2, O2), _v2(P2, O1)], query)
    comparison = _data(answer).comparison

    assert comparison is not None
    assert comparison.completeness.value == "COMPLETE"
    assert [(m.provider_service_id, m.operation_id) for m in comparison.in_both] == [(PRICING, O1)]
    assert [(m.provider_service_id, m.operation_id) for m in comparison.only_in_second] == [
        (LEGACY, O2)
    ]
    assert comparison.only_in_first == []
    # O1 is declared, so it is CONFIRMED in both Workloads.
    assert comparison.qualification_differs == []
    assert answer.outcome is Outcome.ANSWERED


def test_an_invented_compare_identity_is_unknown_and_not_established():
    invented = WorkloadIdentity(
        cluster_uid=W1.cluster_uid, namespace="shop", kind="Deployment", uid="no-such"
    )
    answer = _answer(
        [_v2(P1, O1)], _query(compare=[_identity(W1).model_dump(), invented.model_dump()])
    )
    comparison = _data(answer).comparison

    assert comparison is not None
    assert [scope.evaluation.value for scope in comparison.scopes] == ["POSITIVE", "UNKNOWN"]
    assert comparison.completeness.value == "NOT_ESTABLISHED"
    assert [(m.provider_service_id, m.operation_id) for m in comparison.only_in_first] == [
        (PRICING, O1)
    ]
    assert (answer.outcome, _codes(answer)) == (
        Outcome.PARTIAL,
        ["COMPARISON_INCOMPLETE", "SELECTION_NOT_ESTABLISHED"],
    )


# --- Bounds, caps and continuation (D4, D5, D7, D16.11, D17) ------------------------------------


def _many_workloads(count: int):
    """`count` Pods, each owned by its own Deployment, and one v2 record per Pod."""
    pods, records = [], []
    for n in range(count):
        name, workload = f"orders-gen-{n:04d}", _uid_workload(f"orders-w{n:02d}", f"wl-uid-{n:04d}")
        uid = f"pod-uid-{n:04d}"
        pods.append(_pod(uid, name, workload))
        records.append(
            _v2(
                uid, O1, pod_attributes={"k8s_pod_name": name, "k8s_deployment_name": workload.name}
            )
        )
    return _source("cap-a", *pods), records


def test_the_workload_cap_cuts_the_page_at_a_complete_candidate():
    source, records = _many_workloads(60)
    answer = _answer(records, sources=(source,))
    data = _data(answer)

    assert len(data.localities) == 50 and len(data.candidates) == 50
    inventory = data.inventory
    assert (inventory.i2_truncated, [cap.value for cap in inventory.cap_reached]) == (
        False,
        ["WORKLOADS"],
    )
    assert inventory.completeness.value == "PARTIAL"
    assert all(not item.lineage_complete for item in data.localities)
    assert inventory.next_cursor is not None
    cursor = decode_cursor(inventory.next_cursor)
    assert (
        cursor.after_id == data.candidates[-1].v2_evidence_id == sorted(r.id for r in records)[49]
    )
    assert (cursor.snapshot_id, cursor.query_digest) == (SNAPSHOT, query_digest(_query()))
    assert (answer.outcome, _codes(answer)) == (Outcome.PARTIAL, ["INVENTORY_INCOMPLETE"])


def test_the_membership_cap_counts_operations_of_one_workload():
    records = [_v2(P1, f"operation:service:pricing:GET:/p{n:03d}") for n in range(201)]
    owners = _owners(*((r.object_id, PRICING, EV_PRICING) for r in records))
    data = _data(_answer(records, owners=owners, declared=DeclaredCallEvidence({}, {})))

    assert [cap.value for cap in data.inventory.cap_reached] == ["MEMBERSHIPS"]
    assert len(data.candidates) == 200
    assert sum(len(item.assessments) for item in data.localities) == 200


def test_caps_count_only_the_presented_localities():
    """D17.2: with a provider filter that hides every Workload, 60 Workloads fit on one page."""
    source, records = _many_workloads(60)
    data = _data(_answer(records, _query(provider_service_id=LEGACY), sources=(source,)))

    assert data.inventory.cap_reached == [] and len(data.candidates) == 60
    assert data.localities == []


def test_assess_is_monotone_in_the_candidate_prefix():
    """D17.2's premise: a longer prefix never presents fewer Workloads or memberships."""
    source, records = _many_workloads(12)
    records += [
        _v2(
            "pod-uid-0003",
            O3,
            pod_attributes={"k8s_pod_name": "orders-gen-0003", "k8s_deployment_name": "orders-w03"},
        )
    ]
    query = _query()
    read, _ = _read(records, (source,), request=internal_request(query))
    counts = []
    for n in range(len(read.result.candidates) + 1):
        prefix = replace(read, result=ApplicabilityResult(read.result.candidates[:n], False, None))
        data = _data(
            project_locality_answer(
                query, prefix, STANDARD_OWNERS, considered_sources=1, producer=PRODUCER
            )
        )
        counts.append(
            (len(data.localities), sum(len(item.assessments) for item in data.localities))
        )
    assert counts == sorted(counts)
    assert counts[-1] == (12, 13)


def test_an_i2_truncated_page_continues_after_i2_s_last_candidate():
    answer = _answer([_v2(P1, O1), _v2(P2, O2)], truncated=True)
    data = _data(answer)

    assert data.inventory.i2_truncated and data.inventory.cap_reached == []
    assert data.inventory.next_cursor is not None
    assert decode_cursor(data.inventory.next_cursor).after_id == data.candidates[-1].v2_evidence_id
    assert all(
        not a.observation.lineage_complete for item in data.localities for a in item.assessments
    )
    assert (answer.outcome, _codes(answer)) == (Outcome.PARTIAL, ["INVENTORY_INCOMPLETE"])


def _cursor(query: LocalityQueryRequest, *, snapshot=SNAPSHOT, after_id=None) -> str:
    return encode_cursor(
        LocalityCursor(
            v=1,
            after_id=after_id or _v2(P1, O1).id,
            query_digest=query_digest(query),
            snapshot_id=snapshot,
            schema_version="0.6",
        )
    )


def test_a_final_continuation_page_is_partial_without_a_cursor():
    """D16.11/D17.3: I2 did not truncate, but the page continues a cursor walk."""
    query = _query()
    answer = _answer([_v2(P2, O2)], _query(cursor=_cursor(query)))
    data = _data(answer)

    assert data.inventory.continuation and data.inventory.next_cursor is None
    assert data.inventory.completeness.value == "PARTIAL"
    assert all(
        not a.observation.lineage_complete for item in data.localities for a in item.assessments
    )
    assert (answer.outcome, _codes(answer)) == (Outcome.PARTIAL, ["INVENTORY_INCOMPLETE"])


def test_the_query_digest_ignores_only_cursor_and_snapshot():
    base = _query()
    assert query_digest(base) == query_digest(_query(snapshot_id=SNAPSHOT, cursor=_cursor(base)))
    assert query_digest(base) != query_digest(_query(object_operation_id=O1))
    assert query_digest(base) != query_digest(_query(provider_service_id=PRICING))


def test_explicit_dimensions_equal_to_the_default_are_the_same_query():
    assert query_digest(_query()) == query_digest(
        _query(dimensions=["cluster", "namespace", "workload"])
    )


# --- The service: refusal order and the fence (D6, D9, D17.1) ----------------------------------


class _FakeReads:
    def __init__(self, *, snapshot=SNAPSHOT, considered=1, refuse=False, unstable=False):
        self.calls = []
        self._snapshot, self._considered = snapshot, considered
        self._refuse, self._unstable = refuse, unstable

    def __call__(
        self,
        session,
        request,
        *,
        coverage_qualification_enabled,
        service_workload_mapping_document,
        after_id,
        read_candidates,
    ):
        assert service_workload_mapping_document is None  # the service under test has none
        self.calls.append({"after_id": after_id, "read_candidates": read_candidates})
        if self._unstable:
            raise SnapshotUnstable("never settles")
        model_revision = "sha256:" + self._snapshot.rsplit(":", 1)[1]
        page = None
        if read_candidates:
            read, _ = _read([_v2(P1, O1)], request=request, snapshot=self._snapshot)
            page = ApplicabilityPage(
                captures=(),
                considered_source_count=self._considered,
                result=None if self._refuse else read.result,
                declared=_declared(O1=(DECLARED,)),
            )
        return LocalityInventoryRead(self._snapshot, model_revision, page, STANDARD_OWNERS)


@pytest.fixture
def run(monkeypatch):
    def _run(query, reads):
        monkeypatch.setattr(service_module, "read_locality_inventory", reads)
        monkeypatch.setattr(
            service_module, "open_session", lambda *a, **k: contextlib.nullcontext()
        )
        service = ArchitectureIntelligenceService(None, database="neo4j", producer=PRODUCER)  # pyright: ignore[reportArgumentType]
        answer = service.get_service_dependencies_by_locality(query)
        _assert_valid(answer)
        return answer

    return _run


def test_the_service_answers_from_one_fenced_read(run):
    reads = _FakeReads()
    answer = run(_query(), reads)

    assert answer.outcome is Outcome.ANSWERED
    assert reads.calls == [{"after_id": None, "read_candidates": True}]
    assert answer.snapshot is not None and answer.snapshot.snapshot_id == SNAPSHOT


def test_unsupported_wins_over_a_cursor_mismatch_and_reads_no_candidates(run):
    other = _query(object_operation_id=O1)
    reads = _FakeReads(snapshot=OTHER_SNAPSHOT)
    answer = run(_query(relation_type="SENDS", cursor=_cursor(other)), reads)

    assert _codes(answer) == ["UNSUPPORTED_REQUEST"]
    assert answer.limitations[0].reasons == ["LOCALITY_UNSUPPORTED_RELATION"]
    assert answer.snapshot is not None and answer.data is None
    assert [call["read_candidates"] for call in reads.calls] == [False]


def test_a_cursor_mismatch_wins_over_a_stale_snapshot(run):
    other = _query(object_operation_id=O1)
    reads = _FakeReads(snapshot=OTHER_SNAPSHOT)
    answer = run(_query(cursor=_cursor(other)), reads)

    assert _codes(answer) == ["CURSOR_QUERY_MISMATCH"]
    assert reads.calls[0]["read_candidates"] is False


def test_a_stale_snapshot_wins_over_the_source_bound(run):
    reads = _FakeReads(snapshot=OTHER_SNAPSHOT, considered=2001, refuse=True)
    answer = run(_query(snapshot_id=SNAPSHOT), reads)

    assert _codes(answer) == ["SNAPSHOT_NOT_AVAILABLE"]
    assert answer.snapshot is not None and answer.snapshot.snapshot_id == OTHER_SNAPSHOT


def test_a_cursor_from_another_snapshot_is_refused(run):
    query = _query()
    answer = run(_query(cursor=_cursor(query, snapshot=OTHER_SNAPSHOT)), _FakeReads())

    assert _codes(answer) == ["SNAPSHOT_NOT_AVAILABLE"]


def test_a_cursor_continues_after_its_last_presented_candidate(run):
    query = _query()
    reads = _FakeReads()
    run(_query(cursor=_cursor(query, after_id=_v2(P2, O2).id)), reads)

    assert reads.calls == [{"after_id": _v2(P2, O2).id, "read_candidates": True}]


def test_the_capture_source_bound_fails_closed_and_states_s(run):
    answer = run(_query(), _FakeReads(considered=2001, refuse=True))

    assert (answer.outcome, _codes(answer)) == (Outcome.NOT_ANSWERED, ["RESULT_LIMIT_EXCEEDED"])
    assert answer.data is None
    assert "2001" in answer.limitations[0].message and "2000" in answer.limitations[0].message


def test_an_unstable_snapshot_is_refused_without_a_snapshot(run):
    answer = run(_query(), _FakeReads(unstable=True))

    assert (_codes(answer), answer.snapshot) == (["SNAPSHOT_NOT_AVAILABLE"], None)


def test_the_current_snapshot_assertion_is_answered(run):
    answer = run(_query(snapshot_id=SNAPSHOT), _FakeReads())

    assert answer.outcome is Outcome.ANSWERED
