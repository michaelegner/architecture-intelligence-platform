"""I1 spec §11 Definition of Done: "two clean checkouts at different absolute paths derive the
fixed bundled-example scope/source IDs and apply the same Service/Schema/Message/Queue migration
mappings" and "equivalent runs... produce byte-identical semantic reports." Deliberately pure
Python (no Neo4j) - this is a discovery/mapping-layer determinism proof, not a graph-write one
(the graph-write side is separately covered by
`tests/integration/test_importer.py::test_import_all_sources_with_the_real_bundled_migration_mapping_lands_legacy_ids`).
Lives under `tests/integration/` rather than `tests/unit/` because it exercises the real, checked-in
`examples/` tree and the real, checked-in migration artifact end to end, not a synthetic fixture.
"""

import shutil
from pathlib import Path

from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.identity import source_instance_id
from app.sources.inventory import InventoryStatus
from app.sources.jcs import canonical_json_bytes
from app.sources.migration_mappings import load_migration_mappings
from app.sources.model import DiagnosticCode, FilesystemSourceConfig, SourceKind

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
MIGRATIONS_PATH = REPO_ROOT / "config" / "migrations" / "v0.5.0-bundled-example-identities.yaml"

CONFIGURED_SOURCE_ID = "aip-bundled-examples-v0.5"
STABLE_TARGET_IDENTITY = "urn:aip:logical-root:bundled-examples"


def _config(root: Path) -> FilesystemSourceConfig:
    return FilesystemSourceConfig(
        id=CONFIGURED_SOURCE_ID, root=root, stable_target_identity=STABLE_TARGET_IDENTITY
    )


def _canonical_merged_model_bytes(model) -> bytes:
    """§10: "byte-identical canonical JSON for this projection even when audit captures differ."
    `provenance[].source_file` is the source's own absolute locator (I1 spec §6's audit trail, not
    a semantic fact) and legitimately differs between two checkouts at different physical paths -
    excluded here the same way §10 itself excludes capture-specific audit detail from the
    byte-identity comparison. Every claimed fact (services/operations/queues/messages/schemas/
    relations, including each relation's portable evidence_ids) is still compared in full.
    """
    return canonical_json_bytes(model.model_dump(mode="json", exclude={"provenance"}))


def test_the_real_migration_artifact_loads_without_diagnostics():
    _, diagnostics = load_migration_mappings([MIGRATIONS_PATH])
    assert diagnostics == ()


def test_two_clean_checkouts_at_different_paths_produce_identical_results(tmp_path):
    checkout_one = tmp_path / "checkout-one" / "examples"
    checkout_two = tmp_path / "somewhere" / "else" / "checkout-two" / "examples"
    shutil.copytree(EXAMPLES_DIR, checkout_one)
    shutil.copytree(EXAMPLES_DIR, checkout_two)
    index, diagnostics = load_migration_mappings([MIGRATIONS_PATH])
    assert diagnostics == ()

    result_one = run_filesystem_discovery(_config(checkout_one), migration_mappings=index)
    result_two = run_filesystem_discovery(_config(checkout_two), migration_mappings=index)

    assert result_one.inventory_status == result_two.inventory_status
    assert result_one.commit_eligible is True
    assert result_one.commit_eligible == result_two.commit_eligible
    # discovery_scope_id is the portable identity (derived from the configured scope id/stable
    # target identity, never the physical path); scope_definition_digest is deliberately NOT
    # required to be portable - it also captures the normalized *root path itself* (I1 spec §6:
    # "changing roots/filters preserves DiscoveryScopeId and changes only scope_definition_digest"),
    # so two different absolute checkout paths legitimately produce two different digests here.
    assert result_one.discovery_scope_id == result_two.discovery_scope_id

    # SourceInstanceIds must be identical across checkout paths - the whole point of §5.1.1's
    # portability requirement, since the id formula never depends on the physical root.
    ids_one = set(result_one.source_outcomes.keys())
    ids_two = set(result_two.source_outcomes.keys())
    assert ids_one == ids_two
    expected_sid = source_instance_id(
        configured_source_id=CONFIGURED_SOURCE_ID,
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="order-service/openapi.yaml",
    )
    assert expected_sid in ids_one

    # Byte-identical canonical JSON for the merged model - the DoD's own "byte-identical semantic
    # reports" requirement, proven at the discovery/mapping layer.
    assert _canonical_merged_model_bytes(result_one.merged_model) == _canonical_merged_model_bytes(
        result_two.merged_model
    )

    # Every semantic_input_digest is also identical - the mapping context (which now includes the
    # real migration mapping content) must not vary with the physical checkout path either.
    digests_one = {
        sid: ro.outcome.semantic_input_digest for sid, ro in result_one.source_outcomes.items()
    }
    digests_two = {
        sid: ro.outcome.semantic_input_digest for sid, ro in result_two.source_outcomes.items()
    }
    assert digests_one == digests_two


