from evaluation.__main__ import EXIT_FAILURES, EXIT_OK, _exit_code
from evaluation.comparator import ScenarioResult


def _result(passed: bool) -> ScenarioResult:
    return ScenarioResult(scenario_id="x", passed=passed, mismatches=(), unexpected_count=0)


def test_exit_code_is_ok_only_when_every_scenario_passed():
    assert _exit_code([_result(True), _result(True)]) == EXIT_OK


def test_exit_code_is_failures_when_any_scenario_failed():
    assert _exit_code([_result(True), _result(False)]) == EXIT_FAILURES


def test_exit_code_of_empty_results_is_ok():
    # Vacuously true - discovery/loading already validated there's at least one real scenario
    # before this is ever called with an empty list in practice.
    assert _exit_code([]) == EXIT_OK
