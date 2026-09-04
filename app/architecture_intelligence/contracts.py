"""v0.4.0 I1.1 - the frozen public architecture-answer contract (spec
docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md).

This module defines only the data contract: `ArchitectureAnswer[T]`, its envelope invariants, and
the `get_service_dependencies` payload shape. It intentionally contains no service logic, no Neo4j
access, and no snapshot/observation-context hashing - those land in later I1 sub-increments. The
enums here (Qualification, Coverage) mirror app.analysis.runtime's literal values by value, not by
import, so this public contract doesn't couple to internal analysis-module churn.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.provenance.model import EvidenceType, SourceType

_SHA256_HEX = r"[0-9a-f]{64}"
_SNAPSHOT_ID_PATTERN = rf"^aip:snapshot:v1:{_SHA256_HEX}$"
_MODEL_REVISION_PATTERN = rf"^sha256:{_SHA256_HEX}$"
_CONTEXT_ID_PATTERN = rf"^aip:observation-context:v1:{_SHA256_HEX}$"
_CLAIM_ID_PATTERN = rf"^aip:claim:v1:{_SHA256_HEX}$"

# No leading/trailing whitespace and no control characters anywhere (spec §16.1). Expressed as a
# single character-class-only pattern (no lookaround) so it also compiles under pydantic-core's
# Rust regex engine and therefore shows up as a real `pattern` in the generated JSON Schema.
_ENVIRONMENT_PATTERN = r"^[^\s\x00-\x1f\x7f](?:[^\x00-\x1f\x7f]*[^\s\x00-\x1f\x7f])?$"

_MAX_OBSERVATION_WINDOW = timedelta(days=31)


class Outcome(StrEnum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    NOT_ANSWERED = "NOT_ANSWERED"


class EntityType(StrEnum):
    SERVICE = "SERVICE"
    OPERATION = "OPERATION"
    QUEUE = "QUEUE"


class DeliveryKind(StrEnum):
    SYNC_HTTP = "SYNC_HTTP"
    ASYNC_MESSAGE = "ASYNC_MESSAGE"


class DeliveryRelationType(StrEnum):
    CALLS = "CALLS"
    SENDS = "SENDS"


class DestinationResolution(StrEnum):
    RESOLVED_SERVICE = "RESOLVED_SERVICE"
    DIRECT_TARGET_FALLBACK = "DIRECT_TARGET_FALLBACK"


class Qualification(StrEnum):
    CONFIRMED = "CONFIRMED"
    OBSERVED_ONLY = "OBSERVED_ONLY"
    NOT_OBSERVED_IN_WINDOW = "NOT_OBSERVED_IN_WINDOW"


class Coverage(StrEnum):
    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"
    UNKNOWN = "UNKNOWN"


class LimitationCode(StrEnum):
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    OBSERVATION_CONTEXT_REQUIRED = "OBSERVATION_CONTEXT_REQUIRED"
    SNAPSHOT_NOT_AVAILABLE = "SNAPSHOT_NOT_AVAILABLE"
    RESULT_LIMIT_EXCEEDED = "RESULT_LIMIT_EXCEEDED"


class DependencyPredicate(StrEnum):
    DIRECT_DEPENDENCY = "DIRECT_DEPENDENCY"


class EvidenceRelationType(StrEnum):
    """v0.4.0 I2.1 - the 7 canonical graph relation kinds (spec §11.2's `supports`). Deliberately its
    own closed enum rather than reusing `DeliveryRelationType` (only CALLS/SENDS) or a graph-layer
    string - `get_evidence` describes existing facts, never a new architecture claim."""

    PROVIDES = "PROVIDES"
    CALLS = "CALLS"
    SENDS = "SENDS"
    RECEIVES_FROM = "RECEIVES_FROM"
    CARRIES = "CARRIES"
    CONFORMS_TO = "CONFORMS_TO"
    DEAD_LETTERS_TO = "DEAD_LETTERS_TO"


# Fixed (kind, relation_type, via.type) pairs - spec §11.2/§13. No other combination is valid.
_ALLOWED_DELIVERY_PAIRS = {
    (DeliveryKind.SYNC_HTTP, DeliveryRelationType.CALLS, EntityType.OPERATION),
    (DeliveryKind.ASYNC_MESSAGE, DeliveryRelationType.SENDS, EntityType.QUEUE),
}


class Producer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Literal["architecture-intelligence-platform"]
    version: str
    build_revision: str


class SnapshotRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    model_revision: str = Field(pattern=_MODEL_REVISION_PATTERN)

    @model_validator(mode="after")
    def _check_matching_digest(self) -> SnapshotRef:
        # spec §17: snapshot_id and model_revision intentionally carry the same digest under
        # different public type prefixes.
        snapshot_digest = self.snapshot_id.rsplit(":", 1)[-1]
        model_digest = self.model_revision.split(":", 1)[-1]
        if snapshot_digest != model_digest:
            raise ValueError("snapshot_id and model_revision must carry the same digest")
        return self


class ObservationContextRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    context_id: str = Field(pattern=_CONTEXT_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=_ENVIRONMENT_PATTERN)
    window_start: datetime
    window_end: datetime

    # window_start/window_end having an *explicit* RFC 3339 offset (spec §16.1) is not encodable
    # as a JSON Schema keyword without pulling in an RFC 3339 format-checker dependency this repo
    # doesn't otherwise need - it stays a Pydantic-only check, same as the cross-field window
    # bounds below.
    @field_validator("window_start", "window_end")
    @classmethod
    def _check_explicit_offset(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("window_start/window_end require an explicit RFC 3339 UTC offset")
        return value

    @model_validator(mode="after")
    def _check_window_bounds(self) -> ObservationContextRef:
        if self.window_start > self.window_end:
            raise ValueError("window_start must be less than or equal to window_end")
        if self.window_end - self.window_start > _MAX_OBSERVATION_WINDOW:
            raise ValueError("the inclusive observation window must not exceed 31 days")
        return self


def _entity_ref_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the type-specific field rules (spec §11.1) as JSON Schema if/else so external
    (non-Pydantic) validators reject the same invalid shapes. The Python model_validator below
    is still authoritative at runtime - this only mirrors it for the committed schema."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {"properties": {"type": {"const": "OPERATION"}}, "required": ["type"]},
            "else": {"properties": {"method": {"type": "null"}, "path": {"type": "null"}}},
        },
        {
            "if": {"properties": {"type": {"const": "QUEUE"}}, "required": ["type"]},
            "else": {"properties": {"protocol": {"type": "null"}, "namespace": {"type": "null"}}},
        },
    ]


class EntityRef(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_entity_ref_schema_extra
    )

    id: str
    type: EntityType
    name: str
    method: str | None = None
    path: str | None = None
    protocol: str | None = None
    namespace: str | None = None

    @model_validator(mode="after")
    def _check_type_specific_fields(self) -> EntityRef:
        if self.type != EntityType.OPERATION and (self.method is not None or self.path is not None):
            raise ValueError("method/path are only allowed when type == OPERATION")
        if self.type != EntityType.QUEUE and (
            self.protocol is not None or self.namespace is not None
        ):
            raise ValueError("protocol/namespace are only allowed when type == QUEUE")
        return self


def _delivery_ref_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the fixed (kind, relation_type, via.type) pairs table (spec §11.2/§13) as JSON
    Schema if/then so external (non-Pydantic) validators reject the same invalid combinations.
    The Python model_validator below is still authoritative at runtime - this only mirrors it
    for the committed schema."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {"properties": {"kind": {"const": "SYNC_HTTP"}}, "required": ["kind"]},
            "then": {
                "properties": {
                    "relation_type": {"const": "CALLS"},
                    "via": {"properties": {"type": {"const": "OPERATION"}}, "required": ["type"]},
                },
                "required": ["relation_type", "via"],
            },
        },
        {
            "if": {"properties": {"kind": {"const": "ASYNC_MESSAGE"}}, "required": ["kind"]},
            "then": {
                "properties": {
                    "relation_type": {"const": "SENDS"},
                    "via": {"properties": {"type": {"const": "QUEUE"}}, "required": ["type"]},
                },
                "required": ["relation_type", "via"],
            },
        },
    ]


class DeliveryRef(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_delivery_ref_schema_extra
    )

    kind: DeliveryKind
    relation_type: DeliveryRelationType
    via: EntityRef

    @model_validator(mode="after")
    def _check_allowed_pair(self) -> DeliveryRef:
        pair = (self.kind, self.relation_type, self.via.type)
        if pair not in _ALLOWED_DELIVERY_PAIRS:
            raise ValueError(
                f"unsupported delivery (kind, relation_type, via.type) combination: {pair}"
            )
        return self


def _dependency_claim_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the coverage/resolution-evidence conditionals (spec §14/§15) as JSON Schema
    if/then so external (non-Pydantic) validators reject the same invalid shapes. The Python
    model_validator below is still authoritative at runtime - this only mirrors it for the
    committed schema."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {
                "properties": {"qualification": {"const": "NOT_OBSERVED_IN_WINDOW"}},
                "required": ["qualification"],
            },
            "then": {"properties": {"coverage": {"not": {"type": "null"}}}},
            "else": {"properties": {"coverage": {"type": "null"}}},
        },
        {
            "if": {
                "properties": {"destination_resolution": {"const": "RESOLVED_SERVICE"}},
                "required": ["destination_resolution"],
            },
            "then": {"properties": {"resolution_evidence_refs": {"minItems": 1}}},
            "else": {"properties": {"resolution_evidence_refs": {"maxItems": 0}}},
        },
    ]


class DependencyClaim(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_dependency_claim_schema_extra
    )

    claim_id: str = Field(pattern=_CLAIM_ID_PATTERN)
    subject: EntityRef
    predicate: DependencyPredicate
    object: EntityRef
    destination_resolution: DestinationResolution
    delivery: DeliveryRef
    qualification: Qualification
    coverage: Coverage | None
    evidence_refs: list[str] = Field(min_length=1, json_schema_extra={"uniqueItems": True})
    resolution_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("evidence_refs", "resolution_evidence_refs")
    @classmethod
    def _check_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError(
                "evidence references must be sorted lexicographically and deduplicated"
            )
        return value

    @model_validator(mode="after")
    def _check_coverage_and_evidence(self) -> DependencyClaim:
        if self.qualification == Qualification.NOT_OBSERVED_IN_WINDOW:
            if self.coverage is None:
                raise ValueError("coverage is required for NOT_OBSERVED_IN_WINDOW claims")
        elif self.coverage is not None:
            raise ValueError("coverage is only meaningful for NOT_OBSERVED_IN_WINDOW claims")

        if not self.evidence_refs:
            raise ValueError("evidence_refs must not be empty")

        if self.destination_resolution == DestinationResolution.RESOLVED_SERVICE:
            if not self.resolution_evidence_refs:
                raise ValueError(
                    "resolution_evidence_refs must not be empty when "
                    "destination_resolution == RESOLVED_SERVICE"
                )
        elif self.resolution_evidence_refs:
            raise ValueError(
                "resolution_evidence_refs must be empty when "
                "destination_resolution == DIRECT_TARGET_FALLBACK"
            )

        return self


class Limitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: LimitationCode
    message: str
    claim_ids: list[str] = Field(default_factory=list, json_schema_extra={"uniqueItems": True})

    @field_validator("claim_ids")
    @classmethod
    def _check_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("claim_ids must be sorted lexicographically and deduplicated")
        return value


class ServiceDependenciesData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service: EntityRef
    dependency_claim_ids: list[str]


class SupportedFact(BaseModel):
    """v0.4.0 I2.1 - spec §11.2: one existing canonical relation fact an evidence record supports.
    Not a generic graph record and not a new architecture claim - only the 3 bounded fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relation_type: EvidenceRelationType
    source_id: str
    target_id: str


def _supported_fact_sort_key(fact: SupportedFact) -> tuple[str, str, str]:
    return (fact.relation_type.value, fact.source_id, fact.target_id)


class ObservedEvidenceMetadata(BaseModel):
    """v0.4.0 I2.1 - spec §11.2: bounded observed-evidence metadata only. No raw payloads,
    authorization values, full spans, baggage, resource attributes, or sample trace ids."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str
    bucket_start: datetime
    bucket_end: datetime
    first_seen: datetime
    last_seen: datetime
    observation_count: int
    service_version: str | None
    correlation_mode: str | None


class EvidenceRecord(BaseModel):
    """v0.4.0 I2.1 - spec §11.2. `evidence_type`/`source_type` reuse the existing
    `app.provenance.model` enums rather than redefining them - no new adapter classification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    evidence_type: EvidenceType
    source_type: SourceType
    source_locator: str | None
    source_revision: str | None
    observation: ObservedEvidenceMetadata | None
    supports: list[SupportedFact]

    @field_validator("supports")
    @classmethod
    def _check_supports_sorted_and_deduplicated(
        cls, value: list[SupportedFact]
    ) -> list[SupportedFact]:
        keys = [_supported_fact_sort_key(fact) for fact in value]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError(
                "supports must be sorted by (relation_type, source_id, target_id) and deduplicated"
            )
        return value


class EvidenceData(BaseModel):
    """v0.4.0 I2.1 - spec §11.2/§12. `claims`/top-level `evidence_refs` on the enclosing
    `ArchitectureAnswer` stay empty for this tool - lookup creates no claim; resolved ids live here."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    records: list[EvidenceRecord]
    missing_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("requested_evidence_refs", "missing_evidence_refs")
    @classmethod
    def _check_refs_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("must be sorted lexicographically and deduplicated")
        return value

    @field_validator("records")
    @classmethod
    def _check_records_sorted_by_id(cls, value: list[EvidenceRecord]) -> list[EvidenceRecord]:
        ids = [record.id for record in value]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("records must be sorted by id and deduplicated")
        return value


def _claim_sort_key(claim: DependencyClaim) -> tuple[str, str, str, str]:
    return (claim.object.id, claim.delivery.kind.value, claim.delivery.via.id, claim.claim_id)


def _architecture_answer_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode two more envelope invariants (spec §8.3/§9) as JSON Schema if/then/contains so
    external (non-Pydantic) validators reject the same invalid shapes. The Python
    model_validator below is still authoritative at runtime - this only mirrors it for the
    committed schema."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {
                "properties": {"outcome": {"enum": ["ANSWERED", "PARTIAL"]}},
                "required": ["outcome"],
            },
            "then": {"properties": {"data": {"not": {"type": "null"}}}},
        },
        {
            "if": {
                "properties": {
                    "observation_context": {"type": "null"},
                    "tool": {"const": "get_service_dependencies"},
                },
                "required": ["observation_context", "tool"],
            },
            "then": {
                "properties": {
                    "limitations": {
                        "contains": {
                            "properties": {"code": {"const": "OBSERVATION_CONTEXT_REQUIRED"}},
                            "required": ["code"],
                        }
                    }
                },
                "required": ["limitations"],
            },
        },
    ]


# v0.4.0 I2.1 - spec §3/§14's first sanctioned extension point: only `get_service_dependencies`
# requires a non-null `observation_context` (or an explicit OBSERVATION_CONTEXT_REQUIRED
# limitation); `get_evidence`'s `observation_context` is always null (spec §12) regardless of
# outcome, including outcomes where `data` is also null - `tool`, not `data`'s type, is the only
# discriminator that's always present to key off.
_TOOLS_REQUIRING_OBSERVATION_CONTEXT = frozenset({"get_service_dependencies"})


class ArchitectureAnswer[T: BaseModel](BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_architecture_answer_schema_extra
    )

    schema_version: Literal["0.4"]
    producer: Producer
    tool: Literal["get_service_dependencies", "get_evidence"]
    outcome: Outcome
    snapshot: SnapshotRef | None
    observation_context: ObservationContextRef | None
    data: T | None
    claims: list[DependencyClaim]
    evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    limitations: list[Limitation]

    @model_validator(mode="after")
    def _check_envelope_invariants(self) -> ArchitectureAnswer[T]:
        if self.outcome != Outcome.NOT_ANSWERED and self.data is None:
            raise ValueError("data must not be null for ANSWERED/PARTIAL outcomes")

        has_context_required_limitation = any(
            limitation.code == LimitationCode.OBSERVATION_CONTEXT_REQUIRED
            for limitation in self.limitations
        )
        if (
            self.tool in _TOOLS_REQUIRING_OBSERVATION_CONTEXT
            and self.observation_context is None
            and not has_context_required_limitation
        ):
            raise ValueError(
                "observation_context may only be null when a limitation with code "
                "OBSERVATION_CONTEXT_REQUIRED is present"
            )

        expected_evidence_refs = sorted(
            {
                ref
                for claim in self.claims
                for ref in (*claim.evidence_refs, *claim.resolution_evidence_refs)
            }
        )
        if self.evidence_refs != expected_evidence_refs:
            raise ValueError(
                "evidence_refs must be the sorted, deduplicated union of every claim's "
                "evidence_refs and resolution_evidence_refs"
            )

        if isinstance(self.data, ServiceDependenciesData):
            expected_claim_ids = [claim.claim_id for claim in self.claims]
            if self.data.dependency_claim_ids != expected_claim_ids:
                raise ValueError(
                    "data.dependency_claim_ids must equal claims[*].claim_id in the same order"
                )

        claim_sort_keys = [_claim_sort_key(claim) for claim in self.claims]
        if claim_sort_keys != sorted(claim_sort_keys):
            raise ValueError(
                "claims must be sorted by (object.id, delivery.kind, delivery.via.id, claim_id)"
            )

        return self
