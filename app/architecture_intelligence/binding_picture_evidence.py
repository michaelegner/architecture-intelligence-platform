"""v0.8 I2c: the binding-picture evidence mode (I2 spec §6). It resolves only refs that the query
of the same context issues at the current snapshot: it reruns the I2b projection for that context,
unpaged, records every minted ref with its subject, and builds bounded, sanitized payloads. There
is no ref history, so forged, cross-context and stale refs are all simply `NOT_RESOLVED`. No member
id, client id or host exists in AIP state, so none can appear.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.architecture_intelligence.binding_picture_contracts import (
    SCHEMA_VERSION,
    TOOL_NAME,
    BindingEvidenceKind,
    BindingPictureAnswer,
    BindingPictureData,
    BindingPictureEvidenceData,
    BindingPictureEvidenceRequest,
    EvidenceEntry,
    EvidenceStatus,
    Limitation,
    LimitationCode,
    PromiseEvidence,
)
from app.architecture_intelligence.binding_picture_projection import (
    Minted,
    project_binding_picture,
)
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    AttachmentEvidence,
    AttributionReason,
    MappingEvidence,
)

Row = Mapping[str, Any]
_NOT_RESOLVED = Limitation(
    code=LimitationCode.EVIDENCE_REF_NOT_RESOLVED,
    message="an evidence ref was not issued for this query and snapshot",
)


def _by_id(rows: Any) -> dict[str, Row]:
    return {row["id"]: row for row in rows or ()}


def _promise(state: Mapping[str, Any], promise: Row) -> PromiseEvidence:
    catalog = state["event_catalog_v1"]
    environment = promise["environment"]
    [source] = [r for r in catalog["evidence"] if r["environment"] == environment]
    [lookup] = [
        r
        for r in catalog["event_topics"]
        if r["environment"] == environment and r["event_id"] == promise["event_id"]
    ]
    return PromiseEvidence(
        kind="CATALOG_PROMISE",
        catalog_source_instance_id=source["source_instance_id"],
        catalog_digest=source["catalog_digest"],
        lookup_digest=source["lookup_digest"],
        source_revision=source["source_revision"],
        file=promise["file"],
        service_name=promise["service_name"],
        direction=promise["direction"],
        event_id=promise["event_id"],
        event_version=promise["event_version"],
        topic=lookup["topic"],
        lookup_repository=lookup["repository"],
        lookup_commit=lookup["commit"],
        lookup_path=lookup["path"],
    )


def _group_id(state: Mapping[str, Any], consumer_id: str) -> str:
    return _by_id(state["kafka_consumer_state_v1"]["groups"])[consumer_id]["group_id"]


def _attachment(state: Mapping[str, Any], attribution: Row) -> AttachmentEvidence:
    [capture] = [
        row
        for row in state["kafka_consumer_state_v1"]["evidence"]
        if row["id"] in attribution["attachment_evidence_ids"]
    ]
    return AttachmentEvidence(
        kind="KAFKA_ATTACHMENT",
        consumer_id=attribution["consumer_id"],
        group_id=_group_id(state, attribution["consumer_id"]),
        topic_id=attribution["topic_id"],
        captured_at=attribution["captured_at"],
        capture_source_instance_id=capture["source_instance_id"],
        capture_source_revision=capture["source_revision"],
        capture_content_sha256=capture["capture_content_sha256"],
    )


def _mapping(state: Mapping[str, Any], attribution: Row, entry_id: str) -> MappingEvidence:
    block = state["kafka_consumer_attribution_v1"]
    entry = _by_id(block["mapping_entries"])[entry_id]
    [source] = [row for row in block["mapping_sources"] if row["id"] in entry["evidence_ids"]]
    reading = _by_id(_by_id(block["groups"])[attribution["consumer_id"]]["entries"])[entry_id]
    return MappingEvidence(
        kind="KAFKA_SERVICE_MAPPING",
        consumer_id=attribution["consumer_id"],
        group_id=_group_id(state, attribution["consumer_id"]),
        service_name=entry["service_name"],
        service_namespace=entry.get("service_namespace"),
        service_id=reading.get("service_id"),
        reason=AttributionReason(reading["reason"]) if "reason" in reading else None,
        mapping_source_instance_id=source["source_instance_id"],
        mapping_source_revision=source["source_revision"],
        artifact_sha256=source["artifact_sha256"],
    )


def _payload(state: Mapping[str, Any], kind: BindingEvidenceKind, subject: Any):
    if kind is BindingEvidenceKind.CATALOG_PROMISE:
        return _promise(state, subject)
    if kind is BindingEvidenceKind.KAFKA_ATTACHMENT:
        return _attachment(state, subject)
    attribution, entry_id = subject
    return _mapping(state, attribution, entry_id)


def resolve_binding_picture_evidence(
    request: BindingPictureEvidenceRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> BindingPictureAnswer:
    """The evidence answer at the current snapshot. The query's own refusals (snapshot first, so a
    non-current `snapshot_id` is `SNAPSHOT_NOT_AVAILABLE`) apply unchanged in evidence mode."""
    minted: dict[str, Minted] = {}
    query = project_binding_picture(
        request.as_query(), state, snapshot=snapshot, producer=producer, minted=minted
    )
    if not isinstance(query.data, BindingPictureData):
        return query.model_copy(update={"mode": "evidence"})
    entries = []
    for ref in request.evidence_refs:
        found = minted.get(ref)
        if found is None:
            entries.append(EvidenceEntry(ref=ref, status=EvidenceStatus.NOT_RESOLVED))
            continue
        kind, subject = found
        entries.append(
            EvidenceEntry(
                ref=ref,
                status=EvidenceStatus.RESOLVED,
                kind=kind,
                evidence=_payload(state, kind, subject),
            )
        )
    resolved = sum(entry.status is EvidenceStatus.RESOLVED for entry in entries)
    outcome = (
        Outcome.ANSWERED
        if resolved == len(entries)
        else Outcome.PARTIAL
        if resolved
        else Outcome.NOT_ANSWERED
    )
    return BindingPictureAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="evidence",
        outcome=outcome,
        snapshot=snapshot,
        data=BindingPictureEvidenceData(
            request_context=query.data.request_context, entries=entries
        ),
        limitations=[] if resolved == len(entries) else [_NOT_RESOLVED],
    )
