"""v0.7.0 I3.3 - the exact same-snapshot evidence mode of `get_api_consumer_usage` (I3 spec §9;
decision record D6, D9, D12.9).

There is no server-side ref history and no lookup by internal id. The caller resubmits the query
context and the snapshot; this module rebuilds the finite map `ref -> sanitized payload` for exactly
that context from the same indexed scope that minted the query refs (`ApiUsageScope`), and resolves
only the requested refs that are in it. A forged ref, a ref of another snapshot and a ref of another
target, gateway, window or consumer filter are all simply absent from the map, and are therefore
indistinguishable. Payloads are the closed allow-lists of D9: no internal id and no reconciliation
basis."""

import json
from collections.abc import Callable, Mapping
from typing import Any

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageEvidenceData,
    ApiConsumerUsageEvidenceRequest,
    ApiUsageLimitationCode,
    ConfiguredAccessEvidence,
    Coverage,
    EvidenceEntry,
    EvidenceKind,
    EvidencePayload,
    EvidenceRoute,
    EvidenceStatus,
    ExtractDigests,
    MeasurementCode,
    MeasurementWindowEvidence,
    OperationMappingStatement,
    QualificationLimitationsEvidence,
    Reconciliation,
    RouteOperationReconciliationEvidence,
    RowConsumer,
    RuleRef,
    ServiceLabelStatement,
    ServiceMappingStatement,
    TargetCarrier,
    TargetServiceReconciliationEvidence,
    WindowReasonCode,
)
from app.architecture_intelligence.api_usage_projection import (
    ApiUsageScope,
    Row,
    limitation,
    open_scope,
    refusal_answer,
)
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.sources.apisix_reconciliation import AIP_SERVICE_LABEL

type Candidates = dict[str, tuple[EvidenceKind, Callable[[], EvidencePayload]]]

_CODE = ApiUsageLimitationCode


def _route(scope: ApiUsageScope, route_id: str) -> EvidenceRoute:
    return EvidenceRoute(id=route_id, source_route_id=scope.routes[route_id]["route_id"])


def _window_payload(scope: ApiUsageScope) -> MeasurementWindowEvidence:
    window = scope.window
    evidence = scope.measurement_evidence[window["evidence_ids"][0]]
    reasons = [WindowReasonCode(code) for code in sorted(window.get("window_reasons") or ())]
    return MeasurementWindowEvidence(
        kind="MEASUREMENT_WINDOW",
        source_instance_id=window["source_instance_id"],
        gateway_instance_id=window["gateway_instance_id"],
        environment=window["environment"],
        window_start=window["window_start"],
        window_end=window["window_end"],
        apisix_version=window["apisix_version"],
        start_settled=window["start_settled"],
        end_settled=window["end_settled"],
        no_restart=window["no_restart"],
        start_stable_seconds=window["start_stable_seconds"],
        end_stable_seconds=window["end_stable_seconds"],
        valid=not reasons,
        reasons=reasons,
        evidence_type=evidence["evidence_type"],
        extract_digests=ExtractDigests(
            start_sha256=evidence["start_sha256"], end_sha256=evidence["end_sha256"]
        ),
    )


def _configured_payload(scope: ApiUsageScope, source: Row) -> ConfiguredAccessEvidence:
    access = scope.configured_access[(source["consumer_id"], source["route_id"])]
    return ConfiguredAccessEvidence(
        kind="CONFIGURED_ACCESS",
        gateway_instance_id=scope.gateway_instance_id,
        environment=scope.environment,
        source_revision=access["source_revision"],
        consumer=RowConsumer(id=source["consumer_id"], source_name=source["consumer"]),
        gateway_route=_route(scope, source["route_id"]),
        rule_kind=access["rule_kind"],
        polarity=access["polarity"],
        scope=access["scope"],
    )


def _route_operation_payload(
    scope: ApiUsageScope, route_id: str
) -> RouteOperationReconciliationEvidence:
    row = scope.route_operation.get(route_id, {})
    source_route = scope.routes[route_id]["route_id"]
    resolved = row.get("operation") == Reconciliation.RESOLVED
    return RouteOperationReconciliationEvidence(
        kind="ROUTE_OPERATION_RECONCILIATION",
        gateway_route=_route(scope, route_id),
        outcome=row.get("operation", Reconciliation.UNRESOLVED),
        operation_id=row.get("operation_id") if resolved else None,
        contract_version_reconciliation=row.get("contract_version") if resolved else None,
        contract_version_id=row.get("contract_version_id") if resolved else None,
        mapping_entries=[
            OperationMappingStatement(operation_id=operation_id)
            for operation_id in sorted(
                {
                    entry["target_id"]
                    for entry in scope.mapping_entries
                    if entry["kind"] == "route_operation" and entry["source_id"] == source_route
                }
            )
        ],
        rule=_rule(scope),
    )


def _rule(scope: ApiUsageScope) -> RuleRef:
    rule = scope.reconciliation_rule
    return RuleRef(rule_id=rule["rule_id"], rule_version=rule["rule_version"])


def _label(row: Row | None) -> str | None:
    """The raw `aip/service` value of a Route or Gateway Service, which I2 keeps as `labels_json`."""
    labels = json.loads(row.get("labels_json") or "{}") if row else {}
    return labels.get(AIP_SERVICE_LABEL)


