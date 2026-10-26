"""Shared helpers of the v0.8 I2b binding-picture integration tests."""

import json
from pathlib import Path

from app.architecture_intelligence.binding_picture_contracts import BindingPictureQueryRequest
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.model import (
    EventCatalogSourceConfig,
    FilesystemSourceConfig,
    KafkaConsumerStateSourceConfig,
    KafkaServiceMappingSourceConfig,
)

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/specifications/0.8.0"
I1 = SPEC / "i1-evidence"
PRODUCER = Producer(name="architecture-intelligence-platform", version="0.8.0", build_revision="t")
ENV = "local"
LOCAL, KAFKA = "kafka:sokol111-local", "kafka:sokol111-kafka"
GROUPS = {
    LOCAL: [
        f"ecommerce-{n}-service" for n in ("catalog", "category-query", "image", "product-query")
    ],
    KAFKA: ["ecommerce-catalog-service", "ecommerce-image-service"],
}


def catalog() -> EventCatalogSourceConfig:
    return EventCatalogSourceConfig(id="sokol111-catalog", root=I1, environment=ENV)


def capture(
    broker: str, root: Path, source_id: str | None = None
) -> KafkaConsumerStateSourceConfig:
    return KafkaConsumerStateSourceConfig(
        id=source_id or f"capture-{broker.split(':')[1]}",
        root=root,
        broker_id=broker,
        environment=ENV,
        consumer_groups=GROUPS[broker],
    )


def mapping(broker: str, root: Path) -> KafkaServiceMappingSourceConfig:
    return KafkaServiceMappingSourceConfig(
        id=f"mapping-{broker.split(':')[1]}", root=root, broker_id=broker, environment=ENV
    )


def run_import(driver, **sources) -> list:
    _, runs = run_all_configured_sources(
        SourcesConfig(**{"directories": [], **sources}), driver=driver, database=DATABASE
    )
    return runs


def directory(source_id: str, root: Path) -> FilesystemSourceConfig:
    return FilesystemSourceConfig(id=source_id, root=root)


def answer(driver, **request) -> dict:
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    query = BindingPictureQueryRequest(
        bounded_context_id="catalog-management", environment=ENV, **request
    )
    return service.get_binding_picture(query).model_dump(mode="json")


def essentials(answer: dict) -> list[dict]:
    """The compared fields of each row, in answer order."""
    keys = (
        "broker_id",
        "topic_name",
        "consumer_service_id",
        "crossing",
        "status",
        "reason",
        "cross_broker_producers",
    )
    return [{k: row[k] for k in keys if k in row} for row in answer["data"]["rows"]]


def expected(path: Path) -> dict:
    return json.loads(path.read_text())


def codes(answer: dict) -> list[str]:
    return [item["code"] for item in answer["limitations"]]
