from evaluation.__main__ import EXIT_FAILURES, EXIT_INVALID, EXIT_OK, _exit_code, _load_scenarios
from evaluation.comparator import ScenarioResult


def _result(passed: bool) -> ScenarioResult:
    return ScenarioResult(scenario_id="x", passed=passed, mismatches=())


def test_exit_code_is_ok_only_when_every_scenario_passed():
    assert _exit_code([_result(True), _result(True)]) == EXIT_OK


def test_exit_code_is_failures_when_any_scenario_failed():
    assert _exit_code([_result(True), _result(False)]) == EXIT_FAILURES


def test_load_scenarios_rejects_an_empty_discovered_suite(tmp_path):
    # I1 post-merge review F4: an accidentally empty suite must not silently report a vacuous
    # PASS. _exit_code([]) alone is vacuously EXIT_OK - this guard at the loading boundary is what
    # actually prevents that from ever being reached by `run`.
    result = _load_scenarios(None, scenarios_dir=tmp_path)

    assert result == EXIT_INVALID
