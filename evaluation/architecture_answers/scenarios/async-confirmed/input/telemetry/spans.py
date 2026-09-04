"""Static synthetic OTLP fixture: an OrderService producer span and a PaymentService consumer span
for `payment-q`, matching this scenario's declared SENDS/RECEIVES_FROM exactly - both declared and
observed evidence exist -> CONFIRMED.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a")
_PRODUCER_SPAN_ID = bytes.fromhex("3a3a3a3a3a3a3a3a")
_CONSUMER_SPAN_ID = bytes.fromhex("4a4a4a4a4a4a4a4a")

_QUEUE = "payment-q"

# 2026-08-26T12:00:00Z - inside this scenario's request.yaml window.
_BASE_UNIX_NANO = 1_787_745_600_000_000_000


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
    producer_span = Span(
        trace_id=_TRACE_ID,
        span_id=_PRODUCER_SPAN_ID,
        name=f"{_QUEUE} send",
        kind=Span.SPAN_KIND_PRODUCER,
        start_time_unix_nano=_BASE_UNIX_NANO,
        end_time_unix_nano=_BASE_UNIX_NANO + 10_000_000,
        attributes=[
            _kv("messaging.operation.type", "send"),
            _kv("messaging.destination.name", _QUEUE),
        ],
    )
    consumer_span = Span(
        trace_id=_TRACE_ID,
        span_id=_CONSUMER_SPAN_ID,
        name=f"{_QUEUE} receive",
        kind=Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=_BASE_UNIX_NANO + 20_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 30_000_000,
        attributes=[
            _kv("messaging.operation.type", "receive"),
            _kv("messaging.destination.name", _QUEUE),
        ],
    )

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=_resource("OrderService"),
                scope_spans=[ScopeSpans(spans=[producer_span])],
            ),
            ResourceSpans(
                resource=_resource("PaymentService"),
                scope_spans=[ScopeSpans(spans=[consumer_span])],
            ),
        ]
    )
    return request.SerializeToString()
