from pathlib import Path

import pytest
import yaml

from app.canonical.infrastructure import (
    InfrastructureClaim,
    InfrastructureClaimKind,
    InfrastructureContribution,
    InfrastructureEntity,
    InfrastructureEntityKind,
    KubernetesEvidenceMode,
)
from app.canonical.model import ArchitectureModel
from app.ingestion.orchestrator import merge_models, run_discovery, run_filesystem_discovery
from app.sources.identity import source_instance_id
from app.sources.inventory import InventoryStatus
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
    load_migration_mappings,
)
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import AdapterOutcome, DiscoveryOutcome, SourceAdapterRegistry
from app.sources.tombstones import Tombstone

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
    # I2 Draft 0.2 §3/§8: a snapshot is required for every attempt, including a failed one - the
    # scope id/digest are pure functions of configured values, computable even when the root
    # doesn't exist (a real bug found in review: this used to emit no snapshot at all here).
    assert result.inventory_snapshot is not None
    assert result.inventory_snapshot.status is InventoryStatus.FAILED
    assert result.discovery_scope_id is not None
    assert result.inventory_snapshot.discovery_scope_id == result.discovery_scope_id


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
    """A migration mapping whose pointer matches nothing in this document must not change the
    result at all - proves the resolver seam is a true no-op for a source it doesn't apply to,
    not just "doesn't crash"."""
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
                content_digest="test-content-digest",
                schema_mappings=(
                    IdentityMappingEntry(
                        source_instance_id=sid,
                        document_path="svc/openapi.yaml",
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


def _single_schema_openapi_doc(schema_body: dict) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Svc"},
        "x-aip-service-id": "service:svc",
        "paths": {
            "/x": {
                "get": {
                    "operationId": "getX",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/X"}}
                            }
                        }
                    },
                }
            }
        },
        "components": {"schemas": {"X": schema_body}},
    }


def test_a_real_migration_mapping_changes_the_mapping_context_digest(tmp_path):
    """Regression proof that _compute_mapping_context_digest now has real, non-empty content to
    hash: two runs of the byte-identical document, differing only in whether a migration mapping
    file is configured, must produce different semantic_input_digest values (the mapping context is
    part of that digest's own input), even though the mapping's target pointer matches this
    document's own schema and produces no merge/identity error."""
    _write(tmp_path / "svc" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"}))
    config = FilesystemSourceConfig(id="digest-test", root=tmp_path)

    without_mappings = run_filesystem_discovery(config)
    [outcome_without] = without_mappings.source_outcomes.values()

    sid = source_instance_id(
        configured_source_id="digest-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="aip-v0.5.0-bundled-example-identities-v1",
                artifact_revision="v1",
                locator="migrations.yaml",
                content_digest="test-content-digest",
                schema_mappings=(
                    IdentityMappingEntry(
                        source_instance_id=sid,
                        document_path="svc/openapi.yaml",
                        pointer="/components/schemas/X",
                        pointer_tokens=("components", "schemas", "X"),
                        target_id="schema:X",
                    ),
                ),
            )
        ]
    )
    assert diagnostics == []

    with_mappings = run_filesystem_discovery(config, migration_mappings=index)
    [outcome_with] = with_mappings.source_outcomes.values()

    assert (
        outcome_without.outcome.semantic_input_digest != outcome_with.outcome.semantic_input_digest
    )
    assert outcome_with.outcome.model.schemas[0].id == "schema:X"


