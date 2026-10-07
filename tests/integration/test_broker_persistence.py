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


def test_snapshot_projects_the_broker_so_no_relation_endpoint_is_missing(driver):
    from app.architecture_intelligence.repository import canonical_snapshot_state
    from evaluation.architecture_answers.reference import snapshot as reference_snapshot

    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        _import(session, SOURCE_A, _model("service:a"), "d1")
        state = canonical_snapshot_state(session, coverage_qualification_enabled=True)
        reference = reference_snapshot.canonical_state(session, coverage_qualification_enabled=True)

    assert state["version"] == 4
    assert state["brokers"] == [{"id": BROKER_ID, "stable_broker_id": STABLE}]
    node_ids = {row["id"] for key in ("services", "brokers") for row in state[key]}
    uses = [r for r in state["relations"] if r["type"] == "USES_BROKER"]
    assert len(uses) == 1
    assert uses[0]["source_id"] in node_ids and uses[0]["target_id"] in node_ids
    # the independently transcribed reference agrees with production
    assert reference["brokers"] == state["brokers"]
    assert reference["relations"] == state["relations"]


def test_asyncapi_import_persists_one_shared_broker_until_its_last_declarer_is_removed(
    driver, tmp_path
):
    """v0.6.1 I1b end to end: two AsyncAPI documents naming the same explicit broker id evidence one
    Broker node; removing a declaring document keeps it while another still uses it."""
    from tests.integration.test_pubsub_persistence import BROKER, _doc, _import, _write

    broker_id = broker_owned_id(stable_broker_id=BROKER)
    _write(tmp_path, "orders", _doc("orders", publish=True))
    _write(tmp_path, "billing", _doc("billing", subscription="billing"))
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        assert _count(session, USES_COUNT) == 2
        stored = session.run("MATCH (b:Broker) RETURN b.id AS id").single()["id"]
        assert stored == broker_id

    (tmp_path / "orders" / "asyncapi.yaml").unlink()
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        assert _count(session, USES_COUNT) == 1

    (tmp_path / "billing" / "asyncapi.yaml").unlink()
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 0
        assert _count(session, USES_COUNT) == 0


# --- v0.6.1 I1c: the Architecture Manifest `brokers` block and cross-source lifecycle ---------------


def _write_manifest(root, service: str, *broker_ids: str) -> None:
    import yaml

    path = root / service / "architecture.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "service": service,
                "x-aip-service-id": f"service:{service}",
                "brokers": [{"brokerId": b} for b in broker_ids],
            },
            sort_keys=False,
        )
    )


def _uses_rows(session) -> list[dict]:
    return session.run(
        "MATCH (s:Service)-[r:USES_BROKER]->(b:Broker) "
        "RETURN s.id AS service, b.id AS broker, r.evidence_ids AS evidence ORDER BY b.id"
    ).data()


def test_manifest_and_asyncapi_with_equal_broker_ids_reconcile_to_one_broker(driver, tmp_path):
    from tests.integration.test_pubsub_persistence import BROKER, _doc, _import, _write

    _write(tmp_path, "orders", _doc("orders", publish=True))
    _write_manifest(tmp_path, "orders", BROKER)
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        [row] = _uses_rows(session)
        assert row["service"] == "service:orders"
        # one fact, declared by two independent sources: both sources' evidence is retained
        assert len(row["evidence"]) == 2

    # the manifest alone stops declaring it: the AsyncAPI source still evidences it
    (tmp_path / "orders" / "architecture.yaml").unlink()
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        [row] = _uses_rows(session)
        assert len(row["evidence"]) == 1


def test_different_broker_ids_never_merge_for_one_service(driver, tmp_path):
    from tests.integration.test_pubsub_persistence import BROKER, _doc, _import, _write

    other = "kafka:other-cluster"
    _write(tmp_path, "orders", _doc("orders", publish=True))
    _write_manifest(tmp_path, "orders", other)
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        rows = _uses_rows(session)
        assert {r["broker"] for r in rows} == {
            broker_owned_id(stable_broker_id=BROKER),
            broker_owned_id(stable_broker_id=other),
        }
        assert {r["service"] for r in rows} == {"service:orders"}


def test_manifest_alone_declares_a_broker_and_withdrawing_it_removes_the_broker(driver, tmp_path):
    import yaml

    from tests.integration.test_pubsub_persistence import BROKER, _import

    # a phase-0 OpenAPI source with no Broker evidence of its own declares the Service
    openapi = tmp_path / "orders" / "openapi.yaml"
    openapi.parent.mkdir(parents=True)
    openapi.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.3",
                "info": {"title": "orders", "version": "1"},
                "x-aip-service-id": "service:orders",
                "paths": {
                    "/orders": {
                        "get": {
                            "operationId": "listOrders",
                            "responses": {"200": {"description": "ok"}},
                        }
                    }
                },
            }
        )
    )
    _write_manifest(tmp_path, "orders", BROKER)
    first = _import(driver, tmp_path)
    assert first.committed is True, first.diagnostics
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 1
        assert _count(session, USES_COUNT) == 1

    (tmp_path / "orders" / "architecture.yaml").unlink()
    assert _import(driver, tmp_path).committed is True
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (b:Broker) RETURN count(b) AS c") == 0
        assert _count(session, USES_COUNT) == 0


def test_manifest_for_an_undeclared_service_is_rejected_and_writes_nothing(driver, tmp_path):
    from app.sources.model import DiagnosticCode
    from tests.integration.test_pubsub_persistence import _import

    _write_manifest(tmp_path, "ghost", "kafka:cluster-a")
    stats = _import(driver, tmp_path)
    assert stats.committed is False
    assert DiagnosticCode.MANIFEST_CALL_SOURCE_UNRESOLVED in {d.code for d in stats.diagnostics}
    with driver.session(database=DATABASE) as session:
        assert _count(session, "MATCH (n) WHERE NOT n:AipInternalState RETURN count(n) AS c") == 0
