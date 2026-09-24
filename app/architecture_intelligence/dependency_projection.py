"""v0.4.0 I1.3 - sync/async destination and delivery projection, qualification and evidence
linkage (spec §12-15). Pure functions over the plain rows `app.architecture_intelligence.
repository.read_service_dependency_rows` returns - no Neo4j access here, and no public outcome
decision (that stays `app.architecture_intelligence.service`'s job, spec §7).
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from app.analysis.runtime import ServiceTelemetryCoverage
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    Coverage,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
    DestinationResolution,
    EntityRef,
    EntityType,
    Limitation,
    LimitationCode,
    Qualification,
)
from app.qualification.declared_observed import qualify_relation as _kernel_qualify_relation


def compute_claim_id(
    *,
    subject_id: str,
    predicate: str,
    object_id: str,
    delivery_kind: str,
    delivery_via_id: str,
    subscription_id: str | None = None,
) -> str:
    """`aip:claim:v1:sha256(canonical-json({subject_id, predicate, object_id, delivery_kind,
    delivery_via_id[, subscription_id]}))` (spec §12.1). Qualification, evidence ids, snapshot id,
    display names and observation times are deliberately excluded from the hashed payload.

    v0.5.0 I4 §12.4: `subscription_id` is present only for a Pub/Sub route through a Subscription
    and is *omitted entirely* otherwise - `canonical_json_bytes` does not drop `None`, so adding the
    key unconditionally would change every existing HTTP/Queue claim id."""
    payload = {
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "delivery_kind": delivery_kind,
        "delivery_via_id": delivery_via_id,
    }
    if subscription_id is not None:
        payload["subscription_id"] = subscription_id
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:claim:v1:{digest}"


def _qualify(
    evidence_ids: list[str],
    evidence_by_id: dict[str, dict],
    *,
    environment: str,
    window_start: datetime,
    window_end: datetime,
    relation_type: str,
    coverage: ServiceTelemetryCoverage,
    coverage_enabled: bool,
) -> tuple[Qualification, Coverage | None, list[str]] | None:
    """Spec §14's qualification table. `None` means "no supported dependency claim" - the caller
    must not create one.

    v0.4.1 I1.2: delegates to the shared kernel (`app.qualification.declared_observed.
    qualify_relation`) rather than an independent implementation, and maps the kernel's plain
    strings onto this module's public `Qualification`/`Coverage` enums. `coverage_row_exists` is
    always `True` here: `app.architecture_intelligence.repository.read_service_dependency_rows`'s
    `telemetry_coverage(service_ids=[service_id])[0]` always synthesizes exactly one coverage row
    per requested id, so this call site can never observe "no coverage row" in production - that
    branch is exercised only by the kernel's own I1.1 unit tests, per spec §25.3."""
    result = _kernel_qualify_relation(
        evidence_ids,
        evidence_by_id,
        environment=environment,
        window_start=window_start,
        window_end=window_end,
        relation_type=relation_type,
        http_observed=coverage.http_observed,
        messaging_observed=coverage.messaging_observed,
        spans_observed=coverage.spans_observed,
        coverage_row_exists=True,
        qualification_enabled=coverage_enabled,
    )
    if result is None:
        return None
    return (
        Qualification(result.qualification),
        Coverage(result.coverage) if result.coverage is not None else None,
        result.evidence_refs,
    )


def _operation_ref(call: dict) -> EntityRef:
    name = call.get("operation_name") or f"{call['method']} {call['path']}"
    return EntityRef(
        id=call["operation_id"],
        type=EntityType.OPERATION,
        name=name,
        method=call["method"],
        path=call["path"],
    )


def _queue_ref(send: dict) -> EntityRef:
    return EntityRef(
        id=send["queue_id"],
        type=EntityType.QUEUE,
        name=send["queue_name"],
        protocol=send.get("protocol"),
        namespace=send.get("namespace"),
    )


def _topic_ref(publish: dict) -> EntityRef:
    return EntityRef(
        id=publish["topic_id"],
        type=EntityType.TOPIC,
        name=publish["topic_name"],
        protocol=publish.get("protocol"),
        namespace=publish.get("namespace"),
    )


