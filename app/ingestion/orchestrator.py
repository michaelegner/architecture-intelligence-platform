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
from app.sources.commit_gate import classify_inventory_status, run_is_eligible_to_commit
from app.sources.identity import mapping_context_digest as compute_mapping_context_digest
from app.sources.inventory import InventoryStatus
from app.sources.jcs import sort_entries_by_canonical_bytes
from app.sources.manifest_bindings import (
    BindingIndex,
    build_binding_index,
    parse_architecture_identity_bindings,
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


def _compute_mapping_context_digest(
    binding_index: BindingIndex, registry: SourceAdapterRegistry
) -> str:
    """I1 spec §5.3: the context's input is "the complete canonical index of configured and
    manifest Service bindings, shared Schema/Message mappings, Queue/destination and broker/server/
    namespace mappings, bundled migration mappings, and all active adapter, normalization, and
    mapping-rule identities/versions." 3a's context is honestly small: only the manifest-binding
    index and the registered adapters' own identities are populated; every other mapping category
    not yet wired in 3a is an explicit empty array ("Explicit empty arrays represent absent mapping
    categories" - §5.3).
    """
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
        "sharedSchemaMappings": [],
        "sharedMessageMappings": [],
        "sharedQueueMappings": [],
        "destinationBrokerMappings": [],
        "bundledMigrationMappings": [],
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
    config: FilesystemSourceConfig, *, registry: SourceAdapterRegistry | None = None
) -> DiscoveryRunResult:
    registry = registry or default_registry()
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
    run_mapping_context_digest = _compute_mapping_context_digest(binding_index, registry)

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

    merged_model = merge_models([outcome.outcome.model for outcome in source_outcomes.values()])
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
