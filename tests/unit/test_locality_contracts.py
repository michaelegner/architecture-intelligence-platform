"""v0.6.0 I3.1b: the draft 0.6 locality contract (I3 decision record D1-D16).

Every invariant the JSON Schema can express must be rejected by **both** Pydantic and the committed
schema; the rest are Pydantic-only and are tested as such. The valid answer is the rehearsal's C1
shape (two caller Workloads of `service:orders`), hand-written, not produced by any service code.
"""

import copy
import json
from collections.abc import Callable
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence import contracts
from app.architecture_intelligence.deployment_projection import WORKLOAD_KIND_BY_RAW
from app.architecture_intelligence.local_assessment import (
    ASSERTION_PREFIX,
    ASSESSMENT_PREFIX,
    LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE,
    RULES,
    TARGET_RUNTIME_SCOPE_UNKNOWN,
    AssessmentLimitation,
)
from app.architecture_intelligence.locality_contracts import (
    DEFAULT_DIMENSIONS,
    MAX_CANDIDATE_PAGE,
    UNSUPPORTED_REQUEST_REASONS,
    AdmissionBasis,
    CandidateLimitationCode,
    CapturedWorkloadKind,
    LocalDisposition,
    LocalityAnswer,
    LocalityCursor,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityRequest,
    candidate_page_size,
    decode_cursor,
    encode_cursor,
)
from app.architecture_intelligence.locality_contracts import (
    LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE as PUBLIC_COVERAGE,
)
from app.architecture_intelligence.locality_contracts import (
    TARGET_RUNTIME_SCOPE_UNKNOWN as PUBLIC_TARGET_SCOPE,
)
from app.architecture_intelligence.schema_export import (
    LOCALITY_ANSWER_SCHEMA_PATH,
    LOCALITY_REQUEST_SCHEMA_PATH,
)
from app.architecture_intelligence.scoped_applicability import (
    REASON_UNSUPPORTED_DIMENSION,
    REASON_UNSUPPORTED_RELATION,
    REASON_UNSUPPORTED_TEMPORAL_RESOLUTION,
    SUPPORTED_DIMENSIONS,
    ScopedLimitation,
)
from app.architecture_intelligence.scoped_applicability import (
    AdmissionBasis as InternalAdmissionBasis,
)
from app.architecture_intelligence.scoped_evidence_repository import DEFAULT_PAGE_SIZE
from app.canonical.ids import SCOPED_CALL_V2_ID_PREFIX
from app.telemetry.scoped_attribution import LocalityDisposition

ANSWER_SCHEMA = json.loads(LOCALITY_ANSWER_SCHEMA_PATH.read_text())
REQUEST_SCHEMA = json.loads(LOCALITY_REQUEST_SCHEMA_PATH.read_text())

DIGEST = "3a0b04e1d88feaae5ebb2277f8fe50fba74279cc3af12906edc37a31e55c59f9"
SNAPSHOT_ID = f"aip:snapshot:v1:{DIGEST}"
OTHER_SNAPSHOT_ID = f"aip:snapshot:v1:{'0' * 64}"
V2_W1 = (
    "evidence:otel:calls-scoped:v2:3d17904494047d4ce70edeb55f7083481071ed5bd26c9a3f19dbb4f332cc04e0"
)
V2_W2 = (
    "evidence:otel:calls-scoped:v2:df6b26b5e885eb7a425d1799ed36a2afdbc6c1c269d67a651ee2876d89e28807"
)
V2_LOW = f"evidence:otel:calls-scoped:v2:{'0' * 64}"
CLUSTER = "3c9b3e0f-1239-404a-8a45-c1195a7918f5"
O1 = "operation:service:pricing:GET:/prices"
O2 = "operation:service:legacy-pricing:GET:/prices"
SOURCE = {"source_instance_id": "kubernetes:rehearsal", "revision": "rehearsal-c1"}
RULE_REFS = [{"id": rule_id, "version": version} for rule_id, version in RULES]


def _identity(uid: str) -> dict[str, str]:
    return {"cluster_uid": CLUSTER, "namespace": "aip-locality", "kind": "Deployment", "uid": uid}


W1 = _identity("1cda6fde-w1")
W2 = _identity("d005b4f6-w2")


def _workload_ref(identity: dict[str, str], name: str) -> dict[str, Any]:
    return {"workload_id": f"workload:{name}", "name": name, **identity}


def _pair(identity: dict[str, str], name: str) -> dict[str, Any]:
    return {
        "source": dict(SOURCE),
        "admission": ["CLUSTER_NAMESPACE", "POD_UID"],
        "phase": 4,
        "disposition": "APPLICABLE",
        "reasons": [],
        "limitations": [],
        "workload": _workload_ref(identity, name),
        "evidence_refs": [f"evidence:k8s:owner:{name}", f"evidence:k8s:pod:{name}"],
    }


def _candidate(v2_id: str, identity: dict[str, str], name: str) -> dict[str, Any]:
    return {
        "v2_evidence_id": v2_id,
        "disposition": "APPLICABLE",
        "reasons": [],
        "limitations": [],
        "workload": _workload_ref(identity, name),
        "pairs": [_pair(identity, name)],
    }


def _assessment(
    n: int, operation: str, qualification: str, v2_id: str, name: str, declared: list[str]
) -> dict[str, Any]:
    return {
        "assertion_id": f"{ASSERTION_PREFIX}{str(n) * 64}",
        "assessment_id": f"{ASSESSMENT_PREFIX}{str(n + 4) * 64}",
        "object_operation_id": operation,
        "applicability": "APPLICABLE",
        "qualification": qualification,
        "observation": {
            "evidence_ids": [v2_id],
            "first_seen": "2026-09-30T14:30:00Z",
            "last_seen": "2026-09-30T14:35:00Z",
            "lineage_complete": True,
        },
        "declared_evidence_ids": declared,
        "selected_captures": [
            {
                **SOURCE,
                "evidence_mode": "CAPTURED_RESOURCE",
                "captured_at": "2026-09-30T14:38:11Z",
            }
        ],
        "capture_evidence_refs": [f"evidence:k8s:owner:{name}", f"evidence:k8s:pod:{name}"],
        "source_limitations": [],
        "rules": RULE_REFS,
    }


