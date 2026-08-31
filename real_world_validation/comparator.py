"""Deterministic comparison semantics for the real-world validation contract (I1 §16/§19-21/§34-35).

`compare()` classifies every expected fact and every unexpected in-scope actual fact into the six
frozen classifications (model.CLASSIFICATIONS). It never derives ground truth, never repairs AIP
output, and never invents canonical identities (I1 §16) - it only matches what it is given.
"""

from __future__ import annotations

from real_world_validation.model import (
    CLASSIFICATION_RANK,
    DEFAULT_SEVERITY,
    SEVERITY_RANK,
    ExpectedDocument,
    Finding,
    RelationFact,
)


def _identity(fact: RelationFact) -> tuple[str, str, str]:
    return (fact.type, fact.source, fact.target)


def _matches(expected: RelationFact, actual: RelationFact) -> bool:
    """A field left unset (None) in expected.yaml is not part of the assertion; every field the
    dossier does specify must match exactly (I1 §13.3 - no fuzzy matching)."""
    if expected.status is not None and expected.status != actual.status:
        return False
    if (
        expected.declared_evidence is not None
        and expected.declared_evidence != actual.declared_evidence
    ):
        return False
    return not (
        expected.observed_evidence is not None
        and expected.observed_evidence != actual.observed_evidence
    )


def _finding(
    finding_id: str,
    classification: str,
    *,
    expected: RelationFact | None,
    actual: RelationFact | None,
) -> Finding:
    return Finding(
        id=finding_id,
        classification=classification,
        severity=DEFAULT_SEVERITY[classification],
        expected=expected,
        actual=actual,
    )


def _sort_key(finding: Finding) -> tuple[int, int, str, str, str, str]:
    """I1 §21's canonical order: classification, severity, relation type, source, target, finding
    id - using the documented rank tables so the order is total and independent of dict/set
    iteration order."""
    # UNSUPPORTED/UNRESOLVED_IDENTITY/INSUFFICIENT_EVIDENCE findings (I1 §12.4-12.6) have no
    # RelationFact on either side - they sort by finding id alone after the rank fields.
    fact = finding.expected or finding.actual
    return (
        CLASSIFICATION_RANK[finding.classification],
        SEVERITY_RANK[finding.severity],
        fact.type if fact else "",
        fact.source if fact else "",
        fact.target if fact else "",
        finding.id,
    )


def compare(expected: ExpectedDocument, actual: list[RelationFact]) -> list[Finding]:
    actual_by_identity = {_identity(fact): fact for fact in actual}
    matched_identities: set[tuple[str, str, str]] = set()

    findings: list[Finding] = []

    for relation in expected.expected_relations:
        identity = _identity(relation.fact)
        matched_identities.add(identity)
        found = actual_by_identity.get(identity)
        if found is None:
            findings.append(
                _finding(relation.id, "MISSING_SUPPORTED", expected=relation.fact, actual=None)
            )
        elif not _matches(relation.fact, found):
            findings.append(
                _finding(relation.id, "INCORRECT_SUPPORTED", expected=relation.fact, actual=found)
            )
        else:
            findings.append(_finding(relation.id, "CORRECT", expected=relation.fact, actual=found))

    # I1 §12.4/§12.5/§12.6: these three categories describe what independent ground truth itself
    # could or couldn't establish - they pass through unchanged, they are not matched against
    # `actual` (I1 §32: the comparator SHALL NOT infer unsupported semantics).
    for item in expected.unsupported:
        findings.append(_finding(item.id, "UNSUPPORTED", expected=None, actual=None))
    for item in expected.unresolved_identity:
        findings.append(_finding(item.id, "UNRESOLVED_IDENTITY", expected=None, actual=None))
    for item in expected.insufficient_evidence:
        findings.append(_finding(item.id, "INSUFFICIENT_EVIDENCE", expected=None, actual=None))

    # I1 §35: an unexpected in-scope actual fact must be surfaced, never silently ignored. The
    # frozen six-category vocabulary has no separate "unexpected" bucket, so - per I1 §12.3's own
    # "invented relation" example - it is reported as INCORRECT_SUPPORTED with no expected side.
    for fact in actual:
        identity = _identity(fact)
        if identity in matched_identities:
            continue
        if expected.scope.contains(fact):
            findings.append(
                _finding(
                    f"unexpected:{fact.type}:{fact.source}:{fact.target}",
                    "INCORRECT_SUPPORTED",
                    expected=None,
                    actual=fact,
                )
            )

    return sorted(findings, key=_sort_key)
