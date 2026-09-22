"""v0.5.0 I3 slice 5b - cross-path (A/B/C) agreement/conflict/ambiguity/unresolved reduction (spec
§10), service-scoped projection (§13.4), result bounds (§20), and the public deployment-evidence
bridge/reachability computation (§16.1/§16.2).

Orchestrates `deployment_projection.resolve_path_a`/`_b`/`_c` (unchanged) - does not duplicate their
per-path logic. Because `compute_deployment_resolution_id`/`compute_deployment_claim_id` are pure
functions of `(snapshot_id, context_id, group_key)`/`(service_id, workload_id)` with no per-path
input (verified live: neither takes a method/path argument), Path A/B/C, run independently against
the same `snapshot_id`/`context_id`, produce byte-identical ids for the same group - so cross-path
reduction here is a straightforward group-by-id join over each path's own already-computed
`DeploymentResolution`/`DeploymentClaim` objects. The per-group reduction algorithm mirrors the exact
shape `resolve_path_c`'s own internal multi-observation-per-workload reduction already established
(`deployment_projection.py`'s `resolve_path_c`): a single reduction pass is run uniformly over every
group regardless of member count (1, 2, or 3) - a size-1 group trivially reduces to its own member's
values, so no separate "single-path passthrough" special case is needed.

Path A's deployment evidence is already backed by real `:Evidence` nodes (I2's Kubernetes adapter
mints one per contribution, `source_type=KUBERNETES`) and resolves through the existing evidence
machinery once the visibility predicate is widened (see `repository.py`). Path B (configured
mapping) and Path C (OTel runtime identity) evidence is not - their `evidence_refs` are a computed
mapping-evidence id (`compute_service_workload_mapping_evidence_id`) or a `RuntimeIdentityObservation`
node's own id (deliberately not `:Evidence`-labeled, spec §16.2's own reachability gate didn't exist
before this slice). Per the spec-author's explicit decision (this slice's plan, "Resolved design
decision"), these are exposed as synthetic `EvidenceRecord`s built directly from I2/I3 source data,
encoding their I2/I3-specific identity into the two existing generic `source_locator`/
`source_revision` string fields rather than widening the frozen `EvidenceRecord`/
`ObservedEvidenceMetadata` contracts.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import neo4j

from app.architecture_intelligence.contracts import (
    DeploymentClaim,
    DeploymentPredicate,
    DeploymentResolution,
    DeploymentResolutionStatus,
    EntityRef,
    EntityType,
    EvidenceRecord,
    EvidenceRelationType,
    EvidenceType,
    LimitationCode,
    ObservationContextRef,
    ObservedEvidenceMetadata,
    SupportedFact,
)
from app.architecture_intelligence.deployment_projection import (
    PathResolutionResult,
    RuntimeIdentityObservationRow,
    compute_deployment_claim_id,
    compute_service_workload_mapping_evidence_id,
    resolve_path_a,
    resolve_path_b,
    resolve_path_c,
)
from app.architecture_intelligence.deployment_repository import (
    iter_current_kubernetes_workloads,
    read_captured_pods_by_uid,
    read_current_kubernetes_workload,
    read_declared_service_identity,
    read_declared_service_ids,
    read_runtime_identity_observations,
    read_workload_ids_owning_pod,
)
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.provenance.model import SourceType
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument
from app.telemetry.service_resolver import DeclaredServiceCandidate, fetch_candidates

_DEPLOYMENT_METHOD_TO_STATUS = {
    "RESOLVED_EXPLICIT": DeploymentResolutionStatus.RESOLVED_EXPLICIT,
    "RESOLVED_CONFIGURED": DeploymentResolutionStatus.RESOLVED_CONFIGURED,
    "RESOLVED_OBSERVED": DeploymentResolutionStatus.RESOLVED_OBSERVED,
}

_MAX_DEPLOYMENT_CLAIMS = 100
_MAX_DEPLOYMENT_RESOLUTIONS = 250
_MAX_EVIDENCE_REFS_PER_CLAIM = 64

# A fixed, stable context id for the evidence-visibility-only reconciliation run
# (`observation_context=None` - see `run_whole_graph_reconciliation`'s own docstring). Never
# validated against `ObservationContextRef`'s real pattern/identity and never returned to a client
# - only used as a `compute_deployment_resolution_id` input so that call is deterministic across
# repeated invocations within one snapshot; the actual `resolution_id`/`claim_id` *values* this
# produces are never exposed (evidence visibility only consumes reachable-id-set membership and
# `SupportedFact`s, neither of which carries a `resolution_id`/`claim_id`).
EVIDENCE_VISIBILITY_CONTEXT_ID = "aip:observation-context:v1:" + "0" * 64

# PR #222 review finding (human reviewer, extended): `app.architecture_intelligence.request.
# EvidenceRequest.evidence_refs` enforces a frozen `^evidence:` pattern (spec §11.1), but Path B's
# own mapping-evidence id (`compute_service_workload_mapping_evidence_id`, §8.3) and Path C's own
# observation id (`app.canonical.ids.runtime_identity_observation_id`, §9.4) are each minted with a
# different prefix, by design, in `deployment_projection.py` - neither is `evidence:`-prefixed.
# Reused unchanged as *internal* identity (group keys, synthetic-evidence-record keys), but a
# `DeploymentClaim`/`DeploymentResolution` citing either raw form as a public `evidence_refs` entry
# could never actually be requested through `get_evidence`/`POST /api/evidence/resolve` - violating
# spec §16.2's "every evidence ref emitted...SHALL resolve through...negotiated MCP get_evidence".
# `_public_evidence_ref` is a reversible prefix swap (not a hash) applied only at this module's own
# public-facing boundary (never inside `deployment_projection.py`, which stays exactly as the plan's
# own Non-Goals require) - `_path_b_evidence_records`/`_path_c_evidence_records` key their synthetic
# `EvidenceRecord`s by applying this same function to the same raw identity, so the two always agree
# with no side mapping to keep in sync. A real Path A/I2-Kubernetes ref (already `evidence:`-
# prefixed, including the ones Path C's own owner-chain cites) passes through unchanged.
_PATH_B_RAW_PREFIX = "urn:aip:service-workload-mapping-evidence:v1:"
_PATH_B_EVIDENCE_PREFIX = "evidence:mapping:v1:"
_PATH_C_RAW_PREFIX = "runtime-identity:otel:"
_PATH_C_EVIDENCE_PREFIX = "evidence:otel:"


def _public_evidence_ref(raw: str) -> str:
    if raw.startswith("evidence:"):
        return raw
    if raw.startswith(_PATH_B_RAW_PREFIX):
        return _PATH_B_EVIDENCE_PREFIX + raw[len(_PATH_B_RAW_PREFIX) :]
    if raw.startswith(_PATH_C_RAW_PREFIX):
        return _PATH_C_EVIDENCE_PREFIX + raw[len(_PATH_C_RAW_PREFIX) :]
    return raw  # defensive: an unrecognized shape passes through rather than silently vanishing


def _publicize_evidence_refs(result: PathResolutionResult) -> PathResolutionResult:
    """Rewrites every evidence ref in `result`'s own claims/resolutions through
    `_public_evidence_ref`, re-sorting/deduplicating each field afterward (`model_copy(update=...)`
    never re-validates, so this must produce already-conformant lists) - applied to Path B/C's raw
    output only, never Path A (whose refs are already real `:Evidence` ids, so this is a no-op for
    it, but calling it unconditionally on every path is simpler than special-casing which paths
    need it and keeps this correct if that ever changes)."""
    claims = [
        claim.model_copy(
            update={"evidence_refs": sorted({_public_evidence_ref(r) for r in claim.evidence_refs})}
        )
        for claim in result.claims
    ]
    resolutions = [
        resolution.model_copy(
            update={
                "supporting_evidence_refs": sorted(
                    {_public_evidence_ref(r) for r in resolution.supporting_evidence_refs}
                ),
                "conflicting_evidence_refs": sorted(
                    {_public_evidence_ref(r) for r in resolution.conflicting_evidence_refs}
                ),
            }
        )
        for resolution in result.resolutions
    ]
    return PathResolutionResult(resolutions=resolutions, claims=claims)


# --- §10: cross-path agreement/conflict/ambiguity/unresolved reduction -------------------------


def reduce_cross_path_resolutions(
    *,
    path_a: PathResolutionResult,
    path_b: PathResolutionResult,
    path_c: PathResolutionResult,
) -> PathResolutionResult:
    """Groups every path's own `DeploymentResolution`s by `resolution_id` (§10.5: only a
    `workload:`-keyed group can ever be populated by more than one path - `mapping:`/`otel:` groups
    are single-path by construction) and reduces each group to exactly one public
    `DeploymentResolution`, plus a `DeploymentClaim` when the group agrees (spec §13.1: "exactly one
    DeploymentResolution per canonical reconciliation candidate group")."""
    claims_by_claim_id = {
        claim.claim_id: claim for result in (path_a, path_b, path_c) for claim in result.claims
    }
    by_resolution_id: dict[str, list[DeploymentResolution]] = defaultdict(list)
    for result in (path_a, path_b, path_c):
        for resolution in result.resolutions:
            by_resolution_id[resolution.resolution_id].append(resolution)

    resolutions: list[DeploymentResolution] = []
    claims: list[DeploymentClaim] = []
    for resolution_id in sorted(by_resolution_id):
        merged_resolution, merged_claim = _reduce_group(
            by_resolution_id[resolution_id], claims_by_claim_id
        )
        resolutions.append(merged_resolution)
        if merged_claim is not None:
            claims.append(merged_claim)

    return PathResolutionResult(resolutions=resolutions, claims=claims)


def _reduce_group(
    members: list[DeploymentResolution], claims_by_claim_id: dict[str, DeploymentClaim]
) -> tuple[DeploymentResolution, DeploymentClaim | None]:
    first = members[0]
    successful = [m for m in members if m.status.value.startswith("RESOLVED_")]
    conflicting = [m for m in members if m.status == DeploymentResolutionStatus.CONFLICT]
    ambiguous = [m for m in members if m.status == DeploymentResolutionStatus.AMBIGUOUS]
    # "applicable" = every member that isn't just a plain UNRESOLVED sibling - mirrors
    # resolve_path_c's own established precedent (PR #220 review) that an UNRESOLVED outcome must
    # never silently support or taint a group it wasn't actually part of.
    applicable = successful + conflicting + ambiguous
    distinct_successful_ids = sorted({m.service_id for m in successful})

    # §10.2: a direct contradiction always wins - two-or-more distinct successful resolutions, or
    # any contributing path already reporting CONFLICT.
    if conflicting or len(distinct_successful_ids) > 1:
        candidate_ids = sorted({cid for m in applicable for cid in m.candidate_service_ids})
        conflicting_evidence = sorted(
            {
                ref
                for m in applicable
                for ref in (*m.supporting_evidence_refs, *m.conflicting_evidence_refs)
            }
        )
        return (
            DeploymentResolution(
                resolution_id=first.resolution_id,
                workload=first.workload,
                status=DeploymentResolutionStatus.CONFLICT,
                service_id=None,
                candidate_service_ids=candidate_ids,
                supporting_methods=[],
                supporting_evidence_refs=[],
                conflicting_evidence_refs=conflicting_evidence,
                limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_CONFLICT],
                claim_id=None,
                reconciliation_rule_id=first.reconciliation_rule_id,
                reconciliation_rule_version=first.reconciliation_rule_version,
            ),
            None,
        )

    # §10.3/§10.5: any contributing AMBIGUOUS path (only Path C ever produces one) makes the whole
    # group AMBIGUOUS, never CONFLICT, once a direct contradiction has already been ruled out above.
    if ambiguous:
        candidate_ids = sorted({cid for m in applicable for cid in m.candidate_service_ids})
        supporting_evidence = sorted(
            {
                ref
                for m in applicable
                for ref in (*m.supporting_evidence_refs, *m.conflicting_evidence_refs)
            }
        )
        return (
            DeploymentResolution(
                resolution_id=first.resolution_id,
                workload=first.workload,
                status=DeploymentResolutionStatus.AMBIGUOUS,
                service_id=None,
                candidate_service_ids=candidate_ids,
                supporting_methods=[],
                supporting_evidence_refs=supporting_evidence,
                conflicting_evidence_refs=[],
                limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_AMBIGUOUS],
                claim_id=None,
                reconciliation_rule_id=first.reconciliation_rule_id,
                reconciliation_rule_version=first.reconciliation_rule_version,
            ),
            None,
        )

    # §10.1: every successful member (if any) agrees. A co-existing UNRESOLVED sibling from a
    # different path is deliberately excluded from the agreement (this slice's own disclosed
    # assumption #3 - §13.3's `candidate_service_ids == [service_id]` invariant for RESOLVED_*
    # leaves no room for a phantom extra candidate, and §10.1 itself scopes agreement to "all
    # applicable successful paths").
    if len(distinct_successful_ids) == 1:
        [service_id] = distinct_successful_ids
        methods = sorted(
            {method for m in successful for method in m.supporting_methods},
            key=lambda method: list(_DEPLOYMENT_METHOD_TO_STATUS).index(method.value),
        )
        evidence = sorted({ref for m in successful for ref in m.supporting_evidence_refs})
        existing_claim = claims_by_claim_id[successful[0].claim_id]  # type: ignore[index]
        assert first.workload is not None  # a workload:-keyed group always has a real workload
        claim_id = compute_deployment_claim_id(service_id=service_id, workload_id=first.workload.id)
        merged_claim = DeploymentClaim(
            claim_id=claim_id,
            subject=EntityRef(
                id=service_id, type=EntityType.SERVICE, name=existing_claim.subject.name
            ),
            predicate=DeploymentPredicate.DEPLOYED_AS,
            object=first.workload,
            resolution_method=methods[0],
            supporting_methods=methods,
            reconciliation_rule_id=first.reconciliation_rule_id,
            reconciliation_rule_version=first.reconciliation_rule_version,
            evidence_refs=evidence,
        )
        merged_resolution = DeploymentResolution(
            resolution_id=first.resolution_id,
            workload=first.workload,
            status=_DEPLOYMENT_METHOD_TO_STATUS[methods[0].value],
            service_id=service_id,
            candidate_service_ids=[service_id],
            supporting_methods=methods,
            supporting_evidence_refs=evidence,
            conflicting_evidence_refs=[],
            limitation_codes=[],
            claim_id=claim_id,
            reconciliation_rule_id=first.reconciliation_rule_id,
            reconciliation_rule_version=first.reconciliation_rule_version,
        )
        return merged_resolution, merged_claim

    # §10.4: nothing succeeded and nothing directly conflicted/was ambiguous - every member is its
    # own path's UNRESOLVED outcome. Union everything (no "applicable" subset to prefer - there is
    # no successful sibling this could taint), mirroring resolve_path_c's own terminal
    # all-unresolved case.
    candidate_ids = sorted({cid for m in members for cid in m.candidate_service_ids})
    evidence = sorted(
        {
            ref
            for m in members
            for ref in (*m.supporting_evidence_refs, *m.conflicting_evidence_refs)
        }
    )
    limitation_codes = sorted(
        {code for m in members for code in m.limitation_codes}, key=lambda code: code.value
    )
    return (
        DeploymentResolution(
            resolution_id=first.resolution_id,
            workload=first.workload,
            status=DeploymentResolutionStatus.UNRESOLVED,
            service_id=None,
            candidate_service_ids=candidate_ids,
            supporting_methods=[],
            supporting_evidence_refs=evidence,
            conflicting_evidence_refs=[],
            limitation_codes=limitation_codes,
            claim_id=None,
            reconciliation_rule_id=first.reconciliation_rule_id,
            reconciliation_rule_version=first.reconciliation_rule_version,
        ),
        None,
    )


