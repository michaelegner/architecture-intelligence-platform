import hashlib
import io
import os
from pathlib import Path
from typing import Self

import pytest
import yaml
from pydantic import ValidationError

from app.sources.kubernetes_envelope import (
    EXPECTED_RESOURCE_TYPES,
    MAX_FILE_COUNT,
    MAX_RESOURCE_OBJECT_COUNT,
    MAX_TOTAL_BYTES,
    MAX_YAML_NESTING_DEPTH,
    KubernetesEnvelopeLimitExceeded,
    KubernetesEnvelopeMalformedError,
    KubernetesSourceSnapshot,
    _read_at_most,
    load_bounded_yaml_documents,
    parse_kubernetes_envelope,
    validate_kubernetes_snapshot,
)
from app.sources.model import DiagnosticCode, IngestionResult

_SORTED_RESOURCE_TYPES = sorted(EXPECTED_RESOURCE_TYPES)


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
            "resourceTypes": list(_SORTED_RESOURCE_TYPES),
        },
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "configured-authority-record",
            "expectedPriorInventoryRevision": None,
        },
        "files": [],
    }


def _dump(document: dict) -> bytes:
    return yaml.safe_dump(document).encode()


def _valid_envelope_bytes(**scope_overrides) -> bytes:
    doc = _valid_envelope_dict()
    doc["scope"].update(scope_overrides)
    return _dump(doc)


# --- parse_kubernetes_envelope: happy path --------------------------------------------------


def test_valid_envelope_parses():
    envelope = parse_kubernetes_envelope(_valid_envelope_bytes())
    assert envelope.metadata.id == "snapshot-example"
    assert envelope.source.cluster_uid == "independently-established-cluster-identity"
    assert envelope.source.mode == "CAPTURED_RESOURCE"
    assert envelope.scope.namespaces == ["example"]
    assert set(envelope.scope.resource_types) == EXPECTED_RESOURCE_TYPES
    assert envelope.completeness.status == "COMPLETE"
    assert envelope.completeness.expected_prior_inventory_revision is None
    assert envelope.files == []


def test_json_envelope_parses_too():
    import json

    doc = _valid_envelope_dict()
    envelope = parse_kubernetes_envelope(json.dumps(doc).encode())
    assert envelope.metadata.id == "snapshot-example"


# --- §4.2 shape rules, one violated at a time ------------------------------------------------


def test_wrong_api_version_rejected():
    doc = _valid_envelope_dict()
    doc["apiVersion"] = "aip.dev/v2"
    with pytest.raises(ValidationError, match="apiVersion"):
        parse_kubernetes_envelope(_dump(doc))


def test_wrong_kind_rejected():
    doc = _valid_envelope_dict()
    doc["kind"] = "SomethingElse"
    with pytest.raises(ValidationError, match="kind"):
        parse_kubernetes_envelope(_dump(doc))


def test_unknown_top_level_field_rejected():
    doc = _valid_envelope_dict()
    doc["unexpectedField"] = "nope"
    with pytest.raises(ValidationError):
        parse_kubernetes_envelope(_dump(doc))


def test_unknown_nested_field_rejected():
    doc = _valid_envelope_dict()
    doc["metadata"]["unexpected"] = "nope"
    with pytest.raises(ValidationError):
        parse_kubernetes_envelope(_dump(doc))


def test_missing_required_field_rejected():
    doc = _valid_envelope_dict()
    del doc["source"]["clusterUid"]
    with pytest.raises(ValidationError):
        parse_kubernetes_envelope(_dump(doc))


@pytest.mark.parametrize(
    "path",
    [
        ("metadata", "id"),
        ("metadata", "producer"),
        ("source", "configuredSourceId"),
        ("source", "clusterUid"),
        ("completeness", "authorityRef"),
    ],
)
def test_empty_attribution_string_rejected(path):
    doc = _valid_envelope_dict()
    node = doc
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = ""
    with pytest.raises(ValidationError):
        parse_kubernetes_envelope(_dump(doc))


