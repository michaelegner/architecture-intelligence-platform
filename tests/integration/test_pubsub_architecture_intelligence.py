"""v0.5.0 I4 slice 4: declared Topic/Subscription topology through the public Architecture
Intelligence answers against real Neo4j (spec §12.2-§12.6, §13.4) - dependency and drift claims,
Subscription routes, same-snapshot evidence drill-down, and direct-service / REST / negotiated MCP
equivalence, with zero graph writes on every read."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import jsonschema
import pytest
from mcp.server import MCPServer

from app.analysis.runtime import telemetry_coverage
from app.architecture_intelligence.contracts import (
    Coverage,
    DestinationResolution,
    EntityType,
    LimitationCode,
    Outcome,
    Producer,
    Qualification,
)
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.revision_fence import read_revision
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.sources.owner_ids import subscription_owned_id, topic_owned_id
from tests.integration.test_api_architecture_intelligence_equivalence import _client
from tests.integration.test_pubsub_persistence import (
    BROKER,
    TOPIC_ID,
    _doc,
    _import,
    _pubsub_scene,
    _write,
)
from tests.integration.test_pubsub_runtime import SPAN_TIME, _ingest, _span
from tests.support.negotiated_mcp_client import call_negotiated

DATABASE = "neo4j"
ENVIRONMENT = "production"
WINDOW_START = "2026-09-23T00:00:00.000000Z"
WINDOW_END = "2026-09-24T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "architecture_intelligence" / "v0.5"
DEPENDENCY_SCHEMA = json.loads((_SCHEMA_DIR / "architecture-answer.schema.json").read_text())
DRIFT_SCHEMA = json.loads((_SCHEMA_DIR / "drift-answer.schema.json").read_text())
EVIDENCE_SCHEMA = json.loads((_SCHEMA_DIR / "evidence-answer.schema.json").read_text())

REFUNDS_TOPIC_ID = topic_owned_id(
    stable_broker_id=BROKER, normalized_namespace_or_empty="", exact_topic_address="refunds"
)
BILLING_SUB = subscription_owned_id(
    stable_broker_id=BROKER,
    normalized_namespace_or_empty="",
    topic_id=TOPIC_ID,
    exact_subscription_name="billing",
)
SHIPPING_SUB = subscription_owned_id(
    stable_broker_id=BROKER,
    normalized_namespace_or_empty="",
    topic_id=TOPIC_ID,
    exact_subscription_name="shipping",
)


@pytest.fixture(autouse=True)
def declared_scene(driver, tmp_path):
    """The slice-2b fan-out scene (orders publishes; billing and shipping each subscribe through
    their own Subscription), plus a second `refunds` Topic that orders publishes to with no
    Subscription at all - the §12.3 Topic-fallback row."""
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    _pubsub_scene(tmp_path)
    orders = _doc("orders", publish=True)
    orders["channels"]["refunds"] = {
        "x-aip-destination-kind": "topic",
        "publish": {"message": {"$ref": "#/components/messages/OrderCreated"}},
    }
    _write(tmp_path, "orders", orders)
    assert _import(driver, tmp_path).committed is True
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request_payload(service_id: str) -> dict:
    return {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }


def _dependencies(driver, service_id: str = "service:orders"):
    return _service(driver).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(_request_payload(service_id))
    )


def _drift(driver, service_id: str = "service:orders"):
    return _service(driver).get_architecture_drift(
        ArchitectureDriftRequest.model_validate(_request_payload(service_id))
    )


def _observe_orders_publish_and_billing_consumption(driver) -> None:
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


def _routes(answer) -> list[tuple[str, str | None]]:
    return [
        (
            claim.object.id,
            claim.delivery.subscription.id if claim.delivery.subscription is not None else None,
        )
        for claim in answer.claims
    ]


def _observed_ids(driver) -> set[str]:
    with driver.session(database=DATABASE) as session:
        return {
            r["id"]
            for r in session.run("MATCH (e:Evidence {evidence_type: 'OBSERVED'}) RETURN e.id AS id")
        }


def _graph_state(driver):
    with driver.session(database=DATABASE) as session:
        return (
            read_revision(session),
            session.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        )


# --- §12.3 dependency projection ---------------------------------------------------------------


def test_declared_fanout_projects_one_routed_claim_per_subscription_and_a_topic_fallback(driver):
    answer = _dependencies(driver)
    payload = answer.model_dump(mode="json")
    jsonschema.validate(instance=payload, schema=DEPENDENCY_SCHEMA)

    assert sorted(_routes(answer)) == sorted(
        [
            ("service:billing", BILLING_SUB),
            ("service:shipping", SHIPPING_SUB),
            (REFUNDS_TOPIC_ID, None),
        ]
    )
    by_object = {claim.object.id: claim for claim in answer.claims}
    for consumer in ("service:billing", "service:shipping"):
        claim = by_object[consumer]
        assert claim.destination_resolution == DestinationResolution.RESOLVED_SERVICE
        assert claim.delivery.via.id == TOPIC_ID
        assert claim.delivery.via.type == EntityType.TOPIC
        assert claim.delivery.subscription.type == EntityType.SUBSCRIPTION
        assert claim.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
        assert claim.coverage == Coverage.NONE
        # SUBSCRIPTION_OF evidence and the consumer's RECEIVES_FROM evidence, never the publisher's
        assert claim.resolution_evidence_refs
        assert not set(claim.resolution_evidence_refs) & set(claim.evidence_refs)

    fallback = by_object[REFUNDS_TOPIC_ID]
    assert fallback.destination_resolution == DestinationResolution.DIRECT_TARGET_FALLBACK
    assert fallback.object.type == EntityType.TOPIC
    assert fallback.delivery.subscription is None
    assert [
        lim.claim_ids
        for lim in answer.limitations
        if lim.code == LimitationCode.UNRESOLVED_IDENTITY
    ] == [[fallback.claim_id]]


def test_observed_publish_confirms_routes_and_consumer_evidence_stays_on_its_own_route(driver):
    _observe_orders_publish_and_billing_consumption(driver)
    observed = _observed_ids(driver)

    answer = _dependencies(driver)
    jsonschema.validate(instance=answer.model_dump(mode="json"), schema=DEPENDENCY_SCHEMA)
    by_object = {claim.object.id: claim for claim in answer.claims}

    billing, shipping = by_object["service:billing"], by_object["service:shipping"]
    assert billing.qualification == shipping.qualification == Qualification.CONFIRMED
    assert set(billing.evidence_refs) & observed
    assert set(billing.resolution_evidence_refs) & observed
    assert not set(shipping.resolution_evidence_refs) & observed
    # the unobserved refunds route is judged under the widened shared messaging-coverage rule
    refunds = by_object[REFUNDS_TOPIC_ID]
    assert refunds.qualification == Qualification.NOT_OBSERVED_IN_WINDOW
    assert refunds.coverage == Coverage.SUFFICIENT


def test_pubsub_only_telemetry_counts_as_messaging_coverage(driver):
    _observe_orders_publish_and_billing_consumption(driver)

    with driver.session(database=DATABASE) as session:
        coverage = {
            c.service_id: c
            for c in telemetry_coverage(
                session,
                environment=ENVIRONMENT,
                since=SPAN_TIME.replace(hour=0),
                until=SPAN_TIME.replace(hour=23),
                service_ids=["service:orders", "service:billing", "service:shipping"],
            )
        }
    assert coverage["service:orders"].messaging_observed is True  # PUBLISHES_TO -> Topic
    assert coverage["service:billing"].messaging_observed is True  # RECEIVES_FROM -> Subscription
    assert coverage["service:shipping"].messaging_observed is False


def test_unmatched_consumer_span_changes_no_dependency_answer(driver):
    before = _dependencies(driver).model_dump(mode="json")
    batch = _ingest(
        driver, [_span("billing", "receive", **{"messaging.consumer.group.name": "billing"})]
    )
    assert batch.unresolved
    assert _dependencies(driver).model_dump(mode="json") == before


# --- §12.5 drift --------------------------------------------------------------------------------


def test_drift_is_the_exact_drift_qualified_subset_of_the_dependency_claims(driver):
    _observe_orders_publish_and_billing_consumption(driver)
    dependencies = _dependencies(driver)
    drift = _drift(driver)
    jsonschema.validate(instance=drift.model_dump(mode="json"), schema=DRIFT_SCHEMA)

    assert drift.snapshot == dependencies.snapshot
    assert [claim.model_dump() for claim in drift.claims] == [
        claim.model_dump()
        for claim in dependencies.claims
        if claim.qualification
        in (Qualification.OBSERVED_ONLY, Qualification.NOT_OBSERVED_IN_WINDOW)
    ]
    assert _routes(drift) == [(REFUNDS_TOPIC_ID, None)]


def test_declared_only_drift_carries_every_route(driver):
    drift = _drift(driver)

    assert sorted(_routes(drift)) == sorted(
        [
            ("service:billing", BILLING_SUB),
            ("service:shipping", SHIPPING_SUB),
            (REFUNDS_TOPIC_ID, None),
        ]
    )
    assert {claim.qualification for claim in drift.claims} == {Qualification.NOT_OBSERVED_IN_WINDOW}


# --- §11 / §12.6 evidence drill-down ------------------------------------------------------------


def _all_claim_refs(answer) -> list[str]:
    refs = set(answer.evidence_refs)
    for claim in answer.claims:
        refs.update(claim.evidence_refs)
        refs.update(claim.resolution_evidence_refs)
    return sorted(refs)


def test_every_pubsub_evidence_ref_resolves_at_the_answer_snapshot(driver):
    _observe_orders_publish_and_billing_consumption(driver)
    answer = _dependencies(driver)
    refs = _all_claim_refs(answer)
    assert len(refs) <= 20

    evidence = _service(driver).get_evidence(
        EvidenceRequest.model_validate(
            {"evidence_refs": refs, "snapshot_id": answer.snapshot.snapshot_id}
        )
    )
    jsonschema.validate(instance=evidence.model_dump(mode="json"), schema=EVIDENCE_SCHEMA)
    assert evidence.outcome == Outcome.ANSWERED
    assert evidence.data.missing_evidence_refs == []

    facts = {
        (fact.relation_type.value, fact.source_id, fact.target_id)
        for record in evidence.data.records
        for fact in record.supports
    }
    assert ("PUBLISHES_TO", "service:orders", TOPIC_ID) in facts
    assert ("SUBSCRIPTION_OF", BILLING_SUB, TOPIC_ID) in facts
    assert ("RECEIVES_FROM", "service:billing", BILLING_SUB) in facts
    assert ("SUBSCRIPTION_OF", SHIPPING_SUB, TOPIC_ID) in facts


# --- §13.4 public-surface equivalence and zero writes -------------------------------------------


@pytest.mark.asyncio
async def test_service_rest_and_mcp_agree_and_reads_cause_zero_graph_writes(driver):
    _observe_orders_publish_and_billing_consumption(driver)
    service = _service(driver)
    before = _graph_state(driver)

    dependencies = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(_request_payload("service:orders"))
    ).model_dump(mode="json")
    drift = service.get_architecture_drift(
        ArchitectureDriftRequest.model_validate(_request_payload("service:orders"))
    ).model_dump(mode="json")
    evidence_payload = {
        "evidence_refs": _all_claim_refs(
            service.get_service_dependencies(
                ServiceDependenciesRequest.model_validate(_request_payload("service:orders"))
            )
        ),
        "snapshot_id": dependencies["snapshot"]["snapshot_id"],
    }
    evidence = service.get_evidence(EvidenceRequest.model_validate(evidence_payload)).model_dump(
        mode="json"
    )
    assert any(claim["delivery"]["subscription"] for claim in dependencies["claims"])

    client = _client(driver, service=service)
    params = {"environment": ENVIRONMENT, "from": WINDOW_START, "to": WINDOW_END}
    rest_dependencies = client.get("/api/services/service:orders/dependencies", params=params)
    rest_drift = client.get("/api/services/service:orders/drift", params=params)
    rest_evidence = client.post("/api/evidence/resolve", json=evidence_payload)
    assert rest_dependencies.status_code == rest_drift.status_code == 200
    assert rest_evidence.status_code == 200
    assert rest_dependencies.json() == dependencies
    assert rest_drift.json() == drift
    assert rest_evidence.json() == evidence

    server = MCPServer(name="test", version="0.5.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as http:
            results = {
                name: await call_negotiated(
                    http, origin=_ALLOWED_ORIGIN, name=name, arguments={"request": request}
                )
                for name, request in (
                    ("get_service_dependencies", _request_payload("service:orders")),
                    ("get_architecture_drift", _request_payload("service:orders")),
                    ("get_evidence", evidence_payload),
                )
            }
    assert all(result["isError"] is False for result in results.values())
    assert results["get_service_dependencies"]["structuredContent"] == dependencies
    assert results["get_architecture_drift"]["structuredContent"] == drift
    assert results["get_evidence"]["structuredContent"] == evidence

    assert _graph_state(driver) == before
