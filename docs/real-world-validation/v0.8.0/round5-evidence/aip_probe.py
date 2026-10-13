"""Round 5 probe: source-derived RabbitMQ span profiles -> real AIP decode + adapt.
Run from the AIP repo root: PYTHONPATH=$PWD uv run python round5_probe.py"""
from datetime import UTC, datetime
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from app.telemetry.adapter import adapt
from app.telemetry.otlp_receiver import decode_export_request
from app.telemetry.pubsub_resolver import DeclaredTopicCandidate
from app.telemetry.queue_resolver import DeclaredQueueCandidate
from app.telemetry.service_resolver import DeclaredServiceCandidate

EVENT = "OrderStatusChangedToPaidIntegrationEvent"
# (profile, producer service, consumer service, producer attrs, consumer attrs). OTLP kind CLIENT=3 for both
# sides: both eShop and daonhan start their messaging activities with ActivityKind.Client.
PROFILES = {
    # dotnet/eShop src/EventBusRabbitMQ/RabbitMQEventBus.cs SetActivityContext (publish/receive)
    "eshop": ("ordering-api", "catalog-api", {
        "messaging.system": "rabbitmq", "messaging.destination_kind": "queue",
        "messaging.operation": "{op}", "messaging.destination.name": EVENT, "messaging.rabbitmq.routing_key": EVENT}),
    # daonhan shared-libs ECommerce.Shared.RabbitMq (OpenTelemetryMessagingConventions)
    "daonhan": ("order-microservice", "inventory-microservice", {
        "messaging.system": "rabbitmq", "messaging.operation.name": "{op}", "messaging.destination.name": EVENT}),
}

def kv(k, v):
    return KeyValue(key=k, value=AnyValue(string_value=v))

def build(profile, conformant):
    prod, cons, attrs = PROFILES[profile]
    req = ExportTraceServiceRequest()
    t = int(datetime(2026, 10, 13, 12, tzinfo=UTC).timestamp() * 1e9)
    for i, (svc, op) in enumerate([(prod, "publish"), (cons, "receive")]):
        r = req.resource_spans.add()
        r.resource.attributes.extend([kv("service.name", svc), kv("deployment.environment.name", "local")])
        s = r.scope_spans.add().spans.add()
        s.name, s.kind = f"{EVENT} {op}", 3
        s.trace_id, s.span_id = bytes.fromhex("22" * 16), bytes.fromhex(f"c{i}" * 8)
        if i:
            s.parent_span_id = bytes.fromhex("c0" * 8)
        s.start_time_unix_nano, s.end_time_unix_nano = t, t + 1_000_000
        s.attributes.extend(kv(k, v.replace("{op}", op)) for k, v in attrs.items())
        if conformant:  # control: add the one key AIP recognises, nothing else
            s.attributes.append(kv("messaging.operation.type", "send" if op == "publish" else "receive"))
    return decode_export_request(req.SerializeToString()), (prod, cons)

for profile, conformant in [(p, c) for p in PROFILES for c in (False, True)]:
    spans, svcs = build(profile, conformant)
    cands = [DeclaredServiceCandidate(id=f"svc:{n}", name=n, namespace=None) for n in svcs]
    for declared in ("none", "topic", "queue"):
        batch = adapt(spans, service_candidates=cands, operation_candidates=[], service_aliases={}, queue_aliases={},
                      queue_candidates=[DeclaredQueueCandidate(id="queue:q", name=EVENT, namespace=None)] if declared == "queue" else [],
                      topic_candidates=[DeclaredTopicCandidate(id="topic:t", name=EVENT, namespace=None)] if declared == "topic" else [])
        print(f"{profile:8} +operation.type={conformant!s:5} declared={declared:6} facts={[(f.subject_id, f.relation_type, f.object_id) for f in batch.facts]} "
              f"unresolved={sorted(u.reason for u in batch.unresolved)}")
