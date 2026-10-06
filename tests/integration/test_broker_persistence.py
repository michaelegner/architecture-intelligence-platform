"""v0.6.1 I1a: real-Neo4j persistence of Broker + `USES_BROKER` through the existing I1 ownership/
replay/expiry engine (spec §4.4). No adapter emits Brokers yet, so models are built directly and
driven through `import_source`."""

import pytest

from app.canonical.model import ArchitectureModel, Broker, Relation, Service
from app.graph.importer import import_source
from app.graph.schema import ensure_schema
from app.sources.owner_ids import broker_owned_id

DATABASE = "neo4j"
STABLE = "kafka:cluster-a"
BROKER_ID = broker_owned_id(stable_broker_id=STABLE)
SOURCE_A = "urn:aip:source:test:a"
SOURCE_B = "urn:aip:source:test:b"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _model(service_id: str, *, with_broker: bool = True) -> ArchitectureModel:
    services = [Service(id=service_id, name=service_id)]
    if not with_broker:
        return ArchitectureModel(services=services)
    return ArchitectureModel(
        services=services,
        brokers=[Broker(id=BROKER_ID, stable_broker_id=STABLE)],
        relations=[Relation(type="USES_BROKER", source_id=service_id, target_id=BROKER_ID)],
    )


def _import(session, source: str, model: ArchitectureModel, digest: str):
    return import_source(
        session,
        source_instance_id=source,
        locator=f"{source}/architecture.yaml",
        model=model,
        semantic_input_digest=digest,
        discovery_scope_id="urn:aip:scope:test",
        scope_definition_digest="scope",
    )


def _count(session, query: str) -> int:
    return session.run(query).single()["c"]


BROKER_COUNT = f"MATCH (b:Broker {{id: '{BROKER_ID}'}}) RETURN count(b) AS c"
USES_COUNT = "MATCH (:Service)-[r:USES_BROKER]->(:Broker) RETURN count(r) AS c"


def test_broker_and_uses_broker_persist_with_the_unique_constraint(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, SOURCE_A, _model("service:a"), "d1")
        assert _count(session, BROKER_COUNT) == 1
        assert _count(session, USES_COUNT) == 1
        stored = session.run(f"MATCH (b:Broker {{id: '{BROKER_ID}'}}) RETURN b").single()["b"]
        assert stored["stable_broker_id"] == STABLE
        constraints = {r["name"] for r in session.run("SHOW CONSTRAINTS")}
        assert "broker_id" in constraints


def test_reimport_of_identical_input_is_idempotent(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, SOURCE_A, _model("service:a"), "d1")
        _import(session, SOURCE_A, _model("service:a"), "d1")
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        assert _count(session, USES_COUNT) == 1


def test_equal_broker_ids_from_two_sources_reconcile_to_one_node(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, SOURCE_A, _model("service:a"), "d1")
        _import(session, SOURCE_B, _model("service:b"), "d2")
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        assert _count(session, USES_COUNT) == 2


def test_shared_broker_survives_until_its_last_owner_withdraws(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, SOURCE_A, _model("service:a"), "d1")
        _import(session, SOURCE_B, _model("service:b"), "d2")

        # Source A stops declaring the Broker: B still owns it.
        _import(session, SOURCE_A, _model("service:a", with_broker=False), "d3")
        assert _count(session, BROKER_COUNT) == 1
        assert _count(session, USES_COUNT) == 1

        # Source B stops too: last owner withdrew, Broker and relation are gone.
        _import(session, SOURCE_B, _model("service:b", with_broker=False), "d4")
        assert _count(session, BROKER_COUNT) == 0
        assert _count(session, USES_COUNT) == 0
