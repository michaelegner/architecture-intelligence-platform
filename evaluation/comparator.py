"""Expectation-driven exact comparison (spec I1 §16).

I1's required comparison is expectation-driven: every expected fact must have an exact matching
actual fact, and a same-identity-but-wrong-status-or-evidence match is reported as a semantic
mismatch, not a generic "missing" (§16.1). Exhaustive unexpected-fact enforcement and non-empty
`forbidden` assertions are deferred to I2 (§16.2) - unexpected facts are still counted here for the
diagnostic report line, but never make a scenario fail on their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.model import RelationFact, Scenario

MISSING = "missing"
SEMANTIC_MISMATCH = "semantic_mismatch"


@dataclass(frozen=True)
class Mismatch:
    kind: str  # MISSING | SEMANTIC_MISMATCH
    expected: RelationFact
    actual: RelationFact | None  # None for a MISSING mismatch


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    passed: bool
    mismatches: tuple[Mismatch, ...]
    unexpected_count: int  # diagnostic only - not enforced in I1, see spec §16.2


def _identity(fact: RelationFact) -> tuple[str, str, str]:
    return (fact.type, fact.source, fact.target)


def _matches(expected: RelationFact, actual: RelationFact) -> bool:
    """A field left unset (None) in expected.yaml is not part of the assertion; every field the
    scenario does specify must match exactly (spec §16.3 - no fuzzy matching)."""
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


def compare(scenario: Scenario, actual: set[RelationFact]) -> ScenarioResult:
    actual_by_identity = {_identity(fact): fact for fact in actual}

    mismatches: list[Mismatch] = []
    for expected in scenario.expected_relations:
        found = actual_by_identity.get(_identity(expected))
        if found is None:
            mismatches.append(Mismatch(kind=MISSING, expected=expected, actual=None))
        elif not _matches(expected, found):
            mismatches.append(Mismatch(kind=SEMANTIC_MISMATCH, expected=expected, actual=found))

    expected_identities = {_identity(fact) for fact in scenario.expected_relations}
    unexpected_count = sum(1 for fact in actual if _identity(fact) not in expected_identities)

    return ScenarioResult(
        # The scenario's directory name, not scenario.id (the YAML `scenario:` field) - this is
        # what the CLI's own --scenario argument and discover_scenarios() address scenarios by
        # (spec I1 §19), and what the spec's own report examples (§17) sort/display by.
        scenario_id=scenario.path.name,
        passed=not mismatches,
        mismatches=tuple(mismatches),
        unexpected_count=unexpected_count,
    )
