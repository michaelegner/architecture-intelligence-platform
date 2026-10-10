"""The internal Qualified Local Evidence Assessment (v0.6.0 I2.4; I2 spec §9-§10, decision record
D9 and D14).

Pure and read-side only: nothing is materialized. It takes one fenced I2.3 read - the evaluated
candidate page plus the declared `CALLS` evidence of its Operations - and produces:

- one `QualifiedLocalEvidenceAssessment` per (caller Service, Operation, environment, window,
  Workload) supported by `APPLICABLE` candidates (D14.3), with a stable assertion id and a
  snapshot-bound assessment-instance id (D9, D14.1-D14.2);
- a `CandidateLimitation` for every candidate that supports no positive assertion;
- the answer-level abstention when there is no positive assertion at all (D14.5).

Qualification goes through the one shared kernel, `app.qualification.declared_observed`, with only
the exact Operation's DECLARED evidence and the assertion's own v2 records (D14.4): v1 evidence and
another Operation's declaration never reach it, and a local `NOT_OBSERVED_IN_WINDOW` cannot occur.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.architecture_intelligence.canonical_json import canonical_digest
from app.architecture_intelligence.scoped_applicability import (
    APPLICABILITY_RULE_ID,
    APPLICABILITY_RULE_VERSION,
    REASON_LOCAL_COVERAGE_UNAVAILABLE,
    CandidateResult,
    CapturedWorkload,
    LocalityRequest,
    PairResult,
    RequestRefusal,
    ScopedDayWindowV1,
    ScopedLimitation,
    preflight,
)
from app.architecture_intelligence.scoped_evidence_repository import ScopedApplicabilityRead
from app.provenance.model import SCOPED_KEY_RULE_ID, SCOPED_KEY_RULE_VERSION
from app.qualification.declared_observed import (
    CONFIRMED,
    OBSERVED_ONLY,
    QUALIFICATION_RULE_ID,
    QUALIFICATION_RULE_VERSION,
    matches_declared_evidence,
    qualify_relation,
)
from app.telemetry.scoped_attribution import (
    NORMALIZATION_RULE_ID,
    NORMALIZATION_RULE_VERSION,
    LocalityDisposition,
)

ASSERTION_PREFIX = "aip:local-assertion:v1:"
ASSESSMENT_PREFIX = "aip:local-assessment:v1:"
REASON_NO_ELIGIBLE_LOCAL_OBSERVATION = "LOCALITY_NO_ELIGIBLE_LOCAL_OBSERVATION"
# I1 §5: no admitted v0.6 input establishes Workload-level HTTP coverage.
LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE = "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"
# I1 §4.1: the target's runtime placement is never copied from the caller or the Operation owner.
TARGET_RUNTIME_SCOPE_UNKNOWN = "UNKNOWN"

# D14.2: exactly these four rules, sorted by (id, version).
RULES: tuple[tuple[str, int], ...] = tuple(
    sorted(
        {
            (SCOPED_KEY_RULE_ID, SCOPED_KEY_RULE_VERSION),
            (NORMALIZATION_RULE_ID, NORMALIZATION_RULE_VERSION),
            (APPLICABILITY_RULE_ID, APPLICABILITY_RULE_VERSION),
            (QUALIFICATION_RULE_ID, QUALIFICATION_RULE_VERSION),
        }
    )
)


class AssessmentLimitation(StrEnum):
    """Internal I2.4 limitation code; not a `LOCALITY_*` reason (D14.1)."""

    WORKLOAD_UID_UNAVAILABLE = "WORKLOAD_UID_UNAVAILABLE"


# --- Identities (D9, D14.1-D14.2; frozen vectors in i2-vectors/local-assessment-id.json) ---------


def compute_local_assertion_id(
    *,
    subject_service_id: str,
    object_operation_id: str,
    environment: str,
    window: ScopedDayWindowV1,
    workload: CapturedWorkload,
) -> str:
    """The stable scoped assertion id. The Workload is its captured kind and captured UID; a
    Workload without a captured UID has no assertion id (D14.1)."""
    if workload.uid is None:
        raise ValueError("a Workload without a captured UID has no assertion id (D14.1)")
    payload = {
        "version": 1,
        "subject_service_id": subject_service_id,
        "relation_type": "CALLS",
        "object_operation_id": object_operation_id,
        "environment": environment,
        "first_utc_day": window.first_day.isoformat(),
        "last_utc_day": window.last_day.isoformat(),
        "workload": {
            "cluster_uid": workload.cluster_uid,
            "namespace": workload.namespace,
            "kind": workload.kind,
            "uid": workload.uid,
        },
    }
    return ASSERTION_PREFIX + canonical_digest(payload)


def compute_local_assessment_id(
    *,
    assertion_id: str,
    snapshot_id: str,
    capture_revisions: Iterable[tuple[str, str]],
    rules: Iterable[tuple[str, int]] = RULES,
) -> str:
    """The snapshot-bound assessment-instance id. Both lists are deduplicated and sorted, so their
    input order never matters (vector I02)."""
    payload = {
        "version": 1,
        "assertion_id": assertion_id,
        "snapshot_id": snapshot_id,
        "capture_revisions": [
            {"source_instance_id": source, "revision": revision}
            for source, revision in sorted(set(capture_revisions))
        ],
        "rules": [{"id": rule, "version": version} for rule, version in sorted(set(rules))],
    }
    return ASSESSMENT_PREFIX + canonical_digest(payload)


# --- Result types ------------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectedCapture:
    """A source whose pair supports the assertion: its identity, revision, mode and real
    `capturedAt` (I2 §9 `selected_capture`)."""

    source_instance_id: str
    revision: str
    evidence_mode: str
    captured_at: str


@dataclass(frozen=True)
class LocalObservation:
    """The assertion's distinct v2 evidence (lineage, never its key) and fact time bounds.
    `lineage_complete` is false when the candidate page was truncated (D14.8)."""

    evidence_ids: tuple[str, ...]
    first_seen: datetime
    last_seen: datetime
    lineage_complete: bool


@dataclass(frozen=True)
class QualifiedLocalEvidenceAssessment:
    """I2 §9's semantic unit for one positive caller-Workload-local `CALLS -> Operation`."""

    assertion_id: str
    assessment_id: str
    subject_service_id: str
    relation_type: str
    object_operation_id: str
    environment: str
    window: ScopedDayWindowV1
    caller_workload: CapturedWorkload
    target_runtime_scope: str
    observation: LocalObservation
    declared_evidence_ids: tuple[str, ...]
    selected_captures: tuple[SelectedCapture, ...]
    capture_evidence_refs: tuple[str, ...]
    applicability: LocalityDisposition
    qualification: str
    coverage: str
    source_limitations: tuple[tuple[str, PairResult], ...]
    """Every non-applicable pair of a contributing candidate, as `(v2 id, pair)` (D4)."""
    rules: tuple[tuple[str, int], ...]
    snapshot_id: str
    model_revision: str


