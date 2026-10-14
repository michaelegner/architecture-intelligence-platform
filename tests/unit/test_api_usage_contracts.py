"""v0.7.0 I3.1b: the 0.7 API-consumer-usage contract (I3 decision record D1-D12).

Every invariant the JSON Schema can express must be rejected by **both** Pydantic and the committed
schema; the rest are Pydantic-only and are tested as such. The valid payloads are hand-written, not
produced by any service code (there is none yet).
"""

import base64
import copy
import hashlib
import json
from collections.abc import Callable
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence import contracts
from app.architecture_intelligence.api_usage_contracts import (
    API_USAGE_SCHEMA_VERSION,
    API_USAGE_TOOL_NAME,
    REFUSAL_CODES_EVIDENCE,
    REFUSAL_CODES_QUERY,
    ApiConsumerUsageAnswer,
    ApiConsumerUsageRequest,
    ApiUsageCursor,
    ApiUsageLimitationCode,
    ConfiguredAccessStatus,
    Coverage,
    EvidenceKind,
    MeasurementCode,
    Reconciliation,
    TargetKind,
    UsageStatus,
    WindowReasonCode,
    decode_cursor,
    encode_cursor,
    evidence_ref,
    query_context_digest,
)
from app.architecture_intelligence.schema_export import (
    API_USAGE_ANSWER_SCHEMA_PATH,
    API_USAGE_REQUEST_SCHEMA_PATH,
)
from app.canonical import gateway_measurement
from app.sources import apisix_qualification as qualification
from app.sources import apisix_reconciliation as reconciliation
from app.sources.apisix_measurement_contract import (
    VERSION_INCOMPATIBLE,
    WINDOW_NOT_SETTLED,
    WINDOW_ORDER_INVALID,
    WINDOW_RESTART,
)

ANSWER_SCHEMA = json.loads(API_USAGE_ANSWER_SCHEMA_PATH.read_text())
REQUEST_SCHEMA = json.loads(API_USAGE_REQUEST_SCHEMA_PATH.read_text())

DIGEST = "3a0b04e1d88feaae5ebb2277f8fe50fba74279cc3af12906edc37a31e55c59f9"
SNAPSHOT_ID = f"aip:snapshot:v1:{DIGEST}"
OTHER_SNAPSHOT_ID = f"aip:snapshot:v1:{'0' * 64}"
GATEWAY, ENVIRONMENT = "gw-prod-1", "prod"
WINDOW_START, WINDOW_END = "2026-10-13T10:00:00Z", "2026-10-13T10:10:00Z"
C1, C2 = (f"gateway-consumer:owned:{c * 64}" for c in "12")
R1, R2 = (f"gateway-route:owned:{c * 64}" for c in "34")
OPERATION = "operation:orders:POST:/orders"
SERVICE = "service:order-service"
INTERACTION = f"observed-consumer-interaction:owned:{'5' * 64}"
REF_WINDOW, REF_CONFIG, REF_OPERATION, REF_SERVICE, REF_LIMITS = (
    f"api-evidence:{c * 64}" for c in "abcde"
)
ALL_REFS = [REF_WINDOW, REF_CONFIG, REF_OPERATION, REF_SERVICE]


def _schema_errors(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in validator.iter_errors(instance)]


def _assert_answer_valid(answer: dict[str, Any]) -> None:
    ApiConsumerUsageAnswer.model_validate(answer)
    assert _schema_errors(answer, ANSWER_SCHEMA) == []


def _mutated(base: Callable[[], dict[str, Any]], mutate: Callable[[dict], None]) -> dict:
    answer = copy.deepcopy(base())
    mutate(answer)
    return answer


# --- Hand-written valid shapes ------------------------------------------------------------------


def target(kind: str = "API_OPERATION") -> dict[str, str]:
    ids = {"API_OPERATION": OPERATION, "APPLICATION_SERVICE": SERVICE, "GATEWAY_ROUTE": R1}
    return {"kind": kind, "id": ids[kind]}


def context(kind: str = "API_OPERATION", **extra: Any) -> dict[str, Any]:
    return {
        "target": target(kind),
        "gateway_instance_id": GATEWAY,
        "environment": ENVIRONMENT,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        **extra,
    }


def query_request() -> dict[str, Any]:
    return {"mode": "query", **context(), "limit": 100}


def evidence_request() -> dict[str, Any]:
    return {
        "mode": "evidence",
        "snapshot_id": SNAPSHOT_ID,
        **context(),
        "evidence_refs": ALL_REFS,
    }


def digest_of(ctx: dict[str, Any]) -> str:
    return query_context_digest(
        target_kind=ctx["target"]["kind"],
        target_id=ctx["target"]["id"],
        gateway_instance_id=ctx["gateway_instance_id"],
        environment=ctx["environment"],
        window_start=ctx["window_start"],
        window_end=ctx["window_end"],
        consumer_id=ctx.get("consumer_id"),
    )


def window(*reasons: str) -> dict[str, Any]:
    return {
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "source_instance_id": "urn:aip:source:apisix-measurement:x",
        "valid": not reasons,
        "reasons": list(reasons),
        "evidence_refs": [REF_WINDOW],
    }


def selected_route(
    route: str = R1, *, coverage: str = "SUFFICIENT_FOR_ZERO", limitations: list[str] | None = None
) -> dict[str, Any]:
    limitations = limitations or []
    return {
        "route_id": route,
        "source_route_id": "orders-route",
        "coverage": coverage,
        "limitations": limitations,
        "evidence_refs": [REF_LIMITS] if limitations else [],
    }


