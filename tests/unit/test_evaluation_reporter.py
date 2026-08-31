from evaluation.comparator import (
    FORBIDDEN_PRESENT,
    MISSING,
    SEMANTIC_MISMATCH,
    UNEXPECTED,
    Mismatch,
    ScenarioResult,
)
from evaluation.model import RelationFact
from evaluation.reporter import render

_EXPECTED = RelationFact(
    type="CALLS",
    source="service:order-service",
    target="operation:service:product-service:GET:/prices",
    status="OBSERVED_ONLY",
    declared_evidence=False,
    observed_evidence=True,
)


def _passing(scenario_id: str) -> ScenarioResult:
    return ScenarioResult(scenario_id=scenario_id, passed=True, mismatches=())


def test_all_passing_renders_pass_summary_sorted_by_scenario_id():
    results = [_passing("03-async-confirmed"), _passing("01-rest-confirmed")]

    output = render(results)

    # I4 spec §14: locks the current iteration banner against an accidental regression (e.g. a
    # future iteration's bump landing in reporter.py without updating this test alongside it).
    assert output.startswith("AIP Evaluation — I4\n")

    lines = output.splitlines()
    assert lines.index("[PASS] 01-rest-confirmed") < lines.index("[PASS] 03-async-confirmed")
    assert "Scenarios:          2" in output
    assert "Passed:             2" in output
    assert "Failed:             0" in output
    assert "Missing facts:      0" in output
    assert "Unexpected facts:   0" in output
    assert "Forbidden facts present: 0" in output
    assert "Wrong statuses:     0" in output
    assert "Evidence errors:    0" in output
    assert output.rstrip().endswith("RESULT: PASS")


def test_missing_fact_is_reported_and_fails_the_result():
    result = ScenarioResult(
        scenario_id="02-rest-observed-only",
        passed=False,
        mismatches=(Mismatch(kind=MISSING, expected=_EXPECTED, actual=None),),
    )

    output = render([result])

    assert "[FAIL] 02-rest-observed-only" in output
    assert "missing expected fact" in output
    assert "Missing facts:      1" in output
    assert output.rstrip().endswith("RESULT: FAIL")


def test_wrong_status_is_reported_with_both_expected_and_actual():
    actual = RelationFact(
        type="CALLS",
        source="service:order-service",
        target="operation:service:product-service:GET:/prices",
        status="CONFIRMED",
        declared_evidence=True,
        observed_evidence=True,
    )
    result = ScenarioResult(
        scenario_id="02-rest-observed-only",
        passed=False,
        mismatches=(Mismatch(kind=SEMANTIC_MISMATCH, expected=_EXPECTED, actual=actual),),
    )

    output = render([result])

    assert "status: OBSERVED_ONLY" in output  # expected
    assert "status: CONFIRMED" in output  # actual
    assert "wrong status" in output
    assert "unexpected declared evidence" in output
    assert "Wrong statuses:     1" in output
    assert "Evidence errors:    1" in output


def test_unexpected_fact_renders_without_crashing_and_contributes_to_the_count():
    actual = RelationFact(
        type="CALLS",
        source="service:order-service",
        target="operation:service:other-service:GET:/other",
        status="CONFIRMED",
        declared_evidence=True,
        observed_evidence=True,
    )
    result = ScenarioResult(
        scenario_id="05-mixed-rest-async",
        passed=False,
        mismatches=(Mismatch(kind=UNEXPECTED, expected=None, actual=actual),),
    )

    output = render([result])

    assert "[FAIL] 05-mixed-rest-async" in output
    assert "Unexpected:" in output
    assert "unexpected in-scope fact" in output
    assert "Unexpected facts:   1" in output
    assert "Forbidden facts present: 0" in output
    assert output.rstrip().endswith("RESULT: FAIL")


def test_forbidden_fact_present_renders_correctly_and_contributes_to_the_count():
    forbidden = RelationFact(
        type="RECEIVES_FROM", source="service:order-service", target="queue:unused-q"
    )
    actual = RelationFact(
        type="RECEIVES_FROM",
        source="service:order-service",
        target="queue:unused-q",
        status="CONFIRMED",
        declared_evidence=True,
        observed_evidence=True,
    )
    result = ScenarioResult(
        scenario_id="04-orphan-messaging",
        passed=False,
        mismatches=(Mismatch(kind=FORBIDDEN_PRESENT, expected=forbidden, actual=actual),),
    )

    output = render([result])

    assert "[FAIL] 04-orphan-messaging" in output
    assert "Forbidden:" in output
    assert "forbidden fact present" in output
    assert "Forbidden facts present: 1" in output
    assert "Unexpected facts:   0" in output
    assert output.rstrip().endswith("RESULT: FAIL")
