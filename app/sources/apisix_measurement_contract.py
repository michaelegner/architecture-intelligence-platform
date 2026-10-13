"""v0.7.0 I2.2: the APISIX measurement fixture contract (`aip-apisix-measurement/1`, plus the optional
`aip-apisix-mapping/1` artifact), shared by the separate capture tool
(`app.gateway_capture.apisix_metrics`, which writes it) and - from I2.2b - the replay source (which
validates it). Pure and dependency-free: no HTTP, no graph, no adapter. Every rule below is frozen by
`docs/specifications/0.7.0/i2-measurement-contract.md` (§2, §3, §4, §5, §8) and the independent
vectors in `docs/specifications/0.7.0/i2-vectors/`.

Nothing here ever returns, logs or raises a source *value*: a rejection carries a stable code and the
contract §8 result, nothing else.
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.common.encoding import length_delimited, sha256_hex, utf8

MANIFEST_SCHEMA = "aip-apisix-measurement/1"
MAPPING_SCHEMA = "aip-apisix-mapping/1"
METRIC_NAME = "apisix_http_status"

START_FILE = "apisix-metrics-start.txt"
END_FILE = "apisix-metrics-end.txt"
MANIFEST_FILE = "apisix-measurement-manifest.json"
MAPPING_FILE = "apisix-mapping.json"

# Contract §3: only the inspected release is compatible (review of #522).
SUPPORTED_APISIX_VERSION = "3.19.0"

# Contract §2: bounds. A violation is REJECTED_UNSUPPORTED / GWM_LIMIT_EXCEEDED.
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_EXTRACT_BYTES = 8 * 1024 * 1024
MAX_SERIES = 100_000
MAX_MAPPING_BYTES = 1024 * 1024

UPSTREAM = "upstream"
APISIX = "apisix"
RESPONSE_SOURCES = frozenset({UPSTREAM, APISIX})
REQUIRED_LABELS = frozenset({"code", "consumer", "response_source", "route"})

# Contract §8: the per-source result of each diagnostic.
RESULT_BY_CODE = {
    "GWM_MANIFEST_INVALID": "REJECTED_INVALID",
    "GWM_BINDING_MISMATCH": "REJECTED_INVALID",
    "GWM_EXTRACT_INVALID": "REJECTED_INVALID",
    "GWM_INSTANCE_MISMATCH": "REJECTED_INVALID",
    "GWM_MAPPING_INVALID": "REJECTED_INVALID",
    "GWM_SCHEMA_UNSUPPORTED": "REJECTED_UNSUPPORTED",
    "GWM_LIMIT_EXCEEDED": "REJECTED_UNSUPPORTED",
    "GWM_DUPLICATE_SOURCE": "REJECTED_CONFLICT",
}

# Contract §3: the window reasons (informational limitations, never rejections).
WINDOW_NOT_SETTLED = "GWM_WINDOW_NOT_SETTLED"
WINDOW_RESTART = "GWM_WINDOW_RESTART"
WINDOW_ORDER_INVALID = "GWM_WINDOW_ORDER_INVALID"
VERSION_INCOMPATIBLE = "GWM_VERSION_INCOMPATIBLE"

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAMPLE = re.compile(rf"^{METRIC_NAME}\{{(.*)\}} (\d+)$")
_LABEL = re.compile(r'([a-z_][a-z0-9_]*)="((?:[^"\\]|\\.)*)"')


class MeasurementRejection(Exception):
    """A stable rejection: the code and its contract §8 result, never a source value."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.result = RESULT_BY_CODE[code]


@dataclass(frozen=True)
class Manifest:
    gateway_instance_id: str
    environment: str
    apisix_version: str
    window_start: str
    window_end: str
    start_settled: bool
    end_settled: bool
    start_scrape_count: int
    end_scrape_count: int
    no_restart: bool
    disabled_labels: tuple[str, ...]
    route_coverage: Mapping[str, bool]
    start_sha256: str
    end_sha256: str


