"""v0.7.1 I3.1 - the public destination-consumer contract (schema 0.7.1) for
`get_destination_consumers` (docs/specifications/0.7.1/i3-destination-consumer-public-answer.md).

This module defines only the data contract: the query request, the `DestinationConsumersAnswer`
envelope and its payload, the cursor codec and the two frozen pure derivations (the query-context
digest and the evidence ref). It contains no service logic, no Neo4j access and no projection; the
evidence mode, REST and MCP arrive in I3.2. It follows the v0.7.0 `api_usage_contracts` shape and
reuses `Producer`, `SnapshotRef` and `Outcome`. Like that module, the public outcome and reason enums
mirror the internal I2 values by value, not by import, so internal churn cannot silently change the
published schema (`tests/unit/test_v071_i3_destination_consumer_contracts.py` pins the parity).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
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
_OPAQUE_ID_PATTERN = r"^[^\s\x00-\x1f\x7f]+$"
_TIMESTAMP_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$"
_SERVICE_ID_PATTERN = r"^service:[^\s\x00-\x1f\x7f]*$"
_CONSUMER_ID_PATTERN = rf"^consumer:{_SHA256_HEX}$"
_CAPTURE_SOURCE_PATTERN = rf"^urn:aip:source:kafka-consumer-state:{_SHA256_HEX}$"
_EVIDENCE_REF_PATTERN = rf"^destination-evidence:{_SHA256_HEX}$"
_DIGEST_PATTERN = rf"^{_SHA256_HEX}$"
_CURSOR_PATTERN = r"^[A-Za-z0-9_-]+$"

DestinationConsumersSchemaVersion = Literal["0.7.1"]
SCHEMA_VERSION: DestinationConsumersSchemaVersion = get_args(DestinationConsumersSchemaVersion)[0]
DestinationConsumersToolName = Literal["get_destination_consumers"]
TOOL_NAME: DestinationConsumersToolName = get_args(DestinationConsumersToolName)[0]

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 200
MAX_EVIDENCE_REFS = 20
_MAX_CURSOR_LENGTH = 2048
_MAX_ID_LENGTH = 512
_MAX_BROKER_ID_LENGTH = 256
_MAX_ENVIRONMENT_LENGTH = 128

EVIDENCE_REF_PREFIX = "destination-evidence:"


class LimitationCode(StrEnum):
    """Spec §3: the closed top-level codes, distinct from the I2 row reasons. The first six are
    refusals (`data` is null)."""

    SNAPSHOT_NOT_AVAILABLE = "SNAPSHOT_NOT_AVAILABLE"
    UNKNOWN_DESTINATION = "UNKNOWN_DESTINATION"
    DESTINATION_NOT_KAFKA_TOPIC = "DESTINATION_NOT_KAFKA_TOPIC"
    BROKER_MISMATCH = "BROKER_MISMATCH"
    NO_ACCEPTED_CAPTURE = "NO_ACCEPTED_CAPTURE"
    CURSOR_QUERY_MISMATCH = "CURSOR_QUERY_MISMATCH"
    CAPTURE_SCOPE_LIMITED = "CAPTURE_SCOPE_LIMITED"
    NO_MAPPING_SOURCE = "NO_MAPPING_SOURCE"
    MORE_ROWS_AVAILABLE = "MORE_ROWS_AVAILABLE"
    EVIDENCE_REF_NOT_RESOLVED = "EVIDENCE_REF_NOT_RESOLVED"


_CODE = LimitationCode
REFUSAL_CODES = frozenset(
    {
        _CODE.SNAPSHOT_NOT_AVAILABLE,
        _CODE.UNKNOWN_DESTINATION,
        _CODE.DESTINATION_NOT_KAFKA_TOPIC,
        _CODE.BROKER_MISMATCH,
        _CODE.NO_ACCEPTED_CAPTURE,
        _CODE.CURSOR_QUERY_MISMATCH,
    }
)


class AttributionOutcome(StrEnum):
    """The I2 outcome (`kafka-consumer-attribution` / `1`), unrenamed."""

    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"


class AttributionReason(StrEnum):
    """The I2 reasons, unrenamed."""

    SERVICE_IDENTITY_CONFLICT = "SERVICE_IDENTITY_CONFLICT"
    MAPPING_SOURCE_DISAGREEMENT = "MAPPING_SOURCE_DISAGREEMENT"
    SERVICE_IDENTITY_AMBIGUOUS = "SERVICE_IDENTITY_AMBIGUOUS"
    SERVICE_NOT_DECLARED = "SERVICE_NOT_DECLARED"
    SERVICE_IDENTITY_PLACEHOLDER = "SERVICE_IDENTITY_PLACEHOLDER"
    NO_MAPPING = "NO_MAPPING"


class EvidenceKind(StrEnum):
    """Spec §4: the broker path and the mapping path."""

    KAFKA_ATTACHMENT = "KAFKA_ATTACHMENT"
    KAFKA_SERVICE_MAPPING = "KAFKA_SERVICE_MAPPING"


# --- Shared helpers -----------------------------------------------------------------------------

_UNIQUE: JsonDict = {"uniqueItems": True}

_Timestamp = Annotated[str, Field(pattern=_TIMESTAMP_PATTERN)]
_ConsumerId = Annotated[str, Field(pattern=_CONSUMER_ID_PATTERN)]
_EvidenceRef = Annotated[str, Field(pattern=_EVIDENCE_REF_PATTERN)]
_DestinationId = Annotated[
    str, Field(min_length=1, max_length=_MAX_ID_LENGTH, pattern=_OPAQUE_ID_PATTERN)
]
_BrokerId = Annotated[
    str, Field(min_length=1, max_length=_MAX_BROKER_ID_LENGTH, pattern=_OPAQUE_ID_PATTERN)
]
_Environment = Annotated[
    str, Field(min_length=1, max_length=_MAX_ENVIRONMENT_LENGTH, pattern=ENVIRONMENT_PATTERN)
]


def _check_sorted_unique(values: Sequence[Any], key: Any, what: str) -> None:
    keys = [key(value) for value in values]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{what} must be sorted and duplicate-free")


_NULLABLE_ENVELOPE_FIELDS = frozenset({"data", "snapshot"})


class _Model(BaseModel):
    """An absent optional field is omitted, never null (the v0.7.0 I3.3 owner decision), except
    the two required nullable envelope fields."""

    @model_serializer(mode="wrap")
    def _omit_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        serialized = handler(self)
        return {
            key: value
            for key, value in serialized.items()
            if value is not None or key in _NULLABLE_ENVELOPE_FIELDS
        }


def _closed(**extra: Any) -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid", **extra)


# --- Request context, cursor and frozen derivations --------------------------------------------


class RequestContext(_Model):
    """Spec §2: the exact query context. Page position, `limit` and `snapshot_id` are not part of
    it."""

    model_config = _closed()

    destination_id: _DestinationId
    broker_id: _BrokerId
    environment: _Environment


class Cursor(_Model):
    """The decoded continuation position. Within one Topic, broker and environment each consumer id
    has exactly one attachment, so the consumer id alone is the row position. Opaque to clients and
    unsigned; this model only checks its structure."""

    model_config = _closed()

    v: Literal[1]
    after: _ConsumerId
    query_digest: str = Field(pattern=_DIGEST_PATTERN)
    schema_version: DestinationConsumersSchemaVersion
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)


def encode_cursor(cursor: Cursor) -> str:
    """Unpadded base64url of the canonical JSON (sorted keys, no whitespace)."""
    payload = json.dumps(cursor.model_dump(), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> Cursor:
    """Raises `ValueError` for anything that is not a well-formed cursor in canonical form."""
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode())
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is not a well-formed destination-consumer cursor") from error
    cursor = Cursor.model_validate(payload)
    if encode_cursor(cursor) != value:
        raise ValueError("cursor is not in canonical form")
    return cursor


def _check_cursor(value: str | None) -> str | None:
    if value is not None:
        decode_cursor(value)
    return value


def query_context_digest(context: RequestContext) -> str:
    """Lowercase hex SHA-256 of the canonical JSON (sorted keys, compact, UTF-8) of the context. The
    cursor and every evidence ref bind it."""
    canonical = json.dumps(
        context.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_ref(
    *, snapshot_id: str, query_digest: str, kind: EvidenceKind, internal_ids: Iterable[str]
) -> str:
    """Spec §4: `destination-evidence:<sha256 hex of ld(snapshot_id, query_digest, kind, *sorted
    ids)>`. The internal carrier ids are distinct and sorted bytewise and never exposed."""
    ids = sorted(set(internal_ids))
    parts = (snapshot_id, query_digest, kind.value, *ids)
    return f"{EVIDENCE_REF_PREFIX}{sha256_hex(length_delimited(*(utf8(part) for part in parts)))}"


# --- Request ------------------------------------------------------------------------------------


class DestinationConsumersQueryRequest(_Model):
    """`mode: "query"` (spec §2)."""

    model_config = _closed(title="DestinationConsumersQueryRequest")

    mode: Literal["query"]
    destination_id: _DestinationId
    broker_id: _BrokerId
    environment: _Environment
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
    def _check_request(self) -> DestinationConsumersQueryRequest:
        if self.cursor is not None and self.snapshot_id is None:
            raise ValueError("a cursor requires snapshot_id")
        return self

    def context(self) -> RequestContext:
        return RequestContext(
            destination_id=self.destination_id,
            broker_id=self.broker_id,
            environment=self.environment,
        )


# --- Answer payload -----------------------------------------------------------------------------


class CaptureSource(_Model):
    """One accepted I1 capture of the requested broker and environment, with its own T (spec §3:
    several captures are never collapsed into one invented T)."""

    model_config = _closed()

    source_instance_id: str = Field(pattern=_CAPTURE_SOURCE_PATTERN)
    captured_at: _Timestamp
    source_revision: str = Field(min_length=1)
    scope_digest: str = Field(pattern=_DIGEST_PATTERN)


class RowLimitation(_Model):
    """A non-resolving mapping entry of a RESOLVED group, with the ref of its mapping evidence."""

    model_config = _closed()

    reason: AttributionReason
    mapping_evidence_ref: _EvidenceRef


def _row_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `ConsumerRow._check_row`: `service_id` and `limitations` only when RESOLVED,
    `reason` exactly when not RESOLVED."""
    resolved = {"properties": {"outcome": {"const": "RESOLVED"}}, "required": ["outcome"]}
    schema["allOf"] = [
        {
            "if": resolved,
            "then": {"required": ["service_id"], "not": {"required": ["reason"]}},
            "else": {
                "required": ["reason"],
                "not": {"required": ["service_id"]},
                "properties": {"limitations": {"maxItems": 0}},
            },
        }
    ]


