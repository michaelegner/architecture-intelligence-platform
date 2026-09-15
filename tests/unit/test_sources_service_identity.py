import pytest

from app.sources.service_identity import (
    PointerBinding,
    ServiceIdentityOutcome,
    ServiceIdentityPath,
    is_valid_service_id,
    resolve_service_identity,
)

VALID_SERVICE_IDS = [
    "service:foo",
    "service:ns:foo",
    "service:9lives",
    "service:a.b-c_d",
    "service:ns.a:foo-b",
]

INVALID_SERVICE_IDS = [
    "Service:foo",
    "SERVICE:FOO",
    "service:",
    "service:a:b:c",
    "service: foo",
    "service:-foo",
    "service:foo:",
    "service:foo bar",
    "service",
    "svc:foo",
]


@pytest.mark.parametrize("service_id", VALID_SERVICE_IDS)
def test_is_valid_service_id_accepts_valid_grammar(service_id):
    assert is_valid_service_id(service_id) is True


@pytest.mark.parametrize("service_id", INVALID_SERVICE_IDS)
def test_is_valid_service_id_rejects_invalid_grammar(service_id):
    assert is_valid_service_id(service_id) is False


SOURCE = "urn:aip:source:filesystem:" + "a" * 64
POINTER = "/paths/~1orders/get"


def test_resolve_service_identity_extension_only_resolves():
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="service:order-service",
        configured_mappings=[],
        manifest_bindings=[],
    )
    assert result.outcome is ServiceIdentityOutcome.RESOLVED
    assert result.service_id == "service:order-service"
    assert result.diagnostics == ()


def test_resolve_service_identity_no_evidence_is_unresolved():
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value=None,
        configured_mappings=[],
        manifest_bindings=[],
    )
    assert result.outcome is ServiceIdentityOutcome.REJECTED_UNSUPPORTED
    assert result.service_id is None
    assert len(result.diagnostics) == 1


def test_resolve_service_identity_malformed_extension_is_invalid():
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="not-a-service-id",
        configured_mappings=[],
        manifest_bindings=[],
    )
    assert result.outcome is ServiceIdentityOutcome.REJECTED_INVALID


def test_resolve_service_identity_agreeing_paths_resolve():
    manifest_binding = PointerBinding(
        source_instance_id=SOURCE,
        pointer_prefix="",
        service_id="service:order-service",
        path=ServiceIdentityPath.MANIFEST_BINDING,
    )
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="service:order-service",
        configured_mappings=[],
        manifest_bindings=[manifest_binding],
    )
    assert result.outcome is ServiceIdentityOutcome.RESOLVED
    assert result.service_id == "service:order-service"


def test_resolve_service_identity_disagreeing_paths_conflict():
    manifest_binding = PointerBinding(
        source_instance_id=SOURCE,
        pointer_prefix="",
        service_id="service:other-service",
        path=ServiceIdentityPath.MANIFEST_BINDING,
    )
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="service:order-service",
        configured_mappings=[],
        manifest_bindings=[manifest_binding],
    )
    assert result.outcome is ServiceIdentityOutcome.REJECTED_CONFLICT
    assert result.service_id is None


def test_resolve_service_identity_malformed_mapping_target_is_invalid():
    bad_mapping = PointerBinding(
        source_instance_id=SOURCE,
        pointer_prefix="",
        service_id="not-a-service-id",
        path=ServiceIdentityPath.CONFIGURED_MAPPING,
    )
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value=None,
        configured_mappings=[bad_mapping],
        manifest_bindings=[],
    )
    assert result.outcome is ServiceIdentityOutcome.REJECTED_INVALID


def test_resolve_service_identity_non_matching_pointer_prefix_is_ignored():
    non_matching = PointerBinding(
        source_instance_id=SOURCE,
        pointer_prefix="/paths/~1invoices",
        service_id="service:invoice-service",
        path=ServiceIdentityPath.MANIFEST_BINDING,
    )
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="service:order-service",
        configured_mappings=[],
        manifest_bindings=[non_matching],
    )
    assert result.outcome is ServiceIdentityOutcome.RESOLVED
    assert result.service_id == "service:order-service"


def test_resolve_service_identity_binding_from_different_source_is_ignored():
    other_source_binding = PointerBinding(
        source_instance_id="urn:aip:source:filesystem:" + "b" * 64,
        pointer_prefix="",
        service_id="service:other-service",
        path=ServiceIdentityPath.MANIFEST_BINDING,
    )
    result = resolve_service_identity(
        source_instance_id=SOURCE,
        construct_pointer=POINTER,
        extension_value="service:order-service",
        configured_mappings=[],
        manifest_bindings=[other_source_binding],
    )
    assert result.outcome is ServiceIdentityOutcome.RESOLVED
    assert result.service_id == "service:order-service"