def test_a_document_path_only_change_still_changes_the_mapping_context_digest(tmp_path):
    """Regression proof that documentPath is included in the mapping-context digest projection:
    two configured mappings that are byte-identical except for documentPath ("svc/openapi.yaml" vs.
    "svc/other.yaml") must still produce different semantic_input_digest values, even though the
    document under discovery hasn't changed at all. documentPath is part of each entry's own lookup
    identity (source_instance_id, document_path, pointer) - moving an otherwise identical mapping to
    a different file changes which canonical entity would receive its id, so the revision fence must
    be able to notice that configuration change even when this particular document's own real
    location happens to make it a no-op for the model it produces."""
    _write(tmp_path / "svc" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"}))
    config = FilesystemSourceConfig(id="digest-path-test", root=tmp_path)

    sid = source_instance_id(
        configured_source_id="digest-path-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )

    def _index_for(document_path: str):
        index, diagnostics = build_shared_identity_index(
            [
                MigrationMappingsDocument(
                    artifact_id="aip-v0.5.0-bundled-example-identities-v1",
                    artifact_revision="v1",
                    locator="migrations.yaml",
                    content_digest="test-content-digest",
                    schema_mappings=(
                        IdentityMappingEntry(
                            source_instance_id=sid,
                            document_path=document_path,
                            pointer="/components/schemas/X",
                            pointer_tokens=("components", "schemas", "X"),
                            target_id="schema:X",
                        ),
                    ),
                )
            ]
        )
        assert diagnostics == []
        return index

    from_svc = run_filesystem_discovery(config, migration_mappings=_index_for("svc/openapi.yaml"))
    from_other = run_filesystem_discovery(config, migration_mappings=_index_for("svc/other.yaml"))
    [outcome_svc] = from_svc.source_outcomes.values()
    [outcome_other] = from_other.source_outcomes.values()

    assert outcome_svc.outcome.semantic_input_digest != outcome_other.outcome.semantic_input_digest
    # The documentPath that actually matches this document's own real location is the one whose
    # mapping takes effect - the other is configured for a file that doesn't exist here at all.
    assert outcome_svc.outcome.model.schemas[0].id == "schema:X"
    assert outcome_other.outcome.model.schemas[0].id != "schema:X"


def _bundled_mapping_document(sid: str) -> dict:
    return {
        "apiVersion": "aip.dev/v1",
        "kind": "AipSharedIdentityMappings",
        "metadata": {"id": "aip-v0.5.0-bundled-example-identities-v1", "revision": "v1"},
        "schemaMappings": [
            {
                "sourceInstanceId": sid,
                "documentPath": "svc/openapi.yaml",
                "pointer": "/components/schemas/X",
                "schemaId": "schema:X",
            }
        ],
    }


def test_a_content_digest_only_change_still_changes_the_mapping_context_digest(tmp_path):
    """I1 §5.3: "Each mapping entry retains its ... content digest ..." - a migration-mapping file
    edited to byte-different-but-semantically-identical content (same entries, same artifact id/
    revision, only an added trailing comment) must still produce a different `content_digest` and,
    in turn, a different `semantic_input_digest` - proving content_digest (not just the parsed
    entries) is genuinely part of the digested context, the same way §5.2's `content_sha256` is
    tracked separately from a source document's own semantic normalization."""
    _write(tmp_path / "svc" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"}))
    config = FilesystemSourceConfig(id="digest-content-test", root=tmp_path)
    sid = source_instance_id(
        configured_source_id="digest-content-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    migration_path = tmp_path / "migrations.yaml"
    document_yaml = _bundled_mapping_document(sid)

    migration_path.write_text(yaml.safe_dump(document_yaml))
    index_one, diagnostics_one = load_migration_mappings([migration_path])
    assert diagnostics_one == ()

    migration_path.write_text(
        yaml.safe_dump(document_yaml) + "\n# an incidental trailing comment\n"
    )
    index_two, diagnostics_two = load_migration_mappings([migration_path])
    assert diagnostics_two == ()

    # Sanity: identical semantic mapping content (same entries) - only the raw bytes differ.
    assert index_one.documents[0].schema_mappings == index_two.documents[0].schema_mappings
    assert index_one.documents[0].content_digest != index_two.documents[0].content_digest

    with_one = run_filesystem_discovery(config, migration_mappings=index_one)
    with_two = run_filesystem_discovery(config, migration_mappings=index_two)
    [outcome_one] = with_one.source_outcomes.values()
    [outcome_two] = with_two.source_outcomes.values()
    assert outcome_one.outcome.semantic_input_digest != outcome_two.outcome.semantic_input_digest


def test_an_attribution_only_change_still_changes_the_mapping_context_digest(tmp_path):
    """I1 §5.3: "Each mapping entry retains its ... attribution ..." - the same byte-identical
    migration-mapping content, configured under two different file *names* (not just two different
    directories - see the portability regression right below this one, which proves the opposite
    for a checkout-root-only difference), must still produce a different `semantic_input_digest`,
    since attribution (the configured file's own name) is part of what a change in configuration
    must be able to invalidate replay for."""
    _write(tmp_path / "svc" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"}))
    config = FilesystemSourceConfig(id="digest-attribution-test", root=tmp_path)
    sid = source_instance_id(
        configured_source_id="digest-attribution-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    document_yaml = _bundled_mapping_document(sid)
    raw_bytes = yaml.safe_dump(document_yaml)

    path_one = tmp_path / "migrations-one.yaml"
    path_two = tmp_path / "migrations-two.yaml"
    path_one.write_text(raw_bytes)
    path_two.write_text(raw_bytes)

    index_one, diagnostics_one = load_migration_mappings([path_one])
    index_two, diagnostics_two = load_migration_mappings([path_two])
    assert diagnostics_one == ()
    assert diagnostics_two == ()
    # Sanity: byte-identical content - only the file's own name (attribution) differs.
    assert index_one.documents[0].content_digest == index_two.documents[0].content_digest
    assert index_one.documents[0].locator != index_two.documents[0].locator

    with_one = run_filesystem_discovery(config, migration_mappings=index_one)
    with_two = run_filesystem_discovery(config, migration_mappings=index_two)
    [outcome_one] = with_one.source_outcomes.values()
    [outcome_two] = with_two.source_outcomes.values()
    assert outcome_one.outcome.semantic_input_digest != outcome_two.outcome.semantic_input_digest


def test_attribution_is_portable_across_two_absolute_checkout_roots(tmp_path):
    """I1 §5.3: "Capture times and physical checkout paths are excluded." Two clean checkouts of
    the exact same repository content, at two different absolute directories, must produce
    identical semantic_input_digest values even when each checkout's own migration-mapping file is
    loaded via its own absolute path (as a real deployment would) - `document.locator` is itself
    the exact absolute path per checkout and therefore always differs, so attribution in the digest
    projection must be derived from something checkout-root-independent (the file's own name), not
    `locator` directly."""
    checkout_one = tmp_path / "checkout-one"
    checkout_two = tmp_path / "somewhere" / "else" / "checkout-two"

    sid = source_instance_id(
        configured_source_id="portability-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    document_yaml = _bundled_mapping_document(sid)
    raw_bytes = yaml.safe_dump(document_yaml)

    results = []
    for checkout_root in (checkout_one, checkout_two):
        _write(
            checkout_root / "svc" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"})
        )
        migration_path = checkout_root / "config" / "migrations" / "mapping.yaml"
        migration_path.parent.mkdir(parents=True, exist_ok=True)
        migration_path.write_text(raw_bytes)

        index, diagnostics = load_migration_mappings([migration_path])
        assert diagnostics == ()
        config = FilesystemSourceConfig(id="portability-test", root=checkout_root)
        result = run_filesystem_discovery(config, migration_mappings=index)
        [outcome] = result.source_outcomes.values()
        results.append((index, outcome))

    (index_one, outcome_one), (index_two, outcome_two) = results
    # Sanity: same content, different absolute directories - locator legitimately differs, but
    # content_digest and the resulting semantic_input_digest must not.
    assert index_one.documents[0].content_digest == index_two.documents[0].content_digest
    assert index_one.documents[0].locator != index_two.documents[0].locator
    assert outcome_one.outcome.semantic_input_digest == outcome_two.outcome.semantic_input_digest
    assert outcome_one.outcome.model.schemas[0].id == "schema:X"


def test_cross_source_schema_content_conflict_blocks_the_whole_run(tmp_path):
    """Two sources whose schemas are explicitly mapped to the same id but disagree in content must
    reject the entire run as PARTIAL/not-commit-eligible with SCHEMA_CONTENT_CONFLICT, and commit
    nothing - the real end-to-end proof that app.sources.claim_conflicts is actually wired in, not
    just unit-tested in isolation."""
    _write(tmp_path / "svc-a" / "openapi.yaml", _single_schema_openapi_doc({"type": "object"}))
    _write(tmp_path / "svc-b" / "openapi.yaml", _single_schema_openapi_doc({"type": "string"}))
    config = FilesystemSourceConfig(id="conflict-test", root=tmp_path)

    def _sid(service_dir: str) -> str:
        return source_instance_id(
            configured_source_id="conflict-test",
            source_kind=SourceKind.FILESYSTEM,
            normalized_root_document_path=f"{service_dir}/openapi.yaml",
        )

    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="aip-v0.5.0-bundled-example-identities-v1",
                artifact_revision="v1",
                locator="migrations.yaml",
                content_digest="test-content-digest",
                schema_mappings=(
                    IdentityMappingEntry(
                        source_instance_id=_sid("svc-a"),
                        document_path="svc-a/openapi.yaml",
                        pointer="/components/schemas/X",
                        pointer_tokens=("components", "schemas", "X"),
                        target_id="schema:Shared",
                    ),
                    IdentityMappingEntry(
                        source_instance_id=_sid("svc-b"),
                        document_path="svc-b/openapi.yaml",
                        pointer="/components/schemas/X",
                        pointer_tokens=("components", "schemas", "X"),
                        target_id="schema:Shared",
                    ),
                ),
            )
        ]
    )
    assert diagnostics == []

    result = run_filesystem_discovery(config, migration_mappings=index)

    assert result.inventory_status is InventoryStatus.PARTIAL
    assert result.commit_eligible is False
    assert result.merged_model.schemas == []
    assert any(d.code is DiagnosticCode.SCHEMA_CONTENT_CONFLICT for d in result.diagnostics)
    # Both sources' own individual outcomes are still recorded (each independently succeeded) -
    # only the cross-source combination is rejected.
    assert len(result.source_outcomes) == 2


def test_shared_identity_mapping_disambiguates_the_same_pointer_in_two_files(tmp_path):
    """I1 §8.1/§9.1's "normalized definition source pointer" is the document path plus the RFC 6901
    pointer together, not the pointer alone - one root document's own bounded multi-file $ref
    closure (PR3b) can resolve the identical relative pointer (`/X`) inside two different files.
    Real end-to-end regression: a mapping targeting only `schemas/a.yaml#/X` must not also apply to
    `schemas/b.yaml#/X`, even though both resolve to the exact same pointer_tokens and share the
    same SourceInstanceId (both are $ref'd from the same root document)."""
    _write(tmp_path / "svc" / "schemas" / "a.yaml", {"X": {"type": "object", "title": "FromA"}})
    _write(tmp_path / "svc" / "schemas" / "b.yaml", {"X": {"type": "object", "title": "FromB"}})
    _write(
        tmp_path / "svc" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Svc"},
            "x-aip-service-id": "service:svc",
            "paths": {
                "/a": {
                    "get": {
                        "operationId": "getA",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "schemas/a.yaml#/X"}}
                                }
                            }
                        },
                    }
                },
                "/b": {
                    "get": {
                        "operationId": "getB",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "schemas/b.yaml#/X"}}
                                }
                            }
                        },
                    }
                },
            },
        },
    )
    config = FilesystemSourceConfig(id="disambiguate-test", root=tmp_path)
    sid = source_instance_id(
        configured_source_id="disambiguate-test",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/openapi.yaml",
    )
    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="aip-v0.5.0-bundled-example-identities-v1",
                artifact_revision="v1",
                locator="migrations.yaml",
                content_digest="test-content-digest",
                schema_mappings=(
                    IdentityMappingEntry(
                        source_instance_id=sid,
                        document_path="svc/schemas/a.yaml",
                        pointer="/X",
                        pointer_tokens=("X",),
                        target_id="schema:OnlyFromA",
                    ),
                ),
            )
        ]
    )
    assert diagnostics == []

    result = run_filesystem_discovery(config, migration_mappings=index)
    [outcome] = result.source_outcomes.values()
    assert outcome.outcome.result is IngestionResult.ACCEPTED

    schema_ids = [s.id for s in outcome.outcome.model.schemas]
    # Exactly two distinct schemas: the explicitly-mapped one from a.yaml, and b.yaml's own,
    # unaffected owner-scoped default - proves document_path, not pointer alone, is the key, or
    # both files' identical `/X` pointer would have collided onto one shared id (or a spurious
    # conflict) instead of resolving independently.
    assert len(schema_ids) == 2
    assert schema_ids.count("schema:OnlyFromA") == 1
    other_id = next(sid_value for sid_value in schema_ids if sid_value != "schema:OnlyFromA")
    assert other_id != "schema:OnlyFromA"


