"""AIP v0.4.1 I1.1 - app.qualification.declared_observed
(docs/specifications/0.4.1/i1-qualification-consistency.md §10-§13, §19, §24-§25, §33).

Proves the shared kernel's boundary semantics directly, ahead of I1.3's cross-path differential
integration test - the Q1-Q15 matrix from spec §19/§33, plus the null-last_seen (§25.2),
determinism (§24), and Cypher-text-preservation (§13) requirements found during implementation
review. No Neo4j required anywhere in this file.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.qualification.declared_observed import (
    CONFIRMED,
    COVERAGE_NONE,
    COVERAGE_PARTIAL,
    COVERAGE_SUFFICIENT,
    COVERAGE_UNKNOWN,
    NOT_OBSERVED_IN_WINDOW,
    OBSERVED_ONLY,
    QualifiedRelation,
    classify_coverage,
    declared_evidence_exists,
    matches_declared_evidence,
    matches_observed_evidence,
    not_declared_evidence_exists,
    not_observed_evidence_exists,
    observed_evidence_condition,
    observed_evidence_exists,
    qualify_relation,
    relevant_coverage_signal,
)

ENVIRONMENT = "demo"
WINDOW_START = datetime(2026, 8, 26, tzinfo=UTC)
WINDOW_END = datetime(2026, 8, 27, tzinfo=UTC)
INSIDE_WINDOW = WINDOW_START + timedelta(hours=12)


def _declared(eid: str) -> tuple[str, dict]:
    return eid, {"evidence_type": "DECLARED"}


def _observed(
    eid: str, *, environment: str = ENVIRONMENT, last_seen: datetime | None = INSIDE_WINDOW
) -> tuple[str, dict]:
    return eid, {"evidence_type": "OBSERVED", "environment": environment, "last_seen": last_seen}


def _by_id(*rows: tuple[str, dict]) -> dict[str, dict]:
    return dict(rows)


def _qualify(evidence_ids, evidence_by_id, *, relation_type="CALLS", **coverage_kwargs):
    defaults = {
        "http_observed": False,
        "messaging_observed": False,
        "spans_observed": False,
        "coverage_row_exists": True,
        "qualification_enabled": True,
    }
    defaults.update(coverage_kwargs)
    return qualify_relation(
        evidence_ids,
        evidence_by_id,
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        relation_type=relation_type,
        **defaults,
    )


# --- Q1/Q6-style: declared + observed -> CONFIRMED ---------------------------------------------


def test_confirmed_when_declared_and_observed_both_match():
    evidence_by_id = _by_id(_declared("e1"), _observed("e2"))
    result = _qualify(["e1", "e2"], evidence_by_id)
    assert result == QualifiedRelation(CONFIRMED, None, ["e1", "e2"])


def test_confirmed_evidence_refs_are_the_sorted_union_with_duplicates_collapsed():
    # "z-declared" sorts after "a-observed" despite appearing first in evidence_ids, and
    # "a-observed" is deliberately repeated in evidence_ids to prove duplicates collapse.
    evidence_by_id = _by_id(_declared("z-declared"), _observed("a-observed"))
    result = _qualify(["z-declared", "a-observed", "a-observed"], evidence_by_id)
    assert result == QualifiedRelation(CONFIRMED, None, ["a-observed", "z-declared"])


# --- Q2/Q7-style: observed only -> OBSERVED_ONLY ------------------------------------------------


def test_observed_only_when_no_declared_evidence_matches():
    evidence_by_id = _by_id(_observed("e1"))
    result = _qualify(["e1"], evidence_by_id)
    assert result == QualifiedRelation(OBSERVED_ONLY, None, ["e1"])


# --- Q3/Q4/Q5/Q8-style: declared only -> NOT_OBSERVED_IN_WINDOW + coverage ----------------------


@pytest.mark.parametrize(
    ("relation_type", "http_observed", "messaging_observed", "expected_coverage"),
    [
        # CALLS: relevant signal is http_observed.
        pytest.param("CALLS", True, False, COVERAGE_SUFFICIENT, id="calls-sufficient"),
        pytest.param("CALLS", False, True, COVERAGE_PARTIAL, id="calls-partial"),
        pytest.param("CALLS", False, False, COVERAGE_NONE, id="calls-none"),
        # SENDS: relevant signal is messaging_observed.
        pytest.param("SENDS", False, True, COVERAGE_SUFFICIENT, id="sends-sufficient"),
        pytest.param("SENDS", True, False, COVERAGE_PARTIAL, id="sends-partial"),
        pytest.param("SENDS", False, False, COVERAGE_NONE, id="sends-none"),
        # RECEIVES_FROM: relevant signal is also messaging_observed (spec §12.1).
        pytest.param("RECEIVES_FROM", False, True, COVERAGE_SUFFICIENT, id="receives-sufficient"),
        pytest.param("RECEIVES_FROM", True, False, COVERAGE_PARTIAL, id="receives-partial"),
        pytest.param("RECEIVES_FROM", False, False, COVERAGE_NONE, id="receives-none"),
    ],
)
def test_not_observed_in_window_coverage_by_relation_kind(
    relation_type, http_observed, messaging_observed, expected_coverage
):
    evidence_by_id = _by_id(_declared("e1"))
    result = _qualify(
        ["e1"],
        evidence_by_id,
        relation_type=relation_type,
        http_observed=http_observed,
        messaging_observed=messaging_observed,
        # A relation kind's own signal being False doesn't mean nothing was ever observed for the
        # service - spans_observed mirrors the real http_observed-or-messaging_observed semantics
        # (app.analysis.runtime.ServiceTelemetryCoverage.spans_observed).
        spans_observed=http_observed or messaging_observed,
    )
    assert result == QualifiedRelation(NOT_OBSERVED_IN_WINDOW, expected_coverage, ["e1"])


# --- Q9-style: wrong environment ------------------------------------------------------------


def test_observed_evidence_in_a_different_environment_does_not_count():
    evidence_by_id = _by_id(_declared("e1"), _observed("e2", environment="other"))
    result = _qualify(["e1", "e2"], evidence_by_id, relation_type="CALLS")
    assert result == QualifiedRelation(NOT_OBSERVED_IN_WINDOW, COVERAGE_NONE, ["e1"])


# --- Q10-Q13-style: window boundaries (both bounds inclusive) -----------------------------------


def test_observed_before_window_start_does_not_match():
    evidence_by_id = _by_id(_observed("e1", last_seen=WINDOW_START - timedelta(seconds=1)))
    assert (
        matches_observed_evidence(
            ["e1"],
            evidence_by_id,
            environment=ENVIRONMENT,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        == []
    )


def test_observed_exactly_at_window_start_matches():
    evidence_by_id = _by_id(_observed("e1", last_seen=WINDOW_START))
    assert matches_observed_evidence(
        ["e1"],
        evidence_by_id,
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    ) == ["e1"]


def test_observed_exactly_at_window_end_matches():
    evidence_by_id = _by_id(_observed("e1", last_seen=WINDOW_END))
    assert matches_observed_evidence(
        ["e1"],
        evidence_by_id,
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    ) == ["e1"]


def test_observed_after_window_end_does_not_match():
    evidence_by_id = _by_id(_observed("e1", last_seen=WINDOW_END + timedelta(seconds=1)))
    assert (
        matches_observed_evidence(
            ["e1"],
            evidence_by_id,
            environment=ENVIRONMENT,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        == []
    )


def test_open_ended_window_still_matches_a_far_future_last_seen():
    far_future = WINDOW_START + timedelta(days=3650)
    evidence_by_id = _by_id(_observed("e1", last_seen=far_future))
    assert matches_observed_evidence(
        ["e1"], evidence_by_id, environment=ENVIRONMENT, window_start=WINDOW_START, window_end=None
    ) == ["e1"]


def test_observed_with_null_last_seen_does_not_match():
    """Spec §25.2 - distinct from the dangling-evidence-id case below."""
    evidence_by_id = _by_id(_observed("e1", last_seen=None))
    assert (
        matches_observed_evidence(
            ["e1"],
            evidence_by_id,
            environment=ENVIRONMENT,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        == []
    )


# --- Q14/Q15-style: dangling evidence and no-evidence exclusion ---------------------------------


def test_dangling_evidence_id_counts_as_neither_declared_nor_observed():
    evidence_by_id: dict[str, dict] = {}
    assert matches_declared_evidence(["missing"], evidence_by_id) == []
    assert (
        matches_observed_evidence(
            ["missing"],
            evidence_by_id,
            environment=ENVIRONMENT,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        == []
    )


def test_no_valid_evidence_returns_no_supported_claim():
    evidence_by_id: dict[str, dict] = {}
    assert _qualify(["dangling"], evidence_by_id) is None


def test_empty_evidence_ids_returns_no_supported_claim():
    evidence_by_id = _by_id(_declared("e1"))
    assert _qualify([], evidence_by_id) is None


# --- Determinism (spec §24) ----------------------------------------------------------------------


def test_declared_matching_is_independent_of_input_order_and_duplicates():
    evidence_by_id = _by_id(_declared("e1"), _declared("e2"))
    assert matches_declared_evidence(["e2", "e1", "e2", "e1"], evidence_by_id) == ["e1", "e2"]


def test_observed_matching_is_independent_of_input_order_and_duplicates():
    evidence_by_id = _by_id(_observed("e1"), _observed("e2"))
    assert matches_observed_evidence(
        ["e2", "e1", "e2", "e1"],
        evidence_by_id,
        environment=ENVIRONMENT,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    ) == ["e1", "e2"]


# --- Coverage-row / qualification-enabled edge cases (spec §12.2/§25.3) -------------------------


def test_coverage_is_unknown_when_no_coverage_row_exists():
    """Currently unreachable from either production caller (see the module docstring on
    `classify_coverage`) - supported and tested here regardless, per spec §25.3."""
    assert (
        classify_coverage(
            "CALLS",
            http_observed=True,
            messaging_observed=True,
            spans_observed=True,
            coverage_row_exists=False,
            qualification_enabled=True,
        )
        == COVERAGE_UNKNOWN
    )


def test_coverage_is_unknown_when_qualification_is_disabled():
    assert (
        classify_coverage(
            "CALLS",
            http_observed=True,
            messaging_observed=True,
            spans_observed=True,
            coverage_row_exists=True,
            qualification_enabled=False,
        )
        == COVERAGE_UNKNOWN
    )


def test_relevant_coverage_signal_rejects_an_unsupported_relation_type():
    try:
        relevant_coverage_signal("PROVIDES", http_observed=True, messaging_observed=True)
    except ValueError as exc:
        assert "PROVIDES" in str(exc)
    else:
        raise AssertionError("expected ValueError for an unsupported relation_type")


def test_classify_coverage_rejects_an_unsupported_relation_type():
    try:
        classify_coverage(
            "PROVIDES",
            http_observed=True,
            messaging_observed=True,
            spans_observed=True,
            coverage_row_exists=True,
            qualification_enabled=True,
        )
    except ValueError as exc:
        assert "PROVIDES" in str(exc)
    else:
        raise AssertionError("expected ValueError for an unsupported relation_type")


# --- Cypher fragment builders (spec §13) - golden-string regression tripwires --------------------


def test_observed_evidence_exists_matches_todays_literal_cypher_text():
    assert observed_evidence_exists() == (
        "EXISTS { UNWIND r.evidence_ids AS eid MATCH (e:Evidence {id: eid}) "
        "WHERE e.evidence_type = 'OBSERVED' AND e.environment = $environment "
        "AND e.last_seen >= $since AND ($until IS NULL OR e.last_seen <= $until) }"
    )


def test_declared_evidence_exists_matches_todays_literal_cypher_text():
    assert declared_evidence_exists() == (
        "EXISTS { UNWIND r.evidence_ids AS eid2 MATCH (e2:Evidence {id: eid2}) "
        "WHERE e2.evidence_type = 'DECLARED' }"
    )


def test_observed_evidence_condition_environment_optional_matches_o1s_inline_clause():
    """app/analysis/runtime.py's O1 query inlines this exact text (both UNION branches) instead of
    the EXISTS{}-wrapped form, because O1 needs to UNWIND and return matched rows."""
    assert observed_evidence_condition("e", environment_optional=True) == (
        "e.evidence_type = 'OBSERVED' AND ($environment IS NULL OR e.environment = $environment) "
        "AND e.last_seen >= $since AND ($until IS NULL OR e.last_seen <= $until)"
    )


def test_not_observed_evidence_exists_wraps_the_positive_form():
    assert not_observed_evidence_exists() == f"NOT ({observed_evidence_exists()})"


def test_not_declared_evidence_exists_wraps_the_positive_form():
    assert not_declared_evidence_exists() == f"NOT ({declared_evidence_exists()})"
