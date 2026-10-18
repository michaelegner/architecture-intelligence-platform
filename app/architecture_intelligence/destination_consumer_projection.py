"""v0.7.1 I3.1 - the `mode: "query"` destination-consumer answer (I3 spec §2-§3).

It reads nothing: the caller hands it the `canonical_snapshot_state` it fingerprinted, including the
declared Topic brokers (`kafka_topic_brokers_v1`), so the answer is a function of the snapshot. Rows come
from the I2 `kafka_consumer_attribution_v1` block. When there is no mapping carrier there is no
block, and the rows come from the same pure I2 `attribution_block` called with empty mapping inputs:
no reconciliation rule is reimplemented here. The projection only selects, filters, mints opaque
evidence refs and pages.
"""

from collections.abc import Callable, Mapping
from typing import Any

from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    SCHEMA_VERSION,
    TOOL_NAME,
    AttributionOutcome,
    AttributionReason,
    CaptureSource,
    ConsumerRow,
    Cursor,
    DestinationConsumersAnswer,
    DestinationConsumersData,
    DestinationConsumersQueryRequest,
    EvidenceKind,
    Limitation,
    LimitationCode,
    Page,
    RowLimitation,
    decode_cursor,
    encode_cursor,
    evidence_ref,
    query_context_digest,
)
from app.architecture_intelligence.kafka_consumer_attribution import attribution_block

type Row = Mapping[str, Any]

_CODE = LimitationCode
KAFKA_PROTOCOL = "kafka"
_KAFKA_STATE = "kafka_consumer_state_v1"
_ATTRIBUTION = "kafka_consumer_attribution_v1"
_TOPIC_BROKERS = "kafka_topic_brokers_v1"

_MESSAGES = {
    _CODE.SNAPSHOT_NOT_AVAILABLE: "the requested snapshot is not the current snapshot",
    _CODE.UNKNOWN_DESTINATION: "no declared Topic has this destination id",
    _CODE.DESTINATION_NOT_KAFKA_TOPIC: "the destination is not a Kafka Topic",
    _CODE.BROKER_MISMATCH: "the destination is not declared on the requested broker",
    _CODE.NO_ACCEPTED_CAPTURE: (
        "no accepted Kafka consumer-state capture exists for this broker and environment"
    ),
    _CODE.CURSOR_QUERY_MISMATCH: "the cursor was issued for another query",
    _CODE.CAPTURE_SCOPE_LIMITED: (
        "each capture covers only its configured consumer groups at its own capture time; "
        "the rows are not a complete list of consumers"
    ),
    _CODE.NO_MAPPING_SOURCE: (
        "no accepted Service-mapping source exists for this broker and environment"
    ),
    _CODE.MORE_ROWS_AVAILABLE: "more rows are available with next_cursor",
    _CODE.EVIDENCE_REF_NOT_RESOLVED: "an evidence ref was not issued for this query and snapshot",
}


def limitation(code: LimitationCode) -> Limitation:
    return Limitation(code=code, message=_MESSAGES[code])


def refusal_answer(
    producer: Producer, snapshot: SnapshotRef | None, code: LimitationCode
) -> DestinationConsumersAnswer:
    """Nothing was evaluated: `data` is null and exactly one refusal code is set."""
    return DestinationConsumersAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="query",
        outcome=Outcome.NOT_ANSWERED,
        snapshot=snapshot,
        data=None,
        limitations=[limitation(code)],
    )


def _rows(state: Mapping[str, Any], key: str, section: str) -> list[Row]:
    return list((state.get(key) or {}).get(section) or [])


def destination_refusal(
    state: Mapping[str, Any], destination_id: str, broker_id: str
) -> LimitationCode | None:
    """Spec §2 destination checks, in order. A Queue id or a Topic bound to another protocol is not
    a Kafka Topic. A Topic without a protocol binding (the usual Kafka AsyncAPI shape) counts as
    Kafka through its declaration broker; the accepted Kafka capture check follows. Without any
    Kafka consumer state there is no accepted capture for any broker, and the declared brokers are
    not in the snapshot, so the answer is `NO_ACCEPTED_CAPTURE`."""
    topic = next((row for row in state.get("topics") or () if row["id"] == destination_id), None)
    if topic is None:
        if any(row["id"] == destination_id for row in state.get("queues") or ()):
            return _CODE.DESTINATION_NOT_KAFKA_TOPIC
        return _CODE.UNKNOWN_DESTINATION
    if topic.get("protocol") not in (None, KAFKA_PROTOCOL):
        return _CODE.DESTINATION_NOT_KAFKA_TOPIC
    if _KAFKA_STATE not in state:
        return _CODE.NO_ACCEPTED_CAPTURE
    declared_brokers = {
        row["broker_id"]
        for row in state.get(_TOPIC_BROKERS) or ()
        if row["topic_id"] == destination_id
    }
    if broker_id not in declared_brokers:
        return _CODE.BROKER_MISMATCH
    return None


def _in_scope(row: Row, broker_id: str, environment: str) -> bool:
    return row["broker_id"] == broker_id and row["environment"] == environment


