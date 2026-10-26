"""v0.8 I2b: the experimental binding-picture answer (I2 spec §4-§6, D9, D10). Closed models in the
v0.7.1 envelope conventions; the frozen JSON Schema, REST, MCP and the evidence mode arrive in I2c.

The binding picture has its own evidence-ref domain (`binding-evidence:`) and its own ref kinds, so
the destination-consumer contract stays unchanged (owner review of the I2b plan, correction 3).
Experimental semantics: nothing here is a v1.0 contract (parent §2).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Iterable
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from app.architecture_intelligence.contracts import (
    SNAPSHOT_ID_PATTERN,
    Outcome,
    Producer,
    SnapshotRef,
)
from app.common.encoding import length_delimited, sha256_hex, utf8

TOOL_NAME = "get_binding_picture"
SCHEMA_VERSION = "0.8.0"
EVIDENCE_REF_PREFIX = "binding-evidence:"
DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 200
MAX_BROKERS = 8

_SHA256_HEX = "[0-9a-f]{64}"
_OPAQUE_ID_PATTERN = r"^[^\s\x00-\x1f\x7f]+$"
_DIGEST_PATTERN = rf"^{_SHA256_HEX}$"


class LimitationCode(StrEnum):
    """I2 §6: refusals and limitations of the binding-picture answer."""

    SNAPSHOT_NOT_AVAILABLE = "SNAPSHOT_NOT_AVAILABLE"
    NO_ACCEPTED_CATALOG = "NO_ACCEPTED_CATALOG"
    UNKNOWN_BOUNDED_CONTEXT = "UNKNOWN_BOUNDED_CONTEXT"
    NO_ACCEPTED_CAPTURE = "NO_ACCEPTED_CAPTURE"
    CURSOR_QUERY_MISMATCH = "CURSOR_QUERY_MISMATCH"
    CAPTURE_SCOPE_LIMITED = "CAPTURE_SCOPE_LIMITED"
    PROMISES_ASSUMED_CONFIRMED = "PROMISES_ASSUMED_CONFIRMED"
    PRODUCER_SIDE_DECLARED_ONLY = "PRODUCER_SIDE_DECLARED_ONLY"
    EVENT_HANDLING_NOT_ESTABLISHED = "EVENT_HANDLING_NOT_ESTABLISHED"
    CROSS_BROKER_DELIVERY_NOT_ESTABLISHED = "CROSS_BROKER_DELIVERY_NOT_ESTABLISHED"
    MORE_ROWS_AVAILABLE = "MORE_ROWS_AVAILABLE"


REFUSAL_CODES = frozenset(
    {
        LimitationCode.SNAPSHOT_NOT_AVAILABLE,
        LimitationCode.NO_ACCEPTED_CATALOG,
        LimitationCode.UNKNOWN_BOUNDED_CONTEXT,
        LimitationCode.NO_ACCEPTED_CAPTURE,
        LimitationCode.CURSOR_QUERY_MISMATCH,
    }
)
ALWAYS_PRESENT = (
    LimitationCode.CAPTURE_SCOPE_LIMITED,
    LimitationCode.PROMISES_ASSUMED_CONFIRMED,
    LimitationCode.PRODUCER_SIDE_DECLARED_ONLY,
    LimitationCode.EVENT_HANDLING_NOT_ESTABLISHED,
)


class AssessmentStatus(StrEnum):
    """D10: the closed doctrine §4.3 enum. v0.8 never emits `CONTRADICTED` (no closed-world rule)
    or `OBSERVED_NOT_PROMISED` (no promise coverage)."""

    PROMISED_AND_OBSERVED = "PROMISED_AND_OBSERVED"
    PROMISED_NOT_OBSERVED = "PROMISED_NOT_OBSERVED"
    CONTRADICTED = "CONTRADICTED"
    OBSERVED_NOT_PROMISED = "OBSERVED_NOT_PROMISED"
    UNRESOLVED = "UNRESOLVED"


class AssessmentReason(StrEnum):
    PROMISE_COVERAGE_MISSING = "PROMISE_COVERAGE_MISSING"
    TOPIC_NOT_DECLARED = "TOPIC_NOT_DECLARED"
    # The v0.7.1 attribution reasons of an R6 row, mirrored by value.
    NO_MAPPING = "NO_MAPPING"
    SERVICE_NOT_DECLARED = "SERVICE_NOT_DECLARED"
    SERVICE_IDENTITY_AMBIGUOUS = "SERVICE_IDENTITY_AMBIGUOUS"
    SERVICE_IDENTITY_CONFLICT = "SERVICE_IDENTITY_CONFLICT"
    SERVICE_IDENTITY_PLACEHOLDER = "SERVICE_IDENTITY_PLACEHOLDER"
    MAPPING_SOURCE_DISAGREEMENT = "MAPPING_SOURCE_DISAGREEMENT"


class Crossing(StrEnum):
    """I2 §5 (D9): classification against the selected Bounded Context. It never states delivery."""

    INBOUND = "INBOUND"
    INSIDE = "INSIDE"
    OUTBOUND = "OUTBOUND"
    NONE = "NONE"
    UNRESOLVED = "UNRESOLVED"


class BindingEvidenceKind(StrEnum):
    CATALOG_PROMISE = "CATALOG_PROMISE"
    KAFKA_ATTACHMENT = "KAFKA_ATTACHMENT"
    KAFKA_SERVICE_MAPPING = "KAFKA_SERVICE_MAPPING"


def binding_evidence_ref(
    *, snapshot_id: str, query_digest: str, kind: BindingEvidenceKind, internal_ids: Iterable[str]
) -> str:
    """`binding-evidence:<sha256 hex of ld(tool, snapshot_id, query_digest, kind, *sorted ids)>` -
    the v0.7.1 derivation, with the tool name as a domain separator, so a binding ref never equals
    a destination-consumer ref for the same carriers. Internal ids are never exposed."""
    parts = (TOOL_NAME, snapshot_id, query_digest, kind.value, *sorted(set(internal_ids)))
    return f"{EVIDENCE_REF_PREFIX}{sha256_hex(length_delimited(*(utf8(part) for part in parts)))}"


_NULLABLE_ENVELOPE_FIELDS = frozenset({"data", "snapshot"})


class _Model(BaseModel):
    """An absent optional field is omitted, never null, except the two nullable envelope fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_serializer(mode="wrap")
    def _omit_absent(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        return {
            key: value
            for key, value in handler(self).items()
            if value is not None or key in _NULLABLE_ENVELOPE_FIELDS
        }


class RequestContext(_Model):
    """The exact query context after defaults: the broker ids are the requested ones, or every
    broker with an accepted capture in the environment. The cursor and every ref bind it."""

    bounded_context_id: str = Field(min_length=1, max_length=256, pattern=_OPAQUE_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=_OPAQUE_ID_PATTERN)
    broker_ids: list[str] = Field(min_length=1, max_length=MAX_BROKERS)


def query_context_digest(context: RequestContext) -> str:
    canonical = json.dumps(
        context.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Cursor(_Model):
    v: Literal[1]
    after: list[str] = Field(min_length=3, max_length=3)
    query_digest: str = Field(pattern=_DIGEST_PATTERN)
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)


def encode_cursor(cursor: Cursor) -> str:
    payload = json.dumps(cursor.model_dump(), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> Cursor:
    """Raises `ValueError` for anything that is not a well-formed cursor in canonical form."""
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        cursor = Cursor.model_validate(json.loads(raw.decode()))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is not a well-formed binding-picture cursor") from error
    if encode_cursor(cursor) != value:
        raise ValueError("cursor is not in canonical form")
    return cursor


class BindingPictureQueryRequest(_Model):
    mode: Literal["query"] = "query"
    bounded_context_id: str = Field(min_length=1, max_length=256, pattern=_OPAQUE_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=_OPAQUE_ID_PATTERN)
    broker_ids: list[str] | None = Field(default=None, min_length=1, max_length=MAX_BROKERS)
    snapshot_id: str | None = Field(default=None, pattern=SNAPSHOT_ID_PATTERN)
    limit: int = Field(default=DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT)
    cursor: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def _check(self) -> BindingPictureQueryRequest:
        if self.broker_ids is not None and len(set(self.broker_ids)) != len(self.broker_ids):
            raise ValueError("broker_ids must be unique")
        if self.cursor is not None:
            decode_cursor(self.cursor)
        return self


class ProducerEntry(_Model):
    service_id: str
    bounded_context_id: str | None = None
    broker_ids: list[str]
    declared_event_types: list[str]


class BindingRow(_Model):
    broker_id: str
    topic_name: str
    topic_id: str | None = None
    consumer_service_id: str | None = None
    # Every attributed group of this row (R1, R4, R6), sorted; empty for R2 and R7.
    group_ids: list[str]
    crossing: Crossing
    status: AssessmentStatus
    reason: AssessmentReason | None = None
    declared_event_types: list[str]
    producers: list[ProducerEntry]
    cross_broker_producers: bool
    captured_at: str | None = None
    promise_evidence_refs: list[str]
    attachment_evidence_refs: list[str]
    mapping_evidence_refs: list[str]

    def position(self) -> list[str]:
        consumer = self.consumer_service_id or (self.group_ids[0] if self.group_ids else "")
        return [self.broker_id, self.topic_name, consumer]


class CatalogSource(_Model):
    source_instance_id: str
    catalog_digest: str
    lookup_digest: str
    source_revision: str


class CaptureSource(_Model):
    broker_id: str
    source_instance_id: str
    captured_at: str
    source_revision: str


class Page(_Model):
    limit: int
    returned: int
    next_cursor: str | None = None


class BindingPictureData(_Model):
    request_context: RequestContext
    catalog_source: CatalogSource
    capture_sources: list[CaptureSource]
    rows: list[BindingRow]
    page: Page


class Limitation(_Model):
    code: LimitationCode
    message: str = Field(min_length=1)


class BindingPictureAnswer(_Model):
    """The envelope. `data` is null if and only if the answer is a refusal. An evaluated query is
    always `PARTIAL`: captures cover their allow-lists at their own T, and the promises are assumed
    confirmed, so no answer claims completeness."""

    schema_version: Literal["0.8.0"]
    producer: Producer
    tool: Literal["get_binding_picture"]
    mode: Literal["query"]
    outcome: Outcome
    snapshot: SnapshotRef | None
    data: BindingPictureData | None
    limitations: list[Limitation]

    @model_validator(mode="after")
    def _check_envelope(self) -> BindingPictureAnswer:
        codes = [item.code.value for item in self.limitations]
        if codes != sorted(set(codes)):
            raise ValueError("limitations must be sorted by code, one per code")
        if self.data is None:
            if self.outcome is not Outcome.NOT_ANSWERED or len(codes) != 1:
                raise ValueError("a null data is a NOT_ANSWERED refusal with one limitation")
            if LimitationCode(codes[0]) not in REFUSAL_CODES:
                raise ValueError("a refusal carries a refusal code")
        elif self.outcome is not Outcome.PARTIAL:
            raise ValueError("an evaluated binding picture is PARTIAL")
        return self
