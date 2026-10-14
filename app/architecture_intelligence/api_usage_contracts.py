"""v0.7.0 I3.1b - the public API-consumer-usage contract (schema 0.7) for `get_api_consumer_usage`
(I3 decision record D1-D12, docs/specifications/0.7.0/i3-decision-record.md).

This module defines only the data contract: the two request modes, the `ApiConsumerUsageAnswer`
envelope and its payloads, the cursor codec and the two frozen pure derivations (the query-context
digest and the evidence ref). It contains no service logic, no Neo4j access and no projection, and
nothing here is registered with REST or MCP (I3.3). It is separate from the closed 0.5
`ArchitectureAnswer` and the 0.6 `LocalityAnswer` (D2): it reuses `Producer`, `SnapshotRef` and
`Outcome`, never their tool, claim or limitation enums. Like `locality_contracts.py`, the public
enums mirror the internal I2 values by value, not by import, so internal churn cannot silently
change the published schema (`tests/unit/test_api_usage_contracts.py` pins the parity).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from pydantic.config import JsonDict

from app.architecture_intelligence.contracts import (
    ENVIRONMENT_PATTERN,
    SNAPSHOT_ID_PATTERN,
    Outcome,
    Producer,
    SnapshotRef,
)
from app.common.encoding import length_delimited, sha256_hex, utf8

_SHA256_HEX = r"[0-9a-f]{64}"
# Canonical ids, names and opaque tokens: non-empty, no whitespace or control characters.
_OPAQUE_ID_PATTERN = r"^[^\s\x00-\x1f\x7f]+$"
_TIMESTAMP_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"
_SERVICE_ID_PATTERN = r"^service:[^\s\x00-\x1f\x7f]*$"
_OPERATION_ID_PATTERN = r"^operation:[^\s\x00-\x1f\x7f]*$"
_CONSUMER_ID_PATTERN = rf"^gateway-consumer:owned:{_SHA256_HEX}$"
_ROUTE_ID_PATTERN = rf"^gateway-route:owned:{_SHA256_HEX}$"
_INTERACTION_ID_PATTERN = rf"^observed-consumer-interaction:owned:{_SHA256_HEX}$"
_EVIDENCE_REF_PATTERN = rf"^api-evidence:{_SHA256_HEX}$"
_DIGEST_PATTERN = rf"^{_SHA256_HEX}$"
_CURSOR_PATTERN = r"^[A-Za-z0-9_-]+$"

ApiUsageSchemaVersion = Literal["0.7"]
API_USAGE_SCHEMA_VERSION: ApiUsageSchemaVersion = get_args(ApiUsageSchemaVersion)[0]
ApiUsageToolName = Literal["get_api_consumer_usage"]
API_USAGE_TOOL_NAME: ApiUsageToolName = get_args(ApiUsageToolName)[0]
ApiUsageMode = Literal["query", "evidence"]

# D3 bounds.
DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 200
MAX_EVIDENCE_REFS = 20
CURSOR_FORMAT_VERSION = 1
_MAX_CURSOR_LENGTH = 2048
_MAX_TARGET_ID_LENGTH = 512
_MAX_GATEWAY_INSTANCE_ID_LENGTH = 256
_MAX_ENVIRONMENT_LENGTH = 128

EVIDENCE_REF_PREFIX = "api-evidence:"


# --- Enums (by value; D5, D6, D9, I2 handoff) ---------------------------------------------------


class TargetKind(StrEnum):
    APPLICATION_SERVICE = "APPLICATION_SERVICE"
    API_OPERATION = "API_OPERATION"
    GATEWAY_ROUTE = "GATEWAY_ROUTE"


class ConfiguredAccessStatus(StrEnum):
    CONFIGURED_ACCESS_ESTABLISHED = "CONFIGURED_ACCESS_ESTABLISHED"
    NO_MATCHING_CONFIGURED_ACCESS_FACT = "NO_MATCHING_CONFIGURED_ACCESS_FACT"


class UsageStatus(StrEnum):
    OBSERVED_USAGE = "OBSERVED_USAGE"
    MEASURED_ZERO = "MEASURED_ZERO"
    USAGE_UNESTABLISHED = "USAGE_UNESTABLISHED"


class Coverage(StrEnum):
    SUFFICIENT_FOR_ZERO = "SUFFICIENT_FOR_ZERO"
    UNKNOWN_COVERAGE = "UNKNOWN_COVERAGE"


class Reconciliation(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"


class WindowReasonCode(StrEnum):
    """The I2 window reasons (contract §3)."""

    GWM_WINDOW_NOT_SETTLED = "GWM_WINDOW_NOT_SETTLED"
    GWM_WINDOW_RESTART = "GWM_WINDOW_RESTART"
    GWM_WINDOW_ORDER_INVALID = "GWM_WINDOW_ORDER_INVALID"
    GWM_VERSION_INCOMPATIBLE = "GWM_VERSION_INCOMPATIBLE"


class MeasurementCode(StrEnum):
    """Every I2 limitation code a Route or row can carry: the window reasons and the route-level
    coverage codes (contract §7)."""

    GWM_WINDOW_NOT_SETTLED = "GWM_WINDOW_NOT_SETTLED"
    GWM_WINDOW_RESTART = "GWM_WINDOW_RESTART"
    GWM_WINDOW_ORDER_INVALID = "GWM_WINDOW_ORDER_INVALID"
    GWM_VERSION_INCOMPATIBLE = "GWM_VERSION_INCOMPATIBLE"
    GWM_CONSUMER_LABEL_DISABLED = "GWM_CONSUMER_LABEL_DISABLED"
    GWM_ROUTE_COVERAGE_ABSENT = "GWM_ROUTE_COVERAGE_ABSENT"
    GWM_ROUTE_PROMETHEUS_DISABLED = "GWM_ROUTE_PROMETHEUS_DISABLED"
    GWM_COUNTER_DECREASED = "GWM_COUNTER_DECREASED"
    GWM_SERIES_ONE_BOUNDARY = "GWM_SERIES_ONE_BOUNDARY"
    GWM_UNATTRIBUTED_UPSTREAM = "GWM_UNATTRIBUTED_UPSTREAM"


class ApiUsageLimitationCode(StrEnum):
    """D6: the closed 0.7 envelope codes, separate from the 0.5 `LimitationCode` and the 0.6
    locality enum. The first five are refusal codes."""

    SNAPSHOT_NOT_AVAILABLE = "SNAPSHOT_NOT_AVAILABLE"
    MEASUREMENT_WINDOW_NOT_AVAILABLE = "MEASUREMENT_WINDOW_NOT_AVAILABLE"
    UNKNOWN_TARGET = "UNKNOWN_TARGET"
    TARGET_NOT_IN_WINDOW_SCOPE = "TARGET_NOT_IN_WINDOW_SCOPE"
    CURSOR_QUERY_MISMATCH = "CURSOR_QUERY_MISMATCH"
    NO_ROUTE_SELECTED = "NO_ROUTE_SELECTED"
    MORE_ROWS_AVAILABLE = "MORE_ROWS_AVAILABLE"
    WINDOW_NOT_VALID = "WINDOW_NOT_VALID"
    COVERAGE_UNKNOWN = "COVERAGE_UNKNOWN"
    EVIDENCE_REF_NOT_RESOLVED = "EVIDENCE_REF_NOT_RESOLVED"


# D6: a refusal evaluated nothing, so its answer carries `data: null` and exactly one of these. The
# evidence mode has no cursor, so `CURSOR_QUERY_MISMATCH` is query/continuation-only.
_CODE = ApiUsageLimitationCode
REFUSAL_CODES_EVIDENCE = frozenset(
    {
        _CODE.SNAPSHOT_NOT_AVAILABLE,
        _CODE.MEASUREMENT_WINDOW_NOT_AVAILABLE,
        _CODE.UNKNOWN_TARGET,
        _CODE.TARGET_NOT_IN_WINDOW_SCOPE,
    }
)
REFUSAL_CODES_QUERY = REFUSAL_CODES_EVIDENCE | {_CODE.CURSOR_QUERY_MISMATCH}


class EvidenceKind(StrEnum):
    CONFIGURED_ACCESS = "CONFIGURED_ACCESS"
    MEASUREMENT_WINDOW = "MEASUREMENT_WINDOW"
    ROUTE_OPERATION_RECONCILIATION = "ROUTE_OPERATION_RECONCILIATION"
    TARGET_SERVICE_RECONCILIATION = "TARGET_SERVICE_RECONCILIATION"
    QUALIFICATION_LIMITATIONS = "QUALIFICATION_LIMITATIONS"


class EvidenceStatus(StrEnum):
    RESOLVED = "RESOLVED"
    NOT_RESOLVED = "NOT_RESOLVED"


class TargetCarrier(StrEnum):
    ROUTE = "ROUTE"
    GATEWAY_SERVICE = "GATEWAY_SERVICE"


# --- Shared helpers -----------------------------------------------------------------------------

_UNIQUE: JsonDict = {"uniqueItems": True}

_Opaque = Annotated[str, Field(pattern=_OPAQUE_ID_PATTERN)]
_Timestamp = Annotated[str, Field(pattern=_TIMESTAMP_PATTERN)]
_ConsumerId = Annotated[str, Field(pattern=_CONSUMER_ID_PATTERN)]
_RouteId = Annotated[str, Field(pattern=_ROUTE_ID_PATTERN)]
_EvidenceRef = Annotated[str, Field(pattern=_EVIDENCE_REF_PATTERN)]
_GatewayInstanceId = Annotated[
    str,
    Field(min_length=1, max_length=_MAX_GATEWAY_INSTANCE_ID_LENGTH, pattern=ENVIRONMENT_PATTERN),
]
_Environment = Annotated[
    str, Field(min_length=1, max_length=_MAX_ENVIRONMENT_LENGTH, pattern=ENVIRONMENT_PATTERN)
]


def _check_sorted_unique[T](values: Sequence[T], key: Any, what: str) -> None:
    keys = [key(value) for value in values]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{what} must be sorted and duplicate-free")


def _check_sorted_unique_strings(values: Sequence[Any], what: str) -> None:
    _check_sorted_unique(values, lambda value: str(value), what)


def _closed(**extra: Any) -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid", **extra)


# --- Target and request context (D3) ------------------------------------------------------------

_TARGET_ID_PATTERNS = {
    TargetKind.APPLICATION_SERVICE: _SERVICE_ID_PATTERN,
    TargetKind.API_OPERATION: _OPERATION_ID_PATTERN,
    TargetKind.GATEWAY_ROUTE: _ROUTE_ID_PATTERN,
}


def _target_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `ApiUsageTarget._check_id` as far as JSON Schema can express it."""
    schema["allOf"] = [
        {
            "if": {"properties": {"kind": {"const": kind.value}}, "required": ["kind"]},
            "then": {"properties": {"id": {"pattern": pattern}}},
        }
        for kind, pattern in _TARGET_ID_PATTERNS.items()
    ]


