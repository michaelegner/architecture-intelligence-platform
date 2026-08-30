"""Static synthetic OTLP fixture for I1 scenario 01-rest-confirmed: OrderService CLIENT span
paired with a ProductService SERVER span for `GET /products/{id}`, built the same way
tests/integration/test_telemetry_api.py builds real ExportTraceServiceRequest protobufs - this is
"the existing internal test builder that emits real OTLP structures" the I1 spec asks to prefer
(§12), just packaged as this scenario's own input artifact rather than a pytest fixture.

Environment is set only on the SERVER resource: app.telemetry.adapter.correlate_http_call_observations
always reads environment/method/route from the SERVER span, never the CLIENT span (see its own
docstring for why - the declared Operation id is minted from the provider's OpenAPI path).
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


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def build_export_request() -> bytes:
    client_span = Span(
        trace_id=_TRACE_ID,
        span_id=_CLIENT_SPAN_ID,
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_CLIENT,
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_000_050_000_000,
    )
    server_span = Span(
        trace_id=_TRACE_ID,
        span_id=_SERVER_SPAN_ID,
        parent_span_id=_CLIENT_SPAN_ID,
        name=f"{_METHOD} {_ROUTE}",
        kind=Span.SPAN_KIND_SERVER,
        start_time_unix_nano=1_700_000_000_010_000_000,
        end_time_unix_nano=1_700_000_000_040_000_000,
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
