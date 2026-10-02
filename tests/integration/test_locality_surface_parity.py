"""v0.6.0 I3.3c: cross-surface parity of the locality answer (I3 spec §13, §14 "API and schema
parity"; matrix row S13; decision record D1, D9).

For every oracle answer case X01-X28, one world is built, and the same request is then answered by
three surfaces sharing one `ArchitectureIntelligenceService`, all on the same snapshot:
- the semantic service directly;
- REST: `POST /api/services/{id}/dependencies/by-locality[/evidence]` through `TestClient`;
- negotiated MCP over the real transport: the guard, the SDK's session manager and `tools/call`,
  through `httpx.ASGITransport`.

Transport wrapping and the HTTP status are the only allowed differences (I3 §13): the REST body and
the MCP `structuredContent` must equal the service answer exactly. Each surface's answer also passes
the published 0.6 schema, and the service answer matches the independent oracle (matrix §2).
"""

from __future__ import annotations

import json

import httpx
import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.api import architecture_intelligence, errors
from app.architecture_intelligence.locality_contracts import LOCALITY_TOOL_NAME
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.integration.locality_oracle import world
from tests.integration.locality_oracle.matcher import explain_mismatch, match, substitute
from tests.integration.test_locality_oracle import (
    ANSWER_SCHEMA,
    CASES,
    EVIDENCE_ANSWER_CASES,
    K_ANSWER_CASES,
    REHEARSAL_ANSWER_CASES,
    _ask,
    _current_snapshot,
    _ref_symbols,
    _service,
)
from tests.integration.test_locality_rehearsal_replay import FIXTURE
from tests.support.negotiated_mcp_client import call_negotiated

_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
# Rehearsal cases first, C2 before C1, so the C1 cases share one replay (as in the oracle module).
PARITY_CASES = [*REHEARSAL_ANSWER_CASES, *K_ANSWER_CASES, *EVIDENCE_ANSWER_CASES]


def test_every_answer_case_is_compared_across_surfaces():
    answer_cases = sorted(c for c, case in CASES.items() if case["kind"] == "answer")
    assert sorted(PARITY_CASES) == answer_cases and len(PARITY_CASES) == 28


def _rest(service: ArchitectureIntelligenceService, request: dict) -> httpx.Response:
    app = FastAPI()
    app.include_router(architecture_intelligence.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    body = {k: v for k, v in request.items() if k not in {"subject_service_id", "mode"}}
    route = "dependencies/by-locality" + ("/evidence" if request["mode"] == "evidence" else "")
    return TestClient(app).post(f"/api/services/{request['subject_service_id']}/{route}", json=body)


async def _mcp(service: ArchitectureIntelligenceService, request: dict) -> dict:
    server = MCPServer(name="architecture-intelligence-platform-test", version="0.6.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as client:
            return await call_negotiated(
                client,
                origin=_ALLOWED_ORIGIN,
                name=LOCALITY_TOOL_NAME,
                arguments={"request": request},
            )


def _valid(payload: dict) -> dict:
    errors_found = [
        error.message
        for error in jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(payload)
    ]
    assert errors_found == []
    return payload


@pytest.mark.asyncio
@pytest.mark.parametrize("case_id", PARITY_CASES)
async def test_service_rest_and_mcp_return_the_same_answer(driver, tmp_path, case_id):
    case = CASES[case_id]
    if case["inputs"]["world"] == "rehearsal" and not (FIXTURE / "otlp.jsonl").exists():
        pytest.skip("the rehearsal fixture is not present")
    prebound = world.build(driver, tmp_path, case["inputs"])
    if case["request"]["mode"] == "evidence":
        prebound["SNAPSHOT_ID"] = _current_snapshot(driver)
        prebound |= world.bind_refs(driver, case["inputs"], prebound, _ref_symbols(case["request"]))
    request = substitute(case["request"], prebound)
    service = _service(driver)

    direct = _ask(driver, request, service=service)
    rest = _rest(service, request)
    mcp = await _mcp(service, request)

    assert rest.status_code == 200
    assert mcp["isError"] is False
    assert _valid(rest.json()) == direct
    assert _valid(mcp["structuredContent"]) == direct
    assert match(case["expected"], direct, prebound) is not None, (
        explain_mismatch(substitute(case["expected"], prebound), direct),
        json.dumps(direct, indent=1, sort_keys=True),
    )
