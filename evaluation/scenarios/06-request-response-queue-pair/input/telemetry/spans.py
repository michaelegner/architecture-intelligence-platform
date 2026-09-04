"""Static synthetic OTLP fixture for I2 scenario 06-request-response-queue-pair: OrderService
sends request-q (received by ProductService) and ProductService sends response-q (received by
OrderService) - two independent send/receive pairs, each participant playing the opposite role on
the other queue. See evaluation/scenarios/03-async-confirmed/input/telemetry/spans.py for the
construction rationale.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

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


def _messaging_span(*, trace_id: str, span_id: str, operation_type: str, queue: str) -> Span:
    return Span(
        trace_id=bytes.fromhex(trace_id),
        span_id=bytes.fromhex(span_id),
        name=f"{queue} {operation_type}",
        kind=Span.SPAN_KIND_PRODUCER if operation_type == "send" else Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=_BASE_UNIX_NANO,
        end_time_unix_nano=_BASE_UNIX_NANO + 10_000_000,
        attributes=[
            _kv("messaging.operation.type", operation_type),
            _kv("messaging.destination.name", queue),
        ],
    )


def build_export_request() -> bytes:
    request_send = _messaging_span(
        trace_id="cbf92f3577b34da6a3ce929d0e0e473e",
        span_id="e1ad6b7169203371",
        operation_type="send",
        queue="request-q",
    )
    request_receive = _messaging_span(
        trace_id="dbf92f3577b34da6a3ce929d0e0e473f",
        span_id="51f067aa0ba902f7",
        operation_type="receive",
        queue="request-q",
    )
    response_send = _messaging_span(
        trace_id="ecf92f3577b34da6a3ce929d0e0e4740",
        span_id="f1ad6b7169203381",
        operation_type="send",
        queue="response-q",
    )
    response_receive = _messaging_span(
        trace_id="fcf92f3577b34da6a3ce929d0e0e4741",
        span_id="61f067aa0ba90207",
        operation_type="receive",
        queue="response-q",
    )

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=_resource("OrderService"), scope_spans=[ScopeSpans(spans=[request_send])]
            ),
            ResourceSpans(
                resource=_resource("ProductService"),
                scope_spans=[ScopeSpans(spans=[request_receive])],
            ),
            ResourceSpans(
                resource=_resource("ProductService"),
                scope_spans=[ScopeSpans(spans=[response_send])],
            ),
            ResourceSpans(
                resource=_resource("OrderService"),
                scope_spans=[ScopeSpans(spans=[response_receive])],
            ),
        ]
    )
    return request.SerializeToString()
