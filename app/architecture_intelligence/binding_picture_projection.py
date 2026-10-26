"""v0.8 I2b: the binding picture (I2 spec §4-§6) as a pure function of one snapshot state.

Rows are the union of promise candidates (catalog `RECEIVES` promises of Services in capture scope)
and attachment candidates (every live attachment on a requested broker), one per broker x Topic x
consumer. The status rule is R1-R7 of §4 (R3 before R7); the crossing is D9 (§5). Three claims stay
apart (§3): crossing classification, observed attachment, and cross-broker delivery, which this
answer never states. Promises never fill a gap in Current State (doctrine §4.3).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.architecture_intelligence.binding_picture_contracts import (
    ALWAYS_PRESENT,
    SCHEMA_VERSION,
    TOOL_NAME,
    AssessmentReason,
    AssessmentStatus,
    BindingEvidenceKind,
    BindingPictureAnswer,
    BindingPictureData,
    BindingPictureQueryRequest,
    BindingRow,
    CaptureSource,
    CatalogSource,
    Crossing,
    Cursor,
    Limitation,
    LimitationCode,
    Page,
    ProducerEntry,
    RequestContext,
    binding_evidence_ref,
    decode_cursor,
    encode_cursor,
    query_context_digest,
)
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.kafka_consumer_attribution import attribution_block
from app.sources.owner_ids import topic_owned_id

Row = Mapping[str, Any]
_CODE = LimitationCode
_CATALOG = "event_catalog_v1"
_KAFKA_STATE = "kafka_consumer_state_v1"
_ATTRIBUTION = "kafka_consumer_attribution_v1"
_TOPIC_BROKERS = "kafka_topic_brokers_v1"
_RESOLVED = "RESOLVED"

_MESSAGES = {
    _CODE.SNAPSHOT_NOT_AVAILABLE: "the requested snapshot is not the current snapshot",
    _CODE.NO_ACCEPTED_CATALOG: "no accepted EventCatalog exists for this environment",
    _CODE.UNKNOWN_BOUNDED_CONTEXT: (
        "no catalog domain has this id (bounded_context_id must be a catalog domain id, "
        "such as catalog-management)"
    ),
    _CODE.NO_ACCEPTED_CAPTURE: (
        "no accepted Kafka consumer-state capture exists for a requested broker in this environment"
    ),
    _CODE.CURSOR_QUERY_MISMATCH: "the cursor was issued for another query",
    _CODE.CAPTURE_SCOPE_LIMITED: (
        "each capture covers only its configured consumer groups at its own capture time"
    ),
    _CODE.PROMISES_ASSUMED_CONFIRMED: (
        "catalog entries count as confirmed promises by a disclosed demonstration assumption"
    ),
    _CODE.PRODUCER_SIDE_DECLARED_ONLY: "producers are declared evidence only, never observed",
    _CODE.EVENT_HANDLING_NOT_ESTABLISHED: (
        "an attachment shows a consumer group's topic assignment, not which event types it handles"
    ),
    _CODE.CROSS_BROKER_DELIVERY_NOT_ESTABLISHED: (
        "a row's crossing relies on producers on another broker; delivery between brokers is not "
        "established by AIP"
    ),
    _CODE.MORE_ROWS_AVAILABLE: "more rows are available with next_cursor",
}


def _limitation(code: LimitationCode, *, missing_brokers: Sequence[str] = ()) -> Limitation:
    """In a partial answer, `NO_ACCEPTED_CAPTURE` names every requested broker without an accepted
    capture (I2 §6); the broker ids are the caller's own request values."""
    if code is _CODE.NO_ACCEPTED_CAPTURE and missing_brokers:
        return Limitation(
            code=code,
            message="no accepted Kafka consumer-state capture exists in this environment for "
            f"the requested broker(s): {', '.join(missing_brokers)}",
        )
    return Limitation(code=code, message=_MESSAGES[code])


def refusal_answer(
    producer: Producer, snapshot: SnapshotRef | None, code: LimitationCode
) -> BindingPictureAnswer:
    return BindingPictureAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="query",
        outcome=Outcome.NOT_ANSWERED,
        snapshot=snapshot,
        data=None,
        limitations=[_limitation(code)],
    )


def _section(state: Mapping[str, Any], key: str, section: str) -> list[Row]:
    return list((state.get(key) or {}).get(section, []))


