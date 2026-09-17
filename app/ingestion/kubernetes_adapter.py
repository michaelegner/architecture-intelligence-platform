from app.canonical.model import ArchitectureModel
from app.sources.identity import semantic_input_digest
from app.sources.model import DiagnosticCode, IngestionResult, LoadedSource, SourceKind
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

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
    """I2 Draft 0.2 slice 2b-i: the minimal adapter that turns a Kubernetes `LoadedSource`'s
    discovery-time diagnostics into the correct `AdapterOutcome`, and a clean one into an
    `ACCEPTED` outcome with an empty `ArchitectureModel`. Without a registered adapter, every
    Kubernetes source would instead be rejected by the orchestrator's generic unmatched-adapter
    fallback (`DiagnosticCode.DOCUMENT_PARSE_INVALID`), masking this slice's own diagnostics -
    real canonical projection (`InfrastructureEntity`/`Contribution`/`Claim` population) is slice
    3's job; this adapter deliberately emits nothing semantic yet.
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

        # Deliberately interim: the real §6 "normalized allowlisted resource projection ordered by
        # logical key" digest doesn't exist until slice 3's real mapping logic does. Using the
        # envelope's own content_sha256 as a stand-in is over-eager (any byte-level envelope change
        # looks like a semantic change) but never under-eager, and is replaced wholesale once slice
        # 3 lands - disclosed here rather than silently narrowed.
        digest = semantic_input_digest(
            normalized_document_projection_bytes=loaded.descriptor.content_sha256.encode("utf-8"),
            mapping_context_digest=mapping_context_digest,
        )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=ArchitectureModel(),
            diagnostics=(),
            semantic_input_digest=digest,
        )
