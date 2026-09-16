from pathlib import Path

from app.canonical import ids
from app.canonical.model import ArchitectureModel
from app.ingestion.filesystem_discoverer import FilesystemSourceDiscoverer
from app.ingestion.openapi_adapter import OpenApiSourceAdapter
from app.sources.jcs import canonical_sha256_hex
from app.sources.migration_mappings import (
    EMPTY_SHARED_IDENTITY_INDEX,
    IdentityMappingEntry,
    MigrationMappingsDocument,
    build_shared_identity_index,
)
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.service_identity import (
    PointerBinding,
    ServiceIdentityPath,
    resolve_service_identity,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SOURCE_INSTANCE_ID = "urn:aip:source:filesystem:" + "a" * 64

PRODUCT_SERVICE_DOC = {
    "openapi": "3.1.0",
    "info": {"title": "ProductService", "version": "1.0.0"},
    "x-aip-service-id": "service:product-service",
    "paths": {
        "/products/{id}": {
            "get": {
                "operationId": "getProduct",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Product"}}
                        }
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Product": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                "required": ["id", "name"],
            }
        }
    },
}


class _StubResolver:
    def __init__(self, *, configured_mappings=(), manifest_bindings=()):
        self._configured_mappings = configured_mappings
        self._manifest_bindings = manifest_bindings

    def resolve(self, *, source_instance_id, construct_pointer, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=self._configured_mappings,
            manifest_bindings=self._manifest_bindings,
        )


def _loaded(
    document: dict, *, source_instance_id: str = SOURCE_INSTANCE_ID, locator: str = "test.yaml"
):
    descriptor = SourceDescriptor(
        source_instance_id=source_instance_id,
        source_kind=SourceKind.FILESYSTEM,
        locator=locator,
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


def _map(document: dict, *, shared_identity=EMPTY_SHARED_IDENTITY_INDEX, **resolver_kwargs):
    adapter = OpenApiSourceAdapter()
    return adapter.map(
        _loaded(document),
        service_identity=_StubResolver(**resolver_kwargs),
        shared_identity=shared_identity,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )


def test_parses_service_metadata():
    outcome = _map(PRODUCT_SERVICE_DOC)
    assert outcome.result is IngestionResult.ACCEPTED
    [service] = outcome.model.services
    assert service.id == "service:product-service"
    assert service.name == "ProductService"
    assert service.version == "1.0.0"


def test_parses_operation_with_owner_scoped_schema_id():
    outcome = _map(PRODUCT_SERVICE_DOC)
    [operation] = outcome.model.operations
    assert operation.id == ids.operation_id("service:product-service", "GET", "/products/{id}")
    assert operation.operation_id == "getProduct"
    assert operation.method == "GET"
    assert operation.path == "/products/{id}"
    assert operation.request_schema_ids == []
    [schema_id] = operation.response_schema_ids
    assert schema_id.startswith("schema:owned:")


def test_provides_relation_created():
    outcome = _map(PRODUCT_SERVICE_DOC)
    provides = [r for r in outcome.model.relations if r.type == "PROVIDES"]
    assert len(provides) == 1
    assert provides[0].source_id == "service:product-service"
    assert provides[0].target_id == ids.operation_id(
        "service:product-service", "GET", "/products/{id}"
    )


def test_response_schema_relation_and_rfc8785_canonical_hash():
    outcome = _map(PRODUCT_SERVICE_DOC)
    response_schema_relations = [r for r in outcome.model.relations if r.type == "RESPONSE_SCHEMA"]
    assert len(response_schema_relations) == 1

    [schema] = outcome.model.schemas
    assert schema.id == response_schema_relations[0].target_id
    assert schema.id.startswith("schema:owned:")
    assert schema.name == "Product"
    assert schema.format == "application/json"
    assert schema.canonical_hash == canonical_sha256_hex(
        PRODUCT_SERVICE_DOC["components"]["schemas"]["Product"]
    )


def test_schema_hash_excludes_description_and_examples():
    document = {
        **PRODUCT_SERVICE_DOC,
        "components": {
            "schemas": {
                "Product": {
                    **PRODUCT_SERVICE_DOC["components"]["schemas"]["Product"],
                    "description": "A product.",
                    "example": {"id": "1", "name": "Widget"},
                }
            }
        },
    }
    outcome = _map(document)
    [schema] = outcome.model.schemas
    assert schema.canonical_hash == canonical_sha256_hex(
        PRODUCT_SERVICE_DOC["components"]["schemas"]["Product"]
    )


def test_provenance_recorded():
    outcome = _map(PRODUCT_SERVICE_DOC)
    [provenance] = outcome.model.provenance
    assert provenance.id == ids.evidence_id("OPENAPI", SOURCE_INSTANCE_ID, None)
    assert provenance.source_type == "OPENAPI"
    assert provenance.evidence_type == "DECLARED"
    assert all(r.evidence_ids == [provenance.id] for r in outcome.model.relations)


def test_service_with_no_operations_still_produces_service_and_provenance():
    document = {
        "openapi": "3.1.0",
        "info": {"title": "PaymentService"},
        "x-aip-service-id": "service:payment-service",
        "paths": {},
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.services) == 1
    assert outcome.model.operations == []
    assert outcome.model.schemas == []
    assert outcome.model.relations == []
    assert len(outcome.model.provenance) == 1


def test_request_body_and_schema_dedup_across_operations():
    document = {
        "openapi": "3.1.0",
        "info": {"title": "OrderService", "version": "1.0.0"},
        "x-aip-service-id": "service:order-service",
        "paths": {
            "/orders": {
                "post": {
                    "operationId": "createOrder",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/OrderRequest"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Order"}
                                }
                            }
                        }
                    },
                }
            },
            "/orders/{id}": {
                "get": {
                    "operationId": "getOrder",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Order"}
                                }
                            }
                        }
                    },
                }
            },
        },
        "components": {
            "schemas": {"OrderRequest": {"type": "object"}, "Order": {"type": "object"}}
        },
    }
    outcome = _map(document)

    assert len(outcome.model.operations) == 2
    assert {s.name for s in outcome.model.schemas} == {"OrderRequest", "Order"}

    create_order = next(op for op in outcome.model.operations if op.operation_id == "createOrder")
    get_order = next(op for op in outcome.model.operations if op.operation_id == "getOrder")
    assert create_order.response_schema_ids == get_order.response_schema_ids  # same Order schema id

    provides = [r for r in outcome.model.relations if r.type == "PROVIDES"]
    assert len(provides) == 2


