"""v0.7.0 I3.2: the independent I3 oracle executed against the projection (matrix §2.5).

Every `mode: query` answer case is projected from its world's `snapshot_state`, with the snapshot of
`inputs.current_snapshot` injected as the current one, and must equal the expected answer under the
matrix §2 rules and be valid under Pydantic and the published schema. Property cases (paging, two
gateways, the credential canary) are checked over the actual answers with the same assertion code
that checks the oracle itself. Evidence-mode cases belong to I3.3; request cases are validation."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.api_usage_projection import project_api_consumer_usage
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.schema_export import API_USAGE_ANSWER_SCHEMA_PATH
from tests.api_usage_oracle.matcher import first_difference
from tests.api_usage_oracle.properties import check_property

ORACLE = (
    Path(__file__).resolve().parents[2]
    / "docs/specifications/0.7.0/i3-vectors/expected-answers.json"
)
DOC = json.loads(ORACLE.read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in DOC["cases"]}
ANSWER_SCHEMA = json.loads(API_USAGE_ANSWER_SCHEMA_PATH.read_text())
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.7.0", build_revision="test"
)

QUERY_CASES = sorted(
    case_id
    for case_id, case in CASES.items()
    if case["kind"] == "answer" and case["request"]["mode"] == "query"
)
EVIDENCE_CASES = sorted(
    case_id
    for case_id, case in CASES.items()
    if case["kind"] == "answer" and case["request"]["mode"] == "evidence"
)


@cache
def run_case(case_id: str) -> dict[str, Any]:
    case = CASES[case_id]
    world = DOC["worlds"][case["inputs"]["world"]]
    snapshot = SnapshotRef(**DOC["snapshots"][case["inputs"]["current_snapshot"]])
    answer = project_api_consumer_usage(
        ApiConsumerUsageQueryRequest.model_validate(case["request"]),
        world["snapshot_state"],
        snapshot=snapshot,
        producer=PRODUCER,
    )
    dumped = answer.model_dump(mode="json", exclude_none=True)
    # `data` and `snapshot` are required-but-nullable envelope fields: they stay on the wire as null
    return {**dumped, "data": dumped.get("data"), "snapshot": dumped.get("snapshot")}


@pytest.mark.parametrize("case_id", QUERY_CASES)
def test_the_projection_equals_the_expected_answer(case_id):
    expected = CASES[case_id]["expected"]
    assert first_difference(expected, run_case(case_id)) is None


@pytest.mark.parametrize("case_id", QUERY_CASES)
def test_every_actual_answer_is_valid_under_pydantic_and_the_published_schema(case_id):
    actual = run_case(case_id)
    ApiConsumerUsageAnswer.model_validate(actual)
    assert list(jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(actual)) == []


@pytest.mark.parametrize(
    "case_id", sorted(case_id for case_id, case in CASES.items() if case["kind"] == "property")
)
def test_property_cases_hold_over_the_actual_answers(case_id):
    case = CASES[case_id]
    executed = {
        other: {
            **CASES[other],
            "expected": run_case(other) if other in QUERY_CASES else CASES[other]["expected"],
        }
        for other in CASES
        if CASES[other]["kind"] == "answer"
    }
    for item in case["assert"]:
        check_property(
            item,
            cases=executed,
            world_text=json.dumps(DOC["worlds"]["base"]["internal_only"]),
        )


def test_the_evidence_mode_cases_are_left_to_i3_3():
    assert EVIDENCE_CASES, "the oracle's evidence cases still exist and are not silently dropped"
    assert set(EVIDENCE_CASES).isdisjoint(QUERY_CASES)
