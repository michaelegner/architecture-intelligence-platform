"""v0.7.0 I3.3: cross-surface parity of the API consumer usage answer (I3 spec §10, §13 "schema/client
parity"; decision record D1).

One real import (an APISIX configuration source, the bundled OpenAPI examples and a measurement
source: the I2.4 fixture) and one `ArchitectureIntelligenceService`, answered by three surfaces on the
same snapshot:
- the semantic service directly;
- REST: `POST /api/api-consumer-usage[/evidence]` through `TestClient`;
- negotiated MCP over the real transport: the guard, the SDK's session manager and `tools/call`,
  through `httpx.ASGITransport`.

Transport wrapping and the HTTP status are the only allowed differences: the REST body and the MCP
`structuredContent` equal the service answer exactly, and each passes the published 0.7 schema. The
refs a query emits resolve through every surface's evidence mode at the same snapshot, and nothing
else does.
"""

import json
from typing import Any

import httpx
import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.api import api_consumer_usage, errors
from app.architecture_intelligence.api_usage_contracts import (
    API_USAGE_TOOL_NAME,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.schema_export import API_USAGE_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated

from .test_v070_i2_qualification import (
    DATABASE,
    _gateway_default,
    _run,
    _spec_cases_measurement,
)

_ORIGIN = "http://localhost"
_PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.0", build_revision="t")
_SCHEMA = json.loads(API_USAGE_ANSWER_SCHEMA_PATH.read_text())


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
    app.include_router(api_consumer_usage.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    body = {key: value for key, value in request.items() if key != "mode"}
    route = "/api/api-consumer-usage" + ("/evidence" if request["mode"] == "evidence" else "")
    return TestClient(app).post(route, json=body)


async def _mcp(service: ArchitectureIntelligenceService, request: dict) -> dict:
    server = MCPServer(name="architecture-intelligence-platform-test", version="0.7.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(allowed_origins=[_ORIGIN], allowed_hosts=["localhost"], server=server)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
            return await call_negotiated(
                client,
                origin=_ORIGIN,
                name=API_USAGE_TOOL_NAME,
                arguments={"request": request},
            )


def _direct(service: ArchitectureIntelligenceService, request: dict) -> dict:
    if request["mode"] == "query":
        answer = service.get_api_consumer_usage(
            ApiConsumerUsageQueryRequest.model_validate(request)
        )
    else:
        answer = service.get_api_consumer_usage_evidence(
            ApiConsumerUsageEvidenceRequest.model_validate(request)
        )
    return answer.model_dump(mode="json")


async def _all_surfaces(service, request: dict) -> dict:
    direct = _direct(service, request)
    rest = _rest(service, request)
    mcp = await _mcp(service, request)
    assert rest.status_code == 200 and mcp["isError"] is False
    assert _valid(direct) == _valid(rest.json()) == _valid(mcp["structuredContent"])
    return direct


def _context(state: dict, route: str = "orders-route") -> dict[str, Any]:
    window = state["api_usage_v1"]["windows"][0]
    row = next(r for r in state["gateway_configuration_v1"]["routes"] if r["route_id"] == route)
    return {
        "target": {"kind": "GATEWAY_ROUTE", "id": row["id"]},
        "gateway_instance_id": window["gateway_instance_id"],
        "environment": window["environment"],
        "window_start": window["window_start"],
        "window_end": window["window_end"],
    }


def _refs(answer: dict) -> list[str]:
    data = answer["data"]
    return sorted(
        {
            *data["window"]["evidence_refs"],
            *(ref for route in data["selected_routes"] for ref in route["evidence_refs"]),
            *(ref for row in data["rows"] for ref in row["evidence_refs"]),
        }
    )


@pytest.fixture
def imported(driver, tmp_path):
    state = _run(
        driver,
        gateways=[_gateway_default(tmp_path)],
        measurements=[_spec_cases_measurement(tmp_path)],
    )
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=_PRODUCER)
    return state, service


@pytest.mark.asyncio
async def test_service_rest_and_mcp_return_the_same_query_answer(imported):
    state, service = imported
    for route in ("orders-route", "billing-route"):
        answer = await _all_surfaces(service, {"mode": "query", **_context(state, route)})
        assert answer["data"]["rows"], route


@pytest.mark.asyncio
async def test_pages_are_identical_across_surfaces_and_cover_the_selection_once(imported):
    state, service = imported
    request = {"mode": "query", **_context(state), "limit": 1}
    seen: list[tuple[str, str]] = []
    for _ in range(5):
        answer = await _all_surfaces(service, request)
        seen += [(r["consumer"]["id"], r["gateway_route"]["id"]) for r in answer["data"]["rows"]]
        cursor = answer["data"]["page"].get("next_cursor")
        if cursor is None:
            break
        request = {**request, "cursor": cursor, "snapshot_id": answer["snapshot"]["snapshot_id"]}
    whole = _direct(service, {"mode": "query", **_context(state)})
    assert seen == [(r["consumer"]["id"], r["gateway_route"]["id"]) for r in whole["data"]["rows"]]
    assert len(seen) == len(set(seen)) == 3


@pytest.mark.asyncio
async def test_every_emitted_ref_resolves_on_every_surface_and_a_forged_one_does_not(imported):
    state, service = imported
    context = _context(state)
    query = _direct(service, {"mode": "query", **context})
    snapshot_id = query["snapshot"]["snapshot_id"]

    resolved = await _all_surfaces(
        service,
        {"mode": "evidence", "snapshot_id": snapshot_id, "evidence_refs": _refs(query), **context},
    )
    assert resolved["outcome"] == "ANSWERED"
    assert {e["status"] for e in resolved["data"]["entries"]} == {"RESOLVED"}
    assert {e["kind"] for e in resolved["data"]["entries"]} >= {
        "MEASUREMENT_WINDOW",
        "CONFIGURED_ACCESS",
        "ROUTE_OPERATION_RECONCILIATION",
        "TARGET_SERVICE_RECONCILIATION",
    }

    forged = "api-evidence:" + "0" * 64
    mixed = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": snapshot_id,
            "evidence_refs": sorted([forged, _refs(query)[0]]),
            **context,
        },
    )
    assert mixed["outcome"] == "PARTIAL"
    assert {e["ref"]: e["status"] for e in mixed["data"]["entries"]}[forged] == "NOT_RESOLVED"


@pytest.mark.asyncio
async def test_a_stale_snapshot_is_the_same_refusal_on_every_surface(imported):
    state, service = imported
    stale = "aip:snapshot:v1:" + "0" * 64
    context = _context(state)
    query = await _all_surfaces(service, {"mode": "query", **context, "snapshot_id": stale})
    evidence = await _all_surfaces(
        service,
        {
            "mode": "evidence",
            "snapshot_id": stale,
            "evidence_refs": ["api-evidence:" + "1" * 64],
            **context,
        },
    )
    for answer in (query, evidence):
        assert answer["data"] is None and answer["outcome"] == "NOT_ANSWERED"
        assert [item["code"] for item in answer["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
