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
from typing import Annotated, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.provenance.model import EvidenceType, SourceType

_SHA256_HEX = r"[0-9a-f]{64}"
_SNAPSHOT_ID_PATTERN = rf"^aip:snapshot:v1:{_SHA256_HEX}$"
_MODEL_REVISION_PATTERN = rf"^sha256:{_SHA256_HEX}$"
_CONTEXT_ID_PATTERN = rf"^aip:observation-context:v1:{_SHA256_HEX}$"
_CLAIM_ID_PATTERN = rf"^aip:claim:v1:{_SHA256_HEX}$"
# I3 spec §13.2: DeploymentResolution.resolution_id is a distinct public identity from claim_id -
# it identifies a snapshot-bound reconciliation-candidate-group evaluation, not a claim.
_DEPLOYMENT_RESOLUTION_ID_PATTERN = rf"^aip:deployment-resolution:v1:{_SHA256_HEX}$"

# No leading/trailing whitespace and no control characters anywhere (spec §16.1). Expressed as a
# single character-class-only pattern (no lookaround) so it also compiles under pydantic-core's
# Rust regex engine and therefore shows up as a real `pattern` in the generated JSON Schema.
_ENVIRONMENT_PATTERN = r"^[^\s\x00-\x1f\x7f](?:[^\x00-\x1f\x7f]*[^\s\x00-\x1f\x7f])?$"

_MAX_OBSERVATION_WINDOW = timedelta(days=31)

ArchitectureSchemaVersion = Literal["0.5"]
ARCHITECTURE_SCHEMA_VERSION: ArchitectureSchemaVersion = get_args(ArchitectureSchemaVersion)[0]
ArchitectureToolName = Literal["get_service_dependencies", "get_evidence", "get_architecture_drift"]
TOOL_NAMES: tuple[ArchitectureToolName, ...] = get_args(ArchitectureToolName)[::-1]

# I3 spec §6: the frozen I3 reconciliation rule identity.
DeploymentReconciliationRuleId = Literal["service-workload-reconciliation"]
DEPLOYMENT_RECONCILIATION_RULE_ID: DeploymentReconciliationRuleId = get_args(
    DeploymentReconciliationRuleId
)[0]


class Outcome(StrEnum):
    ANSWERED = "ANSWERED"
    PARTIAL = "PARTIAL"
    NOT_ANSWERED = "NOT_ANSWERED"


class EntityType(StrEnum):
    SERVICE = "SERVICE"
    OPERATION = "OPERATION"
    QUEUE = "QUEUE"
    WORKLOAD = "WORKLOAD"
    # v0.5.0 I4 spec §12.1.
    TOPIC = "TOPIC"
    SUBSCRIPTION = "SUBSCRIPTION"


class WorkloadKind(StrEnum):
    """I3 spec §8.1: the exact supported Kubernetes controller kinds a deployment identity path may
    resolve to - the same closed set I2's own owner-chain resolution already admits."""

    DEPLOYMENT = "DEPLOYMENT"
    STATEFULSET = "STATEFULSET"
    DAEMONSET = "DAEMONSET"


class DeliveryKind(StrEnum):
    SYNC_HTTP = "SYNC_HTTP"
    ASYNC_MESSAGE = "ASYNC_MESSAGE"


class DeliveryRelationType(StrEnum):
    CALLS = "CALLS"
    SENDS = "SENDS"
    PUBLISHES_TO = "PUBLISHES_TO"  # v0.5.0 I4 spec §12.2


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
    # I3 spec §19 - deployment-reconciliation-specific limitation codes.
    DEPLOYMENT_IDENTITY_UNRESOLVED = "DEPLOYMENT_IDENTITY_UNRESOLVED"
    DEPLOYMENT_IDENTITY_AMBIGUOUS = "DEPLOYMENT_IDENTITY_AMBIGUOUS"
    DEPLOYMENT_IDENTITY_CONFLICT = "DEPLOYMENT_IDENTITY_CONFLICT"
    DEPLOYMENT_ENVIRONMENT_MISMATCH = "DEPLOYMENT_ENVIRONMENT_MISMATCH"
    DEPLOYMENT_TEMPORAL_MISMATCH = "DEPLOYMENT_TEMPORAL_MISMATCH"
    DEPLOYMENT_EVIDENCE_INCOMPLETE = "DEPLOYMENT_EVIDENCE_INCOMPLETE"
    DEPLOYMENT_RESULT_LIMIT_EXCEEDED = "DEPLOYMENT_RESULT_LIMIT_EXCEEDED"


class DependencyPredicate(StrEnum):
    DIRECT_DEPENDENCY = "DIRECT_DEPENDENCY"