def _subscription_ref(subscription: dict) -> EntityRef:
    return EntityRef(
        id=subscription["subscription_id"],
        type=EntityType.SUBSCRIPTION,
        name=subscription["subscription_name"],
        protocol=subscription.get("protocol"),
        namespace=subscription.get("namespace"),
    )


def _accepted_evidence_ids(evidence_ids: list[str], evidence_by_id: dict[str, dict]) -> list[str]:
    """Spec §15: every emitted evidence reference must point to an Evidence node included in the
    accepted snapshot. A relation's raw `evidence_ids` can be non-empty yet dangling (the id no
    longer resolves to any Evidence row `read_service_dependency_rows` fetched) - that must not
    count as "evidenced" for destination resolution, any more than it counts for qualification
    (`app.qualification.declared_observed.matches_declared_evidence`/`matches_observed_evidence`
    apply the same `eid in evidence_by_id` filter)."""
    return sorted(eid for eid in evidence_ids if eid in evidence_by_id)


def _group_evidenced_rows(
    rows: list[dict], id_field: str, name_field: str, evidence_by_id: dict[str, dict]
) -> dict[str, tuple[str, set[str]]]:
    """Groups rows by `id_field`, unioning each group's accepted evidence ids rather than letting a
    later row silently overwrite an earlier one for the same id. Neo4j doesn't guarantee row order,
    and MERGE-based writes make more than one row per id unlikely today but not contractually
    impossible - this must not depend on either (spec §13.3/§20: deterministic regardless of
    read/insertion order)."""
    grouped: dict[str, tuple[str, set[str]]] = {}
    for row in rows:
        accepted = _accepted_evidence_ids(row["evidence_ids"], evidence_by_id)
        if not accepted:
            continue
        row_id = row[id_field]
        _name, evidence_ids = grouped.setdefault(row_id, (row[name_field], set()))
        evidence_ids.update(accepted)
    return grouped


def _resolve_sync_destination(
    call: dict, providers: list[dict], evidence_by_id: dict[str, dict]
) -> tuple[DestinationResolution, EntityRef, list[str]]:
    """Spec §13.1: exactly one evidenced provider resolves to that `Service`; zero or more than one
    is not guessed - retain the `Operation` itself with `DIRECT_TARGET_FALLBACK`."""
    evidenced = _group_evidenced_rows(providers, "provider_id", "provider_name", evidence_by_id)
    if len(evidenced) == 1:
        [(provider_id, (provider_name, accepted_ids))] = evidenced.items()
        return (
            DestinationResolution.RESOLVED_SERVICE,
            EntityRef(id=provider_id, type=EntityType.SERVICE, name=provider_name),
            sorted(accepted_ids),
        )
    return DestinationResolution.DIRECT_TARGET_FALLBACK, _operation_ref(call), []


def _resolve_async_destinations(
    send: dict, consumers: list[dict], evidence_by_id: dict[str, dict]
) -> list[tuple[DestinationResolution, EntityRef, list[str]]]:
    """Spec §13.2: every distinct evidenced consumer is valid fan-out, not ambiguity; zero evidenced
    consumers is not guessed - retain the `Queue` itself with `DIRECT_TARGET_FALLBACK`."""
    evidenced = _group_evidenced_rows(consumers, "consumer_id", "consumer_name", evidence_by_id)
    if not evidenced:
        return [(DestinationResolution.DIRECT_TARGET_FALLBACK, _queue_ref(send), [])]
    return [
        (
            DestinationResolution.RESOLVED_SERVICE,
            EntityRef(id=consumer_id, type=EntityType.SERVICE, name=name),
            sorted(accepted_ids),
        )
        for consumer_id, (name, accepted_ids) in sorted(evidenced.items())
    ]


