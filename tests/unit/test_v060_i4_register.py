"""Machine check of the v0.6.0 I4.1 coverage register and bridge vectors.

`docs/specifications/0.6.0/i4-coverage-register.md` maps every parent §20 scenario to independent
anchors and an executable check. This test keeps it honest:

- all 25 §20 rows appear exactly once, and the §20 table itself still has 25 rows;
- every cited oracle ID exists in the frozen I1, I3 or I4 vectors;
- every cited `path::test` exists, found by parsing the file's AST;
- a non-`COVERED` row carries a note, and a `NEW_I4` row cites a `B` case;
- the I4 vectors are reproduced byte for byte by a stdlib-only author, and every bridge case has
  positive, unresolved-or-forbidden and snapshot assertions that are not vacuous.
"""

import ast
import importlib.util
import json
import re
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/specifications/0.6.0"
REGISTER = (SPEC / "i4-coverage-register.md").read_text(encoding="utf-8")
VECTORS = SPEC / "i4-vectors"
STATUSES = {"COVERED", "PARTIAL", "NEW_I4", "NOT_COVERED"}
_ROW = re.compile(r"^\| (S20-\d\d) \|(.*)\|$")
_CITED = re.compile(r"`([^`]+?\.py::[^`]+)`")
_ID = re.compile(r"`([LXPQB]\d\d[ab]?)`")


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
    ids: set[str] = set()
    i1 = json.loads((SPEC / "i1-vectors/conformance-expected.json").read_text(encoding="utf-8"))
    ids.update(case["id"] for case in i1["cases"])
    i3 = json.loads((SPEC / "i3-vectors/expected-answers.json").read_text(encoding="utf-8"))
    ids.update(case["id"] for case in i3["cases"])
    i4 = json.loads((VECTORS / "expected-i4.json").read_text(encoding="utf-8"))
    ids.update(case["id"] for case in i4["cases"])
    return frozenset(ids)


