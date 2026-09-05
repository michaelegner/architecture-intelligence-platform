"""v0.4.0 I2.4 - the closing qualification increment: proves spec §17 scenarios 21-22 through the
REAL production app assembly (`app.main.create_app()`'s lifespan, `app.mcp.wiring.configure(
build_production_service(...))`, the real `/mcp` mount) rather than the isolated `build_mcp_app`/
`register_tools(server, get_service=...)` harness every I2.1-I2.3 test uses. That harness never
exercises `app.mcp.wiring`'s production composition root at all - this file closes that gap.

The app is served by a real `uvicorn` server bound to a loopback TCP port (the same server this
project's `Dockerfile` runs) and driven by a plain `httpx.Client` over ordinary network HTTP -
deliberately not `fastapi.testclient.TestClient`/`httpx.ASGITransport`, which dispatch straight into
the ASGI callable and so would prove nothing about a real listener (spec §18/§19's "one real HTTP
independent-client golden path").
"""

from __future__ import annotations

import json
import socket
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jsonschema
import pytest
import uvicorn

import app.main
from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.revision_fence import read_revision
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate

from .independent_mcp_client import (
    call_tool,
    run_dependency_to_evidence_golden_path,
    tools_list,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_SERVER_STARTUP_TIMEOUT_SECONDS = 30.0
_SERVER_SHUTDOWN_TIMEOUT_SECONDS = 10.0
OBSERVATION_CONTEXT = {
    "environment": ENVIRONMENT,
    "window_start": WINDOW_START,
    "window_end": WINDOW_END,
}

DEPENDENCY_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "architecture-answer.schema.json"
)
EVIDENCE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "evidence-answer.schema.json"
)
DEPENDENCY_SCHEMA = json.loads(DEPENDENCY_SCHEMA_PATH.read_text())
EVIDENCE_SCHEMA = json.loads(EVIDENCE_SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _observe_order_service_calls_product_service(driver):
    subject_id = ids.service_id("order-service")
    object_id = ids.operation_id(ids.service_id("product-service"), "GET", "/products/{id}")
    bucket_start = datetime(2026, 8, 26, 12, tzinfo=UTC)
    evidence = ObservedEvidence(
        id=ids.observed_evidence_id(ENVIRONMENT, bucket_start, subject_id, "CALLS", object_id),
        environment=ENVIRONMENT,
        bucket_start=bucket_start,
        bucket_end=bucket_start,
        first_seen=bucket_start,
        last_seen=bucket_start,
        observation_count=1,
        sample_trace_ids=["a" * 32],
    )
    batch = ObservationBatch(
        facts=[
            ObservedFactCandidate(
                subject_id=subject_id,
                relation_type="CALLS",
                object_id=object_id,
                environment=ENVIRONMENT,
                timestamp=bucket_start,
                trace_id="a" * 32,
                evidence=evidence,
            )
        ]
    )
    persist_observation_batch(driver, DATABASE, batch)


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def _serve_over_real_http(served_app, *, port: int):
    """Runs the app under a real `uvicorn` server bound to a loopback TCP port - the same server
    this project's `Dockerfile` uses - so the client below reaches it over ordinary network HTTP.

    Deliberately NOT `fastapi.testclient.TestClient`/`httpx.ASGITransport` (PR #80 review finding):
    those dispatch straight into the ASGI callable, so a loopback-looking base_url proves nothing
    about a real listener. Spec §18/§19 require one *real* HTTP independent-client golden path."""
    config = uvicorn.Config(served_app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + _SERVER_STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if time.monotonic() > deadline:
            server.should_exit = True
            thread.join(timeout=_SERVER_SHUTDOWN_TIMEOUT_SECONDS)
            raise TimeoutError("uvicorn did not report startup within the bounded wait")
        time.sleep(0.02)
    try:
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=_SERVER_SHUTDOWN_TIMEOUT_SECONDS)


@pytest.fixture
def real_app_client(driver, neo4j_container, tmp_path, monkeypatch):
    """Boots the actual production app against the same shared Neo4j testcontainer the `driver`
    fixture already points at - a second driver instance, same container, so data imported through
    `driver` is visible through the app's own lifespan-built driver - and serves it over real HTTP.

    The MCP Origin/Host allowlist is written to match the dynamically chosen port (rather than
    binding the fixed default 8000, which would collide with anything already listening there);
    `test_mcp_config_wiring.py` already proves `create_app()` honors this config path."""
    monkeypatch.setenv("NEO4J_URI", neo4j_container.get_connection_url())
    monkeypatch.setenv("NEO4J_USER", neo4j_container.username)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_container.password)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    port = _free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "architecture_intelligence:\n"
        "  mcp:\n"
        f'    allowed-origins: ["{base_url}"]\n'
        f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
    )
    monkeypatch.setattr(app.main, "CONFIG_PATH", config_path)

    real_app = app.main.create_app()
    # A plain httpx.Client with its default network transport - no ASGI shortcut.
    with (
        _serve_over_real_http(real_app, port=port),
        httpx.Client(base_url=base_url, headers={"origin": base_url}, timeout=30.0) as client,
    ):
        assert client.get("/health").status_code == 200  # the listener really is serving
        yield real_app, client


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _fingerprint(driver) -> tuple[str, str]:
    with driver.session(database=DATABASE) as session:
        return snapshot_fingerprint(
            canonical_snapshot_state(session, coverage_qualification_enabled=True)
        )


