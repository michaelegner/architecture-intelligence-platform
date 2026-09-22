"""v0.5.0 I3 slice 5b - unit tests for the cross-path reducer (spec §10), the §13.4 service-scoped
filter, and the §20 result bounds - spec §21.4's required cross-path matrix.

Builds real `resolve_path_a`/`resolve_path_b`/`resolve_path_c` outputs (not hand-built
`DeploymentResolution` objects) against one shared `SNAPSHOT_ID`/`CONTEXT_ID` so the same workload
group naturally produces matching `resolution_id`s across paths - the same real join key
`reduce_cross_path_resolutions` relies on, exercised for real rather than assumed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.architecture_intelligence.contracts import (
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    LimitationCode,
)
from app.architecture_intelligence.deployment_projection import (
    CapturedPodRow,
    CurrentKubernetesWorkload,
    DeclaredServiceIdentity,
    PathResolutionResult,
    RuntimeIdentityObservationRow,
    WorkloadContribution,
    WorkloadOwnershipRow,
    resolve_path_a,
    resolve_path_b,
    resolve_path_c,
)
from app.architecture_intelligence.deployment_reconciliation import (
    _bucket_by_window,
    _public_evidence_ref,
    check_result_bounds,
    filter_for_service,
    reduce_cross_path_resolutions,
)
from app.architecture_intelligence.observation_context import build_observation_context_ref
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    ServiceWorkloadMappingEntry,
)
from app.telemetry.service_resolver import DeclaredServiceCandidate

SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
CONTEXT_ID = "aip:observation-context:v1:" + "b" * 64
_EMPTY = PathResolutionResult(resolutions=[], claims=[])
_ENVIRONMENT = "prod"
_WINDOW_START = "2026-08-26T00:00:00.000000Z"
_WINDOW_END = "2026-08-27T00:00:00.000000Z"
_WINDOW_START_DT = datetime(2026, 8, 26, 0, 0, 0, tzinfo=UTC)
_WINDOW_END_DT = datetime(2026, 8, 27, 0, 0, 0, tzinfo=UTC)
_IN_WINDOW_DT = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
_DECLARED_SERVICES = {"service:checkout": "checkout", "service:other": "other"}


def _workload(workload_id="workload:1", kind="Deployment", namespace="checkout", name="checkout"):
    return CurrentKubernetesWorkload(
        workload_id=workload_id, workload_kind=kind, namespace=namespace, name=name
    )


def _annotated_workload(*, service_id: str, evidence_ref: str = "evidence:kubernetes:a"):
    return CurrentKubernetesWorkload(
        workload_id="workload:1",
        workload_kind="Deployment",
        namespace="checkout",
        name="checkout",
        contributions=(WorkloadContribution(annotation=service_id, evidence_refs=(evidence_ref,)),),
    )


def _path_a(*, service_id: str | None, evidence_ref: str = "evidence:kubernetes:a"):
    services = {"service:checkout": "CheckoutService", "service:other": "OtherService"}
    workload = (
        _annotated_workload(service_id=service_id, evidence_ref=evidence_ref)
        if service_id is not None
        else _workload()
    )
    return resolve_path_a(
        workloads=[workload],
        lookup_service_name=lambda sid: services.get(sid),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )


def _mapping_document(*, service_id: str, mapping_id: str = "m1") -> ServiceWorkloadMappingDocument:
    return ServiceWorkloadMappingDocument(
        artifact_id="artifact-1",
        artifact_revision="rev-1",
        locator="/config/service-workload-mappings.yaml",
        content_digest="c" * 64,
        entries=(
            ServiceWorkloadMappingEntry(
                mapping_id=mapping_id,
                service_id=service_id,
                kubernetes_source_id="checkout-cluster",
                cluster_uid="cluster-uid-1",
                api_group="apps",
                workload_kind="Deployment",
                namespace="checkout",
                name="checkout",
            ),
        ),
    )


def _path_b(*, service_id: str | None, mapping_id: str = "m1"):
    services = {"service:checkout": "CheckoutService", "service:other": "OtherService"}
    document = (
        _mapping_document(service_id=service_id, mapping_id=mapping_id) if service_id else None
    )
    return resolve_path_b(
        document=document,
        configured_kubernetes_sources=[("checkout-cluster", "cluster-uid-1")],
        resolve_workload=lambda entity_id: _workload(),
        lookup_service_name=lambda sid: services.get(sid),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )


def _path_c(
    *,
    service_ids: list[str | None],
    evidence_ref_prefix: str = "runtime-identity:otel:prod:2026-08-26:c",
    workload_id: str = "workload:1",
):
    """Builds a real `resolve_path_c` result for `workload:1` (the same default target Path A/B's
    own `_workload()`/`_path_b` helpers use), so C can agree or conflict with A/B against a shared
    group key exactly as the real reducer would see it. One observation per entry in `service_ids`
    - `None` means an observation whose `service_name` matches no declared candidate (unresolved);
    two or more distinct non-None entries produce Path C's own §10.5 `AMBIGUOUS` outcome."""
    pod_uid = "pod-uid-c1"
    pod_id = "pod:c1"
    observations = [
        RuntimeIdentityObservationRow(
            id=f"{evidence_ref_prefix}-{i}",
            service_name=_DECLARED_SERVICES.get(service_id, "ghost-service"),
            service_namespace=None,
            service_version=None,
            environment=_ENVIRONMENT,
            k8s_pod_uid=pod_uid,
            k8s_pod_name=None,
            k8s_namespace_name=None,
            k8s_cluster_uid=None,
            k8s_deployment_name=None,
            k8s_statefulset_name=None,
            k8s_daemonset_name=None,
            last_seen=_IN_WINDOW_DT,
        )
        for i, service_id in enumerate(service_ids)
    ]
    candidates = [
        DeclaredServiceCandidate(sid, name, None) for sid, name in _DECLARED_SERVICES.items()
    ]
    identities = {
        sid: DeclaredServiceIdentity(service_id=sid, name=name, namespace=None, version=None)
        for sid, name in _DECLARED_SERVICES.items()
    }
    observation_context = build_observation_context_ref(
        _ENVIRONMENT, _WINDOW_START_DT, _WINDOW_END_DT
    )
    return resolve_path_c(
        observations=observations,
        observation_context=observation_context,
        lookup_pods_by_uid=lambda uid: (
            [
                CapturedPodRow(
                    pod_id=pod_id,
                    pod_name="pod",
                    pod_namespace="checkout",
                    cluster_uid="cluster-1",
                    captured_at="2026-08-26T12:00:00Z",
                    evidence_refs=(),
                )
            ]
            if uid == pod_uid
            else []
        ),
        lookup_workload_ids_owning_pod=lambda pid: (
            [WorkloadOwnershipRow(workload_id=workload_id, evidence_refs=())]
            if pid == pod_id
            else []
        ),
        resolve_workload=lambda wid: _workload(workload_id=wid) if wid == workload_id else None,
        declared_service_candidates=candidates,
        service_aliases={},
        lookup_declared_service=lambda sid: identities.get(sid),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )


def test_path_a_only_passes_through_as_resolved_explicit():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.service_id == "service:checkout"
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_EXPLICIT
    assert claim.supporting_methods == [DeploymentResolutionMethod.RESOLVED_EXPLICIT]


def test_path_b_only_passes_through_as_resolved_configured():
    reduced = reduce_cross_path_resolutions(
        path_a=_EMPTY, path_b=_path_b(service_id="service:checkout"), path_c=_EMPTY
    )
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_CONFIGURED
    assert resolution.service_id == "service:checkout"


def test_a_and_b_agree_explicit_is_strongest_and_evidence_is_unioned():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout", evidence_ref="evidence:kubernetes:from-a"),
        path_b=_path_b(service_id="service:checkout"),
        path_c=_EMPTY,
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.supporting_methods == [
        DeploymentResolutionMethod.RESOLVED_EXPLICIT,
        DeploymentResolutionMethod.RESOLVED_CONFIGURED,
    ]
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_EXPLICIT
    assert "evidence:kubernetes:from-a" in claim.evidence_refs
    # Path B's own mapping-evidence id (computed, opaque) is also present - both paths' evidence
    # is unioned into one claim, not just the strongest path's own.
    assert len(claim.evidence_refs) == 2


def test_a_vs_b_disagreement_is_conflict_with_no_claim():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"),
        path_b=_path_b(service_id="service:other"),
        path_c=_EMPTY,
    )
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]
    assert resolution.limitation_codes == [LimitationCode.DEPLOYMENT_IDENTITY_CONFLICT]