def row(
    consumer: str = C1,
    route: str = R1,
    *,
    status: str = "OBSERVED_USAGE",
    configured: str = "CONFIGURED_ACCESS_ESTABLISHED",
    coverage: str = "SUFFICIENT_FOR_ZERO",
    counts: tuple[int, int] | None = (3, 0),
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    usage: dict[str, Any] = {"status": status, "coverage": coverage}
    if counts is not None:
        usage |= {"upstream_request_count": counts[0], "rejected_attempt_count": counts[1]}
    if status == "OBSERVED_USAGE":
        usage["interaction_id"] = INTERACTION
    return {
        "consumer": {"id": consumer, "source_name": "alice"},
        "gateway_route": {"id": route, "gateway_instance_id": GATEWAY, "source_route_id": "orders-route"},
        "api": {
            "reconciliation": "RESOLVED",
            "operation_id": OPERATION,
            "contract_version_reconciliation": "RESOLVED",
            "contract_version_id": "contract-version:orders:1",
            "contract_id": "contract:orders",
        },
        "application_service": {"reconciliation": "RESOLVED", "service_id": SERVICE},
        "configured_access": {"status": configured},
        "usage": usage,
        "evidence_refs": ALL_REFS,
        "limitations": limitations or [],
    }  # fmt: skip


def counts(**values: int) -> dict[str, int]:
    return {
        "resolved_to_target": 0,
        "resolved_elsewhere": 0,
        "unresolved": 0,
        "ambiguous": 0,
        "conflict": 0,
        **values,
    }


def query_data() -> dict[str, Any]:
    return {
        "request_context": context(),
        "window": window(),
        "rules": {
            "reconciliation": {"rule_id": "apisix-api-usage-reconciliation", "rule_version": "1"},
            "qualification": {
                "rule_id": "apisix-configured-vs-observed-qualification",
                "rule_version": "1",
            },
        },
        "association_summary": {
            "route_operation": counts(resolved_to_target=1, unresolved=1),
        },
        "selected_routes": [selected_route()],
        "configuration_sources": [
            {"gateway_instance_id": GATEWAY, "environment": ENVIRONMENT, "source_revision": "apisix:3.19.0+etcd:18"}
        ],
        "measurement_sources": [
            {
                "source_instance_id": "urn:aip:source:apisix-measurement:x",
                "window_start": WINDOW_START,
                "window_end": WINDOW_END,
                "apisix_version": "3.19.0",
            }
        ],
        "rows": [row()],
        "page": {"limit": 100, "returned": 1},
    }  # fmt: skip


def envelope(mode: str, outcome: str, data: Any, codes: list[str], *, snapshot=True) -> dict:
    return {
        "schema_version": API_USAGE_SCHEMA_VERSION,
        "producer": {
            "name": "architecture-intelligence-platform",
            "version": "0.7.0",
            "build_revision": "abc1234",
        },
        "tool": API_USAGE_TOOL_NAME,
        "mode": mode,
        "outcome": outcome,
        "snapshot": {"snapshot_id": SNAPSHOT_ID, "model_revision": f"sha256:{DIGEST}"}
        if snapshot
        else None,
        "data": data,
        "limitations": [{"code": code, "message": f"{code}."} for code in codes],
    }


def query_answer() -> dict[str, Any]:
    return envelope("query", "ANSWERED", query_data(), [])


def paged_answer() -> dict[str, Any]:
    data = query_data()
    cursor = encode_cursor(
        ApiUsageCursor(
            v=1,
            after=(C1, R1),
            query_digest=digest_of(data["request_context"]),
            schema_version="0.7",
            snapshot_id=SNAPSHOT_ID,
        )
    )
    data["page"]["next_cursor"] = cursor
    return envelope("query", "PARTIAL", data, ["MORE_ROWS_AVAILABLE"])


def invalid_window_answer() -> dict[str, Any]:
    data = query_data()
    data["window"] = window("GWM_WINDOW_NOT_SETTLED")
    data["selected_routes"] = [
        selected_route(coverage="UNKNOWN_COVERAGE", limitations=["GWM_WINDOW_NOT_SETTLED"])
    ]
    data["rows"] = [
        row(
            status="USAGE_UNESTABLISHED",
            coverage="UNKNOWN_COVERAGE",
            counts=None,
            limitations=["GWM_WINDOW_NOT_SETTLED"],
        )
    ]
    return envelope("query", "PARTIAL", data, ["COVERAGE_UNKNOWN", "WINDOW_NOT_VALID"])


def no_route_answer() -> dict[str, Any]:
    data = query_data()
    data["association_summary"] = {"route_operation": counts(unresolved=2)}
    data["selected_routes"], data["rows"] = [], []
    data["page"]["returned"] = 0
    return envelope("query", "NOT_ANSWERED", data, ["NO_ROUTE_SELECTED"])


def route_target_answer() -> dict[str, Any]:
    data = query_data()
    data["request_context"] = context("GATEWAY_ROUTE")
    del data["association_summary"]
    return envelope("query", "ANSWERED", data, [])


def refusal_answer(
    code: str = "MEASUREMENT_WINDOW_NOT_AVAILABLE", mode: str = "query"
) -> dict[str, Any]:
    return envelope(mode, "NOT_ANSWERED", None, [code], snapshot=code != "SNAPSHOT_NOT_AVAILABLE")


def evidence_payloads() -> dict[str, dict[str, Any]]:
    route = {"id": R1, "source_route_id": "orders-route"}
    rule = {"rule_id": "apisix-api-usage-reconciliation", "rule_version": "1"}
    return {
        REF_CONFIG: {
            "kind": "CONFIGURED_ACCESS",
            "gateway_instance_id": GATEWAY,
            "environment": ENVIRONMENT,
            "source_revision": "apisix:3.19.0+etcd:18",
            "consumer": {"id": C1, "source_name": "alice"},
            "gateway_route": route,
            "rule_kind": "consumer-restriction",
            "polarity": "ALLOW",
            "scope": "route",
        },
        REF_WINDOW: {
            "kind": "MEASUREMENT_WINDOW",
            "source_instance_id": "urn:aip:source:apisix-measurement:x",
            "gateway_instance_id": GATEWAY,
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
            "apisix_version": "3.19.0",
            "start_settled": True,
            "end_settled": True,
            "no_restart": True,
            "start_stable_seconds": 24,
            "end_stable_seconds": 22,
            "valid": True,
            "reasons": [],
            "evidence_type": "OBSERVED",
            "extract_digests": {"start_sha256": "1" * 64, "end_sha256": "2" * 64},
        },
        REF_OPERATION: {
            "kind": "ROUTE_OPERATION_RECONCILIATION",
            "gateway_route": route,
            "outcome": "RESOLVED",
            "operation_id": OPERATION,
            "contract_version_reconciliation": "RESOLVED",
            "contract_version_id": "contract-version:orders:1",
            "mapping_entries": [{"operation_id": OPERATION}],
            "rule": rule,
        },
        REF_SERVICE: {
            "kind": "TARGET_SERVICE_RECONCILIATION",
            "gateway_route": route,
            "outcome": "RESOLVED",
            "service_id": SERVICE,
            "mapping_entries": [{"target": "ROUTE", "service_id": SERVICE}],
            "labels": [{"carrier": "ROUTE", "service_id": SERVICE}],
            "rule": rule,
        },
        REF_LIMITS: {
            "kind": "QUALIFICATION_LIMITATIONS",
            "gateway_route": route,
            "coverage": "UNKNOWN_COVERAGE",
            "codes": ["GWM_UNATTRIBUTED_UPSTREAM"],
            "window_valid": True,
        },
    }


def _entry(ref: str, *, resolved: bool = True) -> dict[str, Any]:
    if not resolved:
        return {"ref": ref, "status": "NOT_RESOLVED"}
    payload = evidence_payloads()[ref]
    return {"ref": ref, "status": "RESOLVED", "kind": payload["kind"], "evidence": payload}


def evidence_answer(resolved: tuple[bool, ...] = (True, True)) -> dict[str, Any]:
    refs = ALL_REFS[: len(resolved)]
    entries = sorted(
        (_entry(ref, resolved=ok) for ref, ok in zip(refs, resolved, strict=True)),
        key=lambda e: e["ref"],
    )
    data = {"request_context": context(), "entries": entries}
    if all(resolved):
        return envelope("evidence", "ANSWERED", data, [])
    outcome = "PARTIAL" if any(resolved) else "NOT_ANSWERED"
    return envelope("evidence", outcome, data, ["EVIDENCE_REF_NOT_RESOLVED"])


# --- Valid shapes -------------------------------------------------------------------------------

VALID_ANSWERS = [
    query_answer,
    paged_answer,
    invalid_window_answer,
    no_route_answer,
    route_target_answer,
    lambda: evidence_answer((True, True)),
    lambda: evidence_answer((True, False)),
    lambda: evidence_answer((False, False)),
    *(
        (lambda code=code: refusal_answer(code))
        for code in sorted(c.value for c in REFUSAL_CODES_QUERY)
    ),
    *(
        (lambda code=code: refusal_answer(code, "evidence"))
        for code in sorted(c.value for c in REFUSAL_CODES_EVIDENCE)
    ),
]


@pytest.mark.parametrize("build", VALID_ANSWERS)
def test_valid_answers_pass_pydantic_and_the_committed_schema(build):
    _assert_answer_valid(build())


@pytest.mark.parametrize("build", [query_request, evidence_request])
def test_valid_requests_pass_pydantic_and_the_committed_schema(build):
    ApiConsumerUsageRequest.model_validate(build())
    assert _schema_errors(build(), REQUEST_SCHEMA) == []


def test_every_evidence_kind_has_a_valid_resolved_entry():
    payloads = evidence_payloads()
    assert {p["kind"] for p in payloads.values()} == {k.value for k in EvidenceKind}
    refs = sorted(payloads)
    data = {"request_context": context(), "entries": [_entry(r) for r in refs]}
    _assert_answer_valid(envelope("evidence", "ANSWERED", data, []))


def test_a_serialized_answer_round_trips_and_still_validates_against_the_schema():
    answer = ApiConsumerUsageAnswer.model_validate(paged_answer())
    payload = answer.model_dump(mode="json")
    assert ApiConsumerUsageAnswer.model_validate(payload) == answer
    assert _schema_errors(payload, ANSWER_SCHEMA) == []


def test_the_request_defaults_and_a_reversed_window_are_accepted():
    request = query_request()
    del request["limit"]
    parsed = ApiConsumerUsageRequest.model_validate(request).root
    assert parsed.limit == 100 and parsed.consumer_id is None and parsed.cursor is None
    reversed_window = query_request() | {"window_start": WINDOW_END, "window_end": WINDOW_START}
    ApiConsumerUsageRequest.model_validate(reversed_window)
    assert _schema_errors(reversed_window, REQUEST_SCHEMA) == []


@pytest.mark.parametrize("kind", [k.value for k in TargetKind])
def test_each_target_kind_accepts_only_its_own_id_form(kind):
    ids = {"API_OPERATION": OPERATION, "APPLICATION_SERVICE": SERVICE, "GATEWAY_ROUTE": R1}
    for other_kind, other_id in ids.items():
        request = query_request() | {"target": {"kind": kind, "id": other_id}}
        ok = other_kind == kind
        assert (_schema_errors(request, REQUEST_SCHEMA) == []) is ok
        if ok:
            ApiConsumerUsageRequest.model_validate(request)
        else:
            with pytest.raises(ValidationError):
                ApiConsumerUsageRequest.model_validate(request)


# --- Both reject (Pydantic and the committed schema) --------------------------------------------

BOTH_REJECT_REQUEST: dict[str, tuple[Callable[[], dict], Callable[[dict], None]]] = {
    "unknown mode": (query_request, lambda r: r.update(mode="graph")),
    "extra field": (query_request, lambda r: r.update(cypher="MATCH (n) RETURN n")),
    "a username search field": (query_request, lambda r: r.update(username="alice")),
    "unknown target kind": (query_request, lambda r: r["target"].update(kind="GATEWAY_SERVICE")),
    "an empty target id": (query_request, lambda r: r["target"].update(id="")),
    "a display name as target": (query_request, lambda r: r["target"].update(id="orders")),
    "no target": (query_request, lambda r: r.pop("target")),
    "no gateway instance": (query_request, lambda r: r.pop("gateway_instance_id")),
    "an empty gateway instance": (query_request, lambda r: r.update(gateway_instance_id="")),
    "no environment": (query_request, lambda r: r.pop("environment")),
    "a date-only window start": (query_request, lambda r: r.update(window_start="2026-10-13")),
    "a fractional window end": (
        query_request,
        lambda r: r.update(window_end="2026-10-13T10:10:00.5Z"),
    ),
    "a non-UTC window end": (
        query_request,
        lambda r: r.update(window_end="2026-10-13T10:10:00+02:00"),
    ),
    "a username as consumer id": (query_request, lambda r: r.update(consumer_id="alice")),
    "limit zero": (query_request, lambda r: r.update(limit=0)),
    "limit above the maximum": (query_request, lambda r: r.update(limit=201)),
    "a malformed snapshot id": (query_request, lambda r: r.update(snapshot_id="latest")),
    "a cursor outside base64url": (query_request, lambda r: r.update(cursor="not a cursor!")),
    "evidence without a snapshot": (evidence_request, lambda r: r.pop("snapshot_id")),
    "evidence without refs": (evidence_request, lambda r: r.update(evidence_refs=[])),
    "21 evidence refs": (
        evidence_request,
        lambda r: r.update(evidence_refs=sorted(f"api-evidence:{n:064x}" for n in range(21))),
    ),
    "a duplicate evidence ref": (
        evidence_request,
        lambda r: r.update(evidence_refs=[REF_WINDOW, REF_WINDOW]),
    ),
    "a malformed evidence ref": (
        evidence_request,
        lambda r: r.update(evidence_refs=["evidence:otel:x"]),
    ),
    "evidence with a limit": (evidence_request, lambda r: r.update(limit=10)),
    "evidence with a cursor": (evidence_request, lambda r: r.update(cursor="abc")),
}


@pytest.mark.parametrize("case", sorted(BOTH_REJECT_REQUEST))
def test_invalid_request_fails_both_pydantic_and_schema(case):
    base, mutate = BOTH_REJECT_REQUEST[case]
    request = _mutated(base, mutate)
    with pytest.raises(ValidationError):
        ApiConsumerUsageRequest.model_validate(request)
    assert _schema_errors(request, REQUEST_SCHEMA) != []


def _refusal(code: str, mode: str = "query") -> Callable[[], dict]:
    return lambda: refusal_answer(code, mode)


BOTH_REJECT_ANSWER: dict[str, tuple[Callable[[], dict], Callable[[dict], None]]] = {
    "a 0.6 schema version": (query_answer, lambda a: a.update(schema_version="0.6")),
    "another tool name": (query_answer, lambda a: a.update(tool="get_evidence")),
    "an unknown mode": (query_answer, lambda a: a.update(mode="graph")),
    "an extra top-level field": (query_answer, lambda a: a.update(cypher="MATCH (n)")),
    "a credential-like field on a row": (
        query_answer,
        lambda a: a["data"]["rows"][0]["consumer"].update(api_key="secret"),
    ),
    "a plugin config on a row": (
        query_answer,
        lambda a: a["data"]["rows"][0].update(plugins={"key-auth": {}}),
    ),
    "an unknown usage status": (
        query_answer,
        lambda a: a["data"]["rows"][0]["usage"].update(status="USED"),
    ),
    "a boolean in place of the reconciliation": (
        query_answer,
        lambda a: a["data"]["rows"][0]["api"].update(reconciliation=True),
    ),
    "a malformed consumer id": (
        query_answer,
        lambda a: a["data"]["rows"][0]["consumer"].update(id="alice"),
    ),
    "a service id on an operation target": (
        query_answer,
        lambda a: a["data"]["request_context"]["target"].update(id=SERVICE),
    ),
    "more than 200 rows per page": (
        query_answer,
        lambda a: a["data"]["page"].update(limit=201),
    ),
    "a null data with a non-refusal code": (
        _refusal("WINDOW_NOT_VALID"),
        lambda a: None,
    ),
    "a null data that is not NOT_ANSWERED": (
        _refusal("UNKNOWN_TARGET"),
        lambda a: a.update(outcome="PARTIAL"),
    ),
    "a refusal with two limitations": (
        _refusal("UNKNOWN_TARGET"),
        lambda a: a["limitations"].append({"code": "WINDOW_NOT_VALID", "message": "x."}),
    ),
    "a cursor mismatch in evidence mode": (
        lambda: refusal_answer("CURSOR_QUERY_MISMATCH", "evidence"),
        lambda a: None,
    ),
    "a refusal code with data": (
        query_answer,
        lambda a: a.update(
            outcome="NOT_ANSWERED", limitations=[{"code": "UNKNOWN_TARGET", "message": "x."}]
        ),
    ),
    "ANSWERED with limitations": (
        query_answer,
        lambda a: a["limitations"].append({"code": "WINDOW_NOT_VALID", "message": "x."}),
    ),
    "PARTIAL without limitations": (paged_answer, lambda a: a.update(limitations=[])),
    "a null snapshot without SNAPSHOT_NOT_AVAILABLE": (
        query_answer,
        lambda a: a.update(snapshot=None),
    ),
    "a no-route answer without NO_ROUTE_SELECTED": (
        no_route_answer,
        lambda a: a.update(limitations=[{"code": "COVERAGE_UNKNOWN", "message": "x."}]),
    ),
    "an unresolved-evidence answer without EVIDENCE_REF_NOT_RESOLVED": (
        lambda: evidence_answer((False, False)),
        lambda a: a.update(limitations=[{"code": "WINDOW_NOT_VALID", "message": "x."}]),
    ),
    "a RESOLVED entry without evidence": (
        lambda: evidence_answer((True, True)),
        lambda a: a["data"]["entries"][0].pop("evidence"),
    ),
    "a NOT_RESOLVED entry with a kind": (
        lambda: evidence_answer((False, False)),
        lambda a: a["data"]["entries"][0].update(kind="CONFIGURED_ACCESS"),
    ),
    "an evidence payload with a raw metric label": (
        lambda: evidence_answer((True, True)),
        lambda a: a["data"]["entries"][0]["evidence"].update(labels={"consumer": "x"}),
    ),
    "an evidence payload of an unknown kind": (
        lambda: evidence_answer((True, True)),
        lambda a: a["data"]["entries"][0]["evidence"].update(kind="RAW_PLUGIN_CONFIG"),
    ),
}

BOTH_REJECT_ANSWER_REASON = {
    "a 0.6 schema version": "Input should be '0.7'",
    "another tool name": "Input should be 'get_api_consumer_usage'",
    "an unknown mode": "Input should be 'query' or 'evidence'",
    "an extra top-level field": "Extra inputs are not permitted",
    "a credential-like field on a row": "Extra inputs are not permitted",
    "a plugin config on a row": "Extra inputs are not permitted",
    "an unknown usage status": "Input should be 'OBSERVED_USAGE'",
    "a boolean in place of the reconciliation": "Input should be 'RESOLVED'",
    "a malformed consumer id": "String should match pattern",
    "a service id on an operation target": "id is not a API_OPERATION id",
    "more than 200 rows per page": "less than or equal to 200",
    "a null data with a non-refusal code": "a query refusal carries one of",
    "a null data that is not NOT_ANSWERED": "a null data is a NOT_ANSWERED refusal",
    "a refusal with two limitations": "a null data is a NOT_ANSWERED refusal",
    "a cursor mismatch in evidence mode": "an evidence refusal carries one of",
    "a refusal code with data": "a refusal code requires null data",
    "ANSWERED with limitations": "limitations must be exactly",
    "PARTIAL without limitations": "limitations must be exactly",
    "a null snapshot without SNAPSHOT_NOT_AVAILABLE": "snapshot may be null only with",
    "a no-route answer without NO_ROUTE_SELECTED": "limitations must be exactly",
    "an unresolved-evidence answer without EVIDENCE_REF_NOT_RESOLVED": "limitations must be exactly",
    "a RESOLVED entry without evidence": "a RESOLVED entry carries kind and evidence",
    "a NOT_RESOLVED entry with a kind": "a NOT_RESOLVED entry carries no kind",
    "an evidence payload with a raw metric label": "Extra inputs are not permitted",
    "an evidence payload of an unknown kind": "does not match any of the expected tags",
}


def test_every_both_reject_case_names_its_pydantic_reason():
    assert set(BOTH_REJECT_ANSWER_REASON) == set(BOTH_REJECT_ANSWER)


@pytest.mark.parametrize("case", sorted(BOTH_REJECT_ANSWER))
def test_invalid_answer_fails_both_pydantic_and_schema(case):
    base, mutate = BOTH_REJECT_ANSWER[case]
    answer = _mutated(base, mutate)
    with pytest.raises(ValidationError) as excinfo:
        ApiConsumerUsageAnswer.model_validate(answer)
    assert BOTH_REJECT_ANSWER_REASON[case] in str(excinfo.value)
    assert _schema_errors(answer, ANSWER_SCHEMA) != []


# --- Pydantic only (JSON Schema cannot express these) -------------------------------------------


def _reversed(items: list) -> None:
    items.reverse()


PYDANTIC_ONLY_REQUEST: dict[str, tuple[Callable[[], dict], Callable[[dict], None], str]] = {
    "a cursor without a snapshot_id": (
        query_request,
        lambda r: r.update(cursor=encode_cursor(_cursor())),
        "a cursor requires snapshot_id",
    ),
    "an undecodable cursor": (
        query_request,
        lambda r: r.update(cursor="AAAA", snapshot_id=SNAPSHOT_ID),
        "cursor is not a well-formed",
    ),
    "unsorted evidence refs": (
        evidence_request,
        lambda r: _reversed(r["evidence_refs"]),
        "evidence_refs must be sorted",
    ),
}


def _cursor(**override: Any) -> ApiUsageCursor:
    fields: dict[str, Any] = {
        "v": 1,
        "after": (C1, R1),
        "query_digest": digest_of(context()),
        "schema_version": "0.7",
        "snapshot_id": SNAPSHOT_ID,
        **override,
    }
    return ApiUsageCursor.model_validate(fields)


@pytest.mark.parametrize("case", sorted(PYDANTIC_ONLY_REQUEST))
def test_cross_field_request_invariants_are_rejected_by_pydantic(case):
    base, mutate, reason = PYDANTIC_ONLY_REQUEST[case]
    with pytest.raises(ValidationError, match=reason):
        ApiConsumerUsageRequest.model_validate(_mutated(base, mutate))


def _rows2(a: dict) -> None:
    data = a["data"]
    data["selected_routes"] = [selected_route(R1), selected_route(R2)]
    data["association_summary"]["route_operation"] = counts(resolved_to_target=2)
    data["rows"] = [row(C1, R1), row(C2, R2)]
    data["page"]["returned"] = 2


PYDANTIC_ONLY_ANSWER: dict[str, tuple[Callable[[], dict], Callable[[dict], None], str]] = {
    "unsorted rows": (
        query_answer,
        lambda a: (_rows2(a), _reversed(a["data"]["rows"])),
        "rows must be sorted",
    ),
    "unsorted selected routes": (
        query_answer,
        lambda a: (_rows2(a), _reversed(a["data"]["selected_routes"])),
        "selected_routes must be sorted",
    ),
    "a window flagged valid with reasons": (
        query_answer,
        lambda a: a["data"]["window"].update(reasons=["GWM_WINDOW_RESTART"]),
        "window.valid must be true exactly",
    ),
    "a window flagged invalid without reasons": (
        query_answer,
        lambda a: a["data"]["window"].update(valid=False),
        "window.valid must be true exactly",
    ),
    "a different window than requested": (
        query_answer,
        lambda a: a["data"]["window"].update(window_end="2026-10-13T10:20:00Z"),
        "window must be the requested window",
    ),
    "counts in an invalid window": (
        invalid_window_answer,
        lambda a: a["data"]["rows"][0]["usage"].update(
            upstream_request_count=0, rejected_attempt_count=0
        ),
        "counts are omitted exactly when the window is invalid",
    ),
    "counts missing in a valid window": (
        query_answer,
        lambda a: a["data"]["rows"][0]["usage"].pop("upstream_request_count"),
        "present together or omitted together",
    ),
    "OBSERVED_USAGE with a zero count": (
        query_answer,
        lambda a: a["data"]["rows"][0]["usage"].update(upstream_request_count=0),
        "OBSERVED_USAGE needs a positive upstream count",
    ),
    "MEASURED_ZERO under unknown coverage": (
        query_answer,
        lambda a: a["data"]["rows"][0]["usage"].update(
            status="MEASURED_ZERO", coverage="UNKNOWN_COVERAGE", upstream_request_count=0
        ),
        "MEASURED_ZERO needs a zero count",
    ),
    "MEASURED_ZERO without configured access": (
        query_answer,
        lambda a: (
            a["data"]["rows"][0]["usage"].update(status="MEASURED_ZERO", upstream_request_count=0),
            a["data"]["rows"][0]["configured_access"].update(
                status="NO_MATCHING_CONFIGURED_ACCESS_FACT"
            ),
        ),
        "MEASURED_ZERO needs established configured access",
    ),
    "an operation id without a RESOLVED Operation": (
        query_answer,
        lambda a: a["data"]["rows"][0]["api"].update(reconciliation="CONFLICT"),
        "operation_id is present exactly when",
    ),
    "a service id without a RESOLVED Service": (
        query_answer,
        lambda a: a["data"]["rows"][0]["application_service"].update(reconciliation="AMBIGUOUS"),
        "service_id is present exactly when",
    ),
    "a contract chain for an unresolved Operation": (
        query_answer,
        lambda a: a["data"]["rows"][0].update(
            api={"reconciliation": "UNRESOLVED", "contract_version_reconciliation": "RESOLVED"}
        ),
        "the contract chain is evaluated only for a RESOLVED Operation",
    ),
    "limitations on SUFFICIENT_FOR_ZERO coverage": (
        query_answer,
        lambda a: a["data"]["rows"][0].update(limitations=["GWM_COUNTER_DECREASED"]),
        "SUFFICIENT_FOR_ZERO coverage has no limitations",
    ),
    "a row on a Route that was not selected": (
        query_answer,
        lambda a: a["data"]["rows"][0]["gateway_route"].update(id=R2),
        "a row's Route must be a selected Route",
    ),
    "a row of another gateway": (
        query_answer,
        lambda a: a["data"]["rows"][0]["gateway_route"].update(gateway_instance_id="gw-other"),
        "a row's Route belongs to the requested gateway",
    ),
    "a row that ignores the consumer filter": (
        query_answer,
        lambda a: a["data"]["request_context"].update(consumer_id=C2),
        "a row's consumer must match the consumer filter",
    ),
    "a summary on a GATEWAY_ROUTE target": (
        route_target_answer,
        lambda a: a["data"].update(
            association_summary={"route_operation": counts(resolved_to_target=1)}
        ),
        "has no association_summary",
    ),
    "no summary on an operation target": (
        query_answer,
        lambda a: a["data"].pop("association_summary"),
        "requires an association_summary",
    ),
    "the wrong summary chain for the target": (
        query_answer,
        lambda a: a["data"].update(
            association_summary={"target_service": counts(resolved_to_target=1)}
        ),
        "chain must match the target kind",
    ),
    "a summary that does not count the selected routes": (
        query_answer,
        lambda a: a["data"]["association_summary"]["route_operation"].update(resolved_to_target=3),
        "resolved_to_target must equal",
    ),
    "a summary with both chains": (
        query_answer,
        lambda a: a["data"]["association_summary"].update(target_service=counts()),
        "exactly one chain",
    ),
    "a page count that is not the row count": (
        query_answer,
        lambda a: a["data"]["page"].update(returned=2),
        "page.returned must equal",
    ),
    "a next_cursor without MORE_ROWS_AVAILABLE": (
        paged_answer,
        lambda a: a.update(outcome="ANSWERED", limitations=[]),
        "limitations must be exactly",
    ),
    "a next_cursor bound to another snapshot": (
        paged_answer,
        lambda a: a["data"]["page"].update(
            next_cursor=encode_cursor(_cursor(snapshot_id=OTHER_SNAPSHOT_ID))
        ),
        "bound to the answer's snapshot",
    ),
    "a next_cursor bound to another query": (
        paged_answer,
        lambda a: a["data"]["page"].update(
            next_cursor=encode_cursor(_cursor(query_digest="0" * 64))
        ),
        "bound to the request context",
    ),
    "unsorted limitation codes": (
        invalid_window_answer,
        lambda a: _reversed(a["limitations"]),
        "limitations must be sorted by code",
    ),
    "a window source that is not listed": (
        query_answer,
        lambda a: a["data"]["window"].update(source_instance_id="urn:other"),
        "the window's source must be listed",
    ),
    "unsorted evidence entries": (
        lambda: evidence_answer((True, True)),
        lambda a: _reversed(a["data"]["entries"]),
        "entries must be sorted",
    ),
    "an evidence payload of another kind than the entry": (
        lambda: evidence_answer((True, True)),
        lambda a: a["data"]["entries"][0].update(kind="QUALIFICATION_LIMITATIONS"),
        "the evidence payload must be of the entry's kind",
    ),
    "a measurement window evidence that is valid with reasons": (
        lambda: evidence_answer((True, True)),
        lambda a: next(e for e in a["data"]["entries"] if e["kind"] == "MEASUREMENT_WINDOW")[
            "evidence"
        ].update(reasons=["GWM_WINDOW_RESTART"]),
        "valid must be true exactly when there are no reasons",
    ),
    "a PARTIAL evidence answer with nothing resolved": (
        lambda: evidence_answer((False, False)),
        lambda a: a.update(outcome="PARTIAL"),
        "outcome must be NOT_ANSWERED",
    ),
    "an ANSWERED evidence answer with an unresolved ref": (
        lambda: evidence_answer((True, False)),
        lambda a: a.update(outcome="ANSWERED"),
        "outcome must be PARTIAL",
    ),
}


@pytest.mark.parametrize("case", sorted(PYDANTIC_ONLY_ANSWER))
def test_cross_field_answer_invariants_are_rejected_by_pydantic(case):
    base, mutate, reason = PYDANTIC_ONLY_ANSWER[case]
    with pytest.raises(ValidationError, match=reason):
        ApiConsumerUsageAnswer.model_validate(_mutated(base, mutate))


# --- Cursor (D8) ---------------------------------------------------------------------------------


def test_a_cursor_round_trips_in_canonical_form():
    cursor = _cursor()
    encoded = encode_cursor(cursor)
    assert decode_cursor(encoded) == cursor
    assert "=" not in encoded
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    assert list(payload) == sorted(payload)
    assert payload["after"] == [C1, R1] and payload["v"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(v=2),
        lambda p: p.update(extra=1),
        lambda p: p.update(after=[C1]),
        lambda p: p.update(after=[R1, C1]),
        lambda p: p.update(query_digest="abc"),
        lambda p: p.update(schema_version="0.6"),
        lambda p: p.update(snapshot_id="latest"),
        lambda p: p.pop("snapshot_id"),
    ],
)
def test_a_malformed_cursor_is_rejected(mutate):
    payload = json.loads(
        base64.urlsafe_b64decode(
            encode_cursor(_cursor()) + "=" * (-len(encode_cursor(_cursor())) % 4)
        )
    )
    mutate(payload)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError):
        decode_cursor(base64.urlsafe_b64encode(raw).decode().rstrip("="))