class ApiUsageTarget(BaseModel):
    """D3: exactly one exact target. The id pattern depends on the kind; never a display name, path
    or host."""

    model_config = _closed(json_schema_extra=_target_schema_extra)

    kind: TargetKind
    id: str = Field(min_length=1, max_length=_MAX_TARGET_ID_LENGTH)

    @model_validator(mode="after")
    def _check_id(self) -> ApiUsageTarget:
        if re.fullmatch(_TARGET_ID_PATTERNS[self.kind], self.id) is None:
            raise ValueError(f"id is not a {self.kind.value} id")
        return self


class ApiUsageRequestContext(BaseModel):
    """D4: the normalized query context (without `limit`, `cursor` and `snapshot_id`)."""

    model_config = _closed()

    target: ApiUsageTarget
    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    window_start: _Timestamp
    window_end: _Timestamp
    consumer_id: _ConsumerId | None = None


# --- Cursor (D8) --------------------------------------------------------------------------------


class ApiUsageCursor(BaseModel):
    """The decoded D8 cursor. It is opaque to clients and carries no signature (D8 integrity); this
    model only checks its structure."""

    model_config = _closed()

    v: Literal[1]
    after: tuple[_ConsumerId, _RouteId]
    query_digest: str = Field(pattern=_DIGEST_PATTERN)
    schema_version: ApiUsageSchemaVersion
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)


