from app.canonical import ids
from app.canonical.infrastructure import (
    KUBERNETES_SOURCE_TYPE,
    InfrastructureClaim,
    InfrastructureClaimKind,
    InfrastructureContribution,
    InfrastructureEntityKind,
    KubernetesEvidenceMode,
)
from app.canonical.model import ArchitectureModel
from app.provenance.model import Provenance
from app.sources.identity import (
    normalized_document_and_reference_projection_bytes,
    semantic_input_digest,
)
from app.sources.kubernetes_mapping import map_kubernetes_resources
from app.sources.model import DiagnosticCode, IngestionResult, LoadedSource, SourceKind
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

_MAPPING_REJECTIONS = frozenset(
    {IngestionResult.REJECTED_INVALID, IngestionResult.REJECTED_CONFLICT}
)

# I2 Draft 0.2 §10: the exact outcome each discovery-time diagnostic this slice's discoverer can
# attach maps to. K8S_SNAPSHOT_INCOMPLETE's REJECTED_INVALID matches the "exact source/run
# distinction" table's "a loaded envelope declares an incomplete capture" row exactly.
_RESULT_BY_DIAGNOSTIC_CODE = {
    DiagnosticCode.K8S_CLUSTER_IDENTITY_UNRESOLVED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.K8S_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.K8S_SNAPSHOT_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE: IngestionResult.REJECTED_INVALID,
}


class KubernetesSourceAdapter:
    """I2 Draft 0.2: turns a Kubernetes `LoadedSource`'s discovery-time diagnostics into the
    correct `AdapterOutcome` (slice 2b-i), and on a clean source, calls `kubernetes_mapping` (slice
    3a) to build the real `InfrastructureEntity`/`Contribution`/`WORKLOAD_EXISTS`-`Claim`/
    `Provenance` set for every admitted Workload/Pod resource. Without a registered adapter, every
    Kubernetes source would instead be rejected by the orchestrator's generic unmatched-adapter
    fallback (`DiagnosticCode.DOCUMENT_PARSE_INVALID`), masking this slice's own diagnostics.
    """

    adapter_identity = "kubernetes-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return loaded.descriptor.source_kind == SourceKind.KUBERNETES

    def map(
        self,
        loaded: LoadedSource,
        *,
        service_identity: ServiceIdentityResolver,
        shared_identity: SharedIdentityResolver,
        upstream_model: ArchitectureModel,
        mapping_context_digest: str,
    ) -> AdapterOutcome:
        if loaded.diagnostics:
            # `validate_kubernetes_snapshot`/the discoverer's own registration-binding check
            # already computed the correct `IngestionResult` - `LoadedSource` has nowhere to carry
            # it forward except `diagnostics`, so it's re-derived from the one diagnostic's own
            # code, which already determines the outcome uniquely and so cannot disagree.
            diagnostic = loaded.diagnostics[0]
            result = _RESULT_BY_DIAGNOSTIC_CODE[diagnostic.code]
            return AdapterOutcome(
                result=result,
                model=ArchitectureModel(),
                diagnostics=tuple(loaded.diagnostics),
                semantic_input_digest=None,
            )

        envelope_source = loaded.document["source"]
        envelope_scope = loaded.document["scope"]
        mapping_result = map_kubernetes_resources(
            loaded.kubernetes_resources,
            cluster_uid=envelope_source["clusterUid"],
            requires_capture_identity=(
                envelope_source["mode"] == KubernetesEvidenceMode.CAPTURED_RESOURCE
            ),
            scope_namespaces=tuple(envelope_scope["namespaces"]),
        )
        if mapping_result.result in _MAPPING_REJECTIONS:
            return AdapterOutcome(
                result=mapping_result.result,
                model=ArchitectureModel(),
                diagnostics=mapping_result.diagnostics,
                semantic_input_digest=None,
            )

        evidence_mode = KubernetesEvidenceMode(envelope_source["mode"])
        revision = loaded.descriptor.declared_provider_revision

        entities = []
        contributions = []
        claims = []
        provenance_records = []
        for mapped in mapping_result.entities:
            entities.append(mapped.entity)
            # One evidence id per (entity, contributing file) - §6: "source pointers remain
            # provenance and are sorted when multiple files represent one object."
            entity_evidence_refs = sorted(
                ids.evidence_id(KUBERNETES_SOURCE_TYPE, f"{mapped.entity.id}#{pointer}", revision)
                for pointer in mapped.source_pointers
            )
            for pointer in mapped.source_pointers:
                provenance_records.append(
                    Provenance(
                        id=ids.evidence_id(
                            KUBERNETES_SOURCE_TYPE, f"{mapped.entity.id}#{pointer}", revision
                        ),
                        source_type=KUBERNETES_SOURCE_TYPE,
                        source_file=pointer,
                        source_revision=revision,
                    )
                )
            contributions.append(
                InfrastructureContribution(
                    entity_id=mapped.entity.id,
                    source_instance_id=loaded.descriptor.source_instance_id,
                    evidence_mode=evidence_mode,
                    resource_semantic_digest=mapped.resource_semantic_digest,
                    captured_resource_uid=mapped.captured_uid,
                    evidence_refs=entity_evidence_refs,
                    mapping_rule_id=self.adapter_identity,
                    mapping_rule_version=self.mapping_rule_version,
                )
            )
            if mapped.entity.entity_kind is InfrastructureEntityKind.KUBERNETES_WORKLOAD:
                claims.append(
                    InfrastructureClaim(
                        kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
                        subject_id=mapped.entity.id,
                        object_id=None,
                        evidence_refs=entity_evidence_refs,
                        mapping_rule_id=self.adapter_identity,
                        mapping_rule_version=self.mapping_rule_version,
                    )
                )

        # §6: "normalize the allowlisted resource projection, ordering resources by logical key" -
        # covers every admitted resource (Namespace/ReplicaSet/Service/Ingress included), not only
        # the Workload/Pod kinds this slice promotes to entities - a Service selector value change,
        # for example, must still invalidate replay even though no entity's own projection changed.
        # `logical_id` IS that logical key, so this reuses I1's existing path-ordered projection
        # hash rather than inventing a parallel ordering rule for Kubernetes.
        #
        # `capturedResourceUid` is folded in here, separately from `resource.projection` itself:
        # §7.1's `resource_semantic_digest` (the per-resource digest used for cross-source/
        # within-source conflict comparison) deliberately excludes capture-only UID, but §6 also
        # requires "any changed UID... MUST trigger owner-chain reevaluation" at the SOURCE level -
        # a same-source UID replacement with an unchanged allowlisted projection must still change
        # this overall `semantic_input_digest` (review round, PR #200: without this, a UID-only
        # replacement was classified REPLAY_NO_OP, silently rewriting the contribution's captured
        # UID without advancing the graph revision fence).
        projection_bytes = normalized_document_and_reference_projection_bytes(
            {
                resource.logical_id: {
                    **resource.projection,
                    "capturedResourceUid": resource.captured_uid,
                }
                for resource in mapping_result.resources
            }
        )
        digest = semantic_input_digest(
            normalized_document_projection_bytes=projection_bytes,
            mapping_context_digest=mapping_context_digest,
        )

        model = ArchitectureModel(
            infrastructure_entities=entities,
            infrastructure_contributions=contributions,
            infrastructure_claims=claims,
            provenance=provenance_records,
        )
        return AdapterOutcome(
            result=mapping_result.result,
            model=model,
            diagnostics=mapping_result.diagnostics,
            semantic_input_digest=digest,
        )