class EvidenceRelationType(StrEnum):
    """v0.4.0 I2.1 - the closed set of canonical graph relation kinds (spec §11.2's `supports`),
    widened by I3 (DEPLOYED_AS) and v0.5.0 I4 (PUBLISHES_TO/SUBSCRIPTION_OF). Deliberately its own
    closed enum rather than reusing `DeliveryRelationType` (only the delivery relations) or a
    graph-layer string - `get_evidence` describes existing facts, never a new architecture claim."""

    PROVIDES = "PROVIDES"
    CALLS = "CALLS"
    SENDS = "SENDS"
    RECEIVES_FROM = "RECEIVES_FROM"
    CARRIES = "CARRIES"
    CONFORMS_TO = "CONFORMS_TO"
    DEAD_LETTERS_TO = "DEAD_LETTERS_TO"
    DEPLOYED_AS = "DEPLOYED_AS"  # I3 spec §16.1
    # v0.5.0 I4 spec §12.1: exactly these two are added; RECEIVES_FROM and CARRIES are reused.
    PUBLISHES_TO = "PUBLISHES_TO"
    SUBSCRIPTION_OF = "SUBSCRIPTION_OF"


# Fixed (kind, relation_type, via.type) pairs - spec §11.2/§13. No other combination is valid.
_ALLOWED_DELIVERY_PAIRS = {
    (DeliveryKind.SYNC_HTTP, DeliveryRelationType.CALLS, EntityType.OPERATION),
    (DeliveryKind.ASYNC_MESSAGE, DeliveryRelationType.SENDS, EntityType.QUEUE),
    # v0.5.0 I4 spec §12.2.
    (DeliveryKind.ASYNC_MESSAGE, DeliveryRelationType.PUBLISHES_TO, EntityType.TOPIC),
}

# v0.5.0 I4 spec §12.1: `EntityRef` may carry bounded protocol/namespace metadata for these only.
_DESTINATION_ENTITY_TYPES = frozenset({EntityType.QUEUE, EntityType.TOPIC, EntityType.SUBSCRIPTION})


ProducerName = Literal["architecture-intelligence-platform"]
PRODUCER_NAME: ProducerName = get_args(ProducerName)[0]


class Producer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ProducerName
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
            "if": {
                "properties": {"type": {"enum": sorted(_DESTINATION_ENTITY_TYPES)}},
                "required": ["type"],
            },
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
        if self.type not in _DESTINATION_ENTITY_TYPES and (
            self.protocol is not None or self.namespace is not None
        ):
            raise ValueError(
                "protocol/namespace are only allowed when type is QUEUE/TOPIC/SUBSCRIPTION"
            )
        return self


class WorkloadRef(BaseModel):
    """I3 spec §11: a bounded public Workload reference, deliberately its own model rather than an
    `EntityRef` extension. `EntityRef` is reused by `DependencyClaim.subject`/`.object` and
    `DeliveryRef.via` - widening its type-specific-field validator with a WORKLOAD branch would make
    a Workload-shaped `EntityRef` constructible inside a dependency claim, exactly the governing
    "DEPLOYED_AS != CALLS" / entity-equivalence boundary spec §1 forbids. `DeploymentClaim.object` is
    typed `WorkloadRef`, never `EntityRef`, for the same reason.

    Cluster UID, Pod UID, source inventory, resource UID, and owner-chain details remain evidence
    drill-down, not fields of this relation target (spec §11's own rule) - `namespace` here is
    identity context, not a locality qualification.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    # No default (PR #212 review finding): a Pydantic field default is omitted from the generated
    # JSON Schema's `required` list, so a defaulted discriminator/identity field is NOT actually
    # required for a non-Pydantic client validating against the committed schema - required here so
    # `type` is a real, always-present field, not a silently-fillable one.
    type: Literal[EntityType.WORKLOAD]
    name: str
    workload_kind: WorkloadKind
    namespace: str


def _delivery_ref_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the fixed (kind, relation_type, via.type) pairs table (spec §11.2/§13, widened by
    v0.5.0 I4 spec §12.2) and the I4 `subscription` invariants as JSON Schema if/then so external
    (non-Pydantic) validators reject the same invalid combinations. The Python model_validator
    below is still authoritative at runtime - this only mirrors it for the committed schema."""
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
                "properties": {"relation_type": {"enum": ["PUBLISHES_TO", "SENDS"]}},
                "required": ["relation_type", "via"],
            },
        },
        {
            "if": {
                "properties": {"relation_type": {"const": "SENDS"}},
                "required": ["relation_type"],
            },
            "then": {
                "properties": {
                    "via": {"properties": {"type": {"const": "QUEUE"}}, "required": ["type"]},
                },
                "required": ["via"],
            },
        },
        {
            "if": {
                "properties": {"relation_type": {"const": "PUBLISHES_TO"}},
                "required": ["relation_type"],
            },
            "then": {
                "properties": {
                    "via": {"properties": {"type": {"const": "TOPIC"}}, "required": ["type"]},
                },
                "required": ["via"],
            },
        },
        # I4 spec §12.2: `subscription` is null unless `via` is a Topic, and a non-null
        # `subscription` is a SUBSCRIPTION-typed ref.
        {
            "if": {
                "properties": {
                    "via": {"properties": {"type": {"const": "TOPIC"}}, "required": ["type"]},
                },
                "required": ["via"],
            },
            "else": {"properties": {"subscription": {"type": "null"}}},
        },
        {
            "properties": {
                "subscription": {
                    "anyOf": [
                        {"type": "null"},
                        {"properties": {"type": {"const": "SUBSCRIPTION"}}, "required": ["type"]},
                    ]
                }
            }
        },
    ]


