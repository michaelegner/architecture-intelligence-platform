"""v0.8 I1 A6: both declaration sets of the I1 spec §4.3 in one snapshot.

The Redpanda set declares the five Services and the pre-wave producers; the Kafka set declares the
four target Topics without operations. I3 needs both in one snapshot, so a Service or Topic
conflict across the two sets would stop the increment (spec §9). Integration because multi-source
Service ownership and Topic identity are only reconciled by the real import into Neo4j.
"""

import json
from pathlib import Path

import pytest

from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.model import FilesystemSourceConfig, IngestionResult

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "docs/specifications/0.8.0/i1-evidence"
IDS = json.loads((PACKAGE.parent / "i1-vectors/ids.json").read_text())
LOCAL, KAFKA = "kafka:sokol111-local", "kafka:sokol111-kafka"
SERVICES = {
    f"service:ecommerce-{name}-service"
    for name in ("tenant", "catalog", "image", "product-query", "category-query")
}
DUAL_BROKER_SERVICES = {"service:ecommerce-tenant-service", "service:ecommerce-catalog-service"}
# I1 spec §4.3: the producers before the wave, all on Redpanda.
PUBLISHES = {
    ("service:ecommerce-tenant-service", LOCAL, "tenant.tenant.events"),
    ("service:ecommerce-catalog-service", LOCAL, "catalog.attribute.events"),
    ("service:ecommerce-catalog-service", LOCAL, "catalog.category.events"),
    ("service:ecommerce-catalog-service", LOCAL, "catalog.product.events"),
    ("service:ecommerce-image-service", LOCAL, "catalog.product.events"),
}


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _import(driver) -> None:
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=[
                FilesystemSourceConfig(
                    id=f"sokol111-declarations-{name}", root=PACKAGE / "declarations" / name
                )
                for name in ("sokol111-local", "sokol111-kafka")
            ]
        ),
        driver=driver,
        database=DATABASE,
    )
    assert all(run.stats.committed and run.stats.diagnostics == () for run in runs)
    results = [r for run in runs for r in run.stats.source_results]
    assert len(results) == 7
    assert {(r.locator, r.result, r.diagnostics) for r in results} == {
        (r.locator, IngestionResult.ACCEPTED, ()) for r in results
    }


def _rows(driver, query: str) -> list[dict]:
    with driver.session(database=DATABASE) as session:
        return [record.data() for record in session.run(query)]


def test_both_sets_import_into_one_snapshot_without_conflict(driver):
    _import(driver)

    # One Service node per id; Tenant and Catalog are declared by one document per broker, and
    # both documents own the one node (no first-wins merge).
    owners = _rows(
        driver, "MATCH (s:Service) RETURN s.id AS id, size(s.owner_source_ids) AS owners"
    )
    assert len(owners) == len(SERVICES)
    assert {r["id"]: r["owners"] for r in owners} == {
        service: 2 if service in DUAL_BROKER_SERVICES else 1 for service in SERVICES
    }

    topics = _rows(driver, "MATCH (t:Topic) RETURN t.id AS id, t.name AS name")
    assert sorted(t["id"] for t in topics) == sorted(
        IDS[broker][name] for broker in (LOCAL, KAFKA) for name in IDS[broker]
    )
    by_id = {IDS[broker][name]: (broker, name) for broker in IDS for name in IDS[broker]}

    publishes = _rows(
        driver, "MATCH (s:Service)-[:PUBLISHES_TO]->(t:Topic) RETURN s.id AS s, t.id AS t"
    )
    assert {(r["s"], *by_id[r["t"]]) for r in publishes} == PUBLISHES

    # A Topic declaration without an operation is no evidence of broker use (spec §3).
    brokers = _rows(
        driver,
        "MATCH (s:Service)-[:USES_BROKER]->(b:Broker) RETURN s.id AS s, b.stable_broker_id AS b",
    )
    assert {r["b"] for r in brokers} == {LOCAL}
    assert {r["s"] for r in brokers} == {s for s, _, _ in PUBLISHES}
