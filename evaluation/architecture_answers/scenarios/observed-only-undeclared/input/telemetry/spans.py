"""Static synthetic OTLP fixture: a producer span for `reporting-q` from a service that declares no
SENDS relation anywhere in this scenario (only billing-service's declared RECEIVES_FROM exists) -
observed evidence with no declared counterpart -> OBSERVED_ONLY. `service.name` is deliberately
already the slug form ("order-service") so the runtime-minted canonical id matches
`service:order-service` exactly, the same id this suite's other scenarios use.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a")
_PRODUCER_SPAN_ID = bytes.fromhex("5a5a5a5a5a5a5a5a")

_QUEUE = "reporting-q"

# 2026-08-26T12:00:00Z - inside this scenario's request.yaml window.
_BASE_UNIX_NANO = 1_787_745_600_000_000_000


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


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

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        _kv("service.name", "order-service"),
                        _kv("deployment.environment.name", "test"),
                    ]
                ),
                scope_spans=[ScopeSpans(spans=[producer_span])],
            ),
        ]
    )
    return request.SerializeToString()
