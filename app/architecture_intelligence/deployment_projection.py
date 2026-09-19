"""v0.5.0 I3 spec §7 (Path A), §8 (Path B), §13 (resolution identity/shape) - pure functions
projecting already-persisted I2 Kubernetes facts and a locally loaded configured mapping artifact
into `DeploymentClaim`/`DeploymentResolution` instances (frozen contracts from
`app.architecture_intelligence.contracts`). No Neo4j access here - real reads live in
`app.architecture_intelligence.deployment_repository`, which supplies this module's `CurrentKubernetesWorkload`
rows and `lookup_service_name`/`resolve_workload` callables; unit tests supply fakes instead,
mirroring how `app.architecture_intelligence.dependency_projection` takes plain rows rather than a
live database. Path C (OTel-observed linkage, slice 4) and cross-path agreement/conflict reduction
across A/B/C (slice 5) are out of scope here - each path below runs alone and returns its own
resolutions/claims.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import (
    DEPLOYMENT_RECONCILIATION_RULE_ID,
    DeploymentClaim,
    DeploymentPredicate,
    DeploymentResolution,
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    EntityRef,
    EntityType,
    LimitationCode,
    WorkloadKind,
    WorkloadRef,
)
from app.sources.identity import kubernetes_logical_resource_id
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    ServiceWorkloadMappingEntry,
)

_RECONCILIATION_RULE_VERSION = 1

# I3 spec §11 / §8.1: the raw Kubernetes controller-kind string (matching I2's own
# `InfrastructureEntity.resource_kind` convention) mapped onto the public, uppercase
# `WorkloadKind` enum. No case folding or fuzzy matching - a `workload_kind` outside this map is a
# real defect (I2 already restricts KUBERNETES_WORKLOAD promotion to exactly these three kinds).
_WORKLOAD_KIND_BY_RAW = {
    "Deployment": WorkloadKind.DEPLOYMENT,
    "StatefulSet": WorkloadKind.STATEFULSET,
    "DaemonSet": WorkloadKind.DAEMONSET,
}


@dataclass(frozen=True)
class WorkloadContribution:
    """One I2 `InfrastructureContribution` row for a Workload, reduced to the fields Path A needs:
    the retained `service-id` annotation (`None` if this contribution carries none) and the
    contribution's own evidence references."""

    annotation: str | None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CurrentKubernetesWorkload:
    """One current I2 `InfrastructureEntity` of kind `KUBERNETES_WORKLOAD`, identified by its
    logical resource id (`app.sources.identity.kubernetes_logical_resource_id`). `contributions` is
    populated for Path A's full scan and left empty (the default) when this row is returned as a
    single Path B point-lookup result, where only the Workload's own identity fields are needed."""

    workload_id: str
    workload_kind: str
    namespace: str
    name: str
    contributions: tuple[WorkloadContribution, ...] = ()


@dataclass(frozen=True)
class PathResolutionResult:
    resolutions: list[DeploymentResolution]
    claims: list[DeploymentClaim]


