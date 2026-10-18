"""v0.7.1 I2.2: the Kafka Service-mapping source discoverer (I2.1 contract §1-§4). One registration is
one operator-supplied artifact. Mirrors `KafkaConsumerStateSourceDiscoverer` without its graph
inputs: a mapping has no ordering rule and resolves no Topic, so discovery needs only the file. The
source identity needs only configured values, so a missing or invalid artifact still yields an
identified source that the adapter rejects with the right per-source result, and the run commits
nothing. Every diagnostic message is fixed text: no group id or Service name ever reaches one.
"""

import hashlib

from app.sources.identity import (
    discovery_scope_id,
    kafka_service_mapping_source_instance_id,
    normalize_relative_posix_path,
    scope_definition_digest,
)
from app.sources.kafka_service_mapping_loader import RejectedMappingArtifact, load_mapping_artifact
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    KafkaServiceMappingSourceConfig,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import DiscoveryOutcome

_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()
ARTIFACT_KEY = "artifact"
ARTIFACT_SHA256_KEY = "artifact_sha256"
CONFIGURED_SOURCE_ID_KEY = "configured_source_id"

MESSAGES = {
    DiagnosticCode.KSM_UNSUPPORTED_SCHEMA: "the Kafka Service-mapping artifact schema is not supported",
    DiagnosticCode.KSM_BROKER_MISMATCH: "the mapping artifact's broker id does not match the registration",
    DiagnosticCode.KSM_ENVIRONMENT_MISMATCH: "the mapping artifact's environment does not match the registration",
    DiagnosticCode.KSM_DUPLICATE_GROUP: "the mapping artifact lists a consumer group more than once",
    DiagnosticCode.KSM_ARTIFACT_INVALID: "the Kafka Service-mapping artifact is missing or malformed",
    DiagnosticCode.KSM_LIMIT_EXCEEDED: "the Kafka Service-mapping artifact exceeds a size, entry or nesting limit",
    DiagnosticCode.KSM_DUPLICATE_SOURCE: "another Kafka Service-mapping registration uses the same id",
}  # fmt: skip


class KafkaServiceMappingSourceDiscoverer:
    source_kind = SourceKind.KAFKA_SERVICE_MAPPING

    def __init__(
        self, config: KafkaServiceMappingSourceConfig, *, duplicate_registration: bool = False
    ):
        self._config = config
        self._duplicate = duplicate_registration
        self.discoverer_identity = "kafka-service-mapping-discoverer@1"

    def discover(self) -> DiscoveryOutcome:
        config = self._config
        scope_id = discovery_scope_id(
            configured_scope_id=config.id,
            stable_target_identity=config.stable_target_identity,
        )
        scope_digest = scope_definition_digest(
            discovery_scope_id=scope_id,
            normalized_roots=[normalize_relative_posix_path(str(config.root))],
            filters=[],
            inclusion_rules=[],
        )
        if not config.root.is_dir():
            return DiscoveryOutcome(
                loaded_sources=(),
                enumeration_complete=False,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.SOURCE_ROOT_UNAVAILABLE,
                        message="configured source root does not exist or is not a directory",
                        source_pointer=str(config.root),
                    ),
                ),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
            )

        def loaded(
            *,
            document: dict,
            diagnostics: list[IngestionDiagnostic],
            content_sha256: str,
            revision: str | None,
        ) -> DiscoveryOutcome:
            source = LoadedSource(
                descriptor=SourceDescriptor(
                    source_instance_id=kafka_service_mapping_source_instance_id(
                        configured_source_id=config.id,
                        broker_id=config.broker_id,
                        environment=config.environment,
                    ),
                    source_kind=SourceKind.KAFKA_SERVICE_MAPPING,
                    locator=str(config.root / config.artifact_relative_path),
                    discovery_scope_id=scope_id,
                    scope_definition_digest=scope_digest,
                    declared_provider_revision=revision,
                    content_sha256=content_sha256,
                    semantic_input_digest="",
                    mapping_context_digest="",
                    adapter_identity="",
                    mapping_rule_id="",
                    mapping_rule_version="",
                ),
                document=document,
                diagnostics=diagnostics,
                source_root=str(config.root),
            )
            return DiscoveryOutcome(
                loaded_sources=(source,),
                enumeration_complete=True,
                diagnostics=(),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
            )

        def reject(code: DiagnosticCode, pointer: str) -> DiscoveryOutcome:
            return loaded(
                document={},
                diagnostics=[
                    IngestionDiagnostic(code=code, message=MESSAGES[code], source_pointer=pointer)
                ],
                content_sha256=_EMPTY_CONTENT_SHA256,
                revision=None,
            )

        if self._duplicate:
            return reject(DiagnosticCode.KSM_DUPLICATE_SOURCE, config.artifact_relative_path)
        result = load_mapping_artifact(config)
        if isinstance(result, RejectedMappingArtifact):
            return reject(
                DiagnosticCode(result.problem.code), result.problem.subject or "/artifact"
            )
        return loaded(
            document={
                # `exclude_none`: an absent namespace stays absent, so the adapter's re-validation
                # sees exactly the accepted shape (an explicit null is a rejection, contract §3).
                ARTIFACT_KEY: result.artifact.model_dump(by_alias=True, exclude_none=True),
                ARTIFACT_SHA256_KEY: result.content_sha256,
                CONFIGURED_SOURCE_ID_KEY: config.id,
            },
            diagnostics=[],
            content_sha256=result.content_sha256,
            revision=result.source_revision,
        )