def encode_cursor(cursor: ApiUsageCursor) -> str:
    """Unpadded base64url of the canonical JSON (sorted keys, no whitespace)."""
    payload = json.dumps(cursor.model_dump(), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> ApiUsageCursor:
    """Raises `ValueError` for anything that is not a well-formed D8 cursor."""
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode())
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is not a well-formed API usage cursor") from error
    # A non-object payload fails here too (pydantic's ValidationError is a ValueError).
    cursor = ApiUsageCursor.model_validate(payload)
    if encode_cursor(cursor) != value:
        raise ValueError("cursor is not in canonical form")
    return cursor


def _check_cursor(value: str | None) -> str | None:
    if value is not None:
        decode_cursor(value)
    return value


# --- Frozen derivations (D9) --------------------------------------------------------------------


def query_context_digest(
    *,
    target_kind: str,
    target_id: str,
    gateway_instance_id: str,
    environment: str,
    window_start: str,
    window_end: str,
    consumer_id: str | None,
) -> str:
    """D9 `normalized_query_context_digest`: lowercase hex SHA-256 of the canonical JSON (sorted
    keys, compact, UTF-8, `ensure_ascii` false) of the normalized context. Page position, `limit` and
    `snapshot_id` are not part of it. The D8 cursor binds the same digest."""
    document = {
        "consumer_id": consumer_id,
        "environment": environment,
        "gateway_instance_id": gateway_instance_id,
        "target": {"id": target_id, "kind": target_kind},
        "window_end": window_end,
        "window_start": window_start,
    }
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_ref(
    *, snapshot_id: str, query_digest: str, kind: str, internal_ids: Iterable[str]
) -> str:
    """D9: `api-evidence:<sha256 hex of ld(snapshot_id, query_digest, kind, *sorted ids)>`. The
    supporting ids are distinct and sorted bytewise; they are never exposed by the answer."""
    ids = sorted(set(internal_ids))
    parts = (snapshot_id, query_digest, kind, *ids)
    return f"{EVIDENCE_REF_PREFIX}{sha256_hex(length_delimited(*(utf8(part) for part in parts)))}"


# --- Requests (D3) ------------------------------------------------------------------------------


class ApiConsumerUsageQueryRequest(BaseModel):
    """`mode: "query"` (D3). A reversed window is accepted: an I2 window with `window_start >=
    window_end` is accepted-but-invalid and must stay addressable."""

    model_config = _closed()

    mode: Literal["query"]
    target: ApiUsageTarget
    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    window_start: _Timestamp
    window_end: _Timestamp
    consumer_id: _ConsumerId | None = None
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    cursor: str | None = Field(
        default=None, min_length=1, max_length=_MAX_CURSOR_LENGTH, pattern=_CURSOR_PATTERN
    )
    snapshot_id: str | None = Field(default=None, pattern=SNAPSHOT_ID_PATTERN)

    @field_validator("cursor")
    @classmethod
    def _check_cursor_structure(cls, value: str | None) -> str | None:
        return _check_cursor(value)

    @model_validator(mode="after")
    def _check_request(self) -> ApiConsumerUsageQueryRequest:
        if self.cursor is not None and self.snapshot_id is None:
            raise ValueError("a cursor requires snapshot_id")
        return self

    def context(self) -> ApiUsageRequestContext:
        return ApiUsageRequestContext(
            target=self.target,
            gateway_instance_id=self.gateway_instance_id,
            environment=self.environment,
            window_start=self.window_start,
            window_end=self.window_end,
            consumer_id=self.consumer_id,
        )


class ApiConsumerUsageEvidenceRequest(BaseModel):
    """`mode: "evidence"` (D3, D9): the query context is resubmitted so the service can rebuild the
    ref map at the exact snapshot."""

    model_config = _closed()

    mode: Literal["evidence"]
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)
    target: ApiUsageTarget
    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    window_start: _Timestamp
    window_end: _Timestamp
    consumer_id: _ConsumerId | None = None
    evidence_refs: list[_EvidenceRef] = Field(
        min_length=1, max_length=MAX_EVIDENCE_REFS, json_schema_extra=_UNIQUE
    )

    @field_validator("evidence_refs")
    @classmethod
    def _check_refs(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "evidence_refs")
        return value

    def context(self) -> ApiUsageRequestContext:
        return ApiUsageRequestContext(
            target=self.target,
            gateway_instance_id=self.gateway_instance_id,
            environment=self.environment,
            window_start=self.window_start,
            window_end=self.window_end,
            consumer_id=self.consumer_id,
        )


class ApiConsumerUsageRequest(
    RootModel[
        Annotated[
            ApiConsumerUsageQueryRequest | ApiConsumerUsageEvidenceRequest,
            Field(discriminator="mode"),
        ]
    ]
):
    """The single MCP `request` argument (D1): one of the two modes, discriminated on `mode`."""

    model_config = ConfigDict(frozen=True, title="ApiConsumerUsageRequest")


# --- Answer building blocks (D4) ----------------------------------------------------------------


class RuleRef(BaseModel):
    model_config = _closed()

    rule_id: _Opaque
    rule_version: _Opaque


class Rules(BaseModel):
    model_config = _closed()

    reconciliation: RuleRef
    qualification: RuleRef