def compute_deployment_claim_id(*, service_id: str, workload_id: str) -> str:
    """Spec §6: `aip:claim:v1:sha256(canonical-json({"DEPLOYED_AS", canonical Service id, logical
    Workload id}))`. Deliberately excludes evidence method - "changing evidence method without
    changing the Service/Workload pair does not create a different semantic claim id" - mirrors
    `app.architecture_intelligence.dependency_projection.compute_claim_id`'s identical shape."""
    payload = {
        "predicate": "DEPLOYED_AS",
        "service_id": service_id,
        "workload_id": workload_id,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:claim:v1:{digest}"


def compute_deployment_group_key(
    *,
    workload_id: str | None = None,
    mapping_artifact_id: str | None = None,
    mapping_artifact_revision: str | None = None,
    mapping_id: str | None = None,
) -> str:
    """Spec §13.1's reconciliation-candidate-group key, restricted to the two branches slice 3
    needs (the third, OTel-unresolved branch, is slice 4's). Exactly one of `workload_id` or the
    three `mapping_*` arguments must be given.

    The mapping branch's canonical-JSON dict encoding (not delimiter concatenation) is normative
    per §13.1, specifically so delimiter-bearing artifact id/revision/mappingId values can never
    collide across a different `(artifact_id, artifact_revision, mapping_id)` tuple.
    """
    mapping_fields_given = any(
        value is not None for value in (mapping_artifact_id, mapping_artifact_revision, mapping_id)
    )
    if workload_id is not None and mapping_fields_given:
        raise ValueError(
            "compute_deployment_group_key accepts either workload_id or the mapping_* fields, "
            "not both"
        )
    if workload_id is not None:
        return f"workload:{workload_id}"
    if mapping_artifact_id is None or mapping_artifact_revision is None or mapping_id is None:
        raise ValueError(
            "compute_deployment_group_key requires either workload_id or all three of "
            "mapping_artifact_id/mapping_artifact_revision/mapping_id"
        )
    payload = {
        "artifact_id": mapping_artifact_id,
        "artifact_revision": mapping_artifact_revision,
        "mapping_id": mapping_id,
    }
    return "mapping:" + canonical_json_bytes(payload).decode("utf-8")


def compute_deployment_resolution_id(
    *,
    snapshot_id: str,
    context_id: str,
    group_key: str,
    reconciliation_rule_id: str = DEPLOYMENT_RECONCILIATION_RULE_ID,
    reconciliation_rule_version: int = _RECONCILIATION_RULE_VERSION,
) -> str:
    """Spec §13.2's literal formula. The exact canonical-JSON key names hashed here are this
    module's own implementation choice (§13.2 states the formula in prose, not a schema) - only
    "same 5 components -> same id, any different component -> a different id" is observable/
    normative behavior."""
    payload = {
        "snapshot_id": snapshot_id,
        "context_id": context_id,
        "group_key": group_key,
        "reconciliation_rule_id": reconciliation_rule_id,
        "reconciliation_rule_version": reconciliation_rule_version,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"aip:deployment-resolution:v1:{digest}"


def compute_service_workload_mapping_evidence_id(
    *, artifact_id: str, artifact_revision: str, content_digest: str, mapping_id: str
) -> str:
    """Spec §8.3: deterministic evidence identity bound to the mapping artifact's id, revision,
    content digest, and this entry's `mappingId`. Uses the same canonical-JSON dict-encoding
    approach as `compute_deployment_group_key`'s mapping branch (not delimiter concatenation), for
    consistency with §13.1's explicit normative requirement and because this is the same 4-field
    identity reused across both formulas."""
    payload = {
        "artifact_id": artifact_id,
        "artifact_revision": artifact_revision,
        "content_digest": content_digest,
        "mapping_id": mapping_id,
    }
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return f"urn:aip:service-workload-mapping-evidence:v1:{digest}"


def _workload_ref(workload: CurrentKubernetesWorkload) -> WorkloadRef:
    return WorkloadRef(
        id=workload.workload_id,
        type=EntityType.WORKLOAD,
        name=workload.name,
        workload_kind=_WORKLOAD_KIND_BY_RAW[workload.workload_kind],
        namespace=workload.namespace,
    )


def _resolved_claim(
    *,
    service_id: str,
    service_name: str,
    workload_ref: WorkloadRef,
    method: DeploymentResolutionMethod,
    evidence_refs: list[str],
) -> DeploymentClaim:
    claim_id = compute_deployment_claim_id(service_id=service_id, workload_id=workload_ref.id)
    return DeploymentClaim(
        claim_id=claim_id,
        subject=EntityRef(id=service_id, type=EntityType.SERVICE, name=service_name),
        predicate=DeploymentPredicate.DEPLOYED_AS,
        object=workload_ref,
        resolution_method=method,
        supporting_methods=[method],
        reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
        reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
        evidence_refs=evidence_refs,
    )


def resolve_path_a(
    *,
    workloads: Sequence[CurrentKubernetesWorkload],
    lookup_service_name: Callable[[str], str | None],
    snapshot_id: str,
    context_id: str,
) -> PathResolutionResult:
    """Spec §7: for every current I2 `KUBERNETES_WORKLOAD` entity, group its contributions'
    retained `service-id` annotations by exact string equality (no trim/case-fold/fuzzy matching).
    A Workload with no annotated contribution at all produces no resolution (there is no Path A
    evidence to report); one agreed annotation resolves or is `UNRESOLVED` depending on whether it
    names a real declared Service; more than one distinct annotation is `CONFLICT`."""
    resolutions: list[DeploymentResolution] = []
    claims: list[DeploymentClaim] = []

    for workload in workloads:
        annotated = [c for c in workload.contributions if c.annotation is not None]
        if not annotated:
            continue

        distinct_values = sorted({c.annotation for c in annotated if c.annotation is not None})
        evidence_refs = sorted({ref for c in annotated for ref in c.evidence_refs})
        workload_ref = _workload_ref(workload)
        group_key = compute_deployment_group_key(workload_id=workload.workload_id)
        resolution_id = compute_deployment_resolution_id(
            snapshot_id=snapshot_id, context_id=context_id, group_key=group_key
        )

        if len(distinct_values) > 1:
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.CONFLICT,
                    service_id=None,
                    candidate_service_ids=distinct_values,
                    supporting_methods=[],
                    supporting_evidence_refs=[],
                    conflicting_evidence_refs=evidence_refs,
                    limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_CONFLICT],
                    claim_id=None,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )
            continue

        [value] = distinct_values
        service_name = lookup_service_name(value)
        if service_name is not None:
            claim = _resolved_claim(
                service_id=value,
                service_name=service_name,
                workload_ref=workload_ref,
                method=DeploymentResolutionMethod.RESOLVED_EXPLICIT,
                evidence_refs=evidence_refs,
            )
            claims.append(claim)
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.RESOLVED_EXPLICIT,
                    service_id=value,
                    candidate_service_ids=[value],
                    supporting_methods=[DeploymentResolutionMethod.RESOLVED_EXPLICIT],
                    supporting_evidence_refs=evidence_refs,
                    conflicting_evidence_refs=[],
                    limitation_codes=[],
                    claim_id=claim.claim_id,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )
        else:
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.UNRESOLVED,
                    service_id=None,
                    candidate_service_ids=[value],
                    supporting_methods=[],
                    supporting_evidence_refs=evidence_refs,
                    conflicting_evidence_refs=[],
                    limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED],
                    claim_id=None,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )

    return PathResolutionResult(resolutions=resolutions, claims=claims)


