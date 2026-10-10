"""v0.6.0 I3.2c: the I3 oracle matcher (`i3-expected-answer-matrix.md` §2) on its own.

Each rule has a positive and a negative case, so a matcher that accepts everything fails here
before it can make an oracle run pass vacuously.
"""

import base64
import json

import pytest

from tests.integration.locality_oracle.matcher import (
    PathError,
    check_property,
    match,
    resolve,
    substitute,
)


def test_literals_must_be_equal():
    assert match({"a": 1, "b": ["x"]}, {"a": 1, "b": ["x"]}) is not None
    assert match({"a": 1}, {"a": 2}) is None
    assert match({"a": 1}, {"a": 1, "b": 2}) is None
    assert match(["x", "y"], ["y", "x"]) is None, "a symbol-free list is positional"
    assert match(True, 1) is None, "a bool is not an int"


def test_a_scalar_binds_on_first_use_and_must_repeat():
    found = match({"a": "{{S}}", "b": "{{S}}"}, {"a": "v", "b": "v"})
    assert found is not None and found.scalars == {"S": "v"}
    assert match({"a": "{{S}}", "b": "{{S}}"}, {"a": "v", "b": "w"}) is None


def test_distinct_names_bind_distinct_values():
    assert match(["{{A}}", "{{B}}"], ["v", "w"]) is not None
    assert match(["{{A}}", "{{B}}"], ["v", "v"]) is None


def test_the_wildcard_matches_any_non_empty_string_and_binds_nothing():
    found = match({"m": "{{*}}", "n": "{{*}}"}, {"m": "one", "n": "two"})
    assert found is not None and found.scalars == {}
    assert match({"m": "{{*}}"}, {"m": ""}) is None
    assert match({"m": "{{*}}"}, {"m": None}) is None


def test_a_spread_binds_one_or_more_values_as_a_set():
    found = match(["lit", "{{...K}}"], ["a", "b", "lit"])
    assert found is not None and found.spreads == {"K": frozenset({"a", "b"})}
    assert match(["lit", "{{...K}}"], ["lit"]) is None, "a spread is never empty"
    assert match(["lit", "{{...K}}"], ["a", "b"]) is None, "the literal must be present"


def test_a_scalar_symbol_beside_a_spread_takes_one_element():
    found = match(
        {"d": "{{D}}", "l": ["lit", "{{...K}}", "{{D}}"]}, {"d": "x", "l": ["k1", "lit", "x"]}
    )
    assert found is not None and found.spreads == {"K": frozenset({"k1"})}
    assert match({"d": "{{D}}", "l": ["{{...K}}", "{{D}}"]}, {"d": "x", "l": ["k1", "y"]}) is None


def test_a_bound_spread_must_repeat_and_distinct_spreads_differ():
    same = {"x": ["{{...K}}"], "y": ["{{...K}}"]}
    assert match(same, {"x": ["a", "b"], "y": ["b", "a"]}) is not None
    assert match(same, {"x": ["a"], "y": ["b"]}) is None
    assert match({"x": ["{{...K}}"], "y": ["{{...L}}"]}, {"x": ["a"], "y": ["a"]}) is None


def test_a_list_with_symbols_may_match_as_a_set():
    expected = [{"s": "{{SOURCE:A}}", "n": 1}, {"s": "{{SOURCE:B}}", "n": 2}]
    actual = [{"s": "z-source", "n": 2}, {"s": "a-source", "n": 1}]
    found = match(expected, actual)
    assert found is not None
    assert found.scalars == {"SOURCE:A": "a-source", "SOURCE:B": "z-source"}
    assert match(expected, [*actual, {"s": "c", "n": 3}]) is None, "lengths must agree"


def test_a_list_binding_that_a_later_field_contradicts_is_replaced():
    """PR #396 review: the first positional binding (X=one, Y=two) conflicts with `z`, but the
    alternative X=two, Y=one satisfies the whole answer, so it must be found."""
    expected = {"a": ["{{X}}", "{{Y}}"], "z": "{{X}}"}
    found = match(expected, {"a": ["one", "two"], "z": "two"})
    assert found is not None and found.scalars == {"X": "two", "Y": "one"}
    assert match(expected, {"a": ["one", "two"], "z": "three"}) is None


