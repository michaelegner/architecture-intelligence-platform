from pathlib import Path

import pytest

from app.analysis.blast_radius import blast_radius
from app.analysis.dependencies import async_flow_to, sync_depends_on
from app.analysis.queues import (
    consumers_of_queue,
    queues_without_consumers,
    queues_without_senders,
    senders_of_queue,
)
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.sources.model import FilesystemSourceConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"


@pytest.fixture(scope="module", autouse=True)
def populated_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(id="test-analyses-examples", root=EXAMPLES_DIR),
    )


@pytest.fixture
def session(driver):
    with driver.session(database=DATABASE) as s:
        yield s


def _queue_id(session, name: str) -> str:
    record = session.run("MATCH (q:Queue {name: $name}) RETURN q.id AS id", name=name).single()
    assert record is not None, f"no Queue node found with name {name!r}"
    return record["id"]


def test_a1_senders_of_payment_q(session):
    result = senders_of_queue(session, _queue_id(session, "payment-q"))
    assert [r.id for r in result] == [ids.service_id("order-service")]


def test_a1_senders_of_queue_with_none(session):
    assert senders_of_queue(session, _queue_id(session, "unknown-producer-q")) == []


def test_a2_consumers_of_payment_q(session):
    result = consumers_of_queue(session, _queue_id(session, "payment-q"))
    assert [r.id for r in result] == [ids.service_id("payment-service")]


def test_a2_consumers_of_queue_with_none(session):
    assert consumers_of_queue(session, _queue_id(session, "unused-q")) == []


def test_a3_queues_without_consumers(session):
    result = queues_without_consumers(session)
    assert [r.id for r in result] == [_queue_id(session, "unused-q")]


def test_a4_queues_without_senders(session):
    result = queues_without_senders(session)
    assert len(result) == 1
    assert result[0].queue_id == _queue_id(session, "unknown-producer-q")
    assert result[0].consumer_name == "PaymentService"


def test_a5_blast_radius_from_order_service(session):
    result = blast_radius(session, ids.service_id("order-service"))
    by_id = {e.service_id: e for e in result}

    assert by_id[ids.service_id("product-service")].depth == 1
    assert by_id[ids.service_id("product-service")].via == "SYNC"
    assert by_id[ids.service_id("payment-service")].depth == 1
    assert by_id[ids.service_id("payment-service")].via == "ASYNC"
    assert by_id[ids.service_id("invoice-service")].depth == 2
    assert by_id[ids.service_id("invoice-service")].via == "ASYNC"
    assert set(by_id) == {
        ids.service_id("product-service"),
        ids.service_id("payment-service"),
        ids.service_id("invoice-service"),
    }


def test_a5_blast_radius_respects_max_depth(session):
    result = blast_radius(session, ids.service_id("order-service"), max_depth=1)
    assert {e.service_id for e in result} == {
        ids.service_id("product-service"),
        ids.service_id("payment-service"),
    }


def test_a5_blast_radius_from_leaf_service_is_empty(session):
    assert blast_radius(session, ids.service_id("invoice-service")) == []


def test_sync_depends_on_computed_view(session):
    result = sync_depends_on(session)
    assert len(result) == 1
    assert result[0].source_id == ids.service_id("order-service")
    assert result[0].target_id == ids.service_id("product-service")


def test_async_flow_to_computed_view(session):
    result = async_flow_to(session)
    edges = {(e.source_id, e.target_id) for e in result}
    assert edges == {
        (ids.service_id("order-service"), ids.service_id("payment-service")),
        (ids.service_id("payment-service"), ids.service_id("invoice-service")),
    }
