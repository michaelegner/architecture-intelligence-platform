from pathlib import Path

from app.canonical.model import ArchitectureModel, Operation
from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.ingestion.manifest_adapter import ManifestSourceAdapter
from app.ingestion.openapi_adapter import OpenApiSourceAdapter
from app.sources.migration_mappings import EMPTY_SHARED_IDENTITY_INDEX
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.service_identity import resolve_service_identity

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SOURCE_INSTANCE_ID = "urn:aip:source:filesystem:" + "a" * 64


class _StubResolver:
    def resolve(self, *, source_instance_id, construct_pointer, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=[],
            manifest_bindings=[],
        )


def _loaded(document: dict):
    descriptor = SourceDescriptor(
        source_instance_id=SOURCE_INSTANCE_ID,
        source_kind=SourceKind.FILESYSTEM,
        locator="architecture.yaml",
        discovery_scope_id="urn:aip:discovery-scope:" + "b" * 64,
        scope_definition_digest="c" * 64,
        content_sha256="d" * 64,
        semantic_input_digest="",
        mapping_context_digest="",
        adapter_identity="",
        mapping_rule_id="",
        mapping_rule_version="",
    )
    return LoadedSource(descriptor=descriptor, document=document)


def _map(document: dict, upstream_model: ArchitectureModel | None = None):
    return ManifestSourceAdapter().map(
        _loaded(document),
        service_identity=_StubResolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=upstream_model if upstream_model is not None else ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )


def _upstream_with_operation(service_id: str, operation_id: str, target_operation_full_id: str):
    return ArchitectureModel(
        operations=[
            Operation(
                id=target_operation_full_id,
                service_id=service_id,
                operation_id=operation_id,
                method="GET",
                path="/x",
            )
        ]
    )


def test_resolves_calls_relation_via_upstream_operations():
    upstream = _upstream_with_operation(
        "service:product-service",
        "getProduct",
        "operation:service:product-service:GET:/products/{id}",
    )
    document = {
        "service": "order-service",
        "x-aip-service-id": "service:order-service",
        "calls": [{"service": "service:product-service", "operationId": "getProduct"}],
    }
    outcome = _map(document, upstream)
    assert outcome.result is IngestionResult.ACCEPTED
    [relation] = outcome.model.relations
    [provenance] = outcome.model.provenance
    assert relation.type == "CALLS"
    assert relation.source_id == "service:order-service"
    assert relation.target_id == "operation:service:product-service:GET:/products/{id}"
    assert relation.evidence_ids == [provenance.id]


def test_unknown_operation_id_is_rejected_unsupported():
    document = {
        "service": "order-service",
        "x-aip-service-id": "service:order-service",
        "calls": [{"service": "service:product-service", "operationId": "doesNotExist"}],
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.diagnostics[0].code is DiagnosticCode.MANIFEST_CALL_TARGET_UNRESOLVED


def test_malformed_call_target_service_id_is_rejected_invalid():
    document = {
        "service": "order-service",
        "x-aip-service-id": "service:order-service",
        "calls": [{"service": "not-a-service-id", "operationId": "getProduct"}],
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_INVALID


def test_no_calls_produces_no_relations():
    document = {"service": "order-service", "x-aip-service-id": "service:order-service"}
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.relations == []


def test_provenance_recorded():
    document = {"service": "order-service", "x-aip-service-id": "service:order-service"}
    outcome = _map(document)
    [provenance] = outcome.model.provenance
    assert provenance.source_type == "MANIFEST"
    assert provenance.source_file == "architecture.yaml"


def test_missing_service_identity_is_rejected_unsupported():
    document = {"service": "order-service"}
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED


def test_supports_matches_only_calls_manifests():
    adapter = ManifestSourceAdapter()
    assert adapter.supports(_loaded({"service": "x"})) is True
    assert adapter.supports(_loaded({"openapi": "3.1.0"})) is False
    assert adapter.supports(_loaded({"kind": "ArchitectureIdentityBindings"})) is False


def test_real_manifest_fixture_resolves_against_real_openapi_fixture():
    discoverer = FilesystemSourceDiscoverer(
        FilesystemSourceConfig(id="aip-bundled-examples-v0.5", root=EXAMPLES_DIR)
    )
    loaded_sources = discoverer.discover().loaded_sources

    product_openapi = next(
        s
        for s in loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "product-service" / "openapi.yaml"
    )
    openapi_outcome = OpenApiSourceAdapter().map(
        product_openapi,
        service_identity=_StubResolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )
    assert openapi_outcome.result is IngestionResult.ACCEPTED

    manifest_source = next(
        s
        for s in loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "order-service" / "architecture.yaml"
    )
    outcome = ManifestSourceAdapter().map(
        manifest_source,
        service_identity=_StubResolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=openapi_outcome.model,
        mapping_context_digest="e" * 64,
    )
    assert outcome.result is IngestionResult.ACCEPTED
    [relation] = outcome.model.relations
    assert relation.type == "CALLS"
    assert relation.source_id == "service:order-service"
    assert relation.target_id == "operation:service:product-service:GET:/products/{id}"
