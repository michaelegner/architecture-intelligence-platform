"""v0.7.0 I1.4: the APISIX replay adapter (I1.1 contract §3-§4, §7). It consumes the validated,
normalized capture fixture only; it never contacts a gateway (I1 spec §3.2). Registered like every
other declared-source adapter - the orchestrator does not branch on source kind.
"""

from app.canonical.model import ArchitectureModel
from app.sources.apisix_contract import ApisixCaptureEnvelope
from app.sources.apisix_mapping import map_capture
from app.sources.identity import (
    normalized_document_and_reference_projection_bytes,
    semantic_input_digest,
)
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    LoadedSource,
    SourceKind,
)
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

# I1.1 contract §7: the per-source result of each discovery-time diagnostic.
_RESULT_BY_CODE = {
    DiagnosticCode.GW_CAPTURE_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GW_CAPTURE_INCONSISTENT: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GW_CAPTURE_INCOMPLETE: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GW_CAPTURE_UNREDACTED: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GW_INSTANCE_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GW_CAPTURE_SURFACE_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.GW_CAPTURE_SCHEMA_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.GW_CAPTURE_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.GW_DUPLICATE_INSTANCE: IngestionResult.REJECTED_CONFLICT,
}


class ApisixSourceAdapter:
    adapter_identity = "apisix-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return loaded.descriptor.source_kind == SourceKind.APISIX

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
            diagnostic = loaded.diagnostics[0]
            return AdapterOutcome(
                result=_RESULT_BY_CODE[diagnostic.code],
                model=ArchitectureModel(),
                diagnostics=tuple(loaded.diagnostics),
                semantic_input_digest=None,
            )

        mapping = map_capture(ApisixCaptureEnvelope.model_validate(loaded.document))
        model = ArchitectureModel(
            gateway_source_evidence=[mapping.source_evidence],
            gateway_consumers=mapping.consumers,
            gateway_routes=mapping.routes,
            gateway_services=mapping.services,
            gateway_configured_accesses=mapping.accesses,
            gateway_limitations=mapping.limitations,
        )
        digest = semantic_input_digest(
            normalized_document_projection_bytes=normalized_document_and_reference_projection_bytes(
                {"apisix-capture": loaded.document}
            ),
            mapping_context_digest=mapping_context_digest,
        )
        if mapping.limitations:
            return AdapterOutcome(
                result=IngestionResult.ACCEPTED_WITH_LIMITATIONS,
                model=model,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.GW_CONFIGURATION_LIMITATIONS,
                        message=(
                            f"{len(mapping.limitations)} source facts were recorded as limitations "
                            "and not interpreted as configured access"
                        ),
                        source_pointer=loaded.descriptor.locator,
                    ),
                ),
                semantic_input_digest=digest,
            )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=model,
            diagnostics=(),
            semantic_input_digest=digest,
        )
