from app.sources.manifest_bindings import (
    ArchitectureIdentityBindingsDocument,
    build_binding_index,
    parse_architecture_identity_bindings,
)
from app.sources.model import DiagnosticCode

SOURCE_A = "urn:aip:source:filesystem:" + "a" * 64
SOURCE_B = "urn:aip:source:filesystem:" + "b" * 64


def _document(**bindings_kwargs):
    return {
        "apiVersion": "aip.dev/v1",
        "kind": "ArchitectureIdentityBindings",
        "metadata": {"id": "bindings-1", "revision": "rev-1"},
        "bindings": [
            {
                "sourceInstanceId": bindings_kwargs.get("source_instance_id", SOURCE_A),
                "pointerPrefix": bindings_kwargs.get("pointer_prefix", ""),
                "serviceId": bindings_kwargs.get("service_id", "service:order-service"),
            }
        ],
    }


def test_parse_valid_root_binding():
    parsed, diagnostics = parse_architecture_identity_bindings(_document(), locator="manifest.yaml")
    assert diagnostics == []
    assert parsed is not None
    assert parsed.manifest_id == "bindings-1"
    assert parsed.manifest_revision == "rev-1"
    assert len(parsed.bindings) == 1
    assert parsed.bindings[0].pointer_tokens == ()
    assert parsed.bindings[0].service_id == "service:order-service"


def test_parse_valid_construct_binding():
    document = _document(pointer_prefix="/paths/~1orders")
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert diagnostics == []
    assert parsed.bindings[0].pointer_tokens == ("paths", "/orders")


def test_parse_rejects_additional_top_level_field():
    document = _document()
    document["extra"] = "not allowed"
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics
    assert diagnostics[0].code is DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID


def test_parse_rejects_additional_metadata_field():
    document = _document()
    document["metadata"]["extra"] = "nope"
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID


def test_parse_rejects_additional_binding_field():
    document = _document()
    document["bindings"][0]["extra"] = "nope"
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID


def test_parse_rejects_wrong_api_version():
    document = _document()
    document["apiVersion"] = "aip.dev/v2"
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID


def test_parse_rejects_malformed_pointer():
    document = _document(pointer_prefix="no-leading-slash")
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.MANIFEST_BINDING_POINTER_INVALID


def test_parse_rejects_malformed_service_id():
    document = _document(service_id="not-a-service-id")
    parsed, diagnostics = parse_architecture_identity_bindings(document, locator="manifest.yaml")
    assert parsed is None
    assert diagnostics[0].code is DiagnosticCode.SERVICE_IDENTITY_INVALID


def _index_document(manifest_id: str, revision: str, *bindings):
    return ArchitectureIdentityBindingsDocument(
        manifest_id=manifest_id,
        manifest_revision=revision,
        locator=f"{manifest_id}.yaml",
        bindings=tuple(bindings),
    )


def _binding(source_instance_id: str, pointer_prefix: str, service_id: str):
    from app.sources.manifest_bindings import ArchitectureIdentityBinding
    from app.sources.pointers import decode_pointer_tokens

    return ArchitectureIdentityBinding(
        source_instance_id=source_instance_id,
        pointer_prefix=pointer_prefix,
        pointer_tokens=decode_pointer_tokens(pointer_prefix),
        service_id=service_id,
    )


def test_build_binding_index_is_permutation_independent_across_documents():
    doc_a = _index_document("a", "1", _binding(SOURCE_A, "", "service:order-service"))
    doc_b = _index_document("b", "1", _binding(SOURCE_B, "", "service:payment-service"))

    forward, forward_diagnostics = build_binding_index([doc_a, doc_b])
    backward, backward_diagnostics = build_binding_index([doc_b, doc_a])

    assert forward == backward
    assert forward_diagnostics == backward_diagnostics == []


def test_build_binding_index_is_permutation_independent_within_one_document():
    binding_one = _binding(SOURCE_A, "/paths/~1orders", "service:order-service")
    binding_two = _binding(SOURCE_A, "/paths/~1payments", "service:payment-service")

    doc_forward = _index_document("a", "1", binding_one, binding_two)
    doc_backward = _index_document("a", "1", binding_two, binding_one)

    forward, _ = build_binding_index([doc_forward])
    backward, _ = build_binding_index([doc_backward])
    assert forward == backward


def test_build_binding_index_deduplicates_identical_bindings():
    binding = _binding(SOURCE_A, "", "service:order-service")
    doc_one = _index_document("a", "1", binding)
    doc_two = _index_document("b", "1", binding)

    index, diagnostics = build_binding_index([doc_one, doc_two])
    assert len(index.entries) == 1
    assert diagnostics == []


def test_build_binding_index_flags_overlapping_prefix_conflict():
    outer = _binding(SOURCE_A, "/paths", "service:a")
    inner = _binding(SOURCE_A, "/paths/~1orders", "service:b")
    index, diagnostics = build_binding_index([_index_document("a", "1", outer, inner)])

    assert index.entries  # both entries are kept - conflict is flagged, not silently dropped
    assert any(d.code is DiagnosticCode.SERVICE_IDENTITY_CONFLICT for d in diagnostics)


def test_build_binding_index_flags_duplicate_pointer_different_service_conflict():
    one = _binding(SOURCE_A, "/paths/~1orders", "service:a")
    two = _binding(SOURCE_A, "/paths/~1orders", "service:b")
    _, diagnostics = build_binding_index([_index_document("a", "1", one, two)])

    assert any(d.code is DiagnosticCode.SERVICE_IDENTITY_CONFLICT for d in diagnostics)


def test_build_binding_index_disjoint_prefixes_do_not_conflict():
    one = _binding(SOURCE_A, "/paths/~1orders", "service:order-service")
    two = _binding(SOURCE_A, "/paths/~1payments", "service:payment-service")
    index, diagnostics = build_binding_index([_index_document("a", "1", one, two)])

    assert len(index.entries) == 2
    assert diagnostics == []


def test_build_binding_index_flags_unknown_source_when_known_set_given():
    binding = _binding(SOURCE_A, "", "service:order-service")
    _, diagnostics = build_binding_index(
        [_index_document("a", "1", binding)], known_source_instance_ids={SOURCE_B}
    )
    assert any(d.code is DiagnosticCode.MANIFEST_BINDING_UNKNOWN_SOURCE for d in diagnostics)


def test_binding_index_applicable_to_matches_by_source_and_pointer():
    binding = _binding(SOURCE_A, "/paths/~1orders", "service:order-service")
    index, _ = build_binding_index([_index_document("a", "1", binding)])

    matches = index.applicable_to(
        source_instance_id=SOURCE_A, construct_pointer="/paths/~1orders/get"
    )
    assert len(matches) == 1

    no_matches = index.applicable_to(
        source_instance_id=SOURCE_A, construct_pointer="/paths/~1payments"
    )
    assert no_matches == ()