# --- §13.4: service-scoped cardinality -----------------------------------------------------------


def filter_for_service(
    reduced: PathResolutionResult, *, service_id: str
) -> tuple[list[DeploymentClaim], list[DeploymentResolution]]:
    """Returns a resolution iff `resolution.service_id == service_id` or `service_id` is one of its
    `candidate_service_ids` (spec §13.4), plus exactly the claims those resolutions name."""
    resolutions = [
        r
        for r in reduced.resolutions
        if r.service_id == service_id or service_id in r.candidate_service_ids
    ]
    claim_ids = {r.claim_id for r in resolutions if r.claim_id is not None}
    claims = [c for c in reduced.claims if c.claim_id in claim_ids]
    return claims, resolutions


# --- §20: result bounds ---------------------------------------------------------------------------


def check_result_bounds(
    claims: Sequence[DeploymentClaim], resolutions: Sequence[DeploymentResolution]
) -> LimitationCode | None:
    """Spec §20's frozen per-Service bounds (100 claims / 250 resolutions / 64 evidence-refs-per-
    claim). Evaluated by the caller on the §13.4-filtered per-Service result, before any further
    consumption - mirrors `service.py`'s existing `_MAX_CLAIMS` precedent and its own documented
    "bound before filter" lesson."""
    if len(claims) > _MAX_DEPLOYMENT_CLAIMS:
        return LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    if len(resolutions) > _MAX_DEPLOYMENT_RESOLUTIONS:
        return LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    if any(len(claim.evidence_refs) > _MAX_EVIDENCE_REFS_PER_CLAIM for claim in claims):
        return LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    return None


