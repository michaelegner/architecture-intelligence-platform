"""Full-envelope comparison between a scenario's frozen expected `ArchitectureAnswer` and a real
one (I1.4 review finding #3: nothing about the public envelope may be silently omitted).

`missing_claim_ids`/`unexpected_claim_ids` are real `claim_id`s - both the frozen-expected and the
live-actual side already carry one, so there is nothing to re-derive at comparison time (finding
#1: comparison is always literal-vs-literal, never recomputed here). Every field on a claim present
on both sides is compared exactly, including both evidence-reference lists (finding #2) - a
wrong-but-existing evidence reference is a real mismatch, not silently passed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

from app.architecture_intelligence.contracts import ArchitectureAnswer, ServiceDependenciesData
from evaluation.architecture_answers.model import Scenario

_CLAIM_FIELDS = (
    "subject",
    "object",
    "predicate",
    "destination_resolution",
    "delivery",
    "qualification",
    "coverage",
    "evidence_refs",
    "resolution_evidence_refs",
)


@dataclass(frozen=True)
class FieldMismatch:
    claim_id: str | None  # None for an answer-level field (outcome, snapshot, ...)
    field: str
    expected: str
    actual: str


@dataclass(frozen=True)
class ScenarioReport:
    scenario_id: str
    passed: bool
    missing_claim_ids: tuple[str, ...]
    unexpected_claim_ids: tuple[str, ...]
    field_mismatches: tuple[FieldMismatch, ...]
    broken_evidence_refs: tuple[str, ...]


def _render(value: object) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render(item) for item in value) + "]"
    return repr(value)


def _mismatch_sort_key(mismatch: FieldMismatch) -> tuple[str, str]:
    return (mismatch.claim_id or "", mismatch.field)


def _check(
    mismatches: list[FieldMismatch], *, claim_id: str | None, field: str, expected, actual
) -> None:
    if expected != actual:
        mismatches.append(
            FieldMismatch(
                claim_id=claim_id, field=field, expected=_render(expected), actual=_render(actual)
            )
        )


def _answer_level_mismatches(
    expected: ArchitectureAnswer[ServiceDependenciesData],
    actual: ArchitectureAnswer[ServiceDependenciesData],
) -> list[FieldMismatch]:
    mismatches: list[FieldMismatch] = []
    _check(
        mismatches, claim_id=None, field="outcome", expected=expected.outcome, actual=actual.outcome
    )
    _check(
        mismatches,
        claim_id=None,
        field="snapshot.snapshot_id",
        expected=expected.snapshot.snapshot_id if expected.snapshot else None,
        actual=actual.snapshot.snapshot_id if actual.snapshot else None,
    )
    _check(
        mismatches,
        claim_id=None,
        field="snapshot.model_revision",
        expected=expected.snapshot.model_revision if expected.snapshot else None,
        actual=actual.snapshot.model_revision if actual.snapshot else None,
    )
    _check(
        mismatches,
        claim_id=None,
        field="observation_context",
        expected=expected.observation_context,
        actual=actual.observation_context,
    )
    _check(mismatches, claim_id=None, field="data", expected=expected.data, actual=actual.data)
    _check(
        mismatches,
        claim_id=None,
        field="evidence_refs",
        expected=expected.evidence_refs,
        actual=actual.evidence_refs,
    )
    _check(
        mismatches,
        claim_id=None,
        field="limitations",
        expected=expected.limitations,
        actual=actual.limitations,
    )
    return mismatches


def compare(
    scenario: Scenario,
    actual: ArchitectureAnswer[ServiceDependenciesData],
    *,
    broken_evidence_refs: tuple[str, ...] = (),
) -> ScenarioReport:
    expected = scenario.expected
    field_mismatches = _answer_level_mismatches(expected, actual)

    expected_by_id = {claim.claim_id: claim for claim in expected.claims}
    actual_by_id = {claim.claim_id: claim for claim in actual.claims}
    missing = sorted(set(expected_by_id) - set(actual_by_id))
    unexpected = sorted(set(actual_by_id) - set(expected_by_id))

    for claim_id in sorted(set(expected_by_id) & set(actual_by_id)):
        expected_claim = expected_by_id[claim_id]
        actual_claim = actual_by_id[claim_id]
        for field in _CLAIM_FIELDS:
            _check(
                field_mismatches,
                claim_id=claim_id,
                field=field,
                expected=getattr(expected_claim, field),
                actual=getattr(actual_claim, field),
            )

    passed = not (missing or unexpected or field_mismatches or broken_evidence_refs)
    return ScenarioReport(
        scenario_id=scenario.id,
        passed=passed,
        missing_claim_ids=tuple(missing),
        unexpected_claim_ids=tuple(unexpected),
        field_mismatches=tuple(sorted(field_mismatches, key=_mismatch_sort_key)),
        broken_evidence_refs=tuple(sorted(broken_evidence_refs)),
    )