def test_a_non_canonical_cursor_encoding_is_rejected():
    payload = _cursor().model_dump()
    pretty = json.dumps(payload, indent=1).encode()
    with pytest.raises(ValueError, match="canonical"):
        decode_cursor(base64.urlsafe_b64encode(pretty).decode().rstrip("="))
    with pytest.raises(ValueError):
        decode_cursor("!!!")
    with pytest.raises(ValueError):
        decode_cursor(base64.urlsafe_b64encode(b"[1]").decode().rstrip("="))


# --- Frozen derivations (D9): known answers computed here with the standard library only --------


def _ld(*parts: str) -> bytes:
    return b"".join(len(p.encode()).to_bytes(8, "big") + p.encode() for p in parts)


def test_the_query_context_digest_is_the_sha256_of_the_canonical_context_json():
    ctx = context(consumer_id=C1)
    canonical = (
        '{"consumer_id":"' + C1 + '","environment":"prod","gateway_instance_id":"gw-prod-1",'
        '"target":{"id":"' + OPERATION + '","kind":"API_OPERATION"},'
        '"window_end":"2026-10-13T10:10:00Z","window_start":"2026-10-13T10:00:00Z"}'
    )
    assert digest_of(ctx) == hashlib.sha256(canonical.encode()).hexdigest()
    absent = canonical.replace('"' + C1 + '"', "null", 1)
    assert digest_of(context()) == hashlib.sha256(absent.encode()).hexdigest()


