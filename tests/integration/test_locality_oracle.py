"""v0.6.0 I3.2c/I3.3a: the independent I3 oracle executed against the real service on real Neo4j
(I3 spec §14, §15 I3.2/I3.3 rows; `i3-expected-answer-matrix.md`; decision record D15).

Every answer and property case of `i3-vectors/expected-answers.json` runs here, in both modes
(`query`, I3.2c; `evidence` and the legacy-reader isolation case P06, I3.3a).
- **Answer cases** must match their complete expected `LocalityAnswer` under the matrix §2 procedure
  (`locality_oracle.matcher`). They must also pass the published 0.6 answer schema and the
  `LocalityAnswer` model.
- **Property cases** run their stated steps, then check every `assert` item. The prose
  `equals_expr` items are decided here, per case, from the generated inputs.

The oracle is read-only. A disagreement is a defect in the implementation, or goes back to the
specification; the expectation is never edited to match (I3 §17 stop condition).

Not executed here:
- the request-validation cases (Q01-Q08) are checked by
  `tests/unit/test_v060_i3_expected_answers.py`.

`test_every_case_is_executed` pins the partition, so no case can be skipped silently.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.ai.cypher_validator import CypherValidationError
from app.ai.question_service import ArchitectureQuestionService
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityRequest,
)
from app.architecture_intelligence.locality_projection import internal_request
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ObservationContextInput,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.schema_export import LOCALITY_ANSWER_SCHEMA_PATH
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.revision_fence import read_revision
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument
from tests.integration.locality_oracle import world
from tests.integration.locality_oracle.matcher import (
    check_property,
    explain_mismatch,
    match,
    resolve,
    substitute,
)
from tests.integration.test_api_architecture_intelligence_equivalence import _client as _rest_client
from tests.integration.test_locality_rehearsal_replay import FIXTURE, PRODUCER

DATABASE = world.DATABASE
ORACLE = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "docs/specifications/0.6.0/i3-vectors/expected-answers.json"
    ).read_text(encoding="utf-8")
)
CASES = {case["id"]: case for case in ORACLE["cases"]}
ANSWER_SCHEMA = json.loads(LOCALITY_ANSWER_SCHEMA_PATH.read_text(encoding="utf-8"))

QUERY_ANSWER_CASES = sorted(
    case_id
    for case_id, case in CASES.items()
    if case["kind"] == "answer" and case["request"]["mode"] == "query"
)
# The rehearsal cases run together, C2 first, so the C1 cases and P08 (defined right after them)
# share one replay (`world.replay_rehearsal` reuses an unchanged replayed snapshot).
REHEARSAL_ANSWER_CASES = ["X03", "X01", "X02"]
K_ANSWER_CASES = [
    case_id for case_id in QUERY_ANSWER_CASES if case_id not in REHEARSAL_ANSWER_CASES
]
QUERY_PROPERTY_CASES = ["P01", "P02", "P03", "P04", "P07", "P08", "P09"]
# I3.3a: the evidence mode and the legacy-reader isolation checks.
EVIDENCE_ANSWER_CASES = sorted(
    case_id
    for case_id, case in CASES.items()
    if case["kind"] == "answer" and case["request"]["mode"] == "evidence"
)
EVIDENCE_PROPERTY_CASES = ["P05", "P06"]
REQUEST_CASES = sorted(case_id for case_id, case in CASES.items() if case["kind"] == "request")

K_DAY = "2026-09-28"
K_REQUEST = {
    "mode": "query",
    "subject_service_id": "service:orders",
    "environment": "production",
    "first_day": K_DAY,
    "last_day": K_DAY,
}
K_CLUSTER = "11111111-1111-4111-8111-000000000001"
O1 = "operation:service:pricing:GET:/prices"

needs_rehearsal = pytest.mark.skipif(
    not (FIXTURE / "otlp.jsonl").exists(), reason="the rehearsal fixture is not present"
)


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _ask(driver, request: dict, *, service: ArchitectureIntelligenceService | None = None) -> dict:
    """One request through the semantic service, dispatched on `mode` as the adapters will (D1).
    The answer must pass both validators."""
    service = service or _service(driver)
    parsed = ServiceDependenciesByLocalityRequest.model_validate(request).root
    answer = (
        service.get_service_dependencies_by_locality(parsed)
        if isinstance(parsed, LocalityQueryRequest)
        else service.resolve_scoped_locality_evidence(parsed)
    )
    payload = json.loads(answer.model_dump_json())
    LocalityAnswer.model_validate(payload)
    errors = [
        error.message
        for error in jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(payload)
    ]
    assert errors == [], errors
    return payload


def _identity(uid: str) -> dict:
    return {"cluster_uid": K_CLUSTER, "namespace": "shop", "kind": "Deployment", "uid": uid}


# --- The partition -------------------------------------------------------------------------------


def test_every_case_is_executed():
    executed = [
        *QUERY_ANSWER_CASES,
        *QUERY_PROPERTY_CASES,
        *EVIDENCE_ANSWER_CASES,
        *EVIDENCE_PROPERTY_CASES,
    ]
    assert len(executed) == len(set(executed))
    assert set(executed) | set(REQUEST_CASES) == set(CASES)
    assert len(QUERY_ANSWER_CASES) == 25 and QUERY_ANSWER_CASES[0] == "X01"
    assert EVIDENCE_ANSWER_CASES == ["X26", "X27", "X28"]
    rehearsal = {c for c in QUERY_ANSWER_CASES if CASES[c]["inputs"]["world"] == "rehearsal"}
    assert rehearsal == set(REHEARSAL_ANSWER_CASES)
    property_cases = {case_id for case_id, case in CASES.items() if case["kind"] == "property"}
    assert property_cases == set(QUERY_PROPERTY_CASES) | set(EVIDENCE_PROPERTY_CASES)


# --- Answer cases --------------------------------------------------------------------------------


def _assert_answer_matches(driver, tmp_path, case_id: str) -> None:
    case = CASES[case_id]
    prebound = world.build(driver, tmp_path, case["inputs"])

    actual = _ask(driver, substitute(case["request"], prebound))

    expected = case["expected"]
    assert match(expected, actual, prebound) is not None, (
        explain_mismatch(substitute(expected, prebound), actual) or "no injective binding matches",
        json.dumps(actual, indent=1, sort_keys=True),
    )


@needs_rehearsal
@pytest.mark.parametrize("case_id", REHEARSAL_ANSWER_CASES)
def test_the_rehearsal_answer_matches_the_oracle(driver, tmp_path, case_id):
    _assert_answer_matches(driver, tmp_path, case_id)


@needs_rehearsal
def test_p08_a_c1_snapshot_is_refused_after_c2(driver, tmp_path):
    world.replay_rehearsal(driver, "c1")
    request = {
        **K_REQUEST,
        "environment": "locality-capture",
        "first_day": "2026-09-30",
        "last_day": "2026-09-30",
    }
    first = _ask(driver, request)
    world.import_rehearsal_capture(driver, tmp_path, "c2")
    stale = _ask(driver, {**request, "snapshot_id": first["snapshot"]["snapshot_id"]})
    latest = _ask(driver, request)

    _check("P08", {1: first, 3: stale, 4: latest})


@pytest.mark.parametrize("case_id", K_ANSWER_CASES)
def test_the_answer_matches_the_oracle(driver, tmp_path, case_id):
    _assert_answer_matches(driver, tmp_path, case_id)


# --- Property cases ------------------------------------------------------------------------------


def _check(case_id: str, steps: dict[int, Any], custom: dict[str, bool] | None = None) -> None:
    for item in CASES[case_id]["assert"]:
        check_property(item, steps, custom)


def _generated_ids(inputs: dict) -> list[str]:
    return sorted(world.v2_id(v2) for v2 in world.generated_v2(inputs))


def test_p01_s_5_and_500_candidates_read_k_400(driver, tmp_path):
    inputs = CASES["P01"]["inputs"]
    world.build(driver, tmp_path, inputs)

    step = _ask(driver, K_REQUEST)

    path = "cursor(data.inventory.next_cursor).after_id"
    _check("P01", {1: step}, {path: resolve(path, step) == _generated_ids(inputs)[399]})


def _two_pages(driver, request: dict) -> tuple[dict, dict]:
    first = _ask(driver, request)
    cursor = first["data"]["inventory"]["next_cursor"]
    assert cursor is not None
    return first, _ask(driver, {**request, "cursor": cursor})


def test_p02_the_i2_page_boundary_is_walked_on_one_snapshot(driver, tmp_path):
    inputs = CASES["P02"]["inputs"]
    world.build(driver, tmp_path, inputs)

    first, second = _two_pages(driver, K_REQUEST)

    seen = [c["v2_evidence_id"] for page in (first, second) for c in page["data"]["candidates"]]
    _check(
        "P02",
        {1: first, 2: second},
        {
            "union of candidates[*].v2_evidence_id over both pages": sorted(seen)
            == _generated_ids(inputs)
        },
    )


def test_p03_the_workload_cap_splits_a_page_that_i2_did_not_truncate(driver, tmp_path):
    inputs = CASES["P03"]["inputs"]
    world.build(driver, tmp_path, inputs)

    first, second = _two_pages(driver, K_REQUEST)

    seen = [
        locality["workload"]["uid"]
        for page in (first, second)
        for locality in page["data"]["localities"]
    ]
    owners = sorted(pod["owner"]["uid"] for pod in world.generated_pods(inputs))
    _check(
        "P03",
        {1: first, 2: second},
        {"union of localities[*].workload.uid over both pages": sorted(seen) == owners},
    )


def test_p04_a_cursor_for_another_query_or_snapshot_is_refused(driver, tmp_path):
    world.build(driver, tmp_path, CASES["P04"]["inputs"])
    first = _ask(driver, K_REQUEST)
    cursor = first["data"]["inventory"]["next_cursor"]
    assert cursor is not None

    other_query = _ask(driver, {**K_REQUEST, "object_operation_id": O1, "cursor": cursor})
    # Step 3: a graph change - capture B, exactly as the K world defines it (X10's inputs).
    [capture_b] = [c for c in CASES["X10"]["inputs"]["captures"] if c["label"] == "B"]
    world.build_capture(driver, tmp_path, capture_b)
    changed = _ask(driver, {**K_REQUEST, "cursor": cursor})

    _check("P04", {1: first, 2: other_query, 4: changed})


@pytest.mark.parametrize("case_id", CASES["P07"]["inputs"]["inputs_of"])
def test_p07_permuted_import_and_span_order_give_identical_bytes(driver, tmp_path, case_id):
    case = CASES[case_id]
    answers = []
    for reverse in (False, True):
        prebound = world.build(driver, tmp_path / str(reverse), case["inputs"], reverse=reverse)
        answer = _ask(driver, substitute(case["request"], prebound))
        answers.append(json.dumps({**answer, "producer": None}, sort_keys=True))

    _check(
        "P07",
        {},
        {"canonical answer bytes without producer": answers[0] == answers[1]},
    )


def test_p09_the_r5_construction_on_a_partial_inventory_is_unknown(driver, tmp_path):
    world.build(driver, tmp_path, CASES["P09"]["inputs"])

    step = _ask(
        driver,
        {
            **K_REQUEST,
            "compare": [
                _identity("aaaaaaaa-0000-4000-8000-000000000001"),
                _identity("aaaaaaaa-0000-4000-8000-000000000002"),
            ],
        },
    )

    _check("P09", {1: step})


# --- Regressions and isolation (I3 §14 "Regression and isolation"; matrix S15) -----------------


def _graph_state(driver) -> tuple[int, int, int]:
    with driver.session(database=DATABASE) as session:
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        relations = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        return read_revision(session), nodes, relations


def _v0_5_answers(
    driver, snapshot_id: str, *, service: ArchitectureIntelligenceService | None = None
) -> list[dict]:
    service = service or _service(driver)
    context = ObservationContextInput(
        environment="production",
        window_start=datetime(2026, 9, 28, tzinfo=UTC),
        window_end=datetime(2026, 9, 28, 23, 59, 59, tzinfo=UTC),
    )
    answers = [
        service.get_service_dependencies(
            ServiceDependenciesRequest(service_id="service:orders", observation_context=context)
        ),
        service.get_architecture_drift(
            ArchitectureDriftRequest(service_id="service:orders", observation_context=context)
        ),
        service.get_evidence(
            EvidenceRequest(evidence_refs=[world.DECLARED_CALLS_EVIDENCE], snapshot_id=snapshot_id)
        ),
    ]
    return [answer.model_dump(mode="json", exclude={"generated_at"}) for answer in answers]


def test_the_locality_query_writes_nothing_and_leaves_v0_5_answers_unchanged(driver, tmp_path):
    case = CASES["X10"]
    prebound = world.build(driver, tmp_path, case["inputs"])
    state = _graph_state(driver)
    snapshot_id = _ask(driver, substitute(case["request"], prebound))["snapshot"]["snapshot_id"]
    before = _v0_5_answers(driver, snapshot_id)

    for case_id in ("X10", "X11", "X14", "X15", "X20", "X24"):
        _ask(driver, substitute(CASES[case_id]["request"], prebound))

    assert _graph_state(driver) == state
    assert _v0_5_answers(driver, snapshot_id) == before


def test_one_snapshot_is_shared_with_the_v0_5_answers_and_no_v2_adds_no_state(driver, tmp_path):
    """No separate fingerprint: the locality answer's snapshot is the canonical one every v0.5
    answer carries. Without v2 (X07), no conditional v2 key enters it (I2 D15.2), so it is the
    snapshot of the same graph without the scoped-evidence operational nodes."""
    prebound = world.build(driver, tmp_path, CASES["X07"]["inputs"])
    answer = _ask(driver, substitute(CASES["X07"]["request"], prebound))
    [dependencies, *_] = _v0_5_answers(driver, answer["snapshot"]["snapshot_id"])
    assert answer["snapshot"] == dependencies["snapshot"]

    with driver.session(database=DATABASE) as session:
        assert session.run("MATCH (v:ScopedObservedCallV2) RETURN count(v) AS c").single()["c"] == 0
        session.run(
            "MATCH (n) WHERE any(label IN labels(n) WHERE label STARTS WITH 'ScopedEvidence') "
            "DETACH DELETE n"
        ).consume()
    assert (
        _ask(driver, substitute(CASES["X07"]["request"], prebound))["snapshot"]
        == (answer["snapshot"])
    )


def test_with_a_mapping_artifact_every_read_still_shares_one_snapshot(driver, tmp_path):
    """I3.3a: a configured Path B mapping artifact enters the canonical snapshot state. The I2
    assessment and the locality answer must pass it as every v0.5 read does, or their snapshot_id
    would differ from the v0.5 answers' (one canonical snapshot, I2 §11)."""
    case = CASES["X04"]
    prebound = world.build(driver, tmp_path, case["inputs"])
    mapping = ServiceWorkloadMappingDocument(
        artifact_id="i3-oracle-mapping",
        artifact_revision="rev-1",
        locator="i3-oracle/service-workload-mapping.yaml",
        content_digest="a" * 64,
    )
    service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=PRODUCER, service_workload_mapping_document=mapping
    )
    request = LocalityQueryRequest.model_validate(substitute(case["request"], prebound))

    locality = service.get_service_dependencies_by_locality(request).snapshot
    assessment = service.assess_local_calls(internal_request(request))
    [dependencies, *_] = _v0_5_answers(driver, "aip:snapshot:v1:" + "0" * 64, service=service)

    assert locality is not None
    assert locality.model_dump() == dependencies["snapshot"]
    assert (assessment.snapshot_id, assessment.model_revision) == (
        locality.snapshot_id,
        locality.model_revision,
    )
    # Without the artifact the snapshot differs, so the test is not vacuous.
    assert (
        _ask(driver, substitute(case["request"], prebound))["snapshot"] != dependencies["snapshot"]
    )