def test_invalid_evidence_mode_rejected():
    doc = _valid_envelope_dict()
    doc["source"]["mode"] = "OBSERVED"
    with pytest.raises(ValidationError, match="DECLARED_MANIFEST or CAPTURED_RESOURCE"):
        parse_kubernetes_envelope(_dump(doc))


def test_empty_namespaces_rejected():
    with pytest.raises(ValidationError, match="non-empty"):
        parse_kubernetes_envelope(_valid_envelope_bytes(namespaces=[]))


def test_wildcard_namespace_rejected():
    with pytest.raises(ValidationError, match="wildcard"):
        parse_kubernetes_envelope(_valid_envelope_bytes(namespaces=["*"]))


def test_unsorted_namespaces_rejected():
    with pytest.raises(ValidationError, match="sorted"):
        parse_kubernetes_envelope(_valid_envelope_bytes(namespaces=["b", "a"]))


def test_duplicate_namespaces_rejected():
    with pytest.raises(ValidationError, match="duplicate-free"):
        parse_kubernetes_envelope(_valid_envelope_bytes(namespaces=["a", "a"]))


def test_resource_types_missing_one_entry_rejected():
    incomplete = _SORTED_RESOURCE_TYPES[:-1]
    with pytest.raises(ValidationError, match="eight-entry set"):
        parse_kubernetes_envelope(_valid_envelope_bytes(resourceTypes=incomplete))


def test_resource_types_extra_entry_rejected():
    extra = [*_SORTED_RESOURCE_TYPES, "v1/ConfigMap"]
    with pytest.raises(ValidationError, match="eight-entry set"):
        parse_kubernetes_envelope(_valid_envelope_bytes(resourceTypes=extra))


def test_resource_types_any_order_accepted():
    """§4.2's own text says "exact eight-entry set" - set language, not list-order equality."""
    reversed_order = list(reversed(_SORTED_RESOURCE_TYPES))
    envelope = parse_kubernetes_envelope(_valid_envelope_bytes(resourceTypes=reversed_order))
    assert set(envelope.scope.resource_types) == EXPECTED_RESOURCE_TYPES


def test_duplicate_file_paths_rejected():
    doc = _valid_envelope_dict()
    doc["files"] = [
        {"path": "a.yaml", "sha256": "a" * 64},
        {"path": "a.yaml", "sha256": "b" * 64},
    ]
    with pytest.raises(ValidationError, match="unique"):
        parse_kubernetes_envelope(_dump(doc))


@pytest.mark.parametrize(
    "bad_path",
    [
        "../escape.yaml",
        "..",
        "a/../../escape.yaml",
        "a/../b.yaml",  # resolvable, but not already normalized - §4.2 requires it to already be
        "./b.yaml",
        "a//b.yaml",
        "a/",
        "a\\b.yaml",
    ],
)
def test_non_normalized_or_traversing_file_path_rejected(bad_path):
    # §4.2: "File paths are unique normalized relative POSIX paths." The producer must supply an
    # already-canonical path; this is not resolved/collapsed on their behalf (unlike $ref
    # resolution elsewhere in this codebase), since silently accepting a non-normalized form would
    # let two differently-spelled entries alias the same file, undermining the spec's own
    # uniqueness requirement over the *supplied* path list.
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": bad_path, "sha256": "a" * 64}]
    with pytest.raises(ValidationError, match="normalized relative POSIX path"):
        parse_kubernetes_envelope(_dump(doc))


def test_absolute_file_path_rejected():
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": "/etc/passwd", "sha256": "a" * 64}]
    with pytest.raises(ValidationError, match="absolute path"):
        parse_kubernetes_envelope(_dump(doc))


