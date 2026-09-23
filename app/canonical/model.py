from enum import StrEnum

from pydantic import BaseModel, Field

from app.canonical.infrastructure import (
    InfrastructureClaim,
    InfrastructureContribution,
    InfrastructureEntity,
)
from app.provenance.model import Provenance


class Direction(StrEnum):
    SEND = "SEND"
    RECEIVE = "RECEIVE"


class Service(BaseModel):
    id: str
    name: str
    version: str | None = None


class Operation(BaseModel):
    id: str
    service_id: str
    operation_id: str | None = None
    method: str
    path: str
    request_schema_ids: list[str] = Field(default_factory=list)
    response_schema_ids: list[str] = Field(default_factory=list)


class Queue(BaseModel):
    id: str
    name: str
    protocol: str | None = None
    namespace: str | None = None
    queue_type: str = "STANDARD"


class Topic(BaseModel):
    """v0.5.0 I4 spec §6.2: a publish destination whose downstream fan-out is expressed only by
    distinct Subscriptions. Deliberately separate from `Queue` (no `queue_type`) and from any generic
    destination supertype (ADR 0017). Not yet carried by `ArchitectureModel` - slice 2 adds it
    together with the importer path and the canonicalization-v3 bump (spec §11)."""

    id: str
    name: str
    protocol: str | None = None
    namespace: str | None = None


class Subscription(BaseModel):
    """v0.5.0 I4 spec §6.2: a stable named logical delivery entity associated with exactly one Topic.
    The Topic association is the `SUBSCRIPTION_OF` relation, not a field here. Carries no consumer
    instances, consumer groups, partitions, offsets, lag, filters, or delivery guarantees."""

    id: str
    name: str
    protocol: str | None = None
    namespace: str | None = None


class Message(BaseModel):
    id: str
    name: str
    version: str | None = None
    schema_id: str | None = None
    # I1 spec §9.1: document_digest is the full normalized message document (provenance only);
    # contract_digest excludes presentation/identity metadata and is used for semantic comparison/
    # conflict detection - see app.sources.message_contract.
    contract_digest: str | None = None
    document_digest: str | None = None


class Schema(BaseModel):
    id: str
    name: str
    version: str | None = None
    format: str | None = None
    canonical_hash: str | None = None


class Relation(BaseModel):
    type: str
    source_id: str
    target_id: str
    evidence_ids: list[str] = Field(default_factory=list)


class ArchitectureModel(BaseModel):
    services: list[Service] = Field(default_factory=list)
    operations: list[Operation] = Field(default_factory=list)
    queues: list[Queue] = Field(default_factory=list)
    messages: list[Message] = Field(default_factory=list)
    schemas: list[Schema] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)
    # I2 Draft 0.2 §3 prerequisite slice (PR B), §7.1/§7.2: the Canonical Model's capacity to carry
    # Kubernetes infrastructure facts - internal-only (§9), unpopulated until I2 §12 slice 3's
    # adapter exists.
    infrastructure_entities: list[InfrastructureEntity] = Field(default_factory=list)
    infrastructure_contributions: list[InfrastructureContribution] = Field(default_factory=list)
    infrastructure_claims: list[InfrastructureClaim] = Field(default_factory=list)
