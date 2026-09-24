"""Deterministic comparison semantics for the real-world validation contract (I1 §16/§19-21/§34-35).

`compare()` classifies every expected fact and every unexpected in-scope actual fact into the six
frozen classifications (model.CLASSIFICATIONS). It never derives ground truth, never repairs AIP
output, and never invents canonical identities (I1 §16) - it only matches what it is given.
"""

from __future__ import annotations

from real_world_validation.model import (
    CLASSIFICATION_RANK,
    DEFAULT_SEVERITY,
    DEPLOYED_AS,
    DEPLOYMENT_METHODS,
    SEVERITY_RANK,
    DeploymentFact,
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


def _deployment_matches(expected: DeploymentFact, actual: DeploymentFact) -> bool:
    """Same rule as `_matches`: status always, and `supporting_methods`/`candidate_service_ids` only
    when the dossier sets them."""
    if expected.status != actual.status:
        return False
    if (
        expected.supporting_methods is not None
        and expected.supporting_methods != actual.supporting_methods
    ):
        return False
    return (
        expected.candidate_service_ids is None
        or expected.candidate_service_ids == actual.candidate_service_ids
    )


def _asserted_field_count(fact: DeploymentFact) -> int:
    return (fact.supporting_methods is not None) + (fact.candidate_service_ids is not None)


def _finding(
    finding_id: str,
    classification: str,
    *,
    expected: RelationFact | DeploymentFact | None,
    actual: RelationFact | DeploymentFact | None,
    forbidden: str | None = None,
) -> Finding:
    return Finding(
        id=finding_id,
        classification=classification,
        severity=DEFAULT_SEVERITY[classification],
        expected=expected,
        actual=actual,
        forbidden=forbidden,
    )


def _sort_fields(fact: RelationFact | DeploymentFact | None) -> tuple[str, str, str]:
    if fact is None:
        return ("", "", "")
    if isinstance(fact, DeploymentFact):
        return (DEPLOYED_AS, fact.service or "", fact.workload.render() if fact.workload else "")
    return (fact.type, fact.source, fact.target)


def _sort_key(finding: Finding) -> tuple[int, int, str, str, str, str]:
    """I1 §21's canonical order: classification, severity, relation type, source, target, finding
    id - using the documented rank tables so the order is total and independent of dict/set
    iteration order."""
    # UNSUPPORTED/UNRESOLVED_IDENTITY/INSUFFICIENT_EVIDENCE findings (I1 §12.4-12.6) have no
    # RelationFact on either side - they sort by finding id alone after the rank fields.
    return (
        CLASSIFICATION_RANK[finding.classification],
        SEVERITY_RANK[finding.severity],
        *_sort_fields(finding.expected or finding.actual),
        finding.id,
    )


def compare(
    expected: ExpectedDocument,
    actual: list[RelationFact],
    actual_deployments: list[DeploymentFact] | None = None,
) -> list[Finding]:
    """`actual_deployments` is None when the capture ran without deployment capture (a v0.3-style
    relation-only capture). In that case deployment expectations can't be judged, so any present is
    a configuration error rather than a silent MISSING_SUPPORTED."""
    if actual_deployments is None and (
        expected.expected_deployments or expected.forbidden_deployments
    ):
        raise ValueError(
            "the dossier has deployment expectations but the capture has no deployments section"
        )
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

    # v0.5.0 I5 §7: forbidden relations are negative expectations. A present one is
    # INCORRECT_SUPPORTED under the forbidden entry's own id, and it is not double-reported as
    # `unexpected:` below. An absent one is CORRECT, which makes the negative proof visible.
    for forbidden in expected.forbidden_relations:
        identity = (forbidden.type, forbidden.source, forbidden.target)
        pattern = f"{forbidden.type} {forbidden.source} -> {forbidden.target}"
        found = actual_by_identity.get(identity)
        matched_identities.add(identity)
        findings.append(
            _finding(
                forbidden.id,
                "CORRECT" if found is None else "INCORRECT_SUPPORTED",
                expected=None,
                actual=found,
                forbidden=pattern,
            )
        )

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

    findings.extend(_compare_deployments(expected, actual_deployments or []))
    return sorted(findings, key=_sort_key)


def _compare_deployments(expected: ExpectedDocument, actual: list[DeploymentFact]) -> list[Finding]:
    """v0.5.0 I5 §7: public `DEPLOYED_AS` outcomes, one per I3 §13.1 reconciliation candidate group.

    Several groups MAY share a (Service, Workload) key, for example two non-resolved groups with a
    null Service and Workload. So matching is one-to-one within each key, never a dict lookup that
    would collapse them:
    - expectations are taken most-specific first (most asserted fields), then by finding id;
    - each takes the first unused actual outcome of its key (in `resolution_id` order) that
      satisfies every asserted field;
    - if none does, the expectation is INCORRECT_SUPPORTED against the first unused actual of its
      key, or MISSING_SUPPORTED if the key has none left;
    - every actual outcome no expectation used is reported as unexpected.

    Capture only queries scoped Services, so every captured outcome is in scope."""
    findings: list[Finding] = []
    unused: dict[tuple, list[DeploymentFact]] = {}
    for fact in sorted(actual, key=lambda f: (f.identity, f.resolution_id or "", f.status)):
        unused.setdefault(fact.identity, []).append(fact)

    ordered = sorted(
        expected.expected_deployments,
        key=lambda d: (-_asserted_field_count(d.fact), d.id),
    )
    for deployment in ordered:
        candidates = unused.get(deployment.fact.identity, [])
        found = next((f for f in candidates if _deployment_matches(deployment.fact, f)), None)
        if found is not None:
            classification = "CORRECT"
        elif candidates:
            found = candidates[0]
            classification = "INCORRECT_SUPPORTED"
        else:
            classification = "MISSING_SUPPORTED"
        if found is not None:
            candidates.remove(found)
        findings.append(
            _finding(deployment.id, classification, expected=deployment.fact, actual=found)
        )

    for forbidden in expected.forbidden_deployments:
        pattern = (
            f"{DEPLOYED_AS} {forbidden.service} -> {forbidden.workload.render()} (any RESOLVED_*)"
        )
        identity = (
            forbidden.service,
            (forbidden.workload.namespace, forbidden.workload.kind, forbidden.workload.name),
        )
        pair = [f for f in actual if f.identity == identity]
        violating = next((f for f in pair if f.status in DEPLOYMENT_METHODS), None)
        shown = violating or (pair[0] if pair else None)
        # Outcomes for a forbidden pair are accounted for by this finding, not reported as
        # unexpected.
        remaining = unused.get(identity, [])
        for fact in pair:
            if fact in remaining:
                remaining.remove(fact)
        findings.append(
            _finding(
                forbidden.id,
                "INCORRECT_SUPPORTED" if violating is not None else "CORRECT",
                expected=None,
                actual=shown,
                forbidden=pattern,
            )
        )

    for facts in unused.values():
        for fact in facts:
            workload = fact.workload.render() if fact.workload else "-"
            findings.append(
                _finding(
                    f"unexpected:{DEPLOYED_AS}:{fact.service or '-'}:{workload}:"
                    f"{fact.resolution_id or '-'}",
                    "INCORRECT_SUPPORTED",
                    expected=None,
                    actual=fact,
                )
            )
    return findings
