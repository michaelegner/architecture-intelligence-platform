"""v0.7.0 I3.4a - the read cost of the API consumer usage answer (I3 spec §13 "I3.4": bounds and
observed read cost; §14 "bounded enumeration ... no Cartesian product").

Records observed values only: no threshold, SLO or optimisation. Like the v0.6 locality benchmark,
the per-phase costs are measured by calling each real function on its own, not logged by production
code.

Each point builds one clean graph through real production write paths, as an operator would:
- an APISIX configuration capture (`app.sources.model.ApisixSourceConfig`): C consumers and R Routes,
  each Route with a `consumer-restriction` allow-list of W consumers and the `aip/service` label that
  resolves it to `service:order-service`;
- an APISIX measurement source (`ApisixMeasurementSourceConfig`): attributed upstream series for some
  of the allow-listed pairs and for E consumers that are not allow-listed;
- the bundled `examples/` OpenAPI, which defines `service:order-service`;
all imported with `app.graph.import_runs.run_all_configured_sources`.

It then times, as medians of `REPEATS` runs:
- the end-to-end `ArchitectureIntelligenceService.get_api_consumer_usage` (first page, `limit` 200);
- each phase on its own: the whole canonical snapshot state read (`canonical_snapshot_state`, which
  the answer is projected from) and its fingerprint, the projection (`project_api_consumer_usage`),
  serialization (`model_dump_json`), and the evidence mode over at most 20 of the page's refs
  (`get_api_consumer_usage_evidence`) next to the finite ref map it rebuilds for the whole selection.

It also records the first page's counts, a full cursor walk (pages, rows seen and distinct, per-page
outcome), the stable-read retries, and the bounds actually reached: the qualification rows against
`consumers * routes` (the bounded union of configured and observed pairs, never a Cartesian product),
the rows per page and the refs per evidence request.

Points:
- row universe 100 / 1,000 / 5,000 / 10,000 for an `APPLICATION_SERVICE` target that selects every
  Route, so the largest point pages 50 times and `consumers * routes` is ten times the rows;
- a `GATEWAY_ROUTE` target (rows bounded by one Route's pairs);
- an invalid window (counts omitted, rows still enumerated, `WINDOW_NOT_VALID`).

Dev/qualification tooling only, like the other benchmarks: never imported by `app/`, never in the
production image. Boots its own disposable Testcontainers Neo4j. An I3 run is not I4 evidence: it
records its own commit and carries no final-candidate claim.

    uv run python -m benchmarks.api_usage_cost --profile smoke --candidate-sha <full-sha>
    uv run python -m benchmarks.api_usage_cost --profile i3 --out <path.json> --candidate-sha <full-sha>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import neo4j

from app.architecture_intelligence import repository
from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageData,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.api_usage_evidence import evidence_candidates
from app.architecture_intelligence.api_usage_projection import (
    ApiUsageScope,
    open_scope,
    project_api_consumer_usage,
)
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.import_runs import run_all_configured_sources
from app.settings import SourcesConfig
from app.sources.apisix_measurement_contract import END_FILE, MANIFEST_FILE, START_FILE
from app.sources.model import (
    ApisixMeasurementSourceConfig,
    ApisixSourceConfig,
    FilesystemSourceConfig,
)
from app.version import package_version
from benchmarks.scoped_churn_cost import _git, _median_ms, _reset
from benchmarks.snapshot_read_cost import collect_runtime_metadata

NAME = "api_usage_cost"
SCHEMA_VERSION = "aip-benchmark-api-usage-cost/1"
DATABASE = "neo4j"
REPEATS = 5
PAGE_LIMIT = 200
MAX_EVIDENCE_REFS = 20

ROOT = Path(__file__).resolve().parents[1]
VECTORS = ROOT / "docs/specifications/0.7.0"
GATEWAY = "gw-prod-1"
ENVIRONMENT = "prod"
SERVICE = "service:order-service"


@dataclass(frozen=True)
class Point:
    """One measured world. Route r allow-lists `whitelist` consumers, so the configured pairs are
    `routes * whitelist`; each Route also has `observed` attributed upstream series on allow-listed
    consumers and `extra` on consumers that are not allow-listed (observed-only pairs). The
    qualification rows are the bounded union, `routes * (whitelist + extra)`; a Cartesian product
    would be `consumers * routes`."""

    name: str
    consumers: int
    routes: int
    whitelist: int
    observed: int
    extra: int = 0
    target: str = "service"  # "service" selects every Route; "route" selects Route 0
    invalid_window: bool = False

    @property
    def rows(self) -> int:
        per_route = self.whitelist + self.extra
        return per_route if self.target == "route" else self.routes * per_route

    def __post_init__(self) -> None:
        assert self.whitelist + self.extra <= self.consumers, "distinct consumers per Route"
        assert self.observed <= self.whitelist


PROFILES: dict[str, tuple[Point, ...]] = {
    "smoke": (
        Point("rows", consumers=12, routes=4, whitelist=5, observed=2, extra=1),
        Point("route-target", consumers=12, routes=4, whitelist=5, observed=2, target="route"),
        Point(
            "invalid-window", consumers=12, routes=4, whitelist=5, observed=2, invalid_window=True
        ),
    ),
    "i3": (
        Point("rows", consumers=20, routes=10, whitelist=10, observed=2),
        Point("rows", consumers=100, routes=20, whitelist=40, observed=5, extra=10),
        Point("rows", consumers=500, routes=50, whitelist=90, observed=10, extra=10),
        Point("rows", consumers=1000, routes=100, whitelist=90, observed=20, extra=10),
        Point(
            "route-target",
            consumers=200,
            routes=20,
            whitelist=100,
            observed=10,
            extra=10,
            target="route",
        ),
        Point(
            "invalid-window",
            consumers=100,
            routes=20,
            whitelist=40,
            observed=5,
            invalid_window=True,
        ),
    ),
}


def _consumer(index: int) -> str:
    return f"consumer-{index:05d}"


def _route(index: int) -> str:
    return f"route-{index:04d}"


def _members(point: Point, route: int) -> tuple[list[str], list[str]]:
    """The allow-listed consumers of one Route, and the observed-only extras."""
    start = (route * 7) % point.consumers
    indexes = [
        (start + offset) % point.consumers for offset in range(point.whitelist + point.extra)
    ]
    names = [_consumer(i) for i in indexes]
    return names[: point.whitelist], names[point.whitelist :]


def _metric(consumer: str, route: str, count: int) -> str:
    return (
        f'apisix_http_status{{code="200",consumer="{consumer}",llm_model="",matched_host="",'
        f'matched_uri="/{route}",request_llm_model="",request_type="traditional_http",'
        f'response_source="upstream",route="{route}",service=""}} {count}'
    )


def write_gateway(point: Point, root: Path) -> ApisixSourceConfig:
    base = json.loads((VECTORS / "i1-vectors/configured-access.json").read_text())["base_capture"]
    routes = [
        {
            "id": _route(r),
            "uri": f"/{_route(r)}",
            "labels": {"aip/service": SERVICE},
            "plugins": {
                "key-auth": {},
                "consumer-restriction": {
                    "type": "consumer_name",
                    "whitelist": _members(point, r)[0],
                },
            },
        }
        for r in range(point.routes)
    ]
    document = {
        **base,
        "gateway_instance_id": GATEWAY,
        "environment": ENVIRONMENT,
        "consumers": [
            {"username": _consumer(i), "credential_ids": []} for i in range(point.consumers)
        ],
        "routes": routes,
        "services": [],
        "upstreams": [],
        "plugin_configs": [],
        "consumer_groups": [],
        "global_rules": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    config = ApisixSourceConfig(id="apisix-gateway", root=root, gateway_instance_id=GATEWAY)
    (root / config.capture_relative_path).write_text(json.dumps(document))
    return config


def write_measurement(point: Point, root: Path) -> ApisixMeasurementSourceConfig:
    base = json.loads((VECTORS / "i2-vectors/manifest-rejections.json").read_text())[
        "base_manifest"
    ]
    start, end = [], []
    for r in range(point.routes):
        allowed, extra = _members(point, r)
        for consumer in [*allowed[: point.observed], *extra]:
            start.append(_metric(consumer, _route(r), 1))
            end.append(_metric(consumer, _route(r), 4))
    start_bytes = "".join(f"{line}\n" for line in sorted(start)).encode()
    end_bytes = "".join(f"{line}\n" for line in sorted(end)).encode()
    manifest = {
        **base,
        "gateway_instance_id": GATEWAY,
        "environment": ENVIRONMENT,
        "route_coverage": {_route(r): True for r in range(point.routes)},
        "start_sha256": hashlib.sha256(start_bytes).hexdigest(),
        "end_sha256": hashlib.sha256(end_bytes).hexdigest(),
        **({"end_settled": False} if point.invalid_window else {}),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / START_FILE).write_bytes(start_bytes)
    (root / END_FILE).write_bytes(end_bytes)
    (root / MANIFEST_FILE).write_text(json.dumps(manifest))
    return ApisixMeasurementSourceConfig(
        id="apisix-metrics", root=root, gateway_instance_id=GATEWAY, environment=ENVIRONMENT
    )


def build(driver: neo4j.Driver, point: Point, work_dir: Path) -> dict[str, Any]:
    """One clean graph through the real import path; returns the import wall time."""
    _reset(driver)
    gateway = write_gateway(point, work_dir / "gateway")
    measurement = write_measurement(point, work_dir / "metrics")
    examples = FilesystemSourceConfig(id="examples", root=ROOT / "examples")
    started = time.perf_counter()
    run_all_configured_sources(
        SourcesConfig(
            directories=[examples], gateways=[gateway], gateway_measurements=[measurement]
        ),
        driver=driver,
        database=DATABASE,
    )
    return {"import_seconds": round(time.perf_counter() - started, 3)}


def _query(
    state: dict, point: Point, *, cursor: str | None = None, snapshot_id: str | None = None
) -> ApiConsumerUsageQueryRequest:
    window = state["api_usage_v1"]["windows"][0]
    if point.target == "route":
        route = next(
            r for r in state["gateway_configuration_v1"]["routes"] if r["route_id"] == _route(0)
        )
        target = {"kind": "GATEWAY_ROUTE", "id": route["id"]}
    else:
        target = {"kind": "APPLICATION_SERVICE", "id": SERVICE}
    return ApiConsumerUsageQueryRequest.model_validate(
        {
            "mode": "query",
            "target": target,
            "gateway_instance_id": GATEWAY,
            "environment": ENVIRONMENT,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            "limit": PAGE_LIMIT,
            **({"cursor": cursor, "snapshot_id": snapshot_id} if cursor else {}),
        }
    )


def _data(answer: ApiConsumerUsageAnswer) -> ApiConsumerUsageData:
    assert isinstance(answer.data, ApiConsumerUsageData)
    return answer.data


def _counts(answer: ApiConsumerUsageAnswer) -> dict[str, Any]:
    data = _data(answer)
    summary = data.association_summary
    return {
        "rows": len(data.rows),
        "selected_routes": len(data.selected_routes),
        "window_valid": data.window.valid,
        "has_next_cursor": data.page.next_cursor is not None,
        "limitations": [limitation.code.value for limitation in answer.limitations],
        "target_service_summary": (
            summary.target_service.model_dump() if summary and summary.target_service else None
        ),
    }


def walk(service: ArchitectureIntelligenceService, state: dict, point: Point) -> dict[str, Any]:
    """Every page of the query, by cursor, on one snapshot."""
    pages: list[dict[str, Any]] = []
    seen: list[tuple[str, str]] = []
    cursor, snapshot_id = None, None
    while True:
        answer = service.get_api_consumer_usage(
            _query(state, point, cursor=cursor, snapshot_id=snapshot_id)
        )
        if answer.data is None:
            pages.append({"refusal": answer.limitations[0].code.value})
            break
        data = _data(answer)
        seen += [(row.consumer.id, row.gateway_route.id) for row in data.rows]
        pages.append({"rows": len(data.rows), "outcome": answer.outcome.value})
        cursor = data.page.next_cursor
        assert answer.snapshot is not None
        snapshot_id = answer.snapshot.snapshot_id
        if cursor is None:
            break
    return {
        "pages": len(pages),
        "rows_seen": len(seen),
        "distinct_rows_seen": len(set(seen)),
        "max_rows_per_page": max((page.get("rows", 0) for page in pages), default=0),
        "refusals": sum(1 for page in pages if "refusal" in page),
        "per_page_outcomes": sorted({page.get("outcome", "REFUSAL") for page in pages}),
    }


def _stable_read_retries(operation: Callable[[], object]) -> int:
    """Attempts minus one: each stable-read attempt reads the revision twice (spec §19.1)."""
    calls: list[int] = []
    original = repository.read_revision

    def counting(session):
        calls.append(1)
        return original(session)

    repository.read_revision = counting
    try:
        operation()
    finally:
        repository.read_revision = original
    return max(len(calls) // 2 - 1, 0)


def _bounds(state: dict, point: Point, first: ApiConsumerUsageAnswer) -> dict[str, Any]:
    usage, gateway = state["api_usage_v1"], state["gateway_configuration_v1"]
    rows = usage["qualification_rows"]
    union = {(r["consumer_id"], r["route_id"]) for r in rows}
    configured = {(a["consumer_id"], a["route_id"]) for a in gateway["configured_access"]}
    observed = {(i["consumer_id"], i["route_id"]) for i in usage["interactions"]}
    return {
        "consumers": len(gateway["consumers"]),
        "routes": len(gateway["routes"]),
        "cartesian_pairs": len(gateway["consumers"]) * len(gateway["routes"]),
        "configured_pairs": len(configured),
        "observed_pairs": len(observed),
        "qualification_rows": len(rows),
        "rows_equal_the_bounded_union": union == configured | observed and len(rows) == len(union),
        "rows_of_the_target": point.rows,
        "page_limit": PAGE_LIMIT,
        "rows_on_first_page": len(_data(first).rows),
    }


def measure_reads(
    driver: neo4j.Driver,
    service: ArchitectureIntelligenceService,
    point: Point,
    configured_producer: Producer,
) -> dict[str, Any]:
    with driver.session(database=DATABASE) as session:
        state = repository.canonical_snapshot_state(session, coverage_qualification_enabled=True)
        query = _query(state, point)
        first = service.get_api_consumer_usage(query)
        assert first.producer == configured_producer and first.snapshot is not None
        data = _data(first)
        snapshot = SnapshotRef(
            snapshot_id=first.snapshot.snapshot_id, model_revision=first.snapshot.model_revision
        )
        refs = sorted(
            {
                *data.window.evidence_refs,
                *(ref for route in data.selected_routes for ref in route.evidence_refs),
                *(ref for row in data.rows for ref in row.evidence_refs),
            }
        )[:MAX_EVIDENCE_REFS]
        evidence = ApiConsumerUsageEvidenceRequest(
            mode="evidence",
            snapshot_id=snapshot.snapshot_id,
            target=query.target,
            gateway_instance_id=query.gateway_instance_id,
            environment=query.environment,
            window_start=query.window_start,
            window_end=query.window_end,
            evidence_refs=refs,
        )
        opened = open_scope(
            state, query.context(), snapshot=snapshot, asserted_snapshot_ids=[snapshot.snapshot_id]
        )
        assert isinstance(opened, ApiUsageScope)
        route_ids = opened.select(query.target)
        timings = {
            "end_to_end_ms_median": _median_ms(lambda: service.get_api_consumer_usage(query)),
            "state_read_ms_median": _median_ms(
                lambda: repository.canonical_snapshot_state(
                    session, coverage_qualification_enabled=True
                )
            ),
            "snapshot_fingerprint_ms_median": _median_ms(
                lambda: repository.snapshot_fingerprint(state)
            ),
            "projection_ms_median": _median_ms(
                lambda: project_api_consumer_usage(
                    query, state, snapshot=snapshot, producer=configured_producer
                )
            ),
            "serialization_ms_median": _median_ms(first.model_dump_json),
            "evidence_lookup_ms_median": _median_ms(
                lambda: service.get_api_consumer_usage_evidence(evidence)
            ),
            "evidence_ref_map_ms_median": _median_ms(
                lambda: evidence_candidates(opened, route_ids, None)
            ),
        }
        graph = {
            "nodes": session.run("MATCH (n) RETURN count(n) AS n").single()["n"],
            "relationships": session.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"],
        }
        evidence_answer = service.get_api_consumer_usage_evidence(evidence)
    evidence_data = evidence_answer.data
    return {
        "retained_graph": graph,
        "bounds": {**_bounds(state, point, first), "evidence_refs_per_request": len(refs)},
        "first_page": _counts(first),
        "outcome": first.outcome.value,
        "evidence": {
            "refs_looked_up": len(refs),
            "outcome": evidence_answer.outcome.value,
            "resolved": sum(
                1
                for entry in getattr(evidence_data, "entries", [])
                if entry.status.value == "RESOLVED"
            ),
            "ref_map_size": len(evidence_candidates(opened, route_ids, None)),
        },
        "timings": timings,
        "walk": walk(service, state, point),
        "stable_read_retries": _stable_read_retries(lambda: service.get_api_consumer_usage(query)),
    }


def measure_point(
    driver: neo4j.Driver, point: Point, work_dir: Path, configured_producer: Producer
) -> dict[str, Any]:
    ingestion = build(driver, point, work_dir)
    service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=configured_producer
    )
    return {
        "point": point.name,
        "target": point.target,
        "invalid_window": point.invalid_window,
        "ingestion": ingestion,
        **measure_reads(driver, service, point, configured_producer),
    }


def _pins() -> dict[str, str]:
    """The inputs of the run: this package, the published 0.7 schemas and the 0.7 specification and
    vector files. Recorded results are not inputs (the artifact would pin itself)."""
    roots = [ROOT / "benchmarks", ROOT / "schemas/architecture_intelligence/v0.7", VECTORS]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.endswith("-cost.json")
    }


def run(profile: str, driver: neo4j.Driver, configured_producer: Producer) -> dict[str, Any]:
    with driver.session(database=DATABASE) as session:
        neo4j_version = session.run(
            "CALL dbms.components() YIELD versions RETURN versions[0] AS v"
        ).single()["v"]
    with tempfile.TemporaryDirectory(prefix="aip-api-usage-cost-") as work:
        points = [
            measure_point(driver, point, Path(work) / f"{index:02d}", configured_producer)
            for index, point in enumerate(PROFILES[profile])
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": NAME,
        "profile": profile,
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _git("rev-parse", "HEAD"),
        "dirty_worktree": bool(_git("status", "--porcelain")),
        "repeats": REPEATS,
        "page_limit": PAGE_LIMIT,
        "runtime": collect_runtime_metadata(neo4j_version=neo4j_version),
        "points": points,
    }


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    parser = argparse.ArgumentParser(prog="python -m benchmarks.api_usage_cost")
    parser.add_argument("--profile", choices=sorted(PROFILES), default="smoke")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--candidate-sha", required=True)
    args = parser.parse_args(argv)
    head = _git("rev-parse", "HEAD")
    if args.candidate_sha != head:
        raise SystemExit(f"--candidate-sha {args.candidate_sha} is not HEAD ({head})")
    if _git("status", "--porcelain"):
        raise SystemExit("the worktree is not clean: a recorded run needs a committed checkout")
    configured_producer = Producer(
        name="architecture-intelligence-platform",
        version=package_version(),
        build_revision=args.candidate_sha,
    )
    with Neo4jContainer(
        "neo4j:5.26.32@sha256:f1e52d4dc6da122468c4a3c1050a4f5e117f6d3268625237c34d49166f0d6082"
    ) as container:
        driver = container.get_driver()
        try:
            result = run(args.profile, driver, configured_producer)
            result["input_pins"] = _pins()
            result["producer"] = configured_producer.model_dump(mode="json")
            result["container_image"] = container.image
            result["command"] = sys.argv
        finally:
            driver.close()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
