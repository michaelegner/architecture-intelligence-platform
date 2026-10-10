"""v0.6.0 I3.2b: the locality query answer on real Neo4j, from the replayed capture REHEARSAL
(REHEARSAL - NOT I5; I3 spec §1, §14 rows "Two actual caller Workloads", "Pod churn" and "No v2").

The expectations are hand-written from the I3 spec's minimum demonstrable result and the
rehearsal's own pre-committed `expected.md` (W1 -> O1 `CONFIRMED`, W2 -> O2 `OBSERVED_ONLY`, P1
`UNRESOLVED` after C2). The full independent oracle runs in I3.2c.
"""

import json

import pytest

from app.architecture_intelligence.contracts import Outcome
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    LocalityQueryRequest,
    ServiceDependenciesByLocalityData,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.revision_fence import read_revision
from tests.integration.test_locality_rehearsal_replay import (
    DATABASE,
    ENVIRONMENT,
    IDS,
    O1,
    O2,
    PRODUCER,
    _replay_and_remember,
    pytestmark,  # noqa: F401 - skip with the fixture, as the I2 replay does
)


@pytest.fixture(scope="module")
def rehearsal(driver):
    """Puts the graph in a replayed state, replaying only when this module last loaded another one:
    every test here only reads the graph after its replay (the first asserts it)."""
    loaded = []

    def load(capture: str, *, scoped: bool = True) -> None:
        if loaded != [(capture, scoped)]:
            _replay_and_remember(driver, capture, scoped=scoped)
            loaded[:] = [(capture, scoped)]

    return load


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _query(**overrides) -> LocalityQueryRequest:
    return LocalityQueryRequest.model_validate(
        {
            "mode": "query",
            "subject_service_id": "service:orders",
            "environment": ENVIRONMENT,
            "first_day": IDS["DAY"],
            "last_day": IDS["DAY"],
            **overrides,
        }
    )


def _data(answer: LocalityAnswer) -> ServiceDependenciesByLocalityData:
    assert isinstance(answer.data, ServiceDependenciesByLocalityData)
    return answer.data


def _graph_state(driver) -> tuple[int, int, int]:
    with driver.session(database=DATABASE) as session:
        nodes = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        relations = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        return read_revision(session), nodes, relations


def test_c1_answers_where_the_two_workloads_call_without_writing(driver, rehearsal):
    rehearsal("c1")
    before = _graph_state(driver)

    answer = _service(driver).get_service_dependencies_by_locality(_query())
    again = _service(driver).get_service_dependencies_by_locality(_query())

    assert _graph_state(driver) == before
    assert answer.model_dump_json() == again.model_dump_json()
    assert (answer.outcome, answer.limitations) == (Outcome.ANSWERED, [])
    data = _data(answer)
    by_name = {locality.workload.name: locality for locality in data.localities}
    assert sorted(by_name) == ["orders", "orders-canary"]
    # Two incarnations of the recorded cluster, told apart by their captured UIDs.
    assert len({locality.workload.uid for locality in data.localities}) == 2
    assert {locality.workload.cluster_uid for locality in data.localities} == {IDS["CLUSTER_UID"]}
    orders, canary = by_name["orders"], by_name["orders-canary"]
    assert [(a.object_operation_id, a.qualification.value) for a in orders.assessments] == [
        (O1, "CONFIRMED")
    ]
    assert [(a.object_operation_id, a.qualification.value) for a in canary.assessments] == [
        (O2, "OBSERVED_ONLY")
    ]
    assert [(g.provider_service_id, g.operation_ids) for g in orders.provider_groups] == [
        ("service:pricing", [O1])
    ]
    assert [(g.provider_service_id, g.operation_ids) for g in canary.provider_groups] == [
        ("service:legacy-pricing", [O2])
    ]
    assert all(locality.target_runtime_scope == "UNKNOWN" for locality in data.localities)
    inventory = data.inventory
    assert (inventory.evaluated_v2_candidate_count, inventory.admitted_pair_count) == (2, 2)
    assert inventory.considered_capture_source_count == 1
    assert inventory.completeness.value == "COMPLETE" and inventory.next_cursor is None
    assert [candidate.disposition.value for candidate in data.candidates] == ["APPLICABLE"] * 2
    LocalityAnswer.model_validate(json.loads(answer.model_dump_json()))


def test_after_c2_p1_s_record_is_unresolved_and_the_c1_snapshot_is_refused(driver, rehearsal):
    rehearsal("c1")
    c1 = _service(driver).get_service_dependencies_by_locality(_query())
    assert c1.snapshot is not None

    rehearsal("c2")
    answer = _service(driver).get_service_dependencies_by_locality(_query())
    data = _data(answer)

    assert [locality.workload.name for locality in data.localities] == ["orders-canary"]
    unresolved = [c for c in data.candidates if c.disposition.value == "UNRESOLVED"]
    assert [c.reasons for c in unresolved] == [["LOCALITY_CAPTURE_MISSING_POD"]]
    assert answer.outcome is Outcome.ANSWERED
    assert answer.snapshot is not None and answer.snapshot != c1.snapshot

    stale = _service(driver).get_service_dependencies_by_locality(
        _query(snapshot_id=c1.snapshot.snapshot_id)
    )
    assert (stale.outcome, [item.code.value for item in stale.limitations]) == (
        Outcome.NOT_ANSWERED,
        ["SNAPSHOT_NOT_AVAILABLE"],
    )
    assert stale.data is None and stale.snapshot == answer.snapshot


def test_without_v2_the_answer_is_insufficient_evidence_not_absence(driver, rehearsal):
    rehearsal("c1", scoped=False)

    answer = _service(driver).get_service_dependencies_by_locality(_query())

    assert (answer.outcome, [item.code.value for item in answer.limitations]) == (
        Outcome.NOT_ANSWERED,
        ["INSUFFICIENT_EVIDENCE"],
    )
    data = _data(answer)
    assert data.candidates == [] and data.localities == []
    assert data.inventory.completeness.value == "COMPLETE"
