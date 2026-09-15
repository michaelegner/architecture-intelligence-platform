from enum import StrEnum
from typing import NewType

from pydantic import BaseModel, Field

SourceInstanceId = NewType("SourceInstanceId", str)
DiscoveryScopeId = NewType("DiscoveryScopeId", str)


class SourceKind(StrEnum):
    FILESYSTEM = "filesystem"
    # Kubernetes stable-source-key is reserved for I2 (I1 spec §5.1) - deliberately no member here
    # yet: "unsupported > falsely supported".


class IngestionResult(StrEnum):
    """I1 spec §10: "Each source receives exactly one result." """

    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_LIMITATIONS = "ACCEPTED_WITH_LIMITATIONS"
    REJECTED_INVALID = "REJECTED_INVALID"
    REJECTED_UNSUPPORTED = "REJECTED_UNSUPPORTED"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"


class DiagnosticCode(StrEnum):
    # Named explicitly by the I1 spec (§4.1, §8, §8.1, §9).
    SERVICE_IDENTITY_UNRESOLVED = "SERVICE_IDENTITY_UNRESOLVED"
    SERVICE_IDENTITY_CONFLICT = "SERVICE_IDENTITY_CONFLICT"
    SERVICE_IDENTITY_INVALID = "SERVICE_IDENTITY_INVALID"
    REFERENCE_LIMIT_EXCEEDED = "REFERENCE_LIMIT_EXCEEDED"
    REFERENCE_CYCLE_UNSUPPORTED = "REFERENCE_CYCLE_UNSUPPORTED"
    SCHEMA_COMPOSITION_UNINTERPRETED = "SCHEMA_COMPOSITION_UNINTERPRETED"
    AMBIGUOUS = "AMBIGUOUS"
    # Not named by the spec text; introduced here for the ArchitectureIdentityBindings shape (§4.2),
    # which the spec describes only in prose. Flagged in the PR description for review.
    MANIFEST_BINDING_SHAPE_INVALID = "MANIFEST_BINDING_SHAPE_INVALID"
    MANIFEST_BINDING_POINTER_INVALID = "MANIFEST_BINDING_POINTER_INVALID"
    MANIFEST_BINDING_UNKNOWN_SOURCE = "MANIFEST_BINDING_UNKNOWN_SOURCE"


class IngestionDiagnostic(BaseModel):
    code: DiagnosticCode
    message: str
    source_pointer: str | None = None
    source_instance_id: str | None = None


class SourceDescriptor(BaseModel):
    """I1 spec §4's `SourceDescriptor` fields. Field names are this PR's own choice - the spec gives
    only a prose bullet list, not a schema - and are called out for review in the PR description.
    `source_inventory_snapshot_ref` is a placeholder `str | None` until a later increment defines the
    real `SourceInventorySnapshot`.
    """

    source_instance_id: str
    source_kind: SourceKind
    locator: str
    discovery_scope_id: str
    scope_definition_digest: str
    source_inventory_snapshot_ref: str | None = None
    declared_provider_revision: str | None = None
    content_sha256: str
    dependency_closure_digest: str | None = None
    semantic_input_digest: str
    declared_service_id: str | None = None
    document_dialect_version: str | None = None
    adapter_identity: str
    mapping_rule_id: str
    mapping_rule_version: str


class LoadedSource(BaseModel):
    descriptor: SourceDescriptor
    document: dict
    diagnostics: list[IngestionDiagnostic] = Field(default_factory=list)
