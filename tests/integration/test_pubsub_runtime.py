"""v0.5.0 I4 slice 3: runtime OTel qualification of already-declared Topic/Subscription topology
against real Neo4j (spec §9, §12.5, §13.2) - observed evidence attaches to the declared
PUBLISHES_TO / RECEIVES_FROM->Subscription relations; nothing Pub/Sub is ever minted, and
unmatched spans never reach the graph or the snapshot."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.telemetry.adapter import adapt
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import RuntimeSpan
from app.telemetry.pubsub_resolver import fetch_subscription_candidates, fetch_topic_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates
from tests.integration.test_pubsub_persistence import TOPIC_ID, _import, _pubsub_scene

DATABASE = "neo4j"
SPAN_TIME = datetime(2026, 9, 23, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def declared_scene(driver, tmp_path):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    _pubsub_scene(tmp_path)
    assert _import(driver, tmp_path).committed is True
    yield


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]


def _span(service: str, operation: str, *, trace: str = "a", **attributes) -> RuntimeSpan:
    return RuntimeSpan(
        trace_id=trace * 32,
        span_id="b" * 16,
        parent_span_id=None,
        span_name="orders",
        span_kind="PRODUCER" if operation == "send" else "CONSUMER",
        service_name=service,
        service_namespace=None,
        service_version=None,
        service_instance_id=None,
        environment="production",
        start_time=SPAN_TIME,
        end_time=SPAN_TIME,
        attributes={
            "messaging.system": "gcp_pubsub",
            "messaging.operation.type": operation,
            "messaging.destination.name": "orders",
            **attributes,
        },
    )


def _ingest(driver, spans):
    with driver.session(database=DATABASE) as session:
        batch = adapt(
            spans,
            service_candidates=fetch_candidates(session),
            operation_candidates=[],
            queue_candidates=fetch_queue_candidates(session),
            service_aliases={},
            queue_aliases={},
            topic_candidates=fetch_topic_candidates(session),
            subscription_candidates=fetch_subscription_candidates(session),
        )
    persist_observation_batch(driver, DATABASE, batch)
    return batch


def _pubsub_node_counts(driver):
    return (
        _count(driver, "MATCH (t:Topic) RETURN count(t) AS c"),
        _count(driver, "MATCH (s:Subscription) RETURN count(s) AS c"),
        _count(
            driver,
            "MATCH (n) WHERE (n:Topic OR n:Subscription) AND n.discovery_status IS NOT NULL "
            "RETURN count(n) AS c",
        ),
    )


def _snapshot_id(driver):
    with driver.session(database=DATABASE) as session:
        return snapshot_fingerprint(
            canonical_snapshot_state(session, coverage_qualification_enabled=True)
        )[0]


def _observed_evidence_on(driver, match: str) -> int:
    return _count(
        driver,
        f"MATCH {match} UNWIND r.evidence_ids AS eid MATCH (e:Evidence {{id: eid}}) "
        "WHERE e.evidence_type = 'OBSERVED' RETURN count(e) AS c",
    )


def test_publish_and_subscription_consumption_attach_observed_evidence_to_declared_relations(
    driver,
):
    before_nodes = _pubsub_node_counts(driver)
    batch = _ingest(
        driver,
        [
            _span("orders", "send", trace="a"),
            _span(
                "billing",
                "process",
                trace="c",
                **{"messaging.destination.subscription.name": "billing"},
            ),
        ],
    )
    assert batch.unresolved == []
    assert (
        _observed_evidence_on(
            driver,
            f"(:Service {{id: 'service:orders'}})-[r:PUBLISHES_TO]->(:Topic {{id: '{TOPIC_ID}'}})",
        )
        == 1
    )
    assert (
        _observed_evidence_on(
            driver,
            "(:Service {id: 'service:billing'})-[r:RECEIVES_FROM]->(:Subscription {name: 'billing'})",
        )
        == 1
    )
    # evidence for one Subscription never confirms its sibling
    assert (
        _observed_evidence_on(
            driver,
            "(:Service {id: 'service:shipping'})-[r:RECEIVES_FROM]->(:Subscription {name: 'shipping'})",
        )
        == 0
    )
    assert _pubsub_node_counts(driver) == before_nodes
    assert _count(driver, "MATCH (:Service)-[r:RECEIVES_FROM]->(:Topic) RETURN count(r) AS c") == 0


@pytest.mark.parametrize(
    "spans",
    [
        [_span("orders", "send", **{"messaging.destination.name": "fights"})],  # undeclared Topic
        [
            _span(
                "orders",
                "send",
                **{"messaging.destination_kind": "topic", "messaging.destination.name": "fights"},
            )
        ],
        [_span("billing", "receive")],  # consumer without a subscription name
        [_span("billing", "receive", **{"messaging.consumer.group.name": "billing"})],
        [_span("billing", "receive", **{"messaging.destination.subscription.name": "ghost"})],
        [_span("billing", "receive", **{"messaging.destination_kind": "subscription"})],
    ],
)
def test_unmatched_pubsub_spans_never_reach_the_graph_or_the_snapshot(driver, spans):
    before_nodes = _pubsub_node_counts(driver)
    before_snapshot = _snapshot_id(driver)
    before_evidence = _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c")

    batch = _ingest(driver, spans)

    assert batch.facts == []
    assert len(batch.unresolved) == len(spans)
    assert _pubsub_node_counts(driver) == before_nodes
    assert _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c") == before_evidence
    assert _snapshot_id(driver) == before_snapshot


def _otlp_payload() -> bytes:
    def kv(key, value):
        return KeyValue(key=key, value=AnyValue(string_value=value))

    resource = Resource(
        attributes=[kv("service.name", "billing"), kv("deployment.environment.name", "production")]
    )
    span = Span(
        trace_id=bytes.fromhex("4bf92f3577b34da6a3ce929d0e0e4736"),
        span_id=bytes.fromhex("00f067aa0ba902b7"),
        name="orders process",
        kind=Span.SPAN_KIND_CONSUMER,
        start_time_unix_nano=1_700_000_000_000_000_000,
        end_time_unix_nano=1_700_000_000_050_000_000,
        attributes=[
            kv("messaging.system", "servicebus"),
            kv("messaging.operation.type", "process"),
            kv("messaging.destination.name", "orders"),
            kv("messaging.destination.subscription.name", "billing"),
        ],
    )
    return ExportTraceServiceRequest(
        resource_spans=[ResourceSpans(resource=resource, scope_spans=[ScopeSpans(spans=[span])])]
    ).SerializeToString()


def test_otlp_endpoint_wires_topic_and_subscription_candidates(driver):
    app = create_app()
    app.state.driver = driver
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {"graph": {"uri": "bolt://ignored:7687", "database": DATABASE}}
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored"),
    )
    response = TestClient(app).post(
        "/v1/traces",
        content=_otlp_payload(),
        headers={"content-type": "application/x-protobuf"},
    )
    assert response.status_code == 200
    assert (
        _observed_evidence_on(
            driver,
            "(:Service {id: 'service:billing'})-[r:RECEIVES_FROM]->(:Subscription {name: 'billing'})",
        )
        == 1
    )
