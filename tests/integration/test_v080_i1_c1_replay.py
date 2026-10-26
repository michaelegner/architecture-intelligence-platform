"""v0.8 I1 A7: the frozen C1 capture against the v0.8 declarations and the extended mapping.

Inputs are the committed bytes under `docs/specifications/0.8.0/i1-evidence/`: the Redpanda
declaration set (Services, producers and Topics, no consumer), the extended Redpanda mapping and a
byte copy of the real v0.7.2 C1 capture. The expected Consumer x Topic set is the parent
specification's §3.5 table, written before any implementation. Everything goes through the
production import; REST and MCP parity of this answer family is already proven by the v0.7.1
surface-parity tests, so the rows are read through the service only.
"""

import hashlib
from pathlib import Path

import pytest

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersQueryRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    KafkaConsumerStateSourceConfig,
    KafkaServiceMappingSourceConfig,
)

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "docs/specifications/0.8.0/i1-evidence"
V072_SUMS = REPO / "docs/specifications/0.7.2/i2-evidence/sokol111/SHA256SUMS"
BROKER, ENV = "kafka:sokol111-local", "local"
GROUPS = [
    f"ecommerce-{name}-service" for name in ("catalog", "category-query", "image", "product-query")
]
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.8.0", build_revision="t")
# Parent specification §3.5: the nine Consumer x Topic attachments of C1 on Redpanda.
EXPECTED = {
    ("ecommerce-product-query-service", "catalog.product.events"),
    ("ecommerce-image-service", "catalog.product.events"),
    ("ecommerce-catalog-service", "tenant.tenant.events"),
    ("ecommerce-image-service", "tenant.tenant.events"),
    ("ecommerce-category-query-service", "catalog.category.events"),
    ("ecommerce-product-query-service", "catalog.attribute.events"),
    ("ecommerce-category-query-service", "catalog.attribute.events"),
    ("ecommerce-product-query-service", "tenant.tenant.events"),
    ("ecommerce-category-query-service", "tenant.tenant.events"),
}


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def test_the_c1_copy_is_byte_identical_to_the_v072_capture() -> None:
    digest = hashlib.sha256((PACKAGE / "c1/kafka-consumer-state.json").read_bytes()).hexdigest()
    assert f"{digest}  c1/kafka-consumer-state.json" in V072_SUMS.read_text().splitlines()


def test_c1_persists_and_resolves_all_nine_attachments(driver) -> None:
    _, runs = run_all_configured_sources(
        SourcesConfig(
            directories=[
                FilesystemSourceConfig(
                    id="sokol111-declarations-sokol111-local",
                    root=PACKAGE / "declarations/sokol111-local",
                )
            ],
            kafka_consumer_state=[
                KafkaConsumerStateSourceConfig(
                    id="sokol111-kafka",
                    root=PACKAGE / "c1",
                    broker_id=BROKER,
                    environment=ENV,
                    consumer_groups=GROUPS,
                )
            ],
            kafka_service_mappings=[
                KafkaServiceMappingSourceConfig(
                    id="sokol111-mapping",
                    root=PACKAGE / "mapping/sokol111-local",
                    broker_id=BROKER,
                    environment=ENV,
                )
            ],
        ),
        driver=driver,
        database=DATABASE,
    )
    assert all(run.stats.committed for run in runs)
    codes = {
        d.code
        for run in runs
        for d in (
            *run.stats.diagnostics,
            *(d for r in run.stats.source_results for d in r.diagnostics),
        )
    }
    assert DiagnosticCode.KAFKA_TOPIC_NOT_DECLARED not in codes

    with driver.session(database=DATABASE) as session:
        topics = {
            record["name"]: record["id"]
            for record in session.run("MATCH (t:Topic) RETURN t.name AS name, t.id AS id")
        }
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    rows = []
    for name, topic_id in sorted(topics.items()):
        answer = service.get_destination_consumers(
            DestinationConsumersQueryRequest(
                mode="query", destination_id=topic_id, broker_id=BROKER, environment=ENV
            )
        ).model_dump(mode="json")
        rows += [(name, row) for row in answer["data"]["rows"]]

    # Exactly one row per expected attachment: a duplicate must fail, not collapse.
    assert sorted((row["group_id"], name) for name, row in rows) == sorted(EXPECTED)
    for _, row in rows:
        assert row["outcome"] == "RESOLVED"
        assert row["service_id"] == f"service:{row['group_id']}"
