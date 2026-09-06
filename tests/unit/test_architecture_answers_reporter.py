from evaluation.architecture_answers.comparator import FieldMismatch, ScenarioReport
from evaluation.architecture_answers.invariants import CrossToolInvariantFailure
from evaluation.architecture_answers.reporter import build_report, exit_code
from evaluation.architecture_answers.runner import SuiteResult


def _result(
    reports, *, semantic_outputs_identical=True, cross_tool_invariant_failures=()
) -> SuiteResult:
    return SuiteResult(
        candidate_sha="f" * 40,
        reports=tuple(reports),
        run_count=2,
        run_output_sha256=(
            "sha256:aaa",
            "sha256:bbb" if not semantic_outputs_identical else "sha256:aaa",
        ),
        semantic_outputs_identical=semantic_outputs_identical,
        cross_tool_invariant_failures=tuple(cross_tool_invariant_failures),
    )


def _passing_report(scenario_id: str, *, tool: str = "get_service_dependencies") -> ScenarioReport:
    return ScenarioReport(
        scenario_id=scenario_id,
        tool=tool,
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
    assert report["candidate_sha"] == "f" * 40


def test_build_report_result_is_fail_when_a_scenario_fails():
    failing = ScenarioReport(
        scenario_id="b",
        tool="get_architecture_drift",
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
    assert scenario_b["tool"] == "get_architecture_drift"
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


# --- I3.3 PR #84 review: cross_tool_invariants must never self-report a check it didn't run -------


def test_service_to_mcp_status_is_qualified_externally_not_pass():
    """§33.4 is proven by a separate pytest suite this process never runs - reporting "PASS" here
    would be exactly the self-reported, unverified claim spec §33.4 requires this artifact to
    avoid."""
    result = _result([_passing_report("a", tool="get_architecture_drift")])
    report = build_report(result)

    service_to_mcp = report["cross_tool_invariants"]["service_to_mcp"]
    assert service_to_mcp["status"] == "QUALIFIED_EXTERNALLY"
    assert service_to_mcp["qualified_by"] == "tests/integration/test_mcp_drift_scenario_parity.py"
    assert service_to_mcp["covered_drift_scenarios"] == 1


def test_insufficient_evidence_qualification_names_the_qualifying_tests():
    """I3 spec §27.6's amendment: this state is unreachable through the declarative scenario
    format, so the report names the real-Neo4j tests that qualify it instead of a scenario id -
    also never a self-reported PASS."""
    result = _result([_passing_report("a")])
    report = build_report(result)

    section = report["cross_tool_invariants"]["insufficient_evidence_qualification"]
    assert section["status"] == "QUALIFIED_EXTERNALLY"
    assert section["qualified_by"] == [
        (
            "tests/integration/test_architecture_intelligence_service.py::"
            "test_drift_retains_a_claim_independent_insufficient_evidence_limitation"
        ),
        (
            "tests/integration/test_architecture_intelligence_service.py::"
            "test_drift_is_not_answered_when_every_candidate_path_lacks_evidence"
        ),
    ]


def test_a_cross_tool_invariant_failure_fails_the_overall_result_even_with_every_scenario_passing():
    failure = CrossToolInvariantFailure(invariant="dependency_to_drift", detail="mismatch")
    result = _result([_passing_report("a")], cross_tool_invariant_failures=[failure])
    report = build_report(result)

    assert report["result"] == "FAIL"
    assert report["cross_tool_invariants"]["dependency_to_drift"]["status"] == "FAIL"
    assert report["cross_tool_invariants"]["dependency_to_drift"]["failures"] == [
        {"invariant": "dependency_to_drift", "detail": "mismatch"}
    ]
    assert exit_code(result) == 1
