"""v0.7.0 I3.2 - the pure projection of one snapshot state into the 0.7 `get_api_consumer_usage`
query answer (I3 spec §§4-9, §11; decision record D3-D9, D12).

It is presentation only and not a second I2 engine: the `qualification_rows` of the requested window
are the row authority, and reconciliation, coverage and counts arrive already decided. This module
performs target selection, bounded enumeration and public enrichment, and mints the D9 evidence refs.
It reads nothing: the caller hands it the `canonical_snapshot_state` it fingerprinted, so the answer
and the snapshot id cannot describe different states.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from app.architecture_intelligence.api_usage_contracts import (
    REFUSAL_CODES_EVIDENCE,
    REFUSAL_CODES_QUERY,
    ApiConsumerUsageAnswer,
    ApiConsumerUsageData,
    ApiConsumerUsageQueryRequest,
    ApiUsageCursor,
    ApiUsageLimitation,
    ApiUsageLimitationCode,
    ApiUsageRequestContext,
    ApiUsageRow,
    ApiUsageTarget,
    ApiUsageWindow,
    AssociationCounts,
    AssociationSummary,
    ConfigurationSource,
    EvidenceKind,
    MeasurementCode,
    MeasurementSource,
    Page,
    Reconciliation,
    RowApi,
    RowConfiguredAccess,
    RowConsumer,
    RowRoute,
    RowService,
    RowUsage,
    RuleRef,
    Rules,
    SelectedRoute,
    TargetKind,
    WindowReasonCode,
    decode_cursor,
    encode_cursor,
    evidence_ref,
    query_context_digest,
    row_key,
)
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef

type Row = Mapping[str, Any]

_CODE = ApiUsageLimitationCode
_RESOLVED = Reconciliation.RESOLVED
_UNRESOLVED = Reconciliation.UNRESOLVED
_OUTCOME_COUNT_FIELD = {
    "UNRESOLVED": "unresolved",
    "AMBIGUOUS": "ambiguous",
    "CONFLICT": "conflict",
}

# D12.3: fixed, deterministic text per code; it never carries a request value.
_MESSAGES = {
    _CODE.SNAPSHOT_NOT_AVAILABLE: "The requested snapshot is not the current snapshot.",
    _CODE.MEASUREMENT_WINDOW_NOT_AVAILABLE: (
        "No accepted measurement window exists for this gateway instance, environment and window."
    ),
    _CODE.UNKNOWN_TARGET: "The target is not known in this snapshot.",
    _CODE.TARGET_NOT_IN_WINDOW_SCOPE: (
        "The target Route belongs to another gateway instance or environment."
    ),
    _CODE.CURSOR_QUERY_MISMATCH: "The cursor was issued for a different request.",
    _CODE.NO_ROUTE_SELECTED: (
        "No Route of this gateway instance, environment and window is resolved to the target."
    ),
    _CODE.MORE_ROWS_AVAILABLE: "More rows follow this page; continue with next_cursor.",
    _CODE.WINDOW_NOT_VALID: "The measurement window is not valid; no usage can be established.",
    _CODE.COVERAGE_UNKNOWN: "At least one selected Route has unknown measurement coverage.",
    _CODE.EVIDENCE_REF_NOT_RESOLVED: (
        "At least one evidence ref is not resolvable for this snapshot and query context."
    ),
}


def limitation(code: ApiUsageLimitationCode) -> ApiUsageLimitation:
    return ApiUsageLimitation(code=code, message=_MESSAGES[code])


def refusal_answer(
    producer: Producer,
    snapshot: SnapshotRef | None,
    code: ApiUsageLimitationCode,
    *,
    mode: Literal["query", "evidence"] = "query",
) -> ApiConsumerUsageAnswer:
    """A D6 refusal: nothing was evaluated, so `data` is null and exactly one refusal code is set.
    The evidence mode has no cursor, so it cannot refuse with `CURSOR_QUERY_MISMATCH`."""
    assert code in (REFUSAL_CODES_QUERY if mode == "query" else REFUSAL_CODES_EVIDENCE)
    return ApiConsumerUsageAnswer(
        schema_version="0.7",
        producer=producer,
        tool="get_api_consumer_usage",
        mode=mode,
        outcome=Outcome.NOT_ANSWERED,
        snapshot=snapshot,
        data=None,
        limitations=[limitation(code)],
    )


def context_digest(context: ApiUsageRequestContext) -> str:
    return query_context_digest(
        target_kind=context.target.kind.value,
        target_id=context.target.id,
        gateway_instance_id=context.gateway_instance_id,
        environment=context.environment,
        window_start=context.window_start,
        window_end=context.window_end,
        consumer_id=context.consumer_id,
    )


def _rows(state: Mapping[str, Any], section: str, name: str) -> list[Row]:
    return list((state.get(section) or {}).get(name) or [])


def _outcome_of(rows: Mapping[str, Row], route_id: str, field: str) -> str:
    """The I2 outcome of one chain. I2 emits a row for every Route of a window's scope; a Route
    without one resolves nothing (I2 reconciliation: no inventory means `UNRESOLVED`)."""
    row = rows.get(route_id)
    return row[field] if row is not None else _UNRESOLVED


@dataclass(frozen=True)
class ApiUsageScope:
    """The facts of one `(gateway_instance_id, environment, window)` of one snapshot, indexed once.
    It also derives the D9 supporting ids of every evidence kind, so the evidence resolver of I3.3
    rebuilds exactly the refs this projection emits."""

    snapshot_id: str
    digest: str
    gateway_instance_id: str
    environment: str
    window: Row
    routes: Mapping[str, Row]
    route_operation: Mapping[str, Row]
    target_service: Mapping[str, Row]
    coverage: Mapping[str, Row]
    qualification_rows: Sequence[Row]
    configured_access: Mapping[tuple[str, str], Row]
    gateway_services: Mapping[str, Row]
    mapping_entries: Sequence[Row]
    limitations: Sequence[Row]
    source_evidence: Sequence[Row]
    versions: Mapping[str, Row]
    measurement_evidence: Mapping[str, Row]
    reconciliation_rule: Row

    @classmethod
    def build(
        cls, state: Mapping[str, Any], *, snapshot_id: str, digest: str, window: Row
    ) -> "ApiUsageScope":
        gateway, environment = window["gateway_instance_id"], window["environment"]

        def in_scope(row: Row) -> bool:
            return (row["gateway_instance_id"], row["environment"]) == (gateway, environment)

        def usage(name: str) -> list[Row]:
            return _rows(state, "api_usage_v1", name)

        def config(name: str) -> list[Row]:
            return _rows(state, "gateway_configuration_v1", name)

        def by_route(rows: Iterable[Row]) -> dict[str, Row]:
            return {row["route_id"]: row for row in rows if row["window_id"] == window["id"]}

        routes = {row["id"]: row for row in config("routes") if in_scope(row)}
        return cls(
            snapshot_id=snapshot_id,
            digest=digest,
            gateway_instance_id=gateway,
            environment=environment,
            window=window,
            routes=routes,
            route_operation=by_route(usage("route_operation")),
            target_service=by_route(usage("target_service")),
            coverage=by_route(usage("coverage")),
            qualification_rows=[
                r for r in usage("qualification_rows") if r["window_id"] == window["id"]
            ],
            configured_access={
                (row["consumer_id"], row["route_id"]): row for row in config("configured_access")
            },
            gateway_services={
                row["service_id"]: row for row in config("services") if in_scope(row)
            },
            mapping_entries=[row for row in usage("mapping_entries") if in_scope(row)],
            limitations=[row for row in usage("limitations") if row["window_id"] == window["id"]],
            source_evidence=[row for row in config("source_evidence") if in_scope(row)],
            versions={row["id"]: row for row in _rows(state, "api_contracts_v1", "versions")},
            measurement_evidence={row["id"]: row for row in usage("evidence")},
            reconciliation_rule=(state.get("api_usage_v1") or {}).get("reconciliation_rule", {}),
        )

    # --- D9 supporting ids (D12.13: each set holds the id that distinguishes its payload) -------

    def _entry_ids(self, kind: str, source_id: str | None) -> list[str]:
        return [
            entry["id"]
            for entry in self.mapping_entries
            if entry["kind"] == kind and entry["source_id"] == source_id
        ]

    def window_ids(self) -> list[str]:
        return [self.window["id"], *self.window.get("evidence_ids", ())]

    def configured_access_ids(self, consumer_id: str, route_id: str) -> list[str]:
        access = self.configured_access[(consumer_id, route_id)]
        return [access["id"], *access.get("evidence_ids", ())]

    def route_operation_ids(self, route_id: str) -> list[str]:
        return [route_id, *self._entry_ids("route_operation", self.routes[route_id]["route_id"])]

    def target_service_ids(self, route_id: str) -> list[str]:
        route = self.routes[route_id]
        ids = [route_id, *self._entry_ids("target_service_route", route["route_id"])]
        service_source_id = route.get("service_id")
        if service_source_id is not None:
            ids.extend(self._entry_ids("target_service_service", service_source_id))
            service = self.gateway_services.get(service_source_id)
            if service is not None:
                ids.append(service["id"])
        return ids

    def limitation_ids(self, route_id: str) -> list[str]:
        source_route = self.routes[route_id]["route_id"]
        carriers = [row["id"] for row in self.limitations if row["route"] == source_route]
        return [route_id, self.window["id"], *carriers]

    def ref(self, kind: EvidenceKind, internal_ids: Iterable[str]) -> str:
        return evidence_ref(
            snapshot_id=self.snapshot_id,
            query_digest=self.digest,
            kind=kind.value,
            internal_ids=internal_ids,
        )

    # --- Selection (I3 §5) ----------------------------------------------------------------------

    def select(self, target: ApiUsageTarget) -> list[str]:
        """The ids of the Routes the target selects, sorted. Only I2-established associations
        attach a Route to an Operation or a Service."""
        if target.kind is TargetKind.GATEWAY_ROUTE:
            return [target.id] if target.id in self.routes else []
        table, outcome_field, key = (
            (self.route_operation, "operation", "operation_id")
            if target.kind is TargetKind.API_OPERATION
            else (self.target_service, "target", "service_id")
        )
        return sorted(
            route_id
            for route_id in self.routes
            if _outcome_of(table, route_id, outcome_field) == _RESOLVED
            and table[route_id].get(key) == target.id
        )

    def summary(self, target: ApiUsageTarget) -> AssociationSummary | None:
        """I3 §5.2/§5.3: every Route of the scope by the outcome of the target kind's chain."""
        if target.kind is TargetKind.GATEWAY_ROUTE:
            return None
        table, outcome_field, key = (
            (self.route_operation, "operation", "operation_id")
            if target.kind is TargetKind.API_OPERATION
            else (self.target_service, "target", "service_id")
        )
        counts = dict.fromkeys(AssociationCounts.model_fields, 0)
        for route_id in self.routes:
            outcome = _outcome_of(table, route_id, outcome_field)
            if outcome == _RESOLVED:
                counts[
                    "resolved_to_target"
                    if table[route_id].get(key) == target.id
                    else "resolved_elsewhere"
                ] += 1
            else:
                counts[_OUTCOME_COUNT_FIELD[outcome]] += 1
        chain = AssociationCounts(**counts)
        return (
            AssociationSummary(route_operation=chain)
            if target.kind is TargetKind.API_OPERATION
            else AssociationSummary(target_service=chain)
        )

    def source_rows(self, route_ids: Iterable[str], consumer_id: str | None) -> list[Row]:
        """The `qualification_rows` of the window on the given Routes, for the consumer filter if
        any. The row authority; nothing is derived."""
        wanted = set(route_ids)
        return [
            row
            for row in self.qualification_rows
            if row["route_id"] in wanted and consumer_id in (None, row["consumer_id"])
        ]

    # --- Public enrichment ----------------------------------------------------------------------

    def window_ref(self) -> str:
        return self.ref(EvidenceKind.MEASUREMENT_WINDOW, self.window_ids())

    def selected_route(self, route_id: str) -> SelectedRoute:
        coverage = self.coverage.get(route_id)
        if coverage is None:
            raise ValueError("I2 invariant violated: a Route of the window has no coverage row")
        limitations = [MeasurementCode(code) for code in sorted(coverage.get("limitations") or ())]
        return SelectedRoute(
            route_id=route_id,
            source_route_id=self.routes[route_id]["route_id"],
            coverage=coverage["coverage"],
            limitations=limitations,
            evidence_refs=(
                [self.ref(EvidenceKind.QUALIFICATION_LIMITATIONS, self.limitation_ids(route_id))]
                if limitations
                else []
            ),
        )

    def _api(self, route_id: str) -> RowApi:
        row = self.route_operation.get(route_id)
        if row is None or row["operation"] != _RESOLVED:
            return RowApi(reconciliation=row["operation"] if row else _UNRESOLVED)
        version_id = row.get("contract_version_id")
        version = self.versions.get(version_id) if version_id is not None else None
        return RowApi(
            reconciliation=_RESOLVED,
            operation_id=row["operation_id"],
            contract_version_reconciliation=row["contract_version"],
            contract_version_id=version_id,
            contract_id=version["contract_id"] if version is not None else None,
        )

    def _service(self, route_id: str) -> RowService:
        row = self.target_service.get(route_id)
        return RowService(
            reconciliation=row["target"] if row else _UNRESOLVED,
            service_id=row.get("service_id") if row else None,
        )

    def row(self, source: Row, selected: SelectedRoute) -> ApiUsageRow:
        route_id, consumer_id = source["route_id"], source["consumer_id"]
        established = source["configured_status"] == "CONFIGURED_ACCESS_ESTABLISHED"
        refs = [
            self.window_ref(),
            self.ref(
                EvidenceKind.ROUTE_OPERATION_RECONCILIATION, self.route_operation_ids(route_id)
            ),
            self.ref(EvidenceKind.TARGET_SERVICE_RECONCILIATION, self.target_service_ids(route_id)),
            *selected.evidence_refs,
        ]
        if established:
            refs.append(
                self.ref(
                    EvidenceKind.CONFIGURED_ACCESS,
                    self.configured_access_ids(consumer_id, route_id),
                )
            )
        return ApiUsageRow(
            consumer=RowConsumer(id=consumer_id, source_name=source["consumer"]),
            gateway_route=RowRoute(
                id=route_id,
                gateway_instance_id=self.gateway_instance_id,
                source_route_id=source["route"],
            ),
            api=self._api(route_id),
            application_service=self._service(route_id),
            configured_access=RowConfiguredAccess(status=source["configured_status"]),
            usage=RowUsage(
                status=source["usage_status"],
                coverage=source["coverage"],
                upstream_request_count=source.get("upstream_request_count"),
                rejected_attempt_count=source.get("rejected_attempt_count"),
                interaction_id=source.get("interaction_id"),
            ),
            evidence_refs=sorted(set(refs)),
            limitations=[MeasurementCode(code) for code in sorted(source.get("limitations") or ())],
        )


