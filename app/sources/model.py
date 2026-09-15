from enum import StrEnum
from pathlib import Path
from typing import NewType

from pydantic import BaseModel, Field, model_validator

SourceInstanceId = NewType("SourceInstanceId", str)
DiscoveryScopeId = NewType("DiscoveryScopeId", str)


class SourceKind(StrEnum):
    FILESYSTEM = "filesystem"
    # Kubernetes stable-source-key is reserved for I2 (I1 spec §5.1) - deliberately no member here
    # yet: "unsupported > falsely supported".


class FilesystemSourceConfig(BaseModel):
    """I1 spec §5.1's "configured filesystem-source id" plus the physical root it scans. A source's
    stable identity must be an explicit, operator-assigned id, never the directory path itself (I1
    §6: "stable target identity MUST NOT be an absolute checkout path, resolved physical directory,
    mount point, or other mutable root location").

    A pure domain contract (not a settings-loading concern) so `app/ingestion/` and `app/graph/`
    can depend on it directly without depending on `app.settings`; `app.settings.SourcesConfig`
    reuses this same type as its field shape.

    `scope_id` and `stable_target_identity` default from `id` when omitted, which is sufficient for
    the common one-directory-one-scope case; a deployment scanning multiple physically distinct
    roots under one logical scope can override `scope_id` to group them.
    """

    id: str
    root: Path
    scope_id: str | None = None
    stable_target_identity: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_bare_entry(cls, value: object) -> object:
        if not isinstance(value, dict):
            # Must be ValueError, not TypeError: pydantic only wraps ValueError/AssertionError
            # raised inside a validator into a ValidationError - a TypeError would propagate
            # uncaught instead of surfacing as a normal config-validation failure.
            raise ValueError(  # noqa: TRY004
                "sources.directories entries must be objects with 'id' and 'root' fields "
                f"(got {value!r}) - a bare directory path can no longer serve as a source's "
                "stable identity; see the v0.5.0 migration guide"
            )
        return value

    @property
    def resolved_scope_id(self) -> str:
        return self.scope_id or self.id

    @property
    def resolved_stable_target_identity(self) -> str:
        return self.stable_target_identity or f"urn:aip:logical-root:{self.id}"


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
    # Not named by the spec text; introduced here for §6's tombstone-staleness rejection reasons.
    TOMBSTONE_STALE = "TOMBSTONE_STALE"
    TOMBSTONE_SCOPE_MISMATCH = "TOMBSTONE_SCOPE_MISMATCH"


class IngestionDiagnostic(BaseModel):
    code: DiagnosticCode
    message: str
    source_pointer: str | None = None
    source_instance_id: str | None = None


class SourceDescriptor(BaseModel):
    """I1 spec §4's `SourceDescriptor` fields. Field names are this PR's own choice - the spec gives
    only a prose bullet list, not a schema - and are called out for review in the PR description.
    `source_inventory_snapshot_ref` is a placeholder `str | None` until a later increment defines the
    real `SourceInventorySnapshot`. `mapping_context_digest` was added by the I1 spec's Draft 0.2
    revision (§5.3) - see `app.sources.identity.mapping_context_digest`.
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
    mapping_context_digest: str
    declared_service_id: str | None = None
    document_dialect_version: str | None = None
    adapter_identity: str
    mapping_rule_id: str
    mapping_rule_version: str


class LoadedSource(BaseModel):
    descriptor: SourceDescriptor
    document: dict
    diagnostics: list[IngestionDiagnostic] = Field(default_factory=list)
