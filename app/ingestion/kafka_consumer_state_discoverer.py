"""v0.7.1 I1.3: the Kafka consumer-state source discoverer (I1.1 contract §1, §4, §7-§8). One
registration is one normalized capture file, written by `app.kafka_capture` (the AIP runtime never
contacts Kafka). Mirrors `ApisixMeasurementSourceDiscoverer`: the source identity needs only
configured values, so a missing or invalid capture still yields an identified source that the
adapter rejects with the right per-source result, and the run becomes PARTIAL (nothing commits).

Two inputs come from the import request, which has the graph driver: the committed capture of this
source (for the R14/R15 ordering rule) and a resolver that says which of the Topic ids a capture
points at are already declared. Every diagnostic message is fixed text: no group id, topic name,
member id or host ever reaches one.
"""

import hashlib
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import datetime

from app.common.encoding import unicode_nfc
from app.sources.identity import (
    discovery_scope_id,
    kafka_consumer_state_source_instance_id,
    normalize_relative_posix_path,
    scope_definition_digest,
)
from app.sources.kafka_consumer_state_contract import STABLE, KafkaConsumerStateEnvelope
from app.sources.kafka_consumer_state_loader import RejectedKafkaCapture, load_capture
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    KafkaConsumerStateSourceConfig,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.owner_ids import topic_owned_id
from app.sources.registry import DiscoveryOutcome

_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()
DECLARED_TOPIC_IDS_KEY = "declared_topic_ids"
CONFIGURED_SOURCE_ID_KEY = "configured_source_id"

MESSAGES = {
    DiagnosticCode.KAFKA_BROKER_MISMATCH: "the capture's broker id does not match the registration",
    DiagnosticCode.KAFKA_ENVIRONMENT_MISMATCH: "the capture's environment does not match the registration",
    DiagnosticCode.KAFKA_SCOPE_MISMATCH: "the capture's group scope does not match the registered allow-list",
    DiagnosticCode.KAFKA_GROUP_NOT_DESCRIBED: "an allow-listed consumer group is missing from the capture",
    DiagnosticCode.KAFKA_STATE_NOT_STABLE: "a consumer group is in a transitional or unknown state",
    DiagnosticCode.KAFKA_CAPTURE_INCOMPLETE: "the capture is incomplete or a group could not be described",
    DiagnosticCode.KAFKA_CAPTURE_UNREDACTED: "the capture contains credential or security material",
    DiagnosticCode.KAFKA_CAPTURE_INVALID: "the Kafka consumer-state capture is missing or malformed",
    DiagnosticCode.KAFKA_UNSUPPORTED_SCHEMA: "the Kafka consumer-state capture schema is not supported",
    DiagnosticCode.KAFKA_DUPLICATE_SOURCE: "another registration declares the same broker, environment and a common group",
    DiagnosticCode.KAFKA_STALE_CAPTURE: "the capture is older than the latest accepted capture of this source",
    DiagnosticCode.KAFKA_CAPTURE_CONFLICT: "a different capture exists for the same capture time",
}  # fmt: skip


@dataclass(frozen=True)
class PriorKafkaCapture:
    """The last accepted capture of this source instance, read from its committed evidence carrier."""

    captured_at: str
    content_sha256: str


TopicResolver = Callable[[Collection[str]], frozenset[str]]


def candidate_topic_ids(envelope: KafkaConsumerStateEnvelope) -> frozenset[str]:
    """The `topic:owned:` ids of every live assignment (contract §6): the registered broker id, the
    empty namespace and the NFC-normalized exact topic name."""
    return frozenset(
        topic_owned_id(
            stable_broker_id=envelope.broker_id,
            normalized_namespace_or_empty="",
            exact_topic_address=unicode_nfc(assignment.topic),
        )
        for group in envelope.groups
        if group.state == STABLE
        for member in group.members
        for assignment in member.assignments
    )


