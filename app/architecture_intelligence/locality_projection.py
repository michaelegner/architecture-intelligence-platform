"""v0.6.0 I3.2 - the pure projection of one fenced locality read into the 0.6 query answer
(I3 spec §6-§11; decision record D4, D5, D7-D10, D16, D17).

It is presentation only and not a second semantic engine: I2's `assess` is the only grouping and
qualification step. Applicability, roll-up and qualification arrive here already decided. This
module chooses the presented candidate prefix (D4, D17.2), maps every candidate and pair unchanged
(D10), resolves each positive Operation's provider with the v0.5 owner rule (D8), applies the
`caller_localities`/`provider_service_id` filters (D10, D16.4), derives the selected-scope status and
comparison (D10), and maps the result to the envelope outcome and limitations (D9). It reads nothing:
the caller hands it one fenced read.
"""

import dataclasses
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.architecture_intelligence.canonical_json import canonical_digest
from app.architecture_intelligence.contracts import Outcome, Producer, SnapshotRef
from app.architecture_intelligence.dependency_projection import group_evidenced_rows
from app.architecture_intelligence.evidence_projection import project_evidence
from app.architecture_intelligence.local_assessment import (
    CandidateLimitation,
    LocalAssessmentResult,
    QualifiedLocalEvidenceAssessment,
    assess,
)
from app.architecture_intelligence.locality_contracts import (
    CAPTURE_SOURCE_BOUND,
    LOCALITY_SCHEMA_VERSION,
    LOCALITY_TOOL_NAME,
    MAX_LOCALITIES_PER_PAGE,
    MAX_MEMBERSHIPS_PER_PAGE,
    PAIR_BOUND,
    V2_EVIDENCE_ID_PATTERN,
    AdmissionBasis,
    CandidateEntry,
    CandidateLimitationCode,
    CapturedWorkloadKind,
    CapturedWorkloadRef,
    ComparedMembership,
    Comparison,
    ComparisonCompleteness,
    ComparisonSide,
    Completeness,
    EvaluatedSource,
    EvidenceEntry,
    EvidenceRefKind,
    EvidenceRefStatus,
    Inventory,
    InventoryBounds,
    LocalDisposition,
    LocalityAnswer,
    LocalityCursor,
    LocalityEntry,
    LocalityEvidenceRequest,
    LocalityLimitation,
    LocalityLimitationCode,
    LocalityMode,
    LocalityQueryRequest,
    LocalityRequestContext,
    LocalityWorkload,
    LocalObservation,
    LocalQualification,
    OperationAssessment,
    PairEntry,
    PairSourceRef,
    PresentationCap,
    ProviderGroup,
    ProviderOwnerReason,
    RuleRef,
    ScopedLocalityEvidenceData,
    ScopedV2Record,
    ScopeEvaluation,
    SelectedCaptureRef,
    SelectedScope,
    SelectionMode,
    ServiceDependenciesByLocalityData,
    SharedMembership,
    SourceLimitation,
    UnresolvedOwnerOperation,
    WorkloadIdentity,
    candidate_page_size,
    encode_cursor,
    workload_identity_key,
)
from app.architecture_intelligence.scoped_applicability import (
    ApplicabilityResult,
    CapturedWorkload,
    LocalityRequest,
    PairResult,
    SourceSelector,
)
from app.architecture_intelligence.scoped_evidence_repository import (
    ProviderOwnerRows,
    ScopedApplicabilityRead,
    ScopedEvidenceRows,
)
from app.provenance.model import ScopedObservedCall

_IdentityKey = tuple[str, str, str, str]
# A comparison membership: (provider Service id, or "" for an unresolved owner; Operation id).
_MembershipKey = tuple[str, str]

