"""I2 Draft 0.2 §7.2 (`INGRESS_ROUTES_TO_NETWORK_SERVICE` claim) and §7.5 ("Ingress backends") -
v0.5.0 I2 §12 slice 4c: resolves each admitted Ingress's `defaultBackend`/`rules[].http.paths[].
backend` references against admitted Service names/ports. Pure logic, no Neo4j and no
`Provenance`/evidence-id construction - mirrors `app.sources.kubernetes_service_selection`'s own
discipline, including its "no rejection outcome" shape: §10 names only `K8S_BACKEND_UNRESOLVED`,
always `ACCEPTED_WITH_LIMITATIONS`. `app.ingestion.kubernetes_adapter` is the caller: it turns
`ResolvedRoute` results into an `InfrastructureClaim`, reusing evidence already minted for the
Ingress/Service participants - this module mints no evidence of its own.

Independent of `kubernetes_owner_chain`/`kubernetes_service_selection` (slices 4a/4b) - Ingress
backend resolution only needs the Ingress/Service entities and projections slices 3a/3b already
built.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.sources.kubernetes_mapping import MappedResource
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult

_INGRESS_KIND = "Ingress"
_SERVICE_KIND = "Service"


@dataclass(frozen=True)
class ResolvedRoute:
    """One resolved §7.5 Ingress-to-Service route, ready for `app.ingestion.kubernetes_adapter` to
    turn into an `INGRESS_ROUTES_TO_NETWORK_SERVICE` claim."""

    ingress_logical_id: str
    service_logical_id: str
    evidence_resource_logical_ids: tuple[str, ...]
    """The Ingress and the Service (§7.2: "evidence retains the backend pointer and the matching
    Service port") - both resource-scoped facts already covered by each resource's own existing
    evidence, not tracked per individual backend/path."""


@dataclass(frozen=True)
class IngressBackendResolutionResult:
    result: IngestionResult
    """`ACCEPTED_WITH_LIMITATIONS` if any `K8S_BACKEND_UNRESOLVED` diagnostic fired; `ACCEPTED`
    otherwise. §10 names no rejection outcome for this claim kind."""
    resolved_routes: tuple[ResolvedRoute, ...]
    diagnostics: tuple[IngestionDiagnostic, ...]


def _resource_pointer(resource: MappedResource) -> str:
    """Mirrors `kubernetes_owner_chain._resource_pointer`/`kubernetes_service_selection._resource_
    pointer`'s own shape (§10: diagnostics carry source pointers, not only a resource id hash) -
    duplicated rather than imported since it's a small, self-contained formula.
    """
    projection = resource.projection
    return (
        f"{','.join(resource.source_pointers)}:{projection['apiVersion']}/{resource.resource_kind}"
        f"/{projection['namespace']}/{projection['name']}"
    )


def _backend_unresolved(resource: MappedResource, message: str) -> IngestionDiagnostic:
    # Review round (PR #204, 2nd pass): §10 requires diagnostics to name "the affected claim kind"
    # and "source/resource IDs where safely known" - `IngestionDiagnostic` has no dedicated field
    # for either, so both are carried in the message text, the same way every diagnostic in this
    # codebase already communicates context beyond its own typed fields. `source_pointer` keeps its
    # established file-attribution shape (matching `kubernetes_owner_chain`/`kubernetes_service_
    # selection`'s own sibling helpers) rather than being repurposed to also carry the resource id.
    return IngestionDiagnostic(
        code=DiagnosticCode.K8S_BACKEND_UNRESOLVED,
        message=(f"INGRESS_ROUTES_TO_NETWORK_SERVICE ({resource.logical_id}): {message}"),
        source_pointer=_resource_pointer(resource),
    )


def _iter_backends(ingress: MappedResource) -> list[dict]:
    projection = ingress.projection
    backends = []
    if projection["defaultBackend"] is not None:
        backends.append(projection["defaultBackend"])
    for rule in projection["rules"]:
        for path in rule["paths"]:
            if path["backend"] is not None:
                backends.append(path["backend"])
    return backends


def _matching_ports(ports: list[dict], backend: dict) -> list[dict]:
    """`kubernetes_mapping._ingress_backend_or_error` already rejects a backend port that sets
    both `name` and `number` (§5: "malformed used fields... reject the source") - by construction,
    exactly one of these is set here, never a tie-break between the two.
    """
    port_number = backend["servicePortNumber"]
    if port_number is not None:
        return [p for p in ports if p["port"] == port_number]
    return [p for p in ports if p["name"] == backend["servicePortName"]]


def resolve_ingress_backends(
    resources: tuple[MappedResource, ...],
) -> IngressBackendResolutionResult:
    """The one entry point `app.ingestion.kubernetes_adapter` needs."""
    ingresses = [r for r in resources if r.resource_kind == _INGRESS_KIND]
    services_by_namespace_and_name: dict[tuple[str, str], MappedResource] = {
        (r.projection["namespace"], r.projection["name"]): r
        for r in resources
        if r.resource_kind == _SERVICE_KIND
    }

    diagnostics: list[IngestionDiagnostic] = []
    resolved: list[ResolvedRoute] = []

    for ingress in ingresses:
        resolved_service_ids: set[str] = set()
        for backend in _iter_backends(ingress):
            if backend.get("resourceBackend"):
                diagnostics.append(
                    _backend_unresolved(ingress, "resource backends are unsupported")
                )
                continue

            service = services_by_namespace_and_name.get(
                (ingress.projection["namespace"], backend["serviceName"])
            )
            if service is None:
                diagnostics.append(
                    _backend_unresolved(
                        ingress, f"referenced Service {backend['serviceName']!r} was not found"
                    )
                )
                continue

            matches = _matching_ports(service.projection["ports"], backend)
            if len(matches) != 1:
                diagnostics.append(
                    _backend_unresolved(
                        ingress,
                        f"backend port does not match exactly one declared port on Service "
                        f"{backend['serviceName']!r} ({len(matches)} matches)",
                    )
                )
                continue

            resolved_service_ids.add(service.logical_id)

        for service_logical_id in sorted(resolved_service_ids):
            resolved.append(
                ResolvedRoute(
                    ingress_logical_id=ingress.logical_id,
                    service_logical_id=service_logical_id,
                    evidence_resource_logical_ids=(ingress.logical_id, service_logical_id),
                )
            )

    result = IngestionResult.ACCEPTED_WITH_LIMITATIONS if diagnostics else IngestionResult.ACCEPTED
    return IngressBackendResolutionResult(
        result=result, resolved_routes=tuple(resolved), diagnostics=tuple(diagnostics)
    )
