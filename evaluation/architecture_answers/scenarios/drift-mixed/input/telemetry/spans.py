"""Static synthetic OTLP fixture for I3 spec section 27.4's primary drift scenario: order-service
with all three qualifications on distinct outgoing dependencies simultaneously.

    CALLS product-service GET /products/{id}     declared + observed -> CONFIRMED
    CALLS legacy-pricing-service GET /pricing     declared only       -> NOT_OBSERVED_IN_WINDOW
    SENDS audit-events-q                          observed only       -> OBSERVED_ONLY

Only the CONFIRMED and OBSERVED_ONLY legs need telemetry - legacy-pricing-service is declared-only
by design (its architecture.yaml `calls` entry, alone, is enough for NOT_OBSERVED_IN_WINDOW), and
mirrors sync-confirmed's CLIENT/SERVER pair and observed-only-undeclared's PRODUCER span exactly,
combined into one OTLP export rather than two.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b")
_CLIENT_SPAN_ID = bytes.fromhex("6b6b6b6b6b6b6b6b")
_SERVER_SPAN_ID = bytes.fromhex("7b7b7b7b7b7b7b7b")
_PRODUCER_SPAN_ID = bytes.fromhex("8b8b8b8b8b8b8b8b")

_METHOD = "GET"
_ROUTE = "/products/{id}"
_QUEUE = "audit-events-q"

# 2026-08-26T12:00:00Z - inside this scenario's request.yaml window (2026-08-26T00:00:00Z..
# 2026-08-27T00:00:00Z).
_BASE_UNIX_NANO = 1_787_745_600_000_000_000


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def build_export_request() -> bytes:
    client_span = Span(
        trace_id=_TRACE_ID,
        span_id=_CLIENT_SPAN_ID,
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_CLIENT,
        start_time_unix_nano=_BASE_UNIX_NANO,
        end_time_unix_nano=_BASE_UNIX_NANO + 50_000_000,
    )
    server_span = Span(
        trace_id=_TRACE_ID,
        span_id=_SERVER_SPAN_ID,
        parent_span_id=_CLIENT_SPAN_ID,
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_SERVER,
        start_time_unix_nano=_BASE_UNIX_NANO + 10_000_000,
        end_time_unix_nano=_BASE_UNIX_NANO + 40_000_000,
        attributes=[
            _kv("http.request.method", _METHOD),
            _kv("http.route", _ROUTE),
        ],
    )
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
                scope_spans=[ScopeSpans(spans=[client_span, producer_span])],
            ),
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        _kv("service.name", "ProductService"),
                        _kv("deployment.environment.name", "test"),
                    ]
                ),
                scope_spans=[ScopeSpans(spans=[server_span])],
            ),
        ]
    )
    return request.SerializeToString()
