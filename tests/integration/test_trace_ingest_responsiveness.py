"""v0.6.3 I1 (spec §3.3): while a `POST /v1/traces` batch is being ingested, unrelated requests are
answered.

Real transport (uvicorn over loopback HTTP), real Neo4j, and the real ingestion path on resolvable
client/server span pairs, as in `benchmarks/traces_stall.py`. The route's `ingest_trace_spans` is
wrapped, not replaced: the wrapper holds the batch inside the route until the test has probed, then
runs the real function. That makes the ordering deterministic without substituting a sleep for the
ingestion work.
"""

import os
import tempfile
import threading
from pathlib import Path

import httpx
import pytest

import app.api.telemetry as telemetry_route
import app.main
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.sources.model import FilesystemSourceConfig
from benchmarks.traces_stall import CONTENT_TYPE, EXAMPLES_DIR, build_payload
from tests.integration.support.live_server import free_loopback_port, serve_over_real_http

_DATABASE = "neo4j"
_WAIT_SECONDS = 30.0


@pytest.fixture
def served(neo4j_container, driver, monkeypatch):
    with driver.session(database=_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    import_all_sources(
        driver,
        database=_DATABASE,
        source_config=FilesystemSourceConfig(id="trace-ingest-responsiveness", root=EXAMPLES_DIR),
    )
    monkeypatch.setenv("NEO4J_URI", neo4j_container.get_connection_url())
    monkeypatch.setenv("NEO4J_USER", neo4j_container.username)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_container.password)
    monkeypatch.setenv("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    port = free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as config_dir:
        config_path = Path(config_dir) / "config.yaml"
        config_path.write_text(
            "architecture_intelligence:\n"
            "  mcp:\n"
            f'    allowed-origins: ["{base_url}"]\n'
            f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
        )
        monkeypatch.setattr(app.main, "CONFIG_PATH", config_path)
        with serve_over_real_http(app.main.create_app(), port=port):
            yield base_url


def test_requests_are_answered_while_a_batch_is_being_ingested(served, driver, monkeypatch):
    real_ingest = telemetry_route.ingest_trace_spans
    ingest_started = threading.Event()
    release_ingest = threading.Event()

    def held_ingest(*args, **kwargs):
        ingest_started.set()
        assert release_ingest.wait(_WAIT_SECONDS)
        return real_ingest(*args, **kwargs)

    monkeypatch.setattr(telemetry_route, "ingest_trace_spans", held_ingest)

    outcome: dict = {}

    def post_batch() -> None:
        with httpx.Client(base_url=served, headers={"origin": served}, timeout=60.0) as poster:
            response = poster.post(
                "/v1/traces",
                content=build_payload(3),
                headers={"content-type": CONTENT_TYPE},
            )
        outcome["status"] = response.status_code

    poster_thread = threading.Thread(target=post_batch)
    poster_thread.start()
    try:
        assert ingest_started.wait(_WAIT_SECONDS)
        with httpx.Client(base_url=served, headers={"origin": served}, timeout=10.0) as probe:
            health = probe.get("/health")
            services = probe.get("/api/services")
        assert health.status_code == 200
        assert services.status_code == 200
        assert poster_thread.is_alive(), "the batch finished before the probes were answered"
        assert "status" not in outcome
    finally:
        release_ingest.set()
        poster_thread.join(timeout=_WAIT_SECONDS)

    assert outcome["status"] == 200
    with driver.session(database=_DATABASE) as session:
        record = session.run(
            "MATCH (a {id: $subject_id})-[r:CALLS]->(b {id: $object_id}) RETURN r.evidence_ids AS ids",
            subject_id=ids.service_id("order-service"),
            object_id=ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}"),
        ).single()
    assert record is not None and len(record["ids"]) >= 1