@pytest.mark.parametrize("bad_digest", ["short", "g" * 64, "A" * 64])
def test_malformed_sha256_rejected(bad_digest):
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": "a.yaml", "sha256": bad_digest}]
    with pytest.raises(ValidationError, match="hex digest"):
        parse_kubernetes_envelope(_dump(doc))


def test_empty_expected_prior_inventory_revision_rejected():
    doc = _valid_envelope_dict()
    doc["completeness"]["expectedPriorInventoryRevision"] = ""
    with pytest.raises(ValidationError, match="must not be an empty string"):
        parse_kubernetes_envelope(_dump(doc))


def test_non_empty_expected_prior_inventory_revision_accepted():
    doc = _valid_envelope_dict()
    doc["completeness"]["expectedPriorInventoryRevision"] = "urn:aip:inventory-revision:abc"
    envelope = parse_kubernetes_envelope(_dump(doc))
    assert envelope.completeness.expected_prior_inventory_revision == (
        "urn:aip:inventory-revision:abc"
    )


def test_more_than_one_document_rejected():
    with pytest.raises(KubernetesEnvelopeMalformedError, match="exactly one"):
        parse_kubernetes_envelope(_valid_envelope_bytes() + b"---\nfoo: bar\n")


def test_non_mapping_root_rejected():
    with pytest.raises(KubernetesEnvelopeMalformedError, match="mapping"):
        parse_kubernetes_envelope(b"- a\n- b\n")


# --- Hardened YAML loading: security/bounds -------------------------------------------------


def test_yaml_alias_rejected():
    with pytest.raises(KubernetesEnvelopeLimitExceeded, match="alias"):
        load_bounded_yaml_documents(b"anchor: &a foo\nrepeat: *a\n")


def test_custom_tag_rejected():
    with pytest.raises(KubernetesEnvelopeLimitExceeded, match="tag"):
        load_bounded_yaml_documents(b"a: !CustomTag foo\n")


def test_duplicate_mapping_key_rejected():
    with pytest.raises(KubernetesEnvelopeMalformedError, match="duplicate mapping key"):
        load_bounded_yaml_documents(b"a: 1\na: 2\n")


def test_unhashable_mapping_key_is_a_clean_rejection_not_a_crash():
    # YAML permits a complex (e.g. sequence) mapping key - `? [a, b]\n: value` - which is
    # unhashable. This must not leak a raw TypeError past the duplicate-key check.
    with pytest.raises(KubernetesEnvelopeMalformedError, match="unhashable"):
        load_bounded_yaml_documents(b"? [a, b]\n: value\n")


def _nested_sequence(depth: int) -> bytes:
    return (("[" * depth) + "1" + ("]" * depth)).encode()


def test_nesting_at_the_boundary_is_accepted():
    # A document composed of `depth` nested sequences has a maximum compose depth of `depth + 1`
    # (the innermost scalar) - `depth = MAX_YAML_NESTING_DEPTH - 1` lands exactly on the bound.
    load_bounded_yaml_documents(_nested_sequence(MAX_YAML_NESTING_DEPTH - 1))


def test_nesting_one_past_the_boundary_is_rejected():
    with pytest.raises(KubernetesEnvelopeLimitExceeded, match="nesting"):
        load_bounded_yaml_documents(_nested_sequence(MAX_YAML_NESTING_DEPTH))


def test_multi_document_yaml_stream_loads_all_documents():
    documents = load_bounded_yaml_documents(b"a: 1\n---\nb: 2\n")
    assert documents == [{"a": 1}, {"b": 2}]


# --- validate_kubernetes_snapshot: bounded sanitized loading, end to end ---------------------


def _resource_yaml(name: str = "example") -> bytes:
    return yaml.safe_dump(
        {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name}}
    ).encode()


