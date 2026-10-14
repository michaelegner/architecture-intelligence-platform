"""v0.7.0 I2.2b: the APISIX measurement replay adapter (I2.1 contract §3-§5, §8). It consumes the
validated, normalized fixture only; it never contacts a gateway. Registered like every other
declared-source adapter - the orchestrator does not branch on source kind.
"""

from app.canonical.model import ArchitectureModel
from app.sources.apisix_measurement_contract import (
    MANIFEST_SCHEMA,
    MappingArtifact,
    ValidatedMeasurement,
    mapping_from_document,
    parse_extract,
    parse_manifest,
)
from app.sources.apisix_measurement_mapping import map_measurement
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

# I2.1 contract §8: the per-source result of each discovery-time diagnostic.
_RESULT_BY_CODE = {
    DiagnosticCode.GWM_MANIFEST_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GWM_BINDING_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GWM_EXTRACT_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GWM_INSTANCE_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GWM_MAPPING_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.GWM_SCHEMA_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.GWM_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.GWM_DUPLICATE_SOURCE: IngestionResult.REJECTED_CONFLICT,
}


class ApisixMeasurementSourceAdapter:
    adapter_identity = "apisix-measurement-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return loaded.descriptor.source_kind == SourceKind.APISIX_MEASUREMENT

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

        document = loaded.document
        assert document["manifest"].get("schema") == MANIFEST_SCHEMA  # the discoverer validated it
        validated = ValidatedMeasurement(
            manifest=parse_manifest(document["manifest"]),
            start=parse_extract(document["start_extract"].encode("utf-8")),
            end=parse_extract(document["end_extract"].encode("utf-8")),
        )
        artifact: MappingArtifact | None = None
        if document["mapping"] is not None:
            artifact = mapping_from_document(
                document["mapping"], gateway_instance_id=validated.manifest.gateway_instance_id
            )
        mapping = map_measurement(
            validated, artifact, source_instance_id=loaded.descriptor.source_instance_id
        )
        model = ArchitectureModel(
            measurement_windows=[mapping.window],
            measurement_evidence=[mapping.evidence],
            measurement_series=mapping.series,
            measurement_limitations=mapping.limitations,
            measurement_mapping_entries=mapping.mapping_entries,
        )
        digest = semantic_input_digest(
            normalized_document_projection_bytes=normalized_document_and_reference_projection_bytes(
                {"apisix-measurement": document}
            ),
            mapping_context_digest=mapping_context_digest,
        )
        if mapping.limitation_count:
            return AdapterOutcome(
                result=IngestionResult.ACCEPTED_WITH_LIMITATIONS,
                model=model,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.GWM_MEASUREMENT_LIMITATIONS,
                        message=(
                            f"{mapping.limitation_count} measurement facts were recorded as "
                            "limitations and not read as usage"
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