# I2 Draft 0.2 §3 prerequisite slice, items 1/3: `run_discovery` is the source-neutral discovery
# entry point, and every discovery attempt constructs a real `SourceInventorySnapshot`.


class _FakeDiscoverer:
    """A minimal non-filesystem `SourceDiscoverer` test double, proving `run_discovery` contains no
    source-kind branch - it never inspects `source_kind` or otherwise special-cases this discoverer.
    `source_kind` is set to the only `SourceKind` member that exists today (a second member is
    deliberately not introduced by this PR - see app.sources.model's own reservation comment); this
    double's whole point is that `run_discovery` never looks at it.
    """

    source_kind = SourceKind.FILESYSTEM

    def __init__(self, outcome: DiscoveryOutcome):
        self.discoverer_identity = "fake-discoverer@1"
        self._outcome = outcome

    def discover(self) -> DiscoveryOutcome:
        return self._outcome


def test_run_discovery_drives_a_non_filesystem_discoverer_with_no_special_casing():
    outcome = DiscoveryOutcome(
        loaded_sources=(),
        enumeration_complete=True,
        diagnostics=(),
        discovery_scope_id="urn:aip:discovery-scope:fake",
        scope_definition_digest="fake-scope-digest",
    )
    result = run_discovery(_FakeDiscoverer(outcome))
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.commit_eligible is True
    assert result.merged_model.services == []
    assert result.inventory_snapshot is not None
    assert result.inventory_snapshot.discoverer_identity == "fake-discoverer@1"
    assert result.inventory_snapshot.discovery_scope_id == "urn:aip:discovery-scope:fake"
    assert result.inventory_snapshot.status is InventoryStatus.COMPLETE
    assert result.inventory_snapshot.discovered_source_ids == ()