class ConsumerRow(_Model):
    """Spec §3: one row per I1 attachment on the queried Topic, in the requested broker and
    environment. `consumer_id` and `group_id` are the Kafka-native group identity, not a Service
    or Subscription."""

    model_config = _closed(json_schema_extra=_row_schema_extra)

    consumer_id: _ConsumerId
    group_id: str = Field(min_length=1)
    outcome: AttributionOutcome
    service_id: str | None = Field(default=None, pattern=_SERVICE_ID_PATTERN)
    reason: AttributionReason | None = None
    limitations: list[RowLimitation] = Field(json_schema_extra=_UNIQUE)
    captured_at: _Timestamp
    attachment_evidence_refs: list[_EvidenceRef] = Field(min_length=1, json_schema_extra=_UNIQUE)
    mapping_evidence_refs: list[_EvidenceRef] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_row(self) -> ConsumerRow:
        resolved = self.outcome is AttributionOutcome.RESOLVED
        if resolved != (self.service_id is not None):
            raise ValueError("service_id is present exactly when the outcome is RESOLVED")
        if resolved == (self.reason is not None):
            raise ValueError("reason is present exactly when the outcome is not RESOLVED")
        if self.limitations and not resolved:
            raise ValueError("limitations qualify a RESOLVED row only")
        _check_sorted_unique(
            self.limitations, lambda item: item.mapping_evidence_ref, "limitations"
        )
        _check_sorted_unique(self.attachment_evidence_refs, str, "attachment_evidence_refs")
        _check_sorted_unique(self.mapping_evidence_refs, str, "mapping_evidence_refs")
        if {item.mapping_evidence_ref for item in self.limitations} - set(
            self.mapping_evidence_refs
        ):
            raise ValueError("every limitation names one of the row's mapping evidence refs")
        return self


