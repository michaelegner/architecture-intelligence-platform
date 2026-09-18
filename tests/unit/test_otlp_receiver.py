import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from app.telemetry.otlp_receiver import OtlpDecodeError, _resource_identity, decode_export_request


def _kv(key: str, **value_kwargs) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(**value_kwargs))


def _resource(**string_attrs: str) -> Resource:
    return Resource(attributes=[_kv(k, string_value=v) for k, v in string_attrs.items()])


def _span(**kwargs) -> Span:
    kwargs.setdefault("trace_id", bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736"))
    kwargs.setdefault("span_id", bytes.fromhex("b7ad6b7169203331"))
    kwargs.setdefault("name", "GET /products/{id}")
    kwargs.setdefault("kind", Span.SPAN_KIND_CLIENT)
    kwargs.setdefault("start_time_unix_nano", 1_700_000_000_000_000_000)
    kwargs.setdefault("end_time_unix_nano", 1_700_000_000_100_000_000)
    return Span(**kwargs)


def _request(*resource_spans: ResourceSpans) -> bytes:
    return ExportTraceServiceRequest(resource_spans=list(resource_spans)).SerializeToString()


def _one_span_batch(resource: Resource, span: Span) -> bytes:
    return _request(ResourceSpans(resource=resource, scope_spans=[ScopeSpans(spans=[span])]))


# --- resource extraction ------------------------------------------------------------------------


def test_full_resource_identity_is_extracted():
    resource = _resource(
        **{
            "service.name": "OrderService",
            "service.namespace": "commerce",
            "service.version": "1.2.3",
            "service.instance.id": "pod-abc",
            "deployment.environment.name": "production",
        }
    )
    [span] = decode_export_request(_one_span_batch(resource, _span()))
    assert span.service_name == "OrderService"
    assert span.service_namespace == "commerce"
    assert span.service_version == "1.2.3"
    assert span.service_instance_id == "pod-abc"
    assert span.environment == "production"


def test_optional_resource_fields_default_to_none_when_absent():
    resource = _resource(**{"service.name": "OrderService"})
    [span] = decode_export_request(_one_span_batch(resource, _span()))
    assert span.service_namespace is None
    assert span.service_version is None
    assert span.service_instance_id is None
    assert span.environment is None
    assert span.k8s_pod_uid is None
    assert span.k8s_pod_name is None
    assert span.k8s_namespace_name is None
    assert span.k8s_cluster_uid is None
    assert span.k8s_deployment_name is None
    assert span.k8s_statefulset_name is None
    assert span.k8s_daemonset_name is None


def test_full_k8s_resource_identity_is_extracted():
    resource = _resource(
        **{
            "service.name": "OrderService",
            "deployment.environment.name": "production",
            "k8s.pod.uid": "9f86d081-uid",
            "k8s.pod.name": "order-service-7d8f-abcde",
            "k8s.namespace.name": "commerce",
            "k8s.cluster.uid": "cluster-uid-1",
            "k8s.deployment.name": "order-service",
            "k8s.statefulset.name": "order-service-sts",
            "k8s.daemonset.name": "order-service-ds",
        }
    )
    [span] = decode_export_request(_one_span_batch(resource, _span()))
    assert span.k8s_pod_uid == "9f86d081-uid"
    assert span.k8s_pod_name == "order-service-7d8f-abcde"
    assert span.k8s_namespace_name == "commerce"
    assert span.k8s_cluster_uid == "cluster-uid-1"
    assert span.k8s_deployment_name == "order-service"
    assert span.k8s_statefulset_name == "order-service-sts"
    assert span.k8s_daemonset_name == "order-service-ds"


def test_out_of_allowlist_k8s_attributes_are_never_retained():
    # Asserting against RuntimeSpan's own fields (as a prior version of this test did) can never
    # catch a regression here: RuntimeSpan has no model_config, so Pydantic's default
    # extra="ignore" would silently discard a leaked key regardless of what _resource_identity()
    # returns - the only place this can be meaningfully tested is _resource_identity()'s raw
    # output dict itself, before it ever reaches RuntimeSpan construction.
    resource = _resource(
        **{
            "service.name": "OrderService",
            "k8s.pod.uid": "9f86d081-uid",
            "k8s.pod.label.app": "order-service",
            "k8s.pod.ip": "10.0.0.5",
        }
    )
    identity = _resource_identity(resource)
    assert identity["k8s_pod_uid"] == "9f86d081-uid"
    assert set(identity.keys()) == {
        "service_name",
        "service_namespace",
        "service_version",
        "service_instance_id",
        "environment",
        "k8s_pod_uid",
        "k8s_pod_name",
        "k8s_namespace_name",
        "k8s_cluster_uid",
        "k8s_deployment_name",
        "k8s_statefulset_name",
        "k8s_daemonset_name",
    }


def test_multiple_resource_spans_blocks_do_not_cross_contaminate():
    resource_a = _resource(
        **{"service.name": "OrderService", "deployment.environment.name": "prod"}
    )
    resource_b = _resource(
        **{"service.name": "PaymentService", "deployment.environment.name": "staging"}
    )
    raw = _request(
        ResourceSpans(resource=resource_a, scope_spans=[ScopeSpans(spans=[_span(name="a")])]),
        ResourceSpans(resource=resource_b, scope_spans=[ScopeSpans(spans=[_span(name="b")])]),
    )
    spans = decode_export_request(raw)
    by_name = {s.span_name: s for s in spans}
    assert by_name["a"].service_name == "OrderService"
    assert by_name["a"].environment == "prod"
    assert by_name["b"].service_name == "PaymentService"
    assert by_name["b"].environment == "staging"


def test_resource_spans_without_service_name_are_skipped_not_erroring():
    good = _resource(**{"service.name": "OrderService"})
    bad = _resource(**{"deployment.environment.name": "production"})  # no service.name
    raw = _request(
        ResourceSpans(resource=bad, scope_spans=[ScopeSpans(spans=[_span(name="dropped")])]),
        ResourceSpans(resource=good, scope_spans=[ScopeSpans(spans=[_span(name="kept")])]),
    )
    spans = decode_export_request(raw)
    assert [s.span_name for s in spans] == ["kept"]


# --- span extraction -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,expected",
    [
        (Span.SPAN_KIND_UNSPECIFIED, "UNSPECIFIED"),
        (Span.SPAN_KIND_INTERNAL, "INTERNAL"),
        (Span.SPAN_KIND_SERVER, "SERVER"),
        (Span.SPAN_KIND_CLIENT, "CLIENT"),
        (Span.SPAN_KIND_PRODUCER, "PRODUCER"),
        (Span.SPAN_KIND_CONSUMER, "CONSUMER"),
    ],
)
def test_span_kind_is_mapped_to_a_friendly_name(kind, expected):
    resource = _resource(**{"service.name": "OrderService"})
    [span] = decode_export_request(_one_span_batch(resource, _span(kind=kind)))
    assert span.span_kind == expected