# --- §16.1: DEPLOYED_AS `supports` augmentation ---------------------------------------------------


def _supported_fact_sort_key(fact: SupportedFact) -> tuple[str, str, str]:
    # Mirrors `contracts._supported_fact_sort_key` (private to that module) and `service.py`'s own
    # identical local copy - `EvidenceRecord.supports`' sort key, reused here since this module
    # produces `SupportedFact` lists that must already satisfy it before a caller ever sees them.
    return (fact.relation_type.value, fact.source_id, fact.target_id)


def deployed_as_supported_facts(
    claims: Sequence[DeploymentClaim],
) -> dict[str, list[SupportedFact]]:
    """§16.1: a public evidence record reachable from a `DeploymentClaim` gets a `DEPLOYED_AS`
    `SupportedFact` in its `supports` list - never for evidence reachable only from a non-resolved
    `DeploymentResolution` (§16.1's explicit "MUST NOT falsely advertise" rule: a resolution alone
    never adds one). `DEPLOYED_AS` is never written to the graph as a real relation, so this can't
    reuse the existing relation-matching evidence query - it's a computed augmentation only this
    module can produce, since only it knows which evidence ids a claim actually names.

    PR #222 review finding: each returned list is sorted and deduplicated here, at the single
    producer, rather than leaving every call site responsible for it - `EvidenceRecord.supports`
    is contractually required to be sorted by `(relation_type, source_id, target_id)` and
    deduplicated, and `model_copy(update=...)` never re-validates that invariant."""
    result: dict[str, list[SupportedFact]] = defaultdict(list)
    for claim in claims:
        fact = SupportedFact(
            relation_type=EvidenceRelationType.DEPLOYED_AS,
            source_id=claim.subject.id,
            target_id=claim.object.id,
        )
        for ref in claim.evidence_refs:
            result[ref].append(fact)
    return {ref: sorted(set(facts), key=_supported_fact_sort_key) for ref, facts in result.items()}


