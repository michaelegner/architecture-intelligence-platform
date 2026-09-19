import yaml

from app.sources.model import DiagnosticCode
from app.sources.service_workload_mapping import (
    ServiceWorkloadMappingDocument,
    load_service_workload_mappings,
    parse_service_workload_mappings,
)


def _entry(**overrides):
    entry = {
        "mappingId": "checkout-runtime",
        "serviceId": "service:checkout",
        "kubernetesSourceId": "checkout-cluster",
        "clusterUid": "599e90a5-7ab8-426f-807f-92a65dcc8822",
        "workload": {
            "apiGroup": "apps",
            "kind": "Deployment",
            "namespace": "checkout",
            "name": "checkout",
        },
    }
    entry.update(overrides)
    return entry


def _document(**overrides):
    document = {
        "apiVersion": "aip.dev/v1",
        "kind": "ServiceWorkloadIdentityMappings",
        "metadata": {"id": "v0.5.0-service-workload-identities", "revision": "v1"},
        "mappings": [_entry()],
    }
    document.update(overrides)
    return document


def test_parse_valid_document():
    parsed, diagnostics = parse_service_workload_mappings(
        _document(), locator="mappings.yaml", content_digest="test-digest"
    )
    assert diagnostics == []
    assert parsed is not None
    assert parsed.artifact_id == "v0.5.0-service-workload-identities"
    assert parsed.artifact_revision == "v1"
    assert len(parsed.entries) == 1
    entry = parsed.entries[0]
    assert entry.mapping_id == "checkout-runtime"
    assert entry.service_id == "service:checkout"
    assert entry.kubernetes_source_id == "checkout-cluster"
    assert entry.cluster_uid == "599e90a5-7ab8-426f-807f-92a65dcc8822"
    assert entry.api_group == "apps"
    assert entry.workload_kind == "Deployment"
    assert entry.namespace == "checkout"
    assert entry.name == "checkout"


def test_parse_accepts_each_supported_workload_kind():
    document = _document(
        mappings=[
            _entry(mappingId="a", workload={**_entry()["workload"], "kind": "Deployment"}),
            _entry(mappingId="b", workload={**_entry()["workload"], "kind": "StatefulSet"}),
            _entry(mappingId="c", workload={**_entry()["workload"], "kind": "DaemonSet"}),
        ]
    )
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert diagnostics == []
    assert [entry.workload_kind for entry in parsed.entries] == [
        "Deployment",
        "StatefulSet",
        "DaemonSet",
    ]


def test_parse_accepts_a_document_with_no_mappings_at_all():
    document = {
        "apiVersion": "aip.dev/v1",
        "kind": "ServiceWorkloadIdentityMappings",
        "metadata": {"id": "empty", "revision": "v1"},
    }
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert diagnostics == []
    assert parsed.entries == ()


def test_parse_rejects_additional_top_level_field():
    parsed, diagnostics = parse_service_workload_mappings(
        _document(extra="nope"), locator="mappings.yaml", content_digest="test-digest"
    )
    assert parsed is None
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_parse_rejects_unsupported_workload_kind():
    document = _document(mappings=[_entry(workload={**_entry()["workload"], "kind": "ReplicaSet"})])
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert parsed is None
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_parse_rejects_missing_required_field():
    entry = _entry()
    del entry["clusterUid"]
    document = _document(mappings=[entry])
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert parsed is None
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_parse_rejects_malformed_service_id():
    document = _document(mappings=[_entry(serviceId="not-a-valid-id")])
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert parsed is None
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_TARGET_INVALID]


def test_parse_collapses_identical_duplicate_mappings():
    document = _document(mappings=[_entry(), _entry()])
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert diagnostics == []
    assert len(parsed.entries) == 1


def test_parse_rejects_duplicate_mapping_id_with_differing_content():
    document = _document(
        mappings=[
            _entry(mappingId="checkout-runtime", serviceId="service:checkout"),
            _entry(mappingId="checkout-runtime", serviceId="service:checkout-v2"),
        ]
    )
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert parsed is None
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_DUPLICATE_ID]


def test_parse_preserves_delimiter_bearing_identity_fields():
    document = _document(
        metadata={"id": "artifact:with/delimiters|here", "revision": "rev:1/2"},
        mappings=[_entry(mappingId="mapping:with/colon")],
    )
    parsed, diagnostics = parse_service_workload_mappings(
        document, locator="mappings.yaml", content_digest="test-digest"
    )
    assert diagnostics == []
    assert parsed.artifact_id == "artifact:with/delimiters|here"
    assert parsed.artifact_revision == "rev:1/2"
    assert parsed.entries[0].mapping_id == "mapping:with/colon"


def test_load_service_workload_mappings_from_a_real_file(tmp_path):
    path = tmp_path / "mappings.yaml"
    path.write_text(yaml.safe_dump(_document()))

    documents, diagnostics = load_service_workload_mappings([path])

    assert diagnostics == ()
    assert len(documents) == 1
    [document] = documents
    assert isinstance(document, ServiceWorkloadMappingDocument)
    assert document.locator == str(path)
    assert len(document.content_digest) == 64
    assert len(document.entries) == 1


def test_load_service_workload_mappings_diagnoses_a_missing_file(tmp_path):
    documents, diagnostics = load_service_workload_mappings([tmp_path / "does-not-exist.yaml"])
    assert documents == ()
    assert [d.code for d in diagnostics] == [
        DiagnosticCode.SERVICE_WORKLOAD_MAPPING_FILE_UNAVAILABLE
    ]


def test_load_service_workload_mappings_diagnoses_malformed_yaml(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("not: valid: yaml: [")
    documents, diagnostics = load_service_workload_mappings([path])
    assert documents == ()
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_load_service_workload_mappings_diagnoses_non_mapping_root(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a\n- list\n")
    documents, diagnostics = load_service_workload_mappings([path])
    assert documents == ()
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_load_service_workload_mappings_diagnoses_a_literal_duplicate_yaml_key(tmp_path):
    path = tmp_path / "duplicate-key.yaml"
    path.write_text(
        "apiVersion: aip.dev/v1\n"
        "kind: ServiceWorkloadIdentityMappings\n"
        "metadata:\n"
        "  id: dup\n"
        "  id: dup-again\n"
        "  revision: v1\n"
    )
    documents, diagnostics = load_service_workload_mappings([path])
    assert documents == ()
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_load_service_workload_mappings_diagnoses_a_multi_document_stream(tmp_path):
    path = tmp_path / "multi.yaml"
    path.write_text(yaml.safe_dump(_document()) + "---\n" + yaml.safe_dump(_document()))
    documents, diagnostics = load_service_workload_mappings([path])
    assert documents == ()
    assert [d.code for d in diagnostics] == [DiagnosticCode.SERVICE_WORKLOAD_MAPPING_SHAPE_INVALID]


def test_load_service_workload_mappings_continues_past_one_bad_file(tmp_path):
    good_path = tmp_path / "good.yaml"
    good_path.write_text(yaml.safe_dump(_document(metadata={"id": "good", "revision": "v1"})))
    bad_path = tmp_path / "does-not-exist.yaml"

    documents, diagnostics = load_service_workload_mappings([good_path, bad_path])

    assert len(documents) == 1
    assert documents[0].artifact_id == "good"
    assert [d.code for d in diagnostics] == [
        DiagnosticCode.SERVICE_WORKLOAD_MAPPING_FILE_UNAVAILABLE
    ]