def _locality(
    identity: dict[str, str], name: str, provider: str, assessment: dict[str, Any]
) -> dict[str, Any]:
    union = sorted(
        {
            *assessment["observation"]["evidence_ids"],
            *assessment["declared_evidence_ids"],
            *assessment["capture_evidence_refs"],
        }
    )
    return {
        "workload": _workload_ref(identity, name),
        "assessments": [assessment],
        "provider_groups": [
            {
                "provider_service_id": provider,
                "operation_ids": [assessment["object_operation_id"]],
                "member_qualifications": [assessment["qualification"]],
                "evidence_refs": union,
            }
        ],
        "unresolved_owner_operations": [],
        "target_runtime_scope": "UNKNOWN",
        "lineage_complete": True,
    }


def _side(assessment: dict[str, Any]) -> dict[str, str]:
    return {
        "qualification": assessment["qualification"],
        "assertion_id": assessment["assertion_id"],
        "assessment_id": assessment["assessment_id"],
    }


def query_answer() -> dict[str, Any]:
    """C1: W1 → O1 CONFIRMED, W2 → O2 OBSERVED_ONLY, compared; complete inventory."""
    a1 = _assessment(1, O1, "CONFIRMED", V2_W1, "orders", ["evidence:openapi:pricing"])
    a2 = _assessment(2, O2, "OBSERVED_ONLY", V2_W2, "orders-canary", [])
    return {
        "schema_version": "0.6",
        "producer": {
            "name": "architecture-intelligence-platform",
            "version": "0.6.0.dev0",
            "build_revision": "c0672e3",
        },
        "tool": "get_service_dependencies_by_locality",
        "mode": "query",
        "outcome": "ANSWERED",
        "snapshot": {"snapshot_id": SNAPSHOT_ID, "model_revision": f"sha256:{DIGEST}"},
        "data": {
            "request_context": {
                "subject_service_id": "service:orders",
                "environment": "locality-capture",
                "first_day": "2026-09-30",
                "last_day": "2026-09-30",
                "relation_type": "CALLS",
                "dimensions": ["cluster", "namespace", "workload"],
                "object_operation_id": None,
                "provider_service_id": None,
                "source_selector": None,
                "caller_localities": None,
                "compare": [W1, W2],
                "selection_mode": "IMPLICIT_COVERING_SOURCES",
            },
            "coverage": "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE",
            "inventory": {
                "considered_capture_source_count": 1,
                "evaluated_v2_candidate_count": 2,
                "admitted_pair_count": 2,
                "evaluated_sources": [
                    {
                        **SOURCE,
                        "cluster_uid": CLUSTER,
                        "namespaces": ["aip-locality"],
                        "evidence_mode": "CAPTURED_RESOURCE",
                        "captured_at": "2026-09-30T14:38:11Z",
                    }
                ],
                "bounds": {
                    "pair_bound": 2000,
                    "capture_source_bound": 2000,
                    "candidate_page_size": 500,
                    "max_localities": 50,
                    "max_memberships": 200,
                },
                "i2_truncated": False,
                "continuation": False,
                "cap_reached": [],
                "next_cursor": None,
                "completeness": "COMPLETE",
            },
            "candidates": [
                _candidate(V2_W1, W1, "orders"),
                _candidate(V2_W2, W2, "orders-canary"),
            ],
            "localities": [
                _locality(W1, "orders", "service:pricing", a1),
                _locality(W2, "orders-canary", "service:legacy-pricing", a2),
            ],
            "selection": None,
            "comparison": {
                "scopes": [
                    {"workload": W1, "evaluation": "POSITIVE"},
                    {"workload": W2, "evaluation": "POSITIVE"},
                ],
                "in_both": [],
                "only_in_first": [
                    {
                        "provider_service_id": "service:pricing",
                        "operation_id": O1,
                        "side": _side(a1),
                    }
                ],
                "only_in_second": [
                    {
                        "provider_service_id": "service:legacy-pricing",
                        "operation_id": O2,
                        "side": _side(a2),
                    }
                ],
                "qualification_differs": [],
                "completeness": "COMPLETE",
            },
        },
        "limitations": [],
    }


def evidence_answer() -> dict[str, Any]:
    answer = query_answer()
    answer["mode"] = "evidence"
    answer["data"] = {
        "subject_service_id": "service:orders",
        "object_operation_id": None,
        "entries": [
            {
                "ref": "evidence:k8s:pod:orders",
                "status": "RESOLVED",
                "ref_kind": "POD_CAPTURE",
                "scoped_record": None,
                "capture_record": {
                    "id": "evidence:k8s:pod:orders",
                    "evidence_type": "DECLARED",
                    "source_type": "KUBERNETES",
                    "source_locator": None,
                    "source_revision": "rehearsal-c1",
                    "observation": None,
                    "supports": [],
                },
            },
            {
                "ref": V2_W1,
                "status": "RESOLVED",
                "ref_kind": "SCOPED_V2",
                "scoped_record": {
                    "id": V2_W1,
                    "subject_id": "service:orders",
                    "object_id": O1,
                    "environment": "locality-capture",
                    "bucket_utc_day": "2026-09-30",
                    "caller_cluster_uid": CLUSTER,
                    "caller_pod_uid": "1cda6fde-9aa4-409d-baff-8b0604b0f63b",
                    "first_seen": "2026-09-30T14:30:00Z",
                    "last_seen": "2026-09-30T14:35:00Z",
                    "observation_count": 3,
                    "correlation_mode": "CLIENT_SERVER",
                    "sample_trace_ids": ["0af7651916cd43dd8448eb211c80319c"],
                    "key_rule_id": "otel-calls-scoped-evidence-v2-key",
                    "key_rule_version": 1,
                    "normalization_rule_id": "otel-client-caller-attribution",
                    "normalization_rule_version": 1,
                },
                "capture_record": None,
            },
        ],
    }
    return answer


