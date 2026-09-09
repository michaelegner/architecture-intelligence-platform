"""v0.4.0 I3.1 - the pure drift projection (I3 spec §7.1, §19, §20).

This module deliberately does one thing: it *selects* from an already-qualified I1 dependency
projection. It never re-derives anything.

    read graph (repository.py)
        |
        v
    project_service_dependencies(...)      dependency_projection.py - owns truth
        |
        v
    ProjectionResult
        |
        +-------------------------------+
        |                               |
        v                               v
    dependency answer          project_architecture_drift(...)   this module - selects only

Spec §16 prohibits a second status engine: no `if declared and observed: ...` reconstruction, no
separate O3/O4 reads, no re-resolved destinations, no recomputed claim ids, no rebuilt evidence
lists. Consequently this module imports no Neo4j driver, no repository, no `app.analysis.runtime`
and no session - only the contract types and the I1 projection's own result type.

Spec §7.3 also keeps the *fact* stable: a drift claim is an ordinary `DIRECT_DEPENDENCY` claim, not a
new predicate. Only its `qualification` carries the discrepancy semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.architecture_intelligence.contracts import DependencyClaim, Limitation, Qualification
from app.architecture_intelligence.dependency_projection import ProjectionResult

# Spec §7.1/§7.2: exactly the two discrepancy qualifications. `CONFIRMED` is not drift, and
# `NOT_OBSERVED_IN_WINDOW` is a reported evidence-qualified discrepancy - never "unused", "obsolete",
# "dead", "incorrect", "unreachable" or "absent".
DRIFT_QUALIFICATIONS = frozenset(
    {Qualification.OBSERVED_ONLY, Qualification.NOT_OBSERVED_IN_WINDOW}
)


@dataclass(frozen=True)
class DriftProjectionResult:
    claims: list[DependencyClaim]
    limitations: list[Limitation]


def project_architecture_drift(projection: ProjectionResult) -> DriftProjectionResult:
    """Spec §7.1: `drift claims == [c in dependency claims where c.qualification in
    {OBSERVED_ONLY, NOT_OBSERVED_IN_WINDOW}]`, subject only to the §19 limitation-projection rules.

    Claims are passed through by reference, never rebuilt, so spec §8's exact-claim-reuse invariant
    holds by construction: `claim_id`, `subject`, `predicate`, `object`, `destination_resolution`,
    `delivery`, `qualification`, `coverage`, `evidence_refs` and `resolution_evidence_refs` are the
    same objects the dependency answer returned. Both lists keep their input relative order (§20) -
    filtering a list must not resort it, so drift claims retain the I1
    `(object.id, delivery.kind, delivery.via.id, claim_id)` order and limitations retain the I1
    limitation order.
    """
    claims = [claim for claim in projection.claims if claim.qualification in DRIFT_QUALIFICATIONS]
    retained_claim_ids = {claim.claim_id for claim in claims}
    limitations = [
        limitation
        for limitation in (
            _project_limitation(limitation, retained_claim_ids)
            for limitation in projection.limitations
        )
        if limitation is not None
    ]
    return DriftProjectionResult(claims=claims, limitations=limitations)


def _project_limitation(limitation: Limitation, retained_claim_ids: set[str]) -> Limitation | None:
    """Spec §19. A claim-independent limitation (`claim_ids == []`, today the `INSUFFICIENT_EVIDENCE`
    case where a candidate produced no safe claim at all) is always retained (§19.2): "no safe claim"
    is not "proved non-drift", so it materially limits the completeness of the drift result.

    A claim-scoped limitation is intersected with the surviving drift claim ids (§19.1). An empty
    intersection drops it - a `CONFIRMED` dependency omitted from the drift answer takes its own
    `UNRESOLVED_IDENTITY` limitation with it. A non-empty intersection retains the limitation
    *narrowed to that intersection*: keeping a claim id that names a claim absent from this answer
    would leave the answer internally inconsistent. Today `dependency_projection` only ever emits
    single-claim `UNRESOLVED_IDENTITY` limitations, so the multi-id narrowing is currently
    unreachable - it is implemented and tested anyway because §19.1 states the rule generally, and
    the projection is free to emit a wider limitation later.
    """
    if not limitation.claim_ids:
        return limitation
    retained = [claim_id for claim_id in limitation.claim_ids if claim_id in retained_claim_ids]
    if not retained:
        return None
    if retained == limitation.claim_ids:
        return limitation
    return limitation.model_copy(update={"claim_ids": retained})
