"""v0.6.1 I2c - the Broker public projection (spec §5): `BrokerClaim`s for `get_service_dependencies`
and Broker-aware `get_evidence` records. Pure functions over the plain rows
`repository.read_service_broker_rows` / `read_broker_support_rows` return - no Neo4j access and no
public outcome decision (that stays `service.py`'s job), mirroring `dependency_projection.py`.

A Broker claim is not a dependency: it carries no delivery, runtime qualification or coverage, and
it never creates or implies a Queue, Topic, Subscription, Message, producer or consumer claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.architecture_intelligence.broker_contracts import (
    BrokerClaim,
    BrokerEntityType,
    BrokerPredicate,
    BrokerRef,
    EvidenceRecordV06,
    EvidenceRelationTypeV06,
    SupportedFactV06,
    supported_fact_v06_sort_key,
)
from app.architecture_intelligence.canonical_json import canonical_digest
from app.architecture_intelligence.contracts import (
    CLAIM_ID_PREFIX,
    EntityRef,
    EntityType,
    EvidenceRecord,
    Limitation,
    LimitationCode,
)


def compute_broker_claim_id(*, service_id: str, broker_id: str) -> str:
    """`aip:claim:v1:sha256(canonical-json({"predicate": "USES_BROKER", "service_id", "broker_id"}))`
    (spec §5.1). Evidence ids, the snapshot id and display names are deliberately excluded, so the
    claim identity follows the Service/Broker pair and not the evidence that currently supports it
    (the dependency-claim rule; the deployment claim id is shaped the same way). The predicate is a
    hashed field so a Broker claim id can never collide with another claim kind's."""
    digest = canonical_digest(
        {
            "predicate": BrokerPredicate.USES_BROKER.value,
            "service_id": service_id,
            "broker_id": broker_id,
        }
    )
    return f"{CLAIM_ID_PREFIX}:{digest}"


@dataclass(frozen=True)
class BrokerProjectionResult:
    claims: list[BrokerClaim]
    limitations: list[Limitation]


def project_broker_claims(
    rows: dict, *, service_id: str, service_name: str
) -> BrokerProjectionResult:
    """One `BrokerClaim` per distinct Broker the service is declared to use.

    `rows["broker_uses"]` holds one row per `USES_BROKER` relation; `rows["evidence"]` maps the
    evidence ids that resolve in this snapshot to their rows. A claim's evidence is the *union* of
    the evidence ids of every row for the same Broker (never one row overwriting another), kept to
    the ids that actually resolve (membership of the specific id, not mere presence of ids). A
    Broker with no resolvable evidence yields no claim - an unevidenced claim is not allowed - and
    one `INSUFFICIENT_EVIDENCE` limitation, the same rule `dependency_projection` applies to a
    dependency with no usable evidence."""
    evidence_by_id = rows["evidence"]
    refs_by_broker: dict[str, set[str]] = {}
    stable_id_by_broker: dict[str, str] = {}
    for row in rows["broker_uses"]:
        refs_by_broker.setdefault(row["broker_id"], set()).update(row["evidence_ids"])
        stable_id_by_broker[row["broker_id"]] = row["stable_broker_id"]

    subject = EntityRef(id=service_id, type=EntityType.SERVICE, name=service_name)
    claims: list[BrokerClaim] = []
    limitations: list[Limitation] = []
    for broker_id in sorted(refs_by_broker):
        resolved = sorted(ref for ref in refs_by_broker[broker_id] if ref in evidence_by_id)
        if not resolved:
            limitations.append(
                Limitation(
                    code=LimitationCode.INSUFFICIENT_EVIDENCE,
                    # Deliberately names only the Service: when no Broker claim results the answer
                    # stays the v0.5 shape, which must not carry Broker identifiers (spec §5.2).
                    message=(
                        f"a declared Broker use of {service_id} has no resolvable evidence; no "
                        "Broker claim was created."
                    ),
                    claim_ids=[],
                )
            )
            continue
        claims.append(
            BrokerClaim(
                claim_id=compute_broker_claim_id(service_id=service_id, broker_id=broker_id),
                subject=subject,
                predicate=BrokerPredicate.USES_BROKER,
                object=BrokerRef(
                    id=broker_id,
                    type=BrokerEntityType.BROKER,
                    name=stable_id_by_broker[broker_id],
                ),
                evidence_refs=resolved,
            )
        )
    return BrokerProjectionResult(claims=claims, limitations=limitations)


def broker_support_facts(
    broker_support_rows: list[dict], *, evidence_id: str
) -> list[SupportedFactV06]:
    """The `USES_BROKER` supported facts one returned evidence record supports: every relation row
    whose `evidence_ids` *contains this id* (membership, not the presence of any ids)."""
    facts = {
        SupportedFactV06(  # pyright: ignore[reportUnhashable]  (frozen pydantic model: hashable at runtime, not modeled by pyright)
            relation_type=EvidenceRelationTypeV06.USES_BROKER,
            source_id=row["source_id"],
            target_id=row["target_id"],
            broker=BrokerRef(
                id=row["target_id"],
                type=BrokerEntityType.BROKER,
                name=row["stable_broker_id"],
            ),
        )
        for row in broker_support_rows
        if evidence_id in row["evidence_ids"]
    }
    return sorted(facts, key=supported_fact_v06_sort_key)


def to_broker_aware_records(
    records: list[EvidenceRecord], broker_support_rows: list[dict]
) -> list[EvidenceRecordV06] | None:
    """The Broker-aware (v0.6) form of the already-built v0.5 evidence records, or `None` when no
    returned record supports a `USES_BROKER` fact (spec §5.2: the answer then stays the v0.5 shape).
    Every v0.5 supported fact is carried over unchanged (with a null `broker`); the `USES_BROKER`
    facts are added, and `supports` stays sorted and deduplicated."""
    added = {
        record.id: broker_support_facts(broker_support_rows, evidence_id=record.id)
        for record in records
    }
    if not any(added.values()):
        return None
    records_v06: list[EvidenceRecordV06] = []
    for record in records:
        carried = {
            SupportedFactV06(  # pyright: ignore[reportUnhashable]  (frozen pydantic model: hashable at runtime, not modeled by pyright)
                relation_type=EvidenceRelationTypeV06(fact.relation_type.value),
                source_id=fact.source_id,
                target_id=fact.target_id,
                broker=None,
            )
            for fact in record.supports
        }
        supports = sorted(
            {*carried, *added[record.id]},  # pyright: ignore[reportUnhashable]  (same as above)
            key=supported_fact_v06_sort_key,
        )
        records_v06.append(
            EvidenceRecordV06(
                id=record.id,
                evidence_type=record.evidence_type,
                source_type=record.source_type,
                source_locator=record.source_locator,
                source_revision=record.source_revision,
                observation=record.observation,
                supports=supports,
            )
        )
    return records_v06
