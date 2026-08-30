"""I1.2 exit condition: a scenario can be loaded into AIP reproducibly from clean state (declared
fixture ingestion + static OTLP injection through the real ingestion path).

Canonical projection/comparison land in I1.3 - these tests assert directly against the raw graph,
the same way tests/integration/test_telemetry_api.py does, rather than against evaluation.projector
(which doesn't exist yet).
"""

from pathlib import Path

import pytest

from app.canonical import ids
from evaluation.loader import load_scenario
from evaluation.runner import (
    ingest_declarations,
    inject_runtime_fixture,
    prepare_scenario,
    reset_graph,
)

SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "scenarios"
DATABASE = "neo4j"


@pytest.fixture
def session(driver):
    with driver.session(database=DATABASE) as s:
        yield s


def _evidence_types(session, *, source_id: str, relation_type: str, target_id: str) -> set[str]:
    record = session.run(
        f"MATCH (a {{id: $source_id}})-[r:{relation_type}]->(b {{id: $target_id}}) "
        "RETURN r.evidence_ids AS ids",
        source_id=source_id,
        target_id=target_id,
    ).single()
    if record is None:
        return set()
    return {
        row["evidence_type"]
        for row in session.run(
            "UNWIND $ids AS eid MATCH (e:Evidence {id: eid}) RETURN e.evidence_type AS evidence_type",
            ids=record["ids"],
        )
    }


def _relation_exists(session, *, source_id: str, relation_type: str, target_id: str) -> bool:
    return (
        session.run(
            f"MATCH (a {{id: $source_id}})-[r:{relation_type}]->(b {{id: $target_id}}) "
            "RETURN count(r) AS c",
            source_id=source_id,
            target_id=target_id,
        ).single()["c"]
        > 0
    )


def test_rest_confirmed_scenario_is_declared_and_observed(driver, session):
    scenario = load_scenario(SCENARIOS_DIR / "01-rest-confirmed")
    prepare_scenario(driver, database=DATABASE, scenario=scenario)

    source_id = ids.service_id("order-service")
    target_id = ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}")
    evidence_types = _evidence_types(
        session, source_id=source_id, relation_type="CALLS", target_id=target_id
    )
    assert evidence_types == {"DECLARED", "OBSERVED"}


def test_rest_observed_only_scenario_has_no_declared_evidence(driver, session):
    scenario = load_scenario(SCENARIOS_DIR / "02-rest-observed-only")
    prepare_scenario(driver, database=DATABASE, scenario=scenario)

    source_id = ids.service_id("order-service")
    target_id = ids.operation_id(ids.service_id("product-service"), "GET", "/prices")
    evidence_types = _evidence_types(
        session, source_id=source_id, relation_type="CALLS", target_id=target_id
    )
    assert evidence_types == {"OBSERVED"}


def test_async_confirmed_scenario_is_declared_and_observed_in_both_directions(driver, session):
    scenario = load_scenario(SCENARIOS_DIR / "03-async-confirmed")
    prepare_scenario(driver, database=DATABASE, scenario=scenario)

    queue_id = ids.queue_id("order-events-q")
    sends_evidence = _evidence_types(
        session,
        source_id=ids.service_id("order-service"),
        relation_type="SENDS",
        target_id=queue_id,
    )
    receives_evidence = _evidence_types(
        session,
        source_id=ids.service_id("inventory-service"),
        relation_type="RECEIVES_FROM",
        target_id=queue_id,
    )
    assert sends_evidence == {"DECLARED", "OBSERVED"}
    assert receives_evidence == {"DECLARED", "OBSERVED"}


def test_reset_graph_wipes_the_previous_scenarios_facts(driver, session):
    first = load_scenario(SCENARIOS_DIR / "01-rest-confirmed")
    prepare_scenario(driver, database=DATABASE, scenario=first)
    assert (
        session.run("MATCH (n) RETURN count(n) AS c").single()["c"] > 0
    )  # sanity: something was written

    reset_graph(driver, database=DATABASE)

    assert session.run("MATCH (n) RETURN count(n) AS c").single()["c"] == 0


def test_ingest_declarations_alone_does_not_write_observed_evidence(driver, session):
    reset_graph(driver, database=DATABASE)
    scenario = load_scenario(SCENARIOS_DIR / "01-rest-confirmed")

    ingest_declarations(driver, database=DATABASE, scenario=scenario)

    source_id = ids.service_id("order-service")
    target_id = ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}")
    assert _relation_exists(
        session, source_id=source_id, relation_type="CALLS", target_id=target_id
    )
    evidence_types = _evidence_types(
        session, source_id=source_id, relation_type="CALLS", target_id=target_id
    )
    assert evidence_types == {"DECLARED"}

    inject_runtime_fixture(driver, database=DATABASE, scenario=scenario)
    evidence_types = _evidence_types(
        session, source_id=source_id, relation_type="CALLS", target_id=target_id
    )
    assert evidence_types == {"DECLARED", "OBSERVED"}
