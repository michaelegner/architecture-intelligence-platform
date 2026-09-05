"""v0.4.0 I2.3 - pure projection from raw evidence/relation rows (`repository.read_evidence_rows`)
to `EvidenceRecord`s (spec §11.2). No Neo4j access, no outcome decision - mirrors
`dependency_projection.py`'s boundary: plain dicts in, contract models out.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.architecture_intelligence.contracts import (
    EvidenceRecord,
    EvidenceRelationType,
    ObservedEvidenceMetadata,
    SupportedFact,
)
from app.provenance.model import EvidenceType, SourceType


def _supported_fact_sort_key(fact: SupportedFact) -> tuple[str, str, str]:
    return (fact.relation_type.value, fact.source_id, fact.target_id)


def sanitize_source_locator(source_file: str | None) -> str | None:
    """Spec §11.2: return `source_file` unchanged only when it is the literal `opentelemetry` or a
    relative POSIX-style path containing no empty, `.` or `..` segment; otherwise `None`. Never
    rewrites an absolute path into a plausible public path, and never returns URI user-info, query
    parameters or fragments - those simply fail the "relative POSIX path" test and become `None`."""
    if source_file is None:
        return None
    if source_file == "opentelemetry":
        return source_file
    if (
        source_file.startswith("/")
        or "\\" in source_file
        or "?" in source_file
        or "#" in source_file
    ):
        return None
    segments = source_file.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return None
    return source_file


def _build_supported_facts(relations: list[dict], *, evidence_id: str) -> list[SupportedFact]:
    facts = {
        SupportedFact(
            relation_type=EvidenceRelationType(relation["type"]),
            source_id=relation["source_id"],
            target_id=relation["target_id"],
        )
        for relation in relations
        if evidence_id in relation["evidence_ids"]
    }
    return sorted(facts, key=_supported_fact_sort_key)


def _build_evidence_record(row: dict, *, supports: list[SupportedFact]) -> EvidenceRecord:
    evidence_type = EvidenceType(row["evidence_type"])
    observation = None
    if evidence_type == EvidenceType.OBSERVED:
        observation = ObservedEvidenceMetadata(
            environment=row["environment"],
            bucket_start=row["bucket_start"],
            bucket_end=row["bucket_end"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            observation_count=row["observation_count"],
            service_version=row.get("service_version"),
            correlation_mode=row.get("correlation_mode"),
        )
    return EvidenceRecord(
        id=row["id"],
        evidence_type=evidence_type,
        source_type=SourceType(row["source_type"]),
        source_locator=sanitize_source_locator(row.get("source_file")),
        source_revision=row.get("source_revision"),
        observation=observation,
        supports=supports,
    )


@dataclass(frozen=True)
class EvidenceProjectionResult:
    records: list[EvidenceRecord]
    missing_evidence_refs: list[str]


def project_evidence(rows: dict, *, requested_ids: list[str]) -> EvidenceProjectionResult:
    """`requested_ids` MUST already be sorted and deduplicated (the service layer guarantees this
    before calling in). Every id present in `rows["evidence"]` becomes a record; every other id is
    reported missing - together they exactly partition `requested_ids`, satisfying `EvidenceData`'s
    own partition invariant."""
    evidence_by_id = rows["evidence"]
    relations = rows["relations"]

    records = [
        _build_evidence_record(
            evidence_by_id[evidence_id],
            supports=_build_supported_facts(relations, evidence_id=evidence_id),
        )
        for evidence_id in requested_ids
        if evidence_id in evidence_by_id
    ]
    missing_evidence_refs = [
        evidence_id for evidence_id in requested_ids if evidence_id not in evidence_by_id
    ]

    return EvidenceProjectionResult(records=records, missing_evidence_refs=missing_evidence_refs)
