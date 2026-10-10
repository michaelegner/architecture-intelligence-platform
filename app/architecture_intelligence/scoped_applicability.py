"""Selected-capture applicability of retained caller-Pod-scoped v2 records (v0.6.0 I2.3; I2 spec
§8.1, I1 §§8-10.1, support matrix §§13-15.2, decision record D3, D4 and D13).

Pure and deterministic: the fenced repository read supplies the v2 candidate page and every
accepted Kubernetes source's committed capture (`SourceInventory`), and this module decides, per
candidate, which sources it is paired with and what each (candidate, source) pair yields under I1's
four ordered phases, then rolls the pairs up into one candidate summary.

- **Selection (D4, D13.3).** An explicit `SourceSelector` names exactly one committed
  `(source, revision)`; otherwise a source is admitted only when it captures a Pod with the
  candidate's exact Pod UID (rule 1, any cluster) or when its envelope `clusterUid` equals the
  candidate's cluster and its complete namespace scope contains the CLIENT namespace (rule 2).
  Every other source is omitted, never judged as a missing Pod.
- **Phases (I1 §10.1, D13.2).** Phase 1 is the request preflight; phases 2-4 run per pair, and the
  first phase with any cause terminates it. Within that phase every cause whose inputs exist is
  kept and the primary disposition follows the I1 precedence. No later phase is evaluated.
- **Roll-up (D4, D13.5)** happens after, not inside, the per-pair gates and keeps every pair.

Nothing here reads or writes the graph, resolves a Service or qualifies a relation (I2.4).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from enum import StrEnum

from app.architecture_intelligence.deployment_projection import (
    WORKLOAD_KIND_BY_RAW,
    WORKLOAD_KIND_CONSISTENCY_ATTR,
)
from app.common.rfc3339 import _parse_rfc3339
from app.provenance.model import ScopedObservedCall
from app.telemetry.scoped_attribution import DISPOSITION_PRECEDENCE, LocalityDisposition

# D14.2: this evaluator's rule identity, named in a local-assessment instance id.
APPLICABILITY_RULE_ID = "scoped-caller-locality-applicability"
APPLICABILITY_RULE_VERSION = 1

# I1 §10 query-time reason codes (the ingestion-only ones never appear here, matrix §15.3).
REASON_UNSUPPORTED_DIMENSION = "LOCALITY_UNSUPPORTED_DIMENSION"
REASON_UNSUPPORTED_RELATION = "LOCALITY_UNSUPPORTED_RELATION"
REASON_UNSUPPORTED_TEMPORAL_RESOLUTION = "LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION"
REASON_CAPTURE_MODE_UNSUPPORTED = "LOCALITY_CAPTURE_MODE_UNSUPPORTED"
REASON_OBSERVATION_TEMPORAL_MISMATCH = "LOCALITY_OBSERVATION_TEMPORAL_MISMATCH"
REASON_CAPTURE_TEMPORAL_MISMATCH = "LOCALITY_CAPTURE_TEMPORAL_MISMATCH"
REASON_CAPTURE_TIMESTAMP_MISSING = "LOCALITY_CAPTURE_TIMESTAMP_MISSING"
REASON_CAPTURE_MISSING_POD = "LOCALITY_CAPTURE_MISSING_POD"
REASON_POD_OWNER_UNRESOLVED = "LOCALITY_POD_OWNER_UNRESOLVED"
REASON_POD_OWNER_AMBIGUOUS = "LOCALITY_POD_OWNER_AMBIGUOUS"
REASON_POD_OWNER_CONFLICT = "LOCALITY_POD_OWNER_CONFLICT"
REASON_CLUSTER_UID_CONFLICT = "LOCALITY_CLUSTER_UID_CONFLICT"
REASON_NAMESPACE_CONFLICT = "LOCALITY_NAMESPACE_CONFLICT"
REASON_LOCAL_COVERAGE_UNAVAILABLE = "LOCALITY_LOCAL_COVERAGE_UNAVAILABLE"

_REASON_DISPOSITION = {
    REASON_UNSUPPORTED_DIMENSION: LocalityDisposition.UNSUPPORTED,
    REASON_UNSUPPORTED_RELATION: LocalityDisposition.UNSUPPORTED,
    REASON_UNSUPPORTED_TEMPORAL_RESOLUTION: LocalityDisposition.UNSUPPORTED,
    REASON_CAPTURE_MODE_UNSUPPORTED: LocalityDisposition.UNSUPPORTED,
    REASON_OBSERVATION_TEMPORAL_MISMATCH: LocalityDisposition.INAPPLICABLE,
    REASON_CAPTURE_TEMPORAL_MISMATCH: LocalityDisposition.INAPPLICABLE,
    REASON_CAPTURE_TIMESTAMP_MISSING: LocalityDisposition.INSUFFICIENT_EVIDENCE,
    REASON_CAPTURE_MISSING_POD: LocalityDisposition.UNRESOLVED,
    REASON_POD_OWNER_UNRESOLVED: LocalityDisposition.UNRESOLVED,
    REASON_POD_OWNER_AMBIGUOUS: LocalityDisposition.AMBIGUOUS,
    REASON_POD_OWNER_CONFLICT: LocalityDisposition.CONFLICT,
    REASON_CLUSTER_UID_CONFLICT: LocalityDisposition.CONFLICT,
    REASON_NAMESPACE_CONFLICT: LocalityDisposition.CONFLICT,
}

# I1 §4.2: the admitted positive locality dimensions; anything else is phase-1 UNSUPPORTED.
SUPPORTED_DIMENSIONS = frozenset({"cluster", "namespace", "workload"})
SUPPORTED_RELATION = "CALLS"
CAPTURED_RESOURCE = "CAPTURED_RESOURCE"


class ScopedLimitation(StrEnum):
    """Internal I2 limitation codes; deliberately not `LOCALITY_*` reasons (D4, D13.4)."""

    NO_SELECTABLE_COVERING_SOURCE = "NO_SELECTABLE_COVERING_SOURCE"
    REQUEST_ENVIRONMENT_MISMATCH = "REQUEST_ENVIRONMENT_MISMATCH"


class AdmissionBasis(StrEnum):
    """Why a source was paired with a candidate (D13.7)."""

    EXPLICIT = "EXPLICIT"
    POD_UID = "POD_UID"
    CLUSTER_NAMESPACE = "CLUSTER_NAMESPACE"


# --- Window and request (phase 1) --------------------------------------------------------------

_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _parse_day(value: str) -> date:
    if not _DATE_PATTERN.fullmatch(value):
        raise ValueError(f"not a YYYY-MM-DD day: {value!r}")
    return date.fromisoformat(value)


@dataclass(frozen=True)
class ScopedDayWindowV1:
    """Matrix §13: an inclusive whole-UTC-day range. `end` is `last_day` at 23:59:59.999999 UTC,
    computed on `last_day` itself so `9999-12-31` stays representable (vector W05)."""

    first_day: date
    last_day: date

    def __post_init__(self) -> None:
        if self.first_day > self.last_day:
            raise ValueError("first_day must not be after last_day")

    @classmethod
    def parse(cls, first_day: str, last_day: str) -> "ScopedDayWindowV1":
        """Refuses anything but two valid `YYYY-MM-DD` days in order; never widens or narrows."""
        return cls(_parse_day(first_day), _parse_day(last_day))

    @property
    def start(self) -> datetime:
        return datetime.combine(self.first_day, time.min, tzinfo=UTC)

    @property
    def end(self) -> datetime:
        return datetime.combine(self.last_day, time.max, tzinfo=UTC)

    def contains(self, instant: datetime) -> bool:
        """Inclusive on both bounds. A naive instant is read as UTC, as `utc_day` does."""
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        return self.start <= instant <= self.end


def _is_date_time(value: str) -> bool:
    if "T" not in value:
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class SourceSelector:
    """An explicit selection of one committed capture (D13.3)."""

    source_instance_id: str
    revision: str


@dataclass(frozen=True)
class LocalityRequest:
    """The internal request. `first_day`/`last_day` stay raw strings so phase 1 can tell a sub-day
    request (UNSUPPORTED, L25) from a malformed one (a validation refusal)."""

    subject_service_id: str
    environment: str
    first_day: str
    last_day: str
    object_operation_id: str | None = None
    relation_type: str = SUPPORTED_RELATION
    dimensions: frozenset[str] = frozenset()
    selector: SourceSelector | None = None


@dataclass(frozen=True)
class RequestRefusal:
    """Phase 1 terminated the whole request (I1 §10.1)."""

    disposition: LocalityDisposition
    reasons: tuple[str, ...]
    phase: int = 1


def preflight(request: LocalityRequest) -> ScopedDayWindowV1 | RequestRefusal:
    """Phase 1. Every established cause is kept. A bound that is neither a day nor a date-time is
    malformed and raises `ValueError`; a date-time bound is a finer resolution (L25)."""
    reasons: set[str] = set()
    if request.relation_type != SUPPORTED_RELATION:
        reasons.add(REASON_UNSUPPORTED_RELATION)
    if request.dimensions - SUPPORTED_DIMENSIONS:
        reasons.add(REASON_UNSUPPORTED_DIMENSION)
    bounds = (request.first_day, request.last_day)
    if any(_is_date_time(bound) for bound in bounds):
        if not all(_is_date_time(bound) or _DATE_PATTERN.fullmatch(bound) for bound in bounds):
            raise ValueError("malformed window bound")
        reasons.add(REASON_UNSUPPORTED_TEMPORAL_RESOLUTION)
        window = None
    else:
        window = ScopedDayWindowV1.parse(*bounds)
    if reasons:
        return RequestRefusal(LocalityDisposition.UNSUPPORTED, tuple(sorted(reasons)))
    assert window is not None
    return window


# --- Inputs read under the fence ---------------------------------------------------------------


@dataclass(frozen=True)
class SourceCapture:
    """One accepted Kubernetes source's committed capture (D5 `SourceState.capture_*`)."""

    source_instance_id: str
    discovery_scope_id: str
    revision: str
    cluster_uid: str
    namespaces: tuple[str, ...]
    evidence_mode: str
    captured_at: str

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (self.source_instance_id, self.discovery_scope_id, self.revision)


