from pathlib import Path

import pytest
import yaml

from app.ingestion.scanner import SpecificationType, scan_directory
from app.validation.source_validation import (
    SourceValidationError,
    check_supported_dialect_version,
    find_remote_reference,
    validate_asyncapi_document,
    validate_manifest_document,
    validate_openapi_document,
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

VALID_OPENAPI_DOC = {
    "openapi": "3.1.0",
    "info": {"title": "X"},
    "paths": {
        "/x": {
            "get": {
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/X"}}
                        }
                    }
                }
            }
        }
    },
    "components": {"schemas": {"X": {"type": "object"}}},
}

VALID_ASYNCAPI_DOC = {
    "asyncapi": "2.6.0",
    "info": {"title": "X"},
    "channels": {"x-q": {"publish": {"message": {"$ref": "#/components/messages/X"}}}},
    "components": {"messages": {"X": {"name": "X"}}},
}

VALID_MANIFEST_DOC = {
    "service": "order-service",
    "calls": [{"service": "product-service", "operationId": "getProduct"}],
}


def test_valid_openapi_document_passes():
    validate_openapi_document(VALID_OPENAPI_DOC, source_file="openapi.yaml")


def test_openapi_local_ref_decodes_json_pointer_tokens_in_order():
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "X"},
        "paths": {
            "/x": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/a~01~1b"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {"schemas": {"a~1/b": {"type": "object"}}},
    }

    validate_openapi_document(doc, source_file="openapi.yaml")


def test_openapi_missing_required_field_raises():
    with pytest.raises(SourceValidationError):
        validate_openapi_document({"openapi": "3.1.0", "paths": {}}, source_file="openapi.yaml")


def test_openapi_dangling_ref_raises():
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "X"},
        "paths": {
            "/x": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Missing"}
                                }
                            }
                        }
                    }
                }
            }
        },
    }
    with pytest.raises(SourceValidationError) as exc:
        validate_openapi_document(doc, source_file="openapi.yaml")
    assert "dangling" in str(exc.value)


def test_openapi_relative_file_ref_is_not_flagged_here():
    # As of PR3b, a relative-file $ref (no scheme/authority) is deliberately NOT rejected at this
    # structural-validation layer - existence/containment/cycles are the resolver's job, at map()
    # time, once the approved source root is known. This validator has no notion of sibling files.
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "X"},
        "paths": {
            "/x": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "other-file.yaml#/Foo"}}
                            }
                        }
                    }
                }
            }
        },
    }
    validate_openapi_document(doc, source_file="openapi.yaml")


def test_openapi_remote_ref_is_not_flagged_by_validate_openapi_document():
    # A remote reference is REJECTED_UNSUPPORTED (I1 spec §8.1), a materially different
    # qualification category from the REJECTED_INVALID validate_openapi_document raises for every
    # other structural error - so it is deliberately NOT raised here; find_remote_reference (below)
    # is the adapter's own separate pre-check for this case.
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "X"},
        "paths": {
            "/x": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "https://example.com/foo.yaml#/Bar"}
                                }
                            }
                        }
                    }
                }
            }
        },
    }
    validate_openapi_document(doc, source_file="openapi.yaml")


def test_find_remote_reference_detects_a_scheme_qualified_ref():
    doc = {"paths": {"/x": {"get": {"schema": {"$ref": "https://example.com/foo.yaml#/Bar"}}}}}
    assert find_remote_reference(doc) == "https://example.com/foo.yaml#/Bar"


def test_find_remote_reference_ignores_local_refs():
    doc = {
        "paths": {
            "/x": {
                "get": {
                    "a": {"$ref": "#/components/schemas/X"},
                    "b": {"$ref": "other-file.yaml#/Foo"},
                }
            }
        }
    }
    assert find_remote_reference(doc) is None


def test_valid_asyncapi_document_passes():
    validate_asyncapi_document(VALID_ASYNCAPI_DOC, source_file="asyncapi.yaml")


def test_asyncapi_local_ref_decodes_json_pointer_tokens():
    doc = {
        "asyncapi": "2.6.0",
        "info": {"title": "X"},
        "channels": {"x-q": {"publish": {"message": {"$ref": "#/components/messages/m~1n~0o"}}}},
        "components": {"messages": {"m/n~o": {"name": "X"}}},
    }

    validate_asyncapi_document(doc, source_file="asyncapi.yaml")


def test_asyncapi_missing_required_field_raises():
    with pytest.raises(SourceValidationError):
        validate_asyncapi_document(
            {"asyncapi": "2.6.0", "channels": {}}, source_file="asyncapi.yaml"
        )


def test_asyncapi_dangling_ref_raises():
    doc = {
        "asyncapi": "2.6.0",
        "info": {"title": "X"},
        "channels": {"x-q": {"publish": {"message": {"$ref": "#/components/messages/Missing"}}}},
    }
    with pytest.raises(SourceValidationError) as exc:
        validate_asyncapi_document(doc, source_file="asyncapi.yaml")
    assert "dangling" in str(exc.value)


def test_valid_manifest_document_passes():
    validate_manifest_document(VALID_MANIFEST_DOC, source_file="architecture.yaml")


def test_manifest_missing_service_raises():
    with pytest.raises(SourceValidationError):
        validate_manifest_document({"calls": []}, source_file="architecture.yaml")


def test_check_supported_dialect_version_accepts_exact_match():
    assert (
        check_supported_dialect_version(
            {"openapi": "3.1.0"},
            dialect_key="openapi",
            accepted_versions=frozenset({"3.0.3", "3.1.0", "3.1.2"}),
        )
        is None
    )


def test_check_supported_dialect_version_rejects_unlisted_version():
    error = check_supported_dialect_version(
        {"openapi": "3.1.1"},
        dialect_key="openapi",
        accepted_versions=frozenset({"3.0.3", "3.1.0", "3.1.2"}),
    )
    assert error is not None
    assert "3.1.1" in error


def test_check_supported_dialect_version_rejects_missing_version():
    error = check_supported_dialect_version(
        {}, dialect_key="asyncapi", accepted_versions=frozenset({"2.6.0"})
    )
    assert error is not None
    assert "asyncapi" in error


def test_manifest_call_entry_missing_operation_id_raises():
    doc = {"service": "order-service", "calls": [{"service": "product-service"}]}
    with pytest.raises(SourceValidationError):
        validate_manifest_document(doc, source_file="architecture.yaml")


def test_real_example_fixtures_all_pass_source_validation():
    for source in scan_directory(EXAMPLES_DIR):
        document = yaml.safe_load(source.path.read_text())
        if source.type == SpecificationType.OPENAPI:
            validate_openapi_document(document, source_file=str(source.path))
        elif source.type == SpecificationType.ASYNCAPI:
            validate_asyncapi_document(document, source_file=str(source.path))
        else:
            validate_manifest_document(document, source_file=str(source.path))