def test_the_query_context_digest_ignores_paging_and_binds_every_context_field():
    base = digest_of(context())
    assert digest_of(context()) == base
    variants = [
        context("APPLICATION_SERVICE"),
        context() | {"gateway_instance_id": "gw-prod-2"},
        context() | {"environment": "staging"},
        context() | {"window_end": "2026-10-13T10:20:00Z"},
        context(consumer_id=C2),
    ]
    assert len({digest_of(v) for v in variants} | {base}) == len(variants) + 1


def test_the_evidence_ref_is_the_sha256_of_the_length_delimited_parts():
    digest = digest_of(context())
    ids = ["measurement-window:owned:b", "measurement-evidence:a"]
    expected = hashlib.sha256(
        _ld(SNAPSHOT_ID, digest, "MEASUREMENT_WINDOW", *sorted(ids))
    ).hexdigest()
    ref = evidence_ref(
        snapshot_id=SNAPSHOT_ID, query_digest=digest, kind="MEASUREMENT_WINDOW", internal_ids=ids
    )
    assert ref == f"api-evidence:{expected}"
    # order and repetition of the supporting ids never change the handle
    assert ref == evidence_ref(
        snapshot_id=SNAPSHOT_ID,
        query_digest=digest,
        kind="MEASUREMENT_WINDOW",
        internal_ids=[*reversed(ids), ids[0]],
    )


