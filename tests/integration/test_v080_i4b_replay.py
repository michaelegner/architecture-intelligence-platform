"""v0.8 I4b E8: the frozen live-run package replays through the production import and the service.

Inputs are the committed bytes of `0.8.0/i4-evidence/` (B-R, A-R, A-K, the agent's frozen plan, its
extracted request, the recordings, the scoring) with the I1 declarations, mappings and EventCatalog
and the I3 after-wave declarations, under the source ids of the run's AIP profiles
(`harness/v08/i4/environment/config.{before,after}.yaml`), with the producer of the recorded answers.

The snapshot id is a digest of the graph state, and that state holds each declaration's absolute
`source_file`: the run read `/app/sokol111-v08/...`, a replay reads this checkout. So the snapshot
id, and every evidence ref bound to it, cannot replay byte for byte (I4b run record, S5). Every
other field must: answers are compared without the snapshot block and with each row's refs reduced
to their count per kind.

1. Before-wave: the agent's frozen request, re-issued through the MCP surface the agent used, gives
   the answer in its transcript; over REST, the agent's request and the report request give the
   frozen recording; the citation check of the frozen recording gives the frozen `citations.json`.
2. After-wave, on a clean graph: the report request gives the frozen `answers-after.json`, and Proof
   C passes against `expected-after.json`.
3. The report rendered from the package manifest is the frozen `report.html`, byte for byte.
"""

import json
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.main import create_app
from app.mcp.app import mcp_session_manager_lifespan
from tests.support.negotiated_mcp_client import call_negotiated

from .binding_picture_support import (
    DATABASE,
    ENV,
    I1,
    KAFKA,
    LOCAL,
    REPO,
    SPEC,
    capture,
    directory,
    mapping,
    run_import,
)

sys.path.insert(0, str(REPO / "harness/v08/i4"))

import citations
import plan_format
import proof_c
import record_answers
import report

PACKAGE = SPEC / "i4-evidence"
I3_DECLARATIONS = SPEC / "i3-evidence/declarations"
ORIGIN = "http://localhost"
# The producer of the recorded answers (the run's AIP image).
RECORDED = json.loads((PACKAGE / "answers-before.json").read_text())
PRODUCER = Producer(**RECORDED["report_request"]["answer"]["producer"])


def _json(name: str) -> dict:
    return json.loads((PACKAGE / name).read_text())


def _clean(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _catalog():
    from app.sources.model import EventCatalogSourceConfig

    return EventCatalogSourceConfig(id="sokol111-catalog", root=I1, environment=ENV)


def _before_wave(driver) -> list:
    return run_import(
        driver,
        directories=[
            directory("sokol111-declarations-sokol111-local", I1 / "declarations/sokol111-local")
        ],
        kafka_consumer_state=[capture(LOCAL, PACKAGE / "captures/b-r", "sokol111-kafka")],
        kafka_service_mappings=[
            mapping(LOCAL, I1 / "mapping/sokol111-local").model_copy(
                update={"id": "sokol111-mapping"}
            )
        ],
        event_catalogs=[_catalog()],
    )


def _after_wave(driver) -> list:
    return run_import(
        driver,
        directories=[
            directory("sokol111-declarations-sokol111-local", I3_DECLARATIONS / "sokol111-local"),
            directory("sokol111-declarations-sokol111-kafka", I3_DECLARATIONS / "sokol111-kafka"),
        ],
        kafka_consumer_state=[
            capture(LOCAL, PACKAGE / "captures/a-r", "sokol111-kafka"),
            capture(KAFKA, PACKAGE / "captures/a-k", "sokol111-kafka-target"),
        ],
        kafka_service_mappings=[
            mapping(LOCAL, I1 / "mapping/sokol111-local").model_copy(
                update={"id": "sokol111-mapping"}
            ),
            mapping(KAFKA, I1 / "mapping/sokol111-kafka").model_copy(
                update={"id": "sokol111-mapping-kafka"}
            ),
        ],
        event_catalogs=[_catalog()],
    )


def _app(tmp_path, driver):
    config = tmp_path / "config.yaml"
    config.write_text(
        "architecture_intelligence:\n"
        "  sources:\n    directories: []\n"
        "  llm:\n    enabled: false\n"
        "  experimental:\n    binding-picture: true\n"
        f"  mcp:\n    allowed-origins: ['{ORIGIN}']\n    allowed-hosts: ['localhost']\n"
    )
    app = create_app(config)
    app.state.architecture_intelligence_service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=PRODUCER
    )
    app.state.driver = driver
    return app


