"""v0.6.1 I3a §6.2: the bounded Broker question against two frozen references on real Neo4j.

- **Quarkus Super Heroes** (the v0.5.1 demo overlay + the frozen v0.5.0 declarations): `rest-fights`
  and `event-statistics` use the one `kafka:fights-kafka` Broker, and the existing Topic/Subscription
  resolution limits are preserved (knowing the Broker does not resolve the missing Subscription).
- **FINOS FluxNova/CALM** (the disclosed transcription package under
  `tests/fixtures/broker-qualification/calm-fluxnova`): both workers use the one frozen Message
  Broker, and nothing richer (Queue, Topic, Subscription, Message, Operation, any other relation) is
  invented from CALM `connects`.

Expectations are hand-authored (`expected.yaml` / the overlay and dossier text); canonical ids come
from the independent evaluation reference, never from production id code. Apache Airflow's negative
case is `tests/unit/test_broker_qualification_airflow.py` (it needs no Neo4j).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.architecture_intelligence.broker_contracts import BrokerClaim
from app.architecture_intelligence.contracts import (
    DependencyClaim,
    LimitationCode,
    Outcome,
)
from app.architecture_intelligence.request import (
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_all_sources
from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.model import DiagnosticCode, FilesystemSourceConfig
from evaluation.architecture_answers.reference import identities
from tests.integration.test_broker_architecture_intelligence import PRODUCER
from tests.support.answer_schemas import validate_dependencies, validate_evidence

DATABASE = "neo4j"
ROOT = Path(__file__).resolve().parents[2]
BROKER_FIXTURES = ROOT / "tests" / "fixtures" / "broker-qualification"
DOSSIER = ROOT / "docs" / "real-world-validation" / "v0.5.0" / "quarkus-super-heroes" / "runtime"
DEMO = ROOT / "examples" / "quarkus-super-heroes-demo"
QUARKUS_CONTEXT = {
    "environment": "quarkus-i5",
    "window_start": "2026-09-25T13:06:47Z",
    "window_end": "2026-09-25T13:06:54Z",
}
FIGHTS_BROKER = "kafka:fights-kafka"
# Any complete observation context works for the Broker question (Broker use is not runtime-qualified).
FLUXNOVA_CONTEXT = {
    "environment": "calm-fluxnova",
    "window_start": "2026-10-06T00:00:00Z",
    "window_end": "2026-10-07T00:00:00Z",
}


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _answer(driver, service_id: str, context: dict):
    return _service(driver).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {"service_id": service_id, "observation_context": context}
        )
    )


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]


def _resolves_to_the_exact_broker_fact(driver, answer, claim: BrokerClaim) -> None:
    """Every ref on the claim resolves at the answer's own snapshot to a v0.6 record whose supports
    contain exactly that `(USES_BROKER, Service, Broker)` fact."""
    evidence = _service(driver).get_evidence(
        EvidenceRequest(evidence_refs=claim.evidence_refs, snapshot_id=answer.snapshot.snapshot_id)
    )
    assert evidence.schema_version == "0.6" and evidence.data.missing_evidence_refs == []
    validate_evidence(json.loads(evidence.model_dump_json()))
    for record in evidence.data.records:
        assert any(
            f.relation_type.value == "USES_BROKER"
            and (f.source_id, f.target_id) == (claim.subject.id, claim.object.id)
            and f.broker is not None
            and f.broker.name == claim.object.name
            for f in record.supports
        ), record.id


# --- Quarkus Super Heroes ---------------------------------------------------------------------------


def _import_quarkus(driver) -> None:
    for source_id, root in (
        ("qsh-v0.5-declarations", DOSSIER / "declarations"),
        ("qsh-demo-overlay", DEMO / "overlay"),
    ):
        assert import_all_sources(
            driver,
            database=DATABASE,
            source_config=FilesystemSourceConfig(id=source_id, root=root),
        ).committed


def test_quarkus_rest_fights_and_event_statistics_share_one_kafka_broker(driver):
    _import_quarkus(driver)
    broker_id = identities.broker_id(FIGHTS_BROKER)

    with driver.session(database=DATABASE) as session:
        brokers = [
            r.data()
            for r in session.run("MATCH (b:Broker) RETURN b.id AS id, b.stable_broker_id AS s")
        ]
    assert brokers == [{"id": broker_id, "s": FIGHTS_BROKER}]

    for service in ("rest-fights", "event-statistics"):
        answer = _answer(driver, f"service:{service}", QUARKUS_CONTEXT)
        assert answer.schema_version == "0.6", service
        [claim] = [c for c in answer.claims if isinstance(c, BrokerClaim)]
        assert (claim.object.id, claim.object.name) == (broker_id, FIGHTS_BROKER)
        assert claim.claim_id == identities.broker_claim_id(
            service_id=f"service:{service}", broker_id=broker_id
        )
        validate_dependencies(json.loads(answer.model_dump_json()))
        _resolves_to_the_exact_broker_fact(driver, answer, claim)


def test_quarkus_keeps_the_existing_topic_and_subscription_resolution_limits(driver):
    _import_quarkus(driver)

    # the consumer side still has no Subscription identity (v0.5.1): the Broker does not supply one
    overlay = run_filesystem_discovery(
        FilesystemSourceConfig(id="qsh-demo-overlay", root=DEMO / "overlay")
    )
    diagnostics = {
        Path(o.descriptor_locator).parent.name: [d.code for d in o.outcome.diagnostics]
        for o in overlay.source_outcomes.values()
    }
    assert diagnostics == {
        "rest-fights": [],
        "event-statistics": [DiagnosticCode.SUBSCRIPTION_IDENTITY_MISSING],
    }
    assert _count(driver, "MATCH (n:Subscription) RETURN count(n) AS c") == 0
    assert _count(driver, "MATCH (n:Topic {name: 'fights'}) RETURN count(n) AS c") == 1

    answer = _answer(driver, "service:rest-fights", QUARKUS_CONTEXT)
    assert answer.outcome is Outcome.PARTIAL
    published = [
        c
        for c in answer.claims
        if isinstance(c, DependencyClaim) and c.delivery.relation_type.value == "PUBLISHES_TO"
    ]
    assert len(published) == 1 and published[0].delivery.subscription is None
    assert [(lim.code, lim.claim_ids) for lim in answer.limitations] == [
        (LimitationCode.UNRESOLVED_IDENTITY, [published[0].claim_id])
    ]
    # no invented Subscription claim anywhere in either service's answer
    for service in ("rest-fights", "event-statistics"):
        for claim in _answer(driver, f"service:{service}", QUARKUS_CONTEXT).claims:
            assert not (
                isinstance(claim, DependencyClaim) and claim.delivery.subscription is not None
            )


# --- FINOS FluxNova / CALM -------------------------------------------------------------------------


def test_fluxnova_broker_connectivity_is_answerable_without_richer_topology(driver):
    expected = yaml.safe_load((BROKER_FIXTURES / "calm-fluxnova" / "expected.yaml").read_text())
    stats = import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="calm-fluxnova", root=BROKER_FIXTURES / "calm-fluxnova" / "declarations"
        ),
    )
    assert stats.committed is True, stats.diagnostics

    with driver.session(database=DATABASE) as session:
        brokers = sorted(
            r["s"] for r in session.run("MATCH (b:Broker) RETURN b.stable_broker_id AS s")
        )
        uses = sorted(
            (r["service"], r["stable"])
            for r in session.run(
                "MATCH (s:Service)-[:USES_BROKER]->(b:Broker) "
                "RETURN s.id AS service, b.stable_broker_id AS stable"
            )
        )
        relations = {
            r["type"]: r["c"]
            for r in session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS c")
        }
    assert brokers == sorted(expected["brokers"])
    assert uses == sorted((f"service:{slug}", stable) for slug, stable in expected["uses_broker"])

    # CALM identifies a broker-level connection only: nothing richer may exist
    for label in expected["absent_labels"]:
        assert _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") == 0, label
    assert relations == expected["relations"]

    broker_id = identities.broker_id("calm:finos-fluxnova:ms-message-broker")
    for slug, _ in expected["uses_broker"]:
        answer = _answer(driver, f"service:{slug}", FLUXNOVA_CONTEXT)
        assert answer.schema_version == "0.6"
        # exactly one claim, a Broker claim: no dependency or deployment claim is invented
        [claim] = answer.claims
        assert isinstance(claim, BrokerClaim)
        assert (claim.object.id, claim.object.name) == (
            broker_id,
            "calm:finos-fluxnova:ms-message-broker",
        )
        assert claim.claim_id == identities.broker_claim_id(
            service_id=f"service:{slug}", broker_id=broker_id
        )
        validate_dependencies(json.loads(answer.model_dump_json()))
        _resolves_to_the_exact_broker_fact(driver, answer, claim)


def test_the_fluxnova_transcription_matches_its_provenance():
    """The disclosed transcription package carries exactly the CALM ids PROVENANCE.md records."""
    provenance = (BROKER_FIXTURES / "calm-fluxnova" / "PROVENANCE.md").read_text()
    assert "c8c2811d28e10c12d0bf96be9434398585bb7d0e" in provenance
    assert "examples/fluxnova/fluxnova-microservices.architecture.json" in provenance
    assert "ms-message-broker" in provenance
    for slug in ("ms-payment-worker", "ms-notification-worker"):
        manifest = yaml.safe_load(
            (
                BROKER_FIXTURES / "calm-fluxnova" / "declarations" / slug / "architecture.yaml"
            ).read_text()
        )
        assert manifest["brokers"] == [{"brokerId": "calm:finos-fluxnova:ms-message-broker"}]
        assert manifest["x-aip-service-id"] == f"service:{slug}"
        assert f"{slug}-to-broker" in provenance and slug in provenance
        openapi = yaml.safe_load(
            (BROKER_FIXTURES / "calm-fluxnova" / "declarations" / slug / "openapi.yaml").read_text()
        )
        assert openapi["paths"] == {} and openapi["x-aip-service-id"] == f"service:{slug}"
