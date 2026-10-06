"""v0.6.1 I2a - the Broker-aware public contract (schema 0.6) for `get_service_dependencies` and
`get_evidence` (spec docs/specifications/0.6.1/specification.md §5).

This module defines only the data contract: `BrokerClaim`, the v0.6 `ServiceDependenciesDataV06`,
`EvidenceDataV06` and the `ArchitectureAnswerV06[T]` envelope. It contains no service logic, no
Neo4j access and no projection. It is separate from the closed, released 0.5 `ArchitectureAnswer`,
exactly as `locality_contracts.py` is: nothing here widens a v0.5 model, enum or union, and the v0.5
schema files stay byte-identical (`tests/unit/test_broker_contracts_schema_frozen.py`). The v0.6
models are standalone classes, never subclasses of the v0.5 ones: a subclass instance would be
accepted by a v0.5 model without revalidation, letting Broker data into a v0.5-labelled answer.

The answer is data-dependent (spec §5.2): an answer without a BrokerClaim stays the v0.5 shape; a
Broker-aware answer is this v0.6 shape. `ArchitectureAnswerV06` therefore *requires* Broker content
- a BrokerClaim for dependencies, a `USES_BROKER` supported fact for evidence - so the two shapes
can never both describe the same answer.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.architecture_intelligence.contracts import (
    CLAIM_ID_PREFIX,
    ArchitectureAnswer,
    ArchitectureToolName,
    DependencyClaim,
    DeploymentClaim,
    DeploymentResolution,
    EntityRef,
    EntityType,
    EvidenceData,
    Limitation,
    ObservationContextRef,
    ObservedEvidenceMetadata,
    Outcome,
    Producer,
    ServiceDependenciesData,
    SnapshotRef,
    _architecture_answer_schema_extra,
    _check_service_dependencies_claim_ids,
    _check_service_field_is_service_typed,
    _evidence_record_schema_extra,
    _service_field_schema_extra,
    check_answer_envelope,
    claim_sort_key,
)
from app.provenance.model import EvidenceType, SourceType

_SHA256_HEX = r"[0-9a-f]{64}"
_BROKER_CLAIM_ID_PATTERN = rf"^{CLAIM_ID_PREFIX}:{_SHA256_HEX}$"
# `app.sources.owner_ids.broker_owned_id`: `broker:owned:<sha256(length-delimited(stable id))>`.
BROKER_ID_PATTERN = rf"^broker:owned:{_SHA256_HEX}$"

BrokerSchemaVersion = Literal["0.6"]
BROKER_SCHEMA_VERSION: BrokerSchemaVersion = get_args(BrokerSchemaVersion)[0]


class BrokerEntityType(StrEnum):
    """The one entity type the Broker-aware contract adds. Its own enum rather than a member of the
    released `EntityType`: widening that enum would change the frozen v0.5 schemas."""

    BROKER = "BROKER"


class BrokerPredicate(StrEnum):
    USES_BROKER = "USES_BROKER"


class BrokerRef(BaseModel):
    """spec §5.1: a bounded public Broker reference, deliberately its own model rather than an
    `EntityRef` extension (the `WorkloadRef` precedent). `name` is the explicit stable broker id the
    source declared; the canonical Broker id is derived from it. No protocol, host, namespace or
    other endpoint detail is a field here: those never establish Broker identity (spec §4.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=BROKER_ID_PATTERN)
    # No default (the PR #212 lesson): a defaulted discriminator drops out of the schema's
    # `required` list, so it would not be required for a non-Pydantic client.
    type: Literal[BrokerEntityType.BROKER]
    name: str = Field(min_length=1)


