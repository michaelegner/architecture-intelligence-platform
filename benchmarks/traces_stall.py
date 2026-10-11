"""Event-loop stall of `POST /v1/traces` (code-health review 2026-10-08, finding 1).

`post_traces` is `async def` and calls the synchronous `ingest_trace_spans`, so while a batch is
ingested the event loop serves nothing else. This measures how long other requests wait: for each
batch size it times an idle baseline of probe requests, then the same probes sent from a second
connection while one real batch is POSTed, and reports the ingest wall time, the probe count and
the worst and p95 probe latency during the ingest.

Measurement only, like the other benchmarks: no threshold, no change to the production path. It
boots its own disposable Testcontainers Neo4j, imports the bundled `examples/` landscape through the
real importer so the spans resolve and the ingest does real read and write work, and serves the real
app (`app.main.create_app()`) over real HTTP. Batches are realistic client/server span pairs, not an
injected delay.

    uv run python -m benchmarks.traces_stall --pairs 15 150 1500 --reps 3

`--pairs N` is N client+server pairs, so 2N spans (the default demo cycle is about 30 spans).
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
DATABASE = "neo4j"
CONTENT_TYPE = "application/x-protobuf"
PROBE_ROUTES = ("/health", "/api/services")
IDLE_PROBES = 50


def build_payload(pairs: int) -> bytes:
    """`pairs` distinct order-service -> product-service `GET /products/{id}` client/server pairs."""
    client = ResourceSpans(resource=_resource("OrderService"), scope_spans=[ScopeSpans(spans=[])])
    server = ResourceSpans(
        resource=_resource("ProductService", environment="production"),
        scope_spans=[ScopeSpans(spans=[])],
    )
    start = 1_700_000_000_000_000_000
    for i in range(pairs):
        trace_id = (i + 1).to_bytes(16, "big")
        client_id = (2 * i + 1).to_bytes(8, "big")
        server_id = (2 * i + 2).to_bytes(8, "big")
        client.scope_spans[0].spans.append(
            Span(
                trace_id=trace_id,
                span_id=client_id,
                name="GET /products/{id}",
                kind=Span.SPAN_KIND_CLIENT,
                start_time_unix_nano=start + i,
                end_time_unix_nano=start + i + 50_000_000,
            )
        )
        server.scope_spans[0].spans.append(
            Span(
                trace_id=trace_id,
                span_id=server_id,
                parent_span_id=client_id,
                name="GET /products/{id}",
                kind=Span.SPAN_KIND_SERVER,
                start_time_unix_nano=start + i + 10_000_000,
                end_time_unix_nano=start + i + 40_000_000,
                attributes=[
                    KeyValue(key="http.request.method", value=AnyValue(string_value="GET")),
                    KeyValue(key="http.route", value=AnyValue(string_value="/products/{id}")),
                ],
            )
        )
    return ExportTraceServiceRequest(resource_spans=[client, server]).SerializeToString()


def _resource(service: str, *, environment: str | None = None) -> Resource:
    attributes = [KeyValue(key="service.name", value=AnyValue(string_value=service))]
    if environment:
        attributes.append(
            KeyValue(key="deployment.environment.name", value=AnyValue(string_value=environment))
        )
    return Resource(attributes=attributes)


def _timed_get(client: httpx.Client, route: str) -> float:
    started = time.perf_counter()
    response = client.get(route)
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    return elapsed


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def measure_once(base_url: str, route: str, payload: bytes) -> dict:
    headers = {"origin": base_url}
    with (
        httpx.Client(base_url=base_url, headers=headers, timeout=300.0) as probe,
        httpx.Client(base_url=base_url, headers=headers, timeout=300.0) as poster,
    ):
        idle = [_timed_get(probe, route) for _ in range(IDLE_PROBES)]
        outcome: dict = {}
        started_ingest = threading.Event()
        done = threading.Event()

        def post() -> None:
            started_ingest.set()
            started = time.perf_counter()
            response = poster.post(
                "/v1/traces", content=payload, headers={"content-type": CONTENT_TYPE}
            )
            outcome["seconds"] = time.perf_counter() - started
            outcome["status"] = response.status_code
            done.set()

        thread = threading.Thread(target=post)
        thread.start()
        started_ingest.wait()
        during: list[float] = []
        while not done.is_set():
            during.append(_timed_get(probe, route))
        thread.join()
    # A probe in flight when the POST started is only answered after the ingest, so the worst
    # during-ingest latency is the stall a client sees; with no probe completing it is the ingest.
    return {
        "idle_max_s": max(idle),
        "idle_p50_s": statistics.median(idle),
        "ingest_s": outcome["seconds"],
        "post_status": outcome["status"],
        "probes_during_ingest": len(during),
        "during_max_s": max(during) if during else None,
        "during_p95_s": _percentile(during, 0.95) if during else None,
    }


def run(base_url: str, pair_counts: list[int], reps: int) -> list[dict]:
    results = []
    for pairs in pair_counts:
        payload = build_payload(pairs)
        for route in PROBE_ROUTES:
            runs = [measure_once(base_url, route, payload) for _ in range(reps)]
            results.append(
                {
                    "pairs": pairs,
                    "spans": 2 * pairs,
                    "payload_bytes": len(payload),
                    "probe_route": route,
                    "reps": runs,
                }
            )
    return results


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    import app.main
    from app.graph.importer import import_all_sources
    from app.sources.model import FilesystemSourceConfig
    from tests.integration.support.live_server import free_loopback_port, serve_over_real_http

    parser = argparse.ArgumentParser(prog="python -m benchmarks.traces_stall")
    parser.add_argument("--pairs", type=int, nargs="+", default=[15, 150, 1500])
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    with Neo4jContainer(
        "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
    ) as container:
        driver = container.get_driver()
        try:
            import_all_sources(
                driver,
                database=DATABASE,
                source_config=FilesystemSourceConfig(id="traces-stall-examples", root=EXAMPLES_DIR),
            )
            os.environ["NEO4J_URI"] = container.get_connection_url()
            os.environ["NEO4J_USER"] = container.username
            os.environ["NEO4J_PASSWORD"] = container.password
            os.environ.setdefault("OPENAI_API_KEY", "")
            port = free_loopback_port()
            base_url = f"http://127.0.0.1:{port}"
            with tempfile.TemporaryDirectory(prefix="aip-benchmark-") as config_dir:
                config_path = Path(config_dir) / "config.yaml"
                config_path.write_text(
                    "architecture_intelligence:\n"
                    "  mcp:\n"
                    f'    allowed-origins: ["{base_url}"]\n'
                    f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
                )
                app.main.CONFIG_PATH = config_path
                with serve_over_real_http(app.main.create_app(), port=port):
                    results = run(base_url, args.pairs, args.reps)
        finally:
            driver.close()
    text = json.dumps(results, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
