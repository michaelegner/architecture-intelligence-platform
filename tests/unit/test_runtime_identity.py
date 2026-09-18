from datetime import UTC, datetime

from app.telemetry.model import RuntimeSpan
from app.telemetry.runtime_identity import extract_runtime_identity_observations

_START = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
_END = datetime(2026, 8, 26, 12, 0, 5, tzinfo=UTC)


def _span(**overrides) -> RuntimeSpan:
    defaults = {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "span_name": "GET /products/{id}",
        "span_kind": "SERVER",
        "service_name": "OrderService",
        "service_namespace": "commerce",
        "environment": "production",
        "k8s_pod_uid": "pod-uid-1",
        "start_time": _START,
        "end_time": _END,
    }
    defaults.update(overrides)
    return RuntimeSpan(**defaults)


def test_a_fully_identified_span_produces_one_observation():
    [observation] = extract_runtime_identity_observations([_span()])
    assert observation.service_name == "OrderService"
    assert observation.service_namespace == "commerce"
    assert observation.environment == "production"
    assert observation.k8s_pod_uid == "pod-uid-1"
    assert observation.first_seen == _END
    assert observation.last_seen == _END
    assert observation.observation_count == 1


def test_missing_k8s_pod_uid_produces_no_observation():
    assert extract_runtime_identity_observations([_span(k8s_pod_uid=None)]) == []


def test_missing_environment_produces_no_observation():
    assert extract_runtime_identity_observations([_span(environment=None)]) == []


def test_optional_consistency_attributes_are_carried_through():
    span = _span(
        k8s_pod_name="order-service-7d8f-abcde",
        k8s_namespace_name="commerce",
        k8s_cluster_uid="cluster-uid-1",
        k8s_deployment_name="order-service",
    )
    [observation] = extract_runtime_identity_observations([span])
    assert observation.k8s_pod_name == "order-service-7d8f-abcde"
    assert observation.k8s_namespace_name == "commerce"
    assert observation.k8s_cluster_uid == "cluster-uid-1"
    assert observation.k8s_deployment_name == "order-service"


def test_identity_excludes_trace_id():
    a = _span(trace_id="a" * 32)
    b = _span(trace_id="c" * 32)
    [obs_a] = extract_runtime_identity_observations([a])
    [obs_b] = extract_runtime_identity_observations([b])
    assert obs_a.id == obs_b.id


def test_distinct_service_names_sharing_one_pod_uid_produce_distinct_ids():
    # §10.5 sidecar case: same Pod UID, two separately-instrumented services.
    primary = _span(service_name="OrderService", k8s_pod_uid="pod-uid-1")
    sidecar = _span(service_name="OrderServiceEnvoySidecar", k8s_pod_uid="pod-uid-1")
    [obs_primary] = extract_runtime_identity_observations([primary])
    [obs_sidecar] = extract_runtime_identity_observations([sidecar])
    assert obs_primary.id != obs_sidecar.id


def test_multiple_spans_from_the_same_pod_produce_the_same_id():
    first = _span(trace_id="a" * 32, end_time=_START)
    second = _span(trace_id="b" * 32, end_time=_END)
    [obs_first, obs_second] = extract_runtime_identity_observations([first, second])
    assert obs_first.id == obs_second.id