# --- §16.2: selective Kubernetes/OTel/configuration evidence visibility --------------------------


def reachable_deployment_evidence_ids(
    reduced: PathResolutionResult, *, declared_service_ids: frozenset[str]
) -> frozenset[str]:
    """§16.2: an id is public iff it's in some `DeploymentClaim.evidence_refs` (always public - a
    claim's subject is always a confirmed-declared Service), or in some `DeploymentResolution`'s
    `supporting_evidence_refs`/`conflicting_evidence_refs` for a resolution that is public under
    §13.4 for at least one *currently declared* Service."""
    ids: set[str] = {ref for claim in reduced.claims for ref in claim.evidence_refs}
    for resolution in reduced.resolutions:
        is_public_for_a_declared_service = (
            resolution.service_id is not None and resolution.service_id in declared_service_ids
        ) or bool(set(resolution.candidate_service_ids) & declared_service_ids)
        if is_public_for_a_declared_service:
            ids.update(resolution.supporting_evidence_refs)
            ids.update(resolution.conflicting_evidence_refs)
    return frozenset(ids)


# --- Path B/C synthetic EvidenceRecord bridge (§16.1) ---------------------------------------------


def _path_b_evidence_records(
    document: ServiceWorkloadMappingDocument | None,
) -> dict[str, EvidenceRecord]:
    """One synthetic `EvidenceRecord` per mapping entry, keyed by its own
    `compute_service_workload_mapping_evidence_id` - the id Path B's `evidence_refs` actually use.
    `source_locator` is the mapping artifact's own basename (never the full, possibly-absolute
    configured path - spec §8.3's "sanitized relative source locator"); `source_revision` packs the
    four values §8.3 requires identifiable (`artifact_id`, `artifact_revision`, `mapping_id`, a short
    `content_digest` prefix) into one compact string - an implementation choice, not spec-normative
    (§8.3: "the exact stored representation is an implementation choice")."""
    if document is None:
        return {}
    locator = Path(document.locator).name
    records: dict[str, EvidenceRecord] = {}
    for entry in document.entries:
        evidence_id = _public_evidence_ref(
            compute_service_workload_mapping_evidence_id(
                artifact_id=document.artifact_id,
                artifact_revision=document.artifact_revision,
                content_digest=document.content_digest,
                mapping_id=entry.mapping_id,
            )
        )
        revision = (
            f"{document.artifact_id}@{document.artifact_revision}:"
            f"{entry.mapping_id}:sha256={document.content_digest[:12]}"
        )
        records[evidence_id] = EvidenceRecord(
            id=evidence_id,
            evidence_type=EvidenceType.DECLARED,
            source_type=SourceType.CONFIGURATION,
            source_locator=locator,
            source_revision=revision,
            observation=None,
            supports=[],
        )
    return records


