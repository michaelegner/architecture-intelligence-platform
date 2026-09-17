"""I2 Draft 0.2 §7.2 (`WORKLOAD_OWNS_POD` claim) and §7.3 ("Workload owner chain") - v0.5.0 I2 §12
slice 4a: resolves each admitted Pod's controller-owner chain to a supported Workload. Pure logic,
no Neo4j and no `Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_mapping`'s
own "sources layer = pure" discipline. `app.ingestion.kubernetes_adapter` is the caller: it turns
`ResolvedOwnership` results into `InfrastructureClaim`/evidence, minting any evidence a resolved
chain's own participants still need.

§7.3's three accepted chains are Pod->StatefulSet, Pod->DaemonSet, and Pod->ReplicaSet->Deployment,
but §7.3 also separately requires detecting "cyclic references" as a *distinct*, source-rejecting
outcome from an ordinary "unsupported chain" limitation (review round, PR #202: an earlier version
of this module stopped following references after two hops, so a longer cycle - e.g.
Pod->ReplicaSet A->ReplicaSet B->ReplicaSet A - was misclassified as merely unsupported). This
module therefore follows the *whole* reachable controller-reference chain with a visited-set,
independent of hop count, and only classifies the terminal shape once it is certain no cycle exists
- termination is guaranteed by the visited-set itself (a bundle has finitely many resources), not by
an artificial hop bound.
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
    """`REJECTED_INVALID` on the first `K8S_OWNER_INVALID` finding (multiple controllers anywhere
    in a reachable chain, or a cycle) - discards everything per this codebase's "a source either
    fully succeeds or is entirely discarded" precedent, already used throughout
    `kubernetes_mapping.py`. `ACCEPTED_WITH_LIMITATIONS` if any Pod's chain didn't resolve;
    `ACCEPTED` otherwise."""
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


def _resource_pointer(resource: MappedResource) -> str:
    """§10: diagnostics carry "source/resource IDs where safely known, source pointers[...]" - not
    the resource's own logical id hash alone (a real gap found in review: an operator couldn't trace
    an unresolved/invalid owner-chain finding back to its contributing YAML file). Mirrors
    `kubernetes_mapping._validation_error`'s own pointer shape, joining every contributing file (a
    resource can have more than one after an identical-duplicate merge) so none are lost.
    """
    projection = resource.projection
    return (
        f"{','.join(resource.source_pointers)}:{projection['apiVersion']}/{resource.resource_kind}"
        f"/{projection['namespace']}/{projection['name']}"
    )


def _limitation(resource: MappedResource, message: str) -> IngestionDiagnostic:
    return IngestionDiagnostic(
        code=DiagnosticCode.K8S_OWNER_UNRESOLVED,
        message=message,
        source_pointer=_resource_pointer(resource),
    )


def _invalid(resource: MappedResource, message: str) -> IngestionDiagnostic:
    return IngestionDiagnostic(
        code=DiagnosticCode.K8S_OWNER_INVALID,
        message=message,
        source_pointer=_resource_pointer(resource),
    )


def _rejected(diagnostic: IngestionDiagnostic) -> OwnerChainResolutionResult:
    return OwnerChainResolutionResult(
        result=IngestionResult.REJECTED_INVALID, resolved_chains=(), diagnostics=(diagnostic,)
    )


@dataclass(frozen=True)
class _MultipleControllers:
    offender: MappedResource


@dataclass(frozen=True)
class _Cycle:
    pass


@dataclass(frozen=True)
class _Path:
    resources: tuple[MappedResource, ...]
    """The pod (`resources[0]`) followed by every resource its controller-reference chain reaches,
    in order, up to (but not including) the point where it can no longer continue - either no
    further controller reference exists, or the next one doesn't resolve to a real resource with a
    matching captured UID. Never contains a cycle - `_walk_owner_chain` returns `_Cycle` instead."""


def _walk_owner_chain(
    pod: MappedResource, *, cluster_uid: str, by_logical_id: dict[str, MappedResource]
) -> _MultipleControllers | _Cycle | _Path:
    """Follows the pod's controller-reference chain as far as it reaches, checking every visited
    resource - not only the first two hops - for multiple controllers or a repeat visit (a cycle).
    Termination is guaranteed by the visited-set: each iteration either stops or adds one new
    resource to it, and a bundle has finitely many resources.
    """
    visited_ids = {pod.logical_id}
    path = [pod]
    current = pod
    while True:
        owner_refs = _controller_references(current.projection["ownerReferences"])
        if len(owner_refs) > 1:
            return _MultipleControllers(current)
        if not owner_refs:
            return _Path(tuple(path))
        candidate = _find_owner(
            owner_refs[0],
            namespace=current.projection["namespace"],
            cluster_uid=cluster_uid,
            by_logical_id=by_logical_id,
        )
        if candidate is None:
            return _Path(tuple(path))
        if candidate.logical_id in visited_ids:
            return _Cycle()
        visited_ids.add(candidate.logical_id)
        path.append(candidate)
        current = candidate


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
        if not requires_capture_identity:
            diagnostics.append(_limitation(pod, "declaration-only input cannot resolve ownership"))
            continue

        walked = _walk_owner_chain(pod, cluster_uid=cluster_uid, by_logical_id=by_logical_id)
        if isinstance(walked, _MultipleControllers):
            return _rejected(
                _invalid(walked.offender, "resource has more than one controller owner reference")
            )
        if isinstance(walked, _Cycle):
            return _rejected(_invalid(pod, "cyclic owner reference chain"))

        path = walked.resources
        if len(path) == 2 and path[1].resource_kind in _DIRECT_WORKLOAD_KINDS:
            resolved.append(
                ResolvedOwnership(
                    workload_logical_id=path[1].logical_id,
                    pod_logical_id=pod.logical_id,
                    evidence_resource_logical_ids=tuple(
                        sorted(resource.logical_id for resource in path)
                    ),
                )
            )
        elif (
            len(path) == 3
            and path[1].resource_kind == _REPLICASET_KIND
            and path[2].resource_kind == _DEPLOYMENT_KIND
        ):
            resolved.append(
                ResolvedOwnership(
                    workload_logical_id=path[2].logical_id,
                    pod_logical_id=pod.logical_id,
                    evidence_resource_logical_ids=tuple(
                        sorted(resource.logical_id for resource in path)
                    ),
                )
            )
        else:
            diagnostics.append(
                _limitation(
                    pod, "controller owner reference chain does not resolve to a supported Workload"
                )
            )

    result = IngestionResult.ACCEPTED_WITH_LIMITATIONS if diagnostics else IngestionResult.ACCEPTED
    return OwnerChainResolutionResult(
        result=result, resolved_chains=tuple(resolved), diagnostics=tuple(diagnostics)
    )