@dataclass(frozen=True)
class CandidateLimitation:
    """A candidate that supports no positive assertion, keyed by its v2 id and the snapshot
    (D9 negative candidates). It carries its unchanged I2.3 summary and pairs."""

    v2_evidence_id: str
    snapshot_id: str
    disposition: LocalityDisposition
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    pairs: tuple[PairResult, ...]


@dataclass(frozen=True)
class LocalAssessmentResult:
    """One assessed candidate page. `disposition`/`reasons` are the answer level: `APPLICABLE`
    with no reasons when at least one assertion exists, the generic abstention otherwise, or the
    phase-1 `UNSUPPORTED` refusal."""

    snapshot_id: str
    model_revision: str
    disposition: LocalityDisposition
    reasons: tuple[str, ...]
    coverage: str
    assertions: tuple[QualifiedLocalEvidenceAssessment, ...]
    candidate_limitations: tuple[CandidateLimitation, ...]
    truncated: bool
    next_after_id: str | None


# --- The builder -------------------------------------------------------------------------------


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _workload_identity(workload: CapturedWorkload) -> tuple[str, str, str, str]:
    """The D14.1 Workload fields of the assertion id, in their canonical order."""
    assert workload.uid is not None
    return (workload.cluster_uid, workload.namespace, workload.kind, workload.uid)