def capture_ordering_problem(
    captured_at: str, content_sha256: str, prior: PriorKafkaCapture | None
) -> DiagnosticCode | None:
    """I1.1 contract §4 capture ordering (R14, R15). Used at discovery time and again inside the
    commit transaction, against the evidence actually committed then."""
    if prior is None:
        return None
    captured = datetime.fromisoformat(captured_at)
    committed = datetime.fromisoformat(prior.captured_at)
    if captured < committed:
        return DiagnosticCode.KAFKA_STALE_CAPTURE
    if captured == committed and content_sha256 != prior.content_sha256:
        return DiagnosticCode.KAFKA_CAPTURE_CONFLICT
    return None


class KafkaConsumerStateSourceDiscoverer:
    source_kind = SourceKind.KAFKA_CONSUMER_STATE

    def __init__(
        self,
        config: KafkaConsumerStateSourceConfig,
        *,
        duplicate_registration: bool = False,
        declared_topic_resolver: TopicResolver | None = None,
        prior_capture: PriorKafkaCapture | None = None,
    ):
        self._config = config
        self._duplicate = duplicate_registration
        self._resolver = declared_topic_resolver or (lambda _ids: frozenset())
        self._prior = prior_capture
        self.discoverer_identity = "kafka-consumer-state-discoverer@1"

    def _loaded(
        self,
        *,
        instance_id: str,
        scope_id: str,
        scope_digest: str,
        document: dict,
        diagnostics: list[IngestionDiagnostic],
        content_sha256: str,
        revision: str | None,
    ) -> DiscoveryOutcome:
        config = self._config
        loaded = LoadedSource(
            descriptor=SourceDescriptor(
                source_instance_id=instance_id,
                source_kind=SourceKind.KAFKA_CONSUMER_STATE,
                locator=str(config.root / config.capture_relative_path),
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
            loaded_sources=(loaded,),
            enumeration_complete=True,
            diagnostics=(),
            discovery_scope_id=scope_id,
            scope_definition_digest=scope_digest,
        )

    def discover(self) -> DiscoveryOutcome:
        config = self._config
        scope_id = discovery_scope_id(
            configured_scope_id=config.resolved_scope_id,
            stable_target_identity=config.resolved_stable_target_identity,
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
        instance_id = kafka_consumer_state_source_instance_id(
            configured_source_id=config.id,
            broker_id=config.broker_id,
            environment=config.environment,
            consumer_groups=config.consumer_groups,
        )
        common = {"instance_id": instance_id, "scope_id": scope_id, "scope_digest": scope_digest}

        def reject(
            code: DiagnosticCode, pointer: str, content_sha256: str = _EMPTY_CONTENT_SHA256
        ) -> DiscoveryOutcome:
            return self._loaded(
                document={},
                diagnostics=[
                    IngestionDiagnostic(code=code, message=MESSAGES[code], source_pointer=pointer)
                ],
                content_sha256=content_sha256,
                revision=None,
                **common,
            )

        if self._duplicate:
            return reject(DiagnosticCode.KAFKA_DUPLICATE_SOURCE, config.capture_relative_path)
        result = load_capture(config)
        if isinstance(result, RejectedKafkaCapture):
            return reject(DiagnosticCode(result.problem.code), result.problem.subject or "/capture")
        ordering = capture_ordering_problem(
            result.envelope.captured_at, result.content_sha256, self._prior
        )
        if ordering is not None:
            return reject(ordering, "/captured_at", result.content_sha256)
        candidates = candidate_topic_ids(result.envelope)
        declared = sorted(self._resolver(candidates) & candidates)
        document = {
            "capture": result.envelope.model_dump(by_alias=True),
            "capture_content_sha256": result.content_sha256,
            CONFIGURED_SOURCE_ID_KEY: config.id,
            DECLARED_TOPIC_IDS_KEY: declared,
        }
        return self._loaded(
            document=document,
            diagnostics=[],
            content_sha256=result.content_sha256,
            revision=result.source_revision,
            **common,
        )
