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
from app.provenance.model import SourceType
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument
from app.telemetry.service_resolver import fetch_candidates

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


def deployed_as_supported_facts(
    claims: Sequence[DeploymentClaim],
) -> dict[str, list[SupportedFact]]:
    """§16.1: a public evidence record reachable from a `DeploymentClaim` gets a `DEPLOYED_AS`
    `SupportedFact` in its `supports` list - never for evidence reachable only from a non-resolved
    `DeploymentResolution` (§16.1's explicit "MUST NOT falsely advertise" rule: a resolution alone
    never adds one). `DEPLOYED_AS` is never written to the graph as a real relation, so this can't
    reuse the existing relation-matching evidence query - it's a computed augmentation only this
    module can produce, since only it knows which evidence ids a claim actually names."""
    result: dict[str, list[SupportedFact]] = defaultdict(list)
    for claim in claims:
        fact = SupportedFact(
            relation_type=EvidenceRelationType.DEPLOYED_AS,
            source_id=claim.subject.id,
            target_id=claim.object.id,
        )
        for ref in claim.evidence_refs:
            result[ref].append(fact)
    return dict(result)


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
        evidence_id = compute_service_workload_mapping_evidence_id(
            artifact_id=document.artifact_id,
            artifact_revision=document.artifact_revision,
            content_digest=document.content_digest,
            mapping_id=entry.mapping_id,
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
    from the observation row with zero new encoding; `source_locator` carries only the bounded,
    *present* `k8s.*` consistency attributes as a short `key=value,...` string (never raw Resource
    data, per §16.3's own "no raw OTLP Resource data" rule)."""
    records: dict[str, EvidenceRecord] = {}
    for obs in observations:
        if obs.environment is None or obs.last_seen is None:
            # An observation missing its own required identity fields was never itself a valid
            # Path C candidate (spec §9.1) - no evidence record is built for it either.
            continue
        present_attrs = [
            f"{label}={getattr(obs, field)}"
            for field, label in _K8S_ATTR_ORDER
            if getattr(obs, field) is not None
        ]
        records[obs.id] = EvidenceRecord(
            id=obs.id,
            evidence_type=EvidenceType.OBSERVED,
            source_type=SourceType.OPENTELEMETRY,
            source_locator=",".join(present_attrs) if present_attrs else None,
            source_revision=None,
            observation=ObservedEvidenceMetadata(
                environment=obs.environment,
                bucket_start=obs.last_seen,
                bucket_end=obs.last_seen,
                first_seen=obs.last_seen,
                last_seen=obs.last_seen,
                observation_count=1,
                service_version=obs.service_version,
                correlation_mode=None,
            ),
            supports=[],
        )
    return records


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
    observations = read_runtime_identity_observations(session) if observation_context else []

    path_a = resolve_path_a(
        workloads=workloads,
        lookup_service_name=_lookup_service_name,
        snapshot_id=snapshot_id,
        context_id=context_id,
    )
    path_b = resolve_path_b(
        document=document,
        configured_kubernetes_sources=configured_kubernetes_sources,
        resolve_workload=lambda entity_id: read_current_kubernetes_workload(
            session, entity_id=entity_id
        ),
        lookup_service_name=_lookup_service_name,
        snapshot_id=snapshot_id,
        context_id=context_id,
    )
    path_c = (
        resolve_path_c(
            observations=observations,
            observation_context=observation_context,
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
        if observation_context is not None
        else PathResolutionResult(resolutions=[], claims=[])
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