def _target_service_payload(
    scope: ApiUsageScope, route_id: str
) -> TargetServiceReconciliationEvidence:
    route = scope.routes[route_id]
    row = scope.target_service.get(route_id, {})
    gateway_service = scope.gateway_services.get(route.get("service_id") or "")
    statements = {
        (TargetCarrier.ROUTE, entry["target_id"])
        for entry in scope.mapping_entries
        if entry["kind"] == "target_service_route" and entry["source_id"] == route["route_id"]
    } | {
        (TargetCarrier.GATEWAY_SERVICE, entry["target_id"])
        for entry in scope.mapping_entries
        if entry["kind"] == "target_service_service"
        and entry["source_id"] == route.get("service_id")
    }
    labels = {
        (carrier, value)
        for carrier, value in (
            (TargetCarrier.ROUTE, _label(route)),
            (TargetCarrier.GATEWAY_SERVICE, _label(gateway_service)),
        )
        if value is not None
    }
    resolved = row.get("target") == Reconciliation.RESOLVED
    return TargetServiceReconciliationEvidence(
        kind="TARGET_SERVICE_RECONCILIATION",
        gateway_route=_route(scope, route_id),
        outcome=row.get("target", Reconciliation.UNRESOLVED),
        service_id=row.get("service_id") if resolved else None,
        mapping_entries=[
            ServiceMappingStatement(target=target, service_id=service_id)
            for target, service_id in sorted(statements, key=lambda s: (s[0].value, s[1]))
        ],
        labels=[
            ServiceLabelStatement(carrier=carrier, service_id=service_id)
            for carrier, service_id in sorted(labels, key=lambda s: (s[0].value, s[1]))
        ],
        rule=_rule(scope),
    )


def _limitations_payload(scope: ApiUsageScope, route_id: str) -> QualificationLimitationsEvidence:
    coverage = scope.coverage[route_id]
    return QualificationLimitationsEvidence(
        kind="QUALIFICATION_LIMITATIONS",
        gateway_route=_route(scope, route_id),
        coverage=Coverage(coverage["coverage"]),
        codes=[MeasurementCode(code) for code in sorted(coverage.get("limitations") or ())],
        window_valid=not scope.window.get("window_reasons"),
    )


def evidence_candidates(
    scope: ApiUsageScope, route_ids: list[str], consumer_id: str | None
) -> Candidates:
    """The finite ref map of one query context: the window, each selected Route's reconciliations
    and (if it has limitations) its qualification limitations, and the configured access of every
    selected row. Payloads are built only for the refs that are asked for."""
    candidates: Candidates = {
        scope.window_ref(): (EvidenceKind.MEASUREMENT_WINDOW, lambda: _window_payload(scope))
    }
    for route_id in route_ids:
        candidates[
            scope.ref(
                EvidenceKind.ROUTE_OPERATION_RECONCILIATION, scope.route_operation_ids(route_id)
            )
        ] = (
            EvidenceKind.ROUTE_OPERATION_RECONCILIATION,
            lambda route_id=route_id: _route_operation_payload(scope, route_id),
        )
        candidates[
            scope.ref(
                EvidenceKind.TARGET_SERVICE_RECONCILIATION, scope.target_service_ids(route_id)
            )
        ] = (
            EvidenceKind.TARGET_SERVICE_RECONCILIATION,
            lambda route_id=route_id: _target_service_payload(scope, route_id),
        )
        if scope.coverage[route_id].get("limitations"):
            candidates[
                scope.ref(EvidenceKind.QUALIFICATION_LIMITATIONS, scope.limitation_ids(route_id))
            ] = (
                EvidenceKind.QUALIFICATION_LIMITATIONS,
                lambda route_id=route_id: _limitations_payload(scope, route_id),
            )
    for source in scope.source_rows(route_ids, consumer_id):
        if source["configured_status"] == "CONFIGURED_ACCESS_ESTABLISHED":
            ids = scope.configured_access_ids(source["consumer_id"], source["route_id"])
            candidates[scope.ref(EvidenceKind.CONFIGURED_ACCESS, ids)] = (
                EvidenceKind.CONFIGURED_ACCESS,
                lambda source=source: _configured_payload(scope, source),
            )
    return candidates


def resolve_api_consumer_usage_evidence(
    request: ApiConsumerUsageEvidenceRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> ApiConsumerUsageAnswer:
    """The `mode: "evidence"` answer for the current snapshot `snapshot` whose canonical state is
    `state`. Refusals are decided in D6 order: snapshot, window, target (no cursor step)."""
    opened = open_scope(
        state, request.context(), snapshot=snapshot, asserted_snapshot_ids=[request.snapshot_id]
    )
    if isinstance(opened, ApiUsageLimitationCode):
        return refusal_answer(producer, snapshot, opened, mode="evidence")
    candidates = evidence_candidates(opened, opened.select(request.target), request.consumer_id)
    entries = []
    for ref in request.evidence_refs:
        found = candidates.get(ref)
        if found is None:
            entries.append(EvidenceEntry(ref=ref, status=EvidenceStatus.NOT_RESOLVED))
        else:
            kind, payload = found
            entries.append(
                EvidenceEntry(
                    ref=ref, status=EvidenceStatus.RESOLVED, kind=kind, evidence=payload()
                )
            )
    data = ApiConsumerUsageEvidenceData(request_context=request.context(), entries=entries)
    codes = data.expected_limitation_codes()
    outcome = (
        Outcome.ANSWERED
        if not codes
        else Outcome.PARTIAL
        if data.any_resolved()
        else Outcome.NOT_ANSWERED
    )
    return ApiConsumerUsageAnswer(
        schema_version="0.7",
        producer=producer,
        tool="get_api_consumer_usage",
        mode="evidence",
        outcome=outcome,
        snapshot=snapshot,
        data=data,
        limitations=[limitation(code) for code in sorted(codes, key=lambda c: c.value)],
    )