@dataclass(frozen=True)
class Series:
    key: str  # the full label string between the braces: the series identity (contract §2.1)
    labels: Mapping[str, str]
    value: int


@dataclass(frozen=True)
class SeriesDelta:
    series: Series  # the end-boundary series when present, else the start-boundary one
    status: str  # DELTA | DECREASED | ONE_BOUNDARY_START | ONE_BOUNDARY_END
    delta: int | None


@dataclass(frozen=True)
class ValidatedMeasurement:
    manifest: Manifest
    start: Mapping[str, Series]
    end: Mapping[str, Series]

    @property
    def window_reasons(self) -> list[str]:
        return window_reasons(self.manifest)

    def series_deltas(self) -> list[SeriesDelta]:
        return series_deltas(self.start, self.end)


# ---- extract -------------------------------------------------------------------------------


def extract_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def format_sample(labels: Mapping[str, str], value: int) -> str:
    """One normalized sample line (without the newline): labels in ascending name order."""
    body = ",".join(f'{name}="{labels[name]}"' for name in sorted(labels))
    return f"{METRIC_NAME}{{{body}}} {value}"


def render_extract(samples: Sequence[tuple[Mapping[str, str], int]]) -> bytes:
    """The canonical bytes of an extract: sorted, LF-terminated; empty = no series."""
    lines = sorted(format_sample(labels, value) for labels, value in samples)
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


def parse_extract(raw: bytes) -> dict[str, Series]:
    """Verify (never repair) a normalized extract (contract §2.1). Raises `GWM_EXTRACT_INVALID`."""
    invalid = MeasurementRejection("GWM_EXTRACT_INVALID")
    if not raw:
        return {}
    if b"\r" in raw or not raw.endswith(b"\n"):
        raise invalid
    try:
        lines = raw.decode("utf-8")[:-1].split("\n")
    except UnicodeDecodeError:
        raise invalid from None
    if len(lines) > MAX_SERIES:
        raise MeasurementRejection("GWM_LIMIT_EXCEEDED")
    if lines != sorted(set(lines)):  # strictly ascending: also rejects a duplicate series
        raise invalid
    series: dict[str, Series] = {}
    for line in lines:
        match = _SAMPLE.match(line)
        if not match:
            raise invalid
        body = match.group(1)
        pairs = _LABEL.findall(body)
        names = [name for name, _ in pairs]
        if ",".join(f'{n}="{v}"' for n, v in pairs) != body:
            raise invalid
        if names != sorted(set(names)) or "node" in names:
            raise invalid
        labels = dict(pairs)
        if (
            not REQUIRED_LABELS <= labels.keys()
            or labels["response_source"] not in RESPONSE_SOURCES
        ):
            raise invalid
        series[body] = Series(key=body, labels=labels, value=int(match.group(2)))
    return series


# ---- manifest ------------------------------------------------------------------------------


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError
    return dict(pairs)


def _load_object(raw: bytes, code: str, *, limit: int) -> dict[str, Any]:
    if len(raw) > limit:
        raise MeasurementRejection("GWM_LIMIT_EXCEEDED")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise MeasurementRejection(code) from None
    if not isinstance(document, dict):
        raise MeasurementRejection(code)
    return document