_MESSAGES = {
    LocalityLimitationCode.UNSUPPORTED_REQUEST: (
        "The request asks for a relation, dimension or temporal resolution that the locality "
        "answer does not support."
    ),
    LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE: (
        "The requested snapshot is not the current one, or no consistent snapshot could be read; "
        "no answer is given for a stale or unstable snapshot."
    ),
    LocalityLimitationCode.CURSOR_QUERY_MISMATCH: (
        "The cursor belongs to a different query; a cursor continues only the query that issued it."
    ),
    LocalityLimitationCode.INVENTORY_INCOMPLETE: (
        "This page does not cover the whole evaluated inventory. Groups on it are provisional, "
        "and a missing item is unknown, not absent."
    ),
    LocalityLimitationCode.COMPARISON_INCOMPLETE: (
        "The comparison is not established on a complete evaluated inventory for both Workloads; "
        "a relation listed for one Workload is not evidence of its absence in the other."
    ),
    LocalityLimitationCode.SELECTION_NOT_ESTABLISHED: (
        "At least one requested Workload identity is not established by the evaluated inventory; "
        "its status is UNKNOWN."
    ),
    LocalityLimitationCode.PROVIDER_OWNER_UNRESOLVED: (
        "At least one positively assessed Operation has no unique evidenced provider Service, so "
        "no provider dependency is stated for it."
    ),
    LocalityLimitationCode.INSUFFICIENT_EVIDENCE: (
        "No caller-Workload-local dependency is positively established for this request. This is "
        "not evidence that no dependency exists."
    ),
}


def limitation(
    code: LocalityLimitationCode, *, reasons: Sequence[str] = (), message: str | None = None
) -> LocalityLimitation:
    """A stable, sanitized message per code; only D6's carries a count (`result_limit_message`)."""
    return LocalityLimitation(
        code=code, message=message or _MESSAGES[code], reasons=sorted(set(reasons))
    )


def internal_request(request: LocalityQueryRequest) -> LocalityRequest:
    """The I2 request for a 0.6 query request; values pass through unchanged (D3)."""
    selector = request.source_selector
    return LocalityRequest(
        subject_service_id=request.subject_service_id,
        environment=request.environment,
        first_day=request.first_day,
        last_day=request.last_day,
        object_operation_id=request.object_operation_id,
        relation_type=request.relation_type,
        dimensions=frozenset(request.dimensions),
        selector=(
            SourceSelector(selector.source_instance_id, selector.revision)
            if selector is not None
            else None
        ),
    )


def query_digest(request: LocalityQueryRequest) -> str:
    """D5: the normalized request without `cursor` and `snapshot_id`."""
    return canonical_digest(request.model_dump(mode="json", exclude={"cursor", "snapshot_id"}))


def refusal_answer(
    producer: Producer,
    snapshot: SnapshotRef | None,
    code: LocalityLimitationCode,
    *,
    reasons: Sequence[str] = (),
    message: str | None = None,
    mode: LocalityMode = "query",
) -> LocalityAnswer:
    """D9: a refusal evaluated nothing, so `data` is null and it carries exactly one code."""
    return LocalityAnswer(
        schema_version=LOCALITY_SCHEMA_VERSION,
        producer=producer,
        tool=LOCALITY_TOOL_NAME,
        mode=mode,
        outcome=Outcome.NOT_ANSWERED,
        snapshot=snapshot,
        data=None,
        limitations=[limitation(code, reasons=reasons, message=message)],
    )


def result_limit_message(considered_sources: int) -> str:
    """D6: the message states `S` and the bound, and how a client may narrow the request."""
    return (
        f"The request would consider {considered_sources} accepted capture sources, more than the "
        f"bound of {CAPTURE_SOURCE_BOUND}; it cannot be answered with the current capture "
        "inventory. Narrow it with an explicit source_selector."
    )


# --- Mapping I2 values unchanged ---------------------------------------------------------------


def _workload_ref(workload: CapturedWorkload | None) -> CapturedWorkloadRef | None:
    if workload is None:
        return None
    return CapturedWorkloadRef(
        workload_id=workload.workload_id,
        name=workload.name,
        cluster_uid=workload.cluster_uid,
        namespace=workload.namespace,
        kind=CapturedWorkloadKind(workload.kind),
        uid=workload.uid,
    )