def test_inventory_snapshot_is_none_when_the_scope_itself_could_not_be_determined():
    """Mirrors `DiscoveryOutcome.discovery_scope_id`'s own documented meaning: `None` only when
    enumeration failed AND the scope itself could not be computed. A snapshot cannot meaningfully
    identify an inventory it can't name the scope of."""
    outcome = DiscoveryOutcome(
        loaded_sources=(),
        enumeration_complete=False,
        diagnostics=(),
        discovery_scope_id=None,
        scope_definition_digest=None,
    )
    result = run_discovery(_FakeDiscoverer(outcome))
    assert result.inventory_status is InventoryStatus.FAILED
    assert result.inventory_snapshot is None


def test_inventory_snapshot_is_built_even_on_failed_enumeration_when_scope_is_known():
    outcome = DiscoveryOutcome(
        loaded_sources=(),
        enumeration_complete=False,
        diagnostics=(),
        discovery_scope_id="urn:aip:discovery-scope:fake",
        scope_definition_digest="fake-scope-digest",
    )
    result = run_discovery(_FakeDiscoverer(outcome))
    assert result.inventory_status is InventoryStatus.FAILED
    assert result.inventory_snapshot is not None
    assert result.inventory_snapshot.status is InventoryStatus.FAILED


def test_filesystem_discovery_produces_an_inventory_snapshot(tmp_path):
    result = run_filesystem_discovery(FilesystemSourceConfig(id="x", root=tmp_path))
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.inventory_snapshot is not None
    assert result.inventory_snapshot.discoverer_identity == "filesystem-discoverer@1"
    assert result.inventory_snapshot.discovery_scope_id == result.discovery_scope_id


