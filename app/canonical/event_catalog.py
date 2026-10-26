"""v0.8 I2 §2: internal, source-owned EventCatalog promise-record carriers - never public canonical
entities, never NL/MCP-visible, never relationships to a public entity. Ids follow the independent
vectors in `docs/specifications/0.8.0/i2-vectors/ids.json`.

A promise is environment-scoped, never broker-scoped, and is stored exactly as the catalog states
it: a promise never manufactures Current State, so no Service, Topic or relation is created here
(doctrine §4.3). Catalog service ids are resolved to declared Services per snapshot, in I2b.
"""

from typing import Literal

from pydantic import BaseModel, Field

CATALOG_PROMISE_LABEL = "CatalogPromise"
CATALOG_MEMBERSHIP_LABEL = "CatalogMembership"
CATALOG_EVENT_TOPIC_LABEL = "CatalogEventTopic"
CATALOG_EVIDENCE_LABEL = "CatalogEvidence"


class CatalogPromise(BaseModel):
    id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    direction: Literal["SENDS", "RECEIVES"]
    event_id: str = Field(min_length=1)
    event_version: str = Field(min_length=1)
    file: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class CatalogMembership(BaseModel):
    id: str = Field(min_length=1)
    bounded_context_id: str = Field(min_length=1)
    bounded_context_name: str = Field(min_length=1)
    owners: list[str]
    service_name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class CatalogEventTopic(BaseModel):
    id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    path: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class CatalogEvidence(BaseModel):
    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    # The registration that produced this source, so retirement can protect a still-configured
    # registration whose replacement did not commit.
    configured_source_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    catalog_digest: str = Field(min_length=64, max_length=64)
    lookup_digest: str = Field(min_length=64, max_length=64)
    source_revision: str = Field(min_length=1)