def _pair(pair: PairResult) -> PairEntry:
    return PairEntry(
        source=PairSourceRef(
            source_instance_id=pair.source.source_instance_id, revision=pair.source.revision
        ),
        admission=sorted({AdmissionBasis(basis.value) for basis in pair.admission}),
        phase=pair.phase,  # pyright: ignore[reportArgumentType]
        disposition=LocalDisposition(pair.disposition.value),
        reasons=sorted(set(pair.reasons)),
        limitations=sorted({CandidateLimitationCode(code.value) for code in pair.limitations}),
        workload=_workload_ref(pair.workload),
        evidence_refs=sorted(set(pair.evidence_refs)),
    )


def _pairs(pairs: Sequence[PairResult]) -> list[PairEntry]:
    return sorted(
        (_pair(pair) for pair in pairs),
        key=lambda entry: (entry.source.source_instance_id, entry.source.revision),
    )


def _candidates(
    result: ApplicabilityResult, assessed: LocalAssessmentResult
) -> list[CandidateEntry]:
    """Every presented candidate (D10). A candidate that supports no assertion carries I2's own
    `CandidateLimitation` (which may add `WORKLOAD_UID_UNAVAILABLE`, D14.1); a contributing one
    carries its I2.3 summary."""
    limitations: dict[str, CandidateLimitation] = {
        item.v2_evidence_id: item for item in assessed.candidate_limitations
    }
    entries = []
    for candidate in result.candidates:
        negative = limitations.get(candidate.record.id)
        codes = negative.limitations if negative is not None else candidate.limitations
        entries.append(
            CandidateEntry(
                v2_evidence_id=candidate.record.id,
                disposition=LocalDisposition(candidate.disposition.value),
                reasons=sorted(set(candidate.reasons)),
                limitations=sorted({CandidateLimitationCode(str(code)) for code in codes}),
                workload=_workload_ref(candidate.workload),
                pairs=_pairs(candidate.pairs),
            )
        )
    return entries


def _assessment(
    item: QualifiedLocalEvidenceAssessment, *, lineage_complete: bool
) -> OperationAssessment:
    """D16.3: the I2 assessment's own values. Only `lineage_complete` may be lowered, on a
    continuation page (D17.3)."""
    return OperationAssessment(
        assertion_id=item.assertion_id,
        assessment_id=item.assessment_id,
        object_operation_id=item.object_operation_id,
        applicability="APPLICABLE",
        qualification=LocalQualification(item.qualification),
        observation=LocalObservation(
            evidence_ids=sorted(set(item.observation.evidence_ids)),
            first_seen=item.observation.first_seen,
            last_seen=item.observation.last_seen,
            lineage_complete=item.observation.lineage_complete and lineage_complete,
        ),
        declared_evidence_ids=sorted(set(item.declared_evidence_ids)),
        selected_captures=[
            SelectedCaptureRef(
                source_instance_id=capture.source_instance_id,
                revision=capture.revision,
                evidence_mode=capture.evidence_mode,
                captured_at=capture.captured_at,
            )
            for capture in sorted(
                item.selected_captures, key=lambda c: (c.source_instance_id, c.revision)
            )
        ],
        capture_evidence_refs=sorted(set(item.capture_evidence_refs)),
        source_limitations=sorted(
            (
                SourceLimitation(v2_evidence_id=v2_id, pair=_pair(pair))
                for v2_id, pair in item.source_limitations
            ),
            key=lambda entry: (
                entry.v2_evidence_id,
                entry.pair.source.source_instance_id,
                entry.pair.source.revision,
            ),
        ),
        rules=[RuleRef(id=rule, version=version) for rule, version in sorted(set(item.rules))],
    )


# --- Provider owners (D8) and localities (D10, D16.4) -------------------------------------------


@dataclass(frozen=True)
class _Owner:
    provider_service_id: str | None
    reason: ProviderOwnerReason | None


