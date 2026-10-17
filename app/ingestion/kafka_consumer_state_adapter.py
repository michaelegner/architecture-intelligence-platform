"""v0.7.1 I1.3: the Kafka consumer-state replay adapter (I1.1 contract §4-§7). It consumes the
validated, normalized capture only; it never contacts Kafka. Registered like every other
declared-source adapter - the orchestrator does not branch on source kind.

It creates no Topic, Subscription or Service. A live assignment becomes an attachment only when its
`topic:owned:` id is among the declared ids the discoverer resolved; otherwise it is counted in a
fixed-text diagnostic and nothing is written for it.
"""

from collections import defaultdict

from app.canonical.kafka_consumer_state import (
    KafkaCaptureEvidence,
    KafkaConsumerAttachment,
    KafkaConsumerGroup,
    kafka_capture_evidence_id,
)
from app.canonical.model import ArchitectureModel
from app.common.encoding import unicode_nfc
from app.common.jcs import JSONValue, canonical_json_bytes
from app.ingestion.kafka_consumer_state_discoverer import (
    CONFIGURED_SOURCE_ID_KEY,
    DECLARED_TOPIC_IDS_KEY,
)
from app.sources.identity import (
    kafka_attachment_id,
    kafka_consumer_id,
    kafka_scope_digest,
    normalized_document_and_reference_projection_bytes,
    semantic_input_digest,
)
from app.sources.kafka_consumer_state_contract import STABLE, KafkaConsumerStateEnvelope
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    LoadedSource,
    SourceKind,
)
from app.sources.owner_ids import topic_owned_id
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

_RESULT_BY_CODE = {
    DiagnosticCode.KAFKA_BROKER_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_ENVIRONMENT_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_SCOPE_MISMATCH: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_GROUP_NOT_DESCRIBED: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_STATE_NOT_STABLE: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_CAPTURE_INCOMPLETE: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_CAPTURE_UNREDACTED: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_CAPTURE_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.KAFKA_UNSUPPORTED_SCHEMA: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.KAFKA_DUPLICATE_SOURCE: IngestionResult.REJECTED_CONFLICT,
    DiagnosticCode.KAFKA_STALE_CAPTURE: IngestionResult.REJECTED_CONFLICT,
    DiagnosticCode.KAFKA_CAPTURE_CONFLICT: IngestionResult.REJECTED_CONFLICT,
}


def _support_json(member_partitions: list[list[int]]) -> str:
    ordered: list[JSONValue] = [list[JSONValue](p) for p in sorted(member_partitions)]
    support: dict[str, JSONValue] = {
        "member_count": len(member_partitions),
        "member_partitions": ordered,
    }
    return canonical_json_bytes(support).decode("utf-8")


class KafkaConsumerStateSourceAdapter:
    adapter_identity = "kafka-consumer-state-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return loaded.descriptor.source_kind == SourceKind.KAFKA_CONSUMER_STATE

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
        envelope = KafkaConsumerStateEnvelope.model_validate(document["capture"])
        source_id = loaded.descriptor.source_instance_id
        declared = frozenset(document[DECLARED_TOPIC_IDS_KEY])
        evidence_id = kafka_capture_evidence_id(source_id)

        groups: list[KafkaConsumerGroup] = []
        attachments: list[KafkaConsumerAttachment] = []
        undeclared = 0
        for group in envelope.groups:
            consumer_id = kafka_consumer_id(
                broker_id=envelope.broker_id,
                environment=envelope.environment,
                group_id=group.group_id,
            )
            groups.append(
                KafkaConsumerGroup(
                    id=consumer_id,
                    source_instance_id=source_id,
                    group_id=group.group_id,
                    broker_id=envelope.broker_id,
                    environment=envelope.environment,
                )
            )
            if group.state != STABLE:
                continue  # Empty / Dead: explicit zero live attachment, no attachment rows
            # Only the member count and each member's partitions are kept (review of #583): member
            # ids, client ids and hosts are client-supplied text that may carry anything, and no
            # identity, mapping or attribution rule needs them (I0 D3), so they never enter AIP state.
            by_topic: dict[str, list[list[int]]] = defaultdict(list)
            for member in group.members:
                for assignment in member.assignments:
                    by_topic[unicode_nfc(assignment.topic)].append(sorted(assignment.partitions))
            for topic in sorted(by_topic):
                topic_id = topic_owned_id(
                    stable_broker_id=envelope.broker_id,
                    normalized_namespace_or_empty="",
                    exact_topic_address=topic,
                )
                if topic_id not in declared:
                    undeclared += 1
                    continue
                attachments.append(
                    KafkaConsumerAttachment(
                        id=kafka_attachment_id(consumer_id=consumer_id, topic_id=topic_id),
                        source_instance_id=source_id,
                        consumer_id=consumer_id,
                        topic_id=topic_id,
                        captured_at=envelope.captured_at,
                        evidence_ids=[evidence_id],
                        support_json=_support_json(by_topic[topic]),
                    )
                )
        evidence = KafkaCaptureEvidence(
            id=evidence_id,
            source_instance_id=source_id,
            configured_source_id=document[CONFIGURED_SOURCE_ID_KEY],
            broker_id=envelope.broker_id,
            environment=envelope.environment,
            captured_at=envelope.captured_at,
            capture_content_sha256=document["capture_content_sha256"],
            scope_digest=kafka_scope_digest(envelope.group_scope),
            source_revision=envelope.source_revision,
            group_states_json=canonical_json_bytes(
                {group.group_id: group.state for group in envelope.groups}
            ).decode("utf-8"),
        )
        model = ArchitectureModel(
            kafka_consumer_groups=sorted(groups, key=lambda g: g.id),
            kafka_consumer_attachments=sorted(attachments, key=lambda a: a.id),
            kafka_capture_evidence=[evidence],
        )
        digest = semantic_input_digest(
            normalized_document_projection_bytes=normalized_document_and_reference_projection_bytes(
                {"kafka-consumer-state": document}
            ),
            mapping_context_digest=mapping_context_digest,
        )
        if undeclared:
            return AdapterOutcome(
                result=IngestionResult.ACCEPTED_WITH_LIMITATIONS,
                model=model,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.KAFKA_TOPIC_NOT_DECLARED,
                        message=(
                            f"{undeclared} live assignment(s) target a Topic that is not "
                            "declared; no attachment was recorded for them"
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
