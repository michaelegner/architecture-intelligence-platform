"""Dedicated reader for the isolated caller-Pod-scoped v2 records (v0.6.0 I2.2a; I2 decision record
D1 and D3).

Only this module reads `:ScopedObservedCallV2`. The public evidence reads, the snapshot state and the
NL query path never see the label (I2.2b proves it). It filters by caller Service and, optionally,
one canonical Operation - and by nothing else: a request's environment, UTC day, cluster or Workload
are applicability checks (I1 §10.1 phases 3-4), not filters, so a wrong-environment or wrong-day
record must still be returned and then judged (I1 L10b, L17d).
"""

import dataclasses
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import neo4j

from app.architecture_intelligence.locality_contracts import (
    CAPTURE_SOURCE_BOUND,
    candidate_page_size,
)
from app.architecture_intelligence.repository import (
    PROVIDES_FOR_OPERATIONS_QUERY,
    SOURCE_CAPTURES_QUERY,
    read_evidence_rows,
    read_qualification_evidence_rows,
    read_stable_snapshot_from_session,
)
from app.architecture_intelligence.scoped_applicability import (
    ApplicabilityResult,
    CapturedWorkload,
    LocalityRequest,
    RequestRefusal,
    ScopedOwner,
    ScopedPod,
    SourceCapture,
    SourceInventory,
    SourceSelector,
    evaluate_candidates,
    preflight,
)
from app.provenance.model import ScopedObservedCall
from app.sources.service_workload_mapping import ServiceWorkloadMappingDocument

# D3: fixed page size; an explicit truncation flag is returned whenever a scan stops early.
DEFAULT_PAGE_SIZE = 500

_V2_FIELDS = (
    "RETURN v.id AS id, v.contract_version AS contract_version, v.source_type AS source_type, "
    "v.evidence_type AS evidence_type, v.relation_type AS relation_type, "
    "v.environment AS environment, v.bucket_utc_day AS bucket_utc_day, "
    "v.subject_id AS subject_id, v.object_id AS object_id, "
    "v.caller_cluster_uid AS caller_cluster_uid, v.caller_pod_uid AS caller_pod_uid, "
    "v.first_seen AS first_seen, v.last_seen AS last_seen, "
    "v.observation_count AS observation_count, v.correlation_mode AS correlation_mode, "
    "v.sample_trace_ids AS sample_trace_ids, "
    "v.k8s_namespace_name AS k8s_namespace_name, v.k8s_pod_name AS k8s_pod_name, "
    "v.k8s_deployment_name AS k8s_deployment_name, "
    "v.k8s_statefulset_name AS k8s_statefulset_name, "
    "v.k8s_daemonset_name AS k8s_daemonset_name, "
    "v.conflicting_consistency_attributes AS conflicting_consistency_attributes, "
    "v.key_rule_id AS key_rule_id, v.key_rule_version AS key_rule_version, "
    "v.normalization_rule_id AS normalization_rule_id, "
    "v.normalization_rule_version AS normalization_rule_version "
)
_READ_QUERY = (
    "MATCH (v:ScopedObservedCallV2) "
    "WHERE v.subject_id = $subject_id "
    "AND ($object_id IS NULL OR v.object_id = $object_id) "
    "AND ($after_id IS NULL OR v.id > $after_id) " + _V2_FIELDS + "ORDER BY v.id LIMIT $limit"
)

_DATETIME_FIELDS = ("first_seen", "last_seen")


@dataclass(frozen=True)
class ScopedCallPage:
    """One page of v2 records in ascending `id` order. `truncated` means more records follow the
    last one returned; continue with `after_id=records[-1].id`."""

    records: tuple[ScopedObservedCall, ...]
    truncated: bool


