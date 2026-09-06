"""Static synthetic OTLP fixture: OrderService CLIENT span paired with a ProductService SERVER
span for `GET /products/{id}`, matching this scenario's declared CALLS/PROVIDES exactly - both
declared and observed evidence exist -> CONFIRMED.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a")
_CLIENT_SPAN_ID = bytes.fromhex("1a1a1a1a1a1a1a1a")
_SERVER_SPAN_ID = bytes.fromhex("2a2a2a2a2a2a2a2a")

_METHOD = "GET"
_ROUTE = "/products/{id}"

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

    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(attributes=[_kv("service.name", "OrderService")]),
                scope_spans=[ScopeSpans(spans=[client_span])],
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
