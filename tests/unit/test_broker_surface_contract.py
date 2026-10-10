"""v0.6.1 I2b: REST and MCP advertise (and accept) both answer versions (spec §5.2).

The service still emits only v0.5 here, so a Broker-aware v0.6 answer is hand-built and returned by
a fake service. What this proves: the advertised MCP `outputSchema` is a `oneOf` discriminated by
`schema_version` whose two branches are exactly the published v0.5 and v0.6 files; both versions
reach the client unchanged over the negotiated JSON-RPC transport, in process (`structuredContent`
stays the bare answer envelope, never `{"result": ...}`) and validate against the *advertised*
schema (the v0.5 branch also has a real-listener proof in the independent-client golden path; the
v0.6 real-listener case lands with the producer in I2c); the REST
routes return both versions with the same bodies. `get_architecture_drift` and the locality tool are
unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import jsonschema
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

from app.api import architecture_intelligence, errors, evidence
from app.architecture_intelligence.broker_contracts import (
    ArchitectureAnswerV06,
    EvidenceDataV06,
    ServiceDependenciesDataV06,
)
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    EvidenceData,
    ServiceDependenciesData,
)
from app.architecture_intelligence.schema_export import (
    BROKER_DEPENDENCIES_SCHEMA_PATH,
    BROKER_EVIDENCE_SCHEMA_PATH,
    DEPENDENCIES_SCHEMA_PATH,
    DRIFT_SCHEMA_PATH,
    EVIDENCE_SCHEMA_PATH,
)
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from tests.support.negotiated_mcp_client import call_negotiated
from tests.unit.test_broker_contracts import dependencies_payload, evidence_payload

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "architecture_intelligence"
_ORIGIN = "http://localhost"
_SNAPSHOT = "aip:snapshot:v1:" + "a" * 64

V05_DEPENDENCIES = ArchitectureAnswer[ServiceDependenciesData].model_validate(
    json.loads((FIXTURES / "i1" / "answered_empty.json").read_text())
)
V06_DEPENDENCIES = ArchitectureAnswerV06[ServiceDependenciesDataV06].model_validate(
    dependencies_payload()
)
V05_EVIDENCE = ArchitectureAnswer[EvidenceData].model_validate(
    json.loads((FIXTURES / "i2" / "answered_full.json").read_text())
)
V06_EVIDENCE = ArchitectureAnswerV06[EvidenceDataV06].model_validate(evidence_payload())


def _inline(node: Any, definitions: dict[str, Any]) -> Any:
    """Resolves every local `$ref` in place, dropping the `$defs` table."""
    if isinstance(node, dict):
        if set(node) == {"$ref"}:
            return _inline(definitions[node["$ref"].rsplit("/", 1)[-1]], definitions)
        return {key: _inline(value, definitions) for key, value in node.items() if key != "$defs"}
    if isinstance(node, list):
        return [_inline(value, definitions) for value in node]
    return node


def _published(path: Path) -> Any:
    schema = json.loads(path.read_text(encoding="utf-8"))
    return _inline(schema, schema.get("$defs", {}))


def _output_schema(tool_name: str) -> dict:
    server = MCPServer(name="test", version="0.6.1")
    register_tools(server)
    tool = server._tool_manager.get_tool(tool_name)
    assert tool is not None and tool.output_schema is not None
    return tool.output_schema


# --- the advertised MCP output schema is exactly the two published files -------------------------


@pytest.mark.parametrize(
    ("tool_name", "v05_path", "v06_path"),
    [
        ("get_service_dependencies", DEPENDENCIES_SCHEMA_PATH, BROKER_DEPENDENCIES_SCHEMA_PATH),
        ("get_evidence", EVIDENCE_SCHEMA_PATH, BROKER_EVIDENCE_SCHEMA_PATH),
    ],
)
def test_the_advertised_one_of_branches_are_exactly_the_published_v05_and_v06_files(
    tool_name, v05_path, v06_path
):
    schema = _output_schema(tool_name)
    assert schema["discriminator"]["propertyName"] == "schema_version"
    branches = {
        branch_key: _inline({"$ref": ref}, schema["$defs"])
        for branch_key, ref in schema["discriminator"]["mapping"].items()
    }
    assert set(branches) == {"0.5", "0.6"}
    assert branches["0.5"] == _published(v05_path)
    assert branches["0.6"] == _published(v06_path)
    assert [branch["$ref"] for branch in schema["oneOf"]] == [
        schema["discriminator"]["mapping"]["0.5"],
        schema["discriminator"]["mapping"]["0.6"],
    ]


def test_drift_advertises_only_the_published_v05_drift_schema():
    schema = _output_schema("get_architecture_drift")
    assert "oneOf" not in schema
    assert _inline(schema, schema.get("$defs", {})) == _published(DRIFT_SCHEMA_PATH)


# --- both versions over the negotiated JSON-RPC transport (in process) ---------------------------------------------


class _FakeService:
    def __init__(self, *, dependencies=None, evidence=None) -> None:
        self._dependencies, self._evidence = dependencies, evidence

    def get_service_dependencies(self, request):
        return self._dependencies

    def get_evidence(self, request):
        return self._evidence


async def _call_mcp(service: _FakeService, name: str, arguments: dict) -> dict:
    server = MCPServer(name="test", version="0.6.1")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(allowed_origins=[_ORIGIN], allowed_hosts=["localhost"], server=server)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
            return await call_negotiated(client, origin=_ORIGIN, name=name, arguments=arguments)


_DEPENDENCIES_ARGS = {"request": {"service_id": "service:invoice-service"}}
_EVIDENCE_ARGS = {"request": {"evidence_refs": ["evidence:declared:a"], "snapshot_id": _SNAPSHOT}}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "published_path", "version"),
    [
        (V05_DEPENDENCIES, DEPENDENCIES_SCHEMA_PATH, "0.5"),
        (V06_DEPENDENCIES, BROKER_DEPENDENCIES_SCHEMA_PATH, "0.6"),
    ],
)
async def test_dependencies_over_the_negotiated_transport_for_both_versions(
    answer, published_path, version
):
    result = await _call_mcp(
        _FakeService(dependencies=answer), "get_service_dependencies", _DEPENDENCIES_ARGS
    )
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert "result" not in structured  # the bare answer envelope, never the SDK's wrapper
    assert structured == answer.model_dump(mode="json")
    assert structured["schema_version"] == version
    # validated against what the server advertises, and against the published file for its version
    advertised = _output_schema("get_service_dependencies")
    jsonschema.validate(instance=structured, schema=advertised)
    jsonschema.validate(instance=structured, schema=json.loads(published_path.read_text()))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "published_path", "version"),
    [
        (V05_EVIDENCE, EVIDENCE_SCHEMA_PATH, "0.5"),
        (V06_EVIDENCE, BROKER_EVIDENCE_SCHEMA_PATH, "0.6"),
    ],
)
async def test_evidence_over_the_negotiated_transport_for_both_versions(
    answer, published_path, version
):
    result = await _call_mcp(_FakeService(evidence=answer), "get_evidence", _EVIDENCE_ARGS)
    assert result["isError"] is False
    structured = result["structuredContent"]
    assert "result" not in structured
    assert structured == answer.model_dump(mode="json")
    assert structured["schema_version"] == version
    jsonschema.validate(instance=structured, schema=_output_schema("get_evidence"))
    jsonschema.validate(instance=structured, schema=json.loads(published_path.read_text()))


@pytest.mark.parametrize("answer", [V05_DEPENDENCIES, V06_DEPENDENCIES])
def test_exactly_one_advertised_branch_matches_each_version(answer):
    """The advertised `oneOf` is not both-match or neither-match: a v0.5 answer matches only the
    v0.5 branch and a v0.6 answer only the v0.6 branch."""
    schema = _output_schema("get_service_dependencies")
    payload = answer.model_dump(mode="json")
    matches = [
        ref
        for ref in schema["discriminator"]["mapping"].values()
        if jsonschema.Draft202012Validator({"$ref": ref, "$defs": schema["$defs"]}).is_valid(
            payload
        )
    ]
    assert matches == [schema["discriminator"]["mapping"][answer.schema_version]]


# --- both versions over REST -------------------------------------------------------------------------


def _client(service: _FakeService) -> TestClient:
    app = FastAPI()
    app.include_router(architecture_intelligence.router)
    app.include_router(evidence.router)
    errors.register_exception_handlers(app)
    app.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    return TestClient(app)


@pytest.mark.parametrize("answer", [V05_DEPENDENCIES, V06_DEPENDENCIES])
def test_rest_dependencies_returns_either_version_unchanged(answer):
    response = _client(_FakeService(dependencies=answer)).get(
        "/api/services/service:invoice-service/dependencies"
    )
    assert response.status_code == 200
    assert response.json() == answer.model_dump(mode="json")
    assert response.json()["schema_version"] == answer.schema_version


@pytest.mark.parametrize("answer", [V05_EVIDENCE, V06_EVIDENCE])
def test_rest_evidence_resolve_returns_either_version_unchanged(answer):
    response = _client(_FakeService(evidence=answer)).post(
        "/api/evidence/resolve",
        json={"evidence_refs": ["evidence:declared:a"], "snapshot_id": _SNAPSHOT},
    )
    assert response.status_code == 200
    assert response.json() == answer.model_dump(mode="json")
    assert response.json()["schema_version"] == answer.schema_version
