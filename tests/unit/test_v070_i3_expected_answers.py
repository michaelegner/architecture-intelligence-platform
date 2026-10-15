"""v0.7.0 I3.1c: the independently authored expected answers (decision record D11, I3 §12).

These tests check the oracle itself, not an implementation: it is reproducible from its stdlib-only
author, it never imports `app`, every answer is a valid 0.7 answer under both Pydantic and the
published schema once its `{{*}}` wildcards are instantiated (matrix §2), every request-level case is
rejected by both, the author's independent derivations agree with the frozen vectors and with the
models' own helpers, and the matrix covers every I3 §12 row.
"""

import ast
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence import api_usage_contracts as contracts
from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageRequest,
)
from app.architecture_intelligence.schema_export import (
    API_USAGE_ANSWER_SCHEMA_PATH,
    API_USAGE_REQUEST_SCHEMA_PATH,
)
from tests.api_usage_oracle import state_checks
from tests.api_usage_oracle.properties import check_property

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specifications" / "0.7.0"
AUTHOR = SPEC_DIR / "i3-vectors" / "author_expected_answers.py"
ORACLE = SPEC_DIR / "i3-vectors" / "expected-answers.json"
MATRIX = SPEC_DIR / "i3-expected-answer-matrix.md"
I1_IDS = SPEC_DIR / "i1-vectors" / "ids.json"
I2_IDS = SPEC_DIR / "i2-vectors" / "ids.json"

DOC = json.loads(ORACLE.read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in DOC["cases"]}
ANSWER_SCHEMA = json.loads(API_USAGE_ANSWER_SCHEMA_PATH.read_text())
REQUEST_SCHEMA = json.loads(API_USAGE_REQUEST_SCHEMA_PATH.read_text())

WILDCARD = "{{*}}"


