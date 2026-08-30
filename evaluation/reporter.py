"""Human-readable, deterministic PASS/FAIL report for the AIP evaluation suite (I1 §17, extended
by I2 §8 to render FORBIDDEN_PRESENT and UNEXPECTED mismatches, which have no `expected` side).
"""

from __future__ import annotations

from evaluation.comparator import (
    FORBIDDEN_PRESENT,
    MISSING,
    SEMANTIC_MISMATCH,
    UNEXPECTED,
    Mismatch,
    ScenarioResult,
)
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
    if mismatch.kind == FORBIDDEN_PRESENT:
        return ["forbidden fact present"]
    if mismatch.kind == UNEXPECTED:
        return ["unexpected in-scope fact"]
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


def _identity_lines(label: str, fact: RelationFact) -> list[str]:
    return [f"{label}:", f"  {fact.type}", f"  {fact.source}", f"    -> {fact.target}"]


def _status_lines(fact: RelationFact) -> list[str]:
    return [
        f"  status: {fact.status}",
        f"  evidence: declared={_bool(fact.declared_evidence)} observed={_bool(fact.observed_evidence)}",
    ]


def _sort_key(mismatch: Mismatch) -> tuple[str, str, str]:
    # An UNEXPECTED mismatch has no expected side (I2 §5.3) - fall back to the actual fact so it
    # still sorts deterministically alongside the others.
    fact = mismatch.expected or mismatch.actual
    return (fact.type, fact.source, fact.target)


def _format_mismatch(mismatch: Mismatch) -> list[str]:
    if mismatch.kind == UNEXPECTED:
        lines = [
            "",
            *_identity_lines("Unexpected", mismatch.actual),
            *_status_lines(mismatch.actual),
        ]
    elif mismatch.kind == FORBIDDEN_PRESENT:
        lines = [
            "",
            *_identity_lines("Forbidden", mismatch.expected),
            "",
            "Actual:",
            *_status_lines(mismatch.actual),
        ]
    else:
        lines = [
            "",
            *_identity_lines("Expected", mismatch.expected),
            *_status_lines(mismatch.expected),
            "",
            "Actual:",
        ]
        if mismatch.kind == MISSING:
            lines.append("  (no matching fact found)")
        else:
            lines.extend(_status_lines(mismatch.actual))
    lines += ["", "Reason:"] + [f"  {reason}" for reason in _reasons(mismatch)]
    return lines


def render(results: list[ScenarioResult]) -> str:
    sorted_results = sorted(results, key=lambda r: r.scenario_id)

    lines = ["AIP Evaluation — I2", ""]
    for result in sorted_results:
        lines.append(f"[{'PASS' if result.passed else 'FAIL'}] {result.scenario_id}")
        for mismatch in sorted(result.mismatches, key=_sort_key):
            lines.extend(_format_mismatch(mismatch))
        if not result.passed:
            lines.append("")

    total = len(sorted_results)
    passed = sum(1 for r in sorted_results if r.passed)
    all_mismatches = [m for r in sorted_results for m in r.mismatches]
    missing = sum(1 for m in all_mismatches if m.kind == MISSING)
    unexpected = sum(1 for m in all_mismatches if m.kind == UNEXPECTED)
    forbidden_present = sum(1 for m in all_mismatches if m.kind == FORBIDDEN_PRESENT)
    wrong_statuses = sum(1 for m in all_mismatches if _wrong_status(m))
    evidence_errors = sum(1 for m in all_mismatches if _wrong_evidence(m))

    lines += [
        f"Scenarios:          {total}",
        f"Passed:             {passed}",
        f"Failed:             {total - passed}",
        "",
        f"Missing facts:      {missing}",
        f"Unexpected facts:   {unexpected}",
        f"Forbidden facts present: {forbidden_present}",
        f"Wrong statuses:     {wrong_statuses}",
        f"Evidence errors:    {evidence_errors}",
        "",
        f"RESULT: {'PASS' if passed == total else 'FAIL'}",
    ]
    return "\n".join(lines)