def _find_window(state: Mapping[str, Any], context: ApiUsageRequestContext) -> Row | None:
    wanted = (
        context.gateway_instance_id,
        context.environment,
        context.window_start,
        context.window_end,
    )
    for window in _rows(state, "api_usage_v1", "windows"):
        key = (
            window["gateway_instance_id"],
            window["environment"],
            window["window_start"],
            window["window_end"],
        )
        if key == wanted:
            return window
    return None


def _target_refusal(
    state: Mapping[str, Any], scope: ApiUsageScope, target: ApiUsageTarget
) -> ApiUsageLimitationCode | None:
    """`UNKNOWN_TARGET` when the id names nothing in the snapshot; `TARGET_NOT_IN_WINDOW_SCOPE` when
    a Route exists only in another gateway instance or environment."""
    if target.kind is TargetKind.GATEWAY_ROUTE:
        if target.id in scope.routes:
            return None
        known = any(
            row["id"] == target.id for row in _rows(state, "gateway_configuration_v1", "routes")
        )
        return _CODE.TARGET_NOT_IN_WINDOW_SCOPE if known else _CODE.UNKNOWN_TARGET
    section = "operations" if target.kind is TargetKind.API_OPERATION else "services"
    known = any(row["id"] == target.id for row in state.get(section) or ())
    return None if known else _CODE.UNKNOWN_TARGET


