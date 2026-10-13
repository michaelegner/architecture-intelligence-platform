"""Round 4 probe: Sokol111 source-derived spans -> real AIP decode + adapt. Run: uv run python -I <this>."""

import sys
from datetime import UTC, datetime

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue

from app.telemetry.adapter import adapt
from app.telemetry.otlp_receiver import decode_export_request
from app.telemetry.pubsub_resolver import DeclaredTopicCandidate
from app.telemetry.service_resolver import DeclaredServiceCandidate

DEST_KEY = sys.argv[1]  # messaging.destination (as emitted) | messaging.destination.name (control)
WITH_OP = len(sys.argv) > 2 and sys.argv[2] == "op"  # add messaging.operation.type (control)
TOPIC = "catalog.product.events"
SVCS = ["ecommerce-catalog-service", "ecommerce-product-query-service", "ecommerce-image-service"]


def kv(k, v):
    return KeyValue(key=k, value=AnyValue(string_value=v))


def span(rs, name, kind, trace, sid, attrs, parent=b""):
    s = rs.scope_spans.add().spans.add()
    s.name, s.kind = name, kind
    s.trace_id, s.span_id, s.parent_span_id = bytes.fromhex(trace), bytes.fromhex(sid), parent
    t = int(datetime(2026, 10, 13, 12, tzinfo=UTC).timestamp() * 1e9)
    s.start_time_unix_nano, s.end_time_unix_nano = t, t + 1_000_000
    s.attributes.extend(kv(k, v) for k, v in attrs.items())


req = ExportTraceServiceRequest()


def res(svc):
    r = req.resource_spans.add()
    r.resource.attributes.extend(
        [
            kv("service.name", svc),
            kv("service.version", "frozen"),
            kv("deployment.environment.name", "local"),
        ]
    )
    return r


tr = "11" * 16
# kind: PRODUCER=4, CONSUMER=5 (OTLP). Attributes exactly as emitted by ecommerce-commons v0.8.16.
span(
    res(SVCS[0]),
    "kafka.produce",
    4,
    tr,
    "a1" * 8,
    {
        "messaging.system": "kafka",
        DEST_KEY: TOPIC,
        "messaging.message.id": "m1",
        **({"messaging.operation.type": "send"} if WITH_OP else {}),
    },
)
for i, svc in enumerate(SVCS[1:]):
    span(
        res(svc),
        "kafka.consume",
        5,
        tr,
        f"b{i}" * 8,
        {
            "messaging.system": "kafka",
            DEST_KEY: TOPIC,
            "messaging.partition": "0",
            **({"messaging.operation.type": "process"} if WITH_OP else {}),
        },
        parent=bytes.fromhex("a1" * 8),
    )
spans = decode_export_request(req.SerializeToString())
cands = [DeclaredServiceCandidate(id=f"svc:{n}", name=n, namespace=None) for n in SVCS]
batch = adapt(
    spans,
    service_candidates=cands,
    operation_candidates=[],
    queue_candidates=[],
    service_aliases={},
    queue_aliases={},
    topic_candidates=[DeclaredTopicCandidate(id="topic:t", name=TOPIC, namespace=None)],
)
print(f"VARIANT dest_key={DEST_KEY} operation_type={WITH_OP}")
print("facts", batch.facts)
print("entities", batch.entities)
print("unresolved", [(u.trace_id[:4], u.reason) for u in batch.unresolved])
