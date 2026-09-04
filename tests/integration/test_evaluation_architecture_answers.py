"""I1.4 exit condition: the architecture-answers evaluation suite proves I1's dependency vertical
slice end to end against real Neo4j - independently-authored frozen expected answers, two full
clean-state passes, and a real evidence-integrity check - not just that the suite is green by
construction (the sanity-break tests below)."""

import json
import shutil
from pathlib import Path

import pytest

from evaluation.architecture_answers.loader import (
    EXPECTED_ANSWER_FILENAME,
    discover_scenarios,
    load_scenario,
)
from evaluation.architecture_answers.reporter import exit_code
from evaluation.architecture_answers.runner import run_suite

# Deliberately relative to the current working directory, matching evaluation/__main__.py's own
# ANSWER_SCENARIOS_DIR (see its comment) - Evidence.source_file (spec §18's allowlist) is derived
# from exactly this path, and an absolute, checkout-location-specific path would make the frozen
# snapshot_id/model_revision literals in expected_answer.json unreproducible in CI.
SCENARIOS_DIR = Path("evaluation") / "architecture_answers" / "scenarios"
DATABASE = "neo4j"


def test_every_bundled_scenario_passes_with_identical_two_pass_output(driver):
    scenarios = [load_scenario(p) for p in discover_scenarios(SCENARIOS_DIR)]
    assert len(scenarios) >= 8  # spec §23's required semantic anchors, not a duplicate test matrix

    result = run_suite(driver, scenarios)

    assert result.semantic_outputs_identical
    assert result.run_output_sha256[0] == result.run_output_sha256[1]
    for report in result.reports:
        assert report.passed, (
            report.scenario_id,
            report.field_mismatches,
            report.missing_claim_ids,
        )
    assert exit_code(result) == 0


def test_a_wrong_expected_qualification_is_caught_as_a_field_mismatch(tmp_path, driver):
    broken_dir = tmp_path / "sync-confirmed"
    shutil.copytree(SCENARIOS_DIR / "sync-confirmed", broken_dir)
    expected_path = broken_dir / EXPECTED_ANSWER_FILENAME
    answer = json.loads(expected_path.read_text())
    answer["claims"][0]["qualification"] = "OBSERVED_ONLY"
    expected_path.write_text(json.dumps(answer))

    scenario = load_scenario(broken_dir)
    result = run_suite(driver, [scenario])

    [report] = result.reports
    assert not report.passed
    assert any(m.field == "qualification" for m in report.field_mismatches)
    assert exit_code(result) == 1


def test_a_forged_expected_claim_id_is_caught_as_missing_and_unexpected(tmp_path, driver):
    """A hand-typed claim_id that doesn't match the real claim-identity formula must not silently
    pass by accident - it should surface as both a missing (expected-but-absent) and an unexpected
    (actual-but-unlisted) claim, never as a false PASS."""
    broken_dir = tmp_path / "sync-confirmed"
    shutil.copytree(SCENARIOS_DIR / "sync-confirmed", broken_dir)
    expected_path = broken_dir / EXPECTED_ANSWER_FILENAME
    answer = json.loads(expected_path.read_text())
    forged_id = "aip:claim:v1:" + "0" * 64
    answer["claims"][0]["claim_id"] = forged_id
    answer["data"]["dependency_claim_ids"] = [forged_id]
    expected_path.write_text(json.dumps(answer))

    scenario = load_scenario(broken_dir)
    result = run_suite(driver, [scenario])

    [report] = result.reports
    assert not report.passed
    assert report.missing_claim_ids == (forged_id,)
    assert len(report.unexpected_claim_ids) == 1


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield
