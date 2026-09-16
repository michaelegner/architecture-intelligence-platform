"""Cross-source content-conflict detection for shared/explicitly-mapped Schema and Message ids.

I1 spec §8.1: "Two current owners explicitly mapped to one shared Schema ID with different
canonical hashes are REJECTED_CONFLICT." §9.1's message equivalent: "different contract digests
under the same explicit shared ID conflict." Two independent sources' claims only become
comparable once collected together - `app.ingestion._shared.upsert_schema_or_conflict`/
`upsert_message_or_conflict` catch the *within one source* case at the point of insertion (their
model already deduped by the time it's returned); this module catches the *across sources* case,
fed the same list of per-source models the orchestrator is about to merge, before `merge_models`'s
own first-wins dedup discards the disagreement.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.canonical.model import ArchitectureModel
from app.sources.model import DiagnosticCode, IngestionDiagnostic


def detect_shared_claim_content_conflicts(
    models: Sequence[ArchitectureModel],
) -> tuple[IngestionDiagnostic, ...]:
    """Groups every source's claimed Schema/Message entities by id across the whole set of models
    about to be merged; more than one distinct `canonical_hash`/`contract_digest` value under one
    id is a real content conflict, identical values under one id is a legitimate merge (silent, no
    diagnostic). Must be called with the *pre-merge* per-source model list - `merge_models`'s own
    first-wins `dict.setdefault` would otherwise have already discarded the disagreeing claim.
    """
    schema_hashes: dict[str, set[str | None]] = {}
    for model in models:
        for schema in model.schemas:
            schema_hashes.setdefault(schema.id, set()).add(schema.canonical_hash)

    message_digests: dict[str, set[str | None]] = {}
    for model in models:
        for message in model.messages:
            message_digests.setdefault(message.id, set()).add(message.contract_digest)

    diagnostics = [
        IngestionDiagnostic(
            code=DiagnosticCode.SCHEMA_CONTENT_CONFLICT,
            message=(
                f"schema {schema_id!r} has {len(hashes)} disagreeing canonical hashes across "
                f"sources: {sorted(h or '<none>' for h in hashes)!r}"
            ),
            source_pointer=schema_id,
        )
        for schema_id, hashes in schema_hashes.items()
        if len(hashes) > 1
    ] + [
        IngestionDiagnostic(
            code=DiagnosticCode.MESSAGE_CONTENT_CONFLICT,
            message=(
                f"message {message_id!r} has {len(digests)} disagreeing contract digests across "
                f"sources: {sorted(d or '<none>' for d in digests)!r}"
            ),
            source_pointer=message_id,
        )
        for message_id, digests in message_digests.items()
        if len(digests) > 1
    ]
    # Deterministic order regardless of caller-supplied model order or dict iteration order.
    return tuple(sorted(diagnostics, key=lambda d: (d.code, d.source_pointer or "")))


@dataclass(frozen=True)
class InfrastructureEntityConflicts:
    """I2 Draft 0.2 §10 specifies `K8S_RESOURCE_CONFLICT`'s outcome as "REJECTED_CONFLICT; no
    commit" - a *source* result, not only a run-level diagnostic. `conflicted_source_instance_ids`
    names exactly the sources whose contributions disagree, so the orchestrator can mark their own
    outcomes `REJECTED_CONFLICT` rather than leaving them reported as ACCEPTED in a run that
    rejected because of them.
    """

    diagnostics: tuple[IngestionDiagnostic, ...]
    conflicted_source_instance_ids: frozenset[str]

    def __bool__(self) -> bool:
        return bool(self.diagnostics)


def detect_infrastructure_entity_content_conflicts(
    models: Sequence[ArchitectureModel],
) -> InfrastructureEntityConflicts:
    """I2 Draft 0.2 §7.1: "For one logical entity ID, equal semantic digests merge contributions and
    union evidence deterministically... Different semantic digests from simultaneously current
    sources are incompatible and reject the affected discovery run as `K8S_RESOURCE_CONFLICT`; no
    source wins by precedence." A separate function from `detect_shared_claim_content_conflicts`
    above rather than folding infrastructure entities into it - a distinct fact category
    (infrastructure, not application), matching `app.canonical.infrastructure` being its own module -
    but identical in structure: groups every source's claimed entity contributions by `entity_id`
    across the whole set of models about to be merged, called with the same pre-merge per-source
    model list before `merge_models`'s own first-wins dedup could discard the disagreement.

    Nothing populates `infrastructure_contributions` yet (I2 Draft 0.2 §3 prerequisite slice, PR B) -
    this becomes load-bearing once I2 §12 slice 3's Kubernetes adapter exists.
    """
    digests_by_entity: dict[str, set[str]] = {}
    sources_by_entity: dict[str, set[str]] = {}
    for model in models:
        for contribution in model.infrastructure_contributions:
            digests_by_entity.setdefault(contribution.entity_id, set()).add(
                contribution.resource_semantic_digest
            )
            sources_by_entity.setdefault(contribution.entity_id, set()).add(
                contribution.source_instance_id
            )

    conflicted_entity_ids = [
        entity_id for entity_id, digests in digests_by_entity.items() if len(digests) > 1
    ]
    diagnostics = [
        IngestionDiagnostic(
            code=DiagnosticCode.K8S_RESOURCE_CONFLICT,
            message=(
                f"infrastructure entity {entity_id!r} has "
                f"{len(digests_by_entity[entity_id])} disagreeing semantic digests across sources "
                f"{sorted(sources_by_entity[entity_id])!r}: "
                f"{sorted(digests_by_entity[entity_id])!r}"
            ),
            source_pointer=entity_id,
        )
        for entity_id in conflicted_entity_ids
    ]
    conflicted_sources: set[str] = set()
    for entity_id in conflicted_entity_ids:
        conflicted_sources |= sources_by_entity[entity_id]

    return InfrastructureEntityConflicts(
        # Deterministic order regardless of caller-supplied model order or dict iteration order.
        diagnostics=tuple(sorted(diagnostics, key=lambda d: (d.code, d.source_pointer or ""))),
        conflicted_source_instance_ids=frozenset(conflicted_sources),
    )
