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
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SNAPSHOT_ID_RE = re.compile(r"^aip:snapshot:v\d+:.+$")
_MODEL_REVISION_RE = re.compile(r"^sha256:.+$")
_CONTEXT_ID_RE = re.compile(r"^aip:observation-context:v\d+:.+$")
_CLAIM_ID_RE = re.compile(r"^aip:claim:v\d+:.+$")


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

    name: Literal["architecture-intelligence-platform"] = "architecture-intelligence-platform"
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
    coverage: Coverage | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    resolution_evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("claim_id")
    @classmethod
    def _check_claim_id(cls, value: str) -> str:
        if not _CLAIM_ID_RE.match(value):
            raise ValueError(f"claim_id must match {_CLAIM_ID_RE.pattern!r}: {value!r}")
        return value

    @model_validator(mode="after")
    def _check_coverage_and_evidence(self) -> DependencyClaim:
        if self.coverage is not None and self.qualification != Qualification.NOT_OBSERVED_IN_WINDOW:
            raise ValueError("coverage is only meaningful for NOT_OBSERVED_IN_WINDOW claims")
        if not self.evidence_refs:
            raise ValueError("evidence_refs must not be empty")
        return self


class Limitation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: LimitationCode
    message: str
    claim_ids: list[str] = Field(default_factory=list)


class ServiceDependenciesData(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service: EntityRef
    dependency_claim_ids: list[str] = Field(default_factory=list)


class ArchitectureAnswer[T: BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["0.4"] = "0.4"
    producer: Producer
    tool: str
    outcome: Outcome
    snapshot: SnapshotRef | None = None
    observation_context: ObservationContextRef | None = None
    data: T | None = None
    claims: list[DependencyClaim] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    limitations: list[Limitation] = Field(default_factory=list)

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

        return self