def open_scope(
    state: Mapping[str, Any],
    context: ApiUsageRequestContext,
    *,
    snapshot: SnapshotRef,
    asserted_snapshot_ids: Iterable[str | None],
) -> ApiUsageScope | ApiUsageLimitationCode:
    """The refusal preamble shared by both modes, in D6 order: snapshot, window, target. Returns the
    indexed scope of the requested window, or the one refusal code."""
    if set(asserted_snapshot_ids) - {None, snapshot.snapshot_id}:
        return _CODE.SNAPSHOT_NOT_AVAILABLE
    window = _find_window(state, context)
    if window is None:
        return _CODE.MEASUREMENT_WINDOW_NOT_AVAILABLE
    scope = ApiUsageScope.build(
        state, snapshot_id=snapshot.snapshot_id, digest=context_digest(context), window=window
    )
    return _target_refusal(state, scope, context.target) or scope


def _window_block(scope: ApiUsageScope) -> ApiUsageWindow:
    window = scope.window
    reasons = [WindowReasonCode(code) for code in sorted(window.get("window_reasons") or ())]
    return ApiUsageWindow(
        window_start=window["window_start"],
        window_end=window["window_end"],
        source_instance_id=window["source_instance_id"],
        valid=not reasons,
        reasons=reasons,
        evidence_refs=[scope.window_ref()],
    )


