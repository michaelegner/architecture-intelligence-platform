"""v0.7.1 I3.2 - the `mode: "evidence"` resolver of `get_destination_consumers` (I3 spec §4).

It reads nothing and keeps no ref history: for the supplied snapshot and query context it rebuilds,
from the same `DestinationScope` the query uses, the finite map of every ref that query could have
issued, and resolves only refs in that map. A forged, cross-snapshot or cross-context ref is simply
not in the map. Payloads are closed and sanitized: ids, revisions, digests, T, the group id and the
mapping exactly as the operator wrote it - no credentials, member/client/host text, raw files or
other graph properties.
"""

from collections.abc import Callable, Mapping
from typing import Any

from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    SCHEMA_VERSION,
    TOOL_NAME,
    AttachmentEvidence,
    AttributionReason,
    DestinationConsumersAnswer,
    DestinationConsumersEvidenceData,
    DestinationConsumersEvidenceRequest,
    EvidenceEntry,
    EvidenceKind,
    EvidenceStatus,
    LimitationCode,
    MappingEvidence,
)
from app.architecture_intelligence.destination_consumer_projection import (
    DestinationScope,
    limitation,
    open_scope,
    refusal_answer,
)

type Row = Mapping[str, Any]
type Candidates = dict[str, tuple[EvidenceKind, Callable[[], AttachmentEvidence | MappingEvidence]]]

_ATTRIBUTION = "kafka_consumer_attribution_v1"


def _by_id(rows: Any) -> dict[str, Row]:
    return {row["id"]: row for row in rows or ()}


def _attachment_payload(scope: DestinationScope, attribution: Row) -> AttachmentEvidence:
    [capture] = [
        row for row in scope.captures if row["id"] in attribution["attachment_evidence_ids"]
    ]
    return AttachmentEvidence(
        kind="KAFKA_ATTACHMENT",
        consumer_id=attribution["consumer_id"],
        group_id=scope.groups[attribution["consumer_id"]],
        topic_id=attribution["topic_id"],
        captured_at=attribution["captured_at"],
        capture_source_instance_id=capture["source_instance_id"],
        capture_source_revision=capture["source_revision"],
        capture_content_sha256=capture["capture_content_sha256"],
    )


def _mapping_payload(
    scope: DestinationScope, attribution: Row, entry_id: str, block: Row
) -> MappingEvidence:
    entry = _by_id(block.get("mapping_entries"))[entry_id]
    [source] = [
        row for row in block.get("mapping_sources") or () if row["id"] in entry["evidence_ids"]
    ]
    group = _by_id(block.get("groups"))[attribution["consumer_id"]]
    reading = _by_id(group["entries"])[entry_id]
    return MappingEvidence(
        kind="KAFKA_SERVICE_MAPPING",
        consumer_id=attribution["consumer_id"],
        group_id=scope.groups[attribution["consumer_id"]],
        service_name=entry["service_name"],
        service_namespace=entry.get("service_namespace"),
        service_id=reading.get("service_id"),
        reason=AttributionReason(reading["reason"]) if "reason" in reading else None,
        mapping_source_instance_id=source["source_instance_id"],
        mapping_source_revision=source["source_revision"],
        artifact_sha256=source["artifact_sha256"],
    )


def evidence_candidates(scope: DestinationScope) -> Candidates:
    """Every ref the query of `scope` issues, across all pages, with a lazy payload builder."""
    block = scope.state.get(_ATTRIBUTION) or {}
    candidates: Candidates = {}
    for attribution in scope.attributions:
        candidates[scope.ref(EvidenceKind.KAFKA_ATTACHMENT, scope.attachment_ids(attribution))] = (
            EvidenceKind.KAFKA_ATTACHMENT,
            lambda attribution=attribution: _attachment_payload(scope, attribution),
        )
        for entry in attribution["mapping_entries"]:
            candidates[scope.ref(EvidenceKind.KAFKA_SERVICE_MAPPING, scope.mapping_ids(entry))] = (
                EvidenceKind.KAFKA_SERVICE_MAPPING,
                lambda attribution=attribution, entry_id=entry["id"]: _mapping_payload(
                    scope, attribution, entry_id, block
                ),
            )
    return candidates


def resolve_destination_consumer_evidence(
    request: DestinationConsumersEvidenceRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> DestinationConsumersAnswer:
    """The evidence answer for the current snapshot whose canonical state is `state`. Refusals are
    decided in `open_scope` order (there is no cursor)."""
    opened = open_scope(
        state, request.context(), snapshot=snapshot, asserted_snapshot_ids=[request.snapshot_id]
    )
    if isinstance(opened, LimitationCode):
        return refusal_answer(producer, snapshot, opened, mode="evidence")
    candidates = evidence_candidates(opened)
    entries = []
    for ref in request.evidence_refs:
        found = candidates.get(ref)
        if found is None:
            entries.append(EvidenceEntry(ref=ref, status=EvidenceStatus.NOT_RESOLVED))
        else:
            kind, payload = found
            entries.append(
                EvidenceEntry(
                    ref=ref, status=EvidenceStatus.RESOLVED, kind=kind, evidence=payload()
                )
            )
    data = DestinationConsumersEvidenceData(request_context=request.context(), entries=entries)
    codes = data.expected_limitation_codes()
    outcome = (
        Outcome.ANSWERED
        if not codes
        else Outcome.PARTIAL
        if data.any_resolved()
        else Outcome.NOT_ANSWERED
    )
    return DestinationConsumersAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="evidence",
        outcome=outcome,
        snapshot=snapshot,
        data=data,
        limitations=[limitation(code) for code in sorted(codes, key=lambda code: code.value)],
    )