# --- Evidence mode (I3.3a; D11, D16.1, D16.7) ----------------------------------------------------


def _current_snapshot(driver) -> str:
    return _ask(driver, K_REQUEST)["snapshot"]["snapshot_id"]


def _ref_symbols(value: Any) -> list[str]:
    text = json.dumps(value)
    return sorted(set(re.findall(r"\{\{(REF:[^{}]+)\}\}", text)))


@pytest.mark.parametrize("case_id", EVIDENCE_ANSWER_CASES)
def test_the_evidence_answer_matches_the_oracle(driver, tmp_path, case_id):
    """X26-X28. `SNAPSHOT_ID` is bound to the current snapshot of the built world (the request
    names it), and `REF:*` to the fixture's own evidence ids (matrix §2 rule 2)."""
    case = CASES[case_id]
    prebound = world.build(driver, tmp_path, case["inputs"])
    prebound["SNAPSHOT_ID"] = _current_snapshot(driver)
    prebound |= world.bind_refs(driver, case["inputs"], prebound, _ref_symbols(case["request"]))

    actual = _ask(driver, substitute(case["request"], prebound))

    expected = case["expected"]
    assert match(expected, actual, prebound) is not None, (
        explain_mismatch(substitute(expected, prebound), actual) or "no injective binding matches",
        json.dumps(actual, indent=1, sort_keys=True),
    )


