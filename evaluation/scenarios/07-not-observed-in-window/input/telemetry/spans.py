"""Static synthetic OTLP fixture for I3 scenario 07-not-observed-in-window: the same OrderService
CLIENT / ProductService SERVER pair as scenario 01-rest-confirmed for `GET /products/{id}`, but
timestamped *before* this scenario's selected observation window
(2026-08-01T10:00:00Z..11:00:00Z) - see expected.yaml. This proves NOT_OBSERVED_IN_WINDOW is
context-qualified: an observation exists, just not in the selected window, which is a different
finding than no observation existing anywhere (I3 spec §8.4).
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

_TRACE_ID = bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736")
_CLIENT_SPAN_ID = bytes.fromhex("b7ad6b7169203331")
_SERVER_SPAN_ID = bytes.fromhex("00f067aa0ba902b7")

_METHOD = "GET"
_ROUTE = "/products/{id}"

# Outside this scenario's expected.yaml observation.window (2026-08-01T10:00:00Z..11:00:00Z) -
# deliberately one hour before it opens, so _NOT_OBSERVED_EXISTS holds for the selected window
# even though a real OBSERVED evidence record exists in the graph.
_BASE_UNIX_NANO = 1_785_576_600_000_000_000  # 2026-08-01T09:30:00Z


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