_K8S_ATTR_ORDER = (
    ("k8s_pod_name", "k8s.pod.name"),
    ("k8s_namespace_name", "k8s.namespace.name"),
    ("k8s_cluster_uid", "k8s.cluster.uid"),
    ("k8s_deployment_name", "k8s.deployment.name"),
    ("k8s_statefulset_name", "k8s.statefulset.name"),
    ("k8s_daemonset_name", "k8s.daemonset.name"),
)


def _path_c_evidence_records(
    observations: Sequence[RuntimeIdentityObservationRow],
) -> dict[str, EvidenceRecord]:
    """One synthetic `EvidenceRecord` per persisted `RuntimeIdentityObservation`, keyed by its own
    `.id` - the id Path C's `evidence_refs` actually use. Most of "OTel observation context" (spec
    §16.1) is already covered by the existing `ObservedEvidenceMetadata` fields, reused directly
    from the observation row's own real `first_seen`/`last_seen`/`observation_count` (no fabricated
    values - `RuntimeIdentityObservation` has no distinct "bucket" concept of its own, so
    `bucket_start`/`bucket_end` reuse the same real `first_seen`/`last_seen` span). `source_locator`
    carries only the bounded, *present* `k8s.*` consistency attributes as a short `key=value,...`
    string (never raw Resource data, per §16.3's own "no raw OTLP Resource data" rule);
    `source_revision` names the normalization rule/version that produced this record (the plan's
    own design decision)."""
    records: dict[str, EvidenceRecord] = {}
    for obs in observations:
        if obs.environment is None or obs.first_seen is None or obs.last_seen is None:
            # An observation missing its own required identity fields was never itself a valid
            # Path C candidate (spec §9.1) - no evidence record is built for it either.
            continue
        present_attrs = [
            f"{label}={getattr(obs, field)}"
            for field, label in _K8S_ATTR_ORDER
            if getattr(obs, field) is not None
        ]
        source_revision = (
            f"{obs.normalization_rule_id}@{obs.normalization_rule_version}"
            if obs.normalization_rule_id is not None and obs.normalization_rule_version is not None
            else None
        )
        evidence_id = _public_evidence_ref(obs.id)
        records[evidence_id] = EvidenceRecord(
            id=evidence_id,
            evidence_type=EvidenceType.OBSERVED,
            source_type=SourceType.OPENTELEMETRY,
            source_locator=",".join(present_attrs) if present_attrs else None,
            source_revision=source_revision,
            observation=ObservedEvidenceMetadata(
                environment=obs.environment,
                bucket_start=obs.first_seen,
                bucket_end=obs.last_seen,
                first_seen=obs.first_seen,
                last_seen=obs.last_seen,
                observation_count=obs.observation_count if obs.observation_count is not None else 1,
                service_version=obs.service_version,
                correlation_mode=None,
            ),
            supports=[],
        )
    return records


# --- §16.2 correctness: context-free Path C for the evidence-visibility-only callers -------------

# Mirrors `app.architecture_intelligence.contracts._MAX_OBSERVATION_WINDOW` (private to that module,
# not re-exported) - kept as its own local constant rather than importing a private symbol across
# modules; `build_observation_context_ref` re-enforces this bound anyway, so a drift here would fail
# loudly (a raised `pydantic.ValidationError`), not silently.
_PATH_C_MAX_WINDOW = timedelta(days=31)
_PATH_C_PLACEHOLDER_ENVIRONMENT = "unspecified"
# Only ever used for a row with no usable first_seen/last_seen at all, where the temporal check
# fails regardless of window choice (see `_bucket_context_free_observations`'s own comment) - any
# fixed, valid, tz-aware placeholder is safe here.
_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)


