"""v0.6.0 I3.1c: the independently authored expected answers (decision record D15, I3 §14).

These tests check the oracle itself, not an implementation: it is reproducible from its stdlib-only
author, it never imports `app`, every full answer is a valid 0.6 answer under both Pydantic and the
published schema once its `{{SYMBOL}}`s are instantiated (matrix §2), every request-level case is
rejected by both, and the matrix covers every I3 §14 row.
"""

import ast
import copy
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    ServiceDependenciesByLocalityRequest,
)
from app.architecture_intelligence.schema_export import (
    LOCALITY_ANSWER_SCHEMA_PATH,
    LOCALITY_REQUEST_SCHEMA_PATH,
)

ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specifications" / "0.6.0"
AUTHOR = SPEC_DIR / "i3-vectors" / "author_expected_answers.py"
ORACLE = SPEC_DIR / "i3-vectors" / "expected-answers.json"
MATRIX = SPEC_DIR / "i3-expected-answer-matrix.md"

DOC = json.loads(ORACLE.read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in DOC["cases"]}
ANSWER_SCHEMA = json.loads(LOCALITY_ANSWER_SCHEMA_PATH.read_text())
REQUEST_SCHEMA = json.loads(LOCALITY_REQUEST_SCHEMA_PATH.read_text())

_SYMBOL = re.compile(r"^\{\{(\.\.\.)?(.+)\}\}$")
_DIGEST = hashlib.sha256(b"i3.1c-instantiation").hexdigest()