def test_trace_and_span_id_are_hex_encoded():
    resource = _resource(**{"service.name": "OrderService"})
    raw_span = _span(
        trace_id=bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736"),
        span_id=bytes.fromhex("b7ad6b7169203331"),
    )
    [span] = decode_export_request(_one_span_batch(resource, raw_span))
    assert span.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span.span_id == "b7ad6b7169203331"


def test_root_span_parent_span_id_is_none():
    resource = _resource(**{"service.name": "OrderService"})
    [span] = decode_export_request(_one_span_batch(resource, _span()))  # no parent_span_id set
    assert span.parent_span_id is None


def test_child_span_parent_span_id_is_hex_string():
    resource = _resource(**{"service.name": "OrderService"})
    raw_span = _span(parent_span_id=bytes.fromhex("00f067aa0ba902b7"))
    [span] = decode_export_request(_one_span_batch(resource, raw_span))
    assert span.parent_span_id == "00f067aa0ba902b7"


def test_scalar_attributes_are_decoded():
    resource = _resource(**{"service.name": "OrderService"})
    raw_span = _span(
        attributes=[
            _kv("http.route", string_value="/products/{id}"),
            _kv("http.status_ok", bool_value=True),
            _kv("http.status_code", int_value=200),
            _kv("http.duration_ms", double_value=12.5),
        ]
    )
    [span] = decode_export_request(_one_span_batch(resource, raw_span))
    assert span.attributes == {
        "http.route": "/products/{id}",
        "http.status_ok": True,
        "http.status_code": 200,
        "http.duration_ms": 12.5,
    }


def test_start_and_end_time_are_converted_to_utc_datetime():
    resource = _resource(**{"service.name": "OrderService"})
    raw_span = _span(
        start_time_unix_nano=1_700_000_000_000_000_000, end_time_unix_nano=1_700_000_000_100_000_000
    )
    [span] = decode_export_request(_one_span_batch(resource, raw_span))
    assert span.end_time > span.start_time
    assert span.start_time.tzinfo is not None


# --- malformed payload / empty batch --------------------------------------------------------------


def test_malformed_payload_raises_otlp_decode_error():
    with pytest.raises(OtlpDecodeError, match="malformed OTLP trace payload"):
        decode_export_request(b"this is not a valid protobuf message at all \x00\xff\x01")


def test_empty_batch_returns_empty_list():
    assert decode_export_request(_request()) == []
