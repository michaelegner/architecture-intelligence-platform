from app.sources.kubernetes_ingress_backend import resolve_ingress_backends
from app.sources.kubernetes_mapping import map_kubernetes_resources
from app.sources.model import DiagnosticCode, IngestionResult, KubernetesResourceEntry

_CLUSTER_UID = "independently-established-cluster-identity"
_NAMESPACE = "checkout"
_OTHER_NAMESPACE = "other"


def _entry(document: dict, *, source_pointer: str = "resources.yaml") -> KubernetesResourceEntry:
    return KubernetesResourceEntry(source_pointer=source_pointer, document=document)


def _service(name: str, *, ports: list[dict], namespace: str = _NAMESPACE) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"ports": ports},
    }


def _backend(
    service_name: str, *, port_name: str | None = None, port_number: int | None = None
) -> dict:
    port: dict = {}
    if port_name is not None:
        port["name"] = port_name
    if port_number is not None:
        port["number"] = port_number
    return {"service": {"name": service_name, "port": port}}


_RESOURCE_BACKEND = {
    "resource": {"apiGroup": "k8s.example.com", "kind": "StorageBucket", "name": "x"}
}


def _ingress(
    name: str = "ing-1",
    *,
    namespace: str = _NAMESPACE,
    default_backend: dict | None = None,
    rules: list[dict] | None = None,
) -> dict:
    spec: dict = {}
    if default_backend is not None:
        spec["defaultBackend"] = default_backend
    if rules is not None:
        spec["rules"] = rules
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": name, "namespace": namespace},
        "spec": spec,
    }


def _rule(host: str, path: str, backend: dict) -> dict:
    return {
        "host": host,
        "http": {"paths": [{"path": path, "pathType": "Prefix", "backend": backend}]},
    }


def _map(documents, *, scope_namespaces=(_NAMESPACE, _OTHER_NAMESPACE)):
    entries = tuple(_entry(doc) for doc in documents)
    result = map_kubernetes_resources(
        entries,
        cluster_uid=_CLUSTER_UID,
        requires_capture_identity=False,
        scope_namespaces=tuple(scope_namespaces),
    )
    assert result.result in (IngestionResult.ACCEPTED, IngestionResult.ACCEPTED_WITH_LIMITATIONS), (
        result.diagnostics
    )
    return result.resources


def _resolve(resources):
    return resolve_ingress_backends(resources)


# --- resolution ----------------------------------------------------------------------------


def test_numeric_port_resolves():
    svc = _service("svc-1", ports=[{"port": 80}])
    ing = _ingress(default_backend=_backend("svc-1", port_number=80))
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED
    [route] = result.resolved_routes
    assert len(route.evidence_resource_logical_ids) == 2


def test_named_port_resolves():
    svc = _service("svc-1", ports=[{"name": "http", "port": 8080}])
    ing = _ingress(default_backend=_backend("svc-1", port_name="http"))
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resolved_routes) == 1


def test_default_backend_and_rule_backend_both_resolve():
    svc = _service("svc-1", ports=[{"port": 80}])
    ing = _ingress(
        default_backend=_backend("svc-1", port_number=80),
        rules=[_rule("a.example.com", "/a", _backend("svc-1", port_number=80))],
    )
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED
    # Both backends resolve to the same Service - one merged relation, not two.
    assert len(result.resolved_routes) == 1


def test_multiple_routes_to_one_service_merge_into_one_relation():
    svc = _service("svc-1", ports=[{"port": 80}])
    ing = _ingress(
        rules=[
            _rule("a.example.com", "/a", _backend("svc-1", port_number=80)),
            _rule("b.example.com", "/b", _backend("svc-1", port_number=80)),
        ]
    )
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resolved_routes) == 1


def test_routes_to_distinct_services_yield_distinct_relations():
    svc_a = _service("svc-a", ports=[{"port": 80}])
    svc_b = _service("svc-b", ports=[{"port": 80}])
    ing = _ingress(
        rules=[
            _rule("a.example.com", "/a", _backend("svc-a", port_number=80)),
            _rule("b.example.com", "/b", _backend("svc-b", port_number=80)),
        ]
    )
    result = _resolve(_map([svc_a, svc_b, ing]))
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resolved_routes) == 2


# --- limitations -----------------------------------------------------------------------------


def test_missing_service_is_a_limitation():
    ing = _ingress(default_backend=_backend("nonexistent", port_number=80))
    result = _resolve(_map([ing]))
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_routes == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code is DiagnosticCode.K8S_BACKEND_UNRESOLVED
    # Review round (PR #204): §10 requires the affected claim kind and a real source pointer.
    assert "INGRESS_ROUTES_TO_NETWORK_SERVICE" in diagnostic.message
    assert "ing-1" in diagnostic.source_pointer


def test_missing_port_is_a_limitation():
    svc = _service("svc-1", ports=[{"port": 8080}])
    ing = _ingress(default_backend=_backend("svc-1", port_number=80))
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_routes == ()
    diagnostic = result.diagnostics[0]
    assert diagnostic.code is DiagnosticCode.K8S_BACKEND_UNRESOLVED
    assert "INGRESS_ROUTES_TO_NETWORK_SERVICE" in diagnostic.message
    assert "ing-1" in diagnostic.source_pointer


def test_ambiguous_port_match_is_a_limitation():
    svc = _service("svc-1", ports=[{"name": "a", "port": 80}, {"name": "b", "port": 80}])
    ing = _ingress(default_backend=_backend("svc-1", port_number=80))
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_routes == ()


def test_service_in_a_different_namespace_does_not_resolve():
    svc = _service("svc-1", ports=[{"port": 80}], namespace=_OTHER_NAMESPACE)
    ing = _ingress(default_backend=_backend("svc-1", port_number=80))
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert result.resolved_routes == ()
    assert result.diagnostics[0].code is DiagnosticCode.K8S_BACKEND_UNRESOLVED


def test_resource_backend_is_a_limitation_but_does_not_block_other_backends():
    svc = _service("svc-1", ports=[{"port": 80}])
    ing = _ingress(
        rules=[
            _rule("a.example.com", "/a", _RESOURCE_BACKEND),
            _rule("b.example.com", "/b", _backend("svc-1", port_number=80)),
        ]
    )
    result = _resolve(_map([svc, ing]))
    assert result.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert len(result.resolved_routes) == 1
    [diagnostic] = [
        d for d in result.diagnostics if d.code is DiagnosticCode.K8S_BACKEND_UNRESOLVED
    ]
    assert "INGRESS_ROUTES_TO_NETWORK_SERVICE" in diagnostic.message
    assert "ing-1" in diagnostic.source_pointer


def test_ambiguous_port_match_diagnostic_names_the_claim_kind_and_a_source_pointer():
    svc = _service("svc-1", ports=[{"name": "a", "port": 80}, {"name": "b", "port": 80}])
    ing = _ingress(default_backend=_backend("svc-1", port_number=80))
    result = _resolve(_map([svc, ing]))
    diagnostic = result.diagnostics[0]
    assert diagnostic.code is DiagnosticCode.K8S_BACKEND_UNRESOLVED
    assert "INGRESS_ROUTES_TO_NETWORK_SERVICE" in diagnostic.message
    assert "ing-1" in diagnostic.source_pointer
