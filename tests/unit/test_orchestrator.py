from pathlib import Path

import yaml

from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.identity import source_instance_id
from app.sources.inventory import InventoryStatus
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
)
from app.sources.model import FilesystemSourceConfig, IngestionResult, SourceKind

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _write(path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document))


def test_missing_root_is_failed_and_not_commit_eligible(tmp_path):
    config = FilesystemSourceConfig(id="x", root=tmp_path / "does-not-exist")
    result = run_filesystem_discovery(config)
    assert result.inventory_status is InventoryStatus.FAILED
    assert result.commit_eligible is False
    assert result.source_outcomes == {}


def test_empty_directory_is_complete_and_commit_eligible(tmp_path):
    config = FilesystemSourceConfig(id="x", root=tmp_path)
    result = run_filesystem_discovery(config)
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.commit_eligible is True
    assert result.merged_model.services == []


def test_a_malformed_document_fails_the_whole_run_not_just_that_source(tmp_path):
    """A parse failure must never be treated as "this source is legitimately absent" - reimporting
    a previously-valid source whose file has since become malformed (a corrupted read, a mid-edit
    save) must FAIL the run and commit nothing, not silently authorize deleting that source's prior
    facts as though it had simply stopped being declared (I1 spec §6)."""
    service_dir = tmp_path / "broken-service"
    service_dir.mkdir()
    (service_dir / "openapi.yaml").write_text("openapi: [unterminated")

    config = FilesystemSourceConfig(id="x", root=tmp_path)
    result = run_filesystem_discovery(config)

    assert result.inventory_status is InventoryStatus.FAILED
    assert result.commit_eligible is False
    assert result.merged_model.services == []
    assert result.source_outcomes == {}


def test_multi_service_multi_source_discovery(tmp_path):
    _write(
        tmp_path / "svc-a" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "A"},
            "x-aip-service-id": "service:a",
            "paths": {"/x": {"get": {"operationId": "getX", "responses": {"200": {}}}}},
        },
    )
    _write(
        tmp_path / "svc-b" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "B"},
            "x-aip-service-id": "service:b",
            "paths": {"/y": {"get": {"operationId": "getY", "responses": {"200": {}}}}},
        },
    )
    result = run_filesystem_discovery(FilesystemSourceConfig(id="multi", root=tmp_path))
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert {s.id for s in result.merged_model.services} == {"service:a", "service:b"}
    assert len(result.merged_model.operations) == 2


def test_one_rejected_source_blocks_commit_but_records_all_outcomes(tmp_path):
    _write(
        tmp_path / "good-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Good"},
            "x-aip-service-id": "service:good",
            "paths": {},
        },
    )
    _write(
        tmp_path / "bad-service" / "openapi.yaml",
        {"openapi": "3.1.0", "info": {"title": "Bad"}, "paths": {}},  # no Service identity
    )
    result = run_filesystem_discovery(FilesystemSourceConfig(id="mixed", root=tmp_path))
    assert result.inventory_status is InventoryStatus.PARTIAL
    assert result.commit_eligible is False
    results = {ro.outcome.result for ro in result.source_outcomes.values()}
    assert IngestionResult.ACCEPTED in results
    assert IngestionResult.REJECTED_UNSUPPORTED in results


def test_manifest_call_resolves_across_services(tmp_path):
    _write(
        tmp_path / "caller" / "architecture.yaml",
        {
            "service": "caller",
            "x-aip-service-id": "service:caller",
            "calls": [{"service": "service:callee", "operationId": "getThing"}],
        },
    )
    _write(
        tmp_path / "callee" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Callee"},
            "x-aip-service-id": "service:callee",
            "paths": {"/thing": {"get": {"operationId": "getThing", "responses": {"200": {}}}}},
        },
    )
    result = run_filesystem_discovery(FilesystemSourceConfig(id="calls", root=tmp_path))
    assert result.inventory_status is InventoryStatus.COMPLETE
    calls = [r for r in result.merged_model.relations if r.type == "CALLS"]
    assert len(calls) == 1
    assert calls[0].source_id == "service:caller"
    assert calls[0].target_id.startswith("operation:service:callee:GET:")


def test_architecture_identity_bindings_resolves_service_without_extension(tmp_path):
    _write(
        tmp_path / "svc" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "NoExtension"},
            "paths": {"/x": {"get": {"operationId": "getX", "responses": {"200": {}}}}},
        },
    )
    # The bound source's SourceInstanceId must be computed the same way the discoverer computes
    # it: configured_source_id + FILESYSTEM + normalized path relative to root.
    bound_id = source_instance_id(
        configured_source_id="bindings-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    _write(
        tmp_path / "bindings" / "architecture-identity-bindings.yaml",
        {
            "apiVersion": "aip.dev/v1",
            "kind": "ArchitectureIdentityBindings",
            "metadata": {"id": "bindings-1", "revision": "1"},
            "bindings": [
                {"sourceInstanceId": bound_id, "pointerPrefix": "", "serviceId": "service:bound"}
            ],
        },
    )
    result = run_filesystem_discovery(FilesystemSourceConfig(id="bindings-test", root=tmp_path))
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert {s.id for s in result.merged_model.services} == {"service:bound"}


def test_maps_real_bundled_examples_end_to_end():
    config = FilesystemSourceConfig(
        id="aip-bundled-examples-v0.5",
        root=EXAMPLES_DIR,
        stable_target_identity="urn:aip:logical-root:bundled-examples",
    )
    result = run_filesystem_discovery(config)

    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.commit_eligible is True
    assert all(
        ro.outcome.result is IngestionResult.ACCEPTED for ro in result.source_outcomes.values()
    )

    service_ids = {s.id for s in result.merged_model.services}
    assert service_ids == {
        "service:order-service",
        "service:product-service",
        "service:payment-service",
        "service:invoice-service",
    }
    queue_names = {q.name for q in result.merged_model.queues}
    assert queue_names == {
        "payment-q",
        "unused-q",
        "invoice-q",
        "unknown-producer-q",
        "payment-dlq",
    }
    calls = [r for r in result.merged_model.relations if r.type == "CALLS"]
    assert len(calls) == 1
    assert calls[0].source_id == "service:order-service"


def test_migration_mappings_parameter_is_accepted_and_defaults_to_a_no_op(tmp_path):
    """The SharedIdentityResolver seam is wired end to end in this PR's commit 4, but no adapter
    consults it yet (that lands in a later commit) - passing a real, non-empty index today must be
    accepted without error and must not change the result, proving the plumbing alone is inert."""
    _write(
        tmp_path / "svc" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Svc"},
            "x-aip-service-id": "service:svc",
            "paths": {"/x": {"get": {"operationId": "getX", "responses": {"200": {}}}}},
        },
    )
    config = FilesystemSourceConfig(id="migtest", root=tmp_path)

    without_mappings = run_filesystem_discovery(config)

    sid = source_instance_id(
        configured_source_id="migtest",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="unrelated-artifact",
                artifact_revision="v1",
                locator="migrations.yaml",
                schema_mappings=(
                    IdentityMappingEntry(
                        source_instance_id=sid,
                        pointer="/components/schemas/Nonexistent",
                        pointer_tokens=("components", "schemas", "Nonexistent"),
                        target_id="schema:Nonexistent",
                    ),
                ),
            )
        ]
    )
    assert diagnostics == []
    assert index != EMPTY_SHARED_IDENTITY_INDEX

    with_mappings = run_filesystem_discovery(config, migration_mappings=index)

    assert with_mappings.inventory_status == without_mappings.inventory_status
    assert with_mappings.merged_model == without_mappings.merged_model
