"""v0.7.0 I2.2b internal, source-owned APISIX measurement carriers (I2.1 contract §4) - never public
canonical entities, never NL/MCP-visible, never relationships to a public entity. Ids follow the
independent vectors M04, M05 and M10-M12 in `docs/specifications/0.7.0/i2-vectors/ids.json`.

Like the I1 gateway evidence, the measurement evidence is a dedicated carrier, not a `Provenance`: a
`Provenance` is written as an `:Evidence` node, which the public evidence reads and the
natural-language Cypher guard treat as publicly reachable. Public exposure is I3's decision.

Consumer usernames live only in `MeasurementSeries.consumer` / `labels_json` (internal-only); no
diagnostic ever carries one.
"""

from pydantic import BaseModel, Field

from app.common.encoding import length_delimited, sha256_hex, utf8

MEASUREMENT_WINDOW_LABEL = "MeasurementWindow"
MEASUREMENT_EVIDENCE_LABEL = "MeasurementEvidence"
MEASUREMENT_SERIES_LABEL = "MeasurementSeries"
MEASUREMENT_LIMITATION_LABEL = "MeasurementLimitation"
MEASUREMENT_MAPPING_ENTRY_LABEL = "MeasurementMappingEntry"

# Series-level limitation codes (contract §7). Window reasons live on the window carrier.
SERIES_ONE_BOUNDARY = "GWM_SERIES_ONE_BOUNDARY"
COUNTER_DECREASED = "GWM_COUNTER_DECREASED"

# Mapping entry kinds (contract §5): the two Route/Service target kinds are distinct objects.
MAPPING_ROUTE_OPERATION = "route_operation"
MAPPING_TARGET_ROUTE = "target_service_route"
MAPPING_TARGET_SERVICE = "target_service_service"


def _owned(prefix: str, *parts: str) -> str:
    return f"{prefix}:owned:{sha256_hex(length_delimited(*(utf8(part) for part in parts)))}"


def measurement_series_id(window_id: str, series_key: str) -> str:
    """`measurement-series:owned:<sha256(ld(window id, series key))>` (vector M10); the series key is
    the full label string between the braces (contract §2.1)."""
    return _owned("measurement-series", window_id, series_key)


def measurement_limitation_id(window_id: str, code: str, route: str, response_source: str) -> str:
    """`measurement-limitation:owned:<sha256(ld(window id, code, route, response_source))>` (M11)."""
    return _owned("measurement-limitation", window_id, code, route, response_source)


def measurement_mapping_entry_id(
    gateway_instance_id: str, environment: str, kind: str, source_id: str, target_id: str
) -> str:
    """`measurement-mapping:owned:<sha256(ld(gateway_instance_id, environment, kind, source id,
    target id))>` (M12). Two entries naming different targets for one object are distinct ids: that
    disagreement is a reconciliation input (I2.3), never collapsed here."""
    return _owned(
        "measurement-mapping", gateway_instance_id, environment, kind, source_id, target_id
    )


class MeasurementWindow(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    apisix_version: str = Field(min_length=1)
    window_start: str = Field(min_length=1)
    window_end: str = Field(min_length=1)
    start_settled: bool
    end_settled: bool
    no_restart: bool
    start_stable_seconds: int = Field(ge=0)
    end_stable_seconds: int = Field(ge=0)
    disabled_labels: list[str] = Field(default_factory=list)
    # Neo4j cannot hold a nested map: RFC 8785 canonical JSON of `{route id: bool}`.
    route_coverage_json: str = "{}"
    # Contract §3 window reasons (sorted); empty means the window is valid.
    window_reasons: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)


class MeasurementEvidence(BaseModel):
    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    apisix_version: str = Field(min_length=1)
    window_start: str = Field(min_length=1)
    window_end: str = Field(min_length=1)
    start_sha256: str = Field(min_length=64, max_length=64)
    end_sha256: str = Field(min_length=64, max_length=64)
    evidence_type: str = Field(default="OBSERVED", pattern=r"^OBSERVED$")


class MeasurementSeries(BaseModel):
    """One source series present at either boundary, with its contract §3 status. Only `DELTA` and
    `DELTA_FIRST_IN_WINDOW` carry a delta; the others keep the series' consumer/route identity (the
    qualification row universe is built from every attributed series, any status, I2.1 contract §7)
    without reading it as usage. `WINDOW_INVALID` marks every series of a window with a reason."""

    id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    window_start: str = Field(min_length=1)
    window_end: str = Field(min_length=1)
    route: str  # the metric's `route` label; may be empty for traffic that matched no Route
    consumer: str  # the metric's `consumer` label; empty = unattributed
    code: str
    response_source: str = Field(pattern=r"^(upstream|apisix)$")
    status: str = Field(
        pattern=r"^(DELTA|DELTA_FIRST_IN_WINDOW|DECREASED|ONE_BOUNDARY_START|ONE_BOUNDARY_END|WINDOW_INVALID)$"
    )
    request_count_delta: int | None = Field(default=None, ge=0)  # None unless the status is usable
    # Every source label (the series identity), RFC 8785 canonical JSON.
    labels_json: str
    evidence_ids: list[str] = Field(min_length=1)


class MeasurementLimitation(BaseModel):
    """A route-level fact that some series of this source had no usable delta. Carried per
    `(code, route, response_source)` so I2.4 can apply the route-wide coverage downgrade without the
    discarded series; it holds a route id, never a count or a value."""

    id: str = Field(min_length=1)
    window_id: str = Field(min_length=1)
    code: str = Field(pattern=r"^(GWM_SERIES_ONE_BOUNDARY|GWM_COUNTER_DECREASED)$")
    route: str
    response_source: str = Field(pattern=r"^(upstream|apisix)$")


class MeasurementMappingEntry(BaseModel):
    """A validated entry of the optional mapping artifact (contract §5), stored verbatim for I2.3."""

    id: str = Field(min_length=1)
    gateway_instance_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    kind: str = Field(pattern=r"^(route_operation|target_service_route|target_service_service)$")
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