def refusal_answer() -> dict[str, Any]:
    answer = query_answer()
    answer.update(
        outcome="NOT_ANSWERED",
        data=None,
        limitations=[
            {
                "code": "UNSUPPORTED_REQUEST",
                "message": "region is not a supported locality dimension",
                "reasons": ["LOCALITY_UNSUPPORTED_DIMENSION"],
            }
        ],
    )
    return answer


def query_request() -> dict[str, Any]:
    return {
        "mode": "query",
        "subject_service_id": "service:orders",
        "environment": "locality-capture",
        "first_day": "2026-09-30",
        "last_day": "2026-09-30",
        "caller_localities": [W1, W2],
        "compare": [W2, W1],
    }


def evidence_request() -> dict[str, Any]:
    return {
        "mode": "evidence",
        "subject_service_id": "service:orders",
        "snapshot_id": SNAPSHOT_ID,
        "refs": [V2_W1],
    }


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in validator.iter_errors(instance)]


def _assert_answer_valid(answer: dict[str, Any]) -> None:
    LocalityAnswer.model_validate(answer)
    assert _schema_errors(answer, ANSWER_SCHEMA) == []


def _assert_answer_rejected_by_pydantic(answer: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LocalityAnswer.model_validate(answer)


def _mutated(base: Callable[[], dict[str, Any]], mutate: Callable[[dict], None]) -> dict:
    answer = copy.deepcopy(base())
    mutate(answer)
    return answer


# --- Valid shapes -------------------------------------------------------------------------------


@pytest.mark.parametrize("build", [query_answer, evidence_answer, refusal_answer])
def test_valid_answers_pass_pydantic_and_the_committed_schema(build):
    _assert_answer_valid(build())


@pytest.mark.parametrize("build", [query_request, evidence_request])
def test_valid_requests_pass_pydantic_and_the_committed_schema(build):
    ServiceDependenciesByLocalityRequest.model_validate(build())
    assert _schema_errors(build(), REQUEST_SCHEMA) == []


def test_a_serialized_answer_round_trips_and_still_validates_against_the_schema():
    answer = LocalityAnswer.model_validate(query_answer())
    payload = answer.model_dump(mode="json")
    assert LocalityAnswer.model_validate(payload) == answer
    assert _schema_errors(payload, ANSWER_SCHEMA) == []


def test_request_defaults_are_the_supported_relation_and_dimensions():
    request = ServiceDependenciesByLocalityRequest.model_validate(
        {k: v for k, v in query_request().items() if k not in ("caller_localities", "compare")}
    ).root
    assert isinstance(request, LocalityQueryRequest)
    assert request.relation_type == "CALLS"
    assert request.dimensions == list(DEFAULT_DIMENSIONS)


@pytest.mark.parametrize(
    "field, value",
    [
        ("relation_type", "PUBLISHES_TO"),
        ("dimensions", ["cluster", "region"]),
        ("first_day", "2026-09-30T00:00:00Z"),
    ],
)
def test_well_formed_unsupported_values_are_accepted_for_a_service_refusal(field, value):
    """D3/D9: these reach I2's phase-1 UNSUPPORTED refusal instead of a validation error."""
    request = {**query_request(), field: value}
    if field == "first_day":
        request["last_day"] = "2026-09-30T23:59:59Z"
    ServiceDependenciesByLocalityRequest.model_validate(request)
    assert _schema_errors(request, REQUEST_SCHEMA) == []


# --- Rejected by both Pydantic and the schema ---------------------------------------------------


def _data(answer: dict) -> dict:
    return answer["data"]


BOTH_REJECT_ANSWER: dict[str, tuple[Callable[[], dict], Callable[[dict], None]]] = {
    "extra envelope key": (query_answer, lambda a: a.update(claims=[])),
    "0.5 schema version": (query_answer, lambda a: a.update(schema_version="0.5")),
    "a v0.5 tool name": (query_answer, lambda a: a.update(tool="get_service_dependencies")),
    "ANSWERED with a limitation": (
        query_answer,
        lambda a: a["limitations"].append(
            {"code": "INVENTORY_INCOMPLETE", "message": "x", "reasons": []}
        ),
    ),
    "PARTIAL without a limitation": (query_answer, lambda a: a.update(outcome="PARTIAL")),
    "null data on ANSWERED": (query_answer, lambda a: a.update(data=None)),
    "refusal with two limitations": (
        refusal_answer,
        lambda a: a["limitations"].insert(
            0, {"code": "SNAPSHOT_NOT_AVAILABLE", "message": "x", "reasons": []}
        ),
    ),
    "refusal with a non-refusal code": (
        refusal_answer,
        lambda a: a.update(
            limitations=[{"code": "INSUFFICIENT_EVIDENCE", "message": "x", "reasons": []}]
        ),
    ),
    "evaluated data with a refusal code": (
        query_answer,
        lambda a: a.update(
            outcome="PARTIAL",
            limitations=[{"code": "RESULT_LIMIT_EXCEEDED", "message": "x", "reasons": []}],
        ),
    ),
    "evaluated NOT_ANSWERED without INSUFFICIENT_EVIDENCE": (
        query_answer,
        lambda a: a.update(
            outcome="NOT_ANSWERED",
            limitations=[{"code": "PROVIDER_OWNER_UNRESOLVED", "message": "x", "reasons": []}],
        ),
    ),
    "null snapshot without SNAPSHOT_NOT_AVAILABLE": (
        refusal_answer,
        lambda a: a.update(snapshot=None),
    ),
    "UNSUPPORTED_REQUEST without reasons": (
        refusal_answer,
        lambda a: a["limitations"][0].update(reasons=[]),
    ),
    "UNSUPPORTED_REQUEST with a non-unsupported reason": (
        refusal_answer,
        lambda a: a["limitations"][0].update(reasons=["LOCALITY_CAPTURE_MISSING_POD"]),
    ),
    "query mode with evidence data": (evidence_answer, lambda a: a.update(mode="query")),
    "evidence mode with query data": (query_answer, lambda a: a.update(mode="evidence")),
    "another coverage value": (query_answer, lambda a: _data(a).update(coverage="SUFFICIENT")),
    "a known target runtime scope": (
        query_answer,
        lambda a: _data(a)["localities"][0].update(target_runtime_scope="SAME_NAMESPACE"),
    ),
    "a local NOT_OBSERVED_IN_WINDOW": (
        query_answer,
        lambda a: _data(a)["localities"][0]["assessments"][0].update(
            qualification="NOT_OBSERVED_IN_WINDOW"
        ),
    ),
    "an APPLICABLE pair without a Workload": (
        query_answer,
        lambda a: _data(a)["candidates"][0]["pairs"][0].update(workload=None),
    ),
    "an INAPPLICABLE pair with a Workload": (
        query_answer,
        lambda a: _data(a)["candidates"][0]["pairs"][0].update(
            disposition="INAPPLICABLE", reasons=["LOCALITY_OBSERVATION_TEMPORAL_MISMATCH"], phase=3
        ),
    ),
    "a phase-2 pair that is not UNSUPPORTED": (
        query_answer,
        lambda a: _data(a)["candidates"][0]["pairs"][0].update(
            phase=2, disposition="INAPPLICABLE", workload=None
        ),
    ),
    "a duplicated candidate": (
        query_answer,
        lambda a: _data(a)["candidates"].append(copy.deepcopy(_data(a)["candidates"][0])),
    ),
    "a selected Workload without a UID": (
        query_answer,
        lambda a: _data(a)["request_context"]["compare"][0].pop("uid"),
    ),
    "a different pair bound": (
        query_answer,
        lambda a: _data(a)["inventory"]["bounds"].update(pair_bound=3000),
    ),
    "a comparison without compare": (
        query_answer,
        lambda a: _data(a)["request_context"].update(compare=None),
    ),
    "compare without a comparison": (query_answer, lambda a: _data(a).update(comparison=None)),
    "a selection without caller_localities": (
        query_answer,
        lambda a: _data(a).update(selection=[]),
    ),
    "a NOT_FOUND entry with a record": (
        evidence_answer,
        lambda a: _data(a)["entries"][0].update(status="NOT_FOUND"),
    ),
    "a capture entry with a v2-shaped ref": (
        evidence_answer,
        lambda a: (
            _data(a)["entries"][0].update(ref=V2_LOW)
            or _data(a)["entries"][0]["capture_record"].update(id=V2_LOW)
        ),
    ),
    "a capture entry with non-Kubernetes evidence": (
        evidence_answer,
        lambda a: _data(a)["entries"][0]["capture_record"].update(source_type="OPENAPI"),
    ),
    "a SCOPED_V2 entry without a scoped record": (
        evidence_answer,
        lambda a: _data(a)["entries"][1].update(scoped_record=None),
    ),
    "a RESOLVED entry without a kind": (
        evidence_answer,
        lambda a: _data(a)["entries"][1].update(ref_kind=None),
    ),
    "a raw span field on a v2 record": (
        evidence_answer,
        lambda a: _data(a)["entries"][1]["scoped_record"].update(span_id="00f067aa0ba902b7"),
    ),
    "more than five sample trace ids": (
        evidence_answer,
        lambda a: _data(a)["entries"][1]["scoped_record"].update(
            sample_trace_ids=[f"{n:032x}" for n in range(6)]
        ),
    ),
}


# The Pydantic message each case must produce, so a case cannot pass on an incidental failure.
BOTH_REJECT_ANSWER_REASON = {
    "extra envelope key": "Extra inputs are not permitted",
    "0.5 schema version": "Input should be '0.6'",
    "a v0.5 tool name": "Input should be 'get_service_dependencies_by_locality'",
    "ANSWERED with a limitation": "limitations must be exactly []",
    "PARTIAL without a limitation": "outcome must be ANSWERED",
    "null data on ANSWERED": "a null data is a NOT_ANSWERED refusal",
    "refusal with two limitations": "a null data is a NOT_ANSWERED refusal",
    "refusal with a non-refusal code": "a null data carries a refusal code",
    "evaluated data with a refusal code": "limitations must be exactly []",
    "evaluated NOT_ANSWERED without INSUFFICIENT_EVIDENCE": "limitations must be exactly []",
    "null snapshot without SNAPSHOT_NOT_AVAILABLE": "snapshot may be null only",
    "UNSUPPORTED_REQUEST without reasons": "UNSUPPORTED_REQUEST carries",
    "UNSUPPORTED_REQUEST with a non-unsupported reason": "UNSUPPORTED_REQUEST carries",
    "query mode with evidence data": "mode 'query' requires",
    "evidence mode with query data": "mode 'evidence' requires",
    "another coverage value": "Input should be 'LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE'",
    "a known target runtime scope": "Input should be 'UNKNOWN'",
    "a local NOT_OBSERVED_IN_WINDOW": "Input should be 'CONFIRMED' or 'OBSERVED_ONLY'",
    "an APPLICABLE pair without a Workload": "an APPLICABLE pair is phase 4",
    "an INAPPLICABLE pair with a Workload": "only an APPLICABLE pair carries",
    "a phase-2 pair that is not UNSUPPORTED": "a phase-2 pair is UNSUPPORTED",
    "a duplicated candidate": "candidates must be sorted and duplicate-free",
    "a selected Workload without a UID": "compare.0.uid",
    "a different pair bound": "Input should be 2000",
    "a comparison without compare": "comparison is present only when compare",
    "compare without a comparison": "comparison is required when compare",
    "a selection without caller_localities": "selection is present only when",
    "a NOT_FOUND entry with a record": "a NOT_FOUND entry carries no kind",
    "a capture entry with a v2-shaped ref": "a v2-shaped ref is never a capture ref",
    "a capture entry with non-Kubernetes evidence": "resolves Kubernetes evidence only",
    "a SCOPED_V2 entry without a scoped record": "exactly a scoped_record",
    "a RESOLVED entry without a kind": "a RESOLVED entry has a ref_kind",
    "a raw span field on a v2 record": "scoped_record.span_id",
    "more than five sample trace ids": "at most 5 items",
}


def test_every_both_reject_case_names_its_pydantic_reason():
    assert set(BOTH_REJECT_ANSWER_REASON) == set(BOTH_REJECT_ANSWER)


@pytest.mark.parametrize("case", sorted(BOTH_REJECT_ANSWER))
def test_invalid_answer_fails_both_pydantic_and_schema(case):
    base, mutate = BOTH_REJECT_ANSWER[case]
    answer = _mutated(base, mutate)
    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(answer)
    assert BOTH_REJECT_ANSWER_REASON[case] in str(excinfo.value)
    assert _schema_errors(answer, ANSWER_SCHEMA) != []


BOTH_REJECT_REQUEST: dict[str, tuple[Callable[[], dict], Callable[[dict], None]]] = {
    "unknown mode": (query_request, lambda r: r.update(mode="graph")),
    "extra field": (query_request, lambda r: r.update(cypher="MATCH (n) RETURN n")),
    "malformed day": (query_request, lambda r: r.update(first_day="30.09.2026")),
    "three compared Workloads": (
        query_request,
        lambda r: r.update(compare=[W1, W2, _identity("third")]),
    ),
    "a duplicate compared Workload": (query_request, lambda r: r.update(compare=[W1, W1])),
    "a compared Workload without a UID": (query_request, lambda r: r["compare"][0].pop("uid")),
    "a Workload kind outside D14.1": (
        query_request,
        lambda r: r["caller_localities"][0].update(kind="ReplicaSet"),
    ),
    "a malformed snapshot id": (query_request, lambda r: r.update(snapshot_id="latest")),
    "a cursor outside base64url": (query_request, lambda r: r.update(cursor="not a cursor!")),
    "evidence without a snapshot": (evidence_request, lambda r: r.pop("snapshot_id")),
    "evidence without refs": (evidence_request, lambda r: r.update(refs=[])),
    "21 evidence refs": (
        evidence_request,
        lambda r: r.update(refs=[f"evidence:k8s:{n:02d}" for n in range(21)]),
    ),
    "a duplicate evidence ref": (evidence_request, lambda r: r.update(refs=[V2_W1, V2_W1])),
    "an empty dimensions list": (query_request, lambda r: r.update(dimensions=[])),
}


@pytest.mark.parametrize("case", sorted(BOTH_REJECT_REQUEST))
def test_invalid_request_fails_both_pydantic_and_schema(case):
    base, mutate = BOTH_REJECT_REQUEST[case]
    request = _mutated(base, mutate)
    with pytest.raises(ValidationError):
        ServiceDependenciesByLocalityRequest.model_validate(request)
    assert _schema_errors(request, REQUEST_SCHEMA) != []


# --- Pydantic-only invariants (cross-field, ordering, decoding) ---------------------------------


PYDANTIC_REJECT_REQUEST: dict[str, Callable[[dict], None]] = {
    "a reversed window": lambda r: r.update(first_day="2026-10-01"),
    "a non-calendar day": lambda r: r.update(first_day="2026-02-30", last_day="2026-02-30"),
    "unsorted caller_localities": lambda r: r.update(caller_localities=[W2, W1]),
    "compare outside caller_localities": lambda r: r.update(
        compare=[W1, _identity("not-selected")]
    ),
    "unsorted dimensions": lambda r: r.update(dimensions=["workload", "cluster"]),
    "a base64url cursor that is not a locality cursor": lambda r: r.update(cursor="bm90LWpzb24"),
}


@pytest.mark.parametrize("case", sorted(PYDANTIC_REJECT_REQUEST))
def test_cross_field_request_invariants_are_rejected_by_pydantic(case):
    request = _mutated(query_request, PYDANTIC_REJECT_REQUEST[case])
    with pytest.raises(ValidationError):
        ServiceDependenciesByLocalityRequest.model_validate(request)


def test_unsorted_evidence_refs_are_rejected():
    with pytest.raises(ValidationError):
        ServiceDependenciesByLocalityRequest.model_validate(
            {**evidence_request(), "refs": [V2_W2, V2_W1]}
        )


def _set_inventory_partial(answer: dict) -> None:
    inventory = _data(answer)["inventory"]
    cursor = LocalityCursor(
        v=1, after_id=V2_W2, query_digest=DIGEST, snapshot_id=SNAPSHOT_ID, schema_version="0.6"
    )
    inventory.update(i2_truncated=True, completeness="PARTIAL", next_cursor=encode_cursor(cursor))
    for locality in _data(answer)["localities"]:
        locality["lineage_complete"] = False
        for assessment in locality["assessments"]:
            assessment["observation"]["lineage_complete"] = False
    _data(answer)["comparison"]["completeness"] = "PARTIAL"
    answer.update(
        outcome="PARTIAL",
        limitations=[
            {"code": "COMPARISON_INCOMPLETE", "message": "x", "reasons": []},
            {"code": "INVENTORY_INCOMPLETE", "message": "x", "reasons": []},
        ],
    )


def test_a_partial_inventory_with_a_snapshot_bound_cursor_is_valid():
    _assert_answer_valid(_mutated(query_answer, _set_inventory_partial))


def _set_continuation_page(answer: dict) -> None:
    """D16.11: the last page of a cursor walk has no next_cursor but is still PARTIAL."""
    _set_inventory_partial(answer)
    _data(answer)["inventory"].update(i2_truncated=False, continuation=True, next_cursor=None)


def test_a_final_continuation_page_is_partial_without_a_cursor():
    _assert_answer_valid(_mutated(query_answer, _set_continuation_page))


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"completeness": "COMPLETE"}, "the page continues a cursor"),
        ({"next_cursor": "x"}, "next_cursor"),
    ],
)
def test_a_continuation_page_never_claims_a_complete_inventory(change, reason):
    def mutate(answer: dict) -> None:
        _set_continuation_page(answer)
        if "next_cursor" in change:
            cursor = LocalityCursor(
                v=1,
                after_id=V2_W2,
                query_digest=DIGEST,
                snapshot_id=SNAPSHOT_ID,
                schema_version="0.6",
            )
            _data(answer)["inventory"]["next_cursor"] = encode_cursor(cursor)
        else:
            _data(answer)["inventory"].update(change)

    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(_mutated(query_answer, mutate))
    assert reason in str(excinfo.value)


