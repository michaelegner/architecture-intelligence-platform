"""v0.7.1 I2.2: the Kafka Service-mapping adapter (I2.1 contract §2-§5). It turns an accepted artifact
into one entry carrier per group and one evidence carrier, and nothing else: it never resolves a
Service (the `service_identity` resolver is deliberately unused - resolution depends on the
snapshot's declared Services and happens in the attribution projection), and it never creates a
`KafkaConsumerGroup`, Topic, Subscription or Service. Registered like every other adapter.
"""

from app.canonical.kafka_service_mapping import (
    KafkaServiceMappingEntry,
    KafkaServiceMappingEvidence,
)
from app.canonical.model import ArchitectureModel
from app.ingestion.kafka_service_mapping_discoverer import (
    ARTIFACT_KEY,
    ARTIFACT_SHA256_KEY,
    CONFIGURED_SOURCE_ID_KEY,
)
from app.sources.identity import (
    kafka_consumer_id,
    kafka_service_mapping_entry_id,
    kafka_service_mapping_evidence_id,
    kafka_service_mapping_source_revision,
    normalized_document_and_reference_projection_bytes,
    semantic_input_digest,
)
from app.sources.kafka_service_mapping_contract import SCHEMA_ID, KafkaServiceMappingArtifact
from app.sources.model import DiagnosticCode, IngestionResult, LoadedSource, SourceKind
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

# Contract §4.
_RESULT_BY_CODE = {
    DiagnosticCode.KSM_UNSUPPORTED_SCHEMA: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.KSM_BROKER_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KSM_ENVIRONMENT_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KSM_DUPLICATE_GROUP: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KSM_ARTIFACT_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KSM_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.KSM_DUPLICATE_SOURCE: IngestionResult.REJECTED_CONFLICT,
}


class KafkaServiceMappingSourceAdapter:
    adapter_identity = "kafka-service-mapping-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        """Contract §1: the schema string, never the filename. A rejected artifact carries its
        diagnostic and no document, and is still this adapter's to report with its frozen result."""
        if loaded.descriptor.source_kind != SourceKind.KAFKA_SERVICE_MAPPING:
            return False
        if loaded.diagnostics:
            return True
        return loaded.document.get(ARTIFACT_KEY, {}).get("schema") == SCHEMA_ID

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
            return AdapterOutcome(
                result=_RESULT_BY_CODE[loaded.diagnostics[0].code],
                model=ArchitectureModel(),
                diagnostics=tuple(loaded.diagnostics),
                semantic_input_digest=None,
            )

        document = loaded.document
        artifact = KafkaServiceMappingArtifact.model_validate(document[ARTIFACT_KEY])
        source_id = loaded.descriptor.source_instance_id
        evidence_id = kafka_service_mapping_evidence_id(source_id)
        entries = [
            KafkaServiceMappingEntry(
                id=kafka_service_mapping_entry_id(
                    source_instance_id=source_id, group_id=mapping.group_id
                ),
                source_instance_id=source_id,
                broker_id=artifact.broker_id,
                environment=artifact.environment,
                group_id=mapping.group_id,
                consumer_id=kafka_consumer_id(
                    broker_id=artifact.broker_id,
                    environment=artifact.environment,
                    group_id=mapping.group_id,
                ),
                service_name=mapping.service_name,
                service_namespace=mapping.service_namespace,
                evidence_ids=[evidence_id],
            )
            for mapping in artifact.mappings
        ]
        evidence = KafkaServiceMappingEvidence(
            id=evidence_id,
            source_instance_id=source_id,
            configured_source_id=document[CONFIGURED_SOURCE_ID_KEY],
            broker_id=artifact.broker_id,
            environment=artifact.environment,
            artifact_sha256=document[ARTIFACT_SHA256_KEY],
            source_revision=kafka_service_mapping_source_revision(document[ARTIFACT_SHA256_KEY]),
        )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=ArchitectureModel(
                kafka_service_mapping_entries=sorted(entries, key=lambda e: e.id),
                kafka_service_mapping_evidence=[evidence],
            ),
            diagnostics=(),
            semantic_input_digest=semantic_input_digest(
                normalized_document_projection_bytes=normalized_document_and_reference_projection_bytes(
                    {"kafka-service-mapping": document}
                ),
                mapping_context_digest=mapping_context_digest,
            ),
        )