def _broker_claim_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """Encode "subject.type == SERVICE" as JSON Schema so external validators reject the shape the
    Python model_validator below rejects at runtime (mirrors `_deployment_claim_schema_extra`).
    `object.type == BROKER` is already a `const` through `BrokerRef.type`."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {"properties": {"subject": {"properties": {"type": {"const": "SERVICE"}}}}},
    ]


class BrokerClaim(BaseModel):
    """spec §5.1: the public `Service -[USES_BROKER]-> Broker` claim. Deliberately has no
    `delivery`/`qualification`/`coverage`/`destination_resolution` fields: those describe a
    CALLS/SENDS/PUBLISHES_TO interaction, and a Broker claim never creates or implies a Queue,
    Topic, Subscription, Message, producer or consumer claim."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_broker_claim_schema_extra
    )

    claim_id: str = Field(pattern=_BROKER_CLAIM_ID_PATTERN)
    subject: EntityRef
    # No default: it is the union discriminator and must be a real required schema field.
    predicate: Literal[BrokerPredicate.USES_BROKER]
    object: BrokerRef
    evidence_refs: list[str] = Field(min_length=1, json_schema_extra={"uniqueItems": True})

    @field_validator("evidence_refs")
    @classmethod
    def _check_evidence_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError(
                "evidence references must be sorted lexicographically and deduplicated"
            )
        return value

    @model_validator(mode="after")
    def _check_subject_type(self) -> BrokerClaim:
        if self.subject.type != EntityType.SERVICE:
            raise ValueError("subject.type must be SERVICE for a Broker claim")
        return self


# The closed claim union of a Broker-aware dependency answer. The discriminator is `predicate`,
# which every arm carries as a `Literal` (pydantic rejects a bare enum field as a discriminator).
ClaimV06 = Annotated[
    DependencyClaim | DeploymentClaim | BrokerClaim, Field(discriminator="predicate")
]


class ServiceDependenciesDataV06(BaseModel):
    """spec §5.1: the v0.5 `ServiceDependenciesData` fields plus `broker_claim_ids`, a sibling of
    `dependency_claim_ids` and `deployment_claim_ids`. It exists only in a Broker-aware answer, so
    `broker_claim_ids` is required and never empty - an answer with no BrokerClaim is the v0.5
    shape and carries no empty field."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_service_field_schema_extra
    )

    service: EntityRef
    dependency_claim_ids: list[str]
    deployment_claim_ids: list[str]
    broker_claim_ids: list[str] = Field(min_length=1, json_schema_extra={"uniqueItems": True})
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
        ids = [resolution.resolution_id for resolution in value]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError(
                "deployment_resolutions must be sorted by resolution_id and deduplicated"
            )
        return value


class EvidenceRelationTypeV06(StrEnum):
    """The closed set of canonical relation kinds a Broker-aware `get_evidence` may describe: the
    released v0.5 set plus `USES_BROKER` (`tests/unit/test_broker_contracts.py` pins that it is
    exactly that)."""

    PROVIDES = "PROVIDES"
    CALLS = "CALLS"
    SENDS = "SENDS"
    RECEIVES_FROM = "RECEIVES_FROM"
    CARRIES = "CARRIES"
    CONFORMS_TO = "CONFORMS_TO"
    DEAD_LETTERS_TO = "DEAD_LETTERS_TO"
    DEPLOYED_AS = "DEPLOYED_AS"
    PUBLISHES_TO = "PUBLISHES_TO"
    SUBSCRIPTION_OF = "SUBSCRIPTION_OF"
    USES_BROKER = "USES_BROKER"


def _supported_fact_v06_schema_extra(schema: dict, _model: type[BaseModel]) -> None:
    """`broker` is present exactly for a `USES_BROKER` fact: required and non-null there, null for
    every other relation (mirrors the Python validator for external validators)."""
    schema["allOf"] = [
        *schema.get("allOf", []),
        {
            "if": {
                "properties": {"relation_type": {"const": "USES_BROKER"}},
                "required": ["relation_type"],
            },
            "then": {"properties": {"broker": {"not": {"type": "null"}}}},
            "else": {"properties": {"broker": {"type": "null"}}},
        },
    ]


class SupportedFactV06(BaseModel):
    """The v0.5 `SupportedFact` (relation type, source id, target id) plus `broker`: the Broker
    endpoint as a bounded `BrokerRef` for a `USES_BROKER` fact, so a Broker-aware evidence answer
    exposes BROKER as an entity type (spec §5.2). Null for every other relation."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_supported_fact_v06_schema_extra
    )

    relation_type: EvidenceRelationTypeV06
    source_id: str
    target_id: str
    # No default: always present, null unless relation_type == USES_BROKER.
    broker: BrokerRef | None

    @model_validator(mode="after")
    def _check_broker_matches_relation(self) -> SupportedFactV06:
        is_uses_broker = self.relation_type == EvidenceRelationTypeV06.USES_BROKER
        if is_uses_broker and self.broker is None:
            raise ValueError("a USES_BROKER fact requires its broker")
        if not is_uses_broker and self.broker is not None:
            raise ValueError("broker is only allowed when relation_type == USES_BROKER")
        # Pydantic-only: JSON Schema cannot compare two sibling properties' values.
        if self.broker is not None and self.broker.id != self.target_id:
            raise ValueError("broker.id must equal target_id")
        return self


