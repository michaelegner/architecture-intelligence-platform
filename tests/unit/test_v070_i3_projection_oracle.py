"""v0.7.0 I3.2/I3.3: the independent I3 oracle executed against the projection (matrix §2.5).

Every answer case, `mode: query` (I3.2) and `mode: evidence` (I3.3), is projected from its world's
`snapshot_state`, with the snapshot of `inputs.current_snapshot` injected as the current one, and
must equal the expected answer under the matrix §2 rules and be valid under Pydantic and the
published schema. Property cases (paging, two gateways, the credential canary) are checked over the
actual answers with the same assertion code that checks the oracle itself. Request cases are
validation and are checked by `test_v070_i3_expected_answers.py`."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.api_usage_evidence import resolve_api_consumer_usage_evidence
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

ANSWER_CASES = sorted(case_id for case_id, case in CASES.items() if case["kind"] == "answer")


@cache
def run_case(case_id: str) -> dict[str, Any]:
    case = CASES[case_id]
    world = DOC["worlds"][case["inputs"]["world"]]
    snapshot = SnapshotRef(**DOC["snapshots"][case["inputs"]["current_snapshot"]])
    if case["request"]["mode"] == "query":
        answer = project_api_consumer_usage(
            ApiConsumerUsageQueryRequest.model_validate(case["request"]),
            world["snapshot_state"],
            snapshot=snapshot,
            producer=PRODUCER,
        )
    else:
        answer = resolve_api_consumer_usage_evidence(
            ApiConsumerUsageEvidenceRequest.model_validate(case["request"]),
            world["snapshot_state"],
            snapshot=snapshot,
            producer=PRODUCER,
        )
    return answer.model_dump(mode="json")


@pytest.mark.parametrize("case_id", ANSWER_CASES)
def test_the_projection_equals_the_expected_answer(case_id):
    expected = CASES[case_id]["expected"]
    assert first_difference(expected, run_case(case_id)) is None


@pytest.mark.parametrize("case_id", ANSWER_CASES)
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
            "expected": run_case(other),
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