def _owners(owners: ProviderOwnerRows, operation_ids: set[str]) -> dict[str, _Owner]:
    """D8: the v0.5 owner rule. Exactly one provider with accepted evidence resolves the owner;
    zero is `PROVIDER_OWNER_MISSING`, two or more `PROVIDER_OWNER_AMBIGUOUS`."""
    rows: dict[str, list[dict]] = defaultdict(list)
    for row in owners.provides:
        rows[row["operation_id"]].append(row)
    resolved = {}
    for operation_id in operation_ids:
        evidenced = group_evidenced_rows(
            rows[operation_id], "provider_id", "provider_name", owners.evidence_rows
        )
        if len(evidenced) == 1:
            [provider_id] = evidenced
            resolved[operation_id] = _Owner(provider_id, None)
        elif not evidenced:
            resolved[operation_id] = _Owner(None, ProviderOwnerReason.PROVIDER_OWNER_MISSING)
        else:
            resolved[operation_id] = _Owner(None, ProviderOwnerReason.PROVIDER_OWNER_AMBIGUOUS)
    return resolved


def _identity(workload: CapturedWorkload) -> _IdentityKey:
    assert workload.uid is not None  # every assertion's Workload has a captured UID (D14.1)
    return (workload.cluster_uid, workload.namespace, workload.kind, workload.uid)


def _localities(
    request: LocalityQueryRequest,
    assessed: LocalAssessmentResult,
    owners: dict[str, _Owner],
    *,
    lineage_complete: bool,
) -> list[LocalityEntry]:
    """One entry per positive Workload, after the `caller_localities` filter (D10) and the
    `provider_service_id` filter (D16.4); a Workload left with no Operation is not listed."""
    selected = (
        {workload_identity_key(item) for item in request.caller_localities}
        if request.caller_localities is not None
        else None
    )
    by_workload: dict[_IdentityKey, list[QualifiedLocalEvidenceAssessment]] = defaultdict(list)
    for item in assessed.assertions:
        by_workload[_identity(item.caller_workload)].append(item)

    entries = []
    for key in sorted(by_workload):
        if selected is not None and key not in selected:
            continue
        items = [
            item
            for item in by_workload[key]
            if request.provider_service_id is None
            or owners[item.object_operation_id].provider_service_id
            in (
                None,
                request.provider_service_id,
            )
        ]
        if not items:
            continue
        assessments = sorted(
            (_assessment(item, lineage_complete=lineage_complete) for item in items),
            key=lambda entry: entry.assertion_id,
        )
        groups: dict[str, list[OperationAssessment]] = defaultdict(list)
        unresolved: dict[str, ProviderOwnerReason] = {}
        for entry in assessments:
            owner = owners[entry.object_operation_id]
            if owner.provider_service_id is not None:
                groups[owner.provider_service_id].append(entry)
            else:
                assert owner.reason is not None
                unresolved[entry.object_operation_id] = owner.reason
        # Every assertion of one Workload has the same Workload; the representative's
        # presentation fields come from I2's own deterministic choice.
        workload = min(
            (item.caller_workload for item in items), key=lambda w: (w.workload_id, w.name)
        )
        assert workload.uid is not None
        entries.append(
            LocalityEntry(
                workload=LocalityWorkload(
                    workload_id=workload.workload_id,
                    name=workload.name,
                    cluster_uid=workload.cluster_uid,
                    namespace=workload.namespace,
                    kind=CapturedWorkloadKind(workload.kind),
                    uid=workload.uid,
                ),
                assessments=assessments,
                provider_groups=[
                    ProviderGroup(
                        provider_service_id=provider,
                        operation_ids=sorted({m.object_operation_id for m in members}),
                        member_qualifications=sorted({m.qualification for m in members}),
                        evidence_refs=sorted(set().union(*(m.evidence_union() for m in members))),
                    )
                    for provider, members in sorted(groups.items())
                ],
                unresolved_owner_operations=[
                    UnresolvedOwnerOperation(operation_id=operation, reason=reason)
                    for operation, reason in sorted(unresolved.items())
                ],
                target_runtime_scope="UNKNOWN",
                lineage_complete=lineage_complete,
            )
        )
    return entries


# --- Selection and comparison (D10, D16.10) ----------------------------------------------------