def _limitation(candidate: CandidateResult, snapshot_id: str, *extra: str) -> CandidateLimitation:
    return CandidateLimitation(
        v2_evidence_id=candidate.record.id,
        snapshot_id=snapshot_id,
        disposition=candidate.disposition,
        reasons=candidate.reasons,
        limitations=tuple(sorted({*candidate.limitations, *extra})),
        pairs=candidate.pairs,
    )


def _assess_group(
    read: ScopedApplicabilityRead,
    request: LocalityRequest,
    window: ScopedDayWindowV1,
    operation_id: str,
    group: list[CandidateResult],
) -> QualifiedLocalEvidenceAssessment:
    # Every candidate of the group has the same D14.1 identity; the representative is fixed by
    # the remaining (non-identity) fields so input order never chooses it.
    workload = min((c.workload for c in group if c.workload), key=lambda w: (w.workload_id, w.name))
    records = sorted((c.record for c in group), key=lambda record: record.id)
    v2_ids = [record.id for record in records]

    # D14.4: only the exact Operation's DECLARED ids plus this assertion's v2 records.
    declared_ids = matches_declared_evidence(
        read.declared.edge_evidence_ids.get(operation_id, ()), read.declared.evidence_rows
    )
    evidence_by_id: dict[str, dict] = {
        eid: read.declared.evidence_rows[eid] for eid in declared_ids
    }
    for record in records:
        evidence_by_id[record.id] = {
            "evidence_type": "OBSERVED",
            "environment": record.environment,
            "last_seen": _aware(record.last_seen),
        }
    qualified = qualify_relation(
        [*declared_ids, *v2_ids],
        evidence_by_id,
        environment=request.environment,
        window_start=window.start,
        window_end=window.end,
        relation_type="CALLS",
        http_observed=False,
        messaging_observed=False,
        spans_observed=False,
        coverage_row_exists=False,
        qualification_enabled=False,
    )
    if qualified is None or qualified.qualification not in (CONFIRMED, OBSERVED_ONLY):
        # D14.4: every assertion has applicable v2, so nothing else is reachable; a local
        # NOT_OBSERVED_IN_WINDOW must never be emitted.
        raise AssertionError(f"local qualification must be CONFIRMED or OBSERVED_ONLY: {qualified}")

    applicable_pairs = [
        pair
        for candidate in group
        for pair in candidate.pairs
        if pair.disposition is LocalityDisposition.APPLICABLE
    ]
    captures = sorted(
        {
            SelectedCapture(
                source_instance_id=pair.source.source_instance_id,
                revision=pair.source.revision,
                evidence_mode=pair.source.evidence_mode,
                captured_at=pair.source.captured_at,
            )
            for pair in applicable_pairs
        },
        key=lambda capture: (capture.source_instance_id, capture.revision),
    )
    source_limitations = sorted(
        (
            (candidate.record.id, pair)
            for candidate in group
            for pair in candidate.pairs
            if pair.disposition is not LocalityDisposition.APPLICABLE
        ),
        key=lambda item: (item[0], item[1].source.sort_key),
    )
    assertion_id = compute_local_assertion_id(
        subject_service_id=request.subject_service_id,
        object_operation_id=operation_id,
        environment=request.environment,
        window=window,
        workload=workload,
    )
    return QualifiedLocalEvidenceAssessment(
        assertion_id=assertion_id,
        assessment_id=compute_local_assessment_id(
            assertion_id=assertion_id,
            snapshot_id=read.snapshot_id,
            capture_revisions=[(c.source_instance_id, c.revision) for c in captures],
        ),
        subject_service_id=request.subject_service_id,
        relation_type="CALLS",
        object_operation_id=operation_id,
        environment=request.environment,
        window=window,
        caller_workload=workload,
        target_runtime_scope=TARGET_RUNTIME_SCOPE_UNKNOWN,
        observation=LocalObservation(
            evidence_ids=tuple(v2_ids),
            first_seen=min(_aware(record.first_seen) for record in records),
            last_seen=max(_aware(record.last_seen) for record in records),
            lineage_complete=not read.result.truncated,
        ),
        declared_evidence_ids=tuple(declared_ids),
        selected_captures=tuple(captures),
        capture_evidence_refs=tuple(sorted({r for p in applicable_pairs for r in p.evidence_refs})),
        applicability=LocalityDisposition.APPLICABLE,
        qualification=qualified.qualification,
        coverage=LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE,
        source_limitations=tuple(source_limitations),
        rules=RULES,
        snapshot_id=read.snapshot_id,
        model_revision=read.model_revision,
    )


