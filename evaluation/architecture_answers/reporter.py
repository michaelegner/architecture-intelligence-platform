"""Deterministic JSON reporter for the architecture-answers evaluation suite (I1.4 artifact
requirements, generalized to all three tools by I3.3 spec §35/§36/§61) - no timestamps, absolute
paths, or other run-specific values anywhere in the output; two invocations against a fresh
container must produce a byte-identical file.

The suite/artifact name drops its "-i1" suffix and `SCHEMA_VERSION` bumps to v2 with I3.3: the suite
is now permanently three-tool-general, not an I1-specific artifact, and §35 requires new fields
(`tool`, `cross_tool_invariants`, `real_system_qualification`) the v1 schema never had.
"""

from __future__ import annotations

from pathlib import Path

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from evaluation.architecture_answers.model import TOOL_ARCHITECTURE_DRIFT
from evaluation.architecture_answers.runner import SuiteResult

SCHEMA_VERSION = "aip-evaluation-result/v2"
SUITE_NAME = "architecture-answers"

RESULTS_PATH = (
    Path(__file__).resolve().parent / "results" / "architecture-answers-evaluation-result.json"
)

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_INVALID = 2

# I3 spec §33.4/§35: the Service-to-MCP invariant is deliberately proven outside this process (see
# evaluation.architecture_answers.invariants' module docstring for why) - this records that
# qualifying evidence as a reviewed, static declaration rather than a live-computed field. Only
# `covered_drift_scenarios` below is live-computed, from this exact run's own loaded scenarios, so
# it can never silently drift out of sync with the real suite.
_MCP_PARITY_TEST_PATH = "tests/integration/test_mcp_drift_scenario_parity.py"
_INSUFFICIENT_EVIDENCE_NOTE = (
    "drift-insufficient-evidence (spec section 27.6) is not a scenario in this suite - that state "
    "is unreachable through the declarative declarations+telemetry scenario format (a relation "
    "with empty evidence_ids is deleted by app.graph.importer's own reconciliation query, never "
    "left dangling); it is qualified instead by "
    "tests/integration/test_architecture_intelligence_service.py's real-Neo4j "
    "INSUFFICIENT_EVIDENCE drift tests, which construct it via a direct evidence-id mutation."
)

# I3 spec §37/§38/§61: the two frozen v0.3 real-system captures this suite's quarkus-frozen-*/
# airflow-frozen-* scenarios derive from - verified via `git hash-object` against the exact blob
# ids spec §37/§38 cite.
_REAL_SYSTEM_SOURCES = (
    {
        "system": "quarkus-super-heroes",
        "scenario_prefix": "quarkus-frozen-",
        "source_artifact": "docs/real-world-validation/cross-system/artifacts/quarkus-actual.yaml",
        "source_artifact_hash": "656446cd79c4cefec8f1ac0124fbb6b34e993704",
    },
    {
        "system": "apache-airflow",
        "scenario_prefix": "airflow-frozen-",
        "source_artifact": "docs/real-world-validation/cross-system/artifacts/airflow-actual.yaml",
        "source_artifact_hash": "8891289baa9facaf70a0cc0c6b9b2e0fdd9c838a",
    },
)


def _scenario_payload(report) -> dict:
    return {
        "id": report.scenario_id,
        "tool": report.tool,
        "result": "PASS" if report.passed else "FAIL",
        "missing_claim_ids": list(report.missing_claim_ids),
        "unexpected_claim_ids": list(report.unexpected_claim_ids),
        "field_mismatches": [
            {"claim_id": m.claim_id, "field": m.field, "expected": m.expected, "actual": m.actual}
            for m in report.field_mismatches
        ],
        "broken_evidence_refs": list(report.broken_evidence_refs),
    }


def _invariant_failure_payload(failure) -> dict:
    return {"invariant": failure.invariant, "detail": failure.detail}


def _live_invariant_section(result: SuiteResult, *, invariant: str) -> dict:
    failures = [f for f in result.cross_tool_invariant_failures if f.invariant == invariant]
    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": [_invariant_failure_payload(f) for f in failures],
    }


def _cross_tool_invariants(result: SuiteResult) -> dict:
    covered_drift_scenarios = sum(
        1 for report in result.reports if report.tool == TOOL_ARCHITECTURE_DRIFT
    )
    return {
        "dependency_to_drift": _live_invariant_section(result, invariant="dependency_to_drift"),
        "drift_to_evidence": _live_invariant_section(result, invariant="drift_to_evidence"),
        "service_to_mcp": {
            "status": "PASS",
            "qualified_by": _MCP_PARITY_TEST_PATH,
            "covered_drift_scenarios": covered_drift_scenarios,
            "note": _INSUFFICIENT_EVIDENCE_NOTE,
        },
    }


def _real_system_qualification(result: SuiteResult) -> list[dict]:
    payload = []
    for source in _REAL_SYSTEM_SOURCES:
        matching = [
            report
            for report in result.reports
            if report.scenario_id.startswith(source["scenario_prefix"])
        ]
        status = "PASS" if matching and all(report.passed for report in matching) else "FAIL"
        payload.append(
            {
                "system": source["system"],
                "source_artifact": source["source_artifact"],
                "source_artifact_hash": source["source_artifact_hash"],
                "status": status,
            }
        )
    return payload


def build_report(result: SuiteResult) -> dict:
    passed = sum(1 for report in result.reports if report.passed)
    total = len(result.reports)
    # Spec §36: a cross-tool invariant failure must fail the suite, same as any per-scenario
    # mismatch - `service_to_mcp`'s reviewed static status deliberately never contributes here, its
    # own gate (the pytest suite it names) is a separate part of the I3 regression gate (spec §60).
    overall_pass = (
        passed == total
        and result.semantic_outputs_identical
        and not result.cross_tool_invariant_failures
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "suite": SUITE_NAME,
        "candidate_sha": result.candidate_sha,
        "result": "PASS" if overall_pass else "FAIL",
        "run_count": result.run_count,
        "semantic_outputs_identical": result.semantic_outputs_identical,
        "run_output_sha256": list(result.run_output_sha256),
        "scenarios": [_scenario_payload(report) for report in result.reports],
        "summary": {"scenarios": total, "passed": passed, "failed": total - passed},
        "cross_tool_invariants": _cross_tool_invariants(result),
        "real_system_qualification": _real_system_qualification(result),
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
    return (
        EXIT_OK
        if passed and result.semantic_outputs_identical and not result.cross_tool_invariant_failures
        else EXIT_FAILURES
    )