class DeliveryRef(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_delivery_ref_schema_extra
    )

    kind: DeliveryKind
    relation_type: DeliveryRelationType
    via: EntityRef
    # v0.5.0 I4 spec §12.2: the optional Pub/Sub Subscription route. Always emitted (as null when
    # absent), like `EntityRef`'s own optional fields. That the Subscription is `SUBSCRIPTION_OF`
    # the `via` Topic in the same snapshot is a projection invariant (graph-dependent), not a
    # model rule.
    subscription: EntityRef | None = None

    @model_validator(mode="after")
    def _check_allowed_pair(self) -> DeliveryRef:
        pair = (self.kind, self.relation_type, self.via.type)
        if pair not in _ALLOWED_DELIVERY_PAIRS:
            raise ValueError(
                f"unsupported delivery (kind, relation_type, via.type) combination: {pair}"
            )
        if self.subscription is not None:
            if self.via.type != EntityType.TOPIC:
                raise ValueError("subscription is only allowed when via.type == TOPIC")
            if self.subscription.type != EntityType.SUBSCRIPTION:
                raise ValueError("subscription.type must be SUBSCRIPTION")
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
        # I3 spec §1: "DEPLOYED_AS != CALLS" / entity-equivalence boundary. EntityType.WORKLOAD
        # exists as of I3 (spec §11), so a dependency claim must reject it explicitly here - a
        # generic EntityRef otherwise has no runtime/schema constraint stopping a Workload-shaped
        # value from being used as a dependency claim's subject/object.
        {
            "properties": {
                "subject": {"properties": {"type": {"const": "SERVICE"}}},
                "object": {"properties": {"type": {"not": {"const": "WORKLOAD"}}}},
            }
        },
    ]


class DependencyClaim(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_dependency_claim_schema_extra
    )

    claim_id: str = Field(pattern=_CLAIM_ID_PATTERN)
    subject: EntityRef
    # No default (PR #212 review finding) - see WorkloadRef.type's own comment on why a
    # discriminator field must never be defaulted.
    predicate: Literal[DependencyPredicate.DIRECT_DEPENDENCY]
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
    def _check_subject_and_object_types(self) -> DependencyClaim:
        # I3 spec §1: a dependency claim is never a deployment-identity claim - EntityType.WORKLOAD
        # (added in I3) must never appear here, mirroring _dependency_claim_schema_extra above.
        if self.subject.type != EntityType.SERVICE:
            raise ValueError("subject.type must be SERVICE for a dependency claim")
        if self.object.type == EntityType.WORKLOAD:
            raise ValueError("object.type must not be WORKLOAD for a dependency claim")
        return self

    @model_validator(mode="after")
    def _check_coverage_and_evidence(self) -> DependencyClaim:
        if self.qualification == Qualification.NOT_OBSERVED_IN_WINDOW:
            if self.coverage is None:
                raise ValueError("coverage is required for NOT_OBSERVED_IN_WINDOW claims")
        elif self.coverage is not None:
            raise ValueError("coverage is only meaningful for NOT_OBSERVED_IN_WINDOW claims")

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


class DeploymentPredicate(StrEnum):
    DEPLOYED_AS = "DEPLOYED_AS"


class DeploymentResolutionMethod(StrEnum):
    """I3 spec §10.1: only the three *successful* identity-path outcomes - never CONFLICT/
    AMBIGUOUS/UNRESOLVED, which are never a "method" a claim can be supported by. Compare
    `DeploymentResolutionStatus` below, which is the wider 6-value outcome set a
    `DeploymentResolution` (as opposed to an actual `DeploymentClaim`) may carry."""

    RESOLVED_EXPLICIT = "RESOLVED_EXPLICIT"
    RESOLVED_CONFIGURED = "RESOLVED_CONFIGURED"
    RESOLVED_OBSERVED = "RESOLVED_OBSERVED"


