"""Deterministic JSON reporter for the architecture-answers evaluation suite (I1.4 artifact
requirements) - no timestamps, absolute paths, or other run-specific values anywhere in the output;
two invocations against a fresh container must produce a byte-identical file.
"""

from __future__ import annotations

from pathlib import Path

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from evaluation.architecture_answers.runner import SuiteResult

SCHEMA_VERSION = "aip-evaluation-result/v1"
SUITE_NAME = "architecture-answers-i1"

RESULTS_PATH = Path(__file__).resolve().parent / "results" / "i1-evaluation-result.json"

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_INVALID = 2


def _scenario_payload(report) -> dict:
    return {
        "id": report.scenario_id,
        "result": "PASS" if report.passed else "FAIL",
        "missing_claim_ids": list(report.missing_claim_ids),
        "unexpected_claim_ids": list(report.unexpected_claim_ids),
        "field_mismatches": [
            {"claim_id": m.claim_id, "field": m.field, "expected": m.expected, "actual": m.actual}
            for m in report.field_mismatches
        ],
        "broken_evidence_refs": list(report.broken_evidence_refs),
    }


def build_report(result: SuiteResult) -> dict:
    passed = sum(1 for report in result.reports if report.passed)
    total = len(result.reports)
    overall_pass = passed == total and result.semantic_outputs_identical
    return {
        "schema_version": SCHEMA_VERSION,
        "suite": SUITE_NAME,
        "result": "PASS" if overall_pass else "FAIL",
        "run_count": result.run_count,
        "semantic_outputs_identical": result.semantic_outputs_identical,
        "run_output_sha256": list(result.run_output_sha256),
        "scenarios": [_scenario_payload(report) for report in result.reports],
        "summary": {"scenarios": total, "passed": passed, "failed": total - passed},
    }


def render_json(result: SuiteResult) -> str:
    return canonical_json_bytes(build_report(result)).decode("utf-8")


def write_report(result: SuiteResult, *, path: Path = RESULTS_PATH) -> str:
    """Writes the report to `path` (creating parent directories as needed) and returns the
    rendered JSON text."""
    text = render_json(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n")
    return text


def exit_code(result: SuiteResult) -> int:
    passed = all(report.passed for report in result.reports)
    return EXIT_OK if passed and result.semantic_outputs_identical else EXIT_FAILURES
