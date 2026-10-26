"""v0.8 I2a: the EventCatalog adapter (I2 §2). It turns accepted catalog declarations into the
promise-record carriers - one per promise, Bounded Context membership and event -> Topic entry, plus
one evidence carrier - and nothing else. It never resolves a Service and never creates a Service,
Topic, Subscription or relation: a promise never manufactures Current State (doctrine §4.3).
"""

from typing import Literal

from app.canonical.event_catalog import (
    CatalogEventTopic,
    CatalogEvidence,
    CatalogMembership,
    CatalogPromise,
)
from app.canonical.model import ArchitectureModel
from app.ingestion.event_catalog_discoverer import (
    CONFIGURED_SOURCE_ID_KEY,
    DECLARATIONS_KEY,
    ENVIRONMENT_KEY,
)
from app.sources.identity import (
    catalog_event_topic_id,
    catalog_evidence_id,
    catalog_membership_id,
    catalog_promise_id,
    normalized_document_and_reference_projection_bytes,
    semantic_input_digest,
)
from app.sources.model import DiagnosticCode, IngestionResult, LoadedSource, SourceKind
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver, SharedIdentityResolver

_RESULT_BY_CODE = {
    DiagnosticCode.EVENTCATALOG_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.EVENTCATALOG_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.EVENTCATALOG_REFERENCE_UNRESOLVED: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.EVENTCATALOG_MEMBERSHIP_INVALID: IngestionResult.REJECTED_INVALID,
    DiagnosticCode.EVENTCATALOG_DUPLICATE_SOURCE: IngestionResult.REJECTED_CONFLICT,
}


_DIRECTIONS: tuple[tuple[Literal["SENDS", "RECEIVES"], str], ...] = (
    ("SENDS", "sends"),
    ("RECEIVES", "receives"),
)


class EventCatalogSourceAdapter:
    adapter_identity = "event-catalog-adapter@1"
    mapping_rule_version = "1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return loaded.descriptor.source_kind == SourceKind.EVENT_CATALOG

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
        declarations = document[DECLARATIONS_KEY]
        environment = document[ENVIRONMENT_KEY]
        source_id = loaded.descriptor.source_instance_id
        evidence_ids = [catalog_evidence_id(source_id)]
        promises = [
            CatalogPromise(
                id=catalog_promise_id(
                    source_instance_id=source_id,
                    service_name=service["id"],
                    direction=direction,
                    event_id=reference["event_id"],
                ),
                service_name=service["id"],
                direction=direction,
                event_id=reference["event_id"],
                event_version=reference["version"],
                file=service["path"],
                environment=environment,
                evidence_ids=evidence_ids,
            )
            for service in declarations["services"]
            for direction, key in _DIRECTIONS
            for reference in service[key]
        ]
        memberships = [
            CatalogMembership(
                id=catalog_membership_id(
                    source_instance_id=source_id,
                    bounded_context_id=domain["id"],
                    service_name=service_name,
                ),
                bounded_context_id=domain["id"],
                bounded_context_name=domain["name"],
                owners=list(domain["owners"]),
                service_name=service_name,
                file=domain["path"],
                environment=environment,
                evidence_ids=evidence_ids,
            )
            for domain in declarations["domains"]
            for service_name in domain["services"]
        ]
        event_topics = [
            CatalogEventTopic(
                id=catalog_event_topic_id(source_instance_id=source_id, event_id=entry["event_id"]),
                event_id=entry["event_id"],
                topic=entry["topic"],
                repository=entry["repository"],
                commit=entry["commit"],
                path=entry["path"],
                environment=environment,
                evidence_ids=evidence_ids,
            )
            for entry in declarations["lookup"]
        ]
        evidence = CatalogEvidence(
            id=evidence_ids[0],
            source_instance_id=source_id,
            configured_source_id=document[CONFIGURED_SOURCE_ID_KEY],
            environment=environment,
            catalog_digest=declarations["catalog_digest"],
            lookup_digest=declarations["lookup_digest"],
            source_revision=declarations["source_revision"],
        )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=ArchitectureModel(
                catalog_promises=sorted(promises, key=lambda p: p.id),
                catalog_memberships=sorted(memberships, key=lambda m: m.id),
                catalog_event_topics=sorted(event_topics, key=lambda t: t.id),
                catalog_evidence=[evidence],
            ),
            diagnostics=(),
            semantic_input_digest=semantic_input_digest(
                normalized_document_projection_bytes=normalized_document_and_reference_projection_bytes(
                    {"event-catalog": document}
                ),
                mapping_context_digest=mapping_context_digest,
            ),
        )
