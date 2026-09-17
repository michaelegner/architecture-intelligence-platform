import hashlib

import yaml

from app.canonical.infrastructure import KubernetesEvidenceMode
from app.ingestion.kubernetes_adapter import KubernetesSourceAdapter
from app.ingestion.kubernetes_discoverer import KubernetesSourceDiscoverer
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    KubernetesSourceConfig,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import AdapterOutcome

_MATCHING_CONFIG_KWARGS = {
    "id": "configured-kubernetes-source",
    "envelope_relative_path": "envelope.yaml",
    "configured_scope_id": "configured-kubernetes-scope",
    "cluster_uid": "independently-established-cluster-identity",
    "evidence_mode": KubernetesEvidenceMode.CAPTURED_RESOURCE,
    "authorized_producer": "attributable-producer",
    "authority_record": "configured-authority-record",
}


def _valid_envelope_dict() -> dict:
    return {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": "snapshot-example",
            "revision": "snapshot-revision",
            "producer": "attributable-producer",
            "capturedAt": "2026-09-15T10:00:00Z",
        },
        "source": {
            "configuredSourceId": "configured-kubernetes-source",
            "configuredScopeId": "configured-kubernetes-scope",
            "clusterUid": "independently-established-cluster-identity",
            "clusterIdentityEvidenceRef": "retained-identity-evidence",
            "mode": "CAPTURED_RESOURCE",
        },
        "scope": {
            "namespaces": ["example"],
            "resourceTypes": [
                "v1/Namespace",
                "v1/Pod",
                "v1/Service",
                "apps/v1/Deployment",
                "apps/v1/StatefulSet",
                "apps/v1/DaemonSet",
                "apps/v1/ReplicaSet",
                "networking.k8s.io/v1/Ingress",
            ],
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "configured-authority-record",
            "expectedPriorInventoryRevision": None,
        },
        "files": [],
    }


def _resource_yaml(name: str = "example") -> bytes:
    return yaml.safe_dump(
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name}}
    ).encode()