@dataclass(frozen=True)
class CapturedWorkload:
    """A current supported Workload as this source captured it. `uid` is its captured UID."""

    workload_id: str
    kind: str
    namespace: str
    name: str
    cluster_uid: str
    uid: str | None = None


@dataclass(frozen=True)
class ScopedOwner:
    """One of this source's `WORKLOAD_OWNS_POD` claim contributions. `workload` is `None` when
    the named Workload is not current."""

    workload_id: str
    workload: CapturedWorkload | None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopedPod:
    """One of this source's captured Pod contributions, with its owners in this source."""

    pod_id: str
    name: str
    namespace: str
    cluster_uid: str
    captured_uid: str
    owners: tuple[ScopedOwner, ...] = ()
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceInventory:
    """What one source contributes to the evaluation: its capture and the Pods it captured whose
    UIDs occur among the candidates (the repository reads nothing else)."""

    capture: SourceCapture
    pods: tuple[ScopedPod, ...] = ()


# --- Results -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class PairResult:
    """One (candidate, source) evaluation. `phase` is the terminating phase (4 when all pass)."""

    source: SourceCapture
    admission: tuple[AdmissionBasis, ...]
    phase: int
    disposition: LocalityDisposition
    reasons: tuple[str, ...]
    limitations: tuple[ScopedLimitation, ...] = ()
    workload: CapturedWorkload | None = None
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateResult:
    """The candidate summary plus every pair, unchanged (D4, D13.5). `supporting_sources` are the
    `(source_instance_id, revision)` of every pair that supports an `APPLICABLE` summary."""

    record: ScopedObservedCall
    disposition: LocalityDisposition
    reasons: tuple[str, ...]
    limitations: tuple[ScopedLimitation, ...]
    workload: CapturedWorkload | None
    supporting_sources: tuple[tuple[str, str], ...]
    pairs: tuple[PairResult, ...]


