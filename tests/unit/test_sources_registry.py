import pytest

from app.canonical.model import ArchitectureModel
from app.sources.model import (
    IngestionResult,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import (
    AdapterOutcome,
    AmbiguousAdapterRegistrationError,
    SourceAdapterRegistry,
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
        "mapping_context_digest": "f" * 64,
        "adapter_identity": "test-adapter",
        "mapping_rule_id": "test-mapping",
        "mapping_rule_version": "v1",
    }
    fields.update(overrides)
    return SourceDescriptor(**fields)


def _loaded(document: dict, **descriptor_overrides) -> LoadedSource:
    return LoadedSource(descriptor=_descriptor(**descriptor_overrides), document=document)


class _FakeAdapter:
    def __init__(self, *, key: str, adapter_identity: str, dependency_phase: int = 0):
        self.key = key
        self.adapter_identity = adapter_identity
        self.mapping_rule_version = "v1"
        self.dependency_phase = dependency_phase

    def supports(self, loaded: LoadedSource) -> bool:
        return self.key in loaded.document

    def map(self, loaded, *, service_identity, upstream_model, mapping_context_digest):
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=ArchitectureModel(),
            diagnostics=(),
            semantic_input_digest="a" * 64,
        )


def test_adapter_for_returns_the_matching_adapter():
    openapi_adapter = _FakeAdapter(key="openapi", adapter_identity="openapi-adapter")
    asyncapi_adapter = _FakeAdapter(key="asyncapi", adapter_identity="asyncapi-adapter")
    registry = SourceAdapterRegistry([openapi_adapter, asyncapi_adapter])

    match = registry.adapter_for(_loaded({"openapi": "3.1.0"}))
    assert match is openapi_adapter


def test_adapter_for_returns_none_when_no_adapter_matches():
    registry = SourceAdapterRegistry([_FakeAdapter(key="openapi", adapter_identity="openapi")])
    assert registry.adapter_for(_loaded({"asyncapi": "2.6.0"})) is None


def test_adapter_for_raises_on_ambiguous_match():
    first = _FakeAdapter(key="shared", adapter_identity="first")
    second = _FakeAdapter(key="shared", adapter_identity="second")
    registry = SourceAdapterRegistry([first, second])

    with pytest.raises(AmbiguousAdapterRegistrationError):
        registry.adapter_for(_loaded({"shared": True}))


def test_phases_returns_sorted_distinct_dependency_phases():
    registry = SourceAdapterRegistry(
        [
            _FakeAdapter(key="a", adapter_identity="a", dependency_phase=1),
            _FakeAdapter(key="b", adapter_identity="b", dependency_phase=0),
            _FakeAdapter(key="c", adapter_identity="c", dependency_phase=0),
        ]
    )
    assert registry.phases() == (0, 1)


def test_adapters_in_phase_filters_correctly():
    phase0 = _FakeAdapter(key="a", adapter_identity="a", dependency_phase=0)
    phase1 = _FakeAdapter(key="b", adapter_identity="b", dependency_phase=1)
    registry = SourceAdapterRegistry([phase0, phase1])

    assert registry.adapters_in_phase(0) == (phase0,)
    assert registry.adapters_in_phase(1) == (phase1,)
    assert registry.adapters_in_phase(2) == ()


def test_empty_registry_has_no_phases_and_no_matches():
    registry = SourceAdapterRegistry([])
    assert registry.phases() == ()
    assert registry.adapter_for(_loaded({"openapi": "3.1.0"})) is None
