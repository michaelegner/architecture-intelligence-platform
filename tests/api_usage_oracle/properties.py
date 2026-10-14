"""The property assertions of the I3 oracle (`i3-expected-answer-matrix.md` §1), shared by the test
that checks the oracle itself (over the *expected* answers) and the harness that executes it (over
the *actual* answers). Pure: no `app` import, so it cannot borrow the semantics it checks."""

import json
from collections.abc import Mapping
from typing import Any

type Cases = Mapping[str, Mapping[str, Any]]


def _rows(cases: Cases, case_id: str) -> list[dict]:
    return cases[case_id]["expected"]["data"]["rows"]


def _row_keys(cases: Cases, case_id: str) -> list[tuple[str, str]]:
    return [(row["consumer"]["id"], row["gateway_route"]["id"]) for row in _rows(cases, case_id)]


def _dig(value: Any, path: str) -> Any:
    for part in path.split("."):
        value = value[part]
    return value


def check_property(item: Mapping[str, Any], *, cases: Cases, world_text: str) -> None:
    """Raise `AssertionError` unless the `assert` item holds over `cases`, a mapping from case id to
    a case whose `expected` is the answer to inspect. Every op carries a non-emptiness guard, so a
    property cannot pass vacuously."""
    op = item["op"]
    if op == "pages_concatenate_to":
        pages = [row for page in item["pages"] for row in _rows(cases, page)]
        assert pages == _rows(cases, item["whole"]) and pages
    elif op == "no_duplicate_rows":
        keys = [key for page in item["cases"] for key in _row_keys(cases, page)]
        assert len(keys) == len(set(keys)) and keys
    elif op == "suffix_of":
        rows, whole = _rows(cases, item["case"]), _rows(cases, item["whole"])
        assert rows and rows == whole[len(whole) - len(rows) :] and len(rows) < len(whole)
    elif op == "row_count":
        assert len(_rows(cases, item["case"])) == item["equals"] > 0
    elif op == "differ":
        values = [_dig(cases[c], item["path"]) for c in item["cases"]]
        assert len(set(values)) == len(values) > 1
    elif op == "disjoint_rows":
        seen: set[tuple[str, str]] = set()
        for case_id in item["cases"]:
            keys = set(_row_keys(cases, case_id))
            assert keys and not (keys & seen)
            seen |= keys
    elif op == "absent_everywhere":
        for case_id, other in cases.items():
            if other["kind"] == "answer":
                assert item["value"] not in json.dumps(other["expected"]), case_id
    elif op == "present_in_world":
        assert item["value"] in world_text
    else:  # a new op must be implemented here
        raise AssertionError(f"unknown property op {op!r}")