def _evaluate(
    identity: WorkloadIdentity,
    localities: Sequence[LocalityEntry],
    candidates: Sequence[CandidateEntry],
    *,
    complete: bool,
) -> ScopeEvaluation:
    key = workload_identity_key(identity)
    if any(workload_identity_key(item.workload.identity()) == key for item in localities):
        return ScopeEvaluation.POSITIVE
    if not complete:
        return ScopeEvaluation.UNKNOWN
    for candidate in candidates:
        for pair in candidate.pairs:
            resolved = pair.workload.identity() if pair.workload is not None else None
            if (
                pair.disposition is LocalDisposition.APPLICABLE
                and resolved is not None
                and workload_identity_key(resolved) == key
            ):
                return ScopeEvaluation.EVALUATED_NO_POSITIVE
    return ScopeEvaluation.UNKNOWN


def _memberships(
    identity: WorkloadIdentity, localities: Sequence[LocalityEntry]
) -> dict[_MembershipKey, ComparisonSide]:
    key = workload_identity_key(identity)
    for locality in localities:
        if workload_identity_key(locality.workload.identity()) != key:
            continue
        provider_of = {
            operation: group.provider_service_id
            for group in locality.provider_groups
            for operation in group.operation_ids
        }
        return {
            (provider_of.get(item.object_operation_id, ""), item.object_operation_id): (
                ComparisonSide(
                    qualification=item.qualification,
                    assertion_id=item.assertion_id,
                    assessment_id=item.assessment_id,
                )
            )
            for item in locality.assessments
        }
    return {}


def _comparison(
    compare: Sequence[WorkloadIdentity],
    localities: Sequence[LocalityEntry],
    candidates: Sequence[CandidateEntry],
    *,
    complete: bool,
) -> Comparison:
    first_id, second_id = compare
    scopes = [
        SelectedScope(
            workload=identity,
            evaluation=_evaluate(identity, localities, candidates, complete=complete),
        )
        for identity in compare
    ]
    first, second = _memberships(first_id, localities), _memberships(second_id, localities)
    in_both = [
        SharedMembership(
            provider_service_id=key[0] or None,
            operation_id=key[1],
            first=first[key],
            second=second[key],
        )
        for key in sorted(first.keys() & second.keys())
    ]

    def only(mine: dict[_MembershipKey, ComparisonSide], other: dict) -> list[ComparedMembership]:
        return [
            ComparedMembership(provider_service_id=key[0] or None, operation_id=key[1], side=side)
            for key, side in sorted(mine.items())
            if key not in other
        ]

    unknown = any(scope.evaluation is ScopeEvaluation.UNKNOWN for scope in scopes)
    return Comparison(
        scopes=scopes,
        in_both=in_both,
        only_in_first=only(first, second),
        only_in_second=only(second, first),
        qualification_differs=[
            item for item in in_both if item.first.qualification != item.second.qualification
        ],
        completeness=(
            ComparisonCompleteness.PARTIAL
            if not complete
            else ComparisonCompleteness.NOT_ESTABLISHED
            if unknown
            else ComparisonCompleteness.COMPLETE
        ),
    )


# --- The presented prefix (D4, D17.2) ----------------------------------------------------------


@dataclass(frozen=True)
class _Presented:
    count: int
    assessed: LocalAssessmentResult
    owners: dict[str, _Owner]
    localities: list[LocalityEntry]


def _present(
    request: LocalityQueryRequest,
    read: ScopedApplicabilityRead,
    owner_rows: ProviderOwnerRows,
    count: int,
) -> _Presented:
    """I2's pure `assess` over the first `count` candidates of the same fenced read (D4). A
    shorter prefix is a truncated page that continues after its last candidate."""
    result = read.result
    if count < len(result.candidates):
        prefix = result.candidates[:count]
        result = ApplicabilityResult(
            candidates=prefix,
            truncated=True,
            next_after_id=prefix[-1].record.id if prefix else None,
        )
    sub_read = dataclasses.replace(read, result=result)
    assessed = assess(sub_read, internal_request(request))
    owners = _owners(owner_rows, {item.object_operation_id for item in assessed.assertions})
    localities = _localities(request, assessed, owners, lineage_complete=not result.truncated)
    return _Presented(count, assessed, owners, localities)