# I3 spec §10.1's canonical supporting-method strength order - lower is stronger. Reused for both
# DeploymentClaim.supporting_methods and DeploymentResolution.supporting_methods so the same
# semantic field sorts identically wherever it appears.
_DEPLOYMENT_METHOD_STRENGTH = {
    DeploymentResolutionMethod.RESOLVED_EXPLICIT: 0,
    DeploymentResolutionMethod.RESOLVED_CONFIGURED: 1,
    DeploymentResolutionMethod.RESOLVED_OBSERVED: 2,
}


def _check_supporting_methods_canonical_order(
    value: list[DeploymentResolutionMethod],
) -> list[DeploymentResolutionMethod]:
    if len(set(value)) != len(value):
        raise ValueError("supporting_methods must be deduplicated")
    if value != sorted(value, key=lambda method: _DEPLOYMENT_METHOD_STRENGTH[method]):
        raise ValueError(
            "supporting_methods must be sorted by §10.1 canonical strength "
            "(RESOLVED_EXPLICIT > RESOLVED_CONFIGURED > RESOLVED_OBSERVED)"
        )
    return value


def _deployment_claim_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode "resolution_method == the strongest (canonically-first) entry of supporting_methods"
    (spec §10.1/§12) and "subject.type == SERVICE" as JSON Schema if/then/const so external
    validators reject the same invalid shapes the Python model_validators below enforce at runtime.
    Mirrors `_dependency_claim_schema_extra`'s own `subject.type` constraint (PR #212 re-review
    finding: the runtime-only version left the committed schema accepting an invalid subject)."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        *(
            {
                "if": {
                    "properties": {
                        "supporting_methods": {"prefixItems": [{"const": method.value}]}
                    },
                    "required": ["supporting_methods"],
                },
                "then": {"properties": {"resolution_method": {"const": method.value}}},
            }
            for method in DeploymentResolutionMethod
        ),
        {"properties": {"subject": {"properties": {"type": {"const": "SERVICE"}}}}},
    ]


class DeploymentClaim(BaseModel):
    """I3 spec §12: the public `Service -[DEPLOYED_AS]-> Workload` claim. Deliberately has no
    `delivery`/`qualification`/`coverage`/`destination_resolution` fields - those are
    `DependencyClaim`-only concepts describing a CALLS/SENDS interaction, and `DEPLOYED_AS` is never
    an interaction (spec §1: "DEPLOYED_AS != CALLS != SENDS != RECEIVES_FROM")."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_deployment_claim_schema_extra
    )

    claim_id: str = Field(pattern=_CLAIM_ID_PATTERN)
    subject: EntityRef
    # No default (PR #212 review finding) - see WorkloadRef.type's own comment: a defaulted
    # discriminator/identity field is silently omitted from the generated JSON Schema's `required`
    # list, so it is NOT actually required for a non-Pydantic client. Applies to `predicate` (the
    # union discriminator) and both `reconciliation_rule_*` fields (frozen identity, not
    # convenience) below.
    predicate: Literal[DeploymentPredicate.DEPLOYED_AS]
    object: WorkloadRef
    resolution_method: DeploymentResolutionMethod
    supporting_methods: list[DeploymentResolutionMethod] = Field(
        min_length=1, json_schema_extra={"uniqueItems": True}
    )
    reconciliation_rule_id: DeploymentReconciliationRuleId
    reconciliation_rule_version: Literal[1]
    evidence_refs: list[str] = Field(min_length=1, json_schema_extra={"uniqueItems": True})

    @field_validator("evidence_refs")
    @classmethod
    def _check_evidence_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError(
                "evidence references must be sorted lexicographically and deduplicated"
            )
        return value

    @field_validator("supporting_methods")
    @classmethod
    def _check_supporting_methods(
        cls, value: list[DeploymentResolutionMethod]
    ) -> list[DeploymentResolutionMethod]:
        return _check_supporting_methods_canonical_order(value)

    @model_validator(mode="after")
    def _check_subject_type_and_resolution_method(self) -> DeploymentClaim:
        # I3 spec §1: DEPLOYED_AS relates a Service to a Workload, never anything else.
        if self.subject.type != EntityType.SERVICE:
            raise ValueError("subject.type must be SERVICE for a deployment claim")
        if self.resolution_method != self.supporting_methods[0]:
            raise ValueError(
                "resolution_method must equal the strongest (first) entry in supporting_methods"
            )
        return self


class DeploymentResolutionStatus(StrEnum):
    """I3 spec §13.3: the wider 6-value outcome set a `DeploymentResolution` may carry - the three
    successful `DeploymentResolutionMethod` values plus the three non-resolved outcomes. Kept as its
    own enum (not reusing `DeploymentResolutionMethod`) since CONFLICT/AMBIGUOUS/UNRESOLVED are never
    valid `DeploymentClaim.resolution_method`/`.supporting_methods` values (spec §10.1: "Similarity is
    never a successful path" - and conflict/ambiguity are never "methods" either)."""

    RESOLVED_EXPLICIT = "RESOLVED_EXPLICIT"
    RESOLVED_CONFIGURED = "RESOLVED_CONFIGURED"
    RESOLVED_OBSERVED = "RESOLVED_OBSERVED"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


def _deployment_resolution_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the Resolved/Non-resolved invariants (spec §13.3) as JSON Schema if/then/else so
    external validators reject the same invalid shapes. The Python model_validator below is still
    authoritative at runtime. `candidate_service_ids == [service_id]` is NOT mirrored here - like
    `ArchitectureAnswer`'s own evidence_refs-union invariant, a cross-property array-content equality
    has no standard JSON Schema expression without the unsupported `$data` extension."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {"properties": {"status": {"pattern": "^RESOLVED_"}}, "required": ["status"]},
            "then": {
                "properties": {
                    "workload": {"not": {"type": "null"}},
                    "service_id": {"not": {"type": "null"}},
                    "claim_id": {"not": {"type": "null"}},
                    "supporting_methods": {"minItems": 1},
                }
            },
            "else": {"properties": {"claim_id": {"type": "null"}}},
        },
    ]


