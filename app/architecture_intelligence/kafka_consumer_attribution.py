"""v0.7.1 I2.2-I2.3: Kafka consumer-group -> Service reconciliation, rule
`kafka-consumer-attribution` / `1` (I2.1 contract §6-§9), and the `kafka_consumer_attribution_v1`
snapshot block built from it. Pure: no graph access, no persistence. The snapshot projection reads
the declared Services, the mapping carriers and the I1 attachments of one snapshot, adds the
configured aliases and calls `attribution_block`; nothing here is ever written back.

Each mapping entry resolves its Service through the shared `decide_service_identity` guard against
the declared Services only. A guard result that would mint an observed-only Service is read as
`SERVICE_NOT_DECLARED`: nothing is minted, and no Service id from it ever leaves this module.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.canonical.kafka_service_mapping import KafkaServiceMappingEntry
from app.telemetry.messaging_guards import (
    AMBIGUOUS_SERVICE_IDENTITY,
    CONFLICTING_SERVICE_IDENTITY,
    PLACEHOLDER_SERVICE_IDENTITY,
    decide_service_identity,
)
from app.telemetry.model import DiscoveryStatus
from app.telemetry.service_resolver import DeclaredServiceCandidate

RULE_ID = "kafka-consumer-attribution"
RULE_VERSION = "1"


class AttributionOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"


class AttributionReason(StrEnum):
    SERVICE_IDENTITY_CONFLICT = "SERVICE_IDENTITY_CONFLICT"
    MAPPING_SOURCE_DISAGREEMENT = "MAPPING_SOURCE_DISAGREEMENT"
    SERVICE_IDENTITY_AMBIGUOUS = "SERVICE_IDENTITY_AMBIGUOUS"
    SERVICE_NOT_DECLARED = "SERVICE_NOT_DECLARED"
    SERVICE_IDENTITY_PLACEHOLDER = "SERVICE_IDENTITY_PLACEHOLDER"
    NO_MAPPING = "NO_MAPPING"


# Keyed by `str | None` so an unexpected refusal (or none at all) fails loudly with a KeyError.
_REASON_BY_REFUSAL: dict[str | None, AttributionReason] = {
    PLACEHOLDER_SERVICE_IDENTITY: AttributionReason.SERVICE_IDENTITY_PLACEHOLDER,
    AMBIGUOUS_SERVICE_IDENTITY: AttributionReason.SERVICE_IDENTITY_AMBIGUOUS,
    CONFLICTING_SERVICE_IDENTITY: AttributionReason.SERVICE_IDENTITY_CONFLICT,
}

# Contract §7: when no entry resolves and none is ambiguous, the group reason is the first of these
# that any entry carries.
_UNRESOLVED_REASON_ORDER = (
    AttributionReason.SERVICE_NOT_DECLARED,
    AttributionReason.SERVICE_IDENTITY_PLACEHOLDER,
)


@dataclass(frozen=True)
class EntryReading:
    """One mapping entry's guard result: a declared Service id, or the reason it has none."""

    entry_id: str
    service_id: str | None
    reason: AttributionReason | None


@dataclass(frozen=True)
class GroupReconciliation:
    """The outcome for one consumer identity (join key). `service_id` is set only when RESOLVED;
    `limitations` lists the non-resolving entries of a RESOLVED group; `entries` keeps every
    contributing entry's own reading, sorted by entry id."""

    consumer_id: str
    group_id: str
    outcome: AttributionOutcome
    reason: AttributionReason | None
    service_id: str | None
    entries: tuple[EntryReading, ...]
    limitations: tuple[EntryReading, ...]


def declared_candidates(rows: Iterable[Mapping[str, Any]]) -> list[DeclaredServiceCandidate]:
    """Contract §6: the Service rows (`id`, `name`, `namespace`, `owner_source_ids`) owned by at least
    one declared source. A runtime-only stub has no owner and is never a candidate."""
    return [
        DeclaredServiceCandidate(row["id"], row["name"], row["namespace"])
        for row in rows
        if row["owner_source_ids"]
    ]


