"""Derived synthetic OTLP fixture (I3 spec section 40) reproducing exactly the three
`declared: true, observed: true` CALLS facts already recorded in the frozen
docs/real-world-validation/cross-system/artifacts/quarkus-actual.yaml (git blob
656446cd79c4cefec8f1ac0124fbb6b34e993704, cited by I3 spec section 37): rest-fights calling
rest-heroes GET /api/heroes/random, rest-narration POST /api/narration, and rest-villains GET
/api/villains/random. Nothing invented and no unresolved/unsupported construct upgraded - this
scenario's `input/declarations/` are the real system's own frozen OpenAPI/Architecture-Manifest
files (see SOURCE.md), and this file only supplies the matching *observed* half already known to
be true. Mirrors sync-confirmed/input/telemetry/spans.py's CLIENT/SERVER pattern, one pair per
CALLS relation rather than one.
"""

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

# 2026-08-26T12:00:00Z - inside this scenario's request.yaml window (2026-08-26T00:00:00Z..
# 2026-08-27T00:00:00Z).
_BASE_UNIX_NANO = 1_787_745_600_000_000_000

_CALLS = (
    ("Fights API", "Hero API", "GET", "/api/heroes/random", "1a"),
    ("Fights API", "Narration API", "POST", "/api/narration", "2b"),
    ("Fights API", "Villain API", "GET", "/api/villains/random", "3c"),
)


def _kv(key: str, value: str) -> KeyValue:
    return KeyValue(key=key, value=AnyValue(string_value=value))


def build_export_request() -> bytes:
    resource_spans = []
    for index, (caller, provider, method, route, span_hex) in enumerate(_CALLS):
        trace_id = bytes.fromhex(span_hex * 16)
        client_span_id = bytes.fromhex(span_hex * 8)
        server_span_id = bytes([0xC0 + index]) * 8
        offset = index * 100_000_000
        client_span = Span(
            trace_id=trace_id,
            span_id=client_span_id,
            name=f"{method} {route}",
            kind=Span.SPAN_KIND_CLIENT,
            start_time_unix_nano=_BASE_UNIX_NANO + offset,
            end_time_unix_nano=_BASE_UNIX_NANO + offset + 50_000_000,
        )
        server_span = Span(
            trace_id=trace_id,
            span_id=server_span_id,
            parent_span_id=client_span_id,
            name=f"{method} {route}",
            kind=Span.SPAN_KIND_SERVER,
            start_time_unix_nano=_BASE_UNIX_NANO + offset + 10_000_000,
            end_time_unix_nano=_BASE_UNIX_NANO + offset + 40_000_000,
            attributes=[_kv("http.request.method", method), _kv("http.route", route)],
        )
        resource_spans.append(
            ResourceSpans(
                resource=Resource(attributes=[_kv("service.name", caller)]),
                scope_spans=[ScopeSpans(spans=[client_span])],
            )
        )
        resource_spans.append(
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        _kv("service.name", provider),
                        _kv("deployment.environment.name", "test"),
                    ]
                ),
                scope_spans=[ScopeSpans(spans=[server_span])],
            )
        )

    return ExportTraceServiceRequest(resource_spans=resource_spans).SerializeToString()