def _write_bundle(tmp_path, *, files: dict[str, bytes], envelope_overrides=None) -> None:
    """Writes an envelope (`envelope.yaml`) plus every file in `files` (path -> raw bytes) under
    `tmp_path`, with the envelope's own `files` list computed to match exactly."""
    doc = _valid_envelope_dict()
    if envelope_overrides:
        doc.update(envelope_overrides)
    doc["files"] = [
        {"path": path, "sha256": hashlib.sha256(content).hexdigest()}
        for path, content in files.items()
    ]
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    for path, content in files.items():
        (tmp_path / path).write_bytes(content)


_FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "kubernetes" / "i2"


def test_validate_kubernetes_snapshot_accepts_the_checked_in_real_fixture_bundle():
    # A non-synthetic-shaped bundle (a Namespace/Deployment/Pod/Service, cross-referencing a real
    # namespace by name) checked into the repo, distinct from every other test's per-case generated
    # `tmp_path` bundle.
    result = validate_kubernetes_snapshot(
        root=_FIXTURES_ROOT, envelope_relative_path="envelope.yaml"
    )
    assert result.result is IngestionResult.ACCEPTED
    assert result.envelope is not None
    assert result.envelope.source.cluster_uid == "d3adbeef-0000-4000-8000-000000000001"
    resource_kinds = sorted(entry.document["kind"] for entry in result.resources)
    assert resource_kinds == ["Deployment", "Namespace", "Pod", "Service"]
    assert all(entry.source_pointer == "resources.yaml" for entry in result.resources)


def test_validate_kubernetes_snapshot_accepts_a_well_formed_bundle(tmp_path):
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.ACCEPTED
    assert result.diagnostics == ()
    assert len(result.resources) == 1
    assert result.resources[0].source_pointer == "resources.yaml"
    assert result.resources[0].document == {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": "example"},
    }
    assert result.envelope_content_sha256 is not None
    assert isinstance(result.envelope, KubernetesSourceSnapshot)


def test_validate_kubernetes_snapshot_accepts_an_explicit_empty_bundle(tmp_path):
    _write_bundle(tmp_path, files={})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.ACCEPTED
    assert result.resources == ()


def test_missing_envelope_file_is_rejected(tmp_path):
    result = validate_kubernetes_snapshot(
        root=tmp_path, envelope_relative_path="does-not-exist.yaml"
    )
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits, chmod is a no-op")
def test_unreadable_envelope_file_is_rejected(tmp_path):
    envelope_path = tmp_path / "envelope.yaml"
    envelope_path.write_bytes(_valid_envelope_bytes())
    envelope_path.chmod(0o000)
    try:
        result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    finally:
        envelope_path.chmod(0o644)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


@pytest.mark.skipif(os.geteuid() == 0, reason="root bypasses permission bits, chmod is a no-op")
def test_unreadable_listed_file_is_rejected(tmp_path):
    content = _resource_yaml()
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": "resources.yaml", "sha256": hashlib.sha256(content).hexdigest()}]
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    resource_path = tmp_path / "resources.yaml"
    resource_path.write_bytes(content)
    resource_path.chmod(0o000)
    try:
        result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    finally:
        resource_path.chmod(0o644)
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_circular_symlink_envelope_is_rejected(tmp_path):
    envelope_path = tmp_path / "envelope.yaml"
    other = tmp_path / "other.yaml"
    envelope_path.symlink_to(other)
    other.symlink_to(envelope_path)
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_envelope_escaping_the_root_is_rejected(tmp_path):
    outside = tmp_path.parent / "outside-envelope.yaml"
    outside.write_bytes(_valid_envelope_bytes())
    try:
        result = validate_kubernetes_snapshot(
            root=tmp_path, envelope_relative_path="../outside-envelope.yaml"
        )
        assert result.result is IngestionResult.REJECTED_INVALID
        assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE
    finally:
        outside.unlink()


def test_malformed_envelope_shape_is_rejected(tmp_path):
    doc = _valid_envelope_dict()
    doc["kind"] = "NotASnapshot"
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID


def test_envelope_hardening_violation_is_a_limit_exceeded_rejection(tmp_path):
    (tmp_path / "envelope.yaml").write_bytes(b"a: &x 1\nb: *x\n")
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_malformed_envelope_diagnostic_does_not_leak_an_unknown_fields_raw_value(tmp_path):
    # §5/§10: "Diagnostics never dump rejected resource payloads" / "sanitized reasons... expose no
    # raw Secret/environment contents." Pydantic's own str(ValidationError) would otherwise embed
    # an unrecognized field's actual value verbatim.
    doc = _valid_envelope_dict()
    doc["backdoor"] = "SENTINEL_SECRET_VALUE"
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INVALID
    assert "SENTINEL_SECRET_VALUE" not in result.diagnostics[0].message
    assert "backdoor" in result.diagnostics[0].message


def test_listed_file_diagnostic_does_not_leak_a_yaml_source_snippet(tmp_path):
    # A MarkedYAMLError's own str() embeds a literal source-line snippet - here, a custom tag's
    # value - which is the same "never dump rejected payloads" leak, in YAML-error shape.
    content = b"a: !CustomTag SENTINEL_SECRET_VALUE\n"
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": "resources.yaml", "sha256": hashlib.sha256(content).hexdigest()}]
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    (tmp_path / "resources.yaml").write_bytes(content)
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED
    assert "SENTINEL_SECRET_VALUE" not in result.diagnostics[0].message


def test_incomplete_status_is_rejected(tmp_path):
    _write_bundle(
        tmp_path,
        files={"resources.yaml": _resource_yaml()},
        envelope_overrides={
            "completeness": {
                "status": "PARTIAL",
                "authorityRef": "configured-authority-record",
                "expectedPriorInventoryRevision": None,
            }
        },
    )
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_missing_listed_file_is_rejected(tmp_path):
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    (tmp_path / "resources.yaml").unlink()
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_sha256_mismatch_is_rejected(tmp_path):
    _write_bundle(tmp_path, files={"resources.yaml": _resource_yaml()})
    (tmp_path / "resources.yaml").write_bytes(_resource_yaml("tampered"))
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_unparseable_listed_file_is_rejected(tmp_path):
    bad_yaml = b"a: [unterminated"
    _write_bundle(tmp_path, files={"resources.yaml": bad_yaml})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_INVALID
    assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE


def test_listed_file_hardening_violation_is_a_limit_exceeded_rejection(tmp_path):
    aliased = b"a: &x 1\nb: *x\n"
    _write_bundle(tmp_path, files={"resources.yaml": aliased})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_listed_file_escaping_the_root_via_symlink_is_rejected(tmp_path):
    outside_dir = tmp_path.parent / "k8s-envelope-escape-target"
    outside_dir.mkdir(exist_ok=True)
    try:
        (outside_dir / "secret.yaml").write_bytes(_resource_yaml("secret"))
        link = tmp_path / "resources.yaml"
        link.symlink_to(outside_dir / "secret.yaml")

        doc = _valid_envelope_dict()
        doc["files"] = [
            {
                "path": "resources.yaml",
                "sha256": hashlib.sha256(_resource_yaml("secret")).hexdigest(),
            }
        ]
        (tmp_path / "envelope.yaml").write_bytes(_dump(doc))

        result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
        assert result.result is IngestionResult.REJECTED_INVALID
        assert result.diagnostics[0].code is DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE
    finally:
        import shutil

        shutil.rmtree(outside_dir, ignore_errors=True)