def resolve_entry(
    entry: KafkaServiceMappingEntry,
    *,
    candidates: Sequence[DeclaredServiceCandidate],
    aliases: Mapping[str, str],
) -> EntryReading:
    decision = decide_service_identity(
        list(candidates),
        service_name=entry.service_name,
        service_namespace=entry.service_namespace,
        aliases=dict(aliases),
    )
    if decision.accepted and decision.discovery_status == DiscoveryStatus.DECLARED:
        return EntryReading(entry.id, decision.service_id, None)
    if decision.accepted:
        return EntryReading(entry.id, None, AttributionReason.SERVICE_NOT_DECLARED)
    return EntryReading(entry.id, None, _REASON_BY_REFUSAL[decision.refusal_reason])


def _reconcile(
    consumer_id: str, group_id: str, readings: tuple[EntryReading, ...]
) -> GroupReconciliation:
    def group(
        outcome: AttributionOutcome,
        reason: AttributionReason | None = None,
        service_id: str | None = None,
        limitations: Sequence[EntryReading] = (),
    ) -> GroupReconciliation:
        return GroupReconciliation(
            consumer_id, group_id, outcome, reason, service_id, readings, tuple(limitations)
        )

    if not readings:
        return group(AttributionOutcome.UNRESOLVED, AttributionReason.NO_MAPPING)
    reasons = {reading.reason for reading in readings}
    if AttributionReason.SERVICE_IDENTITY_CONFLICT in reasons:
        return group(AttributionOutcome.CONFLICT, AttributionReason.SERVICE_IDENTITY_CONFLICT)
    resolved = {reading.service_id for reading in readings if reading.service_id is not None}
    if len(resolved) > 1:
        return group(AttributionOutcome.CONFLICT, AttributionReason.MAPPING_SOURCE_DISAGREEMENT)
    if resolved:
        [service_id] = resolved
        limitations = [reading for reading in readings if reading.service_id is None]
        return group(AttributionOutcome.RESOLVED, service_id=service_id, limitations=limitations)
    if AttributionReason.SERVICE_IDENTITY_AMBIGUOUS in reasons:
        return group(AttributionOutcome.AMBIGUOUS, AttributionReason.SERVICE_IDENTITY_AMBIGUOUS)
    reason = next(reason for reason in _UNRESOLVED_REASON_ORDER if reason in reasons)
    return group(AttributionOutcome.UNRESOLVED, reason)


def reconcile_groups(
    entries: Sequence[KafkaServiceMappingEntry],
    *,
    attached_groups: Mapping[str, str],
    candidates: Sequence[DeclaredServiceCandidate],
    aliases: Mapping[str, str],
) -> tuple[GroupReconciliation, ...]:
    """Contract §7, per join key over every accepted entry of every mapping source.
    `attached_groups` maps the consumer id of each I1 attachment to its exact group id, so a group
    that is attached but has no entry still gets its `NO_MAPPING` row. Sorted by consumer id."""
    by_consumer: dict[str, list[KafkaServiceMappingEntry]] = defaultdict(list)
    for entry in entries:
        by_consumer[entry.consumer_id].append(entry)
    group_ids = dict(attached_groups)
    for consumer_id, grouped in by_consumer.items():
        group_ids[consumer_id] = grouped[0].group_id
    return tuple(
        _reconcile(
            consumer_id,
            group_ids[consumer_id],
            tuple(
                sorted(
                    (
                        resolve_entry(entry, candidates=candidates, aliases=aliases)
                        for entry in by_consumer.get(consumer_id, ())
                    ),
                    key=lambda reading: reading.entry_id,
                )
            ),
        )
        for consumer_id in sorted(group_ids)
    )


def _present(row: dict[str, Any]) -> dict[str, Any]:
    """The snapshot's null rule: an absent value is omitted, never written as null."""
    return {key: value for key, value in row.items() if value is not None}


