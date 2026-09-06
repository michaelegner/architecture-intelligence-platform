"""v0.4.0 I3.1 - `app.architecture_intelligence.drift_projection` (I3 spec §7.1, §19, §20).

These tests are the executable form of the invariant the whole increment exists to establish: the
drift answer is a *selection* from the already-qualified I1 dependency projection, never a second
derivation of it (I3 spec §8/§16). So most assertions here are identity assertions - the claim that
comes out is the object that went in.
"""

from app.architecture_intelligence.contracts import (
    Coverage,
    DeliveryKind,
    DeliveryRef,
    DeliveryRelationType,
    DependencyClaim,
    DependencyPredicate,
    DestinationResolution,
    EntityRef,
    EntityType,
    Limitation,
    LimitationCode,
    Qualification,
)
from app.architecture_intelligence.dependency_projection import ProjectionResult
from app.architecture_intelligence.drift_projection import project_architecture_drift

SUBJECT = EntityRef(id="service:order-service", type=EntityType.SERVICE, name="OrderService")


def _claim(
    marker: str,
    qualification: Qualification,
    *,
    object_id: str = "service:product-service",
    object_name: str = "ProductService",
    operation_path: str = "/products/{id}",
) -> DependencyClaim:
    return DependencyClaim(
        claim_id="aip:claim:v1:" + (marker * 64)[:64],
        subject=SUBJECT,
        predicate=DependencyPredicate.DIRECT_DEPENDENCY,
        object=EntityRef(id=object_id, type=EntityType.SERVICE, name=object_name),
        destination_resolution=DestinationResolution.RESOLVED_SERVICE,
        delivery=DeliveryRef(
            kind=DeliveryKind.SYNC_HTTP,
            relation_type=DeliveryRelationType.CALLS,
            via=EntityRef(
                id=f"operation:{object_id}:GET:{operation_path}",
                type=EntityType.OPERATION,
                name=f"GET {operation_path}",
                method="GET",
                path=operation_path,
            ),
        ),
        qualification=qualification,
        coverage=(Coverage.NONE if qualification == Qualification.NOT_OBSERVED_IN_WINDOW else None),
        evidence_refs=["evidence:declared:" + (marker * 64)[:64]],
        resolution_evidence_refs=["evidence:declared:" + (marker.upper() * 64)[:64].lower()],
    )


CONFIRMED = _claim("a", Qualification.CONFIRMED)
OBSERVED_ONLY = _claim("b", Qualification.OBSERVED_ONLY)
NOT_OBSERVED = _claim("c", Qualification.NOT_OBSERVED_IN_WINDOW)


def _unresolved(*claim_ids: str) -> Limitation:
    return Limitation(
        code=LimitationCode.UNRESOLVED_IDENTITY,
        message="no single evidenced provider service",
        claim_ids=sorted(claim_ids),
    )


def _insufficient() -> Limitation:
    return Limitation(
        code=LimitationCode.INSUFFICIENT_EVIDENCE,
        message="service:order-service -CALLS-> operation:x has no declared or matching observed "
        "evidence; no dependency claim was created.",
        claim_ids=[],
    )


def test_confirmed_claims_are_omitted():
    result = project_architecture_drift(ProjectionResult(claims=[CONFIRMED], limitations=[]))

    assert result.claims == []


def test_observed_only_is_retained_as_the_same_object():
    result = project_architecture_drift(ProjectionResult(claims=[OBSERVED_ONLY], limitations=[]))

    assert result.claims == [OBSERVED_ONLY]
    assert result.claims[0] is OBSERVED_ONLY


def test_not_observed_in_window_is_retained_as_the_same_object():
    result = project_architecture_drift(ProjectionResult(claims=[NOT_OBSERVED], limitations=[]))

    assert result.claims == [NOT_OBSERVED]
    assert result.claims[0] is NOT_OBSERVED


def test_mixed_qualifications_retain_exactly_the_two_drift_states():
    result = project_architecture_drift(
        ProjectionResult(claims=[CONFIRMED, OBSERVED_ONLY, NOT_OBSERVED], limitations=[])
    )

    assert [claim.qualification for claim in result.claims] == [
        Qualification.OBSERVED_ONLY,
        Qualification.NOT_OBSERVED_IN_WINDOW,
    ]


def test_relative_claim_ordering_is_preserved_not_resorted_by_qualification():
    """I3 spec §20: filtering the dependency result preserves its relative order, so the drift claims
    stay in the I1 (object.id, delivery.kind, delivery.via.id, claim_id) order rather than being
    regrouped with (for example) OBSERVED_ONLY ahead of NOT_OBSERVED_IN_WINDOW."""
    first = _claim("c", Qualification.NOT_OBSERVED_IN_WINDOW, object_id="service:a-service")
    middle = _claim("a", Qualification.CONFIRMED, object_id="service:m-service")
    last = _claim("b", Qualification.OBSERVED_ONLY, object_id="service:z-service")

    result = project_architecture_drift(
        ProjectionResult(claims=[first, middle, last], limitations=[])
    )

    assert result.claims == [first, last]