class DeploymentResolution(BaseModel):
    """I3 spec §13.3: the public resolution-outcome shape, returned for every reconciliation
    candidate group whether it produced a claim or not - "Resolved and non-resolved outcomes SHALL
    be inspectable without fabricating a claim." """

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_deployment_resolution_schema_extra
    )

    resolution_id: str = Field(pattern=_DEPLOYMENT_RESOLUTION_ID_PATTERN)
    workload: WorkloadRef | None
    status: DeploymentResolutionStatus
    service_id: str | None
    candidate_service_ids: list[str] = Field(json_schema_extra={"uniqueItems": True})
    supporting_methods: list[DeploymentResolutionMethod] = Field(
        json_schema_extra={"uniqueItems": True}
    )
    supporting_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    conflicting_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    limitation_codes: list[LimitationCode] = Field(json_schema_extra={"uniqueItems": True})
    # PR #212 re-review finding: `Field(pattern=...)` works directly on `str | None` in this
    # Pydantic version (verified live - it generates `anyOf: [{type: string, pattern: ...},
    # {type: null}]` and enforces the pattern only on the non-null branch), so this needs no
    # separate field_validator/schema mirror - both layers get the same constraint from one place.
    claim_id: str | None = Field(pattern=_CLAIM_ID_PATTERN)
    # No default (PR #212 review finding) - see WorkloadRef.type's own comment.
    reconciliation_rule_id: DeploymentReconciliationRuleId
    reconciliation_rule_version: Literal[1]

    @field_validator(
        "candidate_service_ids", "supporting_evidence_refs", "conflicting_evidence_refs"
    )
    @classmethod
    def _check_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("must be sorted lexicographically and deduplicated")
        return value

    @field_validator("limitation_codes")
    @classmethod
    def _check_limitation_codes_sorted_and_deduplicated(
        cls, value: list[LimitationCode]
    ) -> list[LimitationCode]:
        if [code.value for code in value] != sorted({code.value for code in value}):
            raise ValueError("limitation_codes must be sorted lexicographically and deduplicated")
        return value

    @field_validator("supporting_methods")
    @classmethod
    def _check_supporting_methods(
        cls, value: list[DeploymentResolutionMethod]
    ) -> list[DeploymentResolutionMethod]:
        return _check_supporting_methods_canonical_order(value)

    @model_validator(mode="after")
    def _check_resolved_and_non_resolved_invariants(self) -> DeploymentResolution:
        # spec §13.3: "status starts with RESOLVED_" - checked textually so this stays correct if
        # the enum ever grows, without needing a second frozenset kept in sync by hand.
        if self.status.value.startswith("RESOLVED_"):
            if self.workload is None:
                raise ValueError("workload must not be null for a RESOLVED_* status")
            if self.service_id is None:
                raise ValueError("service_id must not be null for a RESOLVED_* status")
            if self.candidate_service_ids != [self.service_id]:
                raise ValueError(
                    "candidate_service_ids must equal [service_id] for a RESOLVED_* status"
                )
            if self.claim_id is None:
                raise ValueError("claim_id must not be null for a RESOLVED_* status")
            if not self.supporting_methods:
                raise ValueError("supporting_methods must not be empty for a RESOLVED_* status")
        elif self.claim_id is not None:
            raise ValueError("claim_id must be null for a non-resolved status")
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