@cache
def _names(path: str) -> frozenset[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.update(
                f"{node.name}::{item.name}"
                for item in node.body
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
            )
    return frozenset(names)


def test_the_register_lists_every_section_20_row_exactly_once():
    assert list(ROWS) == [f"S20-{n:02d}" for n in range(1, 26)]
    parent = (SPEC / "specification.md").read_text(encoding="utf-8")
    section = parent.split("## 20. I4 Frozen Evaluation Method")[1].split("\n## 21.")[0]
    table_rows = [
        line
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("|---")
    ]
    assert len(table_rows) - 1 == 25  # minus the header row


def test_every_row_has_a_valid_status_and_the_required_note():
    for key, cells in ROWS.items():
        status, note = cells[4], cells[5]
        assert status in STATUSES, key
        if status != "COVERED":
            assert note, f"{key} is {status} without a note"
        if status == "NEW_I4":
            assert re.search(r"`B\d\d[ab]?`", cells[2] + note), f"{key} cites no B case"
        assert status != "NOT_COVERED" or note


def test_every_cited_oracle_id_exists():
    for key, cells in ROWS.items():
        cited = _ID.findall(cells[2])
        assert cited, f"{key} cites no oracle id"
        for oracle_id in cited:
            known = oracle_id in _oracle_ids() or any(
                i.startswith(oracle_id) for i in _oracle_ids()
            )
            assert known, f"{key} cites unknown {oracle_id}"


def test_every_cited_test_exists():
    for key, cells in ROWS.items():
        cited = _CITED.findall(cells[3])
        assert cited, f"{key} cites no executable check"
        for ref in cited:
            path, _, name = ref.partition("::")
            assert (ROOT / path).is_file(), f"{key}: {path} is missing"
            assert name in _names(path), f"{key}: {ref} not found"


def test_the_adapter_gates_cite_existing_cases():
    gates = REGISTER.split("## 2.")[1].split("## 3.")[0]
    cited = set(re.findall(r"`(Q\d\d)`", gates))
    assert {"Q01", "Q08"} <= cited
    assert cited <= _oracle_ids()


def test_the_committed_vectors_are_reproduced_by_their_author():
    assert (VECTORS / "expected-i4.json").read_text(encoding="utf-8") == _author().render()


def test_the_author_imports_only_the_standard_library():
    tree = ast.parse((VECTORS / "author_i4_expected.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {"__future__", "hashlib", "json", "pathlib", "typing"}


def test_the_p3_variants_differ_only_where_the_spec_says():
    cases = {c["id"]: c for c in json.loads((VECTORS / "expected-i4.json").read_text())["cases"]}
    a, b = cases["B01a"]["inputs"], cases["B01b"]["inputs"]
    assert a["workload_uids"]["C1"] == a["workload_uids"]["C2"]
    assert b["workload_uids"]["C1"] != b["workload_uids"]["C2"]
    assert a["v2"] == b["v2"]
    pods = [{p["uid"] for p in c["pods"]} for c in a["captures"]]
    p1, p3 = a["v2"]["P1"]["caller_pod_uid"], a["v2"]["P3"]["caller_pod_uid"]
    assert p1 in pods[0] and p1 not in pods[1], "C2 must lack P1"
    assert p3 in pods[1] and p3 not in pods[0], "C2 must hold a different Pod, P3"
    assert a["v2"]["P1"]["object_id"] != a["v2"]["P3"]["object_id"]


def test_every_bridge_case_is_non_vacuous():
    document = json.loads((VECTORS / "expected-i4.json").read_text(encoding="utf-8"))
    for case in document["cases"]:
        kinds = [item["kind"] for item in case["assert"]]
        assert "forbidden" in kinds, case["id"]
        assert len(case["assert"]) >= 2, case["id"]
        assert all(item["kind"] in document["assertion_kinds"] for item in case["assert"]), case[
            "id"
        ]
    for variant in ("B01a", "B01b"):
        case = next(c for c in document["cases"] if c["id"] == variant)
        kinds = {item["kind"] for item in case["assert"]}
        assert {"positive", "unresolved", "evidence_refs_resolve", "refusal"} <= kinds


def _document() -> dict:
    return json.loads((VECTORS / "expected-i4.json").read_text(encoding="utf-8"))


_PLACEHOLDER = re.compile(r"^\{\{(SNAPSHOT_ID|STEP\d_SNAPSHOT_ID|CAPTURE_REF:[^}]+)\}\}$")


def _concrete(value):
    """Replace run-bound placeholders by values of the right shape, for schema validation."""
    if isinstance(value, str):
        match = _PLACEHOLDER.match(value)
        if not match:
            return value
        if "SNAPSHOT_ID" in match.group(1):
            return "aip:snapshot:v1:" + "0" * 64
        return "evidence:zz-capture:" + match.group(1).replace("/", ":")
    if isinstance(value, dict):
        return {key: _concrete(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_concrete(item) for item in value]
    return value


def test_every_authored_request_is_valid_against_the_published_schema_and_models():
    from jsonschema import Draft202012Validator

    from app.architecture_intelligence.locality_contracts import (
        LocalityEvidenceRequest,
        LocalityQueryRequest,
    )

    schema = json.loads(
        (
            ROOT / "schemas/architecture_intelligence/v0.6/"
            "service-dependencies-by-locality-request.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    models = {"query": LocalityQueryRequest, "evidence": LocalityEvidenceRequest}
    checked = 0
    for case in _document()["cases"]:
        for step in case["steps"]:
            if "request" not in step:
                continue
            request = _concrete(step["request"])
            errors = [e.message for e in validator.iter_errors(request)]
            assert not errors, f"{case['id']} step {step['step']}: {errors}"
            models[request["mode"]].model_validate(request)
            checked += 1
    assert checked >= 8


def test_assertions_refer_only_to_declared_steps_and_workloads():
    for case in _document()["cases"]:
        steps = {step["step"] for step in case["steps"]}
        assert sorted(steps) == list(range(1, len(steps) + 1)), case["id"]
        for item in case["assert"]:
            assert item["step"] in steps, f"{case['id']}: {item}"
            if "other" in item:
                assert item["other"] in steps, f"{case['id']}: {item}"
                assert item["other"] != item["step"], f"{case['id']}: {item}"
        for step in case["steps"]:
            request = step.get("request", {})
            compared = request.get("compare", [])
            assert len({w["uid"] for w in compared}) == len(compared), case["id"]


def test_the_quarkus_bridge_uses_the_frozen_replay_context():
    check_ready = (ROOT / "examples/quarkus-super-heroes-demo/check_ready.py").read_text()
    case = next(c for c in _document()["cases"] if c["id"] == "B06")
    request = case["steps"][0]["request"]
    assert f'"{request["environment"]}"' in check_ready
    assert f'"{request["subject_service_id"]}"' in check_ready.replace("service:", '"service:', 1)