def assess(read: ScopedApplicabilityRead, request: LocalityRequest) -> LocalAssessmentResult:
    """Builds the assessment of one fenced read. Deterministic: candidate, pair, source and
    declared-evidence order never change the result."""
    checked = preflight(request)
    base = {
        "snapshot_id": read.snapshot_id,
        "model_revision": read.model_revision,
        "coverage": LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE,
        "truncated": read.result.truncated,
        "next_after_id": read.result.next_after_id,
    }
    if isinstance(checked, RequestRefusal):
        return LocalAssessmentResult(
            disposition=checked.disposition,
            reasons=checked.reasons,
            assertions=(),
            candidate_limitations=(),
            **base,
        )

    groups: dict[tuple[str, tuple[str, str, str, str]], list[CandidateResult]] = defaultdict(list)
    limitations = []
    for candidate in read.result.candidates:
        workload = candidate.workload
        if candidate.disposition is not LocalityDisposition.APPLICABLE or workload is None:
            limitations.append(_limitation(candidate, read.snapshot_id))
        elif workload.uid is None:
            limitations.append(
                _limitation(
                    candidate, read.snapshot_id, AssessmentLimitation.WORKLOAD_UID_UNAVAILABLE
                )
            )
        else:
            # D9/D14.3: group by exactly the assertion's frozen Workload identity, UID included.
            groups[(candidate.record.object_id, _workload_identity(workload))].append(candidate)

    assertions = sorted(
        (
            _assess_group(read, request, checked, operation_id, group)
            for (operation_id, _), group in groups.items()
        ),
        key=lambda assessment: assessment.assertion_id,
    )
    if assertions:
        disposition, reasons = LocalityDisposition.APPLICABLE, ()
    else:
        # D14.5 / I1 §10.2: generic abstention; never a specific ingress code or local absence.
        disposition = LocalityDisposition.INSUFFICIENT_EVIDENCE
        reasons = tuple(
            sorted({REASON_LOCAL_COVERAGE_UNAVAILABLE, REASON_NO_ELIGIBLE_LOCAL_OBSERVATION})
        )
    return LocalAssessmentResult(
        disposition=disposition,
        reasons=reasons,
        assertions=tuple(assertions),
        candidate_limitations=tuple(sorted(limitations, key=lambda item: item.v2_evidence_id)),
        **base,
    )


__all__ = [
    "ASSERTION_PREFIX",
    "ASSESSMENT_PREFIX",
    "RULES",
    "AssessmentLimitation",
    "CandidateLimitation",
    "LocalAssessmentResult",
    "LocalObservation",
    "QualifiedLocalEvidenceAssessment",
    "ScopedLimitation",
    "SelectedCapture",
    "assess",
    "compute_local_assertion_id",
    "compute_local_assessment_id",
]
