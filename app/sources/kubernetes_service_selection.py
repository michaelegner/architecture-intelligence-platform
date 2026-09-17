"""I2 Draft 0.2 §7.2 (`NETWORK_SERVICE_SELECTS_WORKLOAD` claim) and §7.4 ("Service selection") -
v0.5.0 I2 §12 slice 4b: matches a Service's `spec.selector` against captured Pod labels, then
groups every matching, ownership-resolved Pod by its already-resolved Workload. Pure logic, no
Neo4j and no `Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_owner_chain`'s
own "sources layer = pure" discipline. `app.ingestion.kubernetes_adapter` is the caller: it turns
`ResolvedSelection` results into an `InfrastructureClaim`, reusing evidence already minted for the
Service/Pod/Workload/bridging-ReplicaSet participants - this module mints no evidence of its own.

Unlike `kubernetes_owner_chain`'s owner-chain resolution, Service selection has no rejection
outcome at all: §10 names only `NO_QUALIFIED_POD_MATCH`, always `ACCEPTED_WITH_LIMITATIONS`.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sources.kubernetes_mapping import MappedResource
from app.sources.kubernetes_owner_chain import ResolvedOwnership
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult

_SERVICE_KIND = "Service"
_POD_KIND = "Pod"
_EXTERNAL_NAME_TYPE = "ExternalName"


@dataclass(frozen=True)
class ResolvedSelection:
    """One resolved §7.4 Service-to-Workload selection, ready for
    `app.ingestion.kubernetes_adapter` to turn into a `NETWORK_SERVICE_SELECTS_WORKLOAD` claim."""

    service_logical_id: str
    workload_logical_id: str
    evidence_resource_logical_ids: tuple[str, ...]
    """Sorted logical ids of every resource this relation's evidence must union - the Service
    itself (§7.4: "evidence for the selector"), plus every grouped Pod's own
    `ResolvedOwnership.evidence_resource_logical_ids` (the matched Pod incarnation and every
    owner-chain hop, already exactly what §7.4 asks for)."""


@dataclass(frozen=True)
class ServiceSelectionResult:
    result: IngestionResult
    """`ACCEPTED_WITH_LIMITATIONS` if any `NO_QUALIFIED_POD_MATCH` diagnostic fired; `ACCEPTED`
    otherwise. §10 names no rejection outcome for this claim kind."""
    resolved_selections: tuple[ResolvedSelection, ...]
    diagnostics: tuple[IngestionDiagnostic, ...]


def _resource_pointer(resource: MappedResource) -> str:
    """Mirrors `kubernetes_owner_chain._resource_pointer`'s own shape (§10: diagnostics carry
    source pointers, not only a resource id hash) - duplicated rather than imported since it's a
    small, self-contained formula and importing a private helper across sibling modules isn't this
    codebase's own pattern.
    """
    projection = resource.projection
    return (
        f"{','.join(resource.source_pointers)}:{projection['apiVersion']}/{resource.resource_kind}"
        f"/{projection['namespace']}/{projection['name']}"
    )


def _no_qualified_pod_match(resource: MappedResource, message: str) -> IngestionDiagnostic:
    return IngestionDiagnostic(
        code=DiagnosticCode.NO_QUALIFIED_POD_MATCH,
        message=message,
        source_pointer=_resource_pointer(resource),
    )


def _matches_selector(pod: MappedResource, selector: dict[str, str]) -> bool:
    labels = pod.projection["labels"]
    return all(labels.get(key) == value for key, value in selector.items())


def resolve_service_selections(
    resources: tuple[MappedResource, ...],
    resolved_ownerships: tuple[ResolvedOwnership, ...],
) -> ServiceSelectionResult:
    """The one entry point `app.ingestion.kubernetes_adapter` needs."""
    services = [r for r in resources if r.resource_kind == _SERVICE_KIND]
    pods = [r for r in resources if r.resource_kind == _POD_KIND]
    ownership_by_pod_id = {o.pod_logical_id: o for o in resolved_ownerships}

    diagnostics: list[IngestionDiagnostic] = []
    resolved: list[ResolvedSelection] = []

    for service in services:
        projection = service.projection
        selector = projection["selector"]
        if not selector or projection["serviceType"] == _EXTERNAL_NAME_TYPE:
            continue

        matching_pods = [
            pod
            for pod in pods
            if pod.projection["namespace"] == projection["namespace"]
            and _matches_selector(pod, selector)
        ]
        if not matching_pods:
            diagnostics.append(
                _no_qualified_pod_match(service, "no captured Pod matches this Service's selector")
            )
            continue

        ownerships_by_workload: dict[str, list[ResolvedOwnership]] = {}
        for pod in matching_pods:
            ownership = ownership_by_pod_id.get(pod.logical_id)
            if ownership is None:
                diagnostics.append(
                    _no_qualified_pod_match(
                        pod, "matching Pod's controller-owner chain did not resolve"
                    )
                )
                continue
            ownerships_by_workload.setdefault(ownership.workload_logical_id, []).append(ownership)

        for workload_logical_id in sorted(ownerships_by_workload):
            evidence_ids: set[str] = {service.logical_id}
            for ownership in ownerships_by_workload[workload_logical_id]:
                evidence_ids.update(ownership.evidence_resource_logical_ids)
            resolved.append(
                ResolvedSelection(
                    service_logical_id=service.logical_id,
                    workload_logical_id=workload_logical_id,
                    evidence_resource_logical_ids=tuple(sorted(evidence_ids)),
                )
            )

    result = IngestionResult.ACCEPTED_WITH_LIMITATIONS if diagnostics else IngestionResult.ACCEPTED
    return ServiceSelectionResult(
        result=result, resolved_selections=tuple(resolved), diagnostics=tuple(diagnostics)
    )
