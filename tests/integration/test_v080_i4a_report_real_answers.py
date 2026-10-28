"""v0.8 I4a: the citation checker and the report generator on real service answers (not the
qualification tier).

Dependency-only behaviour: the exact answer and evidence shapes come from the service over Neo4j
(row fields, refs bound to the snapshot and the query, evidence entries). A hand-built unit fixture
could drift from them. The inputs are the I2 vectors, not the frozen I3 release evidence: C1 as the
before-wave stand-in, then, on a clean graph, the I2 two-broker fixture as the after-wave stand-in.
"""

import json
import sys

import pytest

from app.architecture_intelligence.binding_picture_contracts import (
    BindingPictureEvidenceRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from tests.unit.v080_i4_plans import KEY, perfect_plan, write_manifest

from .binding_picture_support import (
    DATABASE,
    ENV,
    I1,
    KAFKA,
    LOCAL,
    PRODUCER,
    REPO,
    SPEC,
    answer,
    capture,
    catalog,
    directory,
    mapping,
    run_import,
)

sys.path.insert(0, str(REPO / "harness/v08/i4"))

import citations
import proof_c
import report
import score

FIXTURE = SPEC / "i2-vectors/two-broker"
CONTEXT = {"bounded_context_id": "catalog-management", "environment": ENV}


def _clean(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _evidence(driver, snapshot_id: str, refs: list[str]) -> dict:
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    request = BindingPictureEvidenceRequest(
        mode="evidence", snapshot_id=snapshot_id, broker_ids=[LOCAL], evidence_refs=refs, **CONTEXT
    )
    return service.get_binding_picture_evidence(request).model_dump(mode="json")


@pytest.fixture
def real_inputs(driver):
    _clean(driver)
    run_import(
        driver,
        directories=[directory("decl-local", I1 / "declarations/sokol111-local")],
        kafka_consumer_state=[capture(LOCAL, I1 / "c1")],
        kafka_service_mappings=[mapping(LOCAL, I1 / "mapping/sokol111-local")],
        event_catalogs=[catalog()],
    )
    before = answer(driver, broker_ids=[LOCAL])
    snapshot = before["snapshot"]["snapshot_id"]
    plan = perfect_plan()
    for item in plan["items"]:
        for citation in item["architecture_citations"]:
            citation["snapshot_id"] = snapshot
    category = next(
        r for r in before["data"]["rows"] if r["topic_name"] == "catalog.category.events"
    )
    plan["items"][2]["architecture_citations"] = [
        {"snapshot_id": snapshot, "evidence_refs": category["attachment_evidence_refs"]}
    ]
    request = {**CONTEXT, "broker_ids": [LOCAL]}
    recording = {
        "agent_requests": [{"index": 0, "request": request, "answer": before}],
        "evidence": [
            {
                "request": {**request, "snapshot_id": snapshot},
                "answer": _evidence(driver, snapshot, category["attachment_evidence_refs"]),
            }
        ],
    }
    _clean(driver)
    run_import(
        driver,
        directories=[
            directory("decl-local", FIXTURE / "declarations/sokol111-local"),
            directory("decl-kafka", FIXTURE / "declarations/sokol111-kafka"),
        ],
        kafka_consumer_state=[
            capture(LOCAL, FIXTURE / "captures/redpanda"),
            capture(KAFKA, FIXTURE / "captures/kafka"),
        ],
        kafka_service_mappings=[
            mapping(LOCAL, FIXTURE / "mapping/sokol111-local"),
            mapping(KAFKA, FIXTURE / "mapping/sokol111-kafka"),
        ],
        event_catalogs=[catalog()],
    )
    after = answer(driver, broker_ids=[KAFKA, LOCAL])
    return before, after, plan, recording


def test_citations_resolve_on_real_answers(real_inputs):
    _, _, plan, recording = real_inputs
    scoring = score.score(plan, [], KEY, plan["allow_lists"], {"result": "PASSED"}, {})
    result = citations.check(plan, KEY, recording, scoring)
    assert recording["evidence"][0]["answer"]["data"]["entries"][0]["status"] == "RESOLVED"
    assert {c["id"]: c["verdict"] for c in result["coverage"]} == dict.fromkeys(
        ("K1", "K2", "K3", "K4"), "COVERED"
    )
    assert result["passed"] is True


def test_report_on_real_answers(real_inputs, tmp_path):
    before, after, plan, recording = real_inputs
    path = write_manifest(tmp_path, before, after, plan, recording)
    html = report.render(path)
    assert html == report.render(path)
    assert report.wording_problems(html) == []
    crossing = [r for r in after["data"]["rows"] if r["crossing"] in ("INBOUND", "OUTBOUND")]
    assert len(crossing) == 6
    chains = html[html.index("<h2>3. Agent") : html.index("Proof A: the plan")]
    assert chains.count('<span class="agent">m-') == len(crossing)  # one plan item per chain
    assert "none: observed, undeclared" in html and "promised: " in html


def test_the_two_broker_answer_is_proof_c(real_inputs):
    """The I2 two-broker fixture is the source of expected-after.json, so its real answer passes."""
    _, after, _, _ = real_inputs
    expected = json.loads(proof_c.EXPECTED_AFTER.read_text())
    assert proof_c.check({"report_request": {"answer": after}}, expected)["result"] == "PASSED"
