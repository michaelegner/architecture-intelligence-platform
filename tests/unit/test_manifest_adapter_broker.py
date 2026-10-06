"""v0.6.1 I1c: the Architecture Manifest `brokers[].brokerId` block (spec §4.3). The manifest mints
no Service; with a non-empty `brokers` its Service must be declared by a phase-0 source, otherwise
the whole document is rejected (its `calls` and `brokers` both discarded)."""

import pytest

from app.canonical.model import ArchitectureModel, Service
from app.ingestion.manifest_adapter import ManifestSourceAdapter
from app.sources.model import DiagnosticCode, IngestionResult
from app.sources.owner_ids import broker_owned_id
from app.validation.source_validation import SourceValidationError, validate_manifest_document
from tests.unit.test_manifest_adapter import CALLER, _map, _upstream_with_operation

STABLE = "kafka:cluster-a"
BROKER_ID = broker_owned_id(stable_broker_id=STABLE)


def _doc(*broker_ids: str, **extra) -> dict:
    return {
        "service": "order-service",
        "x-aip-service-id": CALLER.id,
        "brokers": [{"brokerId": b} for b in broker_ids],
        **extra,
    }


def test_manifest_mapping_rule_version_is_bumped_for_the_new_block():
    assert ManifestSourceAdapter.mapping_rule_version == "v2"
    assert ManifestSourceAdapter.adapter_identity == "manifest-adapter@1"


def test_brokers_block_emits_broker_and_declared_uses_broker_without_minting_a_service():
    outcome = _map(_doc(STABLE))
    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.services == []
    [broker] = outcome.model.brokers
    assert (broker.id, broker.stable_broker_id) == (BROKER_ID, STABLE)
    [relation] = outcome.model.relations
    assert (relation.type, relation.source_id, relation.target_id) == (
        "USES_BROKER",
        CALLER.id,
        BROKER_ID,
    )
    assert relation.evidence_ids
    assert set(relation.evidence_ids) <= {p.id for p in outcome.model.provenance}


def test_duplicate_broker_ids_dedupe_and_distinct_ids_are_both_kept():
    deduped = _map(_doc(STABLE, STABLE))
    assert len(deduped.model.brokers) == 1
    assert len(deduped.model.relations) == 1

    other = "kafka:cluster-b"
    both = _map(_doc(STABLE, other))
    assert {b.stable_broker_id for b in both.model.brokers} == {STABLE, other}
    assert len(both.model.relations) == 2


def test_unresolved_service_rejects_the_whole_document_with_zero_artifacts():
    outcome = _map(_doc(STABLE), upstream_model=ArchitectureModel())
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.model == ArchitectureModel()
    assert outcome.semantic_input_digest is None
    [diagnostic] = outcome.diagnostics
    assert diagnostic.code is DiagnosticCode.MANIFEST_CALL_SOURCE_UNRESOLVED
    assert diagnostic.source_pointer == "/x-aip-service-id"


def test_unresolved_service_also_discards_the_calls_in_the_same_document():
    document = _doc(STABLE, calls=[{"service": "service:pricing", "operationId": "getPrice"}])
    upstream = _upstream_with_operation("service:pricing", "getPrice", "operation:p")
    resolved = _map(document, upstream_model=upstream)
    assert {r.type for r in resolved.model.relations} == {"CALLS", "USES_BROKER"}

    unresolved_upstream = ArchitectureModel(
        services=[Service(id="service:other", name="o")],
        operations=upstream.operations,
    )
    rejected = _map(document, upstream_model=unresolved_upstream)
    assert rejected.result is IngestionResult.REJECTED_UNSUPPORTED
    assert rejected.model == ArchitectureModel()


def test_empty_brokers_list_behaves_like_no_block():
    outcome = _map(_doc(), upstream_model=ArchitectureModel())
    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.brokers == [] and outcome.model.relations == []


@pytest.mark.parametrize(
    "brokers",
    [[{"brokerId": ""}], [{"brokerId": 7}], [{}], ["kafka:cluster-a"], "kafka:cluster-a"],
)
def test_malformed_broker_entries_reject_the_whole_document(brokers):
    document = {"service": "order-service", "x-aip-service-id": CALLER.id, "brokers": brokers}
    with pytest.raises(SourceValidationError):
        validate_manifest_document(document, source_file="architecture.yaml")
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert outcome.model == ArchitectureModel()


def test_broker_free_manifest_output_is_unchanged():
    upstream = _upstream_with_operation("service:pricing", "getPrice", "operation:p")
    outcome = _map(
        {
            "service": "order-service",
            "x-aip-service-id": CALLER.id,
            "calls": [{"service": "service:pricing", "operationId": "getPrice"}],
        },
        upstream_model=upstream,
    )
    assert outcome.model.brokers == []
    assert [r.type for r in outcome.model.relations] == ["CALLS"]
