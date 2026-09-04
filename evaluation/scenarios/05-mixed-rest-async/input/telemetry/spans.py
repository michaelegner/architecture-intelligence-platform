"""Static synthetic OTLP fixture for I2 scenario 05-mixed-rest-async: OrderService calls
ProductService's GET /products/{id} (HTTP) AND sends order-status-q, received by ProductService
(messaging) - proving both interaction modes are preserved as distinct canonical relation types
between the same service pair. See evaluation/scenarios/01-rest-confirmed/input/telemetry/spans.py
and .../03-async-confirmed/input/telemetry/spans.py for the construction rationale.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_METHOD = "GET"
_ROUTE = "/products/{id}"
_QUEUE = "order-status-q"

# Within this scenario's expected.yaml observation.window (2026-08-01T10:00:00Z..11:00:00Z) - see
# 01-rest-confirmed/input/telemetry/spans.py for why this matters.
_BASE_UNIX_NANO = 1_785_580_200_000_000_000  # 2026-08-01T10:30:00Z


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def build_export_request() -> bytes:
    client_span = Span(
        trace_id=bytes.fromhex("9bf92f3577b34da6a3ce929d0e0e473b"),
        span_id=bytes.fromhex("c1ad6b7169203351"),
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_CLIENT,
        start_time_unix_nano=_BASE_UNIX_NANO,
        end_time_unix_nano=_BASE_UNIX_NANO + 50_000_000,
    )
    server_span = Span(
        trace_id=bytes.fromhex("9bf92f3577b34da6a3ce929d0e0e473b"),
        span_id=bytes.fromhex("31f067aa0ba902d7"),
        parent_span_id=bytes.fromhex("c1ad6b7169203351"),
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_SERVER,
        start_time_unix_nano=_BASE_UNIX_NANO + 10_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 40_000_000,
        attributes=[
            _kv("http.request.method", _METHOD),
            _kv("http.route", _ROUTE),
        ],
    )
    send_span = Span(
        trace_id=bytes.fromhex("abf92f3577b34da6a3ce929d0e0e473c"),
        span_id=bytes.fromhex("d1ad6b7169203361"),
        name=f"{_QUEUE} send",
        kind=Span.SPAN_KIND_PRODUCER,
        start_time_unix_nano=_BASE_UNIX_NANO + 60_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 70_000_000,
        attributes=[
            _kv("messaging.operation.type", "send"),
            _kv("messaging.destination.name", _QUEUE),
        ],
    )
    receive_span = Span(
        trace_id=bytes.fromhex("bbf92f3577b34da6a3ce929d0e0e473d"),
        span_id=bytes.fromhex("41f067aa0ba902e7"),
        name=f"{_QUEUE} receive",
        kind=Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=_BASE_UNIX_NANO + 80_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 90_000_000,
        attributes=[
            _kv("messaging.operation.type", "receive"),
            _kv("messaging.destination.name", _QUEUE),
        ],
    )

    order_resource = Resource(
        attributes=[
            _kv("service.name", "OrderService"),
        ]
    )
    order_resource_with_env = Resource(
        attributes=[
            _kv("service.name", "OrderService"),
            _kv("deployment.environment.name", "test"),
        ]
    )
    product_resource = Resource(
        attributes=[
            _kv("service.name", "ProductService"),
            _kv("deployment.environment.name", "test"),
        ]
    )

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(resource=order_resource, scope_spans=[ScopeSpans(spans=[client_span])]),
            ResourceSpans(resource=product_resource, scope_spans=[ScopeSpans(spans=[server_span])]),
            ResourceSpans(
                resource=order_resource_with_env, scope_spans=[ScopeSpans(spans=[send_span])]
            ),
            ResourceSpans(
                resource=product_resource, scope_spans=[ScopeSpans(spans=[receive_span])]
            ),
        ]
    )
    return request.SerializeToString()