def test_the_evidence_ref_binds_snapshot_context_kind_and_ids():
    digest = digest_of(context())
    base = {
        "snapshot_id": SNAPSHOT_ID,
        "query_digest": digest,
        "kind": "CONFIGURED_ACCESS",
        "internal_ids": ["a"],
    }
    refs = {
        evidence_ref(**base),
        evidence_ref(**base | {"snapshot_id": OTHER_SNAPSHOT_ID}),
        evidence_ref(**base | {"query_digest": digest_of(context("APPLICATION_SERVICE"))}),
        evidence_ref(**base | {"kind": "MEASUREMENT_WINDOW"}),
        evidence_ref(**base | {"internal_ids": ["a", "b"]}),
    }
    assert len(refs) == 5
    assert all(ref.startswith("api-evidence:") and len(ref) == 13 + 64 for ref in refs)


# --- Parity and boundaries ----------------------------------------------------------------------


def test_public_enums_mirror_the_internal_i2_values():
    assert {c.value for c in ConfiguredAccessStatus} == {
        qualification.CONFIGURED_ACCESS_ESTABLISHED,
        qualification.NO_MATCHING_CONFIGURED_ACCESS_FACT,
    }
    assert {c.value for c in UsageStatus} == {
        qualification.OBSERVED_USAGE,
        qualification.MEASURED_ZERO,
        qualification.USAGE_UNESTABLISHED,
    }
    assert {c.value for c in Coverage} == {
        qualification.SUFFICIENT_FOR_ZERO,
        qualification.UNKNOWN_COVERAGE,
    }
    assert {c.value for c in Reconciliation} == {
        reconciliation.RESOLVED,
        reconciliation.UNRESOLVED,
        reconciliation.AMBIGUOUS,
        reconciliation.CONFLICT,
    }
    window_reasons = {
        WINDOW_NOT_SETTLED,
        WINDOW_RESTART,
        WINDOW_ORDER_INVALID,
        VERSION_INCOMPATIBLE,
    }
    assert {c.value for c in WindowReasonCode} == window_reasons
    assert {c.value for c in MeasurementCode} == window_reasons | {
        qualification.CONSUMER_LABEL_DISABLED,
        qualification.ROUTE_COVERAGE_ABSENT,
        qualification.ROUTE_PROMETHEUS_DISABLED,
        qualification.UNATTRIBUTED_UPSTREAM,
        gateway_measurement.COUNTER_DECREASED,
        gateway_measurement.SERIES_ONE_BOUNDARY,
    }
    assert {c.value for c in TargetKind} == {
        "APPLICATION_SERVICE",
        "API_OPERATION",
        "GATEWAY_ROUTE",
    }