def _write_bundle(
    tmp_path, *, envelope_overrides=None, files: dict[str, bytes] | None = None
) -> None:
    doc = _valid_envelope_dict()
    if envelope_overrides:
        doc.update(envelope_overrides)
    files = files if files is not None else {}
    doc["files"] = [
        {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in files.items()
    ]
    (tmp_path / "envelope.yaml").write_bytes(yaml.safe_dump(doc).encode())
    for path, content in files.items():
        (tmp_path / path).write_bytes(content)


def _config(tmp_path, **overrides) -> KubernetesSourceConfig:
    kwargs = {**_MATCHING_CONFIG_KWARGS, "root": tmp_path, **overrides}
    return KubernetesSourceConfig(**kwargs)


# --- KubernetesSourceDiscoverer.discover() ---------------------------------------------------


def test_missing_root_is_failed_enumeration(tmp_path):
    config = _config(tmp_path / "does-not-exist")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.enumeration_complete is False
    assert outcome.loaded_sources == ()
    assert outcome.diagnostics[0].code is DiagnosticCode.SOURCE_ROOT_UNAVAILABLE
    assert outcome.discovery_scope_id is not None
    assert outcome.scope_definition_digest is not None


def test_missing_envelope_is_one_rejected_loaded_source_not_failed_enumeration(tmp_path):
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.enumeration_complete is True
    assert len(outcome.loaded_sources) == 1
    loaded = outcome.loaded_sources[0]
    assert loaded.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE
    assert loaded.descriptor.source_kind is SourceKind.KUBERNETES
    # §6: SourceInstanceId is computable from configured values alone, even here.
    assert loaded.descriptor.source_instance_id.startswith("urn:aip:source:kubernetes:")


def test_invalid_envelope_shape_is_one_rejected_loaded_source(tmp_path):
    _write_bundle(tmp_path, envelope_overrides={"kind": "NotASnapshot"})
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.enumeration_complete is True
    assert len(outcome.loaded_sources) == 1
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_cluster_uid_mismatch_is_cluster_identity_unresolved(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, cluster_uid="a-different-cluster")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert len(outcome.loaded_sources) == 1
    assert (
        outcome.loaded_sources[0].diagnostics[0].code
        is DiagnosticCode.K8S_CLUSTER_IDENTITY_UNRESOLVED
    )


def test_configured_source_id_mismatch_is_snapshot_invalid(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, id="a-different-source-id")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_configured_scope_id_mismatch_is_snapshot_invalid(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, configured_scope_id="a-different-scope-id")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_evidence_mode_mismatch_is_snapshot_invalid(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, evidence_mode=KubernetesEvidenceMode.DECLARED_MANIFEST)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_authorized_producer_mismatch_is_snapshot_invalid(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, authorized_producer="a-different-producer")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_authority_record_mismatch_is_snapshot_invalid(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, authority_record="a-different-authority")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.loaded_sources[0].diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_valid_matching_envelope_produces_a_correct_loaded_source(tmp_path):
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.enumeration_complete is True
    assert len(outcome.loaded_sources) == 1
    loaded = outcome.loaded_sources[0]
    assert loaded.diagnostics == []
    assert loaded.descriptor.source_kind is SourceKind.KUBERNETES
    assert loaded.descriptor.source_instance_id.startswith("urn:aip:source:kubernetes:")
    assert loaded.document.get("kind") == "KubernetesSourceSnapshot"
    assert len(loaded.kubernetes_resources) == 1
    assert loaded.kubernetes_resources[0]["metadata"]["name"] == "example"


def test_discovery_scope_id_is_identical_regardless_of_envelope_validity(tmp_path):
    config = _config(tmp_path)
    without_envelope = KubernetesSourceDiscoverer(config).discover()
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    with_envelope = KubernetesSourceDiscoverer(config).discover()
    assert without_envelope.discovery_scope_id == with_envelope.discovery_scope_id
    assert without_envelope.scope_definition_digest == with_envelope.scope_definition_digest


# --- KubernetesSourceAdapter -------------------------------------------------------------------


def _outcome_kwargs():
    return {
        "service_identity": None,
        "shared_identity": None,
        "upstream_model": None,
        "mapping_context_digest": "a" * 64,
    }


def test_adapter_supports_only_kubernetes_sources():
    adapter = KubernetesSourceAdapter()
    kubernetes_descriptor = SourceDescriptor(
        source_instance_id="urn:aip:source:kubernetes:" + "a" * 64,
        source_kind=SourceKind.KUBERNETES,
        locator="cluster",
        discovery_scope_id="urn:aip:discovery-scope:" + "a" * 64,
        scope_definition_digest="a" * 64,
        content_sha256="a" * 64,
        semantic_input_digest="",
        mapping_context_digest="",
        adapter_identity="",
        mapping_rule_id="",
        mapping_rule_version="",
    )
    filesystem_descriptor = kubernetes_descriptor.model_copy(
        update={"source_kind": SourceKind.FILESYSTEM}
    )
    assert adapter.supports(LoadedSource(descriptor=kubernetes_descriptor, document={})) is True
    assert adapter.supports(LoadedSource(descriptor=filesystem_descriptor, document={})) is False


def test_adapter_maps_each_diagnostic_code_to_the_correct_result():
    adapter = KubernetesSourceAdapter()
    expected = {
        DiagnosticCode.K8S_CLUSTER_IDENTITY_UNRESOLVED: IngestionResult.REJECTED_UNSUPPORTED,
        DiagnosticCode.K8S_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
        DiagnosticCode.K8S_SNAPSHOT_INVALID: IngestionResult.REJECTED_INVALID,
        DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE: IngestionResult.REJECTED_INVALID,
    }
    for code, expected_result in expected.items():
        descriptor = SourceDescriptor(
            source_instance_id="urn:aip:source:kubernetes:" + "a" * 64,
            source_kind=SourceKind.KUBERNETES,
            locator="cluster",
            discovery_scope_id="urn:aip:discovery-scope:" + "a" * 64,
            scope_definition_digest="a" * 64,
            content_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            semantic_input_digest="",
            mapping_context_digest="",
            adapter_identity="",
            mapping_rule_id="",
            mapping_rule_version="",
        )
        loaded = LoadedSource(
            descriptor=descriptor,
            document={},
            diagnostics=[IngestionDiagnostic(code=code, message="rejected")],
        )
        outcome = adapter.map(loaded, **_outcome_kwargs())
        assert isinstance(outcome, AdapterOutcome)
        assert outcome.result is expected_result
        assert outcome.semantic_input_digest is None
        assert outcome.model.infrastructure_entities == []


def test_adapter_accepts_a_clean_loaded_source_with_an_empty_model(tmp_path):
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    loaded = outcome.loaded_sources[0]

    adapter = KubernetesSourceAdapter()
    result = adapter.map(loaded, **_outcome_kwargs())
    assert result.result is IngestionResult.ACCEPTED
    assert result.diagnostics == ()
    assert result.semantic_input_digest is not None
    assert result.model.infrastructure_entities == []
    assert result.model.services == []