def _usable_subscriptions(
    subscriptions: list[dict], evidence_by_id: dict[str, dict]
) -> list[tuple[dict, list[str]]]:
    """v0.5.0 I4 §12.3: a Subscription route is usable only when its `SUBSCRIPTION_OF` relation to
    the published Topic carries accepted (non-dangling) evidence - the same rule
    `_group_evidenced_rows` applies to consumers. Rows for one Subscription id are unioned, never
    overwritten, and the result is sorted by Subscription id for deterministic claim order."""
    grouped: dict[str, tuple[dict, set[str]]] = {}
    for row in subscriptions:
        accepted = _accepted_evidence_ids(row["evidence_ids"], evidence_by_id)
        if not accepted:
            continue
        _first_row, evidence_ids = grouped.setdefault(row["subscription_id"], (row, set()))
        evidence_ids.update(accepted)
    return [(row, sorted(evidence_ids)) for _sid, (row, evidence_ids) in sorted(grouped.items())]


def _resolve_pubsub_destinations(
    publish: dict,
    subscriptions: list[dict],
    receivers_by_subscription: dict[str, list[dict]],
    evidence_by_id: dict[str, dict],
) -> list[tuple[DestinationResolution, EntityRef, EntityRef | None, list[str]]]:
    """v0.5.0 I4 §12.3, one entry per claim as `(resolution, object, subscription route,
    resolution evidence)`:

    - no usable Subscription -> the Topic itself, `DIRECT_TARGET_FALLBACK`, no route;
    - a usable Subscription with no evidenced consumer -> that Subscription,
      `DIRECT_TARGET_FALLBACK`, routed through it;
    - otherwise one `RESOLVED_SERVICE` entry per distinct evidenced consumer Service on that
      Subscription (competing consumers, not fan-out - §6.3), all sharing its route.

    Fan-out is expressed only by distinct Subscription routes. A resolved claim's resolution
    evidence is its route's own `SUBSCRIPTION_OF` evidence plus that consumer's `RECEIVES_FROM`
    evidence, so evidence for one Subscription never reaches a sibling Subscription's claim."""
    usable = _usable_subscriptions(subscriptions, evidence_by_id)
    if not usable:
        return [(DestinationResolution.DIRECT_TARGET_FALLBACK, _topic_ref(publish), None, [])]
    destinations: list[tuple[DestinationResolution, EntityRef, EntityRef | None, list[str]]] = []
    for subscription_row, subscription_of_evidence in usable:
        route = _subscription_ref(subscription_row)
        evidenced = _group_evidenced_rows(
            receivers_by_subscription.get(route.id, []),
            "consumer_id",
            "consumer_name",
            evidence_by_id,
        )
        if not evidenced:
            # The frozen claim contract keeps `resolution_evidence_refs` empty for every
            # DIRECT_TARGET_FALLBACK (spec §15), so the route's SUBSCRIPTION_OF evidence gates
            # usability here but is referenced only from resolved claims.
            destinations.append((DestinationResolution.DIRECT_TARGET_FALLBACK, route, route, []))
            continue
        destinations.extend(
            (
                DestinationResolution.RESOLVED_SERVICE,
                EntityRef(id=consumer_id, type=EntityType.SERVICE, name=name),
                route,
                sorted(set(subscription_of_evidence) | accepted_ids),
            )
            for consumer_id, (name, accepted_ids) in sorted(evidenced.items())
        )
    return destinations


def _build_claim(
    *,
    subject: EntityRef,
    object_ref: EntityRef,
    delivery: DeliveryRef,
    destination_resolution: DestinationResolution,
    qualification: Qualification,
    coverage: Coverage | None,
    evidence_refs: list[str],
    resolution_evidence_refs: list[str],
) -> DependencyClaim:
    claim_id = compute_claim_id(
        subject_id=subject.id,
        predicate=DependencyPredicate.DIRECT_DEPENDENCY.value,
        object_id=object_ref.id,
        delivery_kind=delivery.kind.value,
        delivery_via_id=delivery.via.id,
        subscription_id=delivery.subscription.id if delivery.subscription is not None else None,
    )
    return DependencyClaim(
        claim_id=claim_id,
        subject=subject,
        predicate=DependencyPredicate.DIRECT_DEPENDENCY,
        object=object_ref,
        destination_resolution=destination_resolution,
        delivery=delivery,
        qualification=qualification,
        coverage=coverage,
        evidence_refs=sorted(set(evidence_refs)),
        resolution_evidence_refs=sorted(set(resolution_evidence_refs)),
    )