def _timestamp_ok(value: object) -> bool:
    if not isinstance(value, str) or not _TIMESTAMP.match(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _nonempty_str(document: Mapping[str, Any], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value:
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    return value


def _bool(document: Mapping[str, Any], name: str) -> bool:
    value = document.get(name)
    if not isinstance(value, bool):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    return value


def _scrape_count(document: Mapping[str, Any], boundary: str, *, settled: bool) -> int:
    count = document.get(f"{boundary}_scrape_count")
    if not isinstance(count, int) or isinstance(count, bool):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    if count < (2 if settled else 1):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    return count


def parse_manifest(document: Mapping[str, Any]) -> Manifest:
    """Contract §2.2 steps 1-2: schema, then field presence/types/consistency."""
    schema = document.get("schema")
    if not isinstance(schema, str):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    if schema != MANIFEST_SCHEMA:
        raise MeasurementRejection("GWM_SCHEMA_UNSUPPORTED")
    gateway_instance_id = _nonempty_str(document, "gateway_instance_id")
    environment = _nonempty_str(document, "environment")
    apisix_version = _nonempty_str(document, "apisix_version")
    for name in ("window_start", "window_end"):
        if not _timestamp_ok(document.get(name)):
            raise MeasurementRejection("GWM_MANIFEST_INVALID")
    start_settled, end_settled = _bool(document, "start_settled"), _bool(document, "end_settled")
    no_restart = _bool(document, "no_restart")
    start_count = _scrape_count(document, "start", settled=start_settled)
    end_count = _scrape_count(document, "end", settled=end_settled)
    labels = document.get("disabled_labels")
    if (
        not isinstance(labels, list)
        or not all(isinstance(label, str) for label in labels)
        or labels != sorted(set(labels))
    ):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    coverage = document.get("route_coverage")
    if not isinstance(coverage, dict) or not all(
        isinstance(route, str) and isinstance(flag, bool) for route, flag in coverage.items()
    ):
        raise MeasurementRejection("GWM_MANIFEST_INVALID")
    hashes = []
    for name in ("start_sha256", "end_sha256"):
        value = document.get(name)
        if not isinstance(value, str) or not _SHA256.match(value):
            raise MeasurementRejection("GWM_MANIFEST_INVALID")
        hashes.append(value)
    return Manifest(
        gateway_instance_id=gateway_instance_id,
        environment=environment,
        apisix_version=apisix_version,
        window_start=document["window_start"],
        window_end=document["window_end"],
        start_settled=start_settled,
        end_settled=end_settled,
        start_scrape_count=start_count,
        end_scrape_count=end_count,
        no_restart=no_restart,
        disabled_labels=tuple(labels),
        route_coverage=dict(coverage),
        start_sha256=hashes[0],
        end_sha256=hashes[1],
    )


def validate_fixture(
    manifest_bytes: bytes,
    start_bytes: bytes,
    end_bytes: bytes,
    *,
    gateway_instance_id: str,
    environment: str,
) -> ValidatedMeasurement:
    """The full contract §2.3 order: size bounds, manifest schema/fields, registration binding, hash
    binding, extract normalization. Raises `MeasurementRejection`; commits nothing itself."""
    if len(start_bytes) > MAX_EXTRACT_BYTES or len(end_bytes) > MAX_EXTRACT_BYTES:
        raise MeasurementRejection("GWM_LIMIT_EXCEEDED")
    manifest = parse_manifest(
        _load_object(manifest_bytes, "GWM_MANIFEST_INVALID", limit=MAX_MANIFEST_BYTES)
    )
    if manifest.gateway_instance_id != gateway_instance_id or manifest.environment != environment:
        raise MeasurementRejection("GWM_INSTANCE_MISMATCH")
    if (
        extract_sha256(start_bytes) != manifest.start_sha256
        or extract_sha256(end_bytes) != manifest.end_sha256
    ):
        raise MeasurementRejection("GWM_BINDING_MISMATCH")
    return ValidatedMeasurement(
        manifest=manifest, start=parse_extract(start_bytes), end=parse_extract(end_bytes)
    )


# ---- window and deltas (contract §3) ---------------------------------------------------------


def window_reasons(manifest: Manifest) -> list[str]:
    reasons: set[str] = set()
    if not (manifest.start_settled and manifest.end_settled):
        reasons.add(WINDOW_NOT_SETTLED)
    if not manifest.no_restart:
        reasons.add(WINDOW_RESTART)
    if manifest.window_start >= manifest.window_end:  # fixed-width UTC strings order lexically
        reasons.add(WINDOW_ORDER_INVALID)
    if manifest.apisix_version != SUPPORTED_APISIX_VERSION:
        reasons.add(VERSION_INCOMPATIBLE)
    return sorted(reasons)


def series_status(start: int | None, end: int | None) -> tuple[str, int | None]:
    if start is None and end is None:
        raise ValueError("a series exists at at least one boundary")
    if start is None:
        return "ONE_BOUNDARY_END", None
    if end is None:
        return "ONE_BOUNDARY_START", None
    if end < start:
        return "DECREASED", None
    return "DELTA", end - start


def series_deltas(start: Mapping[str, Series], end: Mapping[str, Series]) -> list[SeriesDelta]:
    deltas = []
    for key in sorted(start.keys() | end.keys()):
        first, last = start.get(key), end.get(key)
        status, delta = series_status(first.value if first else None, last.value if last else None)
        carrier = last if last is not None else first
        assert carrier is not None
        deltas.append(SeriesDelta(series=carrier, status=status, delta=delta))
    return deltas


# ---- mapping artifact (contract §5) ----------------------------------------------------------


@dataclass(frozen=True)
class RouteOperationMapping:
    route_id: str
    operation_id: str


@dataclass(frozen=True)
class TargetServiceMapping:
    kind: str  # "route" | "service"
    id: str
    service_id: str


@dataclass(frozen=True)
class MappingArtifact:
    route_operation: tuple[RouteOperationMapping, ...]
    target_service: tuple[TargetServiceMapping, ...]


def _entries(document: Mapping[str, Any], key: str, fields: frozenset[str]) -> list[dict[str, str]]:
    rows = document.get(key, [])
    if not isinstance(rows, list):
        raise MeasurementRejection("GWM_MAPPING_INVALID")
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise MeasurementRejection("GWM_MAPPING_INVALID")
        if not all(isinstance(value, str) and value for value in row.values()):
            raise MeasurementRejection("GWM_MAPPING_INVALID")
    return rows


def parse_mapping(raw: bytes, *, gateway_instance_id: str) -> MappingArtifact:
    """Contract §5. Duplicate or disagreeing entries are not rejected: they are reconciliation inputs."""
    document = _load_object(raw, "GWM_MAPPING_INVALID", limit=MAX_MAPPING_BYTES)
    if document.get("schema") != MAPPING_SCHEMA:
        raise MeasurementRejection("GWM_SCHEMA_UNSUPPORTED")
    if document.get("gateway_instance_id") != gateway_instance_id:
        raise MeasurementRejection("GWM_INSTANCE_MISMATCH")
    route_operation = _entries(document, "route_operation", frozenset({"route_id", "operation_id"}))
    target_service = _entries(document, "target_service", frozenset({"kind", "id", "service_id"}))
    if any(row["kind"] not in {"route", "service"} for row in target_service):
        raise MeasurementRejection("GWM_MAPPING_INVALID")
    return MappingArtifact(
        route_operation=tuple(
            RouteOperationMapping(row["route_id"], row["operation_id"]) for row in route_operation
        ),
        target_service=tuple(
            TargetServiceMapping(row["kind"], row["id"], row["service_id"])
            for row in target_service
        ),
    )


# ---- ids (contract §4, vectors M03-M05) --------------------------------------------------------


def _digest(*parts: str) -> str:
    return sha256_hex(length_delimited(*(utf8(part) for part in parts)))


def _window_inputs(manifest: Manifest) -> tuple[str, ...]:
    return (
        manifest.gateway_instance_id,
        manifest.environment,
        manifest.window_start,
        manifest.window_end,
        manifest.start_sha256,
        manifest.end_sha256,
    )


def measurement_window_id(manifest: Manifest) -> str:
    return f"measurement-window:owned:{_digest(*_window_inputs(manifest))}"


def measurement_evidence_id(manifest: Manifest) -> str:
    return f"evidence:apisix-measurement:{_digest(*_window_inputs(manifest))}"