def test_p05_capture_refs_of_a_positive_assessment_resolve_in_evidence_mode_only(driver, tmp_path):
    """R7: the assessment's Pod/owner capture refs resolve here although no Service-level
    DEPLOYED_AS makes them reachable for the legacy `get_evidence`."""
    world.build(driver, tmp_path, CASES["P05"]["inputs"])
    query = _ask(driver, K_REQUEST)
    [locality] = query["data"]["localities"]
    refs = sorted(
        {ref for item in locality["assessments"] for ref in item["capture_evidence_refs"]}
    )
    snapshot_id = query["snapshot"]["snapshot_id"]

    evidence = _ask(
        driver,
        {
            "mode": "evidence",
            "subject_service_id": "service:orders",
            "snapshot_id": snapshot_id,
            "refs": refs,
        },
    )
    legacy = _service(driver).get_evidence(
        EvidenceRequest(evidence_refs=refs, snapshot_id=snapshot_id)
    )

    _check(
        "P05",
        {1: query, 2: evidence},
        {
            "legacy get_evidence result": legacy.data is not None
            and legacy.data.records == []
            and legacy.data.missing_evidence_refs == refs
        },
    )


class _NlProvider:
    """A stub NL provider that proposes one fixed Cypher (as I2's isolation tests do)."""

    def __init__(self, cypher: str):
        self.cypher, self.composed = cypher, 0

    def generate_cypher(self, *, question, schema_description):
        return self.cypher

    def compose_answer(self, *, question, cypher, rows):
        self.composed += 1
        return "answer"