@dataclass(frozen=True)
class _MappingRecord:
    document: ServiceWorkloadMappingDocument
    entry: ServiceWorkloadMappingEntry
    mapping_evidence_id: str
    workload: CurrentKubernetesWorkload | None


def resolve_path_b(
    *,
    document: ServiceWorkloadMappingDocument | None,
    configured_kubernetes_sources: Sequence[tuple[str, str]],
    resolve_workload: Callable[[str], CurrentKubernetesWorkload | None],
    lookup_service_name: Callable[[str], str | None],
    snapshot_id: str,
    context_id: str,
) -> PathResolutionResult:
    """Spec §8.1: "Path B uses one local, versioned mapping artifact" - `document` is that single
    artifact (or `None` when none is configured), never a collection. For every entry, check its
    `(kubernetesSourceId, clusterUid)` against the currently configured I2 sources, then resolve the
    exact Workload via `kubernetes_logical_resource_id` + `resolve_workload` (a point lookup the
    caller supplies - real reads live in `app.architecture_intelligence.deployment_repository`).
    Entries resolving to the same Workload are grouped per §13.1's `"workload:"` branch
    (`RESOLVED_CONFIGURED`/`UNRESOLVED`/`CONFLICT`, mirroring `resolve_path_a`'s identical
    reduction); entries whose target Workload didn't resolve (wrong source/cluster UID, or no
    matching current Workload) each get their own `"mapping:"`-keyed group -> `UNRESOLVED` with
    `workload = null`.
    """
    if document is None:
        return PathResolutionResult(resolutions=[], claims=[])

    current_source_pairs = set(configured_kubernetes_sources)
    records: list[_MappingRecord] = []

    for entry in document.entries:
        mapping_evidence_id = compute_service_workload_mapping_evidence_id(
            artifact_id=document.artifact_id,
            artifact_revision=document.artifact_revision,
            content_digest=document.content_digest,
            mapping_id=entry.mapping_id,
        )
        matches_current_source = (
            entry.kubernetes_source_id,
            entry.cluster_uid,
        ) in current_source_pairs
        workload: CurrentKubernetesWorkload | None = None
        if matches_current_source:
            entity_id = kubernetes_logical_resource_id(
                cluster_uid=entry.cluster_uid,
                api_group=entry.api_group,
                kind=entry.workload_kind,
                namespace=entry.namespace,
                name=entry.name,
            )
            workload = resolve_workload(entity_id)
        records.append(
            _MappingRecord(
                document=document,
                entry=entry,
                mapping_evidence_id=mapping_evidence_id,
                workload=workload,
            )
        )

    by_workload_id: dict[str, list[_MappingRecord]] = defaultdict(list)
    unmatched: list[_MappingRecord] = []
    for record in records:
        if record.workload is not None:
            by_workload_id[record.workload.workload_id].append(record)
        else:
            unmatched.append(record)

    resolutions: list[DeploymentResolution] = []
    claims: list[DeploymentClaim] = []

    for workload_id in sorted(by_workload_id):
        group_records = by_workload_id[workload_id]
        workload_ref = _workload_ref(group_records[0].workload)  # type: ignore[arg-type]
        group_key = compute_deployment_group_key(workload_id=workload_id)
        resolution_id = compute_deployment_resolution_id(
            snapshot_id=snapshot_id, context_id=context_id, group_key=group_key
        )
        distinct_services = sorted({record.entry.service_id for record in group_records})
        evidence_refs = sorted({record.mapping_evidence_id for record in group_records})

        if len(distinct_services) > 1:
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.CONFLICT,
                    service_id=None,
                    candidate_service_ids=distinct_services,
                    supporting_methods=[],
                    supporting_evidence_refs=[],
                    conflicting_evidence_refs=evidence_refs,
                    limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_CONFLICT],
                    claim_id=None,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )
            continue

        [service_id] = distinct_services
        service_name = lookup_service_name(service_id)
        if service_name is not None:
            claim = _resolved_claim(
                service_id=service_id,
                service_name=service_name,
                workload_ref=workload_ref,
                method=DeploymentResolutionMethod.RESOLVED_CONFIGURED,
                evidence_refs=evidence_refs,
            )
            claims.append(claim)
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.RESOLVED_CONFIGURED,
                    service_id=service_id,
                    candidate_service_ids=[service_id],
                    supporting_methods=[DeploymentResolutionMethod.RESOLVED_CONFIGURED],
                    supporting_evidence_refs=evidence_refs,
                    conflicting_evidence_refs=[],
                    limitation_codes=[],
                    claim_id=claim.claim_id,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )
        else:
            resolutions.append(
                DeploymentResolution(
                    resolution_id=resolution_id,
                    workload=workload_ref,
                    status=DeploymentResolutionStatus.UNRESOLVED,
                    service_id=None,
                    candidate_service_ids=[service_id],
                    supporting_methods=[],
                    supporting_evidence_refs=evidence_refs,
                    conflicting_evidence_refs=[],
                    limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED],
                    claim_id=None,
                    reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                    reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
                )
            )

    for record in sorted(
        unmatched,
        key=lambda r: (r.document.artifact_id, r.document.artifact_revision, r.entry.mapping_id),
    ):
        group_key = compute_deployment_group_key(
            mapping_artifact_id=record.document.artifact_id,
            mapping_artifact_revision=record.document.artifact_revision,
            mapping_id=record.entry.mapping_id,
        )
        resolution_id = compute_deployment_resolution_id(
            snapshot_id=snapshot_id, context_id=context_id, group_key=group_key
        )
        resolutions.append(
            DeploymentResolution(
                resolution_id=resolution_id,
                workload=None,
                status=DeploymentResolutionStatus.UNRESOLVED,
                service_id=None,
                candidate_service_ids=[record.entry.service_id],
                supporting_methods=[],
                supporting_evidence_refs=[record.mapping_evidence_id],
                conflicting_evidence_refs=[],
                limitation_codes=[LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED],
                claim_id=None,
                reconciliation_rule_id=DEPLOYMENT_RECONCILIATION_RULE_ID,
                reconciliation_rule_version=_RECONCILIATION_RULE_VERSION,
            )
        )

    return PathResolutionResult(resolutions=resolutions, claims=claims)