def _resolve_workload_group_key(
    session: neo4j.Session, obs: RuntimeIdentityObservationRow
) -> tuple[str, datetime | None] | None:
    """The same Pod-UID -> exactly-one-Pod -> exactly-one-owner resolution
    `deployment_projection._evaluate_observation` performs before its own temporal/environment
    check - replicated here (read-only, side-effect-free) purely to compute a *grouping* key, never
    to decide RESOLVED/CONFLICT/AMBIGUOUS status (that stays `resolve_path_c`'s own job, called
    below with each group's own real data). `None` for every case that never reaches a single
    resolved Workload - those observations don't share a `resolve_path_c` group_key with any
    other observation, so they need no grouping at all (see `_bucket_context_free_observations`).
    Also returns the matched Pod's own `captured_at` (parsed) - PR #222 review finding (human
    reviewer), round 2: `_observation_context_limitation` checks the Pod's `captured_at` against
    the window *in addition to* the observation's own `first_seen`/`last_seen`, so a bucket window
    built from observation timestamps alone can still incorrectly reject an otherwise-applicable
    observation whose Pod was captured outside that narrower span."""
    if not obs.k8s_pod_uid:
        return None
    pods = read_captured_pods_by_uid(session, pod_uid=obs.k8s_pod_uid)
    if len(pods) != 1:
        return None
    [pod] = pods
    owners = read_workload_ids_owning_pod(session, pod_id=pod.pod_id)
    if len(owners) != 1:
        return None
    captured_at = None
    if pod.captured_at is not None:
        try:
            captured_at = datetime.fromisoformat(pod.captured_at)
        except ValueError:
            captured_at = None
    return owners[0].workload_id, captured_at


def _row_span(row: RuntimeIdentityObservationRow, captured_at: datetime | None) -> tuple | None:
    """Every timestamp `_observation_context_limitation` checks this row against - its own
    `first_seen`/`last_seen` *and* its matched Pod's `captured_at` - so a bucket window built to
    cover this span guarantees the row passes §9.7's temporal check regardless of which bucket it
    lands in. `None` when no timestamp is usable at all."""
    values = [v for v in (row.first_seen, row.last_seen, captured_at) if v is not None]
    return (min(values), max(values)) if values else None


def _bucket_by_window(
    rows: list[tuple[RuntimeIdentityObservationRow, datetime | None]],
) -> list[tuple[list[tuple[RuntimeIdentityObservationRow, datetime | None]], tuple | None]]:
    """Greedily packs same-(workload, environment) rows, sorted by their own span start, into
    consecutive buckets whose own combined, *clamped* span never exceeds `ObservationContextRef`'s
    31-day maximum window - so every bucket's returned bounds can become one valid, real
    caller-shaped context. Returns each bucket paired with its own `(window_start, window_end)`
    bounds (already clamped) rather than leaving the caller to recompute them from the bucket's raw
    rows - recomputing independently would silently drop the clamp this function just applied.

    A row with no usable timestamp at all can never satisfy §9.7's temporal check regardless of
    which window is chosen (same outcome a real caller-supplied context would also produce for it:
    `DEPLOYMENT_TEMPORAL_MISMATCH`/`DEPLOYMENT_EVIDENCE_INCOMPLETE`), so it gets its own singleton
    bucket with `None` bounds rather than forcing every other row's window wider to accommodate it.

    PR #222 review finding (round 2): a single row's *own* span (first_seen/last_seen vs. its Pod's
    independently-timestamped captured_at) can itself exceed 31 days - the original version only
    checked the 31-day limit when *merging* a row into an already-existing bucket, never for a
    brand-new one, so an unclamped >31-day single-row span reached `build_observation_context_ref`
    unclamped and raised - a crash (get_evidence's own 500), not a refusal. Clamped here to the most
    recent 31 days: no real caller-supplied context could ever cover a >31-day span either, so this
    row would fail `DEPLOYMENT_TEMPORAL_MISMATCH` against a real request the same way - clamping
    just lets `resolve_path_c` reach that same, correct conclusion instead of crashing first."""
    spans = [(row, captured_at, _row_span(row, captured_at)) for row, captured_at in rows]
    timestamped = sorted((s for s in spans if s[2] is not None), key=lambda s: s[2][0])
    untimestamped = [s for s in spans if s[2] is None]

    buckets: list[list[tuple[RuntimeIdentityObservationRow, datetime | None]]] = []
    bounds: list[tuple] = []
    for row, captured_at, (span_min, span_max) in timestamped:
        if buckets:
            min_first, max_last = bounds[-1]
            candidate_min = min(min_first, span_min)
            candidate_max = max(max_last, span_max)
            if candidate_max - candidate_min <= _PATH_C_MAX_WINDOW:
                buckets[-1].append((row, captured_at))
                bounds[-1] = (candidate_min, candidate_max)
                continue
        buckets.append([(row, captured_at)])
        if span_max - span_min > _PATH_C_MAX_WINDOW:
            bounds.append((span_max - _PATH_C_MAX_WINDOW, span_max))
        else:
            bounds.append((span_min, span_max))

    result = list(zip(buckets, bounds, strict=True))
    result.extend(([(row, captured_at)], None) for row, captured_at, _ in untimestamped)
    return result


