"""Static synthetic OTLP fixture for I2 scenario 04-orphan-messaging: OrderService sends
`unused-q` (no declared/observed consumer anywhere), and InventoryService receives from
`unknown-producer-q` (no declared/observed producer anywhere). See
evaluation/scenarios/01-rest-confirmed/input/telemetry/spans.py for the construction rationale.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_PRODUCER_SPAN_ID = bytes.fromhex("b1ad6b7169203341")
_CONSUMER_SPAN_ID = bytes.fromhex("21f067aa0ba902c7")

# Within this scenario's expected.yaml observation.window (2026-08-01T10:00:00Z..11:00:00Z) - see
# 01-rest-confirmed/input/telemetry/spans.py for why this matters.
_BASE_UNIX_NANO = 1_785_580_200_000_000_000  # 2026-08-01T10:30:00Z


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def _resource(service_name: str) -> Resource:
    return Resource(
        attributes=[
            _kv("service.name", service_name),
            _kv("deployment.environment.name", "test"),
        ]
    )


def build_export_request() -> bytes:
    send_span = Span(
        trace_id=bytes.fromhex("7bf92f3577b34da6a3ce929d0e0e4739"),
        span_id=_PRODUCER_SPAN_ID,
        name="unused-q send",
        kind=Span.SPAN_KIND_PRODUCER,
        start_time_unix_nano=_BASE_UNIX_NANO,
        end_time_unix_nano=_BASE_UNIX_NANO + 10_000_000,
        attributes=[
            _kv("messaging.operation.type", "send"),
            _kv("messaging.destination.name", "unused-q"),
        ],
    )
    receive_span = Span(
        trace_id=bytes.fromhex("8bf92f3577b34da6a3ce929d0e0e473a"),
        span_id=_CONSUMER_SPAN_ID,
        name="unknown-producer-q receive",
        kind=Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=_BASE_UNIX_NANO + 20_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 30_000_000,
        attributes=[
            _kv("messaging.operation.type", "receive"),
            _kv("messaging.destination.name", "unknown-producer-q"),
        ],
    )

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=_resource("OrderService"), scope_spans=[ScopeSpans(spans=[send_span])]
            ),
            ResourceSpans(
                resource=_resource("InventoryService"),
                scope_spans=[ScopeSpans(spans=[receive_span])],
            ),
        ]
    )
    return request.SerializeToString()