PYDANTIC_REJECT_ANSWER: dict[str, tuple[Callable[[], dict], Callable[[dict], None]]] = {
    "unsorted candidates": (query_answer, lambda a: _data(a)["candidates"].reverse()),
    "a wrong candidate count": (
        query_answer,
        lambda a: _data(a)["inventory"].update(evaluated_v2_candidate_count=3),
    ),
    "a wrong pair count": (
        query_answer,
        lambda a: _data(a)["inventory"].update(admitted_pair_count=1),
    ),
    "a page size that ignores the source count": (
        query_answer,
        lambda a: _data(a)["inventory"].update(considered_capture_source_count=5),
    ),
    "an unpaired evaluated source": (
        query_answer,
        lambda a: _data(a)["inventory"]["evaluated_sources"].append(
            {
                "source_instance_id": "kubernetes:zz-unpaired",
                "revision": "r",
                "cluster_uid": "k2",
                "namespaces": [],
                "evidence_mode": "CAPTURED_RESOURCE",
                "captured_at": None,
            }
        ),
    ),
    "a PARTIAL inventory without a cursor": (
        query_answer,
        lambda a: _data(a)["inventory"].update(i2_truncated=True, completeness="PARTIAL"),
    ),
    "a cursor bound to another snapshot": (
        query_answer,
        lambda a: (
            _set_inventory_partial(a),
            _data(a)["inventory"].update(
                next_cursor=encode_cursor(
                    LocalityCursor(
                        v=1,
                        after_id=V2_W2,
                        query_digest=DIGEST,
                        snapshot_id=OTHER_SNAPSHOT_ID,
                        schema_version="0.6",
                    )
                )
            ),
        ),
    ),
    "complete lineage on a PARTIAL inventory": (
        query_answer,
        lambda a: (
            _set_inventory_partial(a),
            _data(a)["localities"][0].update(lineage_complete=True),
        ),
    ),
    "a provider group that pools qualifications": (
        query_answer,
        lambda a: _data(a)["localities"][0]["provider_groups"][0].update(
            member_qualifications=["CONFIRMED", "OBSERVED_ONLY"]
        ),
    ),
    "a provider group evidence union that drops a ref": (
        query_answer,
        lambda a: _data(a)["localities"][0]["provider_groups"][0]["evidence_refs"].pop(),
    ),
    "an assessed Operation in no group": (
        query_answer,
        lambda a: _data(a)["localities"][0].update(provider_groups=[]),
    ),
    "a POSITIVE claim for an evaluated-but-not-positive scope": (
        query_answer,
        lambda a: _data(a)["comparison"]["scopes"][1].update(evaluation="EVALUATED_NO_POSITIVE"),
    ),
    "an only_in_first that omits a membership": (
        query_answer,
        lambda a: _data(a)["comparison"].update(only_in_first=[]),
    ),
    "compared scopes out of request order": (
        query_answer,
        lambda a: _data(a)["comparison"]["scopes"].reverse(),
    ),
    "limitations that do not follow D9": (
        query_answer,
        lambda a: a.update(
            outcome="PARTIAL",
            limitations=[{"code": "PROVIDER_OWNER_UNRESOLVED", "message": "x", "reasons": []}],
        ),
    ),
    "an explicit selector with several sources": (
        query_answer,
        lambda a: (
            _data(a)["request_context"].update(
                source_selector=dict(SOURCE), selection_mode="EXPLICIT_SOURCE"
            )
            or _data(a)["inventory"].update(considered_capture_source_count=2)
            or _data(a)["inventory"]["bounds"].update(candidate_page_size=500)
        ),
    ),
    "a v2 record of another caller": (
        evidence_answer,
        lambda a: _data(a)["entries"][1]["scoped_record"].update(subject_id="service:billing"),
    ),
    "evidence NOT_ANSWERED while a ref resolved": (
        evidence_answer,
        lambda a: (
            _data(a)["entries"][0].update(status="NOT_FOUND", ref_kind=None, capture_record=None),
            a.update(
                outcome="NOT_ANSWERED",
                limitations=[{"code": "INSUFFICIENT_EVIDENCE", "message": "x", "reasons": []}],
            ),
        ),
    ),
}


