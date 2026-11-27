"""v0.8.1 I1 - the MCP Skills extension and the two protocol eras (spec
`docs/specifications/0.8.1/specification.md` §4.3, D3, D8, D9; ADR 0018).

Every test drives the real mounted ASGI app (`build_mcp_app` around `build_mcp_server`) through
`httpx.ASGITransport`, as `test_mcp_discovery.py` does.

- `2026-07-28`: discovery, the SEP-2640 wire shape of `skills/list`, `skills/get` and
  `resources/read`, the skill set per flag, and `subscriptions/listen` declined (D9).
- `2025-11-25` (D8): `initialize`, `resources/list` and `tools/list` equal the stored v0.8.0
  results (`tests/fixtures/mcp_v080/`), and no skill is reachable.
- Both eras: every tool gives the same result.
- Drift guards: each tool name and each code that a skill names exists.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from enum import StrEnum
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.architecture_intelligence import (
    api_usage_contracts,
    binding_picture_contracts,
    contracts,
    destination_consumer_contracts,
    locality_contracts,
)
from app.architecture_intelligence import api_usage_projection as api_usage
from app.architecture_intelligence import binding_picture_projection as binding_picture
from app.architecture_intelligence import destination_consumer_projection as destination
from app.architecture_intelligence import locality_projection as locality
from app.architecture_intelligence.contracts import ArchitectureAnswer, Producer, SnapshotRef
from app.mcp import server as server_module
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.server import build_mcp_server
from app.mcp.skills import (
    BINDING_PICTURE_SKILL,
    READING_ANSWERS_SKILL,
    SKILLS_EXTENSION_ID,
    parse_frontmatter,
    skill_uri,
)
from app.version import package_version
from tests.support.modern_mcp_client import call_modern, post_modern
from tests.support.negotiated_mcp_client import call_negotiated, negotiated_headers

_ORIGIN = "http://localhost"
_REPO = Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO / "app" / "mcp" / "skills"
_V080_DIR = _REPO / "tests" / "fixtures" / "mcp_v080"
_AI_FIXTURES = _REPO / "tests" / "fixtures" / "architecture_intelligence"
_FLAGS = pytest.mark.parametrize("flag", [False, True], ids=["flag-off", "flag-on"])
_INVALID_PARAMS = -32602
_METHOD_NOT_FOUND = -32601


def _expected_skills(flag: bool) -> list[str]:
    return [READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL] if flag else [READING_ANSWERS_SKILL]


def _skill_bytes(name: str) -> bytes:
    return (_SKILLS_DIR / name / "SKILL.md").read_bytes()


@asynccontextmanager
async def _client(
    flag: bool, get_service: Callable[[], Any] | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    server = build_mcp_server(binding_picture=flag, get_service=get_service)
    app = build_mcp_app(allowed_origins=[_ORIGIN], allowed_hosts=["localhost"], server=server)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ORIGIN) as client:
            yield client


async def _modern_result(client: httpx.AsyncClient, method: str, params: dict | None = None):
    name = (params or {}).get("uri") if method == "resources/read" else None
    response = await post_modern(client, origin=_ORIGIN, method=method, params=params, name=name)
    return response.json()


async def _legacy(client: httpx.AsyncClient, body: dict) -> dict:
    return (await client.post("/mcp", headers=negotiated_headers(origin=_ORIGIN), json=body)).json()


# --- 2026-07-28 -----------------------------------------------------------------------------------


@pytest.mark.asyncio
@_FLAGS
async def test_modern_discovery_advertises_skills_and_declines_listen(flag: bool) -> None:
    async with _client(flag) as client:
        capabilities = (await _modern_result(client, "server/discover"))["result"]["capabilities"]
    assert capabilities["extensions"] == {SKILLS_EXTENSION_ID: {}}
    # D9: `subscriptions=False`, so nothing is advertised as changing or subscribable.
    assert capabilities["resources"] == {"listChanged": False, "subscribe": False}
    assert capabilities["tools"] == {"listChanged": False}
    assert capabilities["prompts"] == {"listChanged": False}


@pytest.mark.asyncio
@_FLAGS
async def test_skills_round_trip_with_the_sep_2640_wire_shape(flag: bool) -> None:
    hint = server_module._TOOLS_LIST_CACHE_HINT
    async with _client(flag) as client:
        listed = (await _modern_result(client, "skills/list"))["result"]
        assert listed["resultType"] == "complete"
        assert (listed["ttlMs"], listed["cacheScope"]) == (hint.ttl_ms, hint.scope) == (0, "public")
        assert "nextCursor" not in listed
        assert [entry["uri"] for entry in listed["skills"]] == [
            skill_uri(name) for name in _expected_skills(flag)
        ]

        for name, entry in zip(_expected_skills(flag), listed["skills"], strict=True):
            raw = _skill_bytes(name)
            assert entry["frontmatter"] == parse_frontmatter(raw.decode("utf-8"))
            assert entry["frontmatter"]["name"] == name
            assert entry["uri"].rsplit("/", 2)[-2] == name

            read = (await _modern_result(client, "resources/read", {"uri": entry["uri"]}))["result"]
            [content] = read["contents"]
            assert content["uri"] == entry["uri"]
            assert content["mimeType"] == "text/markdown"
            served = content["text"].encode("utf-8")
            assert served == raw
            assert entry["resources"] == [
                {
                    "uri": entry["uri"],
                    "digest": "sha256:" + hashlib.sha256(served).hexdigest(),
                    "size": len(served),
                }
            ]

            got = (await _modern_result(client, "skills/get", {"uri": entry["uri"]}))["result"]
            # The SDK stamps every 2026-era result with `_meta` (`serverInfo`).
            assert set(got.pop("_meta")) == {"io.modelcontextprotocol/serverInfo"}
            assert got == {
                "resultType": "complete",
                "skill": entry,
                "ttlMs": hint.ttl_ms,
                "cacheScope": hint.scope,
            }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("flag", "uri"),
    [
        (True, "skill://aip/unknown/SKILL.md"),
        (False, "skill://aip/unknown/SKILL.md"),
        (False, skill_uri(BINDING_PICTURE_SKILL)),
    ],
)
async def test_skills_get_of_an_unknown_uri_is_invalid_params(flag: bool, uri: str) -> None:
    async with _client(flag) as client:
        error = (await _modern_result(client, "skills/get", {"uri": uri}))["error"]
    assert error["code"] == _INVALID_PARAMS


@pytest.mark.asyncio
async def test_flag_off_does_not_serve_the_binding_picture_skill_resource() -> None:
    async with _client(False) as client:
        error = (
            await _modern_result(
                client, "resources/read", {"uri": skill_uri(BINDING_PICTURE_SKILL)}
            )
        )["error"]
    assert error["code"] == _INVALID_PARAMS


@pytest.mark.asyncio
async def test_modern_subscriptions_listen_is_method_not_found() -> None:
    """D9: the method is unserved. With the SSE accept that a listen requires, the SDK answers on
    its SSE path with METHOD_NOT_FOUND instead of opening a stream. The guard's body replay, which
    this path needs, is proven by `test_mcp_guard_body_limit.py`."""
    async with _client(True) as client:
        response = await asyncio.wait_for(
            post_modern(
                client, origin=_ORIGIN, method="subscriptions/listen", params={"notifications": {}}
            ),
            timeout=10,
        )
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["error"]["code"] == _METHOD_NOT_FOUND


@pytest.mark.asyncio
async def test_modern_request_from_a_disallowed_origin_is_rejected() -> None:
    """The newly admitted era keeps the SDK's Origin check (docs/mcp.md "Local security boundary")."""
    async with _client(False) as client:
        response = await post_modern(client, origin="http://evil.example", method="tools/list")
    assert response.status_code == 403
    assert "result" not in response.text