def test_applying_the_real_migration_reproduces_the_exact_legacy_ids(tmp_path):
    checkout = tmp_path / "examples"
    shutil.copytree(EXAMPLES_DIR, checkout)
    index, diagnostics = load_migration_mappings([MIGRATIONS_PATH])
    assert diagnostics == ()

    result = run_filesystem_discovery(_config(checkout), migration_mappings=index)

    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.commit_eligible is True
    schema_ids = {s.id for s in result.merged_model.schemas}
    message_ids = {m.id for m in result.merged_model.messages}
    queue_ids = {q.id for q in result.merged_model.queues}

    assert schema_ids == {
        "schema:OrderRequest",
        "schema:Order",
        "schema:Product",
        "schema:PaymentRequested:v2",
        "schema:InvoiceCreated:v1",
        "schema:UnusedMessage",
        "schema:UnknownProducerMessage",
    }
    assert message_ids == {
        "message:PaymentRequested:v2",
        "message:InvoiceCreated:v1",
        "message:UnusedMessage",
        "message:UnknownProducerMessage",
    }
    assert queue_ids == {
        "queue:payment-q",
        "queue:unused-q",
        "queue:invoice-q",
        "queue:unknown-producer-q",
        "queue:payment-dlq",
    }

    # The real cross-source merges: PaymentRequested (order-service + payment-service) and
    # InvoiceCreated (payment-service + invoice-service) each collapse onto ONE shared legacy id,
    # not two distinct owner-scoped ones.
    assert len(schema_ids) == 7
    assert len(message_ids) == 4


def test_a_genuine_cross_source_content_conflict_rejects_the_whole_run(tmp_path):
    """Mutating one service's shared-schema payload so it disagrees with the other source
    explicitly mapped to the same legacy id must reject the whole run - the real, non-synthetic
    proof that app.sources.claim_conflicts fires against real bundled fixtures, not just isolated
    unit fixtures."""
    checkout = tmp_path / "examples"
    shutil.copytree(EXAMPLES_DIR, checkout)
    order_asyncapi = checkout / "order-service" / "asyncapi.yaml"
    content = order_asyncapi.read_text()
    # PaymentRequestedPayload originally requires [orderId, amount] - narrow it to just [orderId]
    # so it disagrees with payment-service's copy of the same payload shape.
    mutated = content.replace("      required: [orderId, amount]\n", "      required: [orderId]\n")
    assert mutated != content
    order_asyncapi.write_text(mutated)

    index, diagnostics = load_migration_mappings([MIGRATIONS_PATH])
    assert diagnostics == ()

    result = run_filesystem_discovery(_config(checkout), migration_mappings=index)

    assert result.commit_eligible is False
    assert result.merged_model.schemas == []
    assert any(d.code is DiagnosticCode.SCHEMA_CONTENT_CONFLICT for d in result.diagnostics)
    # Each individual source's own outcome is still recorded - only the cross-source combination
    # is rejected.
    assert len(result.source_outcomes) == 6
