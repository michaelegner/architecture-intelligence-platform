"""v0.6.1 I2c: Broker claims through the real `ArchitectureIntelligenceService` on real Neo4j
(spec §5): the data-dependent version, claim identity and evidence, the evidence round trip, and the
surfaces that must NOT change (drift, deployments view, Broker-free answers)."""

import json
from pathlib import Path

import pytest
import yaml

from app.architecture_intelligence.broker_contracts import (
    ArchitectureAnswerV06,
    BrokerClaim,
    EvidenceRelationTypeV06,
)
from app.architecture_intelligence.broker_projection import compute_broker_claim_id
from app.architecture_intelligence.contracts import ArchitectureAnswer, Outcome, Producer
from app.architecture_intelligence.deployments_view import project_service_deployments
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from app.sources.owner_ids import broker_owned_id
from tests.integration.test_pubsub_persistence import BROKER, _doc, _import, _write
from tests.support.answer_schemas import validate_dependencies, validate_evidence

DATABASE = "neo4j"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.1", build_revision="f" * 40
)
CONTEXT = {
    "environment": "test",
    "window_start": "2026-08-26T00:00:00.000000Z",
    "window_end": "2026-08-27T00:00:00.000000Z",
}
BROKER_ID = broker_owned_id(stable_broker_id=BROKER)
OTHER = "kafka:other-cluster"
OTHER_ID = broker_owned_id(stable_broker_id=OTHER)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request(service_id: str) -> ServiceDependenciesRequest:
    return ServiceDependenciesRequest.model_validate(
        {"service_id": service_id, "observation_context": CONTEXT}
    )


def _write_plain_service(root: Path) -> None:
    path = root / "plain" / "openapi.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "info": {"title": "plain", "version": "1"},
                "x-aip-service-id": "service:plain",
                "paths": {
                    "/p": {"get": {"operationId": "p", "responses": {"200": {"description": "ok"}}}}
                },
            }
        )
    )


def _two_broker_document() -> dict:
    document = _doc("multi", publish=True)
    document["servers"]["other"] = {
        "url": "kafka.example",
        "protocol": "kafka",
        "x-aip-broker-id": OTHER,
    }
    first = document["channels"]["orders"]
    first["servers"] = ["gcp"]
    second = json.loads(json.dumps(first))
    second["servers"] = ["other"]
    document["channels"]["invoices"] = second
    return document


@pytest.fixture
def graph(driver, tmp_path):
    _write(tmp_path, "orders", _doc("orders", publish=True))
    _write(tmp_path, "billing", _doc("billing", subscription="billing"))
    _write(tmp_path, "multi", _two_broker_document())
    _write_plain_service(tmp_path)
    assert _import(driver, tmp_path).committed is True
    return driver


def test_a_broker_bearing_service_gets_a_v06_answer_with_one_claim(graph):
    answer = _service(graph).get_service_dependencies(_request("service:orders"))
    assert isinstance(answer, ArchitectureAnswerV06)
    assert answer.schema_version == "0.6" and answer.outcome in (Outcome.ANSWERED, Outcome.PARTIAL)
    [claim] = [c for c in answer.claims if isinstance(c, BrokerClaim)]
    assert (claim.subject.id, claim.object.id, claim.object.name) == (
        "service:orders",
        BROKER_ID,
        BROKER,
    )
    assert claim.claim_id == compute_broker_claim_id(
        service_id="service:orders", broker_id=BROKER_ID
    )
    assert answer.data is not None and answer.data.broker_claim_ids == [claim.claim_id]
    assert set(claim.evidence_refs) <= set(answer.evidence_refs)
    validate_dependencies(json.loads(answer.model_dump_json()))


def test_a_broker_free_service_keeps_the_v05_answer_with_no_broker_fields(graph):
    answer = _service(graph).get_service_dependencies(_request("service:plain"))
    assert isinstance(answer, ArchitectureAnswer)
    assert answer.schema_version == "0.5"
    payload = json.loads(answer.model_dump_json())
    assert "broker_claim_ids" not in (payload["data"] or {})
    assert not any(c["predicate"] == "USES_BROKER" for c in payload["claims"])
    validate_dependencies(payload)


def test_two_brokers_for_one_service_give_two_claims_and_one_broker_is_shared(graph):
    multi = _service(graph).get_service_dependencies(_request("service:multi"))
    assert isinstance(multi, ArchitectureAnswerV06)
    brokers = {c.object.id for c in multi.claims if isinstance(c, BrokerClaim)}
    assert brokers == {BROKER_ID, OTHER_ID}

    orders = _service(graph).get_service_dependencies(_request("service:orders"))
    billing = _service(graph).get_service_dependencies(_request("service:billing"))
    claims = {
        answer.claims[0].subject.id: c
        for answer in (orders, billing)
        for c in answer.claims
        if isinstance(c, BrokerClaim)
    }
    assert claims["service:orders"].object.id == claims["service:billing"].object.id == BROKER_ID
    assert claims["service:orders"].claim_id != claims["service:billing"].claim_id