def test_a_unresolved_sibling_does_not_taint_a_clean_b_agreement():
    """Disclosed assumption (this slice's plan, Open Questions #4): an UNRESOLVED path's
    named-but-nonexistent candidate never by itself triggers CONFLICT against a different path's
    real resolution, and is excluded from the agreement entirely."""
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:does-not-exist"),
        path_b=_path_b(service_id="service:checkout"),
        path_c=_EMPTY,
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_CONFIGURED
    assert resolution.service_id == "service:checkout"
    assert resolution.candidate_service_ids == ["service:checkout"]


def test_both_unresolved_merges_candidate_ids_and_evidence():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:missing-a"),
        path_b=_path_b(service_id="service:missing-b"),
        path_c=_EMPTY,
    )
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["service:missing-a", "service:missing-b"]
    assert resolution.limitation_codes == [LimitationCode.DEPLOYMENT_IDENTITY_UNRESOLVED]


def test_no_evidence_at_all_produces_no_resolution():
    """A Workload with no annotation and no mapping entry produces nothing for either path - the
    reducer must not fabricate a resolution from an empty input."""
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id=None), path_b=_EMPTY, path_c=_EMPTY
    )
    assert reduced.resolutions == []
    assert reduced.claims == []


# --- §21.4 cross-path reduction, real Path C (spec §10, §10.5) -----------------------------------


def test_path_c_only_passes_through_as_resolved_observed():
    reduced = reduce_cross_path_resolutions(
        path_a=_EMPTY, path_b=_EMPTY, path_c=_path_c(service_ids=["service:checkout"])
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_OBSERVED
    assert resolution.service_id == "service:checkout"
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_OBSERVED
    assert claim.supporting_methods == [DeploymentResolutionMethod.RESOLVED_OBSERVED]


def test_a_and_c_agree_explicit_is_strongest_and_evidence_is_unioned():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout", evidence_ref="evidence:kubernetes:from-a"),
        path_b=_EMPTY,
        path_c=_path_c(service_ids=["service:checkout"]),
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.supporting_methods == [
        DeploymentResolutionMethod.RESOLVED_EXPLICIT,
        DeploymentResolutionMethod.RESOLVED_OBSERVED,
    ]
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_EXPLICIT
    assert "evidence:kubernetes:from-a" in claim.evidence_refs
    # Path C's own runtime-identity evidence id is unioned in too, not just A's - raw here since
    # this test calls `resolve_path_c` directly, without the `_publicize_evidence_refs` wrapping
    # only `run_whole_graph_reconciliation` applies (already covered on its own by
    # `test_public_evidence_ref_wraps_path_c_runtime_identity_id` above).
    assert any(ref.startswith("runtime-identity:otel:") for ref in claim.evidence_refs)
    assert len(claim.evidence_refs) == 2


def test_b_and_c_agree_configured_is_strongest_and_evidence_is_unioned():
    reduced = reduce_cross_path_resolutions(
        path_a=_EMPTY,
        path_b=_path_b(service_id="service:checkout"),
        path_c=_path_c(service_ids=["service:checkout"]),
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_CONFIGURED
    assert resolution.supporting_methods == [
        DeploymentResolutionMethod.RESOLVED_CONFIGURED,
        DeploymentResolutionMethod.RESOLVED_OBSERVED,
    ]
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_CONFIGURED
    assert len(claim.evidence_refs) == 2


def test_a_b_c_all_agree_explicit_is_strongest_and_evidence_is_unioned_across_all_three():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout", evidence_ref="evidence:kubernetes:from-a"),
        path_b=_path_b(service_id="service:checkout"),
        path_c=_path_c(service_ids=["service:checkout"]),
    )
    assert len(reduced.resolutions) == 1
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.RESOLVED_EXPLICIT
    assert resolution.supporting_methods == [
        DeploymentResolutionMethod.RESOLVED_EXPLICIT,
        DeploymentResolutionMethod.RESOLVED_CONFIGURED,
        DeploymentResolutionMethod.RESOLVED_OBSERVED,
    ]
    [claim] = reduced.claims
    assert claim.resolution_method == DeploymentResolutionMethod.RESOLVED_EXPLICIT
    assert len(claim.evidence_refs) == 3


def test_a_vs_c_disagreement_is_conflict_with_no_claim():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"),
        path_b=_EMPTY,
        path_c=_path_c(service_ids=["service:other"]),
    )
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]
    assert resolution.limitation_codes == [LimitationCode.DEPLOYMENT_IDENTITY_CONFLICT]