PYDANTIC_REJECT_ANSWER_REASON = {
    "unsorted candidates": "candidates must be sorted and duplicate-free",
    "a wrong candidate count": "evaluated_v2_candidate_count must equal len(candidates)",
    "a wrong pair count": "admitted_pair_count must equal the number of listed pairs",
    "a page size that ignores the source count": "candidate_page_size must be min(500",
    "an unpaired evaluated source": "evaluated_sources are exactly the sources that formed a pair",
    "a PARTIAL inventory without a cursor": "next_cursor is present exactly when",
    "a cursor bound to another snapshot": "next_cursor must be bound to the answer's snapshot",
    "complete lineage on a PARTIAL inventory": "lineage must match",
    "a provider group that pools qualifications": "member_qualifications must be",
    "a provider group evidence union that drops a ref": "evidence_refs is its members' union",
    "an assessed Operation in no group": "every assessed Operation is in exactly one",
    "a POSITIVE claim for an evaluated-but-not-positive scope": "evaluation must follow D10",
    "an only_in_first that omits a membership": "only_in_first must be the memberships",
    "compared scopes out of request order": "comparison.scopes are the requested compare",
    "limitations that do not follow D9": "limitations must be exactly []",
    "an explicit selector with several sources": "an explicit source_selector considers",
    "a v2 record of another caller": "a resolved v2 record must match the requested caller",
    "evidence NOT_ANSWERED while a ref resolved": "outcome must be PARTIAL",
}