def test_p06_v2_stays_isolated_from_every_legacy_reader(driver, tmp_path):
    case = CASES["P06"]
    world.build(driver, tmp_path, case["inputs"])
    v2_ids = sorted(item["id"] for item in case["inputs"]["v2"])
    snapshot_id = _current_snapshot(driver)
    service = _service(driver)
    client = _rest_client(driver, service=service)

    # Step 1: legacy get_evidence, POST /api/evidence/resolve and GET /api/evidence.
    legacy = service.get_evidence(EvidenceRequest(evidence_refs=v2_ids, snapshot_id=snapshot_id))
    resolved = client.post(
        "/api/evidence/resolve", json={"evidence_refs": v2_ids, "snapshot_id": snapshot_id}
    )
    listed = client.get("/api/evidence", params={"snapshot_id": snapshot_id})
    lookups = [
        client.get(f"/api/evidence/{v2_id}", params={"snapshot_id": snapshot_id})
        for v2_id in v2_ids
    ]
    assert resolved.status_code == 200 and listed.status_code == 200
    # Step 2: an NL question naming the v2 ids is refused before any answer is composed.
    named = ", ".join(f"'{v2_id}'" for v2_id in v2_ids)
    provider = _NlProvider(
        f"MATCH (n:ScopedObservedCallV2) WHERE n.id IN [{named}] RETURN n.id AS id"
    )
    nl = ArchitectureQuestionService(driver=driver, database=DATABASE, provider=provider)
    with pytest.raises(CypherValidationError):
        nl.ask("which scoped records exist for " + named + "?")
    # Step 3: get_service_dependencies evidence refs.
    [dependencies, *_] = _v0_5_answers(driver, snapshot_id, service=service)

    _check(
        "P06",
        {},
        {
            # A resolve answer echoes the requested ids as missing; it must return no record.
            "every legacy read": all(r.status_code == 404 for r in lookups)
            and legacy.data is not None
            and legacy.data.records == []
            and resolved.json()["data"]["records"] == []
            and not any(v2_id in listed.text for v2_id in v2_ids)
            and provider.composed == 0,
            "get_service_dependencies evidence_refs": not any(
                v2_id in json.dumps(dependencies) for v2_id in v2_ids
            ),
        },
    )