def test_b_vs_c_disagreement_is_conflict_with_no_claim():
    reduced = reduce_cross_path_resolutions(
        path_a=_EMPTY,
        path_b=_path_b(service_id="service:checkout"),
        path_c=_path_c(service_ids=["service:other"]),
    )
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.CONFLICT
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]


def test_path_c_multiple_services_ambiguous_passes_through_reducer_unmerged():
    """Spec §10.5: multiple distinct declared Services satisfying one Path C runtime identity is
    AMBIGUOUS at Path C's own level (never CONFLICT) - this asserts the reducer passes that
    AMBIGUOUS status through untouched when no other path contributes anything, rather than
    silently reinterpreting it."""
    path_c = _path_c(service_ids=["service:checkout", "service:other"])
    [path_c_resolution] = path_c.resolutions
    assert path_c_resolution.status == DeploymentResolutionStatus.AMBIGUOUS
    reduced = reduce_cross_path_resolutions(path_a=_EMPTY, path_b=_EMPTY, path_c=path_c)
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.AMBIGUOUS
    assert resolution.candidate_service_ids == ["service:checkout", "service:other"]


def test_cross_path_similarity_only_reduces_to_unresolved_with_no_claim():
    """A Path A annotation that only similarity-matches a real Service id (wrong case) never
    resolves at Path A's own level (spec §7's exact-case requirement) - this proves the reducer
    still reduces that to a clean UNRESOLVED with no claim once B/C contribute nothing either,
    the same as any other never-resolved path."""
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="Service:Checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    assert reduced.claims == []
    [resolution] = reduced.resolutions
    assert resolution.status == DeploymentResolutionStatus.UNRESOLVED
    assert resolution.candidate_service_ids == ["Service:Checkout"]


# --- §21.7 determinism: one resolution per group_key across multiple simultaneous groups ---------