@dataclass(frozen=True)
class ApplicabilityResult:
    """One page of evaluated candidates, in ascending v2 `id` order. `truncated` means more
    candidates follow `next_after_id`. `refusal` is set, with no candidates, when phase 1
    terminated the request."""

    candidates: tuple[CandidateResult, ...]
    truncated: bool
    next_after_id: str | None
    refusal: RequestRefusal | None = None


# --- Selection ---------------------------------------------------------------------------------


def select_sources(
    record: ScopedObservedCall,
    sources: Iterable[SourceInventory],
    selector: SourceSelector | None,
) -> list[tuple[SourceInventory, tuple[AdmissionBasis, ...]]]:
    """D4/D13.3. Explicit: exactly the named committed `(source, revision)`, or nothing when it is
    absent or stale. Implicit: rule 1 or rule 2; every other source is omitted. Sorted by
    `(source, scope, revision)`."""
    ordered = sorted(sources, key=lambda inventory: inventory.capture.sort_key)
    if selector is not None:
        return [
            (inventory, (AdmissionBasis.EXPLICIT,))
            for inventory in ordered
            if inventory.capture.source_instance_id == selector.source_instance_id
            and inventory.capture.revision == selector.revision
        ]
    selected = []
    for inventory in ordered:
        bases = []
        if any(pod.captured_uid == record.caller_pod_uid for pod in inventory.pods):
            bases.append(AdmissionBasis.POD_UID)
        if (
            inventory.capture.cluster_uid == record.caller_cluster_uid
            and record.k8s_namespace_name is not None
            and record.k8s_namespace_name in inventory.capture.namespaces
        ):
            bases.append(AdmissionBasis.CLUSTER_NAMESPACE)
        if bases:
            selected.append((inventory, tuple(bases)))
    return selected