def test_missing_service_identity_is_rejected_unsupported():
    document = {"openapi": "3.1.0", "info": {"title": "X"}, "paths": {}}
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert outcome.model == ArchitectureModel()
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_UNRESOLVED


def test_malformed_service_identity_is_rejected_invalid():
    document = {
        "openapi": "3.1.0",
        "info": {"title": "X"},
        "x-aip-service-id": "not-a-service-id",
        "paths": {},
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_INVALID


def test_conflicting_service_identity_is_rejected_conflict():
    document = {**PRODUCT_SERVICE_DOC}
    conflicting_mapping = PointerBinding(
        source_instance_id=SOURCE_INSTANCE_ID,
        pointer_prefix="",
        service_id="service:other-service",
        path=ServiceIdentityPath.CONFIGURED_MAPPING,
    )
    outcome = _map(document, configured_mappings=[conflicting_mapping])
    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert outcome.diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_CONFLICT


def test_operation_level_extension_overrides_root_service_identity():
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Multi"},
        "x-aip-service-id": "service:root-service",
        "paths": {
            "/x": {
                "get": {
                    "operationId": "getX",
                    "x-aip-service-id": "service:other-service",
                    "responses": {"200": {}},
                }
            }
        },
    }
    outcome = _map(document)
    assert outcome.result is IngestionResult.ACCEPTED
    assert {s.id for s in outcome.model.services} == {
        "service:root-service",
        "service:other-service",
    }
    [operation] = outcome.model.operations
    assert operation.service_id == "service:other-service"