def test_independent_client_completes_the_real_dependency_to_evidence_golden_path(
    driver, real_app_client
):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)
    real_app, client = real_app_client

    # No LLM key was ever set - the real production wiring must still boot and answer correctly.
    assert real_app.state.llm_provider is None

    tools = tools_list(client)["tools"]
    assert [tool["name"] for tool in tools] == ["get_evidence", "get_service_dependencies"]
    # The client validates against the schemas the server actually *advertises* (spec §17 scenario
    # 21), not only the repository-local frozen copies - a missing, incompatible or mis-wired
    # `outputSchema` would otherwise escape this qualification entirely (PR #80 review finding).
    advertised_output_schemas = {tool["name"]: tool["outputSchema"] for tool in tools}

    revision_before = None
    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    result = run_dependency_to_evidence_golden_path(
        client,
        service_id=ids.service_id("order-service"),
        observation_context=OBSERVATION_CONTEXT,
    )

    dependencies_result = result["dependencies"]
    evidence_result = result["evidence"]
    assert dependencies_result["isError"] is False
    assert evidence_result["isError"] is False

    dependencies_answer = dependencies_result["structuredContent"]
    evidence_answer = evidence_result["structuredContent"]
    jsonschema.validate(
        instance=dependencies_answer,
        schema=advertised_output_schemas["get_service_dependencies"],
    )
    jsonschema.validate(instance=evidence_answer, schema=advertised_output_schemas["get_evidence"])
    # Retained as an additional contract check: the advertised schemas must also not have drifted
    # from the committed frozen ones.
    jsonschema.validate(instance=dependencies_answer, schema=DEPENDENCY_SCHEMA)
    jsonschema.validate(instance=evidence_answer, schema=EVIDENCE_SCHEMA)

    http_claim = next(
        claim
        for claim in dependencies_answer["claims"]
        if claim["object"]["id"] == ids.service_id("product-service")
        and claim["delivery"]["kind"] == "SYNC_HTTP"
    )
    assert http_claim["qualification"] == "CONFIRMED"
    assert evidence_answer["outcome"] == "ANSWERED"
    assert evidence_answer["data"]["missing_evidence_refs"] == []

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before

    # Deterministic outputs: repeating the exact same golden path yields byte-identical *semantic*
    # answers. Compared as independently canonicalized JSON bytes (sorted keys, fixed separators),
    # not parsed dicts, so the assertion literally proves the byte-identity it claims (PR #80 review
    # clarification). The surrounding JSON-RPC envelope is not the semantic target and is excluded.
    repeated = run_dependency_to_evidence_golden_path(
        client,
        service_id=ids.service_id("order-service"),
        observation_context=OBSERVATION_CONTEXT,
    )
    assert _canonical_bytes(repeated["dependencies"]["structuredContent"]) == _canonical_bytes(
        dependencies_answer
    )
    assert _canonical_bytes(repeated["evidence"]["structuredContent"]) == _canonical_bytes(
        evidence_answer
    )


def test_independent_client_refusal_through_the_real_app_leaves_graph_state_unchanged(
    driver, real_app_client
):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _, client = real_app_client

    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    fingerprint_before = _fingerprint(driver)

    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64
    result = call_tool(
        client,
        name="get_evidence",
        arguments={
            "request": {
                "evidence_refs": ["evidence:declared:does-not-exist"],
                "snapshot_id": stale_snapshot_id,
            }
        },
    )

    assert result["isError"] is False
    assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"
    assert result["structuredContent"]["limitations"][0]["code"] == "SNAPSHOT_NOT_AVAILABLE"

    with driver.session(database=DATABASE) as session:
        revision_after = read_revision(session)
    fingerprint_after = _fingerprint(driver)
    assert revision_after == revision_before
    assert fingerprint_after == fingerprint_before