def test_reducer_produces_exactly_one_resolution_per_group_key_across_multiple_groups():
    group_1 = _path_a(service_id="service:checkout")
    workload_2 = CurrentKubernetesWorkload(
        workload_id="workload:2",
        workload_kind="Deployment",
        namespace="checkout",
        name="checkout-other",
        contributions=(
            WorkloadContribution(
                annotation="service:other", evidence_refs=("evidence:kubernetes:g2",)
            ),
        ),
    )
    group_2 = resolve_path_a(
        workloads=[workload_2],
        lookup_service_name=lambda sid: {"service:other": "OtherService"}.get(sid),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    workload_3 = CurrentKubernetesWorkload(
        workload_id="workload:3",
        workload_kind="Deployment",
        namespace="billing",
        name="billing",
        contributions=(
            WorkloadContribution(
                annotation="service:checkout", evidence_refs=("evidence:kubernetes:g3",)
            ),
        ),
    )
    group_3 = resolve_path_a(
        workloads=[workload_3],
        lookup_service_name=lambda sid: {"service:checkout": "CheckoutService"}.get(sid),
        snapshot_id=SNAPSHOT_ID,
        context_id=CONTEXT_ID,
    )
    combined_a = PathResolutionResult(
        resolutions=[*group_1.resolutions, *group_2.resolutions, *group_3.resolutions],
        claims=[*group_1.claims, *group_2.claims, *group_3.claims],
    )
    reduced_multi = reduce_cross_path_resolutions(path_a=combined_a, path_b=_EMPTY, path_c=_EMPTY)
    assert len(reduced_multi.resolutions) == 3
    assert len({r.resolution_id for r in reduced_multi.resolutions}) == 3
    assert len(reduced_multi.claims) == 3


# --- §13.4 service-scoped cardinality ------------------------------------------------------------


def test_filter_for_service_returns_only_resolutions_naming_that_service():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"),
        path_b=_path_b(service_id="service:other"),
        path_c=_EMPTY,
    )
    _claims, resolutions = filter_for_service(reduced, service_id="service:checkout")
    assert len(resolutions) == 1
    assert "service:checkout" in resolutions[0].candidate_service_ids
    claims_unrelated, resolutions_unrelated = filter_for_service(
        reduced, service_id="service:unrelated"
    )
    assert resolutions_unrelated == []
    assert claims_unrelated == []


def test_filter_for_service_shows_a_conflict_from_both_named_services():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"),
        path_b=_path_b(service_id="service:other"),
        path_c=_EMPTY,
    )
    _claims_a, resolutions_a = filter_for_service(reduced, service_id="service:checkout")
    _claims_b, resolutions_b = filter_for_service(reduced, service_id="service:other")
    assert resolutions_a and resolutions_a[0].status == DeploymentResolutionStatus.CONFLICT
    assert resolutions_b and resolutions_b[0].status == DeploymentResolutionStatus.CONFLICT
    assert resolutions_a[0].resolution_id == resolutions_b[0].resolution_id


# --- §20 result bounds -----------------------------------------------------------------------------


def test_check_result_bounds_none_when_within_bounds():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    claims, resolutions = filter_for_service(reduced, service_id="service:checkout")
    assert check_result_bounds(claims, resolutions) is None


def test_check_result_bounds_flags_too_many_claims():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    claims, resolutions = filter_for_service(reduced, service_id="service:checkout")
    assert (
        check_result_bounds(claims * 101, resolutions)
        == LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    )


def test_check_result_bounds_flags_too_many_resolutions():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    claims, resolutions = filter_for_service(reduced, service_id="service:checkout")
    assert (
        check_result_bounds(claims, resolutions * 251)
        == LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    )


def test_check_result_bounds_flags_too_many_evidence_refs_on_one_claim():
    reduced = reduce_cross_path_resolutions(
        path_a=_path_a(service_id="service:checkout"), path_b=_EMPTY, path_c=_EMPTY
    )
    claims, resolutions = filter_for_service(reduced, service_id="service:checkout")
    [claim] = claims
    bloated_claim = claim.model_copy(
        update={"evidence_refs": sorted(f"evidence:kubernetes:{i}" for i in range(65))}
    )
    assert (
        check_result_bounds([bloated_claim], resolutions)
        == LimitationCode.DEPLOYMENT_RESULT_LIMIT_EXCEEDED
    )


# --- PR #222 review fix: _public_evidence_ref / _bucket_by_window ------------------------------


def test_public_evidence_ref_leaves_real_evidence_ids_unchanged():
    assert _public_evidence_ref("evidence:kubernetes:abc") == "evidence:kubernetes:abc"


def test_public_evidence_ref_wraps_path_b_mapping_evidence_id():
    raw = "urn:aip:service-workload-mapping-evidence:v1:deadbeef"
    assert _public_evidence_ref(raw) == "evidence:mapping:v1:deadbeef"


def test_public_evidence_ref_wraps_path_c_runtime_identity_id():
    raw = "runtime-identity:otel:prod:2026-09-19:cafef00d"
    assert _public_evidence_ref(raw) == "evidence:otel:prod:2026-09-19:cafef00d"