# --- 2025-11-25 (D8) ------------------------------------------------------------------------------

_LEGACY_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "capture", "version": "0.0.0"},
    },
}
_LEGACY_LISTS = ("resources/list", "tools/list", "resources/templates/list")


def _v080(flag: bool) -> dict:
    expected = json.loads((_V080_DIR / ("flag_on.json" if flag else "flag_off.json")).read_text())
    expected["initialize"]["result"]["serverInfo"]["version"] = package_version()
    return expected


@pytest.mark.asyncio
@_FLAGS
async def test_legacy_discovery_equals_v080(flag: bool) -> None:
    async with _client(flag) as client:
        actual = {
            "initialize": (
                await client.post(
                    "/mcp",
                    headers=negotiated_headers(origin=_ORIGIN, protocol_version=None),
                    json=_LEGACY_INITIALIZE,
                )
            ).json()
        }
        for method in _LEGACY_LISTS:
            actual[method] = await _legacy(
                client, {"jsonrpc": "2.0", "id": 2, "method": method, "params": {}}
            )
    assert actual == _v080(flag)


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["skills/list", "skills/get"])
async def test_legacy_skills_methods_are_method_not_found(method: str) -> None:
    params = {"uri": skill_uri(READING_ANSWERS_SKILL)} if method == "skills/get" else {}
    async with _client(True) as client:
        body = await _legacy(
            client, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        )
    assert body["error"]["code"] == _METHOD_NOT_FOUND


