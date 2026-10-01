"""Machine check of the v0.6.0 I2 conformance matrix (I2.6b; I2 spec §16 DoD 8).

`docs/specifications/0.6.0/i2-conformance-matrix.md` maps each of the 65 variants of the frozen I1
oracle (`i1-vectors/conformance-expected.json`) to executable tests. This test keeps the map
honest:

- every oracle variant appears exactly once, and nothing else does;
- every cited `path::test` (or `path::Class::method`) exists, found by parsing the file's AST;
- a `COVERED` row cites at least one test;
- a `PARTIAL` or `NOT_REACHABLE` row cites a decision (`D<n>`) or a specification section (`§`).
"""

import ast
import json
import re
from functools import cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/specifications/0.6.0"
MATRIX = (SPEC / "i2-conformance-matrix.md").read_text(encoding="utf-8")
ORACLE = json.loads((SPEC / "i1-vectors/conformance-expected.json").read_text(encoding="utf-8"))
STATUSES = {"COVERED", "PARTIAL", "NOT_REACHABLE"}
_ROW = re.compile(r"^\| (L\d\d[a-z]) \|(.*)\|$")
_CITED = re.compile(r"`([^`]+?\.py::[^`]+)`")


def _rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in MATRIX.splitlines():
        match = _ROW.match(line)
        if match:
            variant, rest = match.groups()
            assert variant not in rows, f"{variant} appears twice"
            rows[variant] = [cell.strip() for cell in rest.split("|")]
    return rows


ROWS = _rows()


@cache
def _names(path: str) -> frozenset[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.update(
                f"{node.name}::{item.name}"
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    return frozenset(names)


def test_every_oracle_variant_appears_exactly_once():
    variants = [f"{c['id']}{v['id']}" for c in ORACLE["cases"] for v in c["variants"]]
    assert len(variants) == 65
    assert sorted(ROWS) == sorted(variants)


@pytest.mark.parametrize("variant", sorted(ROWS))
def test_every_row_is_well_formed_and_cites_real_tests(variant):
    kind, evidence, status, note = ROWS[variant]
    assert kind
    assert status in STATUSES, status
    cited = _CITED.findall(evidence)
    for citation in cited:
        path, name = citation.split("::", 1)
        assert (ROOT / path).is_file(), f"{variant}: {path} does not exist"
        assert name in _names(path), f"{variant}: {citation} does not exist"
    if status == "COVERED":
        assert cited, f"{variant}: COVERED without an executable test"
    else:
        assert re.search(r"\bD\d+|§", note), (
            f"{variant}: {status} needs a cited decision or section"
        )


def test_the_summary_counts_match_the_table():
    statuses = [row[2] for row in ROWS.values()]
    assert statuses.count("COVERED") == 61
    assert statuses.count("PARTIAL") == 2
    assert statuses.count("NOT_REACHABLE") == 2