def test_explicit_tombstones_are_carried_on_the_snapshot_and_affect_its_revision(tmp_path):
    config = FilesystemSourceConfig(id="x", root=tmp_path)
    real_scope_id = run_filesystem_discovery(config).discovery_scope_id
    in_scope_tombstone = Tombstone(
        target_source_instance_id="urn:aip:source:filesystem:deadbeef",
        discovery_scope_id=real_scope_id,
        expected_prior_inventory_revision="urn:aip:inventory-revision:whatever",
        scope_definition_digest="whatever",
        actor="operator@example.com",
        reason="decommissioned",
        tombstone_revision="1",
    )
    without = run_filesystem_discovery(config)
    with_tombstone = run_filesystem_discovery(config, tombstones=(in_scope_tombstone,))
    assert with_tombstone.inventory_snapshot.tombstones == (in_scope_tombstone,)
    assert (
        with_tombstone.inventory_snapshot.inventory_revision
        != without.inventory_snapshot.inventory_revision
    )


def test_a_tombstone_for_a_different_scope_does_not_affect_this_scopes_snapshot_or_revision(
    tmp_path,
):
    """A real bug found in PR review: `app.api.import_api` loads every configured tombstone once
    and reuses the same list for every configured source's own discovery run - an out-of-scope
    tombstone must never enter this scope's own inventory revision/event-id hash, or an unrelated
    scope's tombstone would spuriously churn this one's revision."""
    config = FilesystemSourceConfig(id="x", root=tmp_path)
    out_of_scope_tombstone = Tombstone(
        target_source_instance_id="urn:aip:source:filesystem:deadbeef",
        discovery_scope_id="urn:aip:discovery-scope:some-other-scope-entirely",
        expected_prior_inventory_revision="urn:aip:inventory-revision:whatever",
        scope_definition_digest="whatever",
        actor="operator@example.com",
        reason="decommissioned",
        tombstone_revision="1",
    )
    without = run_filesystem_discovery(config)
    with_out_of_scope_tombstone = run_filesystem_discovery(
        config, tombstones=(out_of_scope_tombstone,)
    )
    assert with_out_of_scope_tombstone.inventory_snapshot.tombstones == ()
    assert (
        with_out_of_scope_tombstone.inventory_snapshot.inventory_revision
        == without.inventory_snapshot.inventory_revision
    )


# I2 Draft 0.2 §3 prerequisite slice (PR B), §7.1: merge_models' dedup behavior for the new
# infrastructure entity/contribution/claim lists, mirroring every existing entity kind's own
# first-wins dedup - nothing populates these fields through a real adapter yet (I2 §12 slice 3), so
# these are direct unit tests of merge_models rather than end-to-end filesystem-discovery ones.