def test_an_owner_capture_ref_resolves_only_for_its_own_caller(driver, tmp_path):
    """D11 capture authority (b), beside X27's Pod case: P9's WORKLOAD_OWNS_POD evidence belongs to
    `service:billing`'s v2 record, so `service:orders` gets NOT_FOUND for every ref of it and
    `service:billing` resolves them."""
    case = CASES["X27"]
    prebound = world.build(driver, tmp_path, case["inputs"])
    [p9] = [
        pod
        for capture in case["inputs"]["captures"]
        for pod in capture["pods"]
        if pod["name"].endswith("-p9")
    ]
    with driver.session(database=DATABASE) as session:
        refs = session.run(
            "MATCH (claim:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD'}) "
            "MATCH (pc:InfrastructureContribution {entity_id: claim.object_id, "
            "captured_resource_uid: $uid}) "
            "MATCH (cc:InfrastructureClaimContribution {claim_id: claim.id}) "
            "UNWIND cc.evidence_refs AS ref RETURN DISTINCT ref ORDER BY ref",
            uid=p9["uid"],
        ).value()
    assert refs, "P9 has owner evidence"
    snapshot_id = _current_snapshot(driver)

    def resolve(subject: str) -> list[tuple[str, str | None]]:
        answer = _ask(
            driver,
            {
                "mode": "evidence",
                "subject_service_id": subject,
                "snapshot_id": snapshot_id,
                "refs": refs,
            },
        )
        return [(entry["status"], entry["ref_kind"]) for entry in answer["data"]["entries"]]

    assert prebound["SOURCE:A"]
    assert resolve("service:orders") == [("NOT_FOUND", None)] * len(refs)
    # The claim's evidence also carries the Pod's own capture ref, which authority (a) labels
    # POD_CAPTURE; the claim's other refs are OWNER_CAPTURE.
    billing = resolve("service:billing")
    assert {status for status, _kind in billing} == {"RESOLVED"}
    assert "OWNER_CAPTURE" in {kind for _status, kind in billing}
    assert {kind for _status, kind in billing} <= {"OWNER_CAPTURE", "POD_CAPTURE"}
