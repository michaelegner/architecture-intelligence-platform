"""v0.7.0 I1.4 internal, source-owned APISIX gateway carriers (I1.1 contract §3-§4) - never public
canonical entities, never NL/MCP-visible, never relationships to a public entity. Ids follow the
independent vectors V01-V07 and V13 in `docs/specifications/0.7.0/i1-vectors/ids.json`.

The source's own evidence record is `GatewaySourceEvidence`, not a `Provenance`: a `Provenance` is
written as an `:Evidence` node, which the public evidence reads and the natural-language Cypher guard
treat as publicly reachable (only the Kubernetes source type is carved out of them). A dedicated
internal carrier keeps gateway evidence off every public surface without widening those guards;
public exposure is I3's decision (contract §4 amended in I1.4).
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.common.encoding import length_delimited, sha256_hex, utf8

GATEWAY_CONSUMER_LABEL = "GatewayConsumer"
GATEWAY_ROUTE_LABEL = "GatewayRoute"
GATEWAY_SERVICE_LABEL = "GatewayService"
GATEWAY_CONFIGURED_ACCESS_LABEL = "GatewayConfiguredAccess"
GATEWAY_LIMITATION_LABEL = "GatewayLimitation"
GATEWAY_SOURCE_EVIDENCE_LABEL = "GatewaySourceEvidence"

CONSUMER_RESTRICTION_ALLOW_LIST: Literal["CONSUMER_RESTRICTION_ALLOW_LIST"] = (
    "CONSUMER_RESTRICTION_ALLOW_LIST"
)


def _owned(prefix: str, *parts: str) -> str:
    return f"{prefix}:owned:{sha256_hex(length_delimited(*(utf8(part) for part in parts)))}"


def gateway_consumer_id(gateway_instance_id: str, username: str) -> str:
    return _owned("gateway-consumer", gateway_instance_id, username)


def gateway_route_id(gateway_instance_id: str, route_id: str) -> str:
    return _owned("gateway-route", gateway_instance_id, route_id)


def gateway_service_id(gateway_instance_id: str, service_id: str) -> str:
    return _owned("gateway-service", gateway_instance_id, service_id)


def configured_access_id(consumer_id: str, route_id: str, rule_kind: str) -> str:
    return _owned("configured-access", consumer_id, route_id, rule_kind)


def gateway_limitation_id(gateway_instance_id: str, code: str, subject: str) -> str:
    return _owned("gateway-limitation", gateway_instance_id, code, subject)


def gateway_source_evidence_id(gateway_instance_id: str, source_revision: str) -> str:
    """`evidence:apisix:<sha256(ld(gateway_instance_id, source_revision))>` (vector V13)."""
    return f"evidence:apisix:{sha256_hex(length_delimited(utf8(gateway_instance_id), utf8(source_revision)))}"


class GatewayConsumer(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    username: str = Field(min_length=1)
    credential_ids: list[str] = Field(default_factory=list)
    created_index: int | None = None
    modified_index: int | None = None


class GatewayRoute(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    uri: str | None = None
    uris: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    service_id: str | None = None
    plugin_config_id: str | None = None
    upstream_id: str | None = None
    upstream_nodes: list[str] = Field(default_factory=list)
    # Neo4j cannot hold a nested map: RFC 8785 canonical JSON of the verbatim labels.
    labels_json: str = "{}"
    auth_plugins: list[str] = Field(default_factory=list)
    plugin_names: list[str] = Field(default_factory=list)
    created_index: int | None = None
    modified_index: int | None = None


class GatewayService(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    upstream_id: str | None = None
    upstream_nodes: list[str] = Field(default_factory=list)
    labels_json: str = "{}"
    plugin_names: list[str] = Field(default_factory=list)
    created_index: int | None = None
    modified_index: int | None = None


class GatewayConfiguredAccess(BaseModel):
    """A source-native allow-list fact (contract §4). It carries no usage, authorization or
    approval meaning."""

    id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    rule_kind: Literal["CONSUMER_RESTRICTION_ALLOW_LIST"] = CONSUMER_RESTRICTION_ALLOW_LIST
    polarity: Literal["ALLOW"] = "ALLOW"
    scope: Literal["ROUTE"] = "ROUTE"
    evidence_ids: list[str] = Field(min_length=1)
    source_revision: str = Field(min_length=1)


class GatewayLimitation(BaseModel):
    """A source fact recorded but not interpreted as access (contract §4 table)."""

    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    subject: str = Field(min_length=1)


class GatewaySourceEvidence(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    apisix_version: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    evidence_type: Literal["DECLARED"] = "DECLARED"