_ENTITY = InfrastructureEntity(
    id="urn:aip:k8s-resource:deadbeef",
    entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
    cluster_uid="cluster-1",
    api_group="apps",
    resource_kind="Deployment",
    namespace="default",
    name="order-service",
)


def _contribution(*, entity_id: str, source_instance_id: str) -> InfrastructureContribution:
    return InfrastructureContribution(
        entity_id=entity_id,
        source_instance_id=source_instance_id,
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        resource_semantic_digest="digest-1",
        evidence_refs=["evidence:kubernetes:1"],
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )


def _claim(*, subject_id: str, evidence_refs=("evidence:kubernetes:1",)) -> InfrastructureClaim:
    return InfrastructureClaim(
        kind=InfrastructureClaimKind.WORKLOAD_EXISTS,
        subject_id=subject_id,
        evidence_refs=list(evidence_refs),
        mapping_rule_id="kubernetes-adapter@1",
        mapping_rule_version="v1",
    )


def test_merge_models_dedupes_infrastructure_entities_by_id():
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_entities=[_ENTITY]),
            ArchitectureModel(infrastructure_entities=[_ENTITY]),
        ]
    )
    assert merged.infrastructure_entities == [_ENTITY]


def test_merge_models_dedupes_identical_infrastructure_contributions():
    contribution = _contribution(
        entity_id=_ENTITY.id, source_instance_id="urn:aip:source:kubernetes:1"
    )
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_contributions=[contribution]),
            ArchitectureModel(infrastructure_contributions=[contribution]),
        ]
    )
    assert merged.infrastructure_contributions == [contribution]


def test_merge_models_keeps_distinct_contributions_from_different_sources():
    first = _contribution(entity_id=_ENTITY.id, source_instance_id="urn:aip:source:kubernetes:1")
    second = _contribution(entity_id=_ENTITY.id, source_instance_id="urn:aip:source:kubernetes:2")
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_contributions=[first]),
            ArchitectureModel(infrastructure_contributions=[second]),
        ]
    )
    assert len(merged.infrastructure_contributions) == 2


def test_merge_models_dedupes_infrastructure_claims_by_kind_subject_object():
    claim = _claim(subject_id=_ENTITY.id)
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_claims=[claim]),
            ArchitectureModel(infrastructure_claims=[claim]),
        ]
    )
    assert merged.infrastructure_claims == [claim]


def test_merge_models_keeps_distinct_claims_with_different_subjects():
    first = _claim(subject_id="urn:aip:k8s-resource:a")
    second = _claim(subject_id="urn:aip:k8s-resource:b")
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_claims=[first]),
            ArchitectureModel(infrastructure_claims=[second]),
        ]
    )
    assert len(merged.infrastructure_claims) == 2


# I2 Draft 0.2 §7.1/§10: a cross-source infrastructure-entity digest disagreement rejects the run
# AND marks the disagreeing sources' own results REJECTED_CONFLICT - driven through the real
# `run_discovery` path with a test-double discoverer/adapter, since no Kubernetes adapter exists yet.


def _loaded_source(source_instance_id: str):
    descriptor = SourceDescriptor(
        source_instance_id=source_instance_id,
        source_kind=SourceKind.FILESYSTEM,
        locator=f"{source_instance_id}.yaml",
        discovery_scope_id="urn:aip:discovery-scope:fake",
        scope_definition_digest="fake-scope-digest",
        content_sha256="a" * 64,
        semantic_input_digest="b" * 64,
        mapping_context_digest="c" * 64,
        adapter_identity="",
        mapping_rule_id="",
        mapping_rule_version="",
    )
    return LoadedSource(descriptor=descriptor, document={"fakeInfrastructureSource": True})