def _page_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `Page._check_page`: a continuation follows at least one returned row."""
    schema["allOf"] = [
        {"if": {"required": ["next_cursor"]}, "then": {"properties": {"returned": {"minimum": 1}}}}
    ]


class Page(_Model):
    model_config = _closed(json_schema_extra=_page_schema_extra)

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
        if self.next_cursor is not None and self.returned == 0:
            raise ValueError("a next_cursor continues after at least one returned row")
        return self


class DestinationConsumersData(_Model):
    """The query payload. `mapping_source_present` says whether any accepted mapping source exists
    for the broker and environment, which decides `NO_MAPPING_SOURCE`."""

    model_config = _closed()

    request_context: RequestContext
    capture_sources: list[CaptureSource] = Field(min_length=1, json_schema_extra=_UNIQUE)
    mapping_source_present: bool
    rows: list[ConsumerRow] = Field(max_length=MAX_PAGE_LIMIT, json_schema_extra=_UNIQUE)
    page: Page

    @model_validator(mode="after")
    def _check_data(self) -> DestinationConsumersData:
        _check_sorted_unique(
            self.capture_sources, lambda source: source.source_instance_id, "capture_sources"
        )
        _check_sorted_unique(self.rows, lambda row: row.consumer_id, "rows")
        if self.page.returned != len(self.rows):
            raise ValueError("page.returned must equal the number of rows")
        return self

    def expected_limitation_codes(self) -> set[LimitationCode]:
        codes = {_CODE.CAPTURE_SCOPE_LIMITED}
        if not self.mapping_source_present:
            codes.add(_CODE.NO_MAPPING_SOURCE)
        if self.page.next_cursor is not None:
            codes.add(_CODE.MORE_ROWS_AVAILABLE)
        return codes


# --- Envelope -----------------------------------------------------------------------------------


class Limitation(_Model):
    model_config = _closed()

    code: LimitationCode
    message: str = Field(min_length=1)


_REFUSAL_ENUM = sorted(code.value for code in REFUSAL_CODES)


def _has_code(code: LimitationCode) -> dict[str, Any]:
    return {
        "properties": {
            "limitations": {"contains": {"properties": {"code": {"const": code.value}}}}
        },
        "required": ["limitations"],
    }


def _lacks_code(code: LimitationCode) -> dict[str, Any]:
    return {
        "properties": {
            "limitations": {"items": {"properties": {"code": {"not": {"const": code.value}}}}}
        }
    }


def _data_has(properties: dict[str, Any]) -> dict[str, Any]:
    """An evaluated `data` object whose fields match `properties` (a null `data` never does)."""
    return {
        "properties": {
            "data": {"type": "object", "properties": properties, "required": sorted(properties)}
        },
        "required": ["data"],
    }


def _answer_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `DestinationConsumersAnswer._check_envelope` as far as JSON Schema can express it."""
    data_null = {"properties": {"data": {"type": "null"}}, "required": ["data"]}
    schema["allOf"] = [
        {
            "if": data_null,
            "then": {
                "properties": {
                    "outcome": {"const": "NOT_ANSWERED"},
                    "limitations": {
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"properties": {"code": {"enum": _REFUSAL_ENUM}}},
                    },
                }
            },
            "else": {
                "properties": {
                    "outcome": {"const": "PARTIAL"},
                    "snapshot": {"not": {"type": "null"}},
                    "limitations": {
                        "items": {"properties": {"code": {"not": {"enum": _REFUSAL_ENUM}}}},
                        "contains": {"properties": {"code": {"const": "CAPTURE_SCOPE_LIMITED"}}},
                    },
                }
            },
        },
        {
            "if": {"properties": {"snapshot": {"type": "null"}}, "required": ["snapshot"]},
            "then": _has_code(_CODE.SNAPSHOT_NOT_AVAILABLE),
        },
        # `expected_limitation_codes`: NO_MAPPING_SOURCE exactly when no mapping source is present,
        # MORE_ROWS_AVAILABLE exactly when a next_cursor is issued.
        {
            "if": _data_has({"mapping_source_present": {"const": False}}),
            "then": _has_code(_CODE.NO_MAPPING_SOURCE),
        },
        {
            "if": _data_has({"mapping_source_present": {"const": True}}),
            "then": _lacks_code(_CODE.NO_MAPPING_SOURCE),
        },
        {
            "if": _data_has({"page": {"required": ["next_cursor"]}}),
            "then": _has_code(_CODE.MORE_ROWS_AVAILABLE),
            "else": _lacks_code(_CODE.MORE_ROWS_AVAILABLE),
        },
        # The query mode resolves no evidence refs.
        _lacks_code(_CODE.EVIDENCE_REF_NOT_RESOLVED),
    ]