def _exceeded(presented: _Presented) -> list[PresentationCap]:
    caps = []
    if len(presented.localities) > MAX_LOCALITIES_PER_PAGE:
        caps.append(PresentationCap.WORKLOADS)
    if sum(len(item.assessments) for item in presented.localities) > MAX_MEMBERSHIPS_PER_PAGE:
        caps.append(PresentationCap.MEMBERSHIPS)
    return sorted(caps)


def _longest_prefix(
    request: LocalityQueryRequest, read: ScopedApplicabilityRead, owners: ProviderOwnerRows
) -> tuple[_Presented, list[PresentationCap]]:
    """D4/D17.2: the longest prefix of complete candidates whose presented projection stays within
    the caps, and the caps the next candidate would exceed. The presented counts never shrink as
    the prefix grows (`assess` is monotone), so a binary search finds it."""
    total = len(read.result.candidates)
    full = _present(request, read, owners, total)
    if not _exceeded(full):
        return full, []
    # One candidate adds at most one assertion, so a one-candidate prefix always fits.
    low, high = 1, total - 1  # invariant: prefix `low` fits, prefix `high + 1` does not
    if _exceeded(_present(request, read, owners, low)):
        raise AssertionError("a single candidate cannot exceed the presentation caps")
    while low < high:
        middle = (low + high + 1) // 2
        if _exceeded(_present(request, read, owners, middle)):
            high = middle - 1
        else:
            low = middle
    return _present(request, read, owners, low), _exceeded(_present(request, read, owners, low + 1))


# --- The answer ---------------------------------------------------------------------------------


def project_locality_answer(
    request: LocalityQueryRequest,
    read: ScopedApplicabilityRead,
    owner_rows: ProviderOwnerRows,
    *,
    considered_sources: int,
    producer: Producer,
) -> LocalityAnswer:
    """The evaluated query answer of one fenced read (D9 rows "evaluated")."""
    presented, caps = _longest_prefix(request, read, owner_rows)
    i2_truncated = read.result.truncated
    continuation = request.cursor is not None
    complete = not (i2_truncated or caps or continuation)

    next_after_id = presented.assessed.next_after_id if caps else read.result.next_after_id
    next_cursor = None
    if i2_truncated or caps:
        assert next_after_id is not None
        next_cursor = encode_cursor(
            LocalityCursor(
                v=1,
                after_id=next_after_id,
                query_digest=query_digest(request),
                snapshot_id=read.snapshot_id,
                schema_version=LOCALITY_SCHEMA_VERSION,
            )
        )

    presented_result = dataclasses.replace(
        read.result, candidates=read.result.candidates[: presented.count]
    )
    candidates = _candidates(presented_result, presented.assessed)
    localities = (
        presented.localities
        if complete
        else _localities(request, presented.assessed, presented.owners, lineage_complete=False)
    )
    pairs = [pair for candidate in candidates for pair in candidate.pairs]
    # D10/D16.6: exactly the sources of the listed pairs.
    captures = {
        (pair.source.source_instance_id, pair.source.revision): pair.source
        for candidate in presented_result.candidates
        for pair in candidate.pairs
    }

    selection = (
        [
            SelectedScope(
                workload=identity,
                evaluation=_evaluate(identity, localities, candidates, complete=complete),
            )
            for identity in request.caller_localities
        ]
        if request.caller_localities is not None
        else None
    )
    comparison = (
        _comparison(request.compare, localities, candidates, complete=complete)
        if request.compare is not None
        else None
    )

    data = ServiceDependenciesByLocalityData(
        request_context=LocalityRequestContext(
            subject_service_id=request.subject_service_id,
            environment=request.environment,
            first_day=request.first_day,
            last_day=request.last_day,
            relation_type="CALLS",
            dimensions=list(request.dimensions),  # pyright: ignore[reportArgumentType]
            object_operation_id=request.object_operation_id,
            provider_service_id=request.provider_service_id,
            source_selector=request.source_selector,
            caller_localities=request.caller_localities,
            compare=request.compare,
            selection_mode=(
                SelectionMode.EXPLICIT_SOURCE
                if request.source_selector is not None
                else SelectionMode.IMPLICIT_COVERING_SOURCES
            ),
        ),
        coverage="LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE",
        inventory=Inventory(
            considered_capture_source_count=considered_sources,
            evaluated_v2_candidate_count=len(candidates),
            admitted_pair_count=len(pairs),
            evaluated_sources=[
                EvaluatedSource(
                    source_instance_id=capture.source_instance_id,
                    revision=capture.revision,
                    cluster_uid=capture.cluster_uid,
                    namespaces=sorted(set(capture.namespaces)),
                    evidence_mode=capture.evidence_mode,
                    captured_at=capture.captured_at,
                )
                for _key, capture in sorted(captures.items())
            ],
            bounds=InventoryBounds(
                pair_bound=PAIR_BOUND,
                capture_source_bound=CAPTURE_SOURCE_BOUND,
                candidate_page_size=candidate_page_size(considered_sources),
                max_localities=MAX_LOCALITIES_PER_PAGE,
                max_memberships=MAX_MEMBERSHIPS_PER_PAGE,
            ),
            i2_truncated=i2_truncated,
            continuation=continuation,
            cap_reached=caps,
            next_cursor=next_cursor,
            completeness=Completeness.COMPLETE if complete else Completeness.PARTIAL,
        ),
        candidates=candidates,
        localities=localities,
        selection=selection,
        comparison=comparison,
    )

    codes = _limitation_codes(data, complete=complete)
    return LocalityAnswer(
        schema_version=LOCALITY_SCHEMA_VERSION,
        producer=producer,
        tool=LOCALITY_TOOL_NAME,
        mode="query",
        outcome=(
            Outcome.NOT_ANSWERED
            if LocalityLimitationCode.INSUFFICIENT_EVIDENCE in codes
            else Outcome.PARTIAL
            if codes
            else Outcome.ANSWERED
        ),
        snapshot=SnapshotRef(snapshot_id=read.snapshot_id, model_revision=read.model_revision),
        data=data,
        limitations=[limitation(code) for code in sorted(codes)],
    )