def test_every_broker_claim_ref_resolves_through_get_evidence_to_the_exact_fact(graph):
    service = _service(graph)
    answer = service.get_service_dependencies(_request("service:orders"))
    [claim] = [c for c in answer.claims if isinstance(c, BrokerClaim)]
    for ref in claim.evidence_refs:
        evidence = service.get_evidence(
            EvidenceRequest(evidence_refs=[ref], snapshot_id=answer.snapshot.snapshot_id)
        )
        assert isinstance(evidence, ArchitectureAnswerV06) and evidence.schema_version == "0.6"
        assert evidence.data.missing_evidence_refs == []
        [record] = evidence.data.records
        [fact] = [
            f for f in record.supports if f.relation_type is EvidenceRelationTypeV06.USES_BROKER
        ]
        assert (fact.source_id, fact.target_id) == ("service:orders", BROKER_ID)
        assert fact.broker is not None
        assert (fact.broker.id, fact.broker.type.value, fact.broker.name) == (
            BROKER_ID,
            "BROKER",
            BROKER,
        )
        validate_evidence(json.loads(evidence.model_dump_json()))


def test_get_evidence_for_a_broker_free_source_stays_v05(graph):
    service = _service(graph)
    plain = service.get_service_dependencies(_request("service:plain"))
    with graph.session(database=DATABASE) as session:
        ref = session.run(
            "MATCH (e:Evidence) WHERE e.source_type = 'OPENAPI' RETURN e.id AS id LIMIT 1"
        ).single()["id"]
    evidence = service.get_evidence(
        EvidenceRequest(evidence_refs=[ref], snapshot_id=plain.snapshot.snapshot_id)
    )
    assert isinstance(evidence, ArchitectureAnswer) and evidence.schema_version == "0.5"
    validate_evidence(json.loads(evidence.model_dump_json()))


def test_drift_never_carries_a_broker_claim_and_stays_v05(graph):
    drift = _service(graph).get_architecture_drift(
        ArchitectureDriftRequest.model_validate(
            {"service_id": "service:orders", "observation_context": CONTEXT}
        )
    )
    assert drift.schema_version == "0.5"
    assert not any(c.predicate.value == "USES_BROKER" for c in drift.claims)


def test_the_deployments_view_of_a_broker_bearing_service_stays_v05(graph):
    answer = _service(graph).get_service_dependencies(_request("service:orders"))
    assert answer.schema_version == "0.6"
    view = project_service_deployments(answer)
    assert view.schema_version == "0.5"
    assert view.deployment_claims == [] and view.service is not None


def test_repeated_reads_are_byte_identical(graph):
    service = _service(graph)
    first = service.get_service_dependencies(_request("service:multi")).model_dump_json()
    second = service.get_service_dependencies(_request("service:multi")).model_dump_json()
    assert first == second


def test_a_refusal_for_a_broker_bearing_service_stays_v05(graph):
    service = _service(graph)
    stale = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {
                "service_id": "service:orders",
                "observation_context": CONTEXT,
                "snapshot_id": "aip:snapshot:v1:" + "0" * 64,
            }
        )
    )
    no_context = service.get_service_dependencies(
        ServiceDependenciesRequest.model_validate({"service_id": "service:orders"})
    )
    for refusal in (stale, no_context):
        assert isinstance(refusal, ArchitectureAnswer)
        assert refusal.schema_version == "0.5" and refusal.outcome is Outcome.NOT_ANSWERED
        assert refusal.data is None and refusal.claims == []


def test_a_broker_with_no_resolvable_evidence_yields_a_v05_refusal_naming_no_broker(driver):
    """The unevidenced-Broker rule (spec §5.1): no claim, one INSUFFICIENT_EVIDENCE limitation that
    names the Service but no Broker, and the answer stays the v0.5 shape. The state cannot come from
    ingestion (importers stamp declared evidence), so it is built directly."""
    with driver.session(database=DATABASE) as session:
        session.run(
            "CREATE (:Service {id: 'service:ghost', name: 'ghost'}) "
            "CREATE (:Broker {id: $broker, stable_broker_id: $stable}) "
            "WITH 1 AS _ MATCH (s:Service {id: 'service:ghost'}), (b:Broker {id: $broker}) "
            "CREATE (s)-[:USES_BROKER {evidence_ids: []}]->(b)",
            broker=BROKER_ID,
            stable=BROKER,
        ).consume()
        ensure_schema(session)  # the revision singleton the stable read fences on
    answer = _service(driver).get_service_dependencies(_request("service:ghost"))
    assert isinstance(answer, ArchitectureAnswer) and answer.schema_version == "0.5"
    assert answer.outcome is Outcome.NOT_ANSWERED and answer.claims == []
    [limitation] = answer.limitations
    assert limitation.code.value == "INSUFFICIENT_EVIDENCE"
    assert "service:ghost" in limitation.message
    assert BROKER_ID not in limitation.message and BROKER not in limitation.message
