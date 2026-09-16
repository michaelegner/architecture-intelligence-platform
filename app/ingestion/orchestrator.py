"""I1 spec §7's orchestrator: discover -> inventory -> classify -> load -> validate -> normalize ->
map -> merge -> canonical validation -> reconciliation plan -> atomic commit.

Everything through "canonical validation" happens here, entirely in memory, with zero Neo4j I/O -
matching PR #1/#2's discipline of pure functions over explicit inputs. "Reconciliation plan" and
"atomic commit" are `app.graph.importer`'s job (this increment's part 9): it calls
`run_filesystem_discovery` to get a `DiscoveryRunResult`, then uses `app.sources.replay`/
`app.sources.claim_reconciliation`/`app.sources.commit_gate` against real committed graph state to
decide what (if anything) to write.

This module replaces `app.ingestion.pipeline`, which is deleted in this same change: its two
responsibilities - `merge_models` (kept, moved here) and hard-coded per-source-kind dispatch
(replaced by the registry) - are both superseded.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.canonical.model import ArchitectureModel, Message, Operation, Queue, Schema, Service
from app.ingestion.asyncapi_adapter import AsyncApiSourceAdapter
from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.ingestion.manifest_adapter import ManifestSourceAdapter
from app.ingestion.openapi_adapter import OpenApiSourceAdapter
from app.provenance.model import Provenance
from app.sources.claim_conflicts import detect_shared_claim_content_conflicts
from app.sources.commit_gate import classify_inventory_status, run_is_eligible_to_commit
from app.sources.identity import mapping_context_digest as compute_mapping_context_digest
from app.sources.inventory import InventoryStatus
from app.sources.jcs import sort_entries_by_canonical_bytes
from app.sources.manifest_bindings import (
    BindingIndex,
    build_binding_index,
    parse_architecture_identity_bindings,
)
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    SharedIdentityMappingIndex,
)
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionDiagnostic,
    IngestionResult,
)
from app.sources.registry import AdapterOutcome, SourceAdapterRegistry
from app.sources.service_identity import (
    PointerBinding,
    ServiceIdentityPath,
    resolve_service_identity,
)

_DEFAULT_ADAPTERS = (OpenApiSourceAdapter(), AsyncApiSourceAdapter(), ManifestSourceAdapter())


def default_registry() -> SourceAdapterRegistry:
    return SourceAdapterRegistry(_DEFAULT_ADAPTERS)


def _is_identity_bindings_document(document: dict) -> bool:
    return document.get("kind") == "ArchitectureIdentityBindings"


def merge_models(models: Sequence[ArchitectureModel]) -> ArchitectureModel:
    """Combines partial models from multiple adapters/sources, deduping entities by id (first
    wins) - unchanged from the old `app.ingestion.pipeline.merge_models`, just relocated: owner-
    scoped ids are already the correct merge key, so this needed no behavior change.
    """
    services: dict[str, Service] = {}
    operations: dict[str, Operation] = {}
    queues: dict[str, Queue] = {}
    messages: dict[str, Message] = {}
    schemas: dict[str, Schema] = {}
    relations = []
    seen_relations: set[tuple[str, str, str]] = set()
    provenance: list[Provenance] = []

    for model in models:
        for service in model.services:
            services.setdefault(service.id, service)
        for operation in model.operations:
            operations.setdefault(operation.id, operation)
        for queue in model.queues:
            queues.setdefault(queue.id, queue)
        for message in model.messages:
            messages.setdefault(message.id, message)
        for schema in model.schemas:
            schemas.setdefault(schema.id, schema)
        for relation in model.relations:
            key = (relation.type, relation.source_id, relation.target_id)
            if key not in seen_relations:
                seen_relations.add(key)
                relations.append(relation)
        provenance.extend(model.provenance)

    return ArchitectureModel(
        services=list(services.values()),
        operations=list(operations.values()),
        queues=list(queues.values()),
        messages=list(messages.values()),
        schemas=list(schemas.values()),
        relations=relations,
        provenance=provenance,
    )


class _RunServiceIdentityResolver:
    """One instance built per discovery run, closing over phase 1's completed `BindingIndex`. I1
    spec §4.1 path 2 (versioned configured source-to-Service mapping) has no config surface in 3a,
    so `configured_mappings` is always empty here.
    """

    def __init__(self, manifest_bindings: Sequence[PointerBinding]):
        self._manifest_bindings = tuple(manifest_bindings)

    def resolve(self, *, source_instance_id: str, construct_pointer: str, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=(),
            manifest_bindings=self._manifest_bindings,
        )


class _RunSharedIdentityResolver:
    """One instance built per discovery run, closing over every configured migration-mapping file's
    merged `SharedIdentityMappingIndex`. Handed to every adapter the same way
    `_RunServiceIdentityResolver` is - adapters never see the index or its source files directly.
    """

    def __init__(self, index: SharedIdentityMappingIndex):
        self._index = index

    def schema_id_for(
        self, *, source_instance_id: str, document_path: str, pointer: str
    ) -> str | None:
        return self._index.schema_id_for(
            source_instance_id=source_instance_id, document_path=document_path, pointer=pointer
        )

    def message_id_for(
        self, *, source_instance_id: str, document_path: str, pointer: str
    ) -> str | None:
        return self._index.message_id_for(
            source_instance_id=source_instance_id, document_path=document_path, pointer=pointer
        )

    def queue_id_for(
        self, *, source_instance_id: str, document_path: str, pointer: str
    ) -> str | None:
        return self._index.queue_id_for(
            source_instance_id=source_instance_id, document_path=document_path, pointer=pointer
        )


def _binding_index_to_pointer_bindings(binding_index: BindingIndex) -> tuple[PointerBinding, ...]:
    return tuple(
        PointerBinding(
            source_instance_id=entry.source_instance_id,
            pointer_prefix=entry.pointer_prefix,
            service_id=entry.service_id,
            path=ServiceIdentityPath.MANIFEST_BINDING,
        )
        for entry in binding_index.entries
    )


# I1 spec §5.1.1's fixed artifact id for the bundled examples/ migration file - any *other*
# configured migration document is a general shared-identity mapping instead, per the
# classification rule in `_classify_shared_identity_entries`'s docstring below.
BUNDLED_MIGRATION_ARTIFACT_ID = "aip-v0.5.0-bundled-example-identities-v1"


def _mapping_entry_context(
    document: MigrationMappingsDocument, entry: IdentityMappingEntry, *, id_field: str
) -> dict[str, str]:
    return {
        "artifactId": document.artifact_id,
        "artifactRevision": document.artifact_revision,
        # §5.3: "Each mapping entry retains its stable artifact identity, revision, content digest,
        # attribution, normalized source pointers, targets, and semantic options." contentDigest is
        # the SHA-256 of this artifact file's own exact raw bytes (MigrationMappingsDocument.
        # content_digest, computed once per file by load_migration_mappings); attribution is which
        # configured file declared the mapping (MigrationMappingsDocument.locator) - both were
        # previously carried on the document but never projected into this digest, so an edit to
        # the artifact's own content/attribution that didn't also change any entry's pointer/target
        # would have gone completely unnoticed by the revision fence. There is no per-artifact
        # "semantic options" concept this mechanism exposes, so that part of §5.3's list has nothing
        # to project (mirroring configuredServiceMappings/destinationBrokerMappings staying explicit
        # empty arrays for categories with no configured instance).
        "contentDigest": document.content_digest,
        "attribution": document.locator,
        "sourceInstanceId": entry.source_instance_id,
        # documentPath is part of this entry's own lookup identity (source_instance_id,
        # document_path, pointer) - omitting it here would mean moving an otherwise identical
        # mapping from one file to another (the same pointer, a different documentPath) changes
        # which canonical entity actually receives the mapped id, without changing this digest, so
        # the revision fence would never notice the resulting graph change.
        "documentPath": entry.document_path,
        "pointer": entry.pointer,
        id_field: entry.target_id,
    }


def _classify_shared_identity_entries(
    shared_identity_index: SharedIdentityMappingIndex,
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """§5.3 names `bundledMigrationMappings` as one context category and `sharedSchemaMappings`/
    `sharedMessageMappings`/`sharedQueueMappings` as three separate ones - a distinction the spec
    text doesn't otherwise define, so this module draws it explicitly (flagged for review): any
    loaded migration document whose artifact id is the fixed §5.1.1 bundled-example constant
    contributes all of its entries (schema, message, and queue alike) to the one
    `bundledMigrationMappings` list; every other configured document's entries are split by kind
    into the three `shared*Mappings` categories instead, since that general mechanism has no
    single-artifact identity to fold entries under.
    """
    bundled: list[dict] = []
    shared_schema: list[dict] = []
    shared_message: list[dict] = []
    shared_queue: list[dict] = []
    for document in shared_identity_index.documents:
        is_bundled = document.artifact_id == BUNDLED_MIGRATION_ARTIFACT_ID
        for entry in document.schema_mappings:
            item = _mapping_entry_context(document, entry, id_field="schemaId")
            (bundled if is_bundled else shared_schema).append(item)
        for entry in document.message_mappings:
            item = _mapping_entry_context(document, entry, id_field="messageId")
            (bundled if is_bundled else shared_message).append(item)
        for entry in document.queue_mappings:
            item = _mapping_entry_context(document, entry, id_field="queueId")
            (bundled if is_bundled else shared_queue).append(item)
    return bundled, shared_schema, shared_message, shared_queue


def _compute_mapping_context_digest(
    binding_index: BindingIndex,
    registry: SourceAdapterRegistry,
    shared_identity_index: SharedIdentityMappingIndex,
) -> str:
    """I1 spec §5.3: the context's input is "the complete canonical index of configured and
    manifest Service bindings, shared Schema/Message mappings, Queue/destination and broker/server/
    namespace mappings, bundled migration mappings, and all active adapter, normalization, and
    mapping-rule identities/versions." `configuredServiceMappings`/`destinationBrokerMappings`
    remain explicit empty arrays - no configured instance of either exists or is needed yet
    ("Explicit empty arrays represent absent mapping categories" - §5.3).
    """
    bundled, shared_schema, shared_message, shared_queue = _classify_shared_identity_entries(
        shared_identity_index
    )
    context = {
        "manifestBindings": sort_entries_by_canonical_bytes(
            [
                {
                    "sourceInstanceId": entry.source_instance_id,
                    "pointerPrefix": entry.pointer_prefix,
                    "serviceId": entry.service_id,
                }
                for entry in binding_index.entries
            ]
        ),
        "configuredServiceMappings": [],
        "sharedSchemaMappings": sort_entries_by_canonical_bytes(shared_schema),
        "sharedMessageMappings": sort_entries_by_canonical_bytes(shared_message),
        "sharedQueueMappings": sort_entries_by_canonical_bytes(shared_queue),
        "destinationBrokerMappings": [],
        "bundledMigrationMappings": sort_entries_by_canonical_bytes(bundled),
        "adapters": sort_entries_by_canonical_bytes(
            [
                {
                    "adapterIdentity": adapter.adapter_identity,
                    "mappingRuleVersion": adapter.mapping_rule_version,
                }
                for adapter in registry.adapters
            ]
        ),
    }
    return compute_mapping_context_digest(context)


@dataclass(frozen=True)
class SourceRunOutcome:
    descriptor_locator: str
    outcome: AdapterOutcome


@dataclass(frozen=True)
class DiscoveryRunResult:
    inventory_status: InventoryStatus
    commit_eligible: bool
    discovery_scope_id: str | None
    scope_definition_digest: str | None
    merged_model: ArchitectureModel
    source_outcomes: dict[str, SourceRunOutcome]
    diagnostics: tuple[IngestionDiagnostic, ...]


def run_filesystem_discovery(
    config: FilesystemSourceConfig,
    *,
    registry: SourceAdapterRegistry | None = None,
    migration_mappings: SharedIdentityMappingIndex | None = None,
) -> DiscoveryRunResult:
    registry = registry or default_registry()
    shared_identity_index = migration_mappings or EMPTY_SHARED_IDENTITY_INDEX
    discovery_outcome = FilesystemSourceDiscoverer(config).discover()

    if not discovery_outcome.enumeration_complete:
        status = classify_inventory_status(source_results=(), discoverer_enumeration_complete=False)
        return DiscoveryRunResult(
            inventory_status=status,
            commit_eligible=run_is_eligible_to_commit(status),
            discovery_scope_id=discovery_outcome.discovery_scope_id,
            scope_definition_digest=discovery_outcome.scope_definition_digest,
            merged_model=ArchitectureModel(),
            source_outcomes={},
            diagnostics=discovery_outcome.diagnostics,
        )

    # Canonical order (by source_instance_id) so permuting discovery order can never change the
    # result - I1 spec §4.2's permutation-independence requirement.
    loaded_sources = tuple(
        sorted(discovery_outcome.loaded_sources, key=lambda s: s.descriptor.source_instance_id)
    )
    run_diagnostics: list[IngestionDiagnostic] = list(discovery_outcome.diagnostics)

    # Phase 1: discover and validate every ArchitectureIdentityBindings manifest before any
    # OpenAPI/AsyncAPI document is mapped (I1 spec §4.2's two-phase evaluation order).
    binding_documents = []
    known_source_instance_ids = {s.descriptor.source_instance_id for s in loaded_sources}
    for loaded in loaded_sources:
        if not _is_identity_bindings_document(loaded.document):
            continue
        parsed, diagnostics = parse_architecture_identity_bindings(
            loaded.document, locator=loaded.descriptor.locator
        )
        run_diagnostics.extend(diagnostics)
        if parsed is not None:
            binding_documents.append(parsed)

    binding_index, binding_index_diagnostics = build_binding_index(
        binding_documents, known_source_instance_ids=known_source_instance_ids
    )
    run_diagnostics.extend(binding_index_diagnostics)

    phase1_failed = bool(binding_index_diagnostics) or any(
        d.code
        in (
            DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID,
            DiagnosticCode.MANIFEST_BINDING_POINTER_INVALID,
            DiagnosticCode.SERVICE_IDENTITY_INVALID,
        )
        for d in run_diagnostics
    )
    if phase1_failed:
        status = classify_inventory_status(source_results=(), discoverer_enumeration_complete=False)
        return DiscoveryRunResult(
            inventory_status=status,
            commit_eligible=run_is_eligible_to_commit(status),
            discovery_scope_id=discovery_outcome.discovery_scope_id,
            scope_definition_digest=discovery_outcome.scope_definition_digest,
            merged_model=ArchitectureModel(),
            source_outcomes={},
            diagnostics=tuple(run_diagnostics),
        )

    resolver = _RunServiceIdentityResolver(_binding_index_to_pointer_bindings(binding_index))
    shared_identity_resolver = _RunSharedIdentityResolver(shared_identity_index)
    run_mapping_context_digest = _compute_mapping_context_digest(
        binding_index, registry, shared_identity_index
    )

    mappable_sources = [
        loaded for loaded in loaded_sources if not _is_identity_bindings_document(loaded.document)
    ]

    source_outcomes: dict[str, SourceRunOutcome] = {}
    phase_upstream_model = ArchitectureModel()

    for phase in registry.phases():
        phase_models: list[ArchitectureModel] = []
        for loaded in mappable_sources:
            source_instance_id = loaded.descriptor.source_instance_id
            if source_instance_id in source_outcomes:
                continue  # already resolved in an earlier phase iteration (shouldn't happen)

            adapter = registry.adapter_for(loaded)
            if adapter is None:
                continue  # handled once, after all phases (no adapter ever claims it)
            if adapter.dependency_phase != phase:
                continue

            enriched = loaded.model_copy(
                update={
                    "descriptor": loaded.descriptor.model_copy(
                        update={
                            "adapter_identity": adapter.adapter_identity,
                            "mapping_rule_id": adapter.adapter_identity,
                            "mapping_rule_version": adapter.mapping_rule_version,
                        }
                    )
                }
            )
            outcome = adapter.map(
                enriched,
                service_identity=resolver,
                shared_identity=shared_identity_resolver,
                upstream_model=phase_upstream_model,
                mapping_context_digest=run_mapping_context_digest,
            )
            source_outcomes[source_instance_id] = SourceRunOutcome(
                descriptor_locator=loaded.descriptor.locator, outcome=outcome
            )
            phase_models.append(outcome.model)

        phase_upstream_model = merge_models([phase_upstream_model, *phase_models])

    unmatched_diagnostics = []
    for loaded in mappable_sources:
        source_instance_id = loaded.descriptor.source_instance_id
        if source_instance_id in source_outcomes:
            continue
        diagnostic = IngestionDiagnostic(
            code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
            message=f"no registered adapter claims {loaded.descriptor.locator!r}",
            source_pointer=loaded.descriptor.locator,
            source_instance_id=source_instance_id,
        )
        unmatched_diagnostics.append(diagnostic)
        source_outcomes[source_instance_id] = SourceRunOutcome(
            descriptor_locator=loaded.descriptor.locator,
            outcome=AdapterOutcome(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                model=ArchitectureModel(),
                diagnostics=(diagnostic,),
                semantic_input_digest=None,
            ),
        )
    run_diagnostics.extend(unmatched_diagnostics)

    source_models = [outcome.outcome.model for outcome in source_outcomes.values()]

    # §8.1/§9.1: "Two current owners explicitly mapped to one shared Schema ID with different
    # canonical hashes are REJECTED_CONFLICT" (and the Message equivalent) - only visible once every
    # source's own claims are collected together, so this runs on the pre-merge per-source model
    # list, before merge_models' own first-wins dedup could discard the disagreement.
    content_conflicts = detect_shared_claim_content_conflicts(source_models)
    if content_conflicts:
        run_diagnostics.extend(content_conflicts)
        return DiscoveryRunResult(
            inventory_status=InventoryStatus.PARTIAL,
            commit_eligible=False,
            discovery_scope_id=discovery_outcome.discovery_scope_id,
            scope_definition_digest=discovery_outcome.scope_definition_digest,
            merged_model=ArchitectureModel(),
            source_outcomes=source_outcomes,
            diagnostics=tuple(run_diagnostics),
        )

    merged_model = merge_models(source_models)
    status = classify_inventory_status(
        source_results=[o.outcome.result for o in source_outcomes.values()],
        discoverer_enumeration_complete=True,
    )

    return DiscoveryRunResult(
        inventory_status=status,
        commit_eligible=run_is_eligible_to_commit(status),
        discovery_scope_id=discovery_outcome.discovery_scope_id,
        scope_definition_digest=discovery_outcome.scope_definition_digest,
        merged_model=merged_model,
        source_outcomes=source_outcomes,
        diagnostics=tuple(run_diagnostics),
    )