def _value(reason: AttributionReason | None) -> str | None:
    """Plain strings in the snapshot, never enum members."""
    return None if reason is None else reason.value


def _reading_row(reading: EntryReading, evidence_ids: Sequence[str]) -> dict[str, Any]:
    return _present(
        {
            "id": reading.entry_id,
            "evidence_ids": sorted(evidence_ids),
            "service_id": reading.service_id,
            "reason": _value(reading.reason),
        }
    )


def attribution_block(
    *,
    sources: Sequence[Mapping[str, Any]],
    entries: Sequence[Mapping[str, Any]],
    attachments: Sequence[Mapping[str, Any]],
    consumer_groups: Sequence[Mapping[str, Any]],
    service_rows: Iterable[Mapping[str, Any]],
    aliases: Mapping[str, str],
) -> dict[str, Any]:
    """Contract §8-§9: the `kafka_consumer_attribution_v1` block from one snapshot's rows - the
    mapping evidence and entry rows, the I1 attachment and consumer-group rows, the Service rows
    (with `owner_source_ids`) and the configured aliases. Every section is sorted, so the block does
    not depend on the order its inputs were read in.

    `aliases_applied` keeps only the aliases whose key is some entry's `service_name`: exactly the
    configuration the outcome can depend on, so the block can be re-derived from the snapshot alone.
    `service_id` appears only on a RESOLVED group or attribution; nothing is ever a negative claim."""
    mapping_entries = sorted(
        (KafkaServiceMappingEntry.model_validate(row) for row in entries), key=lambda e: e.id
    )
    evidence_of = {entry.id: entry.evidence_ids for entry in mapping_entries}
    group_of = {row["id"]: row["group_id"] for row in consumer_groups}
    attached = {row["consumer_id"]: group_of[row["consumer_id"]] for row in attachments}
    groups = reconcile_groups(
        mapping_entries,
        attached_groups=attached,
        candidates=declared_candidates(service_rows),
        aliases=aliases,
    )

    def outcome_fields(group: GroupReconciliation) -> dict[str, Any]:
        return {
            "outcome": group.outcome.value,
            "reason": _value(group.reason),
            "service_id": group.service_id,
            "limitations": [
                {"entry_id": reading.entry_id, "reason": _value(reading.reason)}
                for reading in group.limitations
            ],
        }

    by_consumer = {group.consumer_id: group for group in groups}
    used_names = {entry.service_name for entry in mapping_entries}
    return {
        "rule": {"id": RULE_ID, "version": RULE_VERSION},
        "mapping_sources": sorted((dict(row) for row in sources), key=lambda row: row["id"]),
        "mapping_entries": [entry.model_dump(exclude_none=True) for entry in mapping_entries],
        "aliases_applied": [
            {"alias": alias, "service_id": aliases[alias]}
            for alias in sorted(aliases)
            if alias in used_names
        ],
        "groups": [
            _present(
                {
                    "id": group.consumer_id,
                    "group_id": group.group_id,
                    **outcome_fields(group),
                    "entries": [
                        _reading_row(reading, evidence_of[reading.entry_id])
                        for reading in group.entries
                    ],
                }
            )
            for group in groups
        ],
        "attributions": sorted(
            (
                _present(
                    {
                        "id": row["id"],
                        "consumer_id": row["consumer_id"],
                        "topic_id": row["topic_id"],
                        "captured_at": row["captured_at"],
                        **outcome_fields(group),
                        "attachment_evidence_ids": sorted(row["evidence_ids"]),
                        "mapping_entries": [
                            {
                                "id": reading.entry_id,
                                "evidence_ids": sorted(evidence_of[reading.entry_id]),
                            }
                            for reading in group.entries
                        ],
                    }
                )
                for row in attachments
                for group in (by_consumer[row["consumer_id"]],)
            ),
            key=lambda row: row["id"],
        ),
    }