def _attributions(state: Mapping[str, Any]) -> list[Row]:
    block = state.get(_ATTRIBUTION)
    if block is None:
        block = attribution_block(
            sources=[],
            entries=[],
            attachments=_rows(state, _KAFKA_STATE, "attachments"),
            consumer_groups=_rows(state, _KAFKA_STATE, "groups"),
            service_rows=[],
            aliases={},
        )
    return list(block["attributions"])


def _row(
    attribution: Row, group_id: str, ref: Callable[[EvidenceKind, list[str]], str]
) -> ConsumerRow:
    mapping_refs = {
        entry["id"]: ref(EvidenceKind.KAFKA_SERVICE_MAPPING, [entry["id"], *entry["evidence_ids"]])
        for entry in attribution["mapping_entries"]
    }
    return ConsumerRow(
        consumer_id=attribution["consumer_id"],
        group_id=group_id,
        outcome=AttributionOutcome(attribution["outcome"]),
        service_id=attribution.get("service_id"),
        reason=AttributionReason(attribution["reason"]) if "reason" in attribution else None,
        limitations=sorted(
            (
                RowLimitation(
                    reason=AttributionReason(item["reason"]),
                    mapping_evidence_ref=mapping_refs[item["entry_id"]],
                )
                for item in attribution["limitations"]
            ),
            key=lambda item: item.mapping_evidence_ref,
        ),
        captured_at=attribution["captured_at"],
        attachment_evidence_refs=[
            ref(
                EvidenceKind.KAFKA_ATTACHMENT,
                [attribution["id"], *attribution["attachment_evidence_ids"]],
            )
        ],
        mapping_evidence_refs=sorted(mapping_refs.values()),
    )


def project_destination_consumers(
    request: DestinationConsumersQueryRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> DestinationConsumersAnswer:
    """The query answer for the current snapshot whose canonical state is `state`. Refusals are
    decided in order: snapshot, destination (unknown, not a Kafka Topic, broker mismatch), accepted
    capture, cursor. Without any Kafka consumer state, `NO_ACCEPTED_CAPTURE` comes before the
    broker check: the declared Topic brokers are only in the snapshot beside that state."""
    cursor = decode_cursor(request.cursor) if request.cursor is not None else None
    asserted = {request.snapshot_id, cursor.snapshot_id if cursor else None} - {None}
    if asserted - {snapshot.snapshot_id}:
        return refusal_answer(producer, snapshot, _CODE.SNAPSHOT_NOT_AVAILABLE)
    context = request.context()
    refused = destination_refusal(state, context.destination_id, context.broker_id)
    if refused is not None:
        return refusal_answer(producer, snapshot, refused)
    broker_id, environment = context.broker_id, context.environment
    captures = [
        row
        for row in _rows(state, _KAFKA_STATE, "evidence")
        if _in_scope(row, broker_id, environment)
    ]
    if not captures:
        return refusal_answer(producer, snapshot, _CODE.NO_ACCEPTED_CAPTURE)
    digest = query_context_digest(context)
    if cursor is not None and cursor.query_digest != digest:
        return refusal_answer(producer, snapshot, _CODE.CURSOR_QUERY_MISMATCH)

    # Broker and environment live on the I1 group and capture rows, never on the Topic: a Topic id
    # carries no environment, so one Topic can be attached in several environments.
    groups = {
        row["id"]: row["group_id"]
        for row in _rows(state, _KAFKA_STATE, "groups")
        if _in_scope(row, broker_id, environment)
    }

    def ref(kind: EvidenceKind, internal_ids: list[str]) -> str:
        return evidence_ref(
            snapshot_id=snapshot.snapshot_id,
            query_digest=digest,
            kind=kind,
            internal_ids=internal_ids,
        )

    rows = sorted(
        (
            _row(attribution, groups[attribution["consumer_id"]], ref)
            for attribution in _attributions(state)
            if attribution["topic_id"] == context.destination_id
            and attribution["consumer_id"] in groups
        ),
        key=lambda row: row.consumer_id,
    )
    remaining = [row for row in rows if cursor is None or row.consumer_id > cursor.after]
    page_rows = remaining[: request.limit]
    next_cursor = (
        encode_cursor(
            Cursor(
                v=1,
                after=page_rows[-1].consumer_id,
                query_digest=digest,
                schema_version=SCHEMA_VERSION,
                snapshot_id=snapshot.snapshot_id,
            )
        )
        if len(remaining) > request.limit
        else None
    )
    data = DestinationConsumersData(
        request_context=context,
        capture_sources=sorted(
            (
                CaptureSource(
                    source_instance_id=row["source_instance_id"],
                    captured_at=row["captured_at"],
                    source_revision=row["source_revision"],
                    scope_digest=row["scope_digest"],
                )
                for row in captures
            ),
            key=lambda source: source.source_instance_id,
        ),
        mapping_source_present=any(
            _in_scope(row, broker_id, environment)
            for row in _rows(state, _ATTRIBUTION, "mapping_sources")
        ),
        rows=page_rows,
        page=Page(limit=request.limit, returned=len(page_rows), next_cursor=next_cursor),
    )
    codes = data.expected_limitation_codes()
    return DestinationConsumersAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="query",
        outcome=Outcome.PARTIAL,
        snapshot=snapshot,
        data=data,
        limitations=[limitation(code) for code in sorted(codes, key=lambda code: code.value)],
    )