def test_every_pydantic_reject_case_names_its_reason():
    assert set(PYDANTIC_REJECT_ANSWER_REASON) == set(PYDANTIC_REJECT_ANSWER)


@pytest.mark.parametrize("case", sorted(PYDANTIC_REJECT_ANSWER))
def test_cross_field_answer_invariants_are_rejected_by_pydantic(case):
    base, mutate = PYDANTIC_REJECT_ANSWER[case]
    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(_mutated(base, mutate))
    assert PYDANTIC_REJECT_ANSWER_REASON[case] in str(excinfo.value)


def test_an_evidence_answer_with_some_refs_not_found_is_partial_insufficient_evidence():
    def mutate(answer: dict) -> None:
        _data(answer)["entries"][0].update(status="NOT_FOUND", ref_kind=None, capture_record=None)
        answer.update(
            outcome="PARTIAL",
            limitations=[{"code": "INSUFFICIENT_EVIDENCE", "message": "x", "reasons": []}],
        )

    _assert_answer_valid(_mutated(evidence_answer, mutate))


# --- D10 selected-scope status (decision record D15 R4-R6b) -------------------------------------


def _no_positive_w1(answer: dict) -> None:
    """I2 D4 S04: W1's candidate rolls up CONFLICT although source A's pair is APPLICABLE at W1."""
    data = _data(answer)
    candidate = data["candidates"][0]
    conflicting = copy.deepcopy(candidate["pairs"][0])
    conflicting.update(
        source={"source_instance_id": "kubernetes:other-cluster", "revision": "r2"},
        admission=["POD_UID"],
        disposition="CONFLICT",
        reasons=["LOCALITY_CLUSTER_UID_CONFLICT"],
        workload=None,
    )
    candidate.update(
        disposition="CONFLICT",
        reasons=["LOCALITY_CLUSTER_UID_CONFLICT"],
        workload=None,
        pairs=[conflicting, candidate["pairs"][0]],
    )
    data["inventory"].update(
        considered_capture_source_count=2,
        admitted_pair_count=3,
        evaluated_sources=[
            {
                "source_instance_id": "kubernetes:other-cluster",
                "revision": "r2",
                "cluster_uid": "k2",
                "namespaces": ["aip-locality"],
                "evidence_mode": "CAPTURED_RESOURCE",
                "captured_at": "2026-09-30T14:38:11Z",
            },
            *data["inventory"]["evaluated_sources"],
        ],
    )
    data["localities"].pop(0)
    comparison = data["comparison"]
    comparison["scopes"][0]["evaluation"] = "EVALUATED_NO_POSITIVE"
    comparison["only_in_first"] = []