def _bucket_context_free_observations(
    session: neo4j.Session, observations: Sequence[RuntimeIdentityObservationRow]
) -> list[tuple[list[RuntimeIdentityObservationRow], ObservationContextRef]]:
    """Groups observations exactly the way `resolve_path_c`'s own reduction would (§13.1: a
    `"workload:"` group is keyed by the resolved Workload id alone - never by context), then builds
    one real, valid `ObservationContextRef` per group so each can be passed through the unmodified
    `resolve_path_c` in one call, preserving its own cross-observation AMBIGUOUS/CONFLICT
    detection within the group. Calling `resolve_path_c` once per *observation* instead would be
    unsound: it would silently fragment one Workload's multi-observation reduction into several
    single-observation calls that can never see each other's candidates."""
    grouped: dict[
        tuple[str, str | None], list[tuple[RuntimeIdentityObservationRow, datetime | None]]
    ] = defaultdict(list)
    standalone: list[tuple[RuntimeIdentityObservationRow, datetime | None]] = []
    for obs in observations:
        resolved = _resolve_workload_group_key(session, obs)
        if resolved is None:
            standalone.append((obs, None))
        else:
            workload_id, captured_at = resolved
            grouped[(workload_id, obs.environment)].append((obs, captured_at))

    batches: list[tuple[list[RuntimeIdentityObservationRow], ObservationContextRef]] = []
    for (_workload_id, environment), rows in grouped.items():
        for bucket, bounds in _bucket_by_window(rows):
            # Use `_bucket_by_window`'s own already-clamped bounds directly - recomputing from the
            # bucket's raw rows here would silently drop its 31-day clamp (PR #222 review finding,
            # round 2) and could build an invalid ObservationContextRef again.
            if bounds is not None:
                window_start, window_end = bounds
            else:
                # No usable timestamp on any row in this singleton bucket - the placeholder window
                # is never actually consulted (DEPLOYMENT_EVIDENCE_INCOMPLETE/TEMPORAL_MISMATCH
                # fires first either way), it only needs to be a *valid* ObservationContextRef.
                window_start = window_end = _EPOCH
            context = build_observation_context_ref(
                environment or _PATH_C_PLACEHOLDER_ENVIRONMENT, window_start, window_end
            )
            batches.append(([row for row, _ in bucket], context))

    # Every standalone observation gets its own placeholder-context singleton batch - its
    # resolve_path_c group_key is keyed by its own observation id (never a Workload id), and the
    # temporal/environment check is never reached for it (see `_resolve_workload_group_key`'s
    # docstring), so the context value is inert here too.
    for obs, _captured_at in standalone:
        context = build_observation_context_ref(
            obs.environment or _PATH_C_PLACEHOLDER_ENVIRONMENT,
            obs.first_seen or _EPOCH,
            obs.last_seen or _EPOCH,
        )
        batches.append(([obs], context))

    return batches


def _resolve_path_c_context_free(
    session: neo4j.Session,
    *,
    observations: Sequence[RuntimeIdentityObservationRow],
    candidates: Sequence[DeclaredServiceCandidate],
    service_aliases: dict[str, str],
    snapshot_id: str,
    context_id: str,
) -> PathResolutionResult:
    """spec §16.2: "Every evidence ref emitted in a DeploymentClaim or DeploymentResolution SHALL
    resolve through REST evidence resolution and negotiated MCP get_evidence at the exact same
    snapshot" - unconditional, with no carve-out for Path C. The evidence-visibility-only callers
    (`get_evidence`/`list_public_evidence`/`get_public_evidence`) have no caller-supplied
    observation context of their own, so this builds one synthetic, valid context per group of
    observations that would share one `resolve_path_c` group_key (see
    `_bucket_context_free_observations`) and calls the real, unmodified `resolve_path_c` once per
    group - never reimplementing its resolution logic. `resolution_id`/`claim_id` are unaffected by
    which synthetic context is used (they hash `(snapshot_id, context_id, group_key)`, and
    `group_key` depends only on the resolved Workload id / observation id - never on
    `observation_context`), so this reproduces exactly what a real caller-supplied context wide
    enough to cover the data would also produce.

    Disclosed limitation: a single Workload's own observation history spanning more than 31 days
    is packed into multiple sequential windows (`_bucket_by_window`) rather than one - each window
    is independently resolved, so an observation more than 31 days older than that Workload's most
    recent one is evaluated in a separate `resolve_path_c` call and never cross-checked against it
    for AMBIGUOUS/CONFLICT. This narrows, but does not reopen, the gap this function exists to
    close - the alternative (skipping Path C here entirely) is the actual §16.2 violation."""
    resolutions: list = []
    claims: list = []
    for bucket, context in _bucket_context_free_observations(session, observations):
        result = resolve_path_c(
            observations=bucket,
            observation_context=context,
            lookup_pods_by_uid=lambda pod_uid: read_captured_pods_by_uid(session, pod_uid=pod_uid),
            lookup_workload_ids_owning_pod=lambda pod_id: read_workload_ids_owning_pod(
                session, pod_id=pod_id
            ),
            resolve_workload=lambda entity_id: read_current_kubernetes_workload(
                session, entity_id=entity_id
            ),
            declared_service_candidates=candidates,
            service_aliases=service_aliases,
            lookup_declared_service=lambda service_id: read_declared_service_identity(
                session, service_id=service_id
            ),
            snapshot_id=snapshot_id,
            context_id=context_id,
        )
        resolutions.extend(result.resolutions)
        claims.extend(result.claims)
    return PathResolutionResult(resolutions=resolutions, claims=claims)


# --- Whole-graph orchestration --------------------------------------------------------------------


