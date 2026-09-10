"""v0.4.0 I3.3 - I3 spec §33.4's Service-to-MCP invariant: "for every tested drift case, direct
`ArchitectureIntelligenceService` answer == MCP structuredContent semantic answer."

Deliberately kept out of `evaluation/architecture_answers/` (spec §30's evaluator diagram has no
MCP layer - see `evaluation.architecture_answers.invariants`'s module docstring). Instead, this
test dynamically discovers every `get_architecture_drift`-tool scenario already bundled in that
suite (via its own loader, so a future new drift scenario is automatically covered here too - never
silently missed) and drives each one through both the direct service call and the real MCP tool
dispatch against the identical prepared graph, asserting the two are byte-for-byte the same
structured answer. `reporter.py`'s `cross_tool_invariants.service_to_mcp` section names this file,
plus a live-computed count of the scenarios it covers, as the qualifying evidence for spec §33.4 -
not a prose claim.

Reuses `evaluation.architecture_answers.runner.build_request_payload` for the request shape (the
exact same construction the live evaluator run uses) and mirrors
`test_mcp_architecture_drift_equivalence.py`'s `_build_server_and_app` pattern (I3.2) rather than
inventing a new MCP test harness.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
import pytest
from mcp.server import MCPServer

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.request import ArchitectureDriftRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from evaluation import fixture_setup
from evaluation.architecture_answers.loader import discover_scenarios, load_scenario
from evaluation.architecture_answers.model import TOOL_ARCHITECTURE_DRIFT
from evaluation.architecture_answers.runner import build_request_payload

DATABASE = "neo4j"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"

SCENARIOS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "evaluation"
    / "architecture_answers"
    / "scenarios"
)

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.4.1", build_revision="f" * 40
)


def _drift_scenario_ids() -> list[str]:
    """Collection-time discovery (pure filesystem + Pydantic - no live driver needed), so a new
    drift scenario dropped into the suite is parametrized here automatically."""
    scenarios = [load_scenario(path) for path in discover_scenarios(SCENARIOS_DIR)]
    return sorted(
        scenario.id for scenario in scenarios if scenario.request.tool == TOOL_ARCHITECTURE_DRIFT
    )


DRIFT_SCENARIO_IDS = _drift_scenario_ids()


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


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
        "mcp-name": "get_architecture_drift",
        "mcp-protocol-version": "2026-07-28",
    }


def _json_safe(value: object) -> object:
    """`build_request_payload` returns native `datetime` values (fine for `.model_validate()`
    directly, per the direct-call path below) - the MCP path additionally has to survive a real
    JSON encode, so this recursively renders them to ISO 8601 strings first."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _call_body(request_payload: dict, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "get_architecture_drift",
            "arguments": {"request": _json_safe(request_payload)},
            "_meta": _meta(),
        },
    }


async def _call_drift_via_mcp(client: httpx.AsyncClient, request_payload: dict) -> dict:
    response = await client.post("/mcp", headers=_headers(), json=_call_body(request_payload))
    assert response.status_code == 200
    return response.json()["result"]


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", DRIFT_SCENARIO_IDS)
async def test_drift_scenario_direct_and_mcp_answers_agree(scenario_id, driver):
    scenario = load_scenario(SCENARIOS_DIR / scenario_id)
    fixture_setup.prepare_scenario(driver, database=DATABASE, scenario_path=scenario.path)
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)

    payload = build_request_payload(scenario.request)

    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    direct_answer = service.get_architecture_drift(ArchitectureDriftRequest.model_validate(payload))
    direct_json = direct_answer.model_dump(mode="json")

    server = MCPServer(name="test", version="0.4.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            result = await _call_drift_via_mcp(client, payload)

    assert result["isError"] is False
    assert result["structuredContent"] == direct_json


def test_at_least_one_drift_scenario_is_covered():
    """Guards against a silent regression where scenario discovery breaks and this file's own
    parametrization quietly collects zero tests (a parametrize with an empty list still "passes")."""
    assert len(DRIFT_SCENARIO_IDS) >= 5