def _observation_row(**overrides) -> RuntimeIdentityObservationRow:
    defaults = {
        "id": "runtime-identity:otel:prod:2026-09-19:x",
        "service_name": "checkout",
        "service_namespace": None,
        "service_version": None,
        "environment": "prod",
        "k8s_pod_uid": "pod-uid-1",
        "k8s_pod_name": None,
        "k8s_namespace_name": None,
        "k8s_cluster_uid": None,
        "k8s_deployment_name": None,
        "k8s_statefulset_name": None,
        "k8s_daemonset_name": None,
        "last_seen": None,
        "first_seen": None,
    }
    defaults.update(overrides)
    return RuntimeIdentityObservationRow(**defaults)


def test_bucket_by_window_packs_nearby_rows_into_one_bucket():
    base = datetime(2026, 9, 1, tzinfo=UTC)
    row_a = _observation_row(id="a", first_seen=base, last_seen=base)
    row_b = _observation_row(
        id="b", first_seen=base + timedelta(days=1), last_seen=base + timedelta(days=1)
    )
    buckets = _bucket_by_window([(row_a, None), (row_b, None)])
    assert len(buckets) == 1
    [(rows, bounds)] = buckets
    assert {row.id for row, _ in rows} == {"a", "b"}
    assert bounds[1] - bounds[0] <= timedelta(days=31)


def test_bucket_by_window_splits_rows_more_than_31_days_apart():
    base = datetime(2026, 9, 1, tzinfo=UTC)
    row_a = _observation_row(id="a", first_seen=base, last_seen=base)
    far = base + timedelta(days=40)
    row_b = _observation_row(id="b", first_seen=far, last_seen=far)
    buckets = _bucket_by_window([(row_a, None), (row_b, None)])
    assert len(buckets) == 2


def test_bucket_by_window_includes_captured_at_in_the_span():
    """PR #222 review, round 2: a Pod's own `captured_at` - not just the observation's own
    first_seen/last_seen - must also be covered by the bucket's own bounds, since
    `_observation_context_limitation` checks it independently."""
    base = datetime(2026, 9, 1, tzinfo=UTC)
    row = _observation_row(id="a", first_seen=base, last_seen=base)
    near_captured_at = base + timedelta(days=5)
    [(rows, bounds)] = _bucket_by_window([(row, near_captured_at)])
    assert rows == [(row, near_captured_at)]
    assert bounds[0] <= near_captured_at <= bounds[1]
    assert bounds[0] <= base <= bounds[1]


def test_bucket_by_window_clamps_a_single_rows_own_span_exceeding_31_days():
    """PR #222 review, round 2 (blocking): a single row's own span (its captured_at 40 days from
    its first_seen/last_seen) must never reach the caller unclamped - the original version only
    enforced the 31-day limit when merging into an *existing* bucket, never for a brand-new one,
    letting an invalid >31-day window reach `build_observation_context_ref` and raise instead of
    the row failing DEPLOYMENT_TEMPORAL_MISMATCH like a real request would."""
    base = datetime(2026, 9, 1, tzinfo=UTC)
    row = _observation_row(id="a", first_seen=base, last_seen=base)
    far_captured_at = base + timedelta(days=40)
    [(rows, bounds)] = _bucket_by_window([(row, far_captured_at)])
    assert rows == [(row, far_captured_at)]
    assert bounds is not None
    assert bounds[1] - bounds[0] <= timedelta(days=31)
    # A real ObservationContextRef must actually accept these bounds - this is what a naive
    # unclamped span would fail to do.
    build_observation_context_ref("prod", bounds[0], bounds[1])


def test_bucket_by_window_gives_untimestamped_rows_their_own_none_bounds_bucket():
    row_a = _observation_row(id="a", first_seen=None, last_seen=None)
    row_b = _observation_row(id="b", first_seen=None, last_seen=None)
    buckets = _bucket_by_window([(row_a, None), (row_b, None)])
    assert len(buckets) == 2
    assert all(bounds is None for _rows, bounds in buckets)
