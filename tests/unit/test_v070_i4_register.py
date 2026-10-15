"""Machine check of the v0.7.0 I4.1a coverage register and the B07 bridge vector.

`docs/specifications/0.7.0/i4-coverage-register.md` maps each of the twelve parent §22 requirements
to independent anchors and an executable check, and counts positive against abstaining outcomes per
scenario class. This test keeps it honest:

- all twelve §22 items appear exactly once, and the parent §22 list still has twelve items;
- every cited oracle id exists in the frozen I3, I2 or I4 vectors;
- every cited `path::test` exists, found by parsing the file's AST;
- a non-`COVERED` row carries a note, a `NEW_I4` row cites a `B` case, a `DOSSIER_ONLY` row cites
  no executable check;
- every scenario class has a positive and an abstaining case;
- the I4 vectors are reproduced byte for byte by a stdlib-only author, the bridge world is the exact
  handoff state (its derived sections equal the I2 rules applied to its raw facts), its refs and
  digests equal the models' own derivations, and its expected answers are valid and not vacuous.

It deliberately does not project the bridge vector: the first execution is the I4.2 runner on the
candidate, so the expectation is frozen before the candidate has seen it."""

import ast
import copy
import importlib.util
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    evidence_ref,
    query_context_digest,
)
from app.architecture_intelligence.schema_export import API_USAGE_ANSWER_SCHEMA_PATH
from evaluation.i4.__main__ import REQUIRED_CI_CHECKS
from tests.api_usage_oracle import state_checks

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/specifications/0.7.0"
VECTORS = SPEC / "i4-vectors"
REGISTER = (SPEC / "i4-coverage-register.md").read_text(encoding="utf-8")
DECISIONS = (SPEC / "i4-decision-record.md").read_text(encoding="utf-8")
DOC = json.loads((VECTORS / "expected-i4.json").read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in DOC["cases"]}
STATE = DOC["worlds"]["bridge"]["snapshot_state"]
STATUSES = {"COVERED", "PARTIAL", "NEW_I4", "DOSSIER_ONLY", "NOT_COVERED"}
_ROW = re.compile(r"^\| (S22-\d\d) \|(.*)\|$")
_CITED = re.compile(r"`(tests/[^`]+?\.py::[^`]+)`")
_ID = re.compile(r"`([AEVBK]\d\d[a-c]?)`")


def _rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in REGISTER.splitlines():
        match = _ROW.match(line)
        if match:
            key, rest = match.groups()
            assert key not in rows, f"{key} appears twice"
            rows[key] = [cell.strip() for cell in rest.split("|")]
    return rows


ROWS = _rows()