def supported_fact_v06_sort_key(fact: SupportedFactV06) -> tuple[str, str, str]:
    return (fact.relation_type.value, fact.source_id, fact.target_id)


class EvidenceRecordV06(BaseModel):
    """The v0.5 `EvidenceRecord` with `supports` typed `SupportedFactV06`. Standalone, never a
    subclass: see the module docstring."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_evidence_record_schema_extra
    )

    id: str
    evidence_type: EvidenceType
    source_type: SourceType
    source_locator: str | None
    source_revision: str | None
    observation: ObservedEvidenceMetadata | None
    supports: list[SupportedFactV06]

    @field_validator("supports")
    @classmethod
    def _check_supports_sorted_and_deduplicated(
        cls, value: list[SupportedFactV06]
    ) -> list[SupportedFactV06]:
        keys = [supported_fact_v06_sort_key(fact) for fact in value]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError(
                "supports must be sorted by (relation_type, source_id, target_id) and deduplicated"
            )
        return value

    @model_validator(mode="after")
    def _check_observation_matches_evidence_type(self) -> EvidenceRecordV06:
        if self.evidence_type == EvidenceType.OBSERVED and self.observation is None:
            raise ValueError("observation is required when evidence_type == OBSERVED")
        if self.evidence_type != EvidenceType.OBSERVED and self.observation is not None:
            raise ValueError("observation is only allowed when evidence_type == OBSERVED")
        return self


class EvidenceDataV06(BaseModel):
    """The v0.5 `EvidenceData` with `records` typed `EvidenceRecordV06`. `claims`/top-level
    `evidence_refs` on the enclosing answer stay empty for this tool, as in v0.5."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    records: list[EvidenceRecordV06]
    missing_evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})

    @field_validator("requested_evidence_refs", "missing_evidence_refs")
    @classmethod
    def _check_refs_sorted_and_deduplicated(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("must be sorted lexicographically and deduplicated")
        return value

    @field_validator("records")
    @classmethod
    def _check_records_sorted_by_id(cls, value: list[EvidenceRecordV06]) -> list[EvidenceRecordV06]:
        ids = [record.id for record in value]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("records must be sorted by id and deduplicated")
        return value

    @model_validator(mode="after")
    def _check_records_and_missing_partition_requested(self) -> EvidenceDataV06:
        # Not mirrored in the exported JSON Schema: a set union/disjointness check across three
        # separate array properties has no standard JSON Schema expression.
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


def _check_v06_data(data: Any, claims: list[Any]) -> None:
    if isinstance(data, ServiceDependenciesDataV06):
        # Dependency and deployment partitions plus resolution claim ids: the same check the v0.5
        # envelope runs (it reads only the three shared fields and ignores other claim types).
        _check_service_dependencies_claim_ids(data, claims)  # pyright: ignore[reportArgumentType]
        # Pydantic-only (list equality against the sibling `claims` array has no JSON Schema form).
        # With `broker_claim_ids` non-empty this also guarantees at least one BrokerClaim; the
        # schema states that separately as `claims.contains(USES_BROKER)`.
        expected_broker_ids = [c.claim_id for c in claims if isinstance(c, BrokerClaim)]
        if data.broker_claim_ids != expected_broker_ids:
            raise ValueError(
                "data.broker_claim_ids must equal the BrokerClaim entries of claims, in order"
            )


def _has_uses_broker_support(data: EvidenceDataV06) -> bool:
    return any(
        fact.relation_type == EvidenceRelationTypeV06.USES_BROKER
        for record in data.records
        for fact in record.supports
    )


def _architecture_answer_v06_schema_extra(schema: dict, model: type[BaseModel]) -> None:
    """The v0.5 envelope's schema invariants (including the per-specialization `tool` const, keyed
    through `_TOOL_NAME_BY_DATA_TYPE`) plus the Broker-awareness requirement: a v0.6 answer exists
    only when it carries Broker content, so a Broker-free answer cannot validate as v0.6."""
    _architecture_answer_schema_extra(schema, model)
    args = getattr(model, "__pydantic_generic_metadata__", {}).get("args", ())
    bound = args[0].__name__ if args else None
    answered = {"outcome": {"enum": ["ANSWERED", "PARTIAL"]}}
    all_of = list(schema.get("allOf", []))
    if bound == "ServiceDependenciesDataV06":
        all_of.append(
            {
                "properties": {
                    **answered,
                    "data": {"type": "object"},
                    "claims": {
                        "contains": {
                            "properties": {"predicate": {"const": "USES_BROKER"}},
                            "required": ["predicate"],
                        }
                    },
                },
                "required": ["outcome", "data", "claims"],
            }
        )
    elif bound == "EvidenceDataV06":
        all_of.append(
            {
                "properties": {
                    **answered,
                    "data": {
                        "type": "object",
                        "properties": {
                            "records": {
                                "contains": {
                                    "properties": {
                                        "supports": {
                                            "contains": {
                                                "properties": {
                                                    "relation_type": {"const": "USES_BROKER"}
                                                },
                                                "required": ["relation_type"],
                                            }
                                        }
                                    },
                                    "required": ["supports"],
                                }
                            }
                        },
                        "required": ["records"],
                    },
                },
                "required": ["outcome", "data"],
            }
        )
    schema["allOf"] = all_of


class ArchitectureAnswerV06[T: BaseModel](BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_extra=_architecture_answer_v06_schema_extra
    )

    schema_version: BrokerSchemaVersion
    producer: Producer
    tool: ArchitectureToolName
    outcome: Outcome
    snapshot: SnapshotRef | None
    observation_context: ObservationContextRef | None
    data: T | None
    claims: list[ClaimV06]
    evidence_refs: list[str] = Field(json_schema_extra={"uniqueItems": True})
    limitations: list[Limitation]

    @model_validator(mode="after")
    def _check_envelope_invariants(self) -> ArchitectureAnswerV06[T]:
        check_answer_envelope(self, sort_key=claim_sort_key, check_data=_check_v06_data)
        if self.outcome == Outcome.NOT_ANSWERED:
            raise ValueError("a Broker-aware answer is never NOT_ANSWERED")
        if self.data is not None and not isinstance(
            self.data, ServiceDependenciesDataV06 | EvidenceDataV06
        ):
            raise ValueError(
                "ArchitectureAnswerV06 is only defined for ServiceDependenciesDataV06 and "
                "EvidenceDataV06"
            )
        if isinstance(self.data, EvidenceDataV06) and not _has_uses_broker_support(self.data):
            raise ValueError("a v0.6 evidence answer must resolve a USES_BROKER fact")
        return self


# The two data-dependent answers (spec §5.2) as one discriminated union each. `schema_version` is
# the discriminator: "0.5" selects the released v0.5 answer, "0.6" the Broker-aware answer, so a
# Broker-free response still validates against the frozen v0.5 schema. REST response models and
# the advertised MCP `outputSchema` are both derived from these, never from either branch alone.
ServiceDependenciesAnswer = Annotated[
    ArchitectureAnswer[ServiceDependenciesData] | ArchitectureAnswerV06[ServiceDependenciesDataV06],
    Field(discriminator="schema_version"),
]
EvidenceAnswer = Annotated[
    ArchitectureAnswer[EvidenceData] | ArchitectureAnswerV06[EvidenceDataV06],
    Field(discriminator="schema_version"),
]
