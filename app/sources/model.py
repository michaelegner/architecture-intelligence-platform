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
                "stable identity; add an explicit 'id' (e.g. {'id': "
                "'aip-bundled-examples-v0.5', 'root': <path>})"
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
    # Not named by the spec text; introduced here for filesystem-discovery-level failures (I1 §6's
    # "missing roots, incomplete checkouts ... MUST preserve the prior inventory" list) and
    # malformed source documents encountered before an adapter can even attempt to map them.
    SOURCE_ROOT_UNAVAILABLE = "SOURCE_ROOT_UNAVAILABLE"
    DOCUMENT_PARSE_INVALID = "DOCUMENT_PARSE_INVALID"
    # Not named by the spec text; introduced here for §9's AsyncAPI Queue kind/identity evidence
    # rules. AMBIGUOUS (above) already covers the multi-server broker/namespace-disagreement case.
    QUEUE_KIND_CONFLICT = "QUEUE_KIND_CONFLICT"
    QUEUE_IDENTITY_CONFLICT = "QUEUE_IDENTITY_CONFLICT"
    QUEUE_EVIDENCE_MISSING = "QUEUE_EVIDENCE_MISSING"
    # Not named by the spec text; introduced here for the Architecture Manifest CALLS-relation
    # adapter, distinct from the ArchitectureIdentityBindings manifest's own diagnostic codes above.
    MANIFEST_CALL_TARGET_UNRESOLVED = "MANIFEST_CALL_TARGET_UNRESOLVED"
    # Not named by the spec text; introduced here for PR3b's bounded multi-file $ref resolution
    # (I1 spec §8.1/§9). REFERENCE_LIMIT_EXCEEDED/REFERENCE_CYCLE_UNSUPPORTED already existed above
    # (added ahead of their real use); these three cover the remaining §8.1 resolution-order
    # rejection cases the spec describes in prose without naming a code: a `$ref` with a non-empty
    # URI scheme/authority ("remote/non-local reference -> REJECTED_UNSUPPORTED for the whole
    # source"), and every other resolution-order failure - malformed percent-encoding, an absolute
    # decoded path, a traversal/symlink escape outside the approved source root, a missing/non-file
    # target, or a dangling JSON Pointer fragment ("invalid structure/reference" -> REJECTED_INVALID).
    REMOTE_REFERENCE_UNSUPPORTED = "REMOTE_REFERENCE_UNSUPPORTED"
    REFERENCE_INVALID = "REFERENCE_INVALID"
    # Not named by the spec text; introduced here for §8/§9's exact-version enforcement
    # ("any other version is REJECTED_UNSUPPORTED unless a reviewed amendment adds that exact
    # version and its conformance fixtures").
    UNSUPPORTED_DIALECT_VERSION = "UNSUPPORTED_DIALECT_VERSION"
    # Not named by the spec text; introduced here for PR4's explicit shared-identity/migration
    # mapping mechanism (§5.1.1/§8.1/§9/§9.1), mirroring the MANIFEST_BINDING_* codes' own
    # "shape, then pointer/target validity, then cross-entry conflict" split.
    MIGRATION_MAPPING_SHAPE_INVALID = "MIGRATION_MAPPING_SHAPE_INVALID"
    MIGRATION_MAPPING_TARGET_INVALID = "MIGRATION_MAPPING_TARGET_INVALID"
    MIGRATION_MAPPING_CONFLICT = "MIGRATION_MAPPING_CONFLICT"
    # §5.1.1: "Missing or modified migration configuration is diagnosed and MUST NOT fall back to a
    # directory slug or name-derived identity" - a configured migration path that can't be read at
    # all is its own distinct failure from a file that parses but has the wrong shape.
    MIGRATION_MAPPING_FILE_UNAVAILABLE = "MIGRATION_MAPPING_FILE_UNAVAILABLE"
    # Not named by the spec text; introduced here for the cross-source/within-source content-
    # conflict rule §8.1/§9.1 both state prose-only ("different hashes under an explicit shared ID
    # are REJECTED_CONFLICT"): two claims converging on the same owner-scoped or explicitly-mapped
    # Schema/Message id with disagreeing canonical content.
    SCHEMA_CONTENT_CONFLICT = "SCHEMA_CONTENT_CONFLICT"
    MESSAGE_CONTENT_CONFLICT = "MESSAGE_CONTENT_CONFLICT"
    # Not named by the spec text; introduced here for the I2 Draft 0.2 §3 prerequisite slice's
    # tombstone-file loading (app.sources.tombstones.load_tombstones), mirroring the
    # MIGRATION_MAPPING_FILE_UNAVAILABLE/MIGRATION_MAPPING_SHAPE_INVALID split above.
    TOMBSTONE_FILE_UNAVAILABLE = "TOMBSTONE_FILE_UNAVAILABLE"
    TOMBSTONE_SHAPE_INVALID = "TOMBSTONE_SHAPE_INVALID"
    # Not named by the spec text; introduced here for the I2 Draft 0.2 §3 prerequisite slice's
    # general (source-kind-neutral) transactional predecessor check - the general mechanism the
    # Kubernetes-specific K8S_STALE_INVENTORY code (a later, K8s-specific slice) will layer on.
    STALE_INVENTORY_PREDECESSOR = "STALE_INVENTORY_PREDECESSOR"
    # Not named by the spec text; introduced here for the I2 Draft 0.2 §3 prerequisite slice's (PR
    # B) infrastructure-entity cross-source content-conflict rule (§7.1: "different semantic digests
    # from simultaneously current sources are incompatible and reject the affected discovery run"),
    # mirroring SCHEMA_CONTENT_CONFLICT/MESSAGE_CONTENT_CONFLICT above. Generalized, not Kubernetes-
    # specific, matching STALE_INVENTORY_PREDECESSOR's own precedent - a later Kubernetes-specific
    # K8S_RESOURCE_CONFLICT code (§10) may layer on top of this same underlying rejection.
    INFRASTRUCTURE_ENTITY_CONTENT_CONFLICT = "INFRASTRUCTURE_ENTITY_CONTENT_CONFLICT"


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
    source_root: str = ""
    """The approved containment boundary a `$ref` may resolve within (I1 spec §8.1's "approved
    source root"), as an absolute or process-relative filesystem path string. Populated by the
    discoverer (the only component that knows the configured root); empty only for a `LoadedSource`
    built directly by a test with no real filesystem backing, since none of PR3b's cross-file
    resolution paths apply to it."""