def _check_service_field_is_service_typed(value: EntityRef) -> EntityRef:
    # PR #212 review finding: EntityType.WORKLOAD (added this slice) otherwise lets a
    # Workload-shaped EntityRef slip into a `service` field that identifies the requested AIP
    # Service - the same "DEPLOYED_AS != CALLS" / entity-equivalence boundary the DependencyClaim
    # subject/object guard already enforces, applied here to the answer-level `service` identity.
    if value.type != EntityType.SERVICE:
        raise ValueError("service.type must be SERVICE")
    return value


def _service_field_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Mirrors `_check_service_field_is_service_typed` for external (non-Pydantic) validators."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {"properties": {"service": {"properties": {"type": {"const": "SERVICE"}}}}},
    ]


class ServiceDependenciesData(BaseModel):
    """v0.5.0 I3 spec §14.2: deployment is a separate sibling projection, never a dependency -
    `deployment_claim_ids`/`deployment_resolutions` are additive fields alongside the original
    dependency-only shape, not a replacement of it."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_service_field_schema_extra
    )

    service: EntityRef
    dependency_claim_ids: list[str]
    deployment_claim_ids: list[str]
    deployment_resolutions: list[DeploymentResolution]

    @field_validator("service")
    @classmethod
    def _check_service_type(cls, value: EntityRef) -> EntityRef:
        return _check_service_field_is_service_typed(value)

    @field_validator("deployment_resolutions")
    @classmethod
    def _check_resolutions_sorted_by_id(
        cls, value: list[DeploymentResolution]
    ) -> list[DeploymentResolution]:
        # spec §13.5: "DeploymentResolution[] is sorted lexicographically by resolution_id."
        ids = [resolution.resolution_id for resolution in value]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError(
                "deployment_resolutions must be sorted by resolution_id and deduplicated"
            )
        return value


class ArchitectureDriftData(BaseModel):
    """v0.4.0 I3.1 - spec §10. Deliberately only the service and the drift claim ids: no
    `observed_only[]`/`not_observed[]` buckets, no `severity`/`score`/`summary_text` (spec §10 names
    each of those as prohibited), because every returned `DependencyClaim` already carries the
    authoritative `qualification` that made it drift. The claims themselves stay on the enclosing
    `ArchitectureAnswer.claims` - this data payload only names them, in the same order."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_service_field_schema_extra
    )

    service: EntityRef
    drift_claim_ids: list[str]

    @field_validator("service")
    @classmethod
    def _check_service_type(cls, value: EntityRef) -> EntityRef:
        return _check_service_field_is_service_typed(value)


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


def _evidence_record_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode the evidence_type/observation coupling (spec §11.2's field table) as JSON Schema
    if/then/else so external (non-Pydantic) validators reject the same invalid shapes. The Python
    model_validator below is still authoritative at runtime - this only mirrors it for the
    committed schema."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {
                "properties": {"evidence_type": {"const": "OBSERVED"}},
                "required": ["evidence_type"],
            },
            "then": {"properties": {"observation": {"not": {"type": "null"}}}},
            "else": {"properties": {"observation": {"type": "null"}}},
        },
    ]