@pytest.mark.asyncio
@pytest.mark.parametrize("name", [READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL])
async def test_legacy_skill_resource_read_is_the_unknown_resource_error(name: str) -> None:
    """The same error that the SDK gives for any unknown URI, as v0.8.0 gave for this one."""
    uri = skill_uri(name)
    unknown = "skill://other/none/SKILL.md"
    async with _client(True) as client:
        hidden = await _legacy(
            client, {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri}}
        )
        missing = await _legacy(
            client,
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": unknown}},
        )
    assert hidden["error"] == {
        "code": _INVALID_PARAMS,
        "message": f"Unknown resource: {uri}",
        "data": {"uri": uri},
    }
    assert missing["error"] == {
        "code": _INVALID_PARAMS,
        "message": f"Unknown resource: {unknown}",
        "data": {"uri": unknown},
    }


# --- Both eras ------------------------------------------------------------------------------------


@pytest.mark.asyncio
@_FLAGS
async def test_modern_tools_list_equals_the_v080_tools(flag: bool) -> None:
    async with _client(flag) as client:
        modern = (await _modern_result(client, "tools/list"))["result"]
    assert modern["tools"] == _v080(flag)["tools/list"]["result"]["tools"]


_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.8.1", build_revision="f" * 40
)
_SNAPSHOT = SnapshotRef(
    snapshot_id="aip:snapshot:v1:" + "a" * 64, model_revision="sha256:" + "a" * 64
)
_OBSERVATION = {
    "environment": "demo",
    "window_start": "2026-08-26T00:00:00Z",
    "window_end": "2026-08-26T23:59:59Z",
}


def _fixture(increment: str, data_type: type) -> Any:
    path = _AI_FIXTURES / increment / "answered_full.json"
    return ArchitectureAnswer[data_type].model_validate(json.loads(path.read_text()))


class _StubService:
    """Each method returns one fixed, valid answer; both eras must deliver it unchanged."""

    def get_service_dependencies(self, _request):
        return _fixture("i1", contracts.ServiceDependenciesData)

    def get_evidence(self, _request):
        return _fixture("i2", contracts.EvidenceData)

    def get_architecture_drift(self, _request):
        return _fixture("i3", contracts.ArchitectureDriftData)

    def get_service_dependencies_by_locality(self, _request):
        return locality.refusal_answer(
            _PRODUCER, _SNAPSHOT, locality_contracts.LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE
        )

    def get_api_consumer_usage(self, _request):
        return api_usage.refusal_answer(
            _PRODUCER,
            _SNAPSHOT,
            api_usage_contracts.ApiUsageLimitationCode.MEASUREMENT_WINDOW_NOT_AVAILABLE,
        )

    def get_destination_consumers(self, _request):
        return destination.refusal_answer(
            _PRODUCER, _SNAPSHOT, destination_consumer_contracts.LimitationCode.NO_ACCEPTED_CAPTURE
        )

    def get_binding_picture(self, _request):
        return binding_picture.refusal_answer(
            _PRODUCER, _SNAPSHOT, binding_picture_contracts.LimitationCode.NO_ACCEPTED_CAPTURE
        )