async def _mcp(app, request: dict) -> dict:
    """One get_binding_picture call through the MCP surface, as the agent made it."""
    import httpx

    async with mcp_session_manager_lifespan(app.state.mcp_server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            result = await call_negotiated(
                client, origin=ORIGIN, name="get_binding_picture", arguments={"request": request}
            )
    assert result["isError"] is False, result
    return result["structuredContent"]


@pytest.fixture(autouse=True)
def clean_database(driver):
    _clean(driver)
    yield
    _clean(driver)


def test_the_package_is_the_committed_bytes() -> None:
    subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=PACKAGE, check=True)
    # E1: the keys are the ones committed in I4a.
    plan_format.load_key()
    proof_c.check_reference_digest()


def _unbound(answer: dict) -> str:
    """The answer without what the snapshot id binds: the snapshot block, and each row's evidence
    refs reduced to their count per kind."""
    data = answer.get("data") or {}
    rows = [
        {k: len(v) if k.endswith("_evidence_refs") else v for k, v in row.items()}
        for row in data.get("rows", [])
    ]
    unbound = {k: v for k, v in answer.items() if k != "snapshot"}
    unbound["data"] = {**data, "rows": rows} if data else data
    return record_answers.canonical(unbound)


def _rest(app, request: dict) -> dict:
    response = TestClient(app).post("/api/binding-picture", json=request)
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_before_wave_replays_the_agents_answer_and_the_recording(driver, tmp_path) -> None:
    assert all(run.stats.committed for run in _before_wave(driver))
    app = _app(tmp_path, driver)
    [extracted] = _json("agent-requests.json")
    # The MCP surface the agent used gives the answer in its transcript.
    assert _unbound(await _mcp(app, extracted["request"])) == _unbound(
        extracted["transcript_answer"]
    )
    # REST gives the frozen recording: the agent's request and the report request.
    [exchange] = RECORDED["agent_requests"]
    assert _unbound(_rest(app, exchange["request"])) == _unbound(exchange["answer"])
    report_request = RECORDED["report_request"]
    replayed = _rest(app, report_request["request"])
    assert _unbound(replayed) == _unbound(report_request["answer"])
    assert len(replayed["data"]["rows"]) == 9
    # The citation check of the frozen recording gives the frozen result.
    plan = plan_format.load_plan(PACKAGE / "plan.json")
    checked = citations.check(plan, plan_format.load_key(), RECORDED, _json("scoring.json"))
    assert record_answers.canonical(checked) == record_answers.canonical(_json("citations.json"))


def test_after_wave_replays_the_recording_and_proof_c(driver, tmp_path) -> None:
    assert all(run.stats.committed for run in _after_wave(driver))
    frozen = _json("answers-after.json")["report_request"]
    replayed = _rest(_app(tmp_path, driver), frozen["request"])
    assert _unbound(replayed) == _unbound(frozen["answer"])
    expected = json.loads(plan_format.EXPECTED_AFTER.read_text())
    assert proof_c.check({"report_request": {"answer": replayed}}, expected)["result"] == "PASSED"


def test_the_report_renders_to_the_frozen_bytes() -> None:
    html = report.render(PACKAGE / "report-inputs.json")
    assert report.wording_problems(html) == []
    assert html == (PACKAGE / "report.html").read_text()
