"""v0.8 I2a B5 (unit): the promise-record ids, the adapter's carriers and the duplicate rule.

The expected promises, memberships and event topics are written by hand from I1 §5.2 and §5.3; the
ids come from the hashlib-only `0.8.0/i2-vectors/ids.json`.
"""

import json
from pathlib import Path
from typing import Any, cast

from app.canonical.model import ArchitectureModel
from app.ingestion.event_catalog_adapter import EventCatalogSourceAdapter
from app.ingestion.event_catalog_discoverer import EventCatalogSourceDiscoverer
from app.sources.event_catalog_contract import duplicate_registrations
from app.sources.identity import (
    catalog_evidence_id,
    event_catalog_source_instance_id,
)
from app.sources.model import EventCatalogSourceConfig, IngestionResult

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "docs/specifications/0.8.0/i1-evidence"
IDS = json.loads((REPO / "docs/specifications/0.8.0/i2-vectors/ids.json").read_text())
T, C, I, PQ, CQ = (
    f"ecommerce-{name}-service"
    for name in ("tenant", "catalog", "image", "product-query", "category-query")
)
PROMISES = {
    (T, "SENDS", "TenantUpdated"),
    (C, "SENDS", "ProductEvents"),
    (C, "SENDS", "CategoryEvents"),
    (C, "SENDS", "ProductUpdated"),
    (I, "SENDS", "ProductImagePromoted"),
    (I, "RECEIVES", "ProductUpdated"),
    (PQ, "RECEIVES", "ProductUpdated"),
    (PQ, "RECEIVES", "ProductImagePromoted"),
}
MEMBERSHIPS = {
    ("store-provisioning", T),
    ("catalog-management", C),
    ("catalog-management", I),
    ("storefront", PQ),
    ("storefront", CQ),
}
EVENT_TOPICS = {
    "TenantUpdated": "tenant.tenant.events",
    "ProductEvents": "catalog.product.events",
    "CategoryEvents": "catalog.category.events",
    "ProductUpdated": "catalog.product.events",
    "ProductImagePromoted": "catalog.product.events",
}


def _config(**overrides) -> EventCatalogSourceConfig:
    values = {"id": IDS["configured_source_id"], "root": PACKAGE, "environment": "local"}
    return EventCatalogSourceConfig(**{**values, **overrides})


def _map() -> ArchitectureModel:
    [loaded] = EventCatalogSourceDiscoverer(_config()).discover().loaded_sources
    outcome = EventCatalogSourceAdapter().map(
        loaded,
        service_identity=cast(Any, None),
        shared_identity=cast(Any, None),
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )
    assert outcome.result is IngestionResult.ACCEPTED
    return outcome.model


def test_the_source_and_evidence_ids_equal_the_vectors() -> None:
    source = event_catalog_source_instance_id(
        configured_source_id=IDS["configured_source_id"], environment=IDS["environment"]
    )
    assert source == IDS["source_instance_id"]
    assert catalog_evidence_id(source) == IDS["evidence_id"]


def test_the_adapter_maps_the_i1_package_to_the_expected_promise_record() -> None:
    model = _map()
    assert {(p.service_name, p.direction, p.event_id) for p in model.catalog_promises} == PROMISES
    assert len(model.catalog_promises) == 8
    assert {p.id for p in model.catalog_promises} == set(IDS["promises"].values())
    assert {
        f"{p.service_name}|{p.direction}|{p.event_id}": p.id for p in model.catalog_promises
    } == (IDS["promises"])
    assert {
        (m.bounded_context_id, m.service_name) for m in model.catalog_memberships
    } == MEMBERSHIPS
    assert {
        f"{m.bounded_context_id}|{m.service_name}": m.id for m in model.catalog_memberships
    } == (IDS["memberships"])
    assert {t.event_id: t.topic for t in model.catalog_event_topics} == EVENT_TOPICS
    assert {t.event_id: t.id for t in model.catalog_event_topics} == IDS["event_topics"]
    [evidence] = model.catalog_evidence
    assert (evidence.id, evidence.source_revision) == (IDS["evidence_id"], IDS["source_revision"])
    assert {p.environment for p in model.catalog_promises} == {"local"}


def test_a_promise_never_manufactures_current_state() -> None:
    """Doctrine §4.3: the adapter emits only the internal carriers."""
    model = _map()
    assert not (model.services or model.topics or model.subscriptions or model.relations)
    assert not (model.brokers or model.pubsub_declarations or model.messages)


def test_a_shared_id_or_environment_rejects_every_registration_involved() -> None:
    a, b = _config(id="a"), _config(id="b", root=PACKAGE / "elsewhere")
    assert duplicate_registrations([a, _config(id="a", environment="prod")]) == {"a"}
    assert duplicate_registrations([a, b]) == {"a", "b"}
    assert duplicate_registrations([a, _config(id="c", environment="prod")]) == frozenset()
