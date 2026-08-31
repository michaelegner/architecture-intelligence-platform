"""Expectation-driven exact comparison (I1 §16, extended by I2 §7).

Every expected fact must have an exact matching actual fact, and a same-identity-but-wrong-
status-or-evidence match is reported as a semantic mismatch, not a generic "missing" (I1 §16.1).

I2 promotes two checks that I1 left diagnostic-only: a forbidden identity that IS present in the
actual facts now fails the scenario, and an in-scope actual fact that is neither expected nor
forbidden now fails the scenario too (I2 §7) - there is no longer an unenforced "unexpected count"
separate from real mismatches.
"""

from __future__ import annotations

from dataclasses import dataclass

from evaluation.model import RelationFact, Scenario

MISSING = "missing"
SEMANTIC_MISMATCH = "semantic_mismatch"
FORBIDDEN_PRESENT = "forbidden_present"
UNEXPECTED = "unexpected"


@dataclass(frozen=True)
class Mismatch:
    kind: str  # MISSING | SEMANTIC_MISMATCH | FORBIDDEN_PRESENT | UNEXPECTED
    expected: RelationFact | None  # None for an UNEXPECTED mismatch - there is no expected side
    actual: RelationFact | None  # None for a MISSING mismatch - no actual fact was found


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    passed: bool
    mismatches: tuple[Mismatch, ...]


def _identity(fact: RelationFact) -> tuple[str, str, str]:
    return (fact.type, fact.source, fact.target)


def _mismatch_sort_key(mismatch: Mismatch) -> tuple[str, str, str, str]:
    """I4 spec §10: ScenarioResult.mismatches must itself be deterministic, not just the reporter's
    rendering (which already re-sorts, since I2) - the UNEXPECTED branch below iterates a
    set[RelationFact], whose order depends on Python's string-hash randomization and is not
    guaranteed stable across process runs. `kind` is an extra tiebreaker per spec §10.2; by
    construction at most one mismatch kind exists per canonical identity today, so it never
    actually breaks a tie, but keeps this key meaningful if that ever changes."""
    fact = mismatch.expected or mismatch.actual
    return (*_identity(fact), mismatch.kind)


def _matches(expected: RelationFact, actual: RelationFact) -> bool:
    """A field left unset (None) in expected.yaml is not part of the assertion; every field the
    scenario does specify must match exactly (I1 §16.3 - no fuzzy matching)."""
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

    for forbidden in scenario.forbidden_relations:
        found = actual_by_identity.get(_identity(forbidden))
        if found is not None:
            mismatches.append(Mismatch(kind=FORBIDDEN_PRESENT, expected=forbidden, actual=found))

    expected_identities = {_identity(fact) for fact in scenario.expected_relations}
    forbidden_identities = {_identity(fact) for fact in scenario.forbidden_relations}
    for fact in actual:
        identity = _identity(fact)
        if identity not in expected_identities and identity not in forbidden_identities:
            mismatches.append(Mismatch(kind=UNEXPECTED, expected=None, actual=fact))

    return ScenarioResult(
        # The scenario's directory name, not scenario.id (the YAML `scenario:` field) - this is
        # what the CLI's own --scenario argument and discover_scenarios() address scenarios by
        # (I1 §19), and what the spec's own report examples (I1 §17) sort/display by.
        scenario_id=scenario.path.name,
        passed=not mismatches,
        mismatches=tuple(sorted(mismatches, key=_mismatch_sort_key)),
    )
