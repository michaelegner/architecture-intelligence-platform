"""Human-readable, deterministic PASS/FAIL report for the I1 evaluation suite (spec §17).

In I1, unexpected-in-scope facts are counted for diagnostics only - the report says so explicitly
rather than implying the final v0.2.0 unexpected-fact semantics (full enforcement in I2) are
already complete.
"""

from __future__ import annotations

from evaluation.comparator import MISSING, SEMANTIC_MISMATCH, Mismatch, ScenarioResult
from evaluation.model import RelationFact


def _bool(value: bool | None) -> str:
    return "?" if value is None else str(value).lower()


def _wrong_status(mismatch: Mismatch) -> bool:
    return (
        mismatch.kind == SEMANTIC_MISMATCH
        and mismatch.expected.status is not None
        and mismatch.expected.status != mismatch.actual.status
    )


def _wrong_evidence(mismatch: Mismatch) -> bool:
    if mismatch.kind != SEMANTIC_MISMATCH:
        return False
    expected, actual = mismatch.expected, mismatch.actual
    return (
        expected.declared_evidence is not None
        and expected.declared_evidence != actual.declared_evidence
    ) or (
        expected.observed_evidence is not None
        and expected.observed_evidence != actual.observed_evidence
    )


def _reasons(mismatch: Mismatch) -> list[str]:
    if mismatch.kind == MISSING:
        return ["missing expected fact"]
    reasons = []
    if _wrong_status(mismatch):
        reasons.append("wrong status")
    expected, actual = mismatch.expected, mismatch.actual
    if (
        expected.declared_evidence is not None
        and expected.declared_evidence != actual.declared_evidence
    ):
        reasons.append(
            "missing declared evidence"
            if expected.declared_evidence
            else "unexpected declared evidence"
        )
    if (
        expected.observed_evidence is not None
        and expected.observed_evidence != actual.observed_evidence
    ):
        reasons.append(
            "missing observed evidence"
            if expected.observed_evidence
            else "unexpected observed evidence"
        )
    return reasons


def _fact_sort_key(fact: RelationFact) -> tuple[str, str, str]:
    return (fact.type, fact.source, fact.target)


def _format_mismatch(mismatch: Mismatch) -> list[str]:
    expected = mismatch.expected
    lines = [
        "",
        "Expected:",
        f"  {expected.type}",
        f"  {expected.source}",
        f"    -> {expected.target}",
        f"  status: {expected.status}",
        f"  evidence: declared={_bool(expected.declared_evidence)} observed={_bool(expected.observed_evidence)}",
        "",
        "Actual:",
    ]
    if mismatch.kind == MISSING:
        lines.append("  (no matching fact found)")
    else:
        actual = mismatch.actual
        lines.append(f"  status: {actual.status}")
        lines.append(
            f"  evidence: declared={_bool(actual.declared_evidence)} "
            f"observed={_bool(actual.observed_evidence)}"
        )
    lines += ["", "Reason:"] + [f"  {reason}" for reason in _reasons(mismatch)]
    return lines


def render(results: list[ScenarioResult]) -> str:
    sorted_results = sorted(results, key=lambda r: r.scenario_id)

    lines = ["AIP Evaluation — I1", ""]
    for result in sorted_results:
        lines.append(f"[{'PASS' if result.passed else 'FAIL'}] {result.scenario_id}")
        for mismatch in sorted(result.mismatches, key=lambda m: _fact_sort_key(m.expected)):
            lines.extend(_format_mismatch(mismatch))
        if not result.passed:
            lines.append("")

    total = len(sorted_results)
    passed = sum(1 for r in sorted_results if r.passed)
    all_mismatches = [m for r in sorted_results for m in r.mismatches]
    missing = sum(1 for m in all_mismatches if m.kind == MISSING)
    wrong_statuses = sum(1 for m in all_mismatches if _wrong_status(m))
    evidence_errors = sum(1 for m in all_mismatches if _wrong_evidence(m))

    lines += [
        f"Scenarios:          {total}",
        f"Passed:             {passed}",
        f"Failed:             {total - passed}",
        "",
        f"Missing facts:      {missing}",
        "Unexpected facts:   not enforced in I1",
        f"Wrong statuses:     {wrong_statuses}",
        f"Evidence errors:    {evidence_errors}",
        "",
        f"RESULT: {'PASS' if passed == total else 'FAIL'}",
    ]
    return "\n".join(lines)
