"""I3 spec §17.1: pure query-construction checks for evaluation.projector's classification
branches - no Neo4j needed here (end-to-end classification against a real graph is covered by
tests/integration/test_evaluation_projector.py)."""

from app.analysis.runtime import NOT_OBSERVED_IN_WINDOW
from evaluation.projector import _CLASSIFIED_QUERY, _classified_branch


def test_classified_query_has_a_not_observed_in_window_branch_per_runtime_relation_type():
    for relation_type in ("CALLS", "SENDS", "RECEIVES_FROM"):
        assert f"'{relation_type}' AS type" in _CLASSIFIED_QUERY
    assert f"'{NOT_OBSERVED_IN_WINDOW}' AS status" in _CLASSIFIED_QUERY


def test_classified_query_still_has_confirmed_and_observed_only_branches_unchanged():
    assert "'CONFIRMED' AS status" in _CLASSIFIED_QUERY
    assert "'OBSERVED_ONLY' AS status" in _CLASSIFIED_QUERY


def test_classified_query_has_no_provides_branch():
    """I3 spec §7.4: PROVIDES stays outside the runtime-status branch."""
    assert "PROVIDES" not in _CLASSIFIED_QUERY


def test_classified_branch_can_represent_declared_true_observed_false():
    branch = _classified_branch(
        "CALLS",
        "Operation",
        "declared_guard",
        "observed_guard",
        NOT_OBSERVED_IN_WINDOW,
        declared=True,
        observed=False,
    )
    assert f"'{NOT_OBSERVED_IN_WINDOW}' AS status" in branch
    assert "true AS declared" in branch
    assert "false AS observed" in branch


def test_classified_branch_confirmed_shape_is_declared_true_observed_true():
    branch = _classified_branch(
        "CALLS",
        "Operation",
        "declared_guard",
        "observed_guard",
        "CONFIRMED",
        declared=True,
        observed=True,
    )
    assert "true AS declared" in branch
    assert "true AS observed" in branch


def test_classified_branch_observed_only_shape_is_declared_false_observed_true():
    branch = _classified_branch(
        "CALLS",
        "Operation",
        "declared_guard",
        "observed_guard",
        "OBSERVED_ONLY",
        declared=False,
        observed=True,
    )
    assert "false AS declared" in branch
    assert "true AS observed" in branch