class EvidenceRecord(BaseModel):
    """v0.4.0 I2.1 - spec §11.2. `evidence_type`/`source_type` reuse the existing
    `app.provenance.model` enums rather than redefining them - no new adapter classification."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_evidence_record_schema_extra
    )

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

    @model_validator(mode="after")
    def _check_observation_matches_evidence_type(self) -> EvidenceRecord:
        if self.evidence_type == EvidenceType.OBSERVED and self.observation is None:
            raise ValueError("observation is required when evidence_type == OBSERVED")
        if self.evidence_type != EvidenceType.OBSERVED and self.observation is not None:
            raise ValueError("observation is only allowed when evidence_type == OBSERVED")
        return self


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

    @model_validator(mode="after")
    def _check_records_and_missing_partition_requested(self) -> EvidenceData:
        # Not mirrored in the exported JSON Schema: a set union/disjointness check across three
        # separate array properties has no standard JSON Schema expression - the Python validator
        # here is the sole enforcement point.
        record_ids = {record.id for record in self.records}
        missing_ids = set(self.missing_evidence_refs)
        if record_ids & missing_ids:
            raise ValueError("records and missing_evidence_refs must be disjoint")
        if record_ids | missing_ids != set(self.requested_evidence_refs):
            raise ValueError(
                "records and missing_evidence_refs together must exactly partition "
                "requested_evidence_refs"
            )
        return self


# I3 spec §14.2's closed claim union - the discriminator is `predicate`, since both claim models
# already carry it with exactly one distinct Literal value each (`DIRECT_DEPENDENCY`/`DEPLOYED_AS`).
# Pydantic 2 requires a discriminator field to be `Literal`-typed on every union arm (a bare StrEnum
# field, even with one member, is rejected at class-definition time) - both models' `predicate`
# fields are typed accordingly above.
Claim = Annotated[DependencyClaim | DeploymentClaim, Field(discriminator="predicate")]


def _claim_sort_key(claim: DependencyClaim | DeploymentClaim) -> tuple[str, str, str, str, str]:
    # Resolved via AskUserQuestion during I3 slice 1 planning: the spec defines ordering within each
    # claim type but not across the closed union. (object.id, predicate, ...) interleaves both claim
    # types for the same entity, using only fields both types already carry; DependencyClaim's own
    # existing (delivery.kind, delivery.via.id) tiebreaker becomes ("", "") for a DeploymentClaim,
    # which has no `delivery` field at all.
    if isinstance(claim, DependencyClaim):
        secondary = (claim.delivery.kind.value, claim.delivery.via.id)
    else:
        secondary = ("", "")
    return (claim.object.id, claim.predicate.value, *secondary, claim.claim_id)


# v0.4.0 I2.1 - the tool name each generic specialization is locked to, keyed by its bound `T`.
# Used both to close each frozen schema file down to its one valid `tool` value (each is generated
# from ONE concrete `ArchitectureAnswer[...]` class, but the shared `tool` field's Literal otherwise
# allows either string in both files - spec §14 requires each specialization stay semantically
# closed, not just structurally) and, at runtime, to reject an instance whose `tool` disagrees with
# the specialization it was constructed as (a dependency answer claiming to be `get_evidence`, or
# vice versa).
_TOOL_NAME_BY_DATA_TYPE = {
    "ServiceDependenciesData": "get_service_dependencies",
    "EvidenceData": "get_evidence",
    "ArchitectureDriftData": "get_architecture_drift",
}

# v0.4.0 I3.1 / v0.5.0 I3 slice 1: each claim-carrying data type projects `claims` into its own id
# list(s), never an independent list that could disagree with it. `ServiceDependenciesData` now
# carries BOTH claim types (spec §14.2: deployment is a sibling projection, never a dependency), so
# its own claim-id lists are partitioned by claim subtype rather than being one flat projection like
# `ArchitectureDriftData`'s `drift_claim_ids` - each data type therefore gets its own checker
# function instead of sharing one generic field-name lookup.


def _check_service_dependencies_claim_ids(
    data: ServiceDependenciesData, claims: list[DependencyClaim | DeploymentClaim]
) -> None:
    expected_dependency_ids = [c.claim_id for c in claims if isinstance(c, DependencyClaim)]
    if data.dependency_claim_ids != expected_dependency_ids:
        raise ValueError(
            "data.dependency_claim_ids must equal the DependencyClaim entries of claims, in order"
        )
    expected_deployment_ids = [c.claim_id for c in claims if isinstance(c, DeploymentClaim)]
    if data.deployment_claim_ids != expected_deployment_ids:
        raise ValueError(
            "data.deployment_claim_ids must equal the DeploymentClaim entries of claims, in order"
        )
    # I3 spec §13.3: "claim_id names one returned DeploymentClaim."
    deployment_claim_ids = set(expected_deployment_ids)
    for resolution in data.deployment_resolutions:
        if resolution.claim_id is not None and resolution.claim_id not in deployment_claim_ids:
            raise ValueError(
                "every DeploymentResolution.claim_id must name a DeploymentClaim present in claims"
            )


def _check_architecture_drift_claim_ids(
    data: ArchitectureDriftData, claims: list[DependencyClaim | DeploymentClaim]
) -> None:
    # I3 spec §14.2: "get_architecture_drift returns only dependency-drift claims and never
    # DEPLOYED_AS."
    if any(isinstance(claim, DeploymentClaim) for claim in claims):
        raise ValueError("get_architecture_drift answers must never contain a DeploymentClaim")
    expected_claim_ids = [claim.claim_id for claim in claims]
    if data.drift_claim_ids != expected_claim_ids:
        raise ValueError("data.drift_claim_ids must equal claims[*].claim_id in the same order")


def _bound_data_type_name(model: type[BaseModel]) -> str | None:
    args = getattr(model, "__pydantic_generic_metadata__", {}).get("args", ())
    return args[0].__name__ if args else None


def _architecture_answer_schema_extra(schema: dict, model: type[BaseModel]) -> None:
    """Encode more envelope invariants (spec §8.3/§9/§12/§14) as JSON Schema if/then/contains so
    external (non-Pydantic) validators reject the same invalid shapes. The Python
    model_validator below is still authoritative at runtime - this only mirrors it for the
    committed schema."""
    all_of = [
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
                    "tool": {"enum": sorted(_TOOLS_REQUIRING_OBSERVATION_CONTEXT)},
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
        {
            "if": {
                "properties": {"tool": {"const": "get_evidence"}},
                "required": ["tool"],
            },
            "then": {
                "properties": {
                    "claims": {"maxItems": 0},
                    "evidence_refs": {"maxItems": 0},
                    "observation_context": {"type": "null"},
                }
            },
        },
    ]
    # This schema is generated from one concrete ArchitectureAnswer[T] class - lock `tool` to the
    # one value valid for T, closing the gap the shared Literal otherwise leaves open (both values
    # are structurally valid JSON for either T, since `tool` isn't itself generic).
    tool_name = _TOOL_NAME_BY_DATA_TYPE.get(_bound_data_type_name(model))
    if tool_name is not None:
        all_of.append({"properties": {"tool": {"const": tool_name}}})
    if tool_name == "get_architecture_drift":
        # I3 spec §14.2: "get_architecture_drift returns only dependency-drift claims and never
        # DEPLOYED_AS" - mirrors _check_architecture_drift_claim_ids for external validators.
        all_of.append(
            {
                "properties": {
                    "claims": {
                        "items": {
                            "not": {
                                "properties": {"predicate": {"const": "DEPLOYED_AS"}},
                                "required": ["predicate"],
                            }
                        }
                    }
                }
            }
        )
    schema["allOf"] = all_of


# v0.4.0 I2.1 - spec §3/§14's first sanctioned extension point: only the runtime-context-sensitive
# tools require a non-null `observation_context` (or an explicit OBSERVATION_CONTEXT_REQUIRED
# limitation); `get_evidence`'s `observation_context` is always null (spec §12) regardless of
# outcome, including outcomes where `data` is also null - `tool`, not `data`'s type, is the only
# discriminator that's always present to key off.
# v0.4.0 I3.1 - `get_architecture_drift` joins it (I3 spec §11): drift is a view of an answer that
# is itself qualified against one explicit environment/window, so it inherits the same requirement.
_TOOLS_REQUIRING_OBSERVATION_CONTEXT = frozenset(
    {"get_service_dependencies", "get_architecture_drift"}
)


class ArchitectureAnswer[T: BaseModel](BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_architecture_answer_schema_extra
    )

    schema_version: ArchitectureSchemaVersion
    producer: Producer
    tool: ArchitectureToolName
    outcome: Outcome
    snapshot: SnapshotRef | None
    observation_context: ObservationContextRef | None
    data: T | None
    claims: list[Claim]
    evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    limitations: list[Limitation]

    @model_validator(mode="after")
    def _check_envelope_invariants(self) -> ArchitectureAnswer[T]:
        if self.outcome != Outcome.NOT_ANSWERED and self.data is None:
            raise ValueError("data must not be null for ANSWERED/PARTIAL outcomes")

        expected_tool = _TOOL_NAME_BY_DATA_TYPE.get(_bound_data_type_name(type(self)))
        if expected_tool is not None and self.tool != expected_tool:
            raise ValueError(f"tool must be {expected_tool!r} for this ArchitectureAnswer[T]")

        if self.tool == "get_evidence":
            if self.claims:
                raise ValueError("get_evidence answers must have empty claims")
            if self.evidence_refs:
                raise ValueError("get_evidence answers must have empty top-level evidence_refs")
            if self.observation_context is not None:
                raise ValueError(
                    "get_evidence answers must have observation_context = null (spec §12: "
                    "get_evidence is not runtime-context-sensitive)"
                )

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

        # DeploymentClaim has no resolution_evidence_refs field at all (that's a DependencyClaim/
        # destination-resolution-only concept) - only union it in when present.
        expected_evidence_refs = sorted(
            {
                ref
                for claim in self.claims
                for ref in (
                    *claim.evidence_refs,
                    *(claim.resolution_evidence_refs if isinstance(claim, DependencyClaim) else ()),
                )
            }
        )
        if self.evidence_refs != expected_evidence_refs:
            raise ValueError(
                "evidence_refs must be the sorted, deduplicated union of every claim's "
                "evidence_refs and resolution_evidence_refs"
            )

        if isinstance(self.data, ServiceDependenciesData):
            _check_service_dependencies_claim_ids(self.data, self.claims)
        elif isinstance(self.data, ArchitectureDriftData):
            _check_architecture_drift_claim_ids(self.data, self.claims)

        claim_sort_keys = [_claim_sort_key(claim) for claim in self.claims]
        if claim_sort_keys != sorted(claim_sort_keys):
            raise ValueError(
                "claims must be sorted by (object.id, predicate, delivery.kind, delivery.via.id, "
                "claim_id)"
            )

        return self
