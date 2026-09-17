"""I2 Draft 0.2 §7.2 (`WORKLOAD_OWNS_POD` claim) and §7.3 ("Workload owner chain") - v0.5.0 I2 §12
slice 4a: resolves each admitted Pod's controller-owner chain to a supported Workload. Pure logic,
no Neo4j and no `Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_mapping`'s
own "sources layer = pure" discipline. `app.ingestion.kubernetes_adapter` is the caller: it turns
`ResolvedOwnership` results into `InfrastructureClaim`/evidence, minting any evidence a resolved
chain's own participants still need.

§7.3's three accepted chains are Pod->StatefulSet, Pod->DaemonSet, and Pod->ReplicaSet->Deployment -
at most two hops. This module walks exactly that bound rather than an unbounded reference-chasing
loop: anything requiring a third hop is already "unsupported chain shape" under §7.3's own accepted-
chain list, so a hard two-hop bound can never under- or over-accept relative to the spec, and cannot
itself infinite-loop. A genuine cycle *within* that bound - a resource whose own controller reference
points back at itself or at the resource that named it - is checked explicitly (see `_find_owner`'s
callers) and rejects the source, distinct from an ordinary unsupported-shape limitation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sources.identity import kubernetes_logical_resource_id
from app.sources.kubernetes_mapping import MappedResource
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult

_POD_KIND = "Pod"
_REPLICASET_KIND = "ReplicaSet"
_DEPLOYMENT_KIND = "Deployment"
_DIRECT_WORKLOAD_KINDS = frozenset({"StatefulSet", "DaemonSet"})


def _api_group(api_version: str) -> str:
    """I2 Draft 0.2 §6: "The core API group is the empty string." Duplicated from
    `kubernetes_mapping._api_group` (private there) rather than imported - both are the same
    one-line §6 formula, not a shared abstraction worth coupling two modules over.
    """
    group, _, _version = api_version.rpartition("/")
    return group


@dataclass(frozen=True)
class ResolvedOwnership:
    """One resolved §7.3 chain, ready for `app.ingestion.kubernetes_adapter` to turn into a
    `WORKLOAD_OWNS_POD` claim."""

    workload_logical_id: str
    pod_logical_id: str
    evidence_resource_logical_ids: tuple[str, ...]
    """Sorted logical ids of every resource this chain's evidence must union - the Pod and the
    Workload for a 1-hop chain, plus the bridging ReplicaSet for a 2-hop chain (§7.2: "the relation
    contains evidence for... every owner-chain hop", stated for §7.4 but the same principle applies
    here)."""


@dataclass(frozen=True)
class OwnerChainResolutionResult:
    result: IngestionResult
    """`REJECTED_INVALID` on the first `K8S_OWNER_INVALID` finding (multiple controllers or a
    cycle) - discards everything per this codebase's "a source either fully succeeds or is
    entirely discarded" precedent, already used throughout `kubernetes_mapping.py`.
    `ACCEPTED_WITH_LIMITATIONS` if any Pod's chain didn't resolve; `ACCEPTED` otherwise."""
    resolved_chains: tuple[ResolvedOwnership, ...]
    diagnostics: tuple[IngestionDiagnostic, ...]


def _controller_references(owner_references: list[dict]) -> list[dict]:
    """§7.3: "Non-controller owner references do not select the Workload." Filters
    `MappedResource.projection["ownerReferences"]` (already validated/type-checked by
    `kubernetes_mapping._project_or_error`) down to `controller: true` entries only.
    """
    return [ref for ref in owner_references if ref["controller"]]


def _find_owner(
    ref: dict, *, namespace: str, cluster_uid: str, by_logical_id: dict[str, MappedResource]
) -> MappedResource | None:
    """§7.3: "matching group/kind/name/UID, in the same namespace and the same bundle." Recomputes
    the candidate's own logical id from the reference's claimed (apiVersion, kind, name) plus the
    referencing resource's own namespace and this source's cluster UID - the same §6 formula every
    resource's own `logical_id` already used, so a cross-namespace or bundle-absent "owner" simply
    computes a different hash and is never found. Returns `None` unless a resource with that exact
    identity exists in this bundle *and* its own captured UID equals the reference's claimed UID.
    """
    candidate_id = kubernetes_logical_resource_id(
        cluster_uid=cluster_uid,
        api_group=_api_group(ref["apiVersion"]),
        kind=ref["kind"],
        namespace=namespace,
        name=ref["name"],
    )
    candidate = by_logical_id.get(candidate_id)
    if candidate is None or candidate.captured_uid != ref["uid"]:
        return None
    return candidate


def _limitation(resource: MappedResource, message: str) -> IngestionDiagnostic:
    return IngestionDiagnostic(
        code=DiagnosticCode.K8S_OWNER_UNRESOLVED,
        message=message,
        source_pointer=resource.logical_id,
    )


def _invalid(resource: MappedResource, message: str) -> IngestionDiagnostic:
    return IngestionDiagnostic(
        code=DiagnosticCode.K8S_OWNER_INVALID, message=message, source_pointer=resource.logical_id
    )


def _rejected(diagnostic: IngestionDiagnostic) -> OwnerChainResolutionResult:
    return OwnerChainResolutionResult(
        result=IngestionResult.REJECTED_INVALID, resolved_chains=(), diagnostics=(diagnostic,)
    )


def resolve_owner_chains(
    resources: tuple[MappedResource, ...],
    *,
    cluster_uid: str,
    requires_capture_identity: bool,
) -> OwnerChainResolutionResult:
    """The one entry point `app.ingestion.kubernetes_adapter` needs. `requires_capture_identity` is
    `evidence_mode == CAPTURED_RESOURCE` - §7.2 defines `WORKLOAD_OWNS_POD` in terms of "a **captured**
    Pod's" chain, and §7.3 lists "declaration-only input" alongside missing/unresolved/unsupported
    chains as a reason for a limitation diagnostic (not a silent skip), so a `DECLARED_MANIFEST`
    source's Pods each still get one `K8S_OWNER_UNRESOLVED` rather than being passed over.
    """
    by_logical_id = {resource.logical_id: resource for resource in resources}
    pods = [resource for resource in resources if resource.resource_kind == _POD_KIND]

    diagnostics: list[IngestionDiagnostic] = []
    resolved: list[ResolvedOwnership] = []

    for pod in pods:
        owner_refs = _controller_references(pod.projection["ownerReferences"])
        if len(owner_refs) > 1:
            return _rejected(_invalid(pod, "Pod has more than one controller owner reference"))
        if not requires_capture_identity or not owner_refs:
            diagnostics.append(_limitation(pod, "no resolvable controller owner reference"))
            continue

        hop1 = _find_owner(
            owner_refs[0],
            namespace=pod.projection["namespace"],
            cluster_uid=cluster_uid,
            by_logical_id=by_logical_id,
        )
        if hop1 is None:
            diagnostics.append(
                _limitation(
                    pod,
                    "controller owner reference does not resolve to a captured resource "
                    "with a matching UID",
                )
            )
            continue
        if hop1.logical_id == pod.logical_id:
            return _rejected(_invalid(pod, "cyclic owner reference chain (self-reference)"))

        if hop1.resource_kind in _DIRECT_WORKLOAD_KINDS:
            resolved.append(
                ResolvedOwnership(
                    workload_logical_id=hop1.logical_id,
                    pod_logical_id=pod.logical_id,
                    evidence_resource_logical_ids=tuple(sorted({pod.logical_id, hop1.logical_id})),
                )
            )
            continue

        if hop1.resource_kind != _REPLICASET_KIND:
            diagnostics.append(
                _limitation(
                    pod, "controller owner reference resolves to an unsupported chain shape"
                )
            )
            continue

        # Second hop: ReplicaSet -> Deployment (§7.3's own bridge case). Never walked a third hop -
        # anything a ReplicaSet's own controller reference resolves to that isn't a Deployment is
        # already an unsupported chain shape under §7.3's own accepted-chain list.
        bridge_owner_refs = _controller_references(hop1.projection["ownerReferences"])
        if len(bridge_owner_refs) > 1:
            return _rejected(
                _invalid(hop1, "bridging ReplicaSet has more than one controller owner reference")
            )
        if not bridge_owner_refs:
            diagnostics.append(
                _limitation(pod, "bridging ReplicaSet has no controller owner reference")
            )
            continue

        hop2 = _find_owner(
            bridge_owner_refs[0],
            namespace=hop1.projection["namespace"],
            cluster_uid=cluster_uid,
            by_logical_id=by_logical_id,
        )
        if hop2 is not None and hop2.logical_id in (pod.logical_id, hop1.logical_id):
            return _rejected(_invalid(pod, "cyclic owner reference chain"))
        if hop2 is None or hop2.resource_kind != _DEPLOYMENT_KIND:
            diagnostics.append(
                _limitation(
                    pod,
                    "bridging ReplicaSet's controller owner reference does not resolve to a "
                    "Deployment",
                )
            )
            continue

        resolved.append(
            ResolvedOwnership(
                workload_logical_id=hop2.logical_id,
                pod_logical_id=pod.logical_id,
                evidence_resource_logical_ids=tuple(
                    sorted({pod.logical_id, hop1.logical_id, hop2.logical_id})
                ),
            )
        )

    result = IngestionResult.ACCEPTED_WITH_LIMITATIONS if diagnostics else IngestionResult.ACCEPTED
    return OwnerChainResolutionResult(
        result=result, resolved_chains=tuple(resolved), diagnostics=tuple(diagnostics)
    )
