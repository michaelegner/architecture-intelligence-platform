"""v0.7.0 I2.2b: the pure interpretation of a validated measurement fixture into the internal
measurement carriers (I2.1 contract §3-§5). No I/O. It joins nothing: consumer, Route, Operation and
Service reconciliation are I2.3, and qualification is I2.4. The expected results are the independent
vectors in `docs/specifications/0.7.0/i2-vectors/` (`series-deltas.json`, `ids.json`).

Every series present at either boundary is kept as a `MeasurementSeries`, so the consumer/route pairs
that I2.4's row universe needs survive whatever their status; only `DELTA` and `DELTA_FIRST_IN_WINDOW`
carry a delta. An invalid window has no usable delta at all: its series are kept as `WINDOW_INVALID`
and no series limitation is recorded (the window reasons already explain it; contract §3).
"""

from dataclasses import dataclass

from app.canonical.gateway_measurement import (
    COUNTER_DECREASED,
    MAPPING_ROUTE_OPERATION,
    MAPPING_TARGET_ROUTE,
    MAPPING_TARGET_SERVICE,
    SERIES_ONE_BOUNDARY,
    MeasurementEvidence,
    MeasurementLimitation,
    MeasurementMappingEntry,
    MeasurementSeries,
    MeasurementWindow,
    measurement_limitation_id,
    measurement_mapping_entry_id,
    measurement_series_id,
)
from app.common.jcs import JSONValue, canonical_json_bytes
from app.sources.apisix_measurement_contract import (
    MappingArtifact,
    ValidatedMeasurement,
    measurement_evidence_id,
    measurement_window_id,
)

_USABLE = ("DELTA", "DELTA_FIRST_IN_WINDOW")


@dataclass(frozen=True)
class MeasurementMapping:
    window: MeasurementWindow
    evidence: MeasurementEvidence
    series: list[MeasurementSeries]
    limitations: list[MeasurementLimitation]
    mapping_entries: list[MeasurementMappingEntry]

    @property
    def limitation_count(self) -> int:
        """Window reasons plus series limitations: the number the single diagnostic reports."""
        return len(self.window.window_reasons) + len(self.limitations)


def _json(value: dict[str, JSONValue]) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def map_measurement(
    validated: ValidatedMeasurement,
    mapping: MappingArtifact | None,
    *,
    source_instance_id: str,
) -> MeasurementMapping:
    manifest = validated.manifest
    window_id = measurement_window_id(manifest)
    evidence_id = measurement_evidence_id(manifest)
    reasons = validated.window_reasons
    window = MeasurementWindow(
        id=window_id,
        source_instance_id=source_instance_id,
        gateway_instance_id=manifest.gateway_instance_id,
        environment=manifest.environment,
        apisix_version=manifest.apisix_version,
        window_start=manifest.window_start,
        window_end=manifest.window_end,
        start_settled=manifest.start_settled,
        end_settled=manifest.end_settled,
        no_restart=manifest.no_restart,
        start_stable_seconds=manifest.start_stable_seconds,
        end_stable_seconds=manifest.end_stable_seconds,
        disabled_labels=list(manifest.disabled_labels),
        route_coverage_json=_json(dict(sorted(manifest.route_coverage.items()))),
        window_reasons=reasons,
        evidence_ids=[evidence_id],
    )
    evidence = MeasurementEvidence(
        id=evidence_id,
        source_instance_id=source_instance_id,
        gateway_instance_id=manifest.gateway_instance_id,
        environment=manifest.environment,
        apisix_version=manifest.apisix_version,
        window_start=manifest.window_start,
        window_end=manifest.window_end,
        start_sha256=manifest.start_sha256,
        end_sha256=manifest.end_sha256,
    )
    series: list[MeasurementSeries] = []
    limitations: dict[str, MeasurementLimitation] = {}
    for item in validated.series_deltas():
        labels = item.series.labels
        usable = not reasons and item.status in _USABLE
        series.append(
            MeasurementSeries(
                id=measurement_series_id(window_id, item.series.key),
                window_id=window_id,
                gateway_instance_id=manifest.gateway_instance_id,
                environment=manifest.environment,
                window_start=manifest.window_start,
                window_end=manifest.window_end,
                route=labels["route"],
                consumer=labels["consumer"],
                code=labels["code"],
                response_source=labels["response_source"],
                status=item.status if not reasons else "WINDOW_INVALID",
                request_count_delta=item.delta if usable else None,
                labels_json=_json(dict(sorted(labels.items()))),
                evidence_ids=[evidence_id],
            )
        )
        if not reasons and not usable:
            code = COUNTER_DECREASED if item.status == "DECREASED" else SERIES_ONE_BOUNDARY
            limitation_id = measurement_limitation_id(
                window_id, code, labels["route"], labels["response_source"]
            )
            limitations[limitation_id] = MeasurementLimitation(
                id=limitation_id,
                window_id=window_id,
                code=code,
                route=labels["route"],
                response_source=labels["response_source"],
            )
    entries: dict[str, MeasurementMappingEntry] = {}
    if mapping is not None:
        rows = [
            (MAPPING_ROUTE_OPERATION, row.route_id, row.operation_id)
            for row in mapping.route_operation
        ] + [
            (
                MAPPING_TARGET_ROUTE if row.kind == "route" else MAPPING_TARGET_SERVICE,
                row.id,
                row.service_id,
            )
            for row in mapping.target_service
        ]
        for kind, source_id, target_id in rows:
            entry_id = measurement_mapping_entry_id(
                manifest.gateway_instance_id, manifest.environment, kind, source_id, target_id
            )
            entries[entry_id] = MeasurementMappingEntry(
                id=entry_id,
                gateway_instance_id=manifest.gateway_instance_id,
                environment=manifest.environment,
                kind=kind,
                source_id=source_id,
                target_id=target_id,
            )
    return MeasurementMapping(
        window=window,
        evidence=evidence,
        series=sorted(series, key=lambda s: s.id),
        limitations=sorted(limitations.values(), key=lambda item: item.id),
        mapping_entries=sorted(entries.values(), key=lambda e: e.id),
    )
