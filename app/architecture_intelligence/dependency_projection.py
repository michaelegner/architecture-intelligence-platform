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

_DECLARED = "DECLARED"
_OBSERVED = "OBSERVED"


def compute_claim_id(
    *, subject_id: str, predicate: str, object_id: str, delivery_kind: str, delivery_via_id: str
) -> str:
    """`aip:claim:v1:sha256(canonical-json({subject_id, predicate, object_id, delivery_kind,
    delivery_via_id}))` (spec §12.1). Qualification, evidence ids, snapshot id, display names and
    observation times are deliberately excluded from the hashed payload."""
    payload = {
        "subject_id": subject_id,
        "predicate": predicate,
        "object_id": object_id,
        "delivery_kind": delivery_kind,
        "delivery_via_id": delivery_via_id,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:claim:v1:{digest}"


def _matches_declared(evidence_ids: list[str], evidence_by_id: dict[str, dict]) -> list[str]:
    return sorted(
        eid
        for eid in evidence_ids
        if eid in evidence_by_id and evidence_by_id[eid]["evidence_type"] == _DECLARED
    )


def _matches_observed(
    evidence_ids: list[str],
    evidence_by_id: dict[str, dict],
    *,
    environment: str,
    window_start: datetime,
    window_end: datetime,
) -> list[str]:
    matches = []
    for eid in evidence_ids:
        row = evidence_by_id.get(eid)
        if row is None or row["evidence_type"] != _OBSERVED:
            continue
        if row["environment"] != environment:
            continue
        last_seen = row["last_seen"]
        if last_seen is None or last_seen < window_start or last_seen > window_end:
            continue
        matches.append(eid)
    return sorted(matches)


def _classify_coverage(*, relevant_observed: bool, spans_observed: bool, enabled: bool) -> Coverage:
    """Spec §14's coverage classification for a `NOT_OBSERVED_IN_WINDOW` claim - the same rule
    `app.analysis.runtime._classify_coverage` already applies to O4, restated over the booleans
    O5's `telemetry_coverage` computes rather than re-deriving them."""
    if not enabled:
        return Coverage.UNKNOWN
    if relevant_observed:
        return Coverage.SUFFICIENT
    if spans_observed:
        return Coverage.PARTIAL
    return Coverage.NONE


def _qualify(
    evidence_ids: list[str],
    evidence_by_id: dict[str, dict],
    *,
    environment: str,
    window_start: datetime,
    window_end: datetime,
    relevant_observed: bool,
    spans_observed: bool,
    coverage_enabled: bool,
) -> tuple[Qualification, Coverage | None, list[str]] | None:
    """Spec §14's qualification table. `None` means "no supported dependency claim" - the caller
    must not create one."""
    declared = _matches_declared(evidence_ids, evidence_by_id)
    observed = _matches_observed(
        evidence_ids,
        evidence_by_id,
        environment=environment,
        window_start=window_start,
        window_end=window_end,
    )
    if declared and observed:
        return Qualification.CONFIRMED, None, sorted(set(declared) | set(observed))
    if observed:
        return Qualification.OBSERVED_ONLY, None, observed
    if declared:
        coverage = _classify_coverage(
            relevant_observed=relevant_observed,
            spans_observed=spans_observed,
            enabled=coverage_enabled,
        )
        return Qualification.NOT_OBSERVED_IN_WINDOW, coverage, declared
    return None


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


def _accepted_evidence_ids(evidence_ids: list[str], evidence_by_id: dict[str, dict]) -> list[str]:
    """Spec §15: every emitted evidence reference must point to an Evidence node included in the
    accepted snapshot. A relation's raw `evidence_ids` can be non-empty yet dangling (the id no
    longer resolves to any Evidence row `read_service_dependency_rows` fetched) - that must not
    count as "evidenced" for destination resolution, any more than it counts for qualification
    (`_matches_declared`/`_matches_observed` apply the same `eid in evidence_by_id` filter)."""
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


def _unresolved_identity_limitation(target_ref: EntityRef, claim_id: str) -> Limitation:
    noun, target_noun = (
        ("provider service", "operation")
        if target_ref.type == EntityType.OPERATION
        else ("consumer service", "queue")
    )
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
    """Spec §13/§14/§15 end to end for one service's outgoing `CALLS`/`SENDS` relations. `rows` is
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
            relevant_observed=coverage.http_observed,
            spans_observed=coverage.spans_observed,
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
            limitations.append(_unresolved_identity_limitation(claim.delivery.via, claim.claim_id))

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
            relevant_observed=coverage.messaging_observed,
            spans_observed=coverage.spans_observed,
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
                limitations.append(
                    _unresolved_identity_limitation(claim.delivery.via, claim.claim_id)
                )

    return ProjectionResult(claims=_merge_duplicate_claims(claims), limitations=limitations)