def _author():
    spec = importlib.util.spec_from_file_location("author_i4", VECTORS / "author_i4_expected.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@cache
def _oracle_ids() -> frozenset[str]:
    ids = {case["id"] for case in DOC["cases"]}
    i3 = json.loads((SPEC / "i3-vectors/expected-answers.json").read_text(encoding="utf-8"))
    ids.update(case["id"] for case in i3["cases"])
    i2 = json.loads((SPEC / "i2-vectors/reconciliation.json").read_text(encoding="utf-8"))
    ids.update(case["id"] for case in i2["cases"])
    return frozenset(ids)


@cache
def _names(path: str) -> frozenset[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    return frozenset(
        node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    )


# --- The register -------------------------------------------------------------------------------


def test_the_register_lists_every_parent_section_22_item_exactly_once():
    assert list(ROWS) == [f"S22-{n:02d}" for n in range(1, 13)]
    parent = (SPEC / "specification.md").read_text(encoding="utf-8")
    section = parent.split("## 22. Deterministic Semantic Qualification")[1].split("\n## 23.")[0]
    assert len(re.findall(r"^\d+\. ", section, flags=re.MULTILINE)) == 12


def test_every_row_has_a_valid_status_and_the_required_note():
    for key, cells in ROWS.items():
        anchors, check, status, note = cells[1], cells[2], cells[3], cells[4]
        assert status in STATUSES, key
        assert status != "NOT_COVERED", f"{key}: a documented blocker at freeze"
        if status != "COVERED":
            assert note, f"{key} is {status} without a note"
        if status == "NEW_I4":
            assert re.search(r"`B\d\d[abc]?`", anchors), f"{key} cites no B case"
        if status == "DOSSIER_ONLY":
            assert not _CITED.findall(check) and "Tyk" in anchors + note, key
        else:
            assert _CITED.findall(check), f"{key} cites no executable check"


def test_every_cited_oracle_id_exists():
    for key, cells in ROWS.items():
        for oracle_id in _ID.findall(cells[1]):
            assert oracle_id in _oracle_ids(), f"{key} cites unknown {oracle_id}"


def test_every_cited_test_exists():
    for key, cells in ROWS.items():
        for ref in _CITED.findall(cells[2]):
            path, _, name = ref.partition("::")
            assert (ROOT / path).is_file(), f"{key}: {path} is missing"
            assert name in _names(path), f"{key}: {ref} not found"


def test_every_method_gate_cites_existing_checks_and_cases():
    gates = REGISTER.split("## 3. Method gates")[1].split("## 4.")[0]
    assert [g for g in re.findall(r"^\| (G-\d\d) \|", gates, flags=re.MULTILINE)] == [
        f"G-0{n}" for n in range(1, 7)
    ]
    assert {"V01", "V22"} <= set(_ID.findall(gates))
    for ref in _CITED.findall(gates):
        path, _, name = ref.partition("::")
        assert name in _names(path), ref
    for oracle_id in _ID.findall(gates):
        assert oracle_id in _oracle_ids(), oracle_id


def test_every_scenario_class_has_a_positive_and_an_abstaining_case():
    table = REGISTER.split("## 2. Positive and abstaining outcomes")[1].split("## 3.")[0]
    classes = [
        [cell.strip() for cell in line.strip("|").split("|")]
        for line in table.splitlines()
        if line.startswith("| ") and not line.startswith("| Class") and not line.startswith("|---")
    ]
    assert len(classes) == 7
    for name, _, positive, abstaining in classes:
        for column in (positive, abstaining):
            ids = _ID.findall(column)
            assert ids, f"{name} has an empty column"
            assert all(i in _oracle_ids() for i in ids), name
        assert not set(_ID.findall(positive)) & set(_ID.findall(abstaining)), name


def test_the_decision_record_names_exactly_the_required_ci_checks():
    row = next(line for line in DECISIONS.splitlines() if line.startswith("| Required CI checks"))
    named = set(re.findall(r"`([^`]+)`", row)) - {
        "CodeQL",
        "skipped",
        "completed/success",
        "gh pr checks",
    }
    assert named == set(REQUIRED_CI_CHECKS)


def test_the_decision_record_freezes_the_f1_deferral():
    assert "## D2 — F1: page before enrich is deferred past the candidate" in DECISIONS


# --- The vectors --------------------------------------------------------------------------------


def test_the_committed_vectors_are_reproduced_by_their_author():
    assert (VECTORS / "expected-i4.json").read_text(encoding="utf-8") == _author().render()


def test_the_author_imports_only_the_standard_library():
    tree = ast.parse((VECTORS / "author_i4_expected.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert roots <= {"__future__", "copy", "hashlib", "importlib", "json", "pathlib", "typing"}
    assert "app" not in roots


def test_the_bridge_world_is_the_exact_handoff_state():
    assert state_checks.shape_problems(STATE) == []
    assert state_checks.raw_row_problems(STATE) == []


def test_the_bridge_world_equals_the_i2_rules_applied_to_its_raw_facts():
    assert state_checks.reconciliation_problems(STATE) == []
    assert state_checks.qualification_problems(STATE) == []


def test_the_bridge_world_really_is_the_k08_shape():
    """Two Operations of two contracts expose the Route's exact path and method, with no explicit
    mapping, and the rule says `AMBIGUOUS`: the world cannot pass by accident of construction."""
    route = next(
        r for r in STATE["gateway_configuration_v1"]["routes"] if r["route_id"] == "invoices-route"
    )
    candidates = [
        o for o in STATE["operations"] if o["path"] == route["uri"] and o["method"] == "GET"
    ]
    assert len(candidates) == 2 and STATE["api_usage_v1"]["mapping_entries"] == []
    rows = {r["route_id"]: r for r in STATE["api_usage_v1"]["route_operation"]}
    assert rows[route["id"]] == {
        "window_id": STATE["api_usage_v1"]["windows"][0]["id"],
        "route_id": route["id"],
        "operation": "AMBIGUOUS",
    }


def test_the_refs_and_digests_equal_the_models_own_derivations():
    window = STATE["api_usage_v1"]["windows"][0]
    snapshot_id = DOC["snapshots"]["A"]["snapshot_id"]
    for case_id in ("B07a", "B07b"):
        request = CASES[case_id]["request"]
        digest = query_context_digest(
            target_kind=request["target"]["kind"],
            target_id=request["target"]["id"],
            gateway_instance_id=request["gateway_instance_id"],
            environment=request["environment"],
            window_start=request["window_start"],
            window_end=request["window_end"],
            consumer_id=request.get("consumer_id"),
        )
        expected = evidence_ref(
            snapshot_id=snapshot_id,
            query_digest=digest,
            kind="MEASUREMENT_WINDOW",
            internal_ids=[window["id"], window["evidence_ids"][0]],
        )
        assert CASES[case_id]["expected"]["data"]["window"]["evidence_refs"] == [expected]
    route = next(
        r for r in STATE["gateway_configuration_v1"]["routes"] if r["route_id"] == "invoices-route"
    )
    c_request = CASES["B07c"]["request"]
    digest = query_context_digest(
        target_kind=c_request["target"]["kind"],
        target_id=c_request["target"]["id"],
        gateway_instance_id=c_request["gateway_instance_id"],
        environment=c_request["environment"],
        window_start=c_request["window_start"],
        window_end=c_request["window_end"],
        consumer_id=None,
    )
    kinds = {
        "ROUTE_OPERATION_RECONCILIATION": evidence_ref(
            snapshot_id=snapshot_id,
            query_digest=digest,
            kind="ROUTE_OPERATION_RECONCILIATION",
            internal_ids=[route["id"]],
        ),
        "TARGET_SERVICE_RECONCILIATION": evidence_ref(
            snapshot_id=snapshot_id,
            query_digest=digest,
            kind="TARGET_SERVICE_RECONCILIATION",
            internal_ids=[route["id"]],
        ),
    }
    entries = {e["kind"]: e["ref"] for e in CASES["B07c"]["expected"]["data"]["entries"]}
    assert entries == kinds


def _instantiate(value: Any) -> Any:
    if isinstance(value, str):
        return "x" if value == "{{*}}" else value
    if isinstance(value, dict):
        return {k: _instantiate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_instantiate(v) for v in value]
    return value


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_expected_answer_is_valid_under_pydantic_and_the_published_schema(case_id):
    answer = _instantiate(copy.deepcopy(CASES[case_id]["expected"]))
    ApiConsumerUsageAnswer.model_validate(answer)
    schema = json.loads(API_USAGE_ANSWER_SCHEMA_PATH.read_text())
    assert list(jsonschema.Draft202012Validator(schema).iter_errors(answer)) == []
    assert answer["mode"] == CASES[case_id]["request"]["mode"]


def test_the_assertions_are_not_vacuous():
    a = CASES["B07a"]["expected"]
    rows = a["data"]["rows"]
    assert len(rows) == 2 and a["outcome"] == "ANSWERED" and a["limitations"] == []
    for row in rows:
        assert row["api"] == {"reconciliation": "AMBIGUOUS"}, "no operation_id, no contract chain"
        assert row["application_service"]["reconciliation"] == "RESOLVED"
        assert row["application_service"]["service_id"] == "service:billing"
    assert "association_summary" not in a["data"]

    b = CASES["B07b"]["expected"]
    summary = b["data"]["association_summary"]["route_operation"]
    assert summary["ambiguous"] == 1 and summary["resolved_to_target"] == 0
    assert sum(summary.values()) == 2, "the summary counts every Route of the scope"
    assert b["data"]["selected_routes"] == [] and b["data"]["rows"] == []
    assert b["outcome"] == "NOT_ANSWERED" and [x["code"] for x in b["limitations"]] == [
        "NO_ROUTE_SELECTED"
    ]
    assert b["data"] is not None, "an evaluated negative carries its data"

    c = CASES["B07c"]["expected"]
    by_kind = {e["kind"]: e["evidence"] for e in c["data"]["entries"]}
    operation = by_kind["ROUTE_OPERATION_RECONCILIATION"]
    assert operation["outcome"] == "AMBIGUOUS" and operation["mapping_entries"] == []
    assert "operation_id" not in operation and "basis" not in operation
    assert {e["status"] for e in c["data"]["entries"]} == {"RESOLVED"}
    assert c["outcome"] == "ANSWERED"


def test_the_frozen_classes_cover_every_case_and_match_the_register_tables():
    """The comparator holds each ledger record to this label (decision record D3), so the register's
    positive and abstaining columns must say the same thing as the hand-authored classes."""
    classes = DOC["classifications"]
    required = {
        case["id"]
        for case in json.loads((SPEC / "i3-vectors/expected-answers.json").read_text())["cases"]
    }
    required |= set(CASES)
    assert required <= set(classes)
    assert set(classes.values()) == {"I4_CORRECT", "I4_EXPECTED_NEGATIVE"}
    table = REGISTER.split("## 2. Positive and abstaining outcomes")[1].split("## 3.")[0]
    for line in table.splitlines():
        if line.startswith("| ") and not line.startswith("| Class") and not line.startswith("|---"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            for case in _ID.findall(cells[2]):
                assert classes[case] == "I4_CORRECT", (cells[0], case)
            for case in _ID.findall(cells[3]):
                assert classes[case] == "I4_EXPECTED_NEGATIVE", (cells[0], case)


def test_every_abstaining_class_member_really_abstains_or_is_rejected():
    """A cross-check of the hand-authored labels against the frozen answers, so a typo in the lists
    cannot silently move a case: a positive answer case is ANSWERED or a paging PARTIAL, an
    abstaining one is not an unqualified success."""
    answers = {
        c["id"]: c
        for c in json.loads((SPEC / "i3-vectors/expected-answers.json").read_text())["cases"]
    }
    answers |= CASES
    for case, label in DOC["classifications"].items():
        expected = answers.get(case, {}).get("expected")
        if label == "I4_EXPECTED_NEGATIVE" and expected and case[0] in "AEB":
            data = expected.get("data")
            assert (
                expected["outcome"] != "ANSWERED"
                or expected["limitations"]
                or (
                    data
                    and any(
                        r["usage"]["status"] == "USAGE_UNESTABLISHED"
                        or r["api"]["reconciliation"] != "RESOLVED"
                        or r["application_service"]["reconciliation"] != "RESOLVED"
                        for r in data.get("rows", [])
                    )
                )
            ), case