# --- Per-pair phases 2-4 -----------------------------------------------------------------------


def _primary(reasons: set[str]) -> LocalityDisposition:
    dispositions = {_REASON_DISPOSITION[reason] for reason in reasons}
    return next(d for d in DISPOSITION_PRECEDENCE if d in dispositions)


def _workload_attributes_conflict(record: ScopedObservedCall, workload: CapturedWorkload) -> bool:
    """Path C's kind/name rule (v0.5 I3 §9.6): a present Workload-name attribute of another kind
    than the resolved one, or with another name, contradicts the capture."""
    resolved_kind = WORKLOAD_KIND_BY_RAW[workload.kind]
    for kind, attr_name in WORKLOAD_KIND_CONSISTENCY_ATTR.items():
        value = getattr(record, attr_name)
        if value is not None and (kind is not resolved_kind or value != workload.name):
            return True
    return False


def _phase_4(
    record: ScopedObservedCall, inventory: SourceInventory
) -> tuple[set[str], CapturedWorkload | None, tuple[str, ...]]:
    """D13.2: the Pod count gates everything; with one Pod, the identity checks and the owner step
    both run and their reasons are unioned."""
    pods = [pod for pod in inventory.pods if pod.captured_uid == record.caller_pod_uid]
    if not pods:
        return {REASON_CAPTURE_MISSING_POD}, None, ()
    if len(pods) > 1:
        refs = tuple(sorted({ref for pod in pods for ref in pod.evidence_refs}))
        return {REASON_POD_OWNER_AMBIGUOUS}, None, refs
    [pod] = pods
    refs = set(pod.evidence_refs)
    reasons: set[str] = set()
    if record.caller_cluster_uid != inventory.capture.cluster_uid:
        reasons.add(REASON_CLUSTER_UID_CONFLICT)
    if record.k8s_namespace_name is not None and record.k8s_namespace_name != pod.namespace:
        reasons.add(REASON_NAMESPACE_CONFLICT)
    if record.k8s_pod_name is not None and record.k8s_pod_name != pod.name:
        reasons.add(REASON_POD_OWNER_CONFLICT)
    if record.conflicting_consistency_attributes:
        # v2 contract §3: a flagged attribute is a known CLIENT contradiction for this Pod.
        reasons.add(REASON_POD_OWNER_CONFLICT)

    workload = None
    owners = list(pod.owners)
    refs.update(ref for owner in owners for ref in owner.evidence_refs)
    if not owners:
        reasons.add(REASON_POD_OWNER_UNRESOLVED)
    elif len(owners) > 1:
        reasons.add(REASON_POD_OWNER_AMBIGUOUS)
    else:
        [owner] = owners
        if owner.workload is None or owner.workload.kind not in WORKLOAD_KIND_BY_RAW:
            reasons.add(REASON_POD_OWNER_UNRESOLVED)
        else:
            workload = owner.workload
            if _workload_attributes_conflict(record, workload):
                reasons.add(REASON_POD_OWNER_CONFLICT)
    return reasons, (workload if not reasons else None), tuple(sorted(refs))


def evaluate_pair(
    record: ScopedObservedCall,
    inventory: SourceInventory,
    admission: tuple[AdmissionBasis, ...],
    *,
    environment: str,
    window: ScopedDayWindowV1,
) -> PairResult:
    """Phases 2-4 of I1 §10.1 for one pair; the first phase with a cause terminates."""
    capture = inventory.capture

    def result(phase: int, disposition: LocalityDisposition, reasons: set[str], **kwargs):
        return PairResult(
            source=capture,
            admission=admission,
            phase=phase,
            disposition=disposition,
            reasons=tuple(sorted(reasons)),
            **kwargs,
        )

    # Phase 2: only a CAPTURED_RESOURCE contribution can support observed caller locality.
    if capture.evidence_mode != CAPTURED_RESOURCE:
        reasons = {REASON_CAPTURE_MODE_UNSUPPORTED}
        return result(2, LocalityDisposition.UNSUPPORTED, reasons)

    # Phase 3: exact environment, the v2 bucket's last_seen and the capture's real capturedAt.
    reasons = set()
    if not window.contains(record.last_seen):
        reasons.add(REASON_OBSERVATION_TEMPORAL_MISMATCH)
    captured_at = _parse_rfc3339(capture.captured_at)
    if captured_at is None:
        reasons.add(REASON_CAPTURE_TIMESTAMP_MISSING)
    elif not window.contains(captured_at):
        reasons.add(REASON_CAPTURE_TEMPORAL_MISMATCH)
    if record.environment != environment:
        # D13.4: I1 names no LOCALITY_* code for it; it is INAPPLICABLE, which outranks every
        # other phase-3 disposition.
        return result(
            3,
            LocalityDisposition.INAPPLICABLE,
            reasons,
            limitations=(ScopedLimitation.REQUEST_ENVIRONMENT_MISMATCH,),
        )
    if reasons:
        return result(3, _primary(reasons), reasons)

    # Phase 4: the source's own captured Pod and owner chain.
    reasons, workload, refs = _phase_4(record, inventory)
    disposition = _primary(reasons) if reasons else LocalityDisposition.APPLICABLE
    return result(4, disposition, reasons, workload=workload, evidence_refs=refs)