def test_r5_a_conflicting_candidate_with_an_applicable_pair_is_evaluated_no_positive():
    _assert_answer_valid(_mutated(query_answer, _no_positive_w1))


def test_r5_the_same_scope_cannot_be_reported_unknown_when_it_was_evaluated():
    def mutate(answer: dict) -> None:
        _no_positive_w1(answer)
        _data(answer)["comparison"].update(completeness="NOT_ESTABLISHED")
        _data(answer)["comparison"]["scopes"][0]["evaluation"] = "UNKNOWN"
        answer.update(
            outcome="PARTIAL",
            limitations=[
                {"code": "COMPARISON_INCOMPLETE", "message": "x", "reasons": []},
                {"code": "SELECTION_NOT_ESTABLISHED", "message": "x", "reasons": []},
            ],
        )

    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(_mutated(query_answer, mutate))
    assert "a compared scope's evaluation must follow D10" in str(excinfo.value)


def _invented_first_scope(answer: dict) -> None:
    """D15 R4: `compare` names an identity no evaluated candidate or pair resolved."""
    invented = _identity("invented")
    data = _data(answer)
    data["request_context"]["compare"] = [invented, W2]
    data["comparison"].update(
        scopes=[
            {"workload": invented, "evaluation": "UNKNOWN"},
            {"workload": W2, "evaluation": "POSITIVE"},
        ],
        only_in_first=[],
        completeness="NOT_ESTABLISHED",
    )


def test_r4_an_invented_identity_is_unknown_and_the_comparison_not_established():
    """R4 requires both COMPARISON_INCOMPLETE and SELECTION_NOT_ESTABLISHED, also when only
    `compare` (no `caller_localities`) named the identity (PR #387 review)."""

    def mutate(answer: dict) -> None:
        _invented_first_scope(answer)
        answer.update(
            outcome="PARTIAL",
            limitations=[
                {"code": "COMPARISON_INCOMPLETE", "message": "x", "reasons": []},
                {"code": "SELECTION_NOT_ESTABLISHED", "message": "x", "reasons": []},
            ],
        )

    _assert_answer_valid(_mutated(query_answer, mutate))


def test_r4_without_selection_not_established_is_rejected():
    def mutate(answer: dict) -> None:
        _invented_first_scope(answer)
        answer.update(
            outcome="PARTIAL",
            limitations=[{"code": "COMPARISON_INCOMPLETE", "message": "x", "reasons": []}],
        )

    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(_mutated(query_answer, mutate))
    assert "SELECTION_NOT_ESTABLISHED" in str(excinfo.value)


def test_r4_an_invented_identity_cannot_be_evaluated_no_positive():
    def mutate(answer: dict) -> None:
        invented = _identity("invented")
        data = _data(answer)
        data["request_context"]["compare"] = [invented, W2]
        data["comparison"].update(
            scopes=[
                {"workload": invented, "evaluation": "EVALUATED_NO_POSITIVE"},
                {"workload": W2, "evaluation": "POSITIVE"},
            ],
            only_in_first=[],
        )

    _assert_answer_rejected_by_pydantic(_mutated(query_answer, mutate))


def test_r6_on_a_partial_inventory_the_evaluated_scope_is_unknown():
    def mutate(answer: dict) -> None:
        _no_positive_w1(answer)
        _set_inventory_partial(answer)
        _data(answer)["comparison"]["scopes"][0]["evaluation"] = "UNKNOWN"
        answer["limitations"].append(
            {"code": "SELECTION_NOT_ESTABLISHED", "message": "x", "reasons": []}
        )

    _assert_answer_valid(_mutated(query_answer, mutate))


def test_selection_unknown_entries_add_selection_not_established():
    def mutate(answer: dict) -> None:
        invented = _identity("zz-invented")
        data = _data(answer)
        data["request_context"]["caller_localities"] = [W1, W2, invented]
        data["selection"] = [
            {"workload": W1, "evaluation": "POSITIVE"},
            {"workload": W2, "evaluation": "POSITIVE"},
            {"workload": invented, "evaluation": "UNKNOWN"},
        ]
        answer.update(
            outcome="PARTIAL",
            limitations=[{"code": "SELECTION_NOT_ESTABLISHED", "message": "x", "reasons": []}],
        )

    _assert_answer_valid(_mutated(query_answer, mutate))