def _attribution(state: Mapping[str, Any]) -> Mapping[str, Any]:
    """The v0.7.1 attribution block, or the same pure rule over no mapping (every row `NO_MAPPING`)."""
    block = state.get(_ATTRIBUTION)
    if block is not None:
        return block
    return attribution_block(
        sources=[],
        entries=[],
        attachments=_section(state, _KAFKA_STATE, "attachments"),
        consumer_groups=_section(state, _KAFKA_STATE, "groups"),
        service_rows=[],
        aliases={},
    )


@dataclass
class _Candidate:
    topic_name: str
    topic_id: str | None
    service_id: str | None
    promises: list[Row] = field(default_factory=list)
    # Every supporting attribution: several groups of one Service may attach to one Topic.
    attributions: list[Row] = field(default_factory=list)
    group_ids: set[str] = field(default_factory=set)
    scope_t: str | None = None


@dataclass(frozen=True)
class _Catalog:
    """The catalog of the environment, read once: promises, memberships and resolutions."""

    source: Row
    promises: tuple[Row, ...]
    event_topic: Mapping[str, str]
    service_of_name: Mapping[str, str]
    name_of_service: Mapping[str, str]
    context_of_service: Mapping[str, str]
    contexts: frozenset[str]

    @classmethod
    def read(cls, state: Mapping[str, Any], environment: str) -> _Catalog | None:
        def rows(section: str) -> list[Row]:
            return [
                r for r in _section(state, _CATALOG, section) if r["environment"] == environment
            ]

        evidence = rows("evidence")
        if not evidence:
            return None
        resolved = {
            r["service_name"]: r["service_id"]
            for r in _section(state, _CATALOG, "service_resolutions")
            if r["outcome"] == _RESOLVED
        }
        memberships = rows("memberships")
        return cls(
            source=evidence[0],
            promises=tuple(rows("promises")),
            event_topic={r["event_id"]: r["topic"] for r in rows("event_topics")},
            service_of_name=resolved,
            name_of_service={service_id: name for name, service_id in resolved.items()},
            context_of_service={
                resolved[m["service_name"]]: m["bounded_context_id"]
                for m in memberships
                if m["service_name"] in resolved
            },
            contexts=frozenset(m["bounded_context_id"] for m in memberships),
        )


def _single_time(attributions: list[Row]) -> str | None:
    """The capture time when every supporting attachment shares one T; otherwise none is invented
    (the capture sources still list each T)."""
    times = {row["captured_at"] for row in attributions}
    return times.pop() if len(times) == 1 else None


def _crossing(selected: str, consumer: str | None, producers: list[str | None]) -> Crossing:
    """I2 §5. Unknown membership on either side, or no producer, is `UNRESOLVED`."""
    if consumer is None or not producers or None in producers:
        return Crossing.UNRESOLVED
    if consumer == selected:
        return Crossing.INSIDE if set(producers) == {selected} else Crossing.INBOUND
    return Crossing.OUTBOUND if selected in producers else Crossing.NONE