def test_file_count_at_the_boundary_is_accepted_and_one_over_is_rejected(tmp_path):
    def _resource_files(count: int) -> dict[str, bytes]:
        return {f"r{i}.yaml": _resource_yaml(f"ns-{i}") for i in range(count)}

    _write_bundle(tmp_path, files=_resource_files(MAX_FILE_COUNT))
    accepted = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert accepted.result is IngestionResult.ACCEPTED
    assert len(accepted.resources) == MAX_FILE_COUNT

    _write_bundle(tmp_path, files=_resource_files(MAX_FILE_COUNT + 1))
    rejected = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert rejected.result is IngestionResult.REJECTED_UNSUPPORTED
    assert rejected.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_total_bytes_at_the_boundary_is_accepted_and_one_over_is_rejected(tmp_path):
    # The envelope's own byte length is constant regardless of the resource file's content (only a
    # fixed-length 64-character sha256 hex digest depends on it), so it can be measured once with a
    # placeholder and then used to compute a resource file that lands exactly on the boundary.
    _write_bundle(tmp_path, files={"resources.yaml": b""})
    envelope_length = len((tmp_path / "envelope.yaml").read_bytes())
    target_resource_length = MAX_TOTAL_BYTES - envelope_length
    assert target_resource_length > 6

    at_boundary = b"a: '" + b"x" * (target_resource_length - 6) + b"'\n"
    assert len(at_boundary) == target_resource_length
    _write_bundle(tmp_path, files={"resources.yaml": at_boundary})
    assert len((tmp_path / "envelope.yaml").read_bytes()) + len(at_boundary) == MAX_TOTAL_BYTES
    accepted = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert accepted.result is IngestionResult.ACCEPTED

    one_byte_over = at_boundary[:-1] + b"y'\n"
    _write_bundle(tmp_path, files={"resources.yaml": one_byte_over})
    rejected = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert rejected.result is IngestionResult.REJECTED_UNSUPPORTED
    assert rejected.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_read_at_most_boundary_and_one_over(tmp_path):
    # Direct unit coverage of the primitive the byte bound is actually built on: a stat()-then-
    # read_bytes() pair is a TOCTOU race (the file can grow between the two calls), so the bound
    # must be enforced by the read call itself, not by trusting a size measured beforehand.
    path = tmp_path / "data.bin"
    path.write_bytes(b"x" * 10)
    assert _read_at_most(path, 9) is None
    assert _read_at_most(path, 10) == b"x" * 10
    assert _read_at_most(path, 11) == b"x" * 10


def test_read_at_most_never_reads_more_than_the_limit_plus_one_byte(tmp_path, monkeypatch):
    # A sparse file (no real content materialized) large enough that fully reading it would be
    # unreasonably slow if this regressed to an unbounded read - proves the read call itself is
    # capped, independent of the file's actual on-disk size. `io.BufferedReader` is a C type and
    # cannot be monkeypatched directly, so `Path.open` is wrapped instead.
    path = tmp_path / "huge.bin"
    with open(path, "wb") as handle:
        handle.seek(MAX_TOTAL_BYTES * 4)
        handle.write(b"\0")

    seen_sizes: list[int] = []
    original_open = Path.open

    class _TrackingFile:
        def __init__(self, real_file: io.BufferedReader) -> None:
            self._real_file = real_file

        def read(self, size: int = -1) -> bytes:
            seen_sizes.append(size)
            return self._real_file.read(size)

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *exc_info: object) -> None:
            self._real_file.close()

    def _tracking_open(self: Path, *args: object, **kwargs: object) -> _TrackingFile:
        return _TrackingFile(original_open(self, *args, **kwargs))

    monkeypatch.setattr(Path, "open", _tracking_open)
    result = _read_at_most(path, MAX_TOTAL_BYTES)
    assert result is None
    assert seen_sizes == [MAX_TOTAL_BYTES + 1]