class DestinationConsumersAnswer(_Model):
    """The 0.7.1 envelope. `data` is null if and only if the answer is a refusal. An evaluated
    answer is always `PARTIAL`: an accepted capture covers only its configured group allow-list at
    its own T, so `CAPTURE_SCOPE_LIMITED` is always present and no answer claims completeness."""

    model_config = _closed(
        title="DestinationConsumersAnswer", json_schema_extra=_answer_schema_extra
    )

    schema_version: DestinationConsumersSchemaVersion
    producer: Producer
    tool: DestinationConsumersToolName
    mode: Literal["query"]
    outcome: Outcome
    snapshot: SnapshotRef | None
    data: DestinationConsumersData | None
    limitations: list[Limitation] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_envelope(self) -> DestinationConsumersAnswer:
        codes = [limitation.code for limitation in self.limitations]
        if [code.value for code in codes] != sorted({code.value for code in codes}):
            raise ValueError("limitations must be sorted by code, one per code")
        if self.snapshot is None and _CODE.SNAPSHOT_NOT_AVAILABLE not in codes:
            raise ValueError("snapshot may be null only with SNAPSHOT_NOT_AVAILABLE")
        if self.data is None:
            if self.outcome is not Outcome.NOT_ANSWERED or len(codes) != 1:
                raise ValueError("a null data is a NOT_ANSWERED refusal with one limitation")
            if codes[0] not in REFUSAL_CODES:
                raise ValueError(f"a refusal carries one of {_REFUSAL_ENUM}")
            return self
        if self.snapshot is None:
            raise ValueError("an evaluated answer is bound to a snapshot")
        expected = self.data.expected_limitation_codes()
        if set(codes) != expected:
            raise ValueError(f"limitations must be exactly {sorted(expected)}")
        if self.outcome is not Outcome.PARTIAL:
            raise ValueError("an evaluated answer is PARTIAL (CAPTURE_SCOPE_LIMITED)")
        cursor = self.data.page.next_cursor
        if cursor is not None:
            bound = decode_cursor(cursor)
            if bound.snapshot_id != self.snapshot.snapshot_id:
                raise ValueError("next_cursor must be bound to the answer's snapshot")
            if bound.query_digest != query_context_digest(self.data.request_context):
                raise ValueError("next_cursor must be bound to the request context")
            if bound.after != self.data.rows[-1].consumer_id:
                raise ValueError("next_cursor must continue after the last returned row")
        return self
