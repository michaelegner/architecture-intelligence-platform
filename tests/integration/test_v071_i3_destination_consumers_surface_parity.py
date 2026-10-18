"""v0.7.1 I3.2: cross-surface parity of `get_destination_consumers` (I3 spec §5, §6 "equivalent
Service/REST/MCP payloads").

One real import (the Kafka declarations fixture, an I1 capture and an I2 mapping) and one
`ArchitectureIntelligenceService`, answered by three surfaces on the same snapshot:
- the semantic service directly;
- REST: `POST /api/destination-consumers[/evidence]` through `TestClient`;
- negotiated MCP over the real transport: the guard, the SDK's session manager and `tools/call`,
  through `httpx.ASGITransport`.

The REST body and the MCP `structuredContent` equal the service answer exactly, and each passes the
published 0.7.1 schema. The refs a query emits resolve through every surface's evidence mode at the
same snapshot, and nothing else does.
"""

import json

import httpx
import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.api import destination_consumers, errors
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.destination_consumer_contracts import (
    TOOL_NAME,
    DestinationConsumersEvidenceRequest,
    DestinationConsumersQueryRequest,
)
from app.architecture_intelligence.schema_export import DESTINATION_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated

from .test_v071_i3_destination_consumers_service import (
    BROKER,
    DATABASE,
    _import,
    _kafka,
    _mapping,
    _topic_id,
)

_ORIGIN = "http://localhost"
_PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.1", build_revision="t")
_SCHEMA = json.loads(DESTINATION_ANSWER_SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _valid(payload: dict) -> dict:
    assert list(jsonschema.Draft202012Validator(_SCHEMA).iter_errors(payload)) == []
    return payload


def _rest(service: ArchitectureIntelligenceService, request: dict) -> httpx.Response:
    app = FastAPI()
    app.include_router(destination_consumers.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    body = {key: value for key, value in request.items() if key != "mode"}
    route = "/api/destination-consumers" + ("/evidence" if request["mode"] == "evidence" else "")
    return TestClient(app).post(route, json=body)


async def _mcp(service: ArchitectureIntelligenceService, request: dict) -> dict:
    server = MCPServer(name="architecture-intelligence-platform-test", version="0.7.1")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(allowed_origins=[_ORIGIN], allowed_hosts=["localhost"], server=server)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
            return await call_negotiated(
                client, origin=_ORIGIN, name=TOOL_NAME, arguments={"request": request}
            )


def _direct(service: ArchitectureIntelligenceService, request: dict) -> dict:
    if request["mode"] == "query":
        answer = service.get_destination_consumers(
            DestinationConsumersQueryRequest.model_validate(request)
        )
    else:
        answer = service.get_destination_consumer_evidence(
            DestinationConsumersEvidenceRequest.model_validate(request)
        )
    return answer.model_dump(mode="json")


async def _all_surfaces(service, request: dict) -> dict:
    direct = _direct(service, request)
    rest = _rest(service, request)
    mcp = await _mcp(service, request)
    assert rest.status_code == 200 and mcp["isError"] is False
    assert _valid(direct) == _valid(rest.json()) == _valid(mcp["structuredContent"])
    return direct


@pytest.fixture
def imported(driver, tmp_path):
    _import(driver, kafka=[_kafka(tmp_path, "prod")], mappings=[_mapping(tmp_path)])
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=_PRODUCER)
    context = {"destination_id": _topic_id(driver), "broker_id": BROKER, "environment": "prod"}
    return service, context


@pytest.mark.asyncio
async def test_every_surface_answers_the_query_and_resolves_its_refs(imported) -> None:
    service, context = imported
    query = await _all_surfaces(service, {"mode": "query", **context})
    [row] = query["data"]["rows"]
    assert (row["outcome"], row["service_id"]) == ("RESOLVED", "service:stock-projector")
    refs = sorted([*row["attachment_evidence_refs"], *row["mapping_evidence_refs"]])
    snapshot_id = query["snapshot"]["snapshot_id"]

    resolved = await _all_surfaces(
        service,
        {"mode": "evidence", "snapshot_id": snapshot_id, "evidence_refs": refs, **context},
    )
    assert resolved["outcome"] == "ANSWERED"
    assert {entry["kind"] for entry in resolved["data"]["entries"]} == {
        "KAFKA_ATTACHMENT",
        "KAFKA_SERVICE_MAPPING",
    }
    # Client-supplied member, client and host text never reaches any surface.
    assert "/10.0.0.7" not in json.dumps(resolved)

    forged = "destination-evidence:" + "0" * 64
    mixed = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": snapshot_id,
            "evidence_refs": sorted([forged, refs[0]]),
            **context,
        },
    )
    assert mixed["outcome"] == "PARTIAL"
    assert {e["ref"]: e["status"] for e in mixed["data"]["entries"]}[forged] == "NOT_RESOLVED"


@pytest.mark.asyncio
async def test_refusals_are_identical_on_every_surface(imported) -> None:
    service, context = imported
    stale = "aip:snapshot:v1:" + "0" * 64
    query = await _all_surfaces(service, {"mode": "query", **context, "snapshot_id": stale})
    evidence = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": stale,
            "evidence_refs": ["destination-evidence:" + "1" * 64],
            **context,
        },
    )
    for answer in (query, evidence):
        assert answer["data"] is None and answer["outcome"] == "NOT_ANSWERED"
        assert [item["code"] for item in answer["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
    mismatch = await _all_surfaces(service, {"mode": "query", **context, "broker_id": "kafka:x"})
    assert [item["code"] for item in mismatch["limitations"]] == ["BROKER_MISMATCH"]
