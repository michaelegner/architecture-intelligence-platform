"""Deterministic, human-readable report for the real-world validation contract (I1 §22-23).

No composite/weighted score - only concrete counts (I1 §22), using the field names frozen by I1
§23 (plus an `insufficient_evidence` counter, part of the full count list in I1 §13).
"""

from __future__ import annotations

from real_world_validation.model import Finding

CRITICAL_SEVERITY = "CRITICAL"


def _bool(value: bool | None) -> str:
    return "?" if value is None else str(value).lower()


def _fact_lines(label: str, finding: Finding) -> list[str]:
    fact = finding.expected if label == "Expected" else finding.actual
    if fact is None:
        return [f"{label}: (none)"]
    lines = [f"{label}:", f"  {fact.type}", f"  {fact.source}", f"    -> {fact.target}"]
    if (
        fact.status is not None
        or fact.declared_evidence is not None
        or fact.observed_evidence is not None
    ):
        lines.append(
            f"  status: {fact.status}  "
            f"evidence: declared={_bool(fact.declared_evidence)} observed={_bool(fact.observed_evidence)}"
        )
    return lines


def _format_finding(finding: Finding) -> list[str]:
    lines = ["", f"[{finding.classification}/{finding.severity}] {finding.id}"]
    if finding.expected is not None:
        lines += _fact_lines("Expected", finding)
    if finding.actual is not None:
        lines += _fact_lines("Actual", finding)
    return lines


def has_release_blocking_finding(findings: list[Finding]) -> bool:
    """A release-blocking finding is any CRITICAL-severity finding (I1 §14: unresolved CRITICAL
    findings = 0 is the release gate)."""
    return any(finding.severity == CRITICAL_SEVERITY for finding in findings)


def render(findings: list[Finding]) -> str:
    lines = ["AIP Real-World Validation — I1 contract", ""]
    for finding in findings:
        lines.extend(_format_finding(finding))

    def _count(classification: str) -> int:
        return sum(1 for f in findings if f.classification == classification)

    expected_supported = sum(
        1 for f in findings if f.classification in {"CORRECT", "MISSING_SUPPORTED"}
    ) + sum(
        1 for f in findings if f.classification == "INCORRECT_SUPPORTED" and f.expected is not None
    )
    correct = _count("CORRECT")
    missing_supported = _count("MISSING_SUPPORTED")
    incorrect_supported = _count("INCORRECT_SUPPORTED")
    unsupported = _count("UNSUPPORTED")
    unresolved_identities = _count("UNRESOLVED_IDENTITY")
    insufficient_evidence = _count("INSUFFICIENT_EVIDENCE")
    critical = sum(1 for f in findings if f.severity == CRITICAL_SEVERITY)

    lines += [
        "",
        f"Expected supported facts:      {expected_supported}",
        f"Correct:                       {correct}",
        f"Missing supported:             {missing_supported}",
        f"Incorrect supported:           {incorrect_supported}",
        f"Unsupported constructs:        {unsupported}",
        f"Unresolved identities:         {unresolved_identities}",
        f"Insufficient evidence:         {insufficient_evidence}",
        f"Critical semantic errors:      {critical}",
    ]
    return "\n".join(lines)