# --- Roll-up -----------------------------------------------------------------------------------


def _union(pairs: Iterable[PairResult]) -> tuple[str, ...]:
    return tuple(sorted({reason for pair in pairs for reason in pair.reasons}))


def roll_up(record: ScopedObservedCall, pairs: Sequence[PairResult]) -> CandidateResult:
    """D4 and D13.5, applied after the independent per-pair gates."""

    def summary(
        disposition: LocalityDisposition,
        reasons: Iterable[str] = (),
        limitations: Iterable[ScopedLimitation] = (),
        workload: CapturedWorkload | None = None,
        supporting: Iterable[tuple[str, str]] = (),
    ) -> CandidateResult:
        return CandidateResult(
            record=record,
            disposition=disposition,
            reasons=tuple(sorted(set(reasons))),
            limitations=tuple(sorted(set(limitations))),
            workload=workload,
            supporting_sources=tuple(sorted(set(supporting))),
            pairs=tuple(pairs),
        )

    if not pairs:
        return summary(
            LocalityDisposition.INSUFFICIENT_EVIDENCE,
            [REASON_LOCAL_COVERAGE_UNAVAILABLE],
            [ScopedLimitation.NO_SELECTABLE_COVERING_SOURCE],
        )

    applicable = [pair for pair in pairs if pair.disposition is LocalityDisposition.APPLICABLE]
    # D4: only exactly identical Workload identities deduplicate. The logical `workload_id` omits
    # the captured UID, so two incarnations of one logical Workload are distinct here (D14.1).
    workloads = {pair.workload for pair in applicable if pair.workload}
    conflicting = [pair for pair in pairs if pair.disposition is LocalityDisposition.CONFLICT]
    if conflicting or len(workloads) > 1:
        reasons = set(_union(conflicting))
        if len(workloads) > 1:
            reasons.add(REASON_POD_OWNER_CONFLICT)
        return summary(LocalityDisposition.CONFLICT, reasons)

    ambiguous = [pair for pair in pairs if pair.disposition is LocalityDisposition.AMBIGUOUS]
    if ambiguous:
        return summary(LocalityDisposition.AMBIGUOUS, _union(ambiguous))

    if applicable:
        [workload] = workloads
        return summary(
            LocalityDisposition.APPLICABLE,
            workload=workload,
            supporting=[
                (pair.source.source_instance_id, pair.source.revision) for pair in applicable
            ],
        )

    dispositions = {pair.disposition for pair in pairs}
    if len(dispositions) == 1:
        [disposition] = dispositions
        return summary(
            disposition,
            _union(pairs),
            [limitation for pair in pairs for limitation in pair.limitations],
        )
    return summary(LocalityDisposition.INSUFFICIENT_EVIDENCE)


# --- Entry point -------------------------------------------------------------------------------


def evaluate_candidates(
    request: LocalityRequest,
    records: Sequence[ScopedObservedCall],
    sources: Sequence[SourceInventory],
    *,
    truncated: bool = False,
) -> ApplicabilityResult:
    """Evaluates one candidate page (already filtered by caller Service and optional Operation
    only, D3) against the committed sources, in ascending v2 `id` order."""
    checked = preflight(request)
    if isinstance(checked, RequestRefusal):
        return ApplicabilityResult(
            candidates=(), truncated=False, next_after_id=None, refusal=checked
        )
    candidates = []
    for record in sorted(records, key=lambda r: r.id):
        pairs = [
            evaluate_pair(
                record, inventory, admission, environment=request.environment, window=checked
            )
            for inventory, admission in select_sources(record, sources, request.selector)
        ]
        candidates.append(roll_up(record, pairs))
    return ApplicabilityResult(
        candidates=tuple(candidates),
        truncated=truncated,
        next_after_id=candidates[-1].record.id if truncated and candidates else None,
    )
