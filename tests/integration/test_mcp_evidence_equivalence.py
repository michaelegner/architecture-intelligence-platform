"""v0.4.0 I2.3 Neo4j-integration coverage: spec §17's "Evidence Drill-Down" scenarios 9-16 and
"Read-Only and Independent Client" scenarios 17, 18, 20 that need a real driver, real imported
services, and a real revision fence to mean anything. Adapter-level dispatch/error-mapping against a
stub service is `tests/unit/test_mcp_evidence_adapter.py`'s job.

Mirrors `tests/integration/test_mcp_service_dependencies_equivalence.py`'s fixture setup and
`tests/integration/test_architecture_intelligence_service.py`'s evidence-observation fixture
(`_observe_order_service_calls_product_service`), so a "confirmed"/"safe-refusal" answer here
exercises the exact same graph state I1's and I2.3's own service-level suites already qualify
against.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import jsonschema
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.request import EvidenceRequest, ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.graph.revision_fence import read_revision
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.provenance.model import ObservedEvidence
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import ObservationBatch, ObservedFactCandidate

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "evidence-answer.schema.json"
)
DATABASE = "neo4j"
ENVIRONMENT = "test"
WINDOW_START = "2026-08-26T00:00:00.000000Z"
WINDOW_END = "2026-08-27T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.1", build_revision="f" * 40
)

EVIDENCE_ANSWER_SCHEMA = json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _dependency_request(service_id: str, **overrides) -> ServiceDependenciesRequest:
    payload = {
        "service_id": service_id,
        "observation_context": {
            "environment": ENVIRONMENT,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }
    payload.update(overrides)
    return ServiceDependenciesRequest.model_validate(payload)


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


def _build_server_and_app(driver) -> tuple[MCPServer, object]:
    service = _service(driver)
    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    return server, app


def _meta() -> dict[str, object]:
    return {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }


def _headers() -> dict[str, str]:
    return {
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
        "origin": _ALLOWED_ORIGIN,
        "mcp-method": "tools/call",
        "mcp-name": "get_evidence",
        "mcp-protocol-version": "2026-07-28",
    }


def _call_body(request_payload: dict, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "get_evidence",
            "arguments": {"request": request_payload},
            "_meta": _meta(),
        },
    }


async def _call_mcp(client: httpx.AsyncClient, request_payload: dict) -> dict:
    response = await client.post("/mcp", headers=_headers(), json=_call_body(request_payload))
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
async def test_full_dependency_to_evidence_chain_is_identical_direct_vs_mcp(driver):
    """The code-level vertical-slice proof (spec §1's golden path, minus the real independent HTTP
    client, which is I2.4's job): a real dependency answer's evidence_refs/resolution_evidence_refs
    and snapshot_id feed directly into get_evidence, and every reference resolves identically
    whether called directly or through MCP."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    _observe_order_service_calls_product_service(driver)

    dependency_answer = _service(driver).get_service_dependencies(
        _dependency_request(ids.service_id("order-service"))
    )
    http_claim = next(
        claim
        for claim in dependency_answer.claims
        if claim.object.id == ids.service_id("product-service")
        and claim.delivery.kind.value == "SYNC_HTTP"
    )
    requested_ids = sorted(set(http_claim.evidence_refs) | set(http_claim.resolution_evidence_refs))
    request_payload = {
        "evidence_refs": requested_ids,
        "snapshot_id": dependency_answer.snapshot.snapshot_id,
    }

    direct_json = (
        _service(driver)
        .get_evidence(EvidenceRequest.model_validate(request_payload))
        .model_dump(mode="json")
    )
    assert direct_json["outcome"] == Outcome.ANSWERED.value
    assert direct_json["data"]["missing_evidence_refs"] == []
    jsonschema.validate(instance=direct_json, schema=EVIDENCE_ANSWER_SCHEMA)

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, request_payload)
            assert result["isError"] is False
            jsonschema.validate(instance=result["structuredContent"], schema=EVIDENCE_ANSWER_SCHEMA)
            assert result["structuredContent"] == direct_json


@pytest.mark.asyncio
async def test_two_identical_mcp_calls_produce_byte_identical_structured_content(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    dependency_answer = _service(driver).get_service_dependencies(
        _dependency_request(ids.service_id("order-service"))
    )
    known_id = min(dependency_answer.evidence_refs)
    payload = {"evidence_refs": [known_id], "snapshot_id": dependency_answer.snapshot.snapshot_id}

    server, app = _build_server_and_app(driver)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            first = await _call_mcp(client, payload)
            second = await _call_mcp(client, payload)
            assert first["structuredContent"] == second["structuredContent"]


@pytest.mark.asyncio
async def test_successful_mcp_call_leaves_revision_fence_unchanged(driver):
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    dependency_answer = _service(driver).get_service_dependencies(
        _dependency_request(ids.service_id("order-service"))
    )
    known_id = min(dependency_answer.evidence_refs)

    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    payload = {"evidence_refs": [known_id], "snapshot_id": dependency_answer.snapshot.snapshot_id}
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, payload)
            assert result["isError"] is False

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before


@pytest.mark.asyncio
async def test_refusal_mcp_call_leaves_revision_fence_unchanged(driver):
    """A stale/mismatched snapshot_id forces `NOT_ANSWERED`/`SNAPSHOT_NOT_AVAILABLE` (spec §12) -
    still zero graph writes."""
    import_all_sources(driver, database=DATABASE, root=EXAMPLES_DIR)
    with driver.session(database=DATABASE) as session:
        before = read_revision(session)

    server, app = _build_server_and_app(driver)
    stale_snapshot_id = "aip:snapshot:v1:" + "a" * 64
    payload = {
        "evidence_refs": ["evidence:declared:does-not-exist"],
        "snapshot_id": stale_snapshot_id,
    }
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_mcp(client, payload)
            assert result["isError"] is False
            assert result["structuredContent"]["outcome"] == "NOT_ANSWERED"
            assert result["structuredContent"]["limitations"][0]["code"] == "SNAPSHOT_NOT_AVAILABLE"

    with driver.session(database=DATABASE) as session:
        after = read_revision(session)
    assert after == before