def _author_module():
    spec = importlib.util.spec_from_file_location("i3_author_expected_answers", AUTHOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _label(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()


def _scalar(name: str) -> str:
    """Matrix §2.4: a syntactically valid, distinct stand-in for each symbol."""
    kind, _, rest = name.partition(":")
    if name == "*":
        return "x"
    return {
        "SNAPSHOT_ID": f"aip:snapshot:v1:{_DIGEST}",
        "MODEL_REVISION": f"sha256:{_DIGEST}",
        "PRODUCER_VERSION": "0.6.0.dev0",
        "BUILD_REVISION": "0000000",
        "ASSESSMENT": f"aip:local-assessment:v1:{_label(rest)}",
        "SOURCE": f"urn:aip:source:kubernetes:{_label(rest)}",
        "WORKLOAD_ID": f"workload:{_label(rest)[:16]}",
        "DECLARED": f"evidence:declared:{_label(rest)[:16]}",
        "REF": f"evidence:ref:{_label(rest)[:16]}",
        "K8S": f"evidence:k8s:{_label(rest)[:16]}",
        "FIRST_SEEN": "2026-09-30T00:00:00Z",
        "LAST_SEEN": "2026-09-30T23:59:59Z",
    }[kind]


def _contains_symbol(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_SYMBOL.match(value))
    if isinstance(value, list):
        return any(_contains_symbol(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_symbol(item) for item in value.values())
    return False


def _resort(items: list) -> list:
    """Matrix §2.3: a list whose sort key holds a symbol is a set; restore the contract order."""
    if not items:
        return items
    first = items[0]
    if isinstance(first, str):
        return sorted(items)
    if not isinstance(first, dict):
        return items
    if "pair" in first and "v2_evidence_id" in first:
        return sorted(
            items,
            key=lambda i: (
                i["v2_evidence_id"],
                i["pair"]["source"]["source_instance_id"],
                i["pair"]["source"]["revision"],
            ),
        )
    if "source" in first:
        return sorted(
            items, key=lambda i: (i["source"]["source_instance_id"], i["source"]["revision"])
        )
    if "source_instance_id" in first:
        return sorted(items, key=lambda i: (i["source_instance_id"], i["revision"]))
    if "ref" in first:
        return sorted(items, key=lambda i: i["ref"])
    return items


def instantiate(value: Any) -> Any:
    if isinstance(value, str):
        match = _SYMBOL.match(value)
        return _scalar(match.group(2)) if match else value
    if isinstance(value, dict):
        return {key: instantiate(item) for key, item in value.items()}
    if isinstance(value, list):
        out = []
        for item in value:
            match = _SYMBOL.match(item) if isinstance(item, str) else None
            if match and match.group(1):  # a spread symbol stands for one or more values
                out.append(_scalar(match.group(2)))
            else:
                out.append(instantiate(item))
        return _resort(out) if _contains_symbol(value) else out
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
        "`python docs/specifications/0.6.0/i3-vectors/author_expected_answers.py`"
    )


def test_the_author_imports_only_the_standard_library():
    """I3 §14: the oracle must not be derived from the code it qualifies."""
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
    assert imported <= {"__future__", "copy", "hashlib", "json", "pathlib", "typing"}


def test_case_ids_are_unique_and_kinds_are_known():
    ids = [case["id"] for case in DOC["cases"]]
    assert len(ids) == len(set(ids))
    assert {case["kind"] for case in DOC["cases"]} == {"answer", "property", "request"}


# --- Full answers -------------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_expected_answer_is_a_valid_06_answer(case_id):
    answer = instantiate(copy.deepcopy(CASES[case_id]["expected"]))
    LocalityAnswer.model_validate(answer)
    assert _schema_errors(answer, ANSWER_SCHEMA) == []


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_case_request_is_a_valid_request(case_id):
    request = instantiate(copy.deepcopy(CASES[case_id]["request"]))
    ServiceDependenciesByLocalityRequest.model_validate(request)
    assert _schema_errors(request, REQUEST_SCHEMA) == []


@pytest.mark.parametrize("case_id", _cases("answer"))
def test_every_answer_echoes_its_request_mode(case_id):
    case = CASES[case_id]
    assert case["expected"]["mode"] == case["request"]["mode"]


@pytest.mark.parametrize("case_id", _cases("request"))
def test_every_request_case_is_rejected_by_both_validators(case_id):
    case = CASES[case_id]
    assert case["expected"] == {"validation_error": True}
    request = instantiate(copy.deepcopy(case["request"]))
    with pytest.raises(ValidationError):
        ServiceDependenciesByLocalityRequest.model_validate(request)
    if case_id not in _PYDANTIC_ONLY_REQUEST_CASES:
        assert _schema_errors(request, REQUEST_SCHEMA) != []


# Cross-field request rules the schema cannot express (decision record D16.9).
_PYDANTIC_ONLY_REQUEST_CASES = {"Q02", "Q04", "Q06"}


@pytest.mark.parametrize("case_id", _cases("property"))
def test_every_property_case_has_steps_and_assertions(case_id):
    case = CASES[case_id]
    assert case["steps"] and case["assert"]
    assert all("path" in item for item in case["assert"])


# --- Matrix -------------------------------------------------------------------------------------

_ROW = re.compile(r"^\| (S\d\d) \| (.+?) \| (.+?) \| (COVERED|PROPERTY|DEFERRED) \| (.*) \|$")
_SECTION_14_ROWS = 15


def _matrix_rows() -> list[tuple[str, str, list[str], str, str]]:
    rows = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            row, requirement, cases, status, note = match.groups()
            rows.append((row, requirement, re.findall(r"\b[XPQ]\d\d\b", cases), status, note))
    return rows


def test_the_matrix_lists_every_section_14_row_once():
    rows = [row for row, *_ in _matrix_rows()]
    assert rows == [f"S{n:02d}" for n in range(1, _SECTION_14_ROWS + 1)]


def test_every_matrix_case_exists_and_every_case_is_cited():
    cited = {case for _row, _req, cases, _status, _note in _matrix_rows() for case in cases}
    extra = MATRIX.read_text(encoding="utf-8")
    assert cited <= set(CASES)
    assert set(CASES) <= set(re.findall(r"\b[XPQ]\d\d\b", extra))


def test_covered_rows_cite_cases_and_deferred_rows_cite_an_owner():
    for row, _req, cases, status, note in _matrix_rows():
        if status in ("COVERED", "PROPERTY"):
            assert cases, row
        else:
            assert re.search(r"I3\.[234]|I4|I5|§\d+", note), row
