"""v0.8 I2c B7 (flag on) and B9: the experimental tool over the real negotiated MCP transport and
REST, from the real `create_app` with `experimental.binding-picture`, on the committed C1 package.

Every MCP answer must validate against the server's own advertised `outputSchema` and against the
committed frozen schema; MCP, REST and the service must give the same answer. The evidence mode
must resolve the full chain of a C1 binding at the same snapshot and refuse everything it did not
issue. Integration because the C1 state comes from the production import into Neo4j.
"""

import json

import httpx
import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.architecture_intelligence.binding_picture_contracts import (
    BindingPictureEvidenceRequest,
    BindingPictureQueryRequest,
)
from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.schema_export import (
    BINDING_ANSWER_SCHEMA_PATH,
    BINDING_REQUEST_SCHEMA_PATH,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.main import create_app
from app.mcp.app import mcp_session_manager_lifespan
from tests.support.negotiated_mcp_client import (
    call_negotiated,
    negotiated_headers,
    negotiated_tools_list_body,
)

from .binding_picture_support import (
    DATABASE,
    I1,
    LOCAL,
    capture,
    catalog,
    directory,
    mapping,
    run_import,
)

ORIGIN = "http://localhost"
ANSWER_SCHEMA = json.loads(BINDING_ANSWER_SCHEMA_PATH.read_text())
REQUEST_SCHEMA = json.loads(BINDING_REQUEST_SCHEMA_PATH.read_text())
CONTEXT = {
    "bounded_context_id": "catalog-management",
    "environment": "local",
    "broker_ids": [LOCAL],
}
MEMBER_TEXT = ("kgo-", "172.20.")


@pytest.fixture(scope="module")
def c1(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
    runs = run_import(
        driver,
        directories=[directory("decl-local", I1 / "declarations/sokol111-local")],
        kafka_consumer_state=[capture(LOCAL, I1 / "c1")],
        kafka_service_mappings=[mapping(LOCAL, I1 / "mapping/sokol111-local")],
        event_catalogs=[catalog()],
    )
    assert all(run.stats.committed for run in runs)
    yield
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _app(tmp_path, driver, version: str = "0.8.0"):
    config = tmp_path / f"config-{version}.yaml"
    config.write_text(
        "architecture_intelligence:\n"
        "  sources:\n    directories: []\n"
        "  llm:\n    enabled: false\n"
        "  experimental:\n    binding-picture: true\n"
        "  mcp:\n"
        f"    allowed-origins: ['{ORIGIN}']\n"
        "    allowed-hosts: ['localhost']\n"
    )
    app = create_app(config)
    producer = Producer(
        name="architecture-intelligence-platform", version=version, build_revision="t"
    )
    app.state.architecture_intelligence_service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=producer
    )
    app.state.driver = driver
    return app


def _valid(payload: dict, advertised: dict) -> dict:
    for schema in (advertised, ANSWER_SCHEMA):
        assert list(jsonschema.Draft202012Validator(schema).iter_errors(payload)) == []
    return payload


async def _mcp(app, *calls: dict) -> tuple[list[str], dict, list[dict]]:
    """tools/list, the advertised outputSchema, and each call's structuredContent."""
    async with mcp_session_manager_lifespan(app.state.mcp_server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            listed = await client.post(
                "/mcp", headers=negotiated_headers(origin=ORIGIN), json=negotiated_tools_list_body()
            )
            tools = listed.json()["result"]["tools"]
            [tool] = [t for t in tools if t["name"] == "get_binding_picture"]
            results = []
            for request in calls:
                result = await call_negotiated(
                    client,
                    origin=ORIGIN,
                    name="get_binding_picture",
                    arguments={"request": request},
                )
                assert result["isError"] is False, result
                results.append(result["structuredContent"])
            return [t["name"] for t in tools], tool["outputSchema"], results


def _rest(app, request: dict) -> dict:
    body = {k: v for k, v in request.items() if k != "mode"}
    route = "/api/binding-picture" + ("/evidence" if request["mode"] == "evidence" else "")
    response = TestClient(app).post(route, json=body)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_seven_tools_and_mcp_rest_service_parity_on_c1(c1, driver, tmp_path) -> None:
    app = _app(tmp_path, driver)
    query = {"mode": "query", **CONTEXT}
    assert list(jsonschema.Draft202012Validator(REQUEST_SCHEMA).iter_errors(query)) == []
    names, advertised, [mcp_answer] = await _mcp(app, query)
    assert names == sorted(names) and len(names) == 7 and "get_binding_picture" in names
    service = app.state.architecture_intelligence_service
    direct = service.get_binding_picture(BindingPictureQueryRequest.model_validate(query))
    assert _valid(mcp_answer, advertised) == direct.model_dump(mode="json") == _rest(app, query)
    assert len(mcp_answer["data"]["rows"]) == 9


@pytest.mark.asyncio
async def test_the_evidence_mode_resolves_the_full_chain_and_refuses_the_rest(
    c1, driver, tmp_path
) -> None:
    app = _app(tmp_path, driver)
    service = app.state.architecture_intelligence_service
    query = service.get_binding_picture(
        BindingPictureQueryRequest(mode="query", **CONTEXT)
    ).model_dump(mode="json")
    snapshot_id = query["snapshot"]["snapshot_id"]
    [row] = [
        r
        for r in query["data"]["rows"]
        if r["topic_name"] == "catalog.product.events"
        and r["consumer_service_id"] == "service:ecommerce-product-query-service"
    ]
    chain = sorted(
        [
            *row["promise_evidence_refs"],
            *row["attachment_evidence_refs"],
            *row["mapping_evidence_refs"],
        ]
    )
    forged = "binding-evidence:" + "0" * 64
    other_context = service.get_binding_picture(
        BindingPictureQueryRequest(mode="query", **{**CONTEXT, "bounded_context_id": "storefront"})
    ).model_dump(mode="json")
    cross = other_context["data"]["rows"][0]["attachment_evidence_refs"][0]
    evidence = {"mode": "evidence", "snapshot_id": snapshot_id, **CONTEXT, "evidence_refs": chain}
    mixed = {**evidence, "evidence_refs": sorted({*chain, forged, cross} - {None})}
    stale = {**evidence, "snapshot_id": "aip:snapshot:v1:" + "2" * 64}
    _, advertised, [full, partial, refused] = await _mcp(app, evidence, mixed, stale)

    _valid(full, advertised)
    assert full["outcome"] == "ANSWERED" and full["limitations"] == []
    kinds = {e["kind"]: e["evidence"] for e in full["data"]["entries"]}
    assert set(kinds) == {"CATALOG_PROMISE", "KAFKA_ATTACHMENT", "KAFKA_SERVICE_MAPPING"}
    promises = [e["evidence"] for e in full["data"]["entries"] if e["kind"] == "CATALOG_PROMISE"]
    product_updated = [p for p in promises if p["event_id"] == "ProductUpdated"]
    assert product_updated and product_updated[0]["topic"] == "catalog.product.events"
    assert product_updated[0]["lookup_repository"] == "Sokol111/ecommerce-catalog-service-api"
    assert product_updated[0]["lookup_path"] == "pkg/events/topics.go"
    assert product_updated[0]["event_version"] == "1.0.0"
    assert kinds["KAFKA_SERVICE_MAPPING"]["service_id"] == "service:ecommerce-product-query-service"
    assert (
        service.get_binding_picture_evidence(
            BindingPictureEvidenceRequest.model_validate(evidence)
        ).model_dump(mode="json")
        == full
        == _rest(app, evidence)
    )

    _valid(partial, advertised)
    assert partial["outcome"] == "PARTIAL"
    status = {e["ref"]: e["status"] for e in partial["data"]["entries"]}
    assert status[forged] == "NOT_RESOLVED" and status[cross] == "NOT_RESOLVED"
    assert [i["code"] for i in partial["limitations"]] == ["EVIDENCE_REF_NOT_RESOLVED"]

    _valid(refused, advertised)
    assert (refused["outcome"], [i["code"] for i in refused["limitations"]]) == (
        "NOT_ANSWERED",
        ["SNAPSHOT_NOT_AVAILABLE"],
    )
    # Every ref minted for the nine C1 rows resolves at the same snapshot (batches of at most 20).
    every = sorted(
        {
            ref
            for r in query["data"]["rows"]
            for ref in (
                *r["promise_evidence_refs"],
                *r["attachment_evidence_refs"],
                *r["mapping_evidence_refs"],
            )
        }
    )
    for start in range(0, len(every), 20):
        batch = {**evidence, "evidence_refs": every[start : start + 20]}
        answer = service.get_binding_picture_evidence(
            BindingPictureEvidenceRequest.model_validate(batch)
        ).model_dump(mode="json")
        assert answer["outcome"] == "ANSWERED", start
    text = json.dumps([full, partial])
    for fragment in MEMBER_TEXT:
        assert fragment not in text


@pytest.mark.asyncio
async def test_two_apps_with_overlapping_lifespans_dispatch_to_their_own_service(
    c1, driver, tmp_path
) -> None:
    first, second = _app(tmp_path, driver, "0.8.0"), _app(tmp_path, driver, "0.8.1")
    query = {"mode": "query", **CONTEXT}
    answers = []
    async with (
        mcp_session_manager_lifespan(first.state.mcp_server),
        mcp_session_manager_lifespan(second.state.mcp_server),
    ):
        for app in (first, second, first):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
                result = await call_negotiated(
                    client,
                    origin=ORIGIN,
                    name="get_binding_picture",
                    arguments={"request": query},
                )
            answers.append(result["structuredContent"]["producer"]["version"])
    assert answers == ["0.8.0", "0.8.1", "0.8.0"]