def _limitation_codes(
    data: ServiceDependenciesByLocalityData, *, complete: bool
) -> set[LocalityLimitationCode]:
    """D9 for an evaluated answer."""
    codes: set[LocalityLimitationCode] = set()
    if not complete:
        codes.add(LocalityLimitationCode.INVENTORY_INCOMPLETE)
    comparison = data.comparison
    if comparison is not None and comparison.completeness is not ComparisonCompleteness.COMPLETE:
        codes.add(LocalityLimitationCode.COMPARISON_INCOMPLETE)
    scopes = [*(data.selection or ()), *(comparison.scopes if comparison is not None else ())]
    if any(scope.evaluation is ScopeEvaluation.UNKNOWN for scope in scopes):
        codes.add(LocalityLimitationCode.SELECTION_NOT_ESTABLISHED)
    if any(locality.unresolved_owner_operations for locality in data.localities):
        codes.add(LocalityLimitationCode.PROVIDER_OWNER_UNRESOLVED)
    if complete and not data.localities:
        codes.add(LocalityLimitationCode.INSUFFICIENT_EVIDENCE)
    return codes


# --- The scoped resolver (D11, D16.1, D16.7) ---------------------------------------------------

_V2_REF = re.compile(V2_EVIDENCE_ID_PATTERN)
_EVIDENCE_MESSAGE = (
    "At least one requested ref did not resolve for this caller at this snapshot. An unresolved "
    "ref is not described further."
)


def is_v2_ref(ref: str) -> bool:
    """D11/D16.7: a ref matching the v2 id pattern can only resolve as `SCOPED_V2`."""
    return _V2_REF.fullmatch(ref) is not None