def test_the_refusal_sets_are_mode_specific():
    assert REFUSAL_CODES_EVIDENCE < REFUSAL_CODES_QUERY
    assert REFUSAL_CODES_QUERY - REFUSAL_CODES_EVIDENCE == {
        ApiUsageLimitationCode.CURSOR_QUERY_MISMATCH
    }
    assert len(REFUSAL_CODES_QUERY) == 5


def test_the_published_schemas_have_no_credential_or_raw_configuration_property():
    names: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            names.update(node.get("properties", {}))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ANSWER_SCHEMA)
    walk(REQUEST_SCHEMA)
    forbidden = {
        "credential", "credentials", "credential_ids", "key", "api_key", "secret", "token",
        "password", "plugins", "plugin_configs", "labels_json", "cypher", "username",
    }  # fmt: skip
    assert names.isdisjoint(forbidden)
    # `labels` is only the aip/service label values of the target-Service evidence, never raw labels
    labels = ANSWER_SCHEMA["$defs"]["TargetServiceReconciliationEvidence"]["properties"]["labels"]
    assert labels["items"]["$ref"].endswith("ServiceLabelStatement")
    assert set(ANSWER_SCHEMA["$defs"]["ServiceLabelStatement"]["properties"]) == {
        "carrier",
        "service_id",
    }
    assert "source_name" in names


def test_the_v05_tool_set_is_unchanged_and_the_new_tool_is_not_registered():
    assert contracts.TOOL_NAMES == (
        "get_architecture_drift",
        "get_evidence",
        "get_service_dependencies",
    )
    assert contracts.ARCHITECTURE_SCHEMA_VERSION == "0.5"
    assert API_USAGE_TOOL_NAME not in contracts.TOOL_NAMES
