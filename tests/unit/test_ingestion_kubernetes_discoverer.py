import hashlib
import os

import pytest
import yaml

from app.canonical.infrastructure import KubernetesEvidenceMode
from app.ingestion.kubernetes_adapter import KubernetesSourceAdapter
from app.ingestion.kubernetes_discoverer import KubernetesSourceDiscoverer
from app.ingestion.orchestrator import run_kubernetes_discovery
from app.sources.inventory import InventoryStatus
from app.sources.model import (
    NOT_SUPPLIED,
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


def _resource_yaml(
    name: str = "example", *, uid: str | None = None, resource_version: str | None = None
) -> bytes:
    metadata = {"name": name}
    if uid is not None:
        metadata["uid"] = uid
    if resource_version is not None:
        metadata["resourceVersion"] = resource_version
    return yaml.safe_dump({"apiVersion": "v1", "kind": "Namespace", "metadata": metadata}).encode()


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
    assert loaded.kubernetes_resources[0].document["metadata"]["name"] == "example"
    assert loaded.kubernetes_resources[0].source_pointer == "resources.yaml"
    # I1 spec §7.2: "Every successful load SHALL record... declared/provider revision, where
    # available" - the envelope's own metadata.revision.
    assert loaded.descriptor.declared_provider_revision == "snapshot-revision"
    # I2 Draft 0.2 §4.2 (slice 2b-ii): expectedPriorInventoryRevision: null (the default in
    # _valid_envelope_dict) means "expect no prior committed inventory", not "no check requested".
    assert outcome.expected_prior_inventory_revision is None


def test_accepted_envelope_with_an_explicit_expected_prior_inventory_revision(tmp_path):
    _write_bundle(
        tmp_path,
        envelope_overrides={
            "completeness": {
                **_valid_envelope_dict()["completeness"],
                "expectedPriorInventoryRevision": "urn:aip:inventory-revision:" + "a" * 64,
            }
        },
        files={"resources.yaml": _resource_yaml()},
    )
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.expected_prior_inventory_revision == "urn:aip:inventory-revision:" + "a" * 64


# A safe non-committing fallback (NOT_SUPPLIED) on every rejection path, matching the same
# reasoning already applied to scope_definition_digest: an envelope that hasn't been fully accepted
# doesn't get its declared predecessor claim honored either. Asserted by identity (`is NOT_SUPPLIED`,
# not merely `isinstance`) since this discoverer never constructs its own NotSupplied() - it only
# ever relies on the dataclass field's own default, so the canonical singleton is the only value
# that should ever appear here; `isinstance` alone couldn't catch a regression that accidentally
# constructed a fresh instance instead of using the default.


def test_missing_root_never_reports_an_expected_prior_inventory_revision(tmp_path):
    config = _config(tmp_path / "does-not-exist")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.expected_prior_inventory_revision is NOT_SUPPLIED


def test_missing_envelope_never_reports_an_expected_prior_inventory_revision(tmp_path):
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.expected_prior_inventory_revision is NOT_SUPPLIED


def test_registration_mismatch_never_reports_an_expected_prior_inventory_revision(tmp_path):
    _write_bundle(tmp_path)
    config = _config(tmp_path, cluster_uid="a-different-cluster")
    outcome = KubernetesSourceDiscoverer(config).discover()
    assert outcome.expected_prior_inventory_revision is NOT_SUPPLIED


def test_discovery_scope_id_is_identical_regardless_of_envelope_validity(tmp_path):
    # discovery_scope_id (§6/I1's own DiscoveryScopeId formula) depends only on configured values
    # and must never move. scope_definition_digest is different: once an envelope is accepted, its
    # own declared namespaces participate (§8), so the digest legitimately differs from the
    # config-only fallback used while no valid envelope has been read yet.
    config = _config(tmp_path)
    without_envelope = KubernetesSourceDiscoverer(config).discover()
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    with_envelope = KubernetesSourceDiscoverer(config).discover()
    assert without_envelope.discovery_scope_id == with_envelope.discovery_scope_id
    assert without_envelope.scope_definition_digest != with_envelope.scope_definition_digest


def test_scope_definition_digest_changes_with_accepted_envelope_namespaces(tmp_path):
    config = _config(tmp_path)
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    first = KubernetesSourceDiscoverer(config).discover()

    _write_bundle(
        tmp_path,
        envelope_overrides={"scope": {**_valid_envelope_dict()["scope"], "namespaces": ["other"]}},
        files={"resources.yaml": _resource_yaml()},
    )
    second = KubernetesSourceDiscoverer(config).discover()

    assert first.discovery_scope_id == second.discovery_scope_id
    assert first.scope_definition_digest != second.scope_definition_digest
    assert (
        first.loaded_sources[0].descriptor.scope_definition_digest == first.scope_definition_digest
    )


# --- run_kubernetes_discovery: inventory_status classification -------------------------------


def test_missing_root_classifies_the_run_as_failed(tmp_path):
    config = _config(tmp_path / "does-not-exist")
    result = run_kubernetes_discovery(config)
    assert result.inventory_status is InventoryStatus.FAILED


def test_missing_envelope_classifies_the_run_as_partial_not_failed(tmp_path):
    config = _config(tmp_path)
    result = run_kubernetes_discovery(config)
    assert result.inventory_status is InventoryStatus.PARTIAL


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits, chmod is a no-op")
def test_unreadable_root_classifies_the_run_as_partial_not_failed(tmp_path):
    # A root that exists but cannot be traversed (e.g. chmod 0o000) is NOT "acquisition fails
    # before a stable source can be identified" - a Kubernetes source's identity is computable
    # from configured values alone (§6), regardless of whether its root is readable. is_dir()
    # itself still returns True here (it only requires the *parent* to be traversable), so this
    # falls through to validate_kubernetes_snapshot, which now converts the resulting permission
    # error into a per-source rejection - PARTIAL, matching an unreadable/missing envelope exactly.
    config = _config(tmp_path)
    tmp_path.chmod(0o000)
    try:
        result = run_kubernetes_discovery(config)
    finally:
        tmp_path.chmod(0o755)
    assert result.inventory_status is InventoryStatus.PARTIAL


def test_valid_matching_envelope_classifies_the_run_as_complete(tmp_path):
    # CAPTURED_RESOURCE mode (_MATCHING_CONFIG_KWARGS) needs a capture-identity-valid resource for
    # the adapter's own kubernetes_mapping validation to accept the source (see the adapter test
    # above for why a bare Namespace still maps to an empty model).
    _write_bundle(
        tmp_path,
        files={"resources.yaml": _resource_yaml(uid="namespace-uid", resource_version="1")},
    )
    config = _config(tmp_path)
    result = run_kubernetes_discovery(config)
    assert result.inventory_status is InventoryStatus.COMPLETE


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
    # _MATCHING_CONFIG_KWARGS declares CAPTURED_RESOURCE evidence mode, so the one bundled
    # resource needs metadata.uid/resourceVersion to pass kubernetes_mapping's own per-resource
    # validation - a bare Namespace is never promoted to an entity either way (I2 §7.1 only
    # promotes Workload/Pod kinds), so the model stays empty.
    _write_bundle(
        tmp_path,
        files={"resources.yaml": _resource_yaml(uid="namespace-uid", resource_version="1")},
    )
    config = _config(tmp_path)
    outcome = KubernetesSourceDiscoverer(config).discover()
    loaded = outcome.loaded_sources[0]

    adapter = KubernetesSourceAdapter()
    result = adapter.map(loaded, **_outcome_kwargs())
    assert result.result is IngestionResult.ACCEPTED
    assert result.diagnostics == ()
    assert result.semantic_input_digest is not None
    assert result.model.infrastructure_entities == []
    assert result.model.infrastructure_contributions == []
    assert result.model.infrastructure_claims == []
    assert result.model.provenance == []
    assert result.model.services == []