def test_a_complete_inventory_without_positives_is_not_answered_with_its_payload():
    """D9 (Q1): no positive result is NOT_ANSWERED / INSUFFICIENT_EVIDENCE, with the inventory."""

    def mutate(answer: dict) -> None:
        data = _data(answer)
        data["request_context"]["compare"] = None
        data.update(candidates=[], localities=[], comparison=None)
        data["inventory"].update(
            evaluated_v2_candidate_count=0, admitted_pair_count=0, evaluated_sources=[]
        )
        answer.update(
            outcome="NOT_ANSWERED",
            limitations=[{"code": "INSUFFICIENT_EVIDENCE", "message": "x", "reasons": []}],
        )

    _assert_answer_valid(_mutated(query_answer, mutate))


def test_an_unresolved_owner_is_partial_and_mints_no_provider_group():
    def mutate(answer: dict) -> None:
        locality = _data(answer)["localities"][1]
        locality["provider_groups"] = []
        locality["unresolved_owner_operations"] = [
            {"operation_id": O2, "reason": "PROVIDER_OWNER_MISSING"}
        ]
        _data(answer)["comparison"]["only_in_second"][0]["provider_service_id"] = None
        answer.update(
            outcome="PARTIAL",
            limitations=[{"code": "PROVIDER_OWNER_UNRESOLVED", "message": "x", "reasons": []}],
        )

    _assert_answer_valid(_mutated(query_answer, mutate))


def _filter_to_pricing(answer: dict) -> None:
    """D16.4: the provider filter scopes `localities`; `candidates` stays the full inventory."""
    data = _data(answer)
    data["request_context"].update(provider_service_id="service:pricing", compare=None)
    data["localities"].pop(1)
    data["comparison"] = None


def test_a_provider_filter_lists_only_that_providers_localities():
    _assert_answer_valid(_mutated(query_answer, _filter_to_pricing))


def test_a_provider_filter_rejects_another_providers_group():
    def mutate(answer: dict) -> None:
        _data(answer)["request_context"].update(provider_service_id="service:pricing")

    with pytest.raises(ValidationError) as excinfo:
        LocalityAnswer.model_validate(_mutated(query_answer, mutate))
    assert "only that provider's groups are listed" in str(excinfo.value)


# --- D4/D5 helpers ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sources, expected", [(0, 500), (1, 500), (4, 500), (5, 400), (7, 285), (2000, 1)]
)
def test_candidate_page_size_is_min_500_and_pair_bound_over_sources(sources, expected):
    assert candidate_page_size(sources) == expected


def test_a_cursor_round_trips_in_canonical_form():
    cursor = LocalityCursor(
        v=1, after_id=V2_W1, query_digest=DIGEST, snapshot_id=SNAPSHOT_ID, schema_version="0.6"
    )
    encoded = encode_cursor(cursor)
    assert "=" not in encoded
    assert decode_cursor(encoded) == cursor


@pytest.mark.parametrize(
    "payload",
    [
        {
            "v": 2,
            "after_id": V2_W1,
            "query_digest": DIGEST,
            "snapshot_id": SNAPSHOT_ID,
            "schema_version": "0.6",
        },
        {
            "v": 1,
            "after_id": "evidence:otel:x",
            "query_digest": DIGEST,
            "snapshot_id": SNAPSHOT_ID,
            "schema_version": "0.6",
        },
        {
            "v": 1,
            "after_id": V2_W1,
            "query_digest": DIGEST,
            "snapshot_id": SNAPSHOT_ID,
            "schema_version": "0.6",
            "extra": 1,
        },
    ],
)
def test_a_malformed_cursor_is_rejected(payload):
    import base64

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError):
        decode_cursor(base64.urlsafe_b64encode(raw).decode().rstrip("="))


def test_a_non_canonical_cursor_encoding_is_rejected():
    import base64

    cursor = LocalityCursor(
        v=1, after_id=V2_W1, query_digest=DIGEST, snapshot_id=SNAPSHOT_ID, schema_version="0.6"
    )
    spaced = json.dumps(cursor.model_dump(), sort_keys=True).encode()
    with pytest.raises(ValueError):
        decode_cursor(base64.urlsafe_b64encode(spaced).decode().rstrip("="))


# --- Parity with internal I2 values (by value, not import) --------------------------------------


def test_public_enums_mirror_the_internal_i2_values():
    assert {item.value for item in LocalDisposition} == {item.value for item in LocalityDisposition}
    assert {item.value for item in AdmissionBasis} == {
        item.value for item in InternalAdmissionBasis
    }
    assert {item.value for item in CandidateLimitationCode} == {
        *(item.value for item in ScopedLimitation),
        *(item.value for item in AssessmentLimitation),
    }
    assert {item.value for item in CapturedWorkloadKind} == set(WORKLOAD_KIND_BY_RAW)
    assert UNSUPPORTED_REQUEST_REASONS == {
        REASON_UNSUPPORTED_DIMENSION,
        REASON_UNSUPPORTED_RELATION,
        REASON_UNSUPPORTED_TEMPORAL_RESOLUTION,
    }
    assert set(DEFAULT_DIMENSIONS) == SUPPORTED_DIMENSIONS
    assert MAX_CANDIDATE_PAGE == DEFAULT_PAGE_SIZE
    assert PUBLIC_COVERAGE == LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE
    assert PUBLIC_TARGET_SCOPE == TARGET_RUNTIME_SCOPE_UNKNOWN
    v2_pattern = ANSWER_SCHEMA["$defs"]["ScopedV2Record"]["properties"]["id"]["pattern"]
    assert v2_pattern.startswith(f"^{SCOPED_CALL_V2_ID_PREFIX}")


def test_the_v05_tool_set_is_unchanged():
    """D1/D2: the fourth tool is a separate 0.6 contract, not a widened 0.5 enum."""
    assert contracts.TOOL_NAMES == (
        "get_architecture_drift",
        "get_evidence",
        "get_service_dependencies",
    )
    assert contracts.ARCHITECTURE_SCHEMA_VERSION == "0.5"
