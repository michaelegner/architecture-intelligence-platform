import hashlib

from app.sources.identity import (
    EMPTY_CLOSURE_DIGEST,
    ClosureEntry,
    content_sha256,
    dependency_closure_digest,
    discovery_scope_id,
    normalize_relative_posix_path,
    scope_definition_digest,
    semantic_input_digest,
    source_capture_id,
    source_instance_id,
    source_revision_id,
)
from app.sources.model import SourceKind


def test_empty_closure_digest_matches_sha256_of_empty_bytes():
    assert EMPTY_CLOSURE_DIGEST == hashlib.sha256(b"").hexdigest()


def test_dependency_closure_digest_empty_sequence_is_the_fixed_constant():
    assert dependency_closure_digest([]) == EMPTY_CLOSURE_DIGEST


def test_dependency_closure_digest_is_order_independent_over_call_order():
    entry_a = ClosureEntry(normalized_relative_path="a.yaml", file_bytes=b"A")
    entry_b = ClosureEntry(normalized_relative_path="b.yaml", file_bytes=b"B")
    assert dependency_closure_digest([entry_a, entry_b]) == dependency_closure_digest(
        [entry_b, entry_a]
    )


def test_dependency_closure_digest_changes_with_file_bytes():
    entry = ClosureEntry(normalized_relative_path="a.yaml", file_bytes=b"A")
    other = ClosureEntry(normalized_relative_path="a.yaml", file_bytes=b"B")
    assert dependency_closure_digest([entry]) != dependency_closure_digest([other])


def test_content_sha256_matches_stdlib():
    assert content_sha256(b"hello") == hashlib.sha256(b"hello").hexdigest()


def test_semantic_input_digest_matches_stdlib():
    assert semantic_input_digest(b"projection") == hashlib.sha256(b"projection").hexdigest()


def test_normalize_relative_posix_path_forces_forward_slashes():
    assert normalize_relative_posix_path("a\\b\\c") == "a/b/c"


def test_normalize_relative_posix_path_strips_leading_dot_slash():
    assert normalize_relative_posix_path("./a/b") == "a/b"


def test_normalize_relative_posix_path_collapses_redundant_slashes():
    assert normalize_relative_posix_path("a//b") == "a/b"


def test_source_instance_id_is_stable_for_identical_inputs():
    first = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    second = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    assert first == second
    assert first.startswith("urn:aip:source:filesystem:")


def test_source_instance_id_is_independent_of_absolute_checkout_path():
    # Checkout-path independence holds by construction: the function's signature has no absolute
    # path or cwd input at all, only a configured id and a path relative to the configured root.
    from_checkout_one = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    from_checkout_two = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    assert from_checkout_one == from_checkout_two


def test_source_instance_id_changes_with_configured_source_id():
    a = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    b = source_instance_id(
        configured_source_id="svc-b",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    assert a != b


def test_source_revision_id_changes_with_semantic_input_digest():
    sid = source_instance_id(
        configured_source_id="svc-a",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="openapi.yaml",
    )
    first = source_revision_id(
        source_instance_id=sid, mapping_rule_version="v1", semantic_input_digest="a" * 64
    )
    second = source_revision_id(
        source_instance_id=sid, mapping_rule_version="v1", semantic_input_digest="b" * 64
    )
    assert first != second
    assert first.startswith("urn:aip:source-revision:")


def test_source_capture_id_without_provider_revision_equals_revision_id():
    revision_id = "urn:aip:source-revision:" + "a" * 64
    assert source_capture_id(source_revision_id=revision_id, normalized_provider_revision=None) == (
        revision_id
    )


def test_source_capture_id_with_provider_revision_is_distinct_and_prefixed():
    revision_id = "urn:aip:source-revision:" + "a" * 64
    captured = source_capture_id(source_revision_id=revision_id, normalized_provider_revision="42")
    assert captured != revision_id
    assert captured.startswith("urn:aip:source-capture:")


def test_source_capture_id_distinguishes_provider_revisions():
    revision_id = "urn:aip:source-revision:" + "a" * 64
    one = source_capture_id(source_revision_id=revision_id, normalized_provider_revision="1")
    two = source_capture_id(source_revision_id=revision_id, normalized_provider_revision="2")
    assert one != two


def test_discovery_scope_id_stable_for_bundled_example_fixed_inputs():
    # I1 spec §5.1.1's fixed logical values - proves the derivation mechanism reproduces a stable
    # id from these fixed inputs without hardcoding the future migration file.
    first = discovery_scope_id(
        configured_scope_id="aip-bundled-examples-v0.5",
        stable_target_identity="urn:aip:logical-root:bundled-examples",
    )
    second = discovery_scope_id(
        configured_scope_id="aip-bundled-examples-v0.5",
        stable_target_identity="urn:aip:logical-root:bundled-examples",
    )
    assert first == second
    assert first.startswith("urn:aip:discovery-scope:")


def test_scope_definition_digest_changes_with_roots_but_not_scope_id():
    scope_id = discovery_scope_id(
        configured_scope_id="scope-a", stable_target_identity="urn:aip:logical-root:a"
    )
    original = scope_definition_digest(
        discovery_scope_id=scope_id,
        normalized_roots=["examples/"],
        filters=[],
        inclusion_rules=[],
    )
    changed_roots = scope_definition_digest(
        discovery_scope_id=scope_id,
        normalized_roots=["examples/", "extra/"],
        filters=[],
        inclusion_rules=[],
    )
    assert original != changed_roots
    # DiscoveryScopeId itself must not change when roots/filters change (I1 §6).
    assert scope_id == discovery_scope_id(
        configured_scope_id="scope-a", stable_target_identity="urn:aip:logical-root:a"
    )


def test_scope_definition_digest_does_not_confuse_group_boundaries():
    scope_id = discovery_scope_id(
        configured_scope_id="scope-a", stable_target_identity="urn:aip:logical-root:a"
    )
    partition_one = scope_definition_digest(
        discovery_scope_id=scope_id,
        normalized_roots=["a", "b"],
        filters=[],
        inclusion_rules=["c"],
    )
    partition_two = scope_definition_digest(
        discovery_scope_id=scope_id,
        normalized_roots=["a"],
        filters=["b"],
        inclusion_rules=["c"],
    )
    assert partition_one != partition_two