@dataclass(frozen=True)
class WholeGraphReconciliation:
    reduced: PathResolutionResult
    declared_service_ids: frozenset[str]
    synthetic_evidence_records: dict[str, EvidenceRecord]
    reachable_evidence_ids: frozenset[str]


def run_whole_graph_reconciliation(
    session: neo4j.Session,
    *,
    snapshot_id: str,
    context_id: str,
    observation_context: ObservationContextRef | None,
    document: ServiceWorkloadMappingDocument | None,
    configured_kubernetes_sources: Sequence[tuple[str, str]],
    service_aliases: dict[str, str],
) -> WholeGraphReconciliation:
    """The single whole-graph read+reduce step `ArchitectureIntelligenceService` calls once per
    stable-read attempt (never per-Service - §13.1's reduction is graph-wide, §13.4's per-Service
    filter is applied by the caller afterward from this same result).

    `observation_context=None` skips Path C entirely (Path A/B are context-free; only Path C's
    §9.7 temporal/environment applicability check needs one). Used by the evidence-visibility-only
    callers (`get_evidence`/`list_public_evidence`/`get_public_evidence`), which have no
    caller-supplied observation context of their own to evaluate Path C against - a real,
    disclosed limitation of this slice, not an oversight: `compute_deployment_resolution_id`
    hashes `context_id` into `resolution_id` (spec §13.2), so Path C reachability for these three
    convenience methods would otherwise require picking one arbitrary (environment, window) out of
    thin air, or unioning across every persisted environment despite each producing genuinely
    different (and individually correct) `resolution_id`s that cannot be merged. `get_service_
    dependencies`/`GET .../deployments` (this slice's primary, spec-mandated exposure surface) are
    unaffected - they always supply a real request-scoped observation context and get full Path A/
    B/C support."""
    declared_services = read_declared_service_ids(session)
    declared_service_ids = frozenset(declared_services)

    def _lookup_service_name(service_id: str) -> str | None:
        return declared_services.get(service_id)

    # Path C's own resolution needs the wider (declared-or-observed-only) candidate list purely for
    # `resolve_service`'s name/namespace/alias *candidate generation* - it independently re-verifies
    # any DECLARED result against the strict `owner_source_ids` check via `lookup_declared_service`
    # below (see `deployment_projection._resolve_declared_service_id`'s own docstring), so reusing
    # the loose list here does not reintroduce the OBSERVED_ONLY-qualifies bug fixed above.
    candidates = fetch_candidates(session)

    workloads = iter_current_kubernetes_workloads(session)
    # PR #222 review finding (human reviewer): fetched unconditionally now - the observation_
    # context=None branch below still needs every current observation, both to build the
    # context-free Path C result and to key the synthetic evidence records against it.
    observations = read_runtime_identity_observations(session)

    path_a = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_lookup_service_name,
        snapshot_id=snapshot_id,
        context_id=context_id,
    )
    path_b = _publicize_evidence_refs(
        resolve_path_b(
            document=document,
            configured_kubernetes_sources=configured_kubernetes_sources,
            resolve_workload=lambda entity_id: read_current_kubernetes_workload(
                session, entity_id=entity_id
            ),
            lookup_service_name=_lookup_service_name,
            snapshot_id=snapshot_id,
            context_id=context_id,
        )
    )
    if observation_context is not None:
        path_c = _publicize_evidence_refs(
            resolve_path_c(
                observations=observations,
                observation_context=observation_context,
                lookup_pods_by_uid=lambda pod_uid: read_captured_pods_by_uid(
                    session, pod_uid=pod_uid
                ),
                lookup_workload_ids_owning_pod=lambda pod_id: read_workload_ids_owning_pod(
                    session, pod_id=pod_id
                ),
                resolve_workload=lambda entity_id: read_current_kubernetes_workload(
                    session, entity_id=entity_id
                ),
                declared_service_candidates=candidates,
                service_aliases=service_aliases,
                lookup_declared_service=lambda service_id: read_declared_service_identity(
                    session, service_id=service_id
                ),
                snapshot_id=snapshot_id,
                context_id=context_id,
            )
        )
    else:
        # PR #222 review finding (human reviewer): spec §16.2 requires every evidence ref emitted
        # in a DeploymentClaim/DeploymentResolution to resolve through get_evidence at the same
        # snapshot, with no carve-out for Path C - skipping Path C entirely here (as an earlier
        # version of this function did) would let get_service_dependencies emit Path C evidence
        # refs that get_evidence/list_public_evidence/get_public_evidence could never resolve.
        path_c = _publicize_evidence_refs(
            _resolve_path_c_context_free(
                session,
                observations=observations,
                candidates=candidates,
                service_aliases=service_aliases,
                snapshot_id=snapshot_id,
                context_id=context_id,
            )
        )

    reduced = reduce_cross_path_resolutions(path_a=path_a, path_b=path_b, path_c=path_c)
    reachable = reachable_deployment_evidence_ids(
        reduced, declared_service_ids=declared_service_ids
    )
    synthetic_evidence = {
        **_path_b_evidence_records(document),
        **_path_c_evidence_records(observations),
    }

    return WholeGraphReconciliation(
        reduced=reduced,
        declared_service_ids=declared_service_ids,
        synthetic_evidence_records=synthetic_evidence,
        reachable_evidence_ids=reachable,
    )
