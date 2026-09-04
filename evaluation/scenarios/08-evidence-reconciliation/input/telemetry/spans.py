"""Static synthetic OTLP fixture for I3 scenario 08-evidence-reconciliation: the same OrderService
CLIENT / ProductService SERVER pair as scenario 01-rest-confirmed for `GET /products/{id}`,
timestamped inside this scenario's selected observation window (2026-08-01T10:00:00Z..11:00:00Z)
so the relation is CONFIRMED before the reconciliation re-import strips its DECLARED evidence -
see expected.yaml and evaluation/runner.py's apply_reconciliation.
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

# Within this scenario's expected.yaml observation.window (2026-08-01T10:00:00Z..11:00:00Z).
_BASE_UNIX_NANO = 1_785_580_200_000_000_000  # 2026-08-01T10:30:00Z


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
