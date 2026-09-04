from evaluation.architecture_answers.comparator import FieldMismatch, ScenarioReport
from evaluation.architecture_answers.reporter import build_report, exit_code
from evaluation.architecture_answers.runner import SuiteResult


def _result(reports, *, semantic_outputs_identical=True) -> SuiteResult:
    return SuiteResult(
        reports=tuple(reports),
        run_count=2,
        run_output_sha256=(
            "sha256:aaa",
            "sha256:bbb" if not semantic_outputs_identical else "sha256:aaa",
        ),
        semantic_outputs_identical=semantic_outputs_identical,
    )


def _passing_report(scenario_id: str) -> ScenarioReport:
    return ScenarioReport(
        scenario_id=scenario_id,
        passed=True,
        missing_claim_ids=(),
        unexpected_claim_ids=(),
        field_mismatches=(),
        broken_evidence_refs=(),
    )


def test_build_report_result_is_pass_when_every_scenario_passes_and_runs_are_identical():
    result = _result([_passing_report("a"), _passing_report("b")])
    report = build_report(result)

    assert report["result"] == "PASS"
    assert report["summary"] == {"scenarios": 2, "passed": 2, "failed": 0}
    assert report["semantic_outputs_identical"] is True
    assert report["run_count"] == 2


def test_build_report_result_is_fail_when_a_scenario_fails():
    failing = ScenarioReport(
        scenario_id="b",
        passed=False,
        missing_claim_ids=("aip:claim:v1:" + "1" * 64,),
        unexpected_claim_ids=(),
        field_mismatches=(
            FieldMismatch(claim_id=None, field="outcome", expected="ANSWERED", actual="PARTIAL"),
        ),
        broken_evidence_refs=(),
    )
    result = _result([_passing_report("a"), failing])
    report = build_report(result)

    assert report["result"] == "FAIL"
    assert report["summary"] == {"scenarios": 2, "passed": 1, "failed": 1}
    scenario_b = next(s for s in report["scenarios"] if s["id"] == "b")
    assert scenario_b["missing_claim_ids"] == ["aip:claim:v1:" + "1" * 64]
    assert scenario_b["field_mismatches"] == [
        {"claim_id": None, "field": "outcome", "expected": "ANSWERED", "actual": "PARTIAL"}
    ]


def test_build_report_result_is_fail_when_every_scenario_passes_but_runs_are_not_identical():
    result = _result([_passing_report("a")], semantic_outputs_identical=False)
    report = build_report(result)

    assert report["result"] == "FAIL"
    assert report["semantic_outputs_identical"] is False


def test_exit_code_ok_only_when_every_scenario_passed_and_runs_identical():
    assert exit_code(_result([_passing_report("a")])) == 0
    assert exit_code(_result([_passing_report("a")], semantic_outputs_identical=False)) == 1


def test_scenarios_are_reported_in_the_order_given():
    result = _result([_passing_report("z"), _passing_report("a")])
    report = build_report(result)
    assert [s["id"] for s in report["scenarios"]] == ["z", "a"]