class _FakeInfrastructureAdapter:
    """Emits one infrastructure entity plus a per-source contribution whose semantic digest is
    controlled by the test - the minimum needed to exercise §7.1's cross-source conflict rule
    without a real Kubernetes adapter."""

    adapter_identity = "fake-infrastructure-adapter@1"
    mapping_rule_version = "v1"
    dependency_phase = 0

    def __init__(self, digests_by_source: dict[str, str]):
        self._digests_by_source = digests_by_source

    def supports(self, loaded) -> bool:
        return "fakeInfrastructureSource" in loaded.document

    def map(self, loaded, **_kwargs):
        source_instance_id = loaded.descriptor.source_instance_id
        entity = InfrastructureEntity(
            id="urn:aip:k8s-resource:shared",
            entity_kind=InfrastructureEntityKind.KUBERNETES_WORKLOAD,
            cluster_uid="cluster-1",
            api_group="apps",
            resource_kind="Deployment",
            namespace="default",
            name="order-service",
        )
        contribution = InfrastructureContribution(
            entity_id=entity.id,
            source_instance_id=source_instance_id,
            evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
            resource_semantic_digest=self._digests_by_source[source_instance_id],
            evidence_refs=["evidence:kubernetes:1"],
            mapping_rule_id=self.adapter_identity,
            mapping_rule_version=self.mapping_rule_version,
        )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=ArchitectureModel(
                infrastructure_entities=[entity], infrastructure_contributions=[contribution]
            ),
            diagnostics=(),
            semantic_input_digest=loaded.descriptor.semantic_input_digest,
        )


def _run_with_infrastructure_digests(digests_by_source: dict[str, str]):
    outcome = DiscoveryOutcome(
        loaded_sources=tuple(_loaded_source(sid) for sid in digests_by_source),
        enumeration_complete=True,
        diagnostics=(),
        discovery_scope_id="urn:aip:discovery-scope:fake",
        scope_definition_digest="fake-scope-digest",
    )
    registry = SourceAdapterRegistry([_FakeInfrastructureAdapter(digests_by_source)])
    return run_discovery(_FakeDiscoverer(outcome), registry=registry)


def test_agreeing_infrastructure_digests_across_sources_commit_normally():
    result = _run_with_infrastructure_digests(
        {"urn:aip:source:kubernetes:1": "digest-1", "urn:aip:source:kubernetes:2": "digest-1"}
    )
    assert result.commit_eligible is True
    assert all(
        o.outcome.result is IngestionResult.ACCEPTED for o in result.source_outcomes.values()
    )
    # Equal digests merge into a single entity/contribution pair per source, not a conflict.
    assert len(result.merged_model.infrastructure_entities) == 1
    assert len(result.merged_model.infrastructure_contributions) == 2


def test_disagreeing_infrastructure_digests_reject_the_run_and_both_sources():
    result = _run_with_infrastructure_digests(
        {"urn:aip:source:kubernetes:1": "digest-1", "urn:aip:source:kubernetes:2": "digest-2"}
    )
    assert result.commit_eligible is False
    assert result.inventory_status is InventoryStatus.PARTIAL
    assert any(d.code is DiagnosticCode.K8S_RESOURCE_CONFLICT for d in result.diagnostics)
    # §10: "REJECTED_CONFLICT; no commit" is a source result, not only a run status - and §7.1's
    # "no source wins by precedence" means both disagreeing sources carry it.
    assert [o.outcome.result for o in result.source_outcomes.values()] == [
        IngestionResult.REJECTED_CONFLICT,
        IngestionResult.REJECTED_CONFLICT,
    ]


def test_merge_models_unions_evidence_for_a_shared_claim():
    """§7.2 requires "deterministic evidence union" for a claim identity shared across sources -
    first-wins would silently discard the second source's evidence (a real bug found in PR review).
    """
    first = _claim(subject_id=_ENTITY.id, evidence_refs=("evidence:kubernetes:b",))
    second = _claim(subject_id=_ENTITY.id, evidence_refs=("evidence:kubernetes:a",))
    merged = merge_models(
        [
            ArchitectureModel(infrastructure_claims=[first]),
            ArchitectureModel(infrastructure_claims=[second]),
        ]
    )
    [claim] = merged.infrastructure_claims
    # Unioned and re-sorted, so the merged claim still satisfies its own sorted/duplicate-free
    # invariant - and identical regardless of which source was seen first.
    assert claim.evidence_refs == ["evidence:kubernetes:a", "evidence:kubernetes:b"]

    reversed_merge = merge_models(
        [
            ArchitectureModel(infrastructure_claims=[second]),
            ArchitectureModel(infrastructure_claims=[first]),
        ]
    )
    assert reversed_merge.infrastructure_claims[0].evidence_refs == claim.evidence_refs


# --- v0.5.0 I4 spec §7.3: Topic/Subscription mappings enter the mapping-context digest ----------


def _pubsub_digest(*, topic=(), subscription=()) -> str:
    from app.ingestion.orchestrator import _compute_mapping_context_digest, default_registry
    from app.sources.manifest_bindings import BindingIndex

    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="pubsub-mappings",
                artifact_revision="v1",
                locator="pubsub.yaml",
                content_digest="test-content-digest",
                topic_mappings=tuple(topic),
                subscription_mappings=tuple(subscription),
            )
        ]
    )
    assert diagnostics == []
    return _compute_mapping_context_digest(BindingIndex(entries=()), default_registry(), index)