def read_scoped_observed_calls(
    runner: neo4j.Session | neo4j.ManagedTransaction,
    *,
    subject_id: str,
    object_id: str | None = None,
    after_id: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> ScopedCallPage:
    """Reads up to `limit` v2 records for one caller Service (and optionally one Operation), after
    `after_id`, in ascending `id` order. Fetches one extra row to decide `truncated` exactly.

    `limit` may not exceed the frozen page size (D3): a larger value is rejected, not silently
    capped, so a caller can never bypass the bound and always sees `truncated` for the rest."""
    if not 1 <= limit <= DEFAULT_PAGE_SIZE:
        raise ValueError(f"limit must be between 1 and {DEFAULT_PAGE_SIZE}")
    rows = list(
        runner.run(
            _READ_QUERY,
            subject_id=subject_id,
            object_id=object_id,
            after_id=after_id,
            limit=limit + 1,
        )
    )
    records = [_record(row) for row in rows[:limit]]
    return ScopedCallPage(records=tuple(records), truncated=len(rows) > limit)


def _record(row: neo4j.Record) -> ScopedObservedCall:
    data = dict(row)
    for field in _DATETIME_FIELDS:
        # neo4j.time.DateTime -> datetime.datetime, as the v1 evidence reads do.
        data[field] = data[field].to_native()
    return ScopedObservedCall(**data)


# --- I2.3b: the fenced applicability read (decision record D13.6, D13.7) -------------------------

# D13.6: each source's own captured Pod contributions for the candidates' Pod UIDs, in any cluster
# (rule 1 and L16 need the other-cluster capture). One row per (source, Pod).
_SCOPED_PODS_QUERY = (
    "MATCH (c:InfrastructureContribution) WHERE c.captured_resource_uid IN $pod_uids "
    "MATCH (e:InfrastructureEntity {id: c.entity_id}) WHERE e.entity_kind = 'KUBERNETES_POD' "
    "RETURN c.source_instance_id AS source_instance_id, e.id AS pod_id, e.name AS name, "
    "e.namespace AS namespace, e.cluster_uid AS cluster_uid, "
    "c.captured_resource_uid AS captured_uid, coalesce(c.evidence_refs, []) AS evidence_refs"
)

# D13.6: each source's own WORKLOAD_OWNS_POD view. A claim contribution's id is hashed per
# (claim, source) and written through the shared MERGE template, so its `owner_source_ids` is
# exactly that one source. The Workload's captured UID comes from the same source's contribution.
_SCOPED_OWNERS_QUERY = (
    "MATCH (claim:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD'}) "
    "WHERE claim.object_id IN $pod_ids "
    "MATCH (cc:InfrastructureClaimContribution {claim_id: claim.id}) "
    "UNWIND coalesce(cc.owner_source_ids, []) AS source_instance_id "
    "OPTIONAL MATCH (w:InfrastructureEntity {id: claim.subject_id}) "
    "WHERE w.entity_kind = 'KUBERNETES_WORKLOAD' "
    "OPTIONAL MATCH (wc:InfrastructureContribution {entity_id: claim.subject_id}) "
    "WHERE wc.source_instance_id = source_instance_id "
    "RETURN source_instance_id, claim.object_id AS pod_id, claim.subject_id AS workload_id, "
    "coalesce(cc.evidence_refs, []) AS evidence_refs, w.id AS current_workload_id, "
    "w.resource_kind AS kind, w.namespace AS namespace, w.name AS name, "
    "w.cluster_uid AS cluster_uid, wc.captured_resource_uid AS workload_uid"
)


def read_source_captures(
    runner: neo4j.Session | neo4j.ManagedTransaction,
) -> list[SourceCapture]:
    """Every accepted Kubernetes source's committed capture, without any Pod or owner (I3 D4 step
    1), sorted by `SourceCapture.sort_key`."""
    return sorted(
        (
            SourceCapture(
                source_instance_id=row["source_instance_id"],
                discovery_scope_id=row["discovery_scope_id"] or "",
                revision=row["revision"],
                cluster_uid=row["cluster_uid"],
                namespaces=tuple(sorted(row["namespaces"] or ())),
                evidence_mode=row["evidence_mode"],
                captured_at=row["captured_at"],
            )
            for row in runner.run(SOURCE_CAPTURES_QUERY)
        ),
        key=lambda capture: capture.sort_key,
    )


def read_source_inventories(
    runner: neo4j.Session | neo4j.ManagedTransaction,
    *,
    pod_uids: Sequence[str],
    captures: Sequence[SourceCapture] | None = None,
) -> list[SourceInventory]:
    """Every accepted Kubernetes source's committed capture, each with only the Pods *it*
    captured under one of `pod_uids`, and only *its* owner claims for them (D13.6). `captures`
    are read here unless the caller already read them under the same fence."""
    if captures is None:
        captures = read_source_captures(runner)
    pod_rows = list(runner.run(_SCOPED_PODS_QUERY, pod_uids=sorted(set(pod_uids))))
    owners: dict[tuple[str, str], list[ScopedOwner]] = defaultdict(list)
    for row in runner.run(_SCOPED_OWNERS_QUERY, pod_ids=sorted({r["pod_id"] for r in pod_rows})):
        workload = (
            CapturedWorkload(
                workload_id=row["current_workload_id"],
                kind=row["kind"],
                namespace=row["namespace"],
                name=row["name"],
                cluster_uid=row["cluster_uid"],
                uid=row["workload_uid"],
            )
            if row["current_workload_id"] is not None
            else None
        )
        owners[(row["source_instance_id"], row["pod_id"])].append(
            ScopedOwner(
                workload_id=row["workload_id"],
                workload=workload,
                evidence_refs=tuple(sorted(set(row["evidence_refs"]))),
            )
        )
    pods: dict[str, list[ScopedPod]] = defaultdict(list)
    for row in pod_rows:
        key = (row["source_instance_id"], row["pod_id"])
        pods[row["source_instance_id"]].append(
            ScopedPod(
                pod_id=row["pod_id"],
                name=row["name"],
                namespace=row["namespace"],
                cluster_uid=row["cluster_uid"],
                captured_uid=row["captured_uid"],
                owners=tuple(sorted(owners[key], key=lambda owner: owner.workload_id)),
                evidence_refs=tuple(sorted(set(row["evidence_refs"]))),
            )
        )
    return [
        SourceInventory(
            capture=capture,
            pods=tuple(sorted(pods[capture.source_instance_id], key=lambda pod: pod.pod_id)),
        )
        for capture in sorted(captures, key=lambda capture: capture.sort_key)
    ]


# I2.4 (decision record D14.4): the legacy declared `CALLS` edge from the caller to each candidate
# Operation and the qualification fields of the evidence it references. The qualification builder
# passes on only the DECLARED ids; the edge's v1 OBSERVED ids are read but never used locally.
_DECLARED_CALLS_QUERY = (
    "MATCH (:Service {id: $subject_id})-[r:CALLS]->(o:Operation) WHERE o.id IN $operation_ids "
    "RETURN o.id AS operation_id, coalesce(r.evidence_ids, []) AS evidence_ids"
)


@dataclass(frozen=True)
class DeclaredCallEvidence:
    """The caller's legacy `CALLS` edge evidence per candidate Operation, read under the fence."""

    edge_evidence_ids: dict[str, tuple[str, ...]]
    evidence_rows: dict[str, dict]


def read_declared_call_evidence(
    runner: neo4j.Session | neo4j.ManagedTransaction,
    *,
    subject_id: str,
    operation_ids: Sequence[str],
) -> DeclaredCallEvidence:
    edges = {
        row["operation_id"]: tuple(sorted(set(row["evidence_ids"])))
        for row in runner.run(
            _DECLARED_CALLS_QUERY, subject_id=subject_id, operation_ids=sorted(set(operation_ids))
        )
    }
    evidence_ids = sorted({eid for ids in edges.values() for eid in ids})
    rows = read_qualification_evidence_rows(runner, evidence_ids=evidence_ids)
    return DeclaredCallEvidence(edge_evidence_ids=edges, evidence_rows=rows)


@dataclass(frozen=True)
class ProviderOwnerRows:
    """The `(:Service)-[:PROVIDES]->(:Operation)` rows of some Operations and the qualification
    fields of the `Evidence` they reference, read under the caller's fence (I3 D8). Deciding the
    owner is the caller's job (`dependency_projection.group_evidenced_rows`)."""

    provides: tuple[dict, ...]
    evidence_rows: dict[str, dict]


def read_provider_owners(
    runner: neo4j.Session | neo4j.ManagedTransaction, *, operation_ids: Sequence[str]
) -> ProviderOwnerRows:
    """I3 D8: the v0.5 `PROVIDES` read of `read_service_dependency_rows`, for a given set of
    Operations. Must run inside the same stable-snapshot attempt as the candidate read."""
    ids = sorted(set(operation_ids))
    if not ids:
        return ProviderOwnerRows(provides=(), evidence_rows={})
    provides = tuple(
        dict(record) for record in runner.run(PROVIDES_FOR_OPERATIONS_QUERY, operation_ids=ids)
    )
    evidence_ids = sorted({eid for row in provides for eid in row["evidence_ids"]})
    return ProviderOwnerRows(
        provides=provides,
        evidence_rows=read_qualification_evidence_rows(runner, evidence_ids=evidence_ids),
    )


@dataclass(frozen=True)
class ScopedApplicabilityRead:
    """One evaluated candidate page, and the declared evidence of its Operations, bound to the
    snapshot it was read under (I2 §8, §11)."""

    snapshot_id: str
    model_revision: str
    result: ApplicabilityResult
    declared: DeclaredCallEvidence = dataclasses.field(
        default_factory=lambda: DeclaredCallEvidence({}, {})
    )


@dataclass(frozen=True)
class ApplicabilityPage:
    """What `read_applicability_page` read under the caller's fence. `considered_source_count` is
    I3 D4's `S`. `result` is `None` when `page_size_for` stopped the read before any candidate was
    read (I3 D6)."""

    captures: tuple[SourceCapture, ...]
    considered_source_count: int
    result: ApplicabilityResult | None
    declared: DeclaredCallEvidence


def considered_source_count(
    captures: Sequence[SourceCapture], selector: SourceSelector | None
) -> int:
    """I3 D4 step 1: with an explicit selector, 1 if the selected `(source, revision)` is a current
    capture, else 0; otherwise every accepted capture, paired or not."""
    if selector is None:
        return len(captures)
    return int(
        any(
            capture.source_instance_id == selector.source_instance_id
            and capture.revision == selector.revision
            for capture in captures
        )
    )


def read_applicability_page(
    runner: neo4j.Session,
    request: LocalityRequest,
    *,
    after_id: str | None,
    page_size_for: Callable[[int], int | None],
) -> ApplicabilityPage:
    """One candidate page and everything its evaluation needs (D3, D13.6-D13.7, D14.4), read in
    the I3 D4 order: the captures first, then `page_size_for(S)` chooses the page size - `None`
    stops before any candidate is read - then the candidates, their Pods/owners and the declared
    `CALLS` evidence. It opens no fence of its own: call it inside a stable-snapshot `read_extra`.
    A phase-1 refusal reads nothing."""
    empty = DeclaredCallEvidence({}, {})
    if isinstance(preflight(request), RequestRefusal):
        return ApplicabilityPage((), 0, evaluate_candidates(request, [], []), empty)
    captures = read_source_captures(runner)
    count = considered_source_count(captures, request.selector)
    page_size = page_size_for(count)
    if page_size is None:
        return ApplicabilityPage(tuple(captures), count, None, empty)
    page = read_scoped_observed_calls(
        runner,
        subject_id=request.subject_service_id,
        object_id=request.object_operation_id,
        after_id=after_id,
        limit=page_size,
    )
    sources = read_source_inventories(
        runner, pod_uids=[record.caller_pod_uid for record in page.records], captures=captures
    )
    declared = read_declared_call_evidence(
        runner,
        subject_id=request.subject_service_id,
        operation_ids=[record.object_id for record in page.records],
    )
    result = evaluate_candidates(request, page.records, sources, truncated=page.truncated)
    return ApplicabilityPage(tuple(captures), count, result, declared)


def read_scoped_applicability(
    session: neo4j.Session,
    request: LocalityRequest,
    *,
    coverage_qualification_enabled: bool,
    service_workload_mapping_document: ServiceWorkloadMappingDocument | None,
    after_id: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_attempts: int = 3,
) -> ScopedApplicabilityRead:
    """Reads one candidate page of at most `page_size` records (D3; I3 D4 allows a smaller page),
    the committed source captures and their Pods/owners, and the declared `CALLS` evidence of the
    page's Operations inside one stable-snapshot attempt, then evaluates the page (D13.7, D14.4).
    A malformed window raises `ValueError` before anything is read; a phase-1 refusal reads no
    candidates. `SnapshotUnstable` propagates.

    `service_workload_mapping_document` is required, not defaulted: it enters the canonical snapshot
    state, so the caller must pass the same configured artifact every v0.5 read passes, or this
    read's `snapshot_id` would differ from theirs (one canonical snapshot, I2 §11; I3.3a)."""
    if not 1 <= page_size <= DEFAULT_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {DEFAULT_PAGE_SIZE}")
    preflight(request)

    snapshot = read_stable_snapshot_from_session(
        session,
        coverage_qualification_enabled=coverage_qualification_enabled,
        service_workload_mapping_document=service_workload_mapping_document,
        read_extra=lambda runner: read_applicability_page(
            runner, request, after_id=after_id, page_size_for=lambda _count: page_size
        ),
        max_attempts=max_attempts,
    )
    page = snapshot.extra
    assert page.result is not None  # a fixed page size never stops the read
    return ScopedApplicabilityRead(
        snapshot_id=snapshot.snapshot_id,
        model_revision=snapshot.model_revision,
        result=page.result,
        declared=page.declared,
    )


# --- I3.2: the fenced locality read (I3 decision record D4, D6, D8, D17) -------------------------


def locality_page_size(considered_sources: int) -> int | None:
    """I3 D4 step 2: `None` (refuse before reading any candidate, D6) beyond the capture-source
    bound, else `k = min(500, ⌊2000 / S⌋)`."""
    if considered_sources > CAPTURE_SOURCE_BOUND:
        return None
    return candidate_page_size(considered_sources)


@dataclass(frozen=True)
class LocalityInventoryRead:
    """One stable-snapshot attempt for the locality answer. `page` is `None` when the caller asked
    for the snapshot only (a refusal decided before the read, D17.1)."""

    snapshot_id: str
    model_revision: str
    page: ApplicabilityPage | None
    owners: ProviderOwnerRows

    def applicability(self) -> ScopedApplicabilityRead:
        """The read in the shape I2's pure `assess` takes."""
        assert self.page is not None and self.page.result is not None
        return ScopedApplicabilityRead(
            snapshot_id=self.snapshot_id,
            model_revision=self.model_revision,
            result=self.page.result,
            declared=self.page.declared,
        )


def read_locality_inventory(
    session: neo4j.Session,
    request: LocalityRequest,
    *,
    coverage_qualification_enabled: bool,
    service_workload_mapping_document: ServiceWorkloadMappingDocument | None,
    after_id: str | None,
    read_candidates: bool,
    max_attempts: int = 3,
) -> LocalityInventoryRead:
    """The candidate page (bounded by D4's preflight) and the `PROVIDES` rows of its Operations
    (D8), read in one stable-snapshot attempt. With `read_candidates=False` only the snapshot is
    fenced. `SnapshotUnstable` propagates. `service_workload_mapping_document` is required for the
    reason `read_scoped_applicability` gives."""
    no_owners = ProviderOwnerRows(provides=(), evidence_rows={})

    def read_extra(runner: neo4j.Session) -> tuple[ApplicabilityPage | None, ProviderOwnerRows]:
        if not read_candidates:
            return None, no_owners
        page = read_applicability_page(
            runner, request, after_id=after_id, page_size_for=locality_page_size
        )
        if page.result is None:
            return page, no_owners
        operations = [candidate.record.object_id for candidate in page.result.candidates]
        return page, read_provider_owners(runner, operation_ids=operations)

    snapshot = read_stable_snapshot_from_session(
        session,
        coverage_qualification_enabled=coverage_qualification_enabled,
        service_workload_mapping_document=service_workload_mapping_document,
        read_extra=read_extra,
        max_attempts=max_attempts,
    )
    page, owners = snapshot.extra
    return LocalityInventoryRead(
        snapshot_id=snapshot.snapshot_id,
        model_revision=snapshot.model_revision,
        page=page,
        owners=owners,
    )


# --- I3.3a: the same-snapshot scoped resolver read (I3 decision record D11) ----------------------

_V2_BY_ID_QUERY = "MATCH (v:ScopedObservedCallV2) WHERE v.id IN $ids " + _V2_FIELDS

# D11 capture authority (a): a captured Pod contribution carrying the ref, whose captured UID is
# the caller Pod of a v2 record of this subject (and Operation). It starts from the refs, never
# from the subject's v2 records, so its result is bounded by the at most 20 refs.
_POD_CAPTURE_AUTHORITY_QUERY = (
    "MATCH (c:InfrastructureContribution) "
    "WHERE c.captured_resource_uid IS NOT NULL "
    "AND any(ref IN coalesce(c.evidence_refs, []) WHERE ref IN $refs) "
    "MATCH (e:InfrastructureEntity {id: c.entity_id}) WHERE e.entity_kind = 'KUBERNETES_POD' "
    "AND EXISTS { MATCH (v:ScopedObservedCallV2) WHERE v.subject_id = $subject_id "
    "AND ($object_id IS NULL OR v.object_id = $object_id) "
    "AND v.caller_pod_uid = c.captured_resource_uid } "
    "UNWIND c.evidence_refs AS ref WITH ref WHERE ref IN $refs RETURN DISTINCT ref"
)
# D11 capture authority (b): a WORKLOAD_OWNS_POD claim contribution carrying the ref, whose Pod is
# such a Pod (one of its captured contributions has a caller Pod UID of a matching v2 record).
_OWNER_CAPTURE_AUTHORITY_QUERY = (
    "MATCH (cc:InfrastructureClaimContribution) "
    "WHERE any(ref IN coalesce(cc.evidence_refs, []) WHERE ref IN $refs) "
    "MATCH (claim:InfrastructureClaim {id: cc.claim_id, kind: 'WORKLOAD_OWNS_POD'}) "
    "WHERE EXISTS { MATCH (pc:InfrastructureContribution {entity_id: claim.object_id}) "
    "WHERE pc.captured_resource_uid IS NOT NULL "
    "MATCH (v:ScopedObservedCallV2) WHERE v.subject_id = $subject_id "
    "AND ($object_id IS NULL OR v.object_id = $object_id) "
    "AND v.caller_pod_uid = pc.captured_resource_uid } "
    "UNWIND cc.evidence_refs AS ref WITH ref WHERE ref IN $refs RETURN DISTINCT ref"
)


@dataclass(frozen=True)
class ScopedEvidenceRows:
    """What the D11 resolver read under one fence. `v2` holds only the records whose subject (and
    Operation) the request authorizes. `pod_refs`/`owner_refs` are the capture refs the authority
    admits, and `evidence_rows` is the `read_evidence_rows` result for exactly those refs."""

    v2: dict[str, ScopedObservedCall]
    pod_refs: frozenset[str]
    owner_refs: frozenset[str]
    evidence_rows: dict


def read_scoped_evidence(
    runner: neo4j.Session,
    *,
    subject_id: str,
    object_id: str | None,
    v2_refs: Sequence[str],
    capture_refs: Sequence[str],
) -> ScopedEvidenceRows:
    """The D11 reads for one evidence-mode request. Run it inside a stable-snapshot `read_extra`.
    A v2 record is returned only for its own caller (and Operation). A capture ref is admitted only
    through the D13.6 Pod/owner relations of such a record, never because an answer selected it,
    so nothing here recomputes a pair, an owner or a claim."""
    v2 = {
        record.id: record
        for record in (_record(row) for row in runner.run(_V2_BY_ID_QUERY, ids=sorted(v2_refs)))
        if record.subject_id == subject_id and (object_id is None or record.object_id == object_id)
    }
    params = {"refs": sorted(capture_refs), "subject_id": subject_id, "object_id": object_id}
    pod_refs = frozenset(row["ref"] for row in runner.run(_POD_CAPTURE_AUTHORITY_QUERY, **params))
    owner_refs = frozenset(
        row["ref"] for row in runner.run(_OWNER_CAPTURE_AUTHORITY_QUERY, **params)
    )
    authorized = sorted(pod_refs | owner_refs)
    evidence_rows = read_evidence_rows(
        runner, evidence_ids=authorized, reachable_kubernetes_evidence_ids=frozenset(authorized)
    )
    return ScopedEvidenceRows(
        v2=v2, pod_refs=pod_refs, owner_refs=owner_refs, evidence_rows=evidence_rows
    )
