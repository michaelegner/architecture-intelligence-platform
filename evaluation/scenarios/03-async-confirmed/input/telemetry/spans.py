"""Static synthetic OTLP fixture for I1 scenario 03-async-confirmed: an OrderService producer span
and an InventoryService consumer span for `order-events-q`.

Unlike the REST scenarios, messaging observation (app.telemetry.adapter.correlate_queue_observations)
needs no CLIENT/SERVER correlation - each span is an independent SENDS/RECEIVES_FROM observation,
classified purely off `messaging.operation.type` + `messaging.destination.name`, so environment must
be set on both resources (not just one, unlike the HTTP CALLS path).
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("5bf92f3577b34da6a3ce929d0e0e4737")
_PRODUCER_SPAN_ID = bytes.fromhex("a7ad6b7169203331")
_CONSUMER_SPAN_ID = bytes.fromhex("10f067aa0ba902b7")

_QUEUE = "order-events-q"


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
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_000_010_000_000,
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
        start_time_unix_nano=1_700_000_000_020_000_000,
        end_time_unix_nano=1_700_000_000_030_000_000,
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
                resource=_resource("InventoryService"),
                scope_spans=[ScopeSpans(spans=[consumer_span])],
            ),
        ]
    )
    return request.SerializeToString()
