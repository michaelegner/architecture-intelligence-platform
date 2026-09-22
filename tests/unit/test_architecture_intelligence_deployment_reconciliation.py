"""v0.5.0 I3 slice 5b - unit tests for the cross-path reducer (spec §10), the §13.4 service-scoped
filter, and the §20 result bounds - spec §21.4's required cross-path matrix.

Builds real `resolve_path_a`/`resolve_path_b`/`resolve_path_c` outputs (not hand-built
`DeploymentResolution` objects) against one shared `SNAPSHOT_ID`/`CONTEXT_ID` so the same workload
group naturally produces matching `resolution_id`s across paths - the same real join key
`reduce_cross_path_resolutions` relies on, exercised for real rather than assumed.
"""

from __future__ import annotations

from app.architecture_intelligence.contracts import (
    DeploymentResolutionMethod,
    DeploymentResolutionStatus,
    LimitationCode,
)
from app.architecture_intelligence.deployment_projection import (
    CurrentKubernetesWorkload,
    PathResolutionResult,
    WorkloadContribution,
    resolve_path_a,
    resolve_path_b,
)
from app.architecture_intelligence.deployment_reconciliation import (
    check_result_bounds,
    filter_for_service,
    reduce_cross_path_resolutions,
)
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    ServiceWorkloadMappingEntry,
)

SNAPSHOT_ID = "aip:snapshot:v1:" + "a" * 64
CONTEXT_ID = "aip:observation-context:v1:" + "b" * 64
_EMPTY = PathResolutionResult(resolutions=[], claims=[])
_ENVIRONMENT = "prod"
_WINDOW_START = "2026-08-26T00:00:00.000000Z"
_WINDOW_END = "2026-08-27T00:00:00.000000Z"


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