def _rule(state: Mapping[str, Any], name: str) -> RuleRef:
    rule = (state.get("api_usage_v1") or {})[name]
    return RuleRef(rule_id=rule["rule_id"], rule_version=rule["rule_version"])


def _page(
    rows: list[ApiUsageRow], request: ApiConsumerUsageQueryRequest, cursor: ApiUsageCursor | None
) -> tuple[list[ApiUsageRow], bool]:
    """D8: the rows strictly after the cursor position, at most `limit`, and whether rows remain."""
    after = tuple(cursor.after) if cursor is not None else None
    remaining = [row for row in rows if after is None or row_key(row) > after]
    return remaining[: request.limit], len(remaining) > request.limit


def project_api_consumer_usage(
    request: ApiConsumerUsageQueryRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> ApiConsumerUsageAnswer:
    """The `mode: "query"` answer for the current snapshot `snapshot` whose canonical state is
    `state`. Refusals are decided in D6 order: snapshot, window, target, cursor."""
    cursor = decode_cursor(request.cursor) if request.cursor is not None else None
    opened = open_scope(
        state,
        request.context(),
        snapshot=snapshot,
        asserted_snapshot_ids=[request.snapshot_id, cursor.snapshot_id if cursor else None],
    )
    if isinstance(opened, ApiUsageLimitationCode):
        return refusal_answer(producer, snapshot, opened)
    scope, digest, window = opened, opened.digest, opened.window
    if cursor is not None and cursor.query_digest != digest:
        return refusal_answer(producer, snapshot, _CODE.CURSOR_QUERY_MISMATCH)

    selected = [scope.selected_route(route_id) for route_id in scope.select(request.target)]
    by_route = {route.route_id: route for route in selected}
    rows = sorted(
        (
            scope.row(source, by_route[source["route_id"]])
            for source in scope.source_rows(by_route, request.consumer_id)
        ),
        key=row_key,
    )
    page_rows, more = _page(rows, request, cursor)
    next_cursor = (
        encode_cursor(
            ApiUsageCursor(
                v=1,
                after=row_key(page_rows[-1]),
                query_digest=digest,
                schema_version="0.7",
                snapshot_id=snapshot.snapshot_id,
            )
        )
        if more
        else None
    )
    data = ApiConsumerUsageData(
        request_context=request.context(),
        window=_window_block(scope),
        rules=Rules(
            reconciliation=_rule(state, "reconciliation_rule"),
            qualification=_rule(state, "qualification_rule"),
        ),
        association_summary=scope.summary(request.target),
        selected_routes=selected,
        configuration_sources=sorted(
            (
                ConfigurationSource(
                    gateway_instance_id=row["gateway_instance_id"],
                    environment=row["environment"],
                    source_revision=row["source_revision"],
                )
                for row in scope.source_evidence
            ),
            key=lambda s: (s.gateway_instance_id, s.environment, s.source_revision),
        ),
        measurement_sources=[
            MeasurementSource(
                source_instance_id=window["source_instance_id"],
                window_start=window["window_start"],
                window_end=window["window_end"],
                apisix_version=window["apisix_version"],
            )
        ],
        rows=page_rows,
        page=Page(limit=request.limit, returned=len(page_rows), next_cursor=next_cursor),
    )
    codes = data.expected_limitation_codes()
    outcome = (
        Outcome.NOT_ANSWERED
        if _CODE.NO_ROUTE_SELECTED in codes
        else Outcome.PARTIAL
        if codes
        else Outcome.ANSWERED
    )
    return ApiConsumerUsageAnswer(
        schema_version="0.7",
        producer=producer,
        tool="get_api_consumer_usage",
        mode="query",
        outcome=outcome,
        snapshot=snapshot,
        data=data,
        limitations=[limitation(code) for code in sorted(codes, key=lambda c: c.value)],
    )