def test_pre_bound_symbols_are_substituted_before_matching():
    assert substitute({"s": "{{SOURCE:A}}", "t": "{{X}}"}, {"SOURCE:A": "real"}) == {
        "s": "real",
        "t": "{{X}}",
    }
    assert match({"s": "{{SOURCE:A}}"}, {"s": "real"}, {"SOURCE:A": "real"}) is not None
    assert match({"s": "{{SOURCE:A}}"}, {"s": "other"}, {"SOURCE:A": "real"}) is None


def test_a_list_ordered_by_a_pre_bound_symbol_is_matched_as_a_set():
    """X14: pairs are sorted by real source ids, the oracle by the symbols' text."""
    expected = [{"s": "{{SOURCE:A}}", "n": 1}, {"s": "{{SOURCE:X}}", "n": 2}]
    actual = [{"s": "id-2", "n": 2}, {"s": "id-9", "n": 1}]
    assert match(expected, actual, {"SOURCE:A": "id-9", "SOURCE:X": "id-2"}) is not None
    assert match(expected, actual, {"SOURCE:A": "id-2", "SOURCE:X": "id-9"}) is None


def test_snapshot_and_model_revision_must_carry_one_digest():
    expected = {"snapshot_id": "{{SNAPSHOT_ID}}", "model_revision": "{{MODEL_REVISION}}"}
    good = {"snapshot_id": "aip:snapshot:v1:" + "a" * 64, "model_revision": "sha256:" + "a" * 64}
    bad = {"snapshot_id": "aip:snapshot:v1:" + "a" * 64, "model_revision": "sha256:" + "b" * 64}
    assert match(expected, good) is not None
    assert match(expected, bad) is None


# --- Property paths and operators ---------------------------------------------------------------

DOC = {
    "outcome": "PARTIAL",
    "data": {
        "items": [{"v": 1, "s": "A"}, {"v": 1, "s": "B"}],
        "empty": [],
        "cursor": base64.urlsafe_b64encode(json.dumps({"after_id": "x"}).encode())
        .decode()
        .rstrip("="),
    },
}


def test_paths_resolve_fields_indexes_fan_out_len_and_cursor():
    assert resolve("data.items[1].s", DOC) == "B"
    assert resolve("data.items[*].v", DOC) == [1, 1]
    assert resolve("len(data.items)", DOC) == 2
    assert resolve("cursor(data.cursor).after_id", DOC) == "x"
    with pytest.raises(PathError):
        resolve("data.missing", DOC)


@pytest.mark.parametrize(
    ("item", "holds"),
    [
        ({"path": "outcome", "equals": "PARTIAL"}, True),
        ({"path": "outcome", "equals": "ANSWERED"}, False),
        ({"path": "data.items[*].v", "all_equal": 1}, True),
        ({"path": "data.items[*].s", "all_equal": "A"}, False),
        ({"path": "data.empty", "all_equal": 1}, False),
        ({"path": "data.items[*].s", "contains": "B"}, True),
        ({"path": "data.items[*].s", "contains": "C"}, False),
        ({"path": "data.items[*].s", "subset_of": ["A", "B", "C"]}, True),
        ({"path": "data.items[*].s", "subset_of": ["A"]}, False),
        ({"path": "data.empty", "subset_of": ["A"]}, False),
        ({"path": "len(data.items)", "at_least": 2}, True),
        ({"path": "len(data.items)", "at_least": 3}, False),
        ({"path": "len(data.items)", "at_most": 2}, True),
        ({"path": "len(data.items)", "at_most": 1}, False),
        ({"path": "outcome", "step": 2, "equals_step": 1}, True),
        ({"path": "outcome", "step": 3, "equals_step": 1}, False),
        ({"path": "outcome", "step": 3, "not_equals_step": 1}, True),
        ({"path": "outcome", "step": 2, "not_equals_step": 1}, False),
    ],
)
def test_every_operator_holds_and_fails(item, holds):
    steps = {1: DOC, 2: DOC, 3: {**DOC, "outcome": "ANSWERED"}}
    if holds:
        check_property(item, steps)
    else:
        with pytest.raises(AssertionError):
            check_property(item, steps)


def test_prose_items_need_a_harness_verdict():
    item = {"path": "union of pages", "equals_expr": "every ID once"}
    with pytest.raises(AssertionError, match="no harness check"):
        check_property(item, {1: DOC})
    check_property(item, {1: DOC}, {"union of pages": True})
    with pytest.raises(AssertionError):
        check_property(item, {1: DOC}, {"union of pages": False})


def test_an_unknown_operator_is_rejected():
    with pytest.raises(AssertionError, match="unknown assert operator"):
        check_property({"path": "outcome", "roughly": 1}, {1: DOC})