def _scoped_record(record: ScopedObservedCall) -> ScopedV2Record:
    """D11: exactly the admitted public fields; never a Resource, host, IP or Workload."""
    return ScopedV2Record(
        id=record.id,
        subject_id=record.subject_id,
        object_id=record.object_id,
        environment=record.environment,
        bucket_utc_day=record.bucket_utc_day,
        caller_cluster_uid=record.caller_cluster_uid,
        caller_pod_uid=record.caller_pod_uid,
        first_seen=record.first_seen,
        last_seen=record.last_seen,
        observation_count=record.observation_count,
        correlation_mode=record.correlation_mode,  # pyright: ignore[reportArgumentType]
        sample_trace_ids=sorted(set(record.sample_trace_ids)),
        key_rule_id=record.key_rule_id,  # pyright: ignore[reportArgumentType]
        key_rule_version=record.key_rule_version,  # pyright: ignore[reportArgumentType]
        normalization_rule_id=record.normalization_rule_id,  # pyright: ignore[reportArgumentType]
        normalization_rule_version=record.normalization_rule_version,  # pyright: ignore[reportArgumentType]
    )


def _not_found(ref: str) -> EvidenceEntry:
    return EvidenceEntry(
        ref=ref,
        status=EvidenceRefStatus.NOT_FOUND,
        ref_kind=None,
        scoped_record=None,
        capture_record=None,
    )


def project_scoped_evidence(
    request: LocalityEvidenceRequest,
    rows: ScopedEvidenceRows,
    *,
    snapshot: SnapshotRef,
    producer: Producer,
) -> LocalityAnswer:
    """The evaluated `mode: "evidence"` answer (D11). A ref that fails its rule is `NOT_FOUND`
    with no detail. The outcome follows D16.1: `ANSWERED` if every ref resolved, `PARTIAL` if
    some did, `NOT_ANSWERED` if none did, the last two with `INSUFFICIENT_EVIDENCE`."""
    authorized = sorted(rows.pod_refs | rows.owner_refs)
    records = {
        record.id: record
        for record in project_evidence(rows.evidence_rows, requested_ids=authorized).records
        if record.source_type.value == "KUBERNETES"
    }
    entries = []
    for ref in request.refs:
        if is_v2_ref(ref):
            record = rows.v2.get(ref)
            entries.append(
                EvidenceEntry(
                    ref=ref,
                    status=EvidenceRefStatus.RESOLVED,
                    ref_kind=EvidenceRefKind.SCOPED_V2,
                    scoped_record=_scoped_record(record),
                    capture_record=None,
                )
                if record is not None
                else _not_found(ref)
            )
        elif ref in records:
            entries.append(
                EvidenceEntry(
                    ref=ref,
                    status=EvidenceRefStatus.RESOLVED,
                    ref_kind=(
                        EvidenceRefKind.POD_CAPTURE
                        if ref in rows.pod_refs
                        else EvidenceRefKind.OWNER_CAPTURE
                    ),
                    scoped_record=None,
                    capture_record=records[ref],
                )
            )
        else:
            entries.append(_not_found(ref))

    resolved = sum(entry.status is EvidenceRefStatus.RESOLVED for entry in entries)
    complete = resolved == len(entries)
    return LocalityAnswer(
        schema_version=LOCALITY_SCHEMA_VERSION,
        producer=producer,
        tool=LOCALITY_TOOL_NAME,
        mode="evidence",
        outcome=(
            Outcome.ANSWERED if complete else Outcome.PARTIAL if resolved else Outcome.NOT_ANSWERED
        ),
        snapshot=snapshot,
        data=ScopedLocalityEvidenceData(
            subject_service_id=request.subject_service_id,
            object_operation_id=request.object_operation_id,
            entries=entries,
        ),
        limitations=(
            []
            if complete
            else [
                limitation(LocalityLimitationCode.INSUFFICIENT_EVIDENCE, message=_EVIDENCE_MESSAGE)
            ]
        ),
    )


__all__ = [
    "internal_request",
    "is_v2_ref",
    "limitation",
    "project_locality_answer",
    "project_scoped_evidence",
    "query_digest",
    "refusal_answer",
    "result_limit_message",
]