_FALLBACK_TARGET_NOUNS = {
    EntityType.OPERATION: ("provider service", "operation"),
    EntityType.QUEUE: ("consumer service", "queue"),
    EntityType.TOPIC: ("subscription", "topic"),
    EntityType.SUBSCRIPTION: ("consumer service", "subscription"),
}


def _unresolved_identity_limitation(target_ref: EntityRef, claim_id: str) -> Limitation:
    """`target_ref` is the fallback claim's own object (the retained direct target). The Operation
    and Queue wording is unchanged from before v0.5.0 I4."""
    noun, target_noun = _FALLBACK_TARGET_NOUNS[target_ref.type]
    return Limitation(
        code=LimitationCode.UNRESOLVED_IDENTITY,
        message=(
            f"{target_ref.id} has no single evidenced {noun}; retained as the direct "
            f"{target_noun} target rather than guessed."
        ),
        claim_ids=[claim_id],
    )


def _insufficient_evidence_limitation(
    relation_type: str, source_id: str, target_id: str
) -> Limitation:
    return Limitation(
        code=LimitationCode.INSUFFICIENT_EVIDENCE,
        message=(
            f"{source_id} -{relation_type}-> {target_id} has no declared or matching observed "
            f"evidence; no dependency claim was created."
        ),
        claim_ids=[],
    )


def _merge_duplicate_claims(claims: list[DependencyClaim]) -> list[DependencyClaim]:
    """Spec §13.3: dedup is allowed only for rows sharing the same deterministic `claim_id`, and
    their evidence references must then be unioned and sorted rather than one row silently winning.
    Unreachable with today's MERGE-unique relation model, but kept as an explicit, tested guarantee
    rather than an assumption."""
    merged: dict[str, DependencyClaim] = {}
    for claim in claims:
        existing = merged.get(claim.claim_id)
        if existing is None:
            merged[claim.claim_id] = claim
            continue
        merged[claim.claim_id] = existing.model_copy(
            update={
                "evidence_refs": sorted(set(existing.evidence_refs) | set(claim.evidence_refs)),
                "resolution_evidence_refs": sorted(
                    set(existing.resolution_evidence_refs) | set(claim.resolution_evidence_refs)
                ),
            }
        )
    return list(merged.values())


@dataclass(frozen=True)
class ProjectionResult:
    claims: list[DependencyClaim]
    limitations: list[Limitation]


