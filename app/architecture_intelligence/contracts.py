"""v0.4.0 I1.1 - the frozen public architecture-answer contract (spec
docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md).

This module defines only the data contract: `ArchitectureAnswer[T]`, its envelope invariants, and
the `get_service_dependencies` payload shape. It intentionally contains no service logic, no Neo4j
access, and no snapshot/observation-context hashing - those land in later I1 sub-increments. The
enums here (Qualification, Coverage) mirror app.analysis.runtime's literal values by value, not by
import, so this public contract doesn't couple to internal analysis-module churn.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_HEX = r"[0-9a-f]{64}"
_SNAPSHOT_ID_RE = re.compile(rf"^aip:snapshot:v1:{_SHA256_HEX}$")
_MODEL_REVISION_RE = re.compile(rf"^sha256:{_SHA256_HEX}$")
_CONTEXT_ID_RE = re.compile(rf"^aip:observation-context:v1:{_SHA256_HEX}$")
_CLAIM_ID_RE = re.compile(rf"^aip:claim:v1:{_SHA256_HEX}$")

_MAX_OBSERVATION_WINDOW = timedelta(days=31)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


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

    snapshot_id: str
    model_revision: str

    @field_validator("snapshot_id")
    @classmethod
    def _check_snapshot_id(cls, value: str) -> str:
        if not _SNAPSHOT_ID_RE.match(value):
            raise ValueError(f"snapshot_id must match {_SNAPSHOT_ID_RE.pattern!r}: {value!r}")
        return value

    @field_validator("model_revision")
    @classmethod
    def _check_model_revision(cls, value: str) -> str:
        if not _MODEL_REVISION_RE.match(value):
            raise ValueError(f"model_revision must match {_MODEL_REVISION_RE.pattern!r}: {value!r}")
        return value


class ObservationContextRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    context_id: str
    environment: str
    window_start: datetime
    window_end: datetime

    @field_validator("context_id")
    @classmethod
    def _check_context_id(cls, value: str) -> str:
        if not _CONTEXT_ID_RE.match(value):
            raise ValueError(f"context_id must match {_CONTEXT_ID_RE.pattern!r}: {value!r}")
        return value

    @field_validator("environment")
    @classmethod
    def _check_environment(cls, value: str) -> str:
        if not 1 <= len(value) <= 128:
            raise ValueError("environment must be 1..128 Unicode code points")
        if _CONTROL_CHAR_RE.search(value):
            raise ValueError("environment must not contain control characters")
        if value != value.strip():
            raise ValueError("environment must not have leading or trailing whitespace")
        return value

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


class EntityRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

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


class DeliveryRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

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


class DependencyClaim(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    claim_id: str
    subject: EntityRef
    predicate: DependencyPredicate
    object: EntityRef
    destination_resolution: DestinationResolution
    delivery: DeliveryRef
    qualification: Qualification
    coverage: Coverage | None
    evidence_refs: list[str]
    resolution_evidence_refs: list[str]

    @field_validator("claim_id")
    @classmethod
    def _check_claim_id(cls, value: str) -> str:
        if not _CLAIM_ID_RE.match(value):
            raise ValueError(f"claim_id must match {_CLAIM_ID_RE.pattern!r}: {value!r}")
        return value

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
    claim_ids: list[str] = Field(default_factory=list)


class ServiceDependenciesData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service: EntityRef
    dependency_claim_ids: list[str]


def _claim_sort_key(claim: DependencyClaim) -> tuple[str, str, str, str]:
    return (claim.object.id, claim.delivery.kind.value, claim.delivery.via.id, claim.claim_id)


class ArchitectureAnswer[T: BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["0.4"]
    producer: Producer
    tool: str
    outcome: Outcome
    snapshot: SnapshotRef | None
    observation_context: ObservationContextRef | None
    data: T | None
    claims: list[DependencyClaim]
    evidence_refs: list[str]
    limitations: list[Limitation]

    @model_validator(mode="after")
    def _check_envelope_invariants(self) -> ArchitectureAnswer[T]:
        if self.outcome != Outcome.NOT_ANSWERED and self.data is None:
            raise ValueError("data must not be null for ANSWERED/PARTIAL outcomes")

        has_context_required_limitation = any(
            limitation.code == LimitationCode.OBSERVATION_CONTEXT_REQUIRED
            for limitation in self.limitations
        )
        if self.observation_context is None and not has_context_required_limitation:
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