def test_invalid_document_structure_is_rejected_invalid():
    document = {"openapi": "3.1.0"}  # missing required "info"/"paths"
    outcome = _map(document)
    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert outcome.diagnostics[0].code is DiagnosticCode.DOCUMENT_PARSE_INVALID


def test_supports_matches_only_openapi_documents():
    adapter = OpenApiSourceAdapter()
    assert adapter.supports(_loaded(PRODUCT_SERVICE_DOC)) is True
    assert adapter.supports(_loaded({"asyncapi": "2.6.0"})) is False


def test_maps_real_product_service_fixture_via_discoverer():
    discoverer = FilesystemSourceDiscoverer(FilesystemSourceConfig(id="test", root=EXAMPLES_DIR))
    loaded = next(
        s
        for s in discoverer.discover().loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "product-service" / "openapi.yaml"
    )
    outcome = OpenApiSourceAdapter().map(
        loaded,
        service_identity=_StubResolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )
    assert outcome.result is IngestionResult.ACCEPTED
    [operation] = outcome.model.operations
    assert operation.operation_id == "getProduct"
    assert operation.service_id == "service:product-service"


def test_maps_real_order_service_fixture_via_discoverer():
    discoverer = FilesystemSourceDiscoverer(FilesystemSourceConfig(id="test", root=EXAMPLES_DIR))
    loaded = next(
        s
        for s in discoverer.discover().loaded_sources
        if Path(s.descriptor.locator) == EXAMPLES_DIR / "order-service" / "openapi.yaml"
    )
    outcome = OpenApiSourceAdapter().map(
        loaded,
        service_identity=_StubResolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )
    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.operations) == 2
    assert {s.name for s in outcome.model.schemas} == {"OrderRequest", "Order"}


def _shared_identity_index(*schema_mappings: tuple[str, str]):
    """schema_mappings entries are (pointer, target_id) - built against SOURCE_INSTANCE_ID and
    "test.yaml", the fixed default `_loaded()` source instance id/locator used throughout this file
    (root_relative_path == the locator itself, since these LoadedSources have no source_root).
    """
    index, diagnostics = build_shared_identity_index(
        [
            MigrationMappingsDocument(
                artifact_id="test-artifact",
                artifact_revision="v1",
                locator="migrations.yaml",
                content_digest="test-content-digest",
                schema_mappings=tuple(
                    IdentityMappingEntry(
                        source_instance_id=SOURCE_INSTANCE_ID,
                        document_path="test.yaml",
                        pointer=pointer,
                        pointer_tokens=tuple(pointer.strip("/").split("/")),
                        target_id=target_id,
                    )
                    for pointer, target_id in schema_mappings
                ),
            )
        ]
    )
    assert diagnostics == []
    return index


def test_explicit_shared_schema_mapping_overrides_the_owner_scoped_default():
    index = _shared_identity_index(("/components/schemas/Product", "schema:Product"))
    outcome = _map(PRODUCT_SERVICE_DOC, shared_identity=index)

    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.schemas[0].id == "schema:Product"


def test_explicit_mapping_to_the_same_id_with_disagreeing_content_conflicts():
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "ConflictService"},
        "x-aip-service-id": "service:conflict",
        "paths": {
            "/a": {
                "get": {
                    "operationId": "getA",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/A"}}
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
                                "application/json": {"schema": {"$ref": "#/components/schemas/B"}}
                            }
                        }
                    },
                }
            },
        },
        "components": {"schemas": {"A": {"type": "object"}, "B": {"type": "string"}}},
    }
    index = _shared_identity_index(
        ("/components/schemas/A", "schema:Shared"),
        ("/components/schemas/B", "schema:Shared"),
    )
    outcome = _map(doc, shared_identity=index)

    assert outcome.result is IngestionResult.REJECTED_CONFLICT
    assert any(d.code is DiagnosticCode.SCHEMA_CONTENT_CONFLICT for d in outcome.diagnostics)
    assert outcome.model.schemas == []