def test_oversized_envelope_is_rejected(tmp_path):
    # The envelope's own bytes alone can exceed the bound with an empty files list, in which case
    # the byte-total check inside the per-file loop never runs at all - it must also be checked
    # once up front, before the envelope's shape is ever parsed. A sparse file (no real content
    # written) is enough to prove the rejection fires: `_read_at_most` never needs valid YAML to
    # reach its own size check.
    envelope_path = tmp_path / "envelope.yaml"
    with open(envelope_path, "wb") as handle:
        handle.seek(MAX_TOTAL_BYTES)
        handle.write(b"\0")

    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_oversized_listed_file_is_rejected(tmp_path):
    doc = _valid_envelope_dict()
    doc["files"] = [{"path": "resources.yaml", "sha256": "a" * 64}]
    (tmp_path / "envelope.yaml").write_bytes(_dump(doc))
    resource_path = tmp_path / "resources.yaml"
    with open(resource_path, "wb") as handle:
        handle.seek(MAX_TOTAL_BYTES)
        handle.write(b"\0")

    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_resource_object_count_at_the_boundary_is_accepted_and_one_over_is_rejected(tmp_path):
    def _documents(count: int) -> bytes:
        return b"---\n".join(
            yaml.safe_dump(
                {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": f"ns-{i}"}}
            ).encode()
            for i in range(count)
        )

    _write_bundle(tmp_path, files={"resources.yaml": _documents(MAX_RESOURCE_OBJECT_COUNT)})
    accepted = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert accepted.result is IngestionResult.ACCEPTED
    assert len(accepted.resources) == MAX_RESOURCE_OBJECT_COUNT

    _write_bundle(tmp_path, files={"resources.yaml": _documents(MAX_RESOURCE_OBJECT_COUNT + 1)})
    rejected = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert rejected.result is IngestionResult.REJECTED_UNSUPPORTED
    assert rejected.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_v1_list_is_expanded_into_individual_items(tmp_path):
    list_document = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "a"}},
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "b"}},
        ],
    }
    _write_bundle(tmp_path, files={"resources.yaml": yaml.safe_dump(list_document).encode()})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resources) == 2
    assert {entry.document["metadata"]["name"] for entry in result.resources} == {"a", "b"}
    assert all(entry.source_pointer == "resources.yaml" for entry in result.resources)


def test_nested_list_is_rejected(tmp_path):
    nested = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [{"apiVersion": "v1", "kind": "List", "items": []}],
    }
    _write_bundle(tmp_path, files={"resources.yaml": yaml.safe_dump(nested).encode()})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.REJECTED_UNSUPPORTED
    assert result.diagnostics[0].code is DiagnosticCode.K8S_LIMIT_EXCEEDED


def test_non_v1_list_kind_is_not_expanded_as_a_container(tmp_path):
    # §4.3 authorizes only v1/List as a container - a kind:List object under a different
    # apiVersion is not this container and must not be silently flattened/reinterpreted; it passes
    # through as one opaque object instead (admissibility of that object is a later slice's job).
    not_a_v1_list = {
        "apiVersion": "custom.io/v2",
        "kind": "List",
        "items": [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "a"}}],
    }
    _write_bundle(tmp_path, files={"resources.yaml": yaml.safe_dump(not_a_v1_list).encode()})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resources) == 1
    assert result.resources[0].document == not_a_v1_list
    assert result.resources[0].source_pointer == "resources.yaml"


def test_non_v1_list_kind_nested_inside_a_real_v1_list_is_not_rejected_as_nested(tmp_path):
    # The nested-List rejection is specifically about a nested *v1/List*; a differently-versioned
    # kind:List item inside a real v1/List is just an ordinary (opaque) item, not itself a
    # container, so it must not trigger the nested-container rejection.
    outer_list = {
        "apiVersion": "v1",
        "kind": "List",
        "items": [{"apiVersion": "custom.io/v2", "kind": "List", "items": []}],
    }
    _write_bundle(tmp_path, files={"resources.yaml": yaml.safe_dump(outer_list).encode()})
    result = validate_kubernetes_snapshot(root=tmp_path, envelope_relative_path="envelope.yaml")
    assert result.result is IngestionResult.ACCEPTED
    assert len(result.resources) == 1
    assert result.resources[0].document == {
        "apiVersion": "custom.io/v2",
        "kind": "List",
        "items": [],
    }