def project_binding_picture(
    request: BindingPictureQueryRequest,
    state: Mapping[str, Any],
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> BindingPictureAnswer:
    """The query answer for the snapshot whose canonical state is `state`. Refusals in order:
    snapshot, catalog, Bounded Context, capture, cursor."""
    cursor = decode_cursor(request.cursor) if request.cursor is not None else None
    asserted = {request.snapshot_id, cursor.snapshot_id if cursor else None} - {None}
    if asserted - {snapshot.snapshot_id}:
        return refusal_answer(producer, snapshot, _CODE.SNAPSHOT_NOT_AVAILABLE)
    environment = request.environment
    catalog = _Catalog.read(state, environment)
    if catalog is None:
        return refusal_answer(producer, snapshot, _CODE.NO_ACCEPTED_CATALOG)
    selected = request.bounded_context_id
    if selected not in catalog.contexts:
        return refusal_answer(producer, snapshot, _CODE.UNKNOWN_BOUNDED_CONTEXT)

    # Every accepted capture, grouped by broker: several captures with disjoint allow-lists may
    # share a broker and environment, and are never collapsed into one T (I2 §6).
    captures: dict[str, list[Row]] = defaultdict(list)
    for row in sorted(
        _section(state, _KAFKA_STATE, "evidence"), key=lambda row: row["source_instance_id"]
    ):
        if row["environment"] == environment:
            captures[row["broker_id"]].append(row)
    captured_at = {
        row["source_instance_id"]: row["captured_at"] for rows in captures.values() for row in rows
    }
    requested = sorted(request.broker_ids or captures)
    if not requested or not any(captures.get(broker) for broker in requested):
        return refusal_answer(producer, snapshot, _CODE.NO_ACCEPTED_CAPTURE)
    context = RequestContext(
        bounded_context_id=selected, environment=environment, broker_ids=requested
    )
    digest = query_context_digest(context)
    if cursor is not None and cursor.query_digest != digest:
        return refusal_answer(producer, snapshot, _CODE.CURSOR_QUERY_MISMATCH)

    attribution = _attribution(state)
    topics = {row["id"]: row["name"] for row in state.get("topics", [])}
    topic_broker = {row["topic_id"]: row["broker_id"] for row in state.get(_TOPIC_BROKERS, [])}
    # Brokers of the environment: those with an accepted capture or mapping source in it. Topics
    # and PUBLISHES_TO carry no environment, so no other broker counts (I2 §5).
    environment_brokers = set(captures) | {
        row["broker_id"]
        for row in attribution.get("mapping_sources", [])
        if row["environment"] == environment
    }
    producers_of: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for relation in state.get("relations", []):
        if relation["type"] != "PUBLISHES_TO" or relation["target_id"] not in topics:
            continue
        broker = topic_broker.get(relation["target_id"])
        if broker is not None and broker in environment_brokers:
            producers_of[topics[relation["target_id"]]][relation["source_id"]].add(broker)

    groups = {
        row["id"]: row
        for row in _section(state, _KAFKA_STATE, "groups")
        if row["environment"] == environment
    }
    group_outcomes = {row["id"]: row for row in attribution.get("groups", [])}

    def ref(kind: BindingEvidenceKind, ids: list[str]) -> str:
        return binding_evidence_ref(
            snapshot_id=snapshot.snapshot_id, query_digest=digest, kind=kind, internal_ids=ids
        )

    rows: list[BindingRow] = []
    for broker in requested:
        if not captures.get(broker):
            continue
        broker_groups = {cid for cid, row in groups.items() if row["broker_id"] == broker}
        # Service -> the captures whose allow-listed groups resolve to it (its capture scope).
        scope: dict[str, set[str]] = defaultdict(set)
        for cid in broker_groups:
            outcome = group_outcomes.get(cid)
            if outcome is not None and outcome["outcome"] == _RESOLVED:
                scope[outcome["service_id"]].add(groups[cid]["source_instance_id"])
        in_scope = set(scope)
        candidates: dict[tuple[str, str], _Candidate] = {}
        for promise in catalog.promises:
            service_id = catalog.service_of_name.get(promise["service_name"])
            if (
                promise["direction"] != "RECEIVES"
                or service_id is None
                or service_id not in in_scope
            ):
                continue  # R3 comes first: no row outside capture scope, before any R7 check.
            topic = catalog.event_topic[promise["event_id"]]
            topic_id = topic_owned_id(
                stable_broker_id=broker, normalized_namespace_or_empty="", exact_topic_address=topic
            )
            declared = topics.get(topic_id) == topic and topic_broker.get(topic_id) == broker
            candidate = candidates.setdefault(
                (topic, service_id),
                _Candidate(topic, topic_id if declared else None, service_id),
            )
            candidate.promises.append(promise)
            # R2 reports the T of the one capture that scopes S; with several, no single T.
            times = {captured_at[source] for source in scope[service_id]}
            candidate.scope_t = times.pop() if len(times) == 1 else None
        for row in attribution.get("attributions", []):
            if row["consumer_id"] not in broker_groups or row["topic_id"] not in topics:
                continue
            topic = topics[row["topic_id"]]
            group_id = groups[row["consumer_id"]]["group_id"]
            if row["outcome"] == _RESOLVED:
                key = (topic, row["service_id"])
                service_id = row["service_id"]
            else:
                key, service_id = (topic, f"group:{group_id}"), None
            candidate = candidates.setdefault(key, _Candidate(topic, row["topic_id"], service_id))
            candidate.attributions.append(row)
            candidate.group_ids.add(group_id)

        for candidate in candidates.values():
            rows.append(_row(candidate, broker, catalog, selected, producers_of, ref))

    rows.sort(key=lambda row: row.position())
    remaining = [row for row in rows if cursor is None or row.position() > cursor.after]
    page_rows = remaining[: request.limit]
    more = len(remaining) > request.limit
    next_cursor = (
        encode_cursor(
            Cursor(
                v=1,
                after=page_rows[-1].position(),
                query_digest=digest,
                snapshot_id=snapshot.snapshot_id,
            )
        )
        if more
        else None
    )
    codes: set[LimitationCode] = set(ALWAYS_PRESENT)
    if any(row.cross_broker_producers for row in rows):
        codes.add(_CODE.CROSS_BROKER_DELIVERY_NOT_ESTABLISHED)
    missing = [broker for broker in requested if not captures.get(broker)]
    if missing:
        codes.add(_CODE.NO_ACCEPTED_CAPTURE)
    if more:
        codes.add(_CODE.MORE_ROWS_AVAILABLE)
    return BindingPictureAnswer(
        schema_version=SCHEMA_VERSION,
        producer=producer,
        tool=TOOL_NAME,
        mode="query",
        outcome=Outcome.PARTIAL,
        snapshot=snapshot,
        data=BindingPictureData(
            request_context=context,
            catalog_source=CatalogSource(
                source_instance_id=catalog.source["source_instance_id"],
                catalog_digest=catalog.source["catalog_digest"],
                lookup_digest=catalog.source["lookup_digest"],
                source_revision=catalog.source["source_revision"],
            ),
            capture_sources=[
                CaptureSource(
                    broker_id=broker,
                    source_instance_id=row["source_instance_id"],
                    captured_at=row["captured_at"],
                    source_revision=row["source_revision"],
                )
                for broker in requested
                for row in captures.get(broker, [])
            ],
            rows=page_rows,
            page=Page(limit=request.limit, returned=len(page_rows), next_cursor=next_cursor),
        ),
        limitations=[
            _limitation(code, missing_brokers=missing)
            for code in sorted(codes, key=lambda code: code.value)
        ],
    )


def _row(
    candidate: _Candidate,
    broker: str,
    catalog: _Catalog,
    selected: str,
    producers_of: Mapping[str, Mapping[str, set[str]]],
    ref: Callable[[BindingEvidenceKind, list[str]], str],
) -> BindingRow:
    attributions = sorted(candidate.attributions, key=lambda row: row["id"])
    if candidate.service_id is None:  # R6: an attachment whose attribution is not RESOLVED.
        # One R6 row per group, so every attribution of it carries the same reason.
        status, reason = AssessmentStatus.UNRESOLVED, AssessmentReason(attributions[0]["reason"])
    elif candidate.promises and candidate.topic_id is None:  # R7
        status, reason = AssessmentStatus.UNRESOLVED, AssessmentReason.TOPIC_NOT_DECLARED
    elif candidate.promises and attributions:  # R1
        status, reason = AssessmentStatus.PROMISED_AND_OBSERVED, None
    elif candidate.promises:  # R2: in scope, no live attachment to this Topic.
        status, reason = AssessmentStatus.PROMISED_NOT_OBSERVED, None
    else:  # R4: observed, undeclared.
        status, reason = AssessmentStatus.UNRESOLVED, AssessmentReason.PROMISE_COVERAGE_MISSING

    topic = candidate.topic_name
    producers = []
    for service_id, brokers in sorted(producers_of.get(topic, {}).items()):
        name = catalog.name_of_service.get(service_id)
        producers.append(
            ProducerEntry(
                service_id=service_id,
                bounded_context_id=catalog.context_of_service.get(service_id),
                broker_ids=sorted(brokers),
                declared_event_types=sorted(
                    p["event_id"]
                    for p in catalog.promises
                    if p["direction"] == "SENDS"
                    and p["service_name"] == name
                    and catalog.event_topic.get(p["event_id"]) == topic
                ),
            )
        )
    consumer_context = (
        catalog.context_of_service.get(candidate.service_id) if candidate.service_id else None
    )
    crossing = _crossing(selected, consumer_context, [p.bounded_context_id for p in producers])
    return BindingRow(
        broker_id=broker,
        topic_name=topic,
        topic_id=candidate.topic_id,
        consumer_service_id=candidate.service_id,
        group_ids=sorted(candidate.group_ids),
        crossing=crossing,
        status=status,
        reason=reason,
        declared_event_types=sorted(p["event_id"] for p in candidate.promises),
        producers=producers,
        cross_broker_producers=any(broker not in p.broker_ids for p in producers),
        captured_at=_single_time(attributions)
        if attributions
        else (None if reason is AssessmentReason.TOPIC_NOT_DECLARED else candidate.scope_t),
        promise_evidence_refs=sorted(
            ref(BindingEvidenceKind.CATALOG_PROMISE, [p["id"], *p["evidence_ids"]])
            for p in candidate.promises
        ),
        attachment_evidence_refs=sorted(
            ref(BindingEvidenceKind.KAFKA_ATTACHMENT, [row["id"], *row["attachment_evidence_ids"]])
            for row in attributions
        ),
        mapping_evidence_refs=sorted(
            {
                ref(
                    BindingEvidenceKind.KAFKA_SERVICE_MAPPING, [entry["id"], *entry["evidence_ids"]]
                )
                for row in attributions
                for entry in row["mapping_entries"]
            }
        ),
    )
