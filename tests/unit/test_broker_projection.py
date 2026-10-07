"""v0.6.1 I2c: the pure Broker projection (spec §5.1): claim identity, evidence membership and
union, the unevidenced-Broker rule, and the Broker-aware evidence conversion."""

import hashlib
import json

from app.architecture_intelligence.broker_contracts import BrokerClaim, EvidenceRelationTypeV06
from app.architecture_intelligence.broker_projection import (
    broker_support_facts,
    compute_broker_claim_id,
    project_broker_claims,
    to_broker_aware_records,
)
from app.architecture_intelligence.contracts import (
    EvidenceRecord,
    EvidenceRelationType,
    LimitationCode,
    SupportedFact,
)
from app.provenance.model import EvidenceType, SourceType
from app.sources.owner_ids import broker_owned_id

SERVICE = "service:invoice-service"
STABLE = "kafka:cluster-a"
BROKER = broker_owned_id(stable_broker_id=STABLE)
E1 = "evidence:asyncapi:urn:aip:source:filesystem:" + "1" * 64
E2 = "evidence:manifest:urn:aip:source:filesystem:" + "2" * 64
GHOST = "evidence:asyncapi:urn:aip:source:filesystem:" + "9" * 64


def _rows(uses, resolvable=(E1, E2)):
    return {"broker_uses": uses, "evidence": {eid: {"id": eid} for eid in resolvable}}


def _use(evidence_ids, broker_id=BROKER, stable=STABLE):
    return {"broker_id": broker_id, "stable_broker_id": stable, "evidence_ids": evidence_ids}


def test_claim_id_matches_the_independently_derived_formula():
    # Written from spec §5.1 (canonical JSON = sorted keys, no whitespace), not from app code.
    payload = {"broker_id": BROKER, "predicate": "USES_BROKER", "service_id": SERVICE}
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert compute_broker_claim_id(service_id=SERVICE, broker_id=BROKER) == f"aip:claim:v1:{digest}"


def test_claim_id_follows_the_pair_not_the_evidence_and_never_collides_across_pairs():
    base = compute_broker_claim_id(service_id=SERVICE, broker_id=BROKER)
    assert compute_broker_claim_id(service_id=SERVICE, broker_id=BROKER) == base
    assert compute_broker_claim_id(service_id="service:other", broker_id=BROKER) != base
    other = broker_owned_id(stable_broker_id="kafka:cluster-b")
    assert compute_broker_claim_id(service_id=SERVICE, broker_id=other) != base
    # the claim built from different evidence has the same id
    one = project_broker_claims(_rows([_use([E1])]), service_id=SERVICE, service_name="Inv")
    two = project_broker_claims(_rows([_use([E2])]), service_id=SERVICE, service_name="Inv")
    assert one.claims[0].claim_id == two.claims[0].claim_id == base


def test_a_broker_claim_names_the_service_the_broker_and_its_resolvable_evidence():
    result = project_broker_claims(_rows([_use([E2, E1])]), service_id=SERVICE, service_name="Inv")
    [claim] = result.claims
    assert isinstance(claim, BrokerClaim)
    assert (claim.subject.id, claim.subject.type.value, claim.subject.name) == (
        SERVICE,
        "SERVICE",
        "Inv",
    )
    assert (claim.object.id, claim.object.type.value, claim.object.name) == (
        BROKER,
        "BROKER",
        STABLE,
    )
    assert claim.evidence_refs == [E1, E2]  # sorted
    assert result.limitations == []


def test_evidence_of_several_rows_for_one_broker_is_unioned_not_overwritten():
    rows = _rows([_use([E1]), _use([E2, E1])])
    [claim] = project_broker_claims(rows, service_id=SERVICE, service_name="Inv").claims
    assert claim.evidence_refs == [E1, E2]


def test_only_evidence_ids_that_resolve_are_kept():
    rows = _rows([_use([E1, GHOST])], resolvable=(E1,))
    [claim] = project_broker_claims(rows, service_id=SERVICE, service_name="Inv").claims
    assert claim.evidence_refs == [E1]  # membership of each id, not "the relation has evidence ids"


def test_a_broker_with_no_resolvable_evidence_yields_no_claim_and_one_limitation():
    rows = _rows([_use([GHOST])], resolvable=())
    result = project_broker_claims(rows, service_id=SERVICE, service_name="Inv")
    assert result.claims == []
    [limitation] = result.limitations
    assert limitation.code is LimitationCode.INSUFFICIENT_EVIDENCE
    assert limitation.claim_ids == []
    # the answer stays the v0.5 shape when no claim results, so no Broker identifier may leak in
    assert BROKER not in limitation.message and STABLE not in limitation.message
    assert SERVICE in limitation.message


def test_two_brokers_for_one_service_give_two_claims_in_a_stable_order():
    other = broker_owned_id(stable_broker_id="kafka:cluster-b")
    rows = _rows([_use([E1], other, "kafka:cluster-b"), _use([E2])])
    result = project_broker_claims(rows, service_id=SERVICE, service_name="Inv")
    assert [c.object.id for c in result.claims] == sorted([BROKER, other])


def test_no_broker_rows_yield_nothing():
    result = project_broker_claims(_rows([]), service_id=SERVICE, service_name="Inv")
    assert result.claims == [] and result.limitations == []


# --- the Broker-aware evidence conversion -------------------------------------------------------


def _record(evidence_id, supports=()):
    return EvidenceRecord(
        id=evidence_id,
        evidence_type=EvidenceType.DECLARED,
        source_type=SourceType.ASYNCAPI,
        source_locator="invoice-service/asyncapi.yaml",
        source_revision=None,
        observation=None,
        supports=list(supports),
    )


def _support_row(evidence_ids, stable=STABLE, target=BROKER):
    return {
        "source_id": SERVICE,
        "target_id": target,
        "stable_broker_id": stable,
        "evidence_ids": evidence_ids,
    }


def test_no_returned_record_supporting_a_broker_keeps_the_v05_shape():
    assert to_broker_aware_records([_record(E1)], []) is None
    # a Broker relation whose evidence is not among the returned records does not count
    assert to_broker_aware_records([_record(E1)], [_support_row([E2])]) is None


def test_membership_not_presence_decides_which_record_supports_the_broker_fact():
    records = [_record(E1), _record(E2)]
    converted = to_broker_aware_records(records, [_support_row([E2])])
    assert converted is not None
    by_id = {r.id: r for r in converted}
    assert by_id[E1].supports == []
    [fact] = by_id[E2].supports
    assert fact.relation_type is EvidenceRelationTypeV06.USES_BROKER
    assert (fact.source_id, fact.target_id) == (SERVICE, BROKER)
    assert fact.broker is not None and (fact.broker.id, fact.broker.name) == (BROKER, STABLE)


def test_existing_facts_are_carried_over_and_supports_stay_sorted():
    calls = SupportedFact(
        relation_type=EvidenceRelationType.CALLS, source_id=SERVICE, target_id="operation:x"
    )
    converted = to_broker_aware_records([_record(E1, [calls])], [_support_row([E1])])
    assert converted is not None
    facts = converted[0].supports
    assert [f.relation_type.value for f in facts] == ["CALLS", "USES_BROKER"]
    assert facts[0].broker is None and facts[1].broker is not None


def test_broker_support_facts_dedupe_rows_for_the_same_pair():
    rows = [_support_row([E1]), _support_row([E1, E2])]
    assert len(broker_support_facts(rows, evidence_id=E1)) == 1