def _topic_entry(topic_id="topic:owned:" + "1" * 64):
    return IdentityMappingEntry(
        source_instance_id="urn:aip:source:filesystem:" + "a" * 64,
        document_path="svc/asyncapi.yaml",
        pointer="/channels/orders",
        pointer_tokens=("channels", "orders"),
        target_id=topic_id,
    )


def _subscription_entry(**overrides):
    fields = {
        "source_instance_id": "urn:aip:source:filesystem:" + "a" * 64,
        "document_path": "svc/asyncapi.yaml",
        "pointer": "/channels/orders/subscribe",
        "pointer_tokens": ("channels", "orders", "subscribe"),
        "target_id": "subscription:owned:" + "3" * 64,
        "bound_topic_id": "topic:owned:" + "1" * 64,
        "subscription_name": "billing",
    }
    fields.update(overrides)
    return IdentityMappingEntry(**fields)


def test_empty_pubsub_mapping_digest_is_deterministic():
    assert _pubsub_digest() == _pubsub_digest()


def test_topic_and_subscription_mappings_each_change_the_mapping_context_digest():
    empty = _pubsub_digest()
    with_topic = _pubsub_digest(topic=[_topic_entry()])
    with_subscription = _pubsub_digest(subscription=[_subscription_entry()])
    assert len({empty, with_topic, with_subscription}) == 3


def test_topic_id_only_change_changes_the_mapping_context_digest():
    assert _pubsub_digest(topic=[_topic_entry()]) != _pubsub_digest(
        topic=[_topic_entry("topic:owned:" + "2" * 64)]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_id", "subscription:owned:" + "9" * 64),
        ("bound_topic_id", "topic:owned:" + "2" * 64),
        ("subscription_name", "shipping"),
    ],
)
def test_each_subscription_payload_field_changes_the_mapping_context_digest(field, value):
    """I4 spec §7.3: the Topic binding and Subscription name are part of the entry's identity
    payload, so each alone must be visible to the revision fence."""
    assert _pubsub_digest(subscription=[_subscription_entry()]) != _pubsub_digest(
        subscription=[_subscription_entry(**{field: value})]
    )


def test_one_source_reusing_a_configured_subscription_id_across_two_topics_rejects_cleanly(
    tmp_path,
):
    """PR #230 review: a single source that binds one configured Subscription id to two different
    Topics (two subscribe operations) must be rejected at the discovery boundary - REJECTED_CONFLICT
    with SUBSCRIPTION_IDENTITY_CONFLICT and a non-commit-eligible run - never reaching import-time
    canonical validation (which would raise instead of rejecting)."""
    message = {"name": "M", "payload": {"type": "object"}}
    document = {
        "asyncapi": "2.6.0",
        "info": {"title": "Svc", "version": "1"},
        "x-aip-service-id": "service:svc",
        "channels": {
            channel: {"x-aip-destination-kind": "topic", "subscribe": {"message": message}}
            for channel in ("orders", "invoices")
        },
    }
    _write(tmp_path / "svc" / "asyncapi.yaml", document)
    config = FilesystemSourceConfig(id="one-source-subscription", root=tmp_path)
    sid = source_instance_id(
        configured_source_id="one-source-subscription",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="svc/asyncapi.yaml",
    )

    def entry(pointer, target_id, **extra):
        return IdentityMappingEntry(
            source_instance_id=sid,
            document_path="svc/asyncapi.yaml",
            pointer=pointer,
            pointer_tokens=tuple(pointer.strip("/").split("/")),
            target_id=target_id,
            **extra,
        )

    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="one-source",
                artifact_revision="v1",
                locator="mappings.yaml",
                content_digest="x",
                topic_mappings=tuple(
                    entry(f"/channels/{c}", f"topic:configured-{c}") for c in ("orders", "invoices")
                ),
                subscription_mappings=tuple(
                    entry(
                        f"/channels/{c}/subscribe",
                        "subscription:configured-shared",
                        bound_topic_id=f"topic:configured-{c}",
                        subscription_name="shared",
                    )
                    for c in ("orders", "invoices")
                ),
            )
        ]
    )
    assert diagnostics == []

    run = run_filesystem_discovery(config, migration_mappings=index)

    assert run.commit_eligible is False
    [outcome] = run.source_outcomes.values()
    assert outcome.outcome.result is IngestionResult.REJECTED_CONFLICT
    assert DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT in {d.code for d in run.diagnostics}