class ApiUsageWindow(BaseModel):
    """D4: the I2 window the answer is about. `valid` is true iff there are no reasons."""

    model_config = _closed()

    window_start: _Timestamp
    window_end: _Timestamp
    source_instance_id: _Opaque
    valid: bool
    reasons: list[WindowReasonCode] = Field(json_schema_extra=_UNIQUE)
    evidence_refs: list[_EvidenceRef] = Field(min_length=1, json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_window(self) -> ApiUsageWindow:
        _check_sorted_unique_strings(self.reasons, "reasons")
        _check_sorted_unique_strings(self.evidence_refs, "evidence_refs")
        if self.valid != (not self.reasons):
            raise ValueError("window.valid must be true exactly when there are no reasons")
        return self


class AssociationCounts(BaseModel):
    """I3 §5.2/§5.3: all GatewayRoutes of the selected scope by the I2 outcome of one chain."""

    model_config = _closed()

    resolved_to_target: int = Field(ge=0)
    resolved_elsewhere: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    ambiguous: int = Field(ge=0)
    conflict: int = Field(ge=0)


class AssociationSummary(BaseModel):
    """Exactly one chain: `route_operation` for an `API_OPERATION` target, `target_service` for an
    `APPLICATION_SERVICE` target. Informational only."""

    model_config = _closed()

    route_operation: AssociationCounts | None = None
    target_service: AssociationCounts | None = None

    @model_validator(mode="after")
    def _check_summary(self) -> AssociationSummary:
        if (self.route_operation is None) == (self.target_service is None):
            raise ValueError("an association summary carries exactly one chain")
        return self


class SelectedRoute(BaseModel):
    """D4: a Route selected by the target, emitted independently of `rows`."""

    model_config = _closed()

    route_id: _RouteId
    source_route_id: _Opaque
    coverage: Coverage
    limitations: list[MeasurementCode] = Field(json_schema_extra=_UNIQUE)
    evidence_refs: list[_EvidenceRef] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_route(self) -> SelectedRoute:
        _check_sorted_unique_strings(self.limitations, "limitations")
        _check_sorted_unique_strings(self.evidence_refs, "evidence_refs")
        if (self.coverage is Coverage.SUFFICIENT_FOR_ZERO) != (not self.limitations):
            raise ValueError("SUFFICIENT_FOR_ZERO coverage has no limitations, UNKNOWN has some")
        if bool(self.evidence_refs) != bool(self.limitations):
            raise ValueError("a Route has evidence refs exactly when it has limitations")
        return self


class ConfigurationSource(BaseModel):
    model_config = _closed()

    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    source_revision: _Opaque


class MeasurementSource(BaseModel):
    model_config = _closed()

    source_instance_id: _Opaque
    window_start: _Timestamp
    window_end: _Timestamp
    apisix_version: _Opaque


class RowConsumer(BaseModel):
    """D7: `source_name` is the APISIX Consumer username, a source-qualified identity."""

    model_config = _closed()

    id: _ConsumerId
    source_name: _Opaque


class RowRoute(BaseModel):
    model_config = _closed()

    id: _RouteId
    gateway_instance_id: _GatewayInstanceId
    source_route_id: _Opaque


class RowApi(BaseModel):
    """The Route -> Operation -> contract-version chain, with the I2 outcomes unrenamed."""

    model_config = _closed()

    reconciliation: Reconciliation
    operation_id: str | None = Field(default=None, pattern=_OPERATION_ID_PATTERN)
    contract_version_reconciliation: Reconciliation | None = None
    contract_version_id: _Opaque | None = None
    contract_id: _Opaque | None = None

    @model_validator(mode="after")
    def _check_api(self) -> RowApi:
        resolved = self.reconciliation is Reconciliation.RESOLVED
        if (self.operation_id is not None) != resolved:
            raise ValueError("operation_id is present exactly when the Operation is RESOLVED")
        if (self.contract_version_reconciliation is not None) != resolved:
            raise ValueError("the contract chain is evaluated only for a RESOLVED Operation")
        version_resolved = self.contract_version_reconciliation is Reconciliation.RESOLVED
        if (self.contract_version_id is not None) != version_resolved:
            raise ValueError("contract_version_id is present exactly when the version is RESOLVED")
        if self.contract_id is not None and self.contract_version_id is None:
            raise ValueError("contract_id requires contract_version_id")
        return self


class RowService(BaseModel):
    model_config = _closed()

    reconciliation: Reconciliation
    service_id: str | None = Field(default=None, pattern=_SERVICE_ID_PATTERN)

    @model_validator(mode="after")
    def _check_service(self) -> RowService:
        if (self.service_id is not None) != (self.reconciliation is Reconciliation.RESOLVED):
            raise ValueError("service_id is present exactly when the Service is RESOLVED")
        return self


class RowConfiguredAccess(BaseModel):
    model_config = _closed()

    status: ConfiguredAccessStatus


class RowUsage(BaseModel):
    """The usage proposition. The counts are omitted, never zero, when I2 could not establish them
    (an invalid window); the interaction id is an opaque row-local value (D4)."""

    model_config = _closed()

    status: UsageStatus
    coverage: Coverage
    upstream_request_count: int | None = Field(default=None, ge=0)
    rejected_attempt_count: int | None = Field(default=None, ge=0)
    interaction_id: str | None = Field(default=None, pattern=_INTERACTION_ID_PATTERN)

    @model_validator(mode="after")
    def _check_usage(self) -> RowUsage:
        if (self.upstream_request_count is None) != (self.rejected_attempt_count is None):
            raise ValueError("the two counts are present together or omitted together")
        upstream = self.upstream_request_count
        if self.status is UsageStatus.OBSERVED_USAGE and (upstream is None or upstream <= 0):
            raise ValueError("OBSERVED_USAGE needs a positive upstream count")
        if self.status is UsageStatus.MEASURED_ZERO and (
            upstream != 0 or self.coverage is not Coverage.SUFFICIENT_FOR_ZERO
        ):
            raise ValueError("MEASURED_ZERO needs a zero count under SUFFICIENT_FOR_ZERO coverage")
        if self.status is UsageStatus.USAGE_UNESTABLISHED and upstream:
            raise ValueError("USAGE_UNESTABLISHED has no positive upstream count")
        return self


def row_key(row: ApiUsageRow) -> tuple[str, str]:
    return (row.consumer.id, row.gateway_route.id)


class ApiUsageRow(BaseModel):
    """D4: one I2 `qualification_rows` entry, enriched only with same-snapshot reconciliation."""

    model_config = _closed()

    consumer: RowConsumer
    gateway_route: RowRoute
    api: RowApi
    application_service: RowService
    configured_access: RowConfiguredAccess
    usage: RowUsage
    evidence_refs: list[_EvidenceRef] = Field(min_length=1, json_schema_extra=_UNIQUE)
    limitations: list[MeasurementCode] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_row(self) -> ApiUsageRow:
        _check_sorted_unique_strings(self.evidence_refs, "evidence_refs")
        _check_sorted_unique_strings(self.limitations, "limitations")
        if (self.usage.coverage is Coverage.SUFFICIENT_FOR_ZERO) != (not self.limitations):
            raise ValueError("SUFFICIENT_FOR_ZERO coverage has no limitations, UNKNOWN has some")
        if (
            self.usage.status is UsageStatus.MEASURED_ZERO
            and self.configured_access.status
            is not ConfiguredAccessStatus.CONFIGURED_ACCESS_ESTABLISHED
        ):
            raise ValueError("MEASURED_ZERO needs established configured access")
        return self


class Page(BaseModel):
    model_config = _closed()

    limit: int = Field(ge=1, le=MAX_PAGE_LIMIT)
    returned: int = Field(ge=0, le=MAX_PAGE_LIMIT)
    next_cursor: str | None = Field(
        default=None, min_length=1, max_length=_MAX_CURSOR_LENGTH, pattern=_CURSOR_PATTERN
    )

    @field_validator("next_cursor")
    @classmethod
    def _check_next_cursor(cls, value: str | None) -> str | None:
        return _check_cursor(value)

    @model_validator(mode="after")
    def _check_page(self) -> Page:
        if self.returned > self.limit:
            raise ValueError("returned must not exceed limit")
        return self


# --- Query payload (D4) -------------------------------------------------------------------------


def _query_data_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors the target-kind rule of `ApiConsumerUsageData` as far as JSON Schema can."""
    schema["allOf"] = [
        {
            "if": {
                "properties": {
                    "request_context": {
                        "properties": {"target": {"properties": {"kind": {"const": kind}}}}
                    }
                },
                "required": ["request_context"],
            },
            "then": then,
        }
        for kind, then in (
            ("GATEWAY_ROUTE", {"not": {"required": ["association_summary"]}}),
            (
                "API_OPERATION",
                {
                    "required": ["association_summary"],
                    "properties": {"association_summary": {"required": ["route_operation"]}},
                },
            ),
            (
                "APPLICATION_SERVICE",
                {
                    "required": ["association_summary"],
                    "properties": {"association_summary": {"required": ["target_service"]}},
                },
            ),
        )
    ]


class ApiConsumerUsageData(BaseModel):
    """D4: the `mode: "query"` payload."""

    model_config = _closed(json_schema_extra=_query_data_schema_extra)

    request_context: ApiUsageRequestContext
    window: ApiUsageWindow
    rules: Rules
    association_summary: AssociationSummary | None = None
    selected_routes: list[SelectedRoute] = Field(json_schema_extra=_UNIQUE)
    configuration_sources: list[ConfigurationSource] = Field(json_schema_extra=_UNIQUE)
    measurement_sources: list[MeasurementSource] = Field(min_length=1, json_schema_extra=_UNIQUE)
    rows: list[ApiUsageRow] = Field(max_length=MAX_PAGE_LIMIT, json_schema_extra=_UNIQUE)
    page: Page

    @model_validator(mode="after")
    def _check_data(self) -> ApiConsumerUsageData:
        context = self.request_context
        _check_sorted_unique(self.selected_routes, lambda r: r.route_id, "selected_routes")
        _check_sorted_unique(
            self.configuration_sources,
            lambda s: (s.gateway_instance_id, s.environment, s.source_revision),
            "configuration_sources",
        )
        _check_sorted_unique(
            self.measurement_sources,
            lambda s: (s.source_instance_id, s.window_start, s.window_end),
            "measurement_sources",
        )
        _check_sorted_unique(self.rows, row_key, "rows")
        self._check_summary(context.target.kind)
        if (self.window.window_start, self.window.window_end) != (
            context.window_start,
            context.window_end,
        ):
            raise ValueError("window must be the requested window")
        if not any(
            source.source_instance_id == self.window.source_instance_id
            and (source.window_start, source.window_end)
            == (self.window.window_start, self.window.window_end)
            for source in self.measurement_sources
        ):
            raise ValueError("the window's source must be listed in measurement_sources")
        self._check_selection(context)
        self._check_rows(context)
        if self.page.returned != len(self.rows):
            raise ValueError("page.returned must equal the number of rows")
        return self

    def _check_summary(self, kind: TargetKind) -> None:
        summary = self.association_summary
        if kind is TargetKind.GATEWAY_ROUTE:
            if summary is not None:
                raise ValueError("a GATEWAY_ROUTE target has no association_summary")
            return
        if summary is None:
            raise ValueError(f"a {kind.value} target requires an association_summary")
        counts = (
            summary.route_operation if kind is TargetKind.API_OPERATION else summary.target_service
        )
        if counts is None:
            raise ValueError("the association_summary chain must match the target kind")
        if counts.resolved_to_target != len(self.selected_routes):
            raise ValueError("resolved_to_target must equal the number of selected routes")

    def _check_selection(self, context: ApiUsageRequestContext) -> None:
        if context.target.kind is TargetKind.GATEWAY_ROUTE and (
            [route.route_id for route in self.selected_routes] != [context.target.id]
        ):
            raise ValueError("a GATEWAY_ROUTE target selects exactly that Route")

    def _check_rows(self, context: ApiUsageRequestContext) -> None:
        selected = {route.route_id: route for route in self.selected_routes}
        for row in self.rows:
            route = selected.get(row.gateway_route.id)
            if route is None:
                raise ValueError("a row's Route must be a selected Route")
            if row.gateway_route.gateway_instance_id != context.gateway_instance_id:
                raise ValueError("a row's Route belongs to the requested gateway")
            if context.consumer_id is not None and row.consumer.id != context.consumer_id:
                raise ValueError("a row's consumer must match the consumer filter")
            if (
                row.usage.coverage is not route.coverage
                or row.limitations != route.limitations
                or row.gateway_route.source_route_id != route.source_route_id
            ):
                raise ValueError("a row carries its Route's coverage, limitations and source id")
            has_counts = row.usage.upstream_request_count is not None
            if has_counts != self.window.valid:
                raise ValueError("counts are omitted exactly when the window is invalid")
            if not self.window.valid and row.usage.status is not UsageStatus.USAGE_UNESTABLISHED:
                raise ValueError("an invalid window establishes no usage")

    def expected_limitation_codes(self) -> set[ApiUsageLimitationCode]:
        """D6: exactly the codes the data implies."""
        codes: set[ApiUsageLimitationCode] = set()
        if self.page.next_cursor is not None:
            codes.add(_CODE.MORE_ROWS_AVAILABLE)
        if not self.window.valid:
            codes.add(_CODE.WINDOW_NOT_VALID)
        if any(route.coverage is Coverage.UNKNOWN_COVERAGE for route in self.selected_routes):
            codes.add(_CODE.COVERAGE_UNKNOWN)
        if not self.selected_routes:
            codes.add(_CODE.NO_ROUTE_SELECTED)
        return codes


# --- Evidence payloads (D9) ---------------------------------------------------------------------


class EvidenceRoute(BaseModel):
    model_config = _closed()

    id: _RouteId
    source_route_id: _Opaque


class ExtractDigests(BaseModel):
    model_config = _closed()

    start_sha256: str = Field(pattern=_DIGEST_PATTERN)
    end_sha256: str = Field(pattern=_DIGEST_PATTERN)


class ConfiguredAccessEvidence(BaseModel):
    model_config = _closed()

    kind: Literal["CONFIGURED_ACCESS"]
    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    source_revision: _Opaque
    consumer: RowConsumer
    gateway_route: EvidenceRoute
    rule_kind: _Opaque
    polarity: _Opaque
    scope: _Opaque


class MeasurementWindowEvidence(BaseModel):
    model_config = _closed()

    kind: Literal["MEASUREMENT_WINDOW"]
    source_instance_id: _Opaque
    gateway_instance_id: _GatewayInstanceId
    environment: _Environment
    window_start: _Timestamp
    window_end: _Timestamp
    apisix_version: _Opaque
    start_settled: bool
    end_settled: bool
    no_restart: bool
    start_stable_seconds: int = Field(ge=0)
    end_stable_seconds: int = Field(ge=0)
    valid: bool
    reasons: list[WindowReasonCode] = Field(json_schema_extra=_UNIQUE)
    evidence_type: Literal["OBSERVED"]
    extract_digests: ExtractDigests

    @model_validator(mode="after")
    def _check_window(self) -> MeasurementWindowEvidence:
        _check_sorted_unique_strings(self.reasons, "reasons")
        if self.valid != (not self.reasons):
            raise ValueError("valid must be true exactly when there are no reasons")
        return self


class OperationMappingStatement(BaseModel):
    model_config = _closed()

    operation_id: str = Field(pattern=_OPERATION_ID_PATTERN)


class ServiceMappingStatement(BaseModel):
    model_config = _closed()

    target: TargetCarrier
    service_id: str = Field(pattern=_SERVICE_ID_PATTERN)


class ServiceLabelStatement(BaseModel):
    model_config = _closed()

    carrier: TargetCarrier
    service_id: str = Field(pattern=_SERVICE_ID_PATTERN)


class RouteOperationReconciliationEvidence(BaseModel):
    """Only what the frozen I2 snapshot carries (D9 provenance boundary): the outcome, the raw
    explicit mapping entries and the rule. No reconciliation basis is exposed."""

    model_config = _closed()

    kind: Literal["ROUTE_OPERATION_RECONCILIATION"]
    gateway_route: EvidenceRoute
    outcome: Reconciliation
    operation_id: str | None = Field(default=None, pattern=_OPERATION_ID_PATTERN)
    contract_version_reconciliation: Reconciliation | None = None
    contract_version_id: _Opaque | None = None
    mapping_entries: list[OperationMappingStatement] = Field(json_schema_extra=_UNIQUE)
    rule: RuleRef

    @model_validator(mode="after")
    def _check_evidence(self) -> RouteOperationReconciliationEvidence:
        _check_sorted_unique(self.mapping_entries, lambda e: e.operation_id, "mapping_entries")
        resolved = self.outcome is Reconciliation.RESOLVED
        if (self.operation_id is not None) != resolved:
            raise ValueError("operation_id is present exactly when the outcome is RESOLVED")
        if (self.contract_version_reconciliation is not None) != resolved:
            raise ValueError("the contract chain is evaluated only for a RESOLVED Operation")
        version_resolved = self.contract_version_reconciliation is Reconciliation.RESOLVED
        if (self.contract_version_id is not None) != version_resolved:
            raise ValueError("contract_version_id is present exactly when the version is RESOLVED")
        return self


class TargetServiceReconciliationEvidence(BaseModel):
    model_config = _closed()

    kind: Literal["TARGET_SERVICE_RECONCILIATION"]
    gateway_route: EvidenceRoute
    outcome: Reconciliation
    service_id: str | None = Field(default=None, pattern=_SERVICE_ID_PATTERN)
    mapping_entries: list[ServiceMappingStatement] = Field(json_schema_extra=_UNIQUE)
    labels: list[ServiceLabelStatement] = Field(json_schema_extra=_UNIQUE)
    rule: RuleRef

    @model_validator(mode="after")
    def _check_evidence(self) -> TargetServiceReconciliationEvidence:
        _check_sorted_unique(
            self.mapping_entries, lambda e: (e.target.value, e.service_id), "mapping_entries"
        )
        _check_sorted_unique(self.labels, lambda e: (e.carrier.value, e.service_id), "labels")
        if (self.service_id is not None) != (self.outcome is Reconciliation.RESOLVED):
            raise ValueError("service_id is present exactly when the outcome is RESOLVED")
        return self


class QualificationLimitationsEvidence(BaseModel):
    model_config = _closed()

    kind: Literal["QUALIFICATION_LIMITATIONS"]
    gateway_route: EvidenceRoute
    coverage: Coverage
    codes: list[MeasurementCode] = Field(json_schema_extra=_UNIQUE)
    window_valid: bool

    @model_validator(mode="after")
    def _check_evidence(self) -> QualificationLimitationsEvidence:
        _check_sorted_unique_strings(self.codes, "codes")
        return self


EvidencePayload = Annotated[
    ConfiguredAccessEvidence
    | MeasurementWindowEvidence
    | RouteOperationReconciliationEvidence
    | TargetServiceReconciliationEvidence
    | QualificationLimitationsEvidence,
    Field(discriminator="kind"),
]


def _evidence_entry_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `EvidenceEntry._check_entry`: only a RESOLVED entry carries kind and evidence."""
    schema["allOf"] = [
        {
            "if": {"properties": {"status": {"const": "RESOLVED"}}, "required": ["status"]},
            "then": {"required": ["kind", "evidence"]},
            "else": {"not": {"anyOf": [{"required": ["kind"]}, {"required": ["evidence"]}]}},
        }
    ]


class EvidenceEntry(BaseModel):
    """D9: one requested ref. A forged, cross-snapshot and cross-context ref are all simply
    `NOT_RESOLVED` and indistinguishable (no ref history is kept)."""

    model_config = _closed(json_schema_extra=_evidence_entry_schema_extra)

    ref: _EvidenceRef
    status: EvidenceStatus
    kind: EvidenceKind | None = None
    evidence: EvidencePayload | None = None

    @model_validator(mode="after")
    def _check_entry(self) -> EvidenceEntry:
        if self.status is EvidenceStatus.RESOLVED:
            if self.kind is None or self.evidence is None:
                raise ValueError("a RESOLVED entry carries kind and evidence")
            if self.evidence.kind != self.kind.value:
                raise ValueError("the evidence payload must be of the entry's kind")
        elif self.kind is not None or self.evidence is not None:
            raise ValueError("a NOT_RESOLVED entry carries no kind and no evidence")
        return self


class ApiConsumerUsageEvidenceData(BaseModel):
    """D9: the `mode: "evidence"` payload, one entry per requested ref, sorted by ref."""

    model_config = _closed()

    request_context: ApiUsageRequestContext
    entries: list[EvidenceEntry] = Field(
        min_length=1, max_length=MAX_EVIDENCE_REFS, json_schema_extra=_UNIQUE
    )

    @model_validator(mode="after")
    def _check_data(self) -> ApiConsumerUsageEvidenceData:
        _check_sorted_unique(self.entries, lambda entry: entry.ref, "entries")
        return self

    def expected_limitation_codes(self) -> set[ApiUsageLimitationCode]:
        if all(entry.status is EvidenceStatus.RESOLVED for entry in self.entries):
            return set()
        return {_CODE.EVIDENCE_REF_NOT_RESOLVED}

    def any_resolved(self) -> bool:
        return any(entry.status is EvidenceStatus.RESOLVED for entry in self.entries)


# --- Envelope (D2, D6) --------------------------------------------------------------------------


class ApiUsageLimitation(BaseModel):
    model_config = _closed()

    code: ApiUsageLimitationCode
    message: str = Field(min_length=1)


def _codes_contain(*codes: ApiUsageLimitationCode) -> dict[str, Any]:
    return {
        "properties": {
            "limitations": {
                "contains": {"properties": {"code": {"enum": sorted(c.value for c in codes)}}}
            }
        },
        "required": ["limitations"],
    }


_REFUSAL_QUERY_ENUM = sorted(code.value for code in REFUSAL_CODES_QUERY)
_REFUSAL_EVIDENCE_ENUM = sorted(code.value for code in REFUSAL_CODES_EVIDENCE)


def _answer_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `ApiConsumerUsageAnswer._check_envelope` as far as JSON Schema can express it."""
    data_null = {"properties": {"data": {"type": "null"}}, "required": ["data"]}
    mode_evidence = {"properties": {"mode": {"const": "evidence"}}, "required": ["mode"]}
    schema["allOf"] = [
        {
            "if": {"properties": {"mode": {"const": "query"}}, "required": ["mode"]},
            # Each payload is closed, so its required keys identify it without a `$ref`.
            "then": {
                "properties": {
                    "data": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "object", "required": ["request_context", "rows"]},
                        ]
                    }
                }
            },
            "else": {
                "properties": {
                    "data": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "object", "required": ["request_context", "entries"]},
                        ]
                    }
                }
            },
        },
        {
            "if": data_null,
            "then": {
                "properties": {
                    "outcome": {"const": "NOT_ANSWERED"},
                    "limitations": {
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"properties": {"code": {"enum": _REFUSAL_QUERY_ENUM}}},
                    },
                }
            },
            "else": {
                "properties": {
                    "limitations": {
                        "items": {"properties": {"code": {"not": {"enum": _REFUSAL_QUERY_ENUM}}}}
                    }
                }
            },
        },
        {
            "if": {"allOf": [data_null, mode_evidence]},
            "then": {
                "properties": {
                    "limitations": {
                        "items": {"properties": {"code": {"enum": _REFUSAL_EVIDENCE_ENUM}}}
                    }
                }
            },
        },
        {
            "if": {"properties": {"outcome": {"const": "ANSWERED"}}, "required": ["outcome"]},
            "then": {"properties": {"limitations": {"maxItems": 0}}},
        },
        {
            "if": {"properties": {"outcome": {"const": "PARTIAL"}}, "required": ["outcome"]},
            "then": {"properties": {"limitations": {"minItems": 1}}},
        },
        {
            "if": {"properties": {"snapshot": {"type": "null"}}, "required": ["snapshot"]},
            "then": _codes_contain(_CODE.SNAPSHOT_NOT_AVAILABLE),
        },
        {
            "if": {
                "properties": {
                    "mode": {"const": "query"},
                    "outcome": {"const": "NOT_ANSWERED"},
                    "data": {"not": {"type": "null"}},
                },
                "required": ["mode", "outcome", "data"],
            },
            "then": _codes_contain(_CODE.NO_ROUTE_SELECTED),
        },
        {
            "if": {
                "properties": {
                    "mode": {"const": "evidence"},
                    "outcome": {"const": "NOT_ANSWERED"},
                    "data": {"not": {"type": "null"}},
                },
                "required": ["mode", "outcome", "data"],
            },
            "then": _codes_contain(_CODE.EVIDENCE_REF_NOT_RESOLVED),
        },
    ]


class ApiConsumerUsageAnswer(BaseModel):
    """The 0.7 envelope (D2, D6). `data` is null if and only if the answer is a refusal (a
    pre-evaluation failure); an evaluated `NOT_ANSWERED` still carries its payload."""

    model_config = _closed(title="ApiConsumerUsageAnswer", json_schema_extra=_answer_schema_extra)

    schema_version: ApiUsageSchemaVersion
    producer: Producer
    tool: ApiUsageToolName
    mode: ApiUsageMode
    outcome: Outcome
    snapshot: SnapshotRef | None
    data: ApiConsumerUsageData | ApiConsumerUsageEvidenceData | None
    limitations: list[ApiUsageLimitation] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_envelope(self) -> ApiConsumerUsageAnswer:
        codes = [limitation.code for limitation in self.limitations]
        if [code.value for code in codes] != sorted({code.value for code in codes}):
            raise ValueError("limitations must be sorted by code, one per code")
        if self.snapshot is None and _CODE.SNAPSHOT_NOT_AVAILABLE not in codes:
            raise ValueError("snapshot may be null only with SNAPSHOT_NOT_AVAILABLE")
        if self.data is None:
            self._check_refusal(codes)
            return self
        expected_type = (
            ApiConsumerUsageData if self.mode == "query" else ApiConsumerUsageEvidenceData
        )
        if type(self.data) is not expected_type:
            raise ValueError(f"mode {self.mode!r} requires {expected_type.__name__} data")
        if self.snapshot is None:
            raise ValueError("an evaluated answer is bound to a snapshot")
        if set(codes) & REFUSAL_CODES_QUERY:
            raise ValueError("a refusal code requires null data")
        expected_codes = self.data.expected_limitation_codes()
        if set(codes) != expected_codes:
            raise ValueError(f"limitations must be exactly {sorted(expected_codes)} (D6)")
        self._check_outcome(expected_codes)
        if isinstance(self.data, ApiConsumerUsageData):
            cursor = self.data.page.next_cursor
            if cursor is not None:
                bound = decode_cursor(cursor)
                if bound.snapshot_id != self.snapshot.snapshot_id:
                    raise ValueError("next_cursor must be bound to the answer's snapshot (D8)")
                if bound.query_digest != query_context_digest(
                    target_kind=self.data.request_context.target.kind.value,
                    target_id=self.data.request_context.target.id,
                    gateway_instance_id=self.data.request_context.gateway_instance_id,
                    environment=self.data.request_context.environment,
                    window_start=self.data.request_context.window_start,
                    window_end=self.data.request_context.window_end,
                    consumer_id=self.data.request_context.consumer_id,
                ):
                    raise ValueError("next_cursor must be bound to the request context (D8)")
        return self

    def _check_refusal(self, codes: Sequence[ApiUsageLimitationCode]) -> None:
        if self.outcome is not Outcome.NOT_ANSWERED or len(codes) != 1:
            raise ValueError("a null data is a NOT_ANSWERED refusal with exactly one limitation")
        allowed = REFUSAL_CODES_QUERY if self.mode == "query" else REFUSAL_CODES_EVIDENCE
        if codes[0] not in allowed:
            article = "a query" if self.mode == "query" else "an evidence"
            raise ValueError(
                f"{article} refusal carries one of {sorted(code.value for code in allowed)}"
            )

    def _check_outcome(self, codes: Iterable[ApiUsageLimitationCode]) -> None:
        codes = set(codes)
        if isinstance(self.data, ApiConsumerUsageEvidenceData):
            expected = (
                Outcome.ANSWERED
                if not codes
                else Outcome.PARTIAL
                if self.data.any_resolved()
                else Outcome.NOT_ANSWERED
            )
        else:
            expected = (
                Outcome.NOT_ANSWERED
                if _CODE.NO_ROUTE_SELECTED in codes
                else Outcome.PARTIAL
                if codes
                else Outcome.ANSWERED
            )
        if self.outcome is not expected:
            raise ValueError(f"outcome must be {expected.value} for these limitations (D6)")