def project_service_dependencies(
    rows: dict,
    *,
    service_id: str,
    service_name: str,
    environment: str,
    window_start: datetime,
    window_end: datetime,
    coverage_enabled: bool,
) -> ProjectionResult:
    """Spec §13/§14/§15 end to end for one service's outgoing `CALLS`/`SENDS` relations, plus
    v0.5.0 I4 §12.3's `PUBLISHES_TO` routes. `rows` is
    exactly what `app.architecture_intelligence.repository.read_service_dependency_rows` returns;
    the caller is responsible for the `UNKNOWN_ENTITY` check (`rows["service_name"] is None`)
    before calling this."""
    evidence_by_id = rows["evidence"]
    coverage: ServiceTelemetryCoverage = rows["coverage"]
    subject = EntityRef(id=service_id, type=EntityType.SERVICE, name=service_name)

    claims: list[DependencyClaim] = []
    limitations: list[Limitation] = []

    providers_by_operation: dict[str, list[dict]] = defaultdict(list)
    for row in rows["provides"]:
        providers_by_operation[row["operation_id"]].append(row)

    for call in rows["calls"]:
        qualified = _qualify(
            call["evidence_ids"],
            evidence_by_id,
            environment=environment,
            window_start=window_start,
            window_end=window_end,
            relation_type="CALLS",
            coverage=coverage,
            coverage_enabled=coverage_enabled,
        )
        if qualified is None:
            limitations.append(
                _insufficient_evidence_limitation("CALLS", service_id, call["operation_id"])
            )
            continue
        qualification, coverage_class, evidence_refs = qualified
        destination_resolution, object_ref, resolution_evidence_refs = _resolve_sync_destination(
            call, providers_by_operation.get(call["operation_id"], []), evidence_by_id
        )
        claim = _build_claim(
            subject=subject,
            object_ref=object_ref,
            delivery=DeliveryRef(
                kind=DeliveryKind.SYNC_HTTP,
                relation_type=DeliveryRelationType.CALLS,
                via=_operation_ref(call),
            ),
            destination_resolution=destination_resolution,
            qualification=qualification,
            coverage=coverage_class,
            evidence_refs=evidence_refs,
            resolution_evidence_refs=resolution_evidence_refs,
        )
        claims.append(claim)
        if destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK:
            limitations.append(_unresolved_identity_limitation(claim.object, claim.claim_id))

    receivers_by_queue: dict[str, list[dict]] = defaultdict(list)
    for row in rows["receives"]:
        receivers_by_queue[row["queue_id"]].append(row)

    for send in rows["sends"]:
        qualified = _qualify(
            send["evidence_ids"],
            evidence_by_id,
            environment=environment,
            window_start=window_start,
            window_end=window_end,
            relation_type="SENDS",
            coverage=coverage,
            coverage_enabled=coverage_enabled,
        )
        if qualified is None:
            limitations.append(
                _insufficient_evidence_limitation("SENDS", service_id, send["queue_id"])
            )
            continue
        qualification, coverage_class, evidence_refs = qualified
        destinations = _resolve_async_destinations(
            send, receivers_by_queue.get(send["queue_id"], []), evidence_by_id
        )
        for destination_resolution, object_ref, resolution_evidence_refs in destinations:
            claim = _build_claim(
                subject=subject,
                object_ref=object_ref,
                delivery=DeliveryRef(
                    kind=DeliveryKind.ASYNC_MESSAGE,
                    relation_type=DeliveryRelationType.SENDS,
                    via=_queue_ref(send),
                ),
                destination_resolution=destination_resolution,
                qualification=qualification,
                coverage=coverage_class,
                evidence_refs=evidence_refs,
                resolution_evidence_refs=resolution_evidence_refs,
            )
            claims.append(claim)
            if destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK:
                limitations.append(_unresolved_identity_limitation(claim.object, claim.claim_id))

    subscriptions_by_topic: dict[str, list[dict]] = defaultdict(list)
    for row in rows["subscriptions"]:
        subscriptions_by_topic[row["topic_id"]].append(row)
    receivers_by_subscription: dict[str, list[dict]] = defaultdict(list)
    for row in rows["subscription_receives"]:
        receivers_by_subscription[row["subscription_id"]].append(row)

    # v0.5.0 I4 §12.3/§12.5: qualification comes only from the subject's own `PUBLISHES_TO`
    # evidence, exactly as Queue claims qualify from `SENDS` alone; consumer-side evidence only
    # resolves (and is attributed to) its own Subscription route.
    for publish in rows["publishes"]:
        qualified = _qualify(
            publish["evidence_ids"],
            evidence_by_id,
            environment=environment,
            window_start=window_start,
            window_end=window_end,
            relation_type="PUBLISHES_TO",
            coverage=coverage,
            coverage_enabled=coverage_enabled,
        )
        if qualified is None:
            limitations.append(
                _insufficient_evidence_limitation("PUBLISHES_TO", service_id, publish["topic_id"])
            )
            continue
        qualification, coverage_class, evidence_refs = qualified
        destinations = _resolve_pubsub_destinations(
            publish,
            subscriptions_by_topic.get(publish["topic_id"], []),
            receivers_by_subscription,
            evidence_by_id,
        )
        for destination_resolution, object_ref, route, resolution_evidence_refs in destinations:
            claim = _build_claim(
                subject=subject,
                object_ref=object_ref,
                delivery=DeliveryRef(
                    kind=DeliveryKind.ASYNC_MESSAGE,
                    relation_type=DeliveryRelationType.PUBLISHES_TO,
                    via=_topic_ref(publish),
                    subscription=route,
                ),
                destination_resolution=destination_resolution,
                qualification=qualification,
                coverage=coverage_class,
                evidence_refs=evidence_refs,
                resolution_evidence_refs=resolution_evidence_refs,
            )
            claims.append(claim)
            if destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK:
                limitations.append(_unresolved_identity_limitation(claim.object, claim.claim_id))

    return ProjectionResult(claims=_merge_duplicate_claims(claims), limitations=limitations)