def test_claim_identity_and_evidence_survive_the_projection_untouched():
    """I3 spec §8: no drift claim-id namespace, no drift-specific evidence list, no re-resolved
    destination - every field is the one the dependency answer carries."""
    (projected,) = project_architecture_drift(
        ProjectionResult(claims=[NOT_OBSERVED], limitations=[])
    ).claims

    assert projected.claim_id == NOT_OBSERVED.claim_id
    assert projected.subject == NOT_OBSERVED.subject
    assert projected.predicate == NOT_OBSERVED.predicate
    assert projected.object == NOT_OBSERVED.object
    assert projected.destination_resolution == NOT_OBSERVED.destination_resolution
    assert projected.delivery == NOT_OBSERVED.delivery
    assert projected.qualification == NOT_OBSERVED.qualification
    assert projected.coverage == NOT_OBSERVED.coverage
    assert projected.evidence_refs == NOT_OBSERVED.evidence_refs
    assert projected.resolution_evidence_refs == NOT_OBSERVED.resolution_evidence_refs


def test_predicate_stays_direct_dependency():
    """I3 spec §7.3: the same architecture fact does not become a different fact merely because its
    evidence state changed - there is no DRIFTS_FROM / UNDECLARED_DEPENDENCY predicate."""
    (projected,) = project_architecture_drift(
        ProjectionResult(claims=[OBSERVED_ONLY], limitations=[])
    ).claims

    assert projected.predicate == DependencyPredicate.DIRECT_DEPENDENCY


def test_claim_scoped_limitation_is_retained_for_a_surviving_drift_claim():
    limitation = _unresolved(OBSERVED_ONLY.claim_id)

    result = project_architecture_drift(
        ProjectionResult(claims=[OBSERVED_ONLY], limitations=[limitation])
    )

    assert result.limitations == [limitation]


def test_claim_scoped_limitation_of_an_omitted_confirmed_claim_is_dropped():
    """I3 spec §19.1's worked example: a CONFIRMED dependency omitted from the drift answer takes its
    own claim-scoped unresolved limitation with it."""
    result = project_architecture_drift(
        ProjectionResult(
            claims=[CONFIRMED, OBSERVED_ONLY], limitations=[_unresolved(CONFIRMED.claim_id)]
        )
    )

    assert result.claims == [OBSERVED_ONLY]
    assert result.limitations == []


def test_limitation_spanning_several_claims_is_narrowed_to_the_intersection():
    """I3 spec §19.1: "claim_ids -> intersect with returned drift claim IDs". Retaining the whole
    list would leave the answer naming a claim it does not return."""
    result = project_architecture_drift(
        ProjectionResult(
            claims=[CONFIRMED, OBSERVED_ONLY, NOT_OBSERVED],
            limitations=[
                _unresolved(CONFIRMED.claim_id, OBSERVED_ONLY.claim_id, NOT_OBSERVED.claim_id)
            ],
        )
    )

    (limitation,) = result.limitations
    assert limitation.claim_ids == sorted({OBSERVED_ONLY.claim_id, NOT_OBSERVED.claim_id})
    assert limitation.code == LimitationCode.UNRESOLVED_IDENTITY
    assert limitation.message == "no single evidenced provider service"


def test_every_retained_claim_id_names_a_returned_claim():
    result = project_architecture_drift(
        ProjectionResult(
            claims=[CONFIRMED, OBSERVED_ONLY],
            limitations=[_unresolved(CONFIRMED.claim_id, OBSERVED_ONLY.claim_id), _insufficient()],
        )
    )

    returned_ids = {claim.claim_id for claim in result.claims}
    for limitation in result.limitations:
        assert set(limitation.claim_ids) <= returned_ids


def test_claim_independent_insufficient_evidence_limitation_is_always_retained():
    """I3 spec §19.2: "no safe claim" is not "proved non-drift" - it materially limits how complete
    the drift result is, so it survives even when nothing at all drifted."""
    limitation = _insufficient()

    result = project_architecture_drift(
        ProjectionResult(claims=[CONFIRMED], limitations=[limitation])
    )

    assert result.claims == []
    assert result.limitations == [limitation]


def test_limitation_ordering_is_preserved():
    first = _insufficient()
    second = _unresolved(OBSERVED_ONLY.claim_id)

    result = project_architecture_drift(
        ProjectionResult(claims=[OBSERVED_ONLY], limitations=[first, second])
    )

    assert result.limitations == [first, second]


def test_empty_projection_projects_to_empty_drift():
    result = project_architecture_drift(ProjectionResult(claims=[], limitations=[]))

    assert result.claims == []
    assert result.limitations == []


def test_projection_does_not_mutate_its_input():
    projection = ProjectionResult(
        claims=[CONFIRMED, OBSERVED_ONLY], limitations=[_unresolved(CONFIRMED.claim_id)]
    )

    project_architecture_drift(projection)

    assert projection.claims == [CONFIRMED, OBSERVED_ONLY]
    assert projection.limitations == [_unresolved(CONFIRMED.claim_id)]