def _author_module():
    spec = importlib.util.spec_from_file_location("i3_v070_author_expected_answers", AUTHOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def instantiate(value: Any) -> Any:
    """Matrix §2.2: the only placeholder is the wildcard, replaced by a valid non-empty string."""
    if isinstance(value, str):
        return "x" if value == WILDCARD else value
    if isinstance(value, dict):
        return {key: instantiate(item) for key, item in value.items()}
    if isinstance(value, list):
        return [instantiate(item) for item in value]
    return value


def _schema_errors(instance: Any, schema: dict) -> list[str]:
    return [
        error.message for error in jsonschema.Draft202012Validator(schema).iter_errors(instance)
    ]


def _cases(kind: str) -> list[str]:
    return sorted(case_id for case_id, case in CASES.items() if case["kind"] == kind)


# --- Reproducibility and independence -----------------------------------------------------------


def test_the_committed_oracle_is_reproduced_by_its_author():
    assert ORACLE.read_text(encoding="utf-8") == _author_module().render(), (
        "expected-answers.json is out of date - rerun "
        "`python docs/specifications/0.7.0/i3-vectors/author_expected_answers.py`"
    )


def test_the_author_imports_only_the_standard_library():
    """I3 §12: the oracle must not be derived from the code it qualifies."""
    tree = ast.parse(AUTHOR.read_text(encoding="utf-8"))
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imported <= {"__future__", "base64", "copy", "hashlib", "json", "pathlib", "typing"}


def test_case_ids_are_unique_and_kinds_are_known():
    ids = [case["id"] for case in DOC["cases"]]
    assert len(ids) == len(set(ids))
    assert {case["kind"] for case in DOC["cases"]} == {"answer", "property", "request"}


def test_the_authors_identifier_formulas_reproduce_the_frozen_vectors():
    """The author re-derives ids from the frozen rules; the I1 and I2 vector files are the proof."""
    author = _author_module()
    i2 = {v["id"]: v for v in json.loads(I2_IDS.read_text())["vectors"]}
    m01 = i2["M01"]["inputs"]
    assert (
        author.measurement_source_id(
            m01["source_id"], m01["gateway_instance_id"], m01["environment"]
        )
        == i2["M01"]["expected"]
    )
    m04 = i2["M04"]["inputs"]
    parts = [
        m04[key]
        for key in (
            "gateway_instance_id",
            "environment",
            "window_start",
            "window_end",
            "start_sha256",
            "end_sha256",
        )
    ]
    assert "measurement-window:owned:" + author.sha(*parts) == i2["M04"]["expected"]
    assert "evidence:apisix-measurement:" + author.sha(*parts) == i2["M05"]["expected"]
    m06 = i2["M06"]["inputs"]
    assert (
        author.interaction_id(
            m06["consumer_id"],
            m06["route_id"],
            m06["environment"],
            m06["window_start"],
            m06["window_end"],
        )
        == i2["M06"]["expected"]
    )
    i1 = {v["id"]: v for v in json.loads(I1_IDS.read_text())["vectors"]}
    v01 = i1["V01"]["inputs"]
    assert author.consumer_id(v01["gateway_instance_id"], v01["username"]) == i1["V01"]["expected"]
    v03 = i1["V03"]["inputs"]
    assert author.route_id(v03["gateway_instance_id"], v03["route_id"]) == i1["V03"]["expected"]


def test_the_authors_derivations_agree_with_the_models_helpers():
    """The author is stdlib-only; the models' frozen D8/D9 derivations must produce the same values.
    A drift on either side fails here."""
    author = _author_module()
    snapshot = author.SNAPSHOTS["A"]["snapshot_id"]
    for ids in (["a"], ["b", "a", "a"], ["gateway-route:owned:" + "1" * 64, "x", "y"]):
        for kind in (
            "CONFIGURED_ACCESS",
            "MEASUREMENT_WINDOW",
            "ROUTE_OPERATION_RECONCILIATION",
            "TARGET_SERVICE_RECONCILIATION",
            "QUALIFICATION_LIMITATIONS",
        ):
            assert author.evidence_ref(snapshot, "d" * 64, kind, ids) == contracts.evidence_ref(
                snapshot_id=snapshot, query_digest="d" * 64, kind=kind, internal_ids=ids
            )
    for consumer in (None, "gateway-consumer:owned:" + "2" * 64):
        context = {
            "target": {"kind": "API_OPERATION", "id": author.OP_ORDERS},
            "gateway_instance_id": "gw-prod-1",
            "environment": "prod",
            "window_start": author.WS,
            "window_end": author.WE,
            "consumer_id": consumer,
        }
        assert author.query_digest(context) == contracts.query_context_digest(
            target_kind="API_OPERATION",
            target_id=author.OP_ORDERS,
            gateway_instance_id="gw-prod-1",
            environment="prod",
            window_start=author.WS,
            window_end=author.WE,
            consumer_id=consumer,
        )
    cursor = contracts.ApiUsageCursor(
        v=1,
        after=("gateway-consumer:owned:" + "3" * 64, "gateway-route:owned:" + "4" * 64),
        query_digest="5" * 64,
        schema_version="0.7",
        snapshot_id=snapshot,
    )
    assert author.encode_cursor(
        after=cursor.after, digest=cursor.query_digest, snapshot_id=cursor.snapshot_id
    ) == contracts.encode_cursor(cursor)


# --- Answers ------------------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_expected_answer_is_a_valid_07_answer(case_id):
    answer = instantiate(copy.deepcopy(CASES[case_id]["expected"]))
    ApiConsumerUsageAnswer.model_validate(answer)
    assert _schema_errors(answer, ANSWER_SCHEMA) == []


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_case_request_is_a_valid_request(case_id):
    request = instantiate(copy.deepcopy(CASES[case_id]["request"]))
    ApiConsumerUsageRequest.model_validate(request)
    assert _schema_errors(request, REQUEST_SCHEMA) == []


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_echoes_its_request_mode_and_context(case_id):
    case = CASES[case_id]
    expected, request = case["expected"], case["request"]
    assert expected["mode"] == request["mode"]
    if expected["data"] is not None:
        context = expected["data"]["request_context"]
        for key in ("gateway_instance_id", "environment", "window_start", "window_end"):
            assert context[key] == request[key]
        assert context["target"] == request["target"]
        assert context.get("consumer_id") == request.get("consumer_id")


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_is_bound_to_the_current_snapshot(case_id):
    case = CASES[case_id]
    current = DOC["snapshots"][case["inputs"]["current_snapshot"]]
    assert case["expected"]["snapshot"] == current
    request_snapshot = case["request"].get("snapshot_id")
    if request_snapshot is not None and request_snapshot != current["snapshot_id"]:
        assert case["expected"]["data"] is None
        assert [item["code"] for item in case["expected"]["limitations"]] == [
            "SNAPSHOT_NOT_AVAILABLE"
        ]


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_case_names_a_defined_world(case_id):
    assert CASES[case_id]["inputs"]["world"] in DOC["worlds"]


def test_every_issued_cursor_is_bound_to_its_snapshot_and_context():
    issued = [
        case["expected"]["data"]["page"]["next_cursor"]
        for case in CASES.values()
        if case["kind"] == "answer"
        and case["expected"]["data"] is not None
        and "page" in case["expected"]["data"]
        and "next_cursor" in case["expected"]["data"]["page"]
    ]
    assert issued, "non-vacuous: at least one page issues a cursor"
    for value in issued:
        assert contracts.decode_cursor(value).schema_version == "0.7"


def test_evidence_answers_return_exactly_the_requested_refs():
    evidence = [
        case
        for case in CASES.values()
        if case["kind"] == "answer" and case["request"]["mode"] == "evidence"
    ]
    assert evidence
    for case in evidence:
        if case["expected"]["data"] is None:
            continue
        refs = [entry["ref"] for entry in case["expected"]["data"]["entries"]]
        assert refs == case["request"]["evidence_refs"]


def test_the_evidence_cases_cover_every_kind_and_a_not_resolved_entry():
    kinds, statuses = set(), set()
    for case in CASES.values():
        data = case["expected"].get("data") if case["kind"] == "answer" else None
        for entry in (data or {}).get("entries", []):
            statuses.add(entry["status"])
            if entry["status"] == "RESOLVED":
                kinds.add(entry["kind"])
    assert kinds == {kind.value for kind in contracts.EvidenceKind}
    assert statuses == {"RESOLVED", "NOT_RESOLVED"}


def test_the_refusal_cases_cover_every_refusal_code():
    seen = set()
    for case in CASES.values():
        if case["kind"] == "answer" and case["expected"]["data"] is None:
            seen.add((case["expected"]["mode"], case["expected"]["limitations"][0]["code"]))
    assert {code for mode, code in seen if mode == "query"} == {
        code.value for code in contracts.REFUSAL_CODES_QUERY
    }
    assert {code for mode, code in seen if mode == "evidence"} >= {"SNAPSHOT_NOT_AVAILABLE"}


# --- Requests -----------------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _cases("request"))
def test_every_request_case_is_rejected_by_both_validators(case_id):
    case = CASES[case_id]
    assert case["expected"] == {"validation_error": True}
    request = instantiate(copy.deepcopy(case["request"]))
    with pytest.raises(ValidationError):
        ApiConsumerUsageRequest.model_validate(request)
    if "pydantic_only" in case:
        assert case["pydantic_only"]
        assert _schema_errors(request, REQUEST_SCHEMA) == []
    else:
        assert _schema_errors(request, REQUEST_SCHEMA) != []


# --- Properties ---------------------------------------------------------------------------------


def _check(item: dict, case: dict) -> None:
    check_property(item, cases=CASES, world_text=json.dumps(DOC["worlds"]["base"]["internal_only"]))


@pytest.mark.parametrize("case_id", _cases("property"))
def test_every_property_case_holds_and_is_not_vacuous(case_id):
    case = CASES[case_id]
    assert case["steps"] and case["assert"]
    for step in case["steps"]:
        assert step == "ALL" or step in CASES
    for item in case["assert"]:
        assert item["description"]
        _check(item, case)


def test_the_canary_is_in_the_world_but_in_no_expected_payload():
    canary = DOC["worlds"]["base"]["internal_only"]["credential_canary"]
    for case in DOC["cases"]:
        if case["kind"] == "answer":
            assert canary not in json.dumps(case["expected"]), case["id"]
            assert canary not in json.dumps(case["request"]), case["id"]
    assert canary in json.dumps(DOC["worlds"]["base"]["internal_only"])
    # credentials never reach the graph, so the snapshot state has none
    for world in DOC["worlds"].values():
        assert canary not in json.dumps(world["snapshot_state"])


def test_no_expected_payload_carries_a_credential_like_key():
    forbidden = {"key", "token", "secret", "password", "credential", "plugins", "labels_raw"}

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {k for item in value.values() for k in keys(item)}
        if isinstance(value, list):
            return {k for item in value for k in keys(item)}
        return set()

    for case in DOC["cases"]:
        if case["kind"] == "answer":
            assert not (keys(case["expected"]) & forbidden), case["id"]


# --- Worlds are the frozen I2 -> I3 handoff state ------------------------------------------------

WORLDS = DOC["worlds"]


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_a_world_is_the_handoff_snapshot_state_and_nothing_else(name):
    world = WORLDS[name]
    assert set(world) == {"snapshot_state", "internal_only"}
    assert state_checks.shape_problems(world["snapshot_state"]) == []


@pytest.mark.parametrize("name", sorted(WORLDS))
def test_raw_rows_use_only_the_snapshot_columns_and_are_sorted_by_id(name):
    assert state_checks.raw_row_problems(WORLDS[name]["snapshot_state"]) == []


@pytest.mark.parametrize(
    "name", sorted(w for w in WORLDS if "api_usage_v1" in WORLDS[w]["snapshot_state"])
)
def test_the_reconciliation_sections_equal_the_i2_rule_applied_to_the_raw_facts(name):
    assert state_checks.reconciliation_problems(WORLDS[name]["snapshot_state"]) == []


@pytest.mark.parametrize(
    "name", sorted(w for w in WORLDS if "api_usage_v1" in WORLDS[w]["snapshot_state"])
)
def test_the_qualification_sections_equal_the_i2_rule_applied_to_the_raw_facts(name):
    assert state_checks.qualification_problems(WORLDS[name]["snapshot_state"]) == []


# --- Matrix -------------------------------------------------------------------------------------

_ROW = re.compile(r"^\| (S\d\d) \| (.+?) \| (.+?) \| (COVERED|PROPERTY|DEFERRED) \| (.*) \|$")
_SECTION_12_ROWS = 20
_CASE_ID = re.compile(r"\b(?:A\d\d[a-z]?|E\d\d[a-z]|C\d\d|V\d\d)\b")


def _matrix_rows() -> list[tuple[str, str, list[str], str, str]]:
    rows = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            row, requirement, cases, status, note = match.groups()
            rows.append((row, requirement, _CASE_ID.findall(cases), status, note))
    return rows


def test_the_matrix_lists_every_section_12_row_once():
    rows = [row for row, *_ in _matrix_rows()]
    assert rows == [f"S{n:02d}" for n in range(1, _SECTION_12_ROWS + 1)]


def test_every_matrix_case_exists_and_every_case_is_cited():
    text = MATRIX.read_text(encoding="utf-8")
    cited = {case for _row, _req, cases, _status, _note in _matrix_rows() for case in cases}
    assert cited <= set(CASES)
    assert set(CASES) <= set(_CASE_ID.findall(text))


def test_covered_rows_cite_cases_and_deferred_rows_cite_an_owner():
    for row, _req, cases, status, note in _matrix_rows():
        if status in ("COVERED", "PROPERTY"):
            assert cases, row
        else:
            assert re.search(r"I3\.[234]|I4|§\d+", note), row
