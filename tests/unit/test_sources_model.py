from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)


def _descriptor(**overrides) -> SourceDescriptor:
    fields = {
        "source_instance_id": "urn:aip:source:filesystem:" + "a" * 64,
        "source_kind": SourceKind.FILESYSTEM,
        "locator": "examples/order-service/openapi.yaml",
        "discovery_scope_id": "urn:aip:discovery-scope:" + "b" * 64,
        "scope_definition_digest": "c" * 64,
        "content_sha256": "d" * 64,
        "semantic_input_digest": "e" * 64,
        "adapter_identity": "openapi-adapter",
        "mapping_rule_id": "openapi-mapping",
        "mapping_rule_version": "v1",
    }
    fields.update(overrides)
    return SourceDescriptor(**fields)


def test_source_descriptor_requires_only_documented_fields():
    descriptor = _descriptor()
    assert descriptor.declared_provider_revision is None
    assert descriptor.source_inventory_snapshot_ref is None


def test_source_descriptor_accepts_optional_fields():
    descriptor = _descriptor(
        declared_provider_revision="rev-1",
        declared_service_id="service:order-service",
        document_dialect_version="3.1.0",
        dependency_closure_digest="f" * 64,
    )
    assert descriptor.declared_service_id == "service:order-service"
    assert descriptor.document_dialect_version == "3.1.0"


def test_loaded_source_defaults_to_no_diagnostics():
    loaded = LoadedSource(descriptor=_descriptor(), document={"openapi": "3.1.0"})
    assert loaded.diagnostics == []


def test_loaded_source_carries_diagnostics():
    diagnostic = IngestionDiagnostic(
        code=DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED,
        message="no Service identity resolves",
    )
    loaded = LoadedSource(
        descriptor=_descriptor(), document={"openapi": "3.1.0"}, diagnostics=[diagnostic]
    )
    assert loaded.diagnostics == [diagnostic]


def test_ingestion_result_has_exactly_five_values():
    assert {member.value for member in IngestionResult} == {
        "ACCEPTED",
        "ACCEPTED_WITH_LIMITATIONS",
        "REJECTED_INVALID",
        "REJECTED_UNSUPPORTED",
        "REJECTED_CONFLICT",
    }