_TOOL_CALLS = {
    "get_service_dependencies": {
        "service_id": "service:order-service",
        "observation_context": _OBSERVATION,
    },
    "get_evidence": {
        "evidence_refs": ["evidence:declared:" + "1" * 64],
        "snapshot_id": _SNAPSHOT.snapshot_id,
    },
    "get_architecture_drift": {
        "service_id": "service:order-service",
        "observation_context": _OBSERVATION,
    },
    "get_service_dependencies_by_locality": {
        "mode": "query",
        "subject_service_id": "service:orders",
        "environment": "production",
        "first_day": "2026-09-28",
        "last_day": "2026-09-28",
    },
    "get_api_consumer_usage": {
        "mode": "query",
        "target": {"kind": "GATEWAY_ROUTE", "id": "gateway-route:owned:" + "b" * 64},
        "gateway_instance_id": "gw-prod-1",
        "environment": "prod",
        "window_start": "2026-10-13T10:00:00Z",
        "window_end": "2026-10-13T10:10:00Z",
    },
    "get_destination_consumers": {
        "mode": "query",
        "destination_id": "topic:owned:" + "b" * 64,
        "broker_id": "kafka:cluster-a",
        "environment": "prod",
    },
    "get_binding_picture": {
        "mode": "query",
        "bounded_context_id": "catalog-management",
        "environment": "prod",
    },
}


def test_the_regression_covers_every_tool() -> None:
    v080_tools = _v080(True)["tools/list"]["result"]["tools"]
    assert sorted(_TOOL_CALLS) == [tool["name"] for tool in v080_tools]


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", sorted(_TOOL_CALLS))
async def test_every_tool_answers_the_same_on_both_eras(tool: str) -> None:
    service = _StubService()
    expected = getattr(service, tool)(None).model_dump(mode="json")
    arguments = {"request": _TOOL_CALLS[tool]}
    async with _client(True, get_service=lambda: service) as client:
        legacy = await call_negotiated(client, origin=_ORIGIN, name=tool, arguments=arguments)
        modern = await call_modern(client, origin=_ORIGIN, name=tool, arguments=arguments)
    assert legacy["isError"] is False
    assert legacy["structuredContent"] == expected
    for key in ("isError", "structuredContent", "content"):
        assert modern[key] == legacy[key], key


# --- Skill files and drift guards -----------------------------------------------------------------

_CONTRACT_MODULES = (
    contracts,
    binding_picture_contracts,
    api_usage_contracts,
    destination_consumer_contracts,
    locality_contracts,
)
_CODE = re.compile(r"`([A-Z][A-Z0-9_]+)`")
_TOOL = re.compile(r"`(get_[a-z_]+)`")


def _skill_body(name: str) -> str:
    return _skill_bytes(name).decode("utf-8")


def _contract_codes() -> set[str]:
    codes: set[str] = set()
    for module in _CONTRACT_MODULES:
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, StrEnum):
                codes.update(member.value for member in value)
    return codes


@pytest.mark.parametrize("name", [READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL])
def test_skill_frontmatter_has_name_and_description_only(name: str) -> None:
    """Spec §2: no host permission fields such as `allowed-tools`."""
    frontmatter = parse_frontmatter(_skill_body(name))
    assert sorted(frontmatter) == ["description", "name"]
    assert frontmatter["name"] == name


@pytest.mark.parametrize("name", [READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL])
def test_each_tool_a_skill_names_exists(name: str) -> None:
    v080_tools = {tool["name"] for tool in _v080(True)["tools/list"]["result"]["tools"]}
    named = set(_TOOL.findall(_skill_body(name)))
    assert named
    assert named <= v080_tools


@pytest.mark.parametrize("name", [READING_ANSWERS_SKILL, BINDING_PICTURE_SKILL])
def test_each_code_a_skill_names_is_a_contract_enum_value(name: str) -> None:
    named = set(_CODE.findall(_skill_body(name)))
    assert named
    assert named <= _contract_codes(), named - _contract_codes()


def test_the_binding_picture_skill_names_every_crossing_and_served_status() -> None:
    body = _skill_body(BINDING_PICTURE_SKILL)
    contract = binding_picture_contracts
    served_statuses = {"PROMISED_AND_OBSERVED", "PROMISED_NOT_OBSERVED", "UNRESOLVED"}
    assert served_statuses <= {status.value for status in contract.AssessmentStatus}
    for code in [*(crossing.value for crossing in contract.Crossing), *served_statuses]:
        assert f"`{code}`" in body, code
    assert f"`{contract.LimitationCode.CROSS_BROKER_DELIVERY_NOT_ESTABLISHED.value}`" in body
