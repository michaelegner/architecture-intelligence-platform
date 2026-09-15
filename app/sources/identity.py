from collections.abc import Sequence
from dataclasses import dataclass

from app.sources.encoding import length_delimited, length_delimited_group, sha256_hex
from app.sources.model import DiscoveryScopeId, SourceInstanceId, SourceKind

# I1 spec §5.3: "The empty closure digest is SHA-256 of the zero-length byte string."
EMPTY_CLOSURE_DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def normalize_relative_posix_path(path: str) -> str:
    """Forces forward slashes and strips a leading './'. Pure string normalization only - no
    filesystem I/O and no '..' resolution; a real filesystem discoverer (a later increment) is
    responsible for rejecting any path that would escape its configured root.
    """
    posix_path = path.replace("\\", "/")
    while posix_path.startswith("./"):
        posix_path = posix_path[2:]
    while "//" in posix_path:
        posix_path = posix_path.replace("//", "/")
    return posix_path


def source_instance_id(
    *,
    configured_source_id: str,
    source_kind: SourceKind,
    normalized_root_document_path: str,
) -> SourceInstanceId:
    """I1 spec §5.1:

        source_instance_id = urn:aip:source:<source-kind>:<sha256(stable-source-key)>

        filesystem stable-source-key
          = configured filesystem-source id + source kind
            + normalized POSIX root-document path relative to configured source root

    Deliberately takes no absolute path or cwd - "checkout path does not affect source identity"
    holds by construction of this signature.
    """
    stable_source_key = length_delimited(
        _utf8(configured_source_id),
        _utf8(source_kind.value),
        _utf8(normalized_root_document_path),
    )
    return SourceInstanceId(f"urn:aip:source:{source_kind.value}:{sha256_hex(stable_source_key)}")


def source_revision_id(
    *,
    source_instance_id: SourceInstanceId,
    mapping_rule_version: str,
    semantic_input_digest: str,
) -> str:
    """I1 spec §5.2:

    source_revision_id
      = urn:aip:source-revision:<sha256(length-delimited(
          SourceInstanceId, mapping-rule version, semantic_input_digest))>
    """
    digest_input = length_delimited(
        _utf8(source_instance_id),
        _utf8(mapping_rule_version),
        _utf8(semantic_input_digest),
    )
    return f"urn:aip:source-revision:{sha256_hex(digest_input)}"


def source_capture_id(
    *,
    source_revision_id: str,
    normalized_provider_revision: str | None,
) -> str:
    """I1 spec §5.2:

        source_capture_id
          = urn:aip:source-capture:<sha256(length-delimited(
              source_revision_id, normalized declared/provider revision))>

        "Without an independent provider revision, source_capture_id equals source_revision_id."

    Implemented literally: with no provider revision, this returns `source_revision_id`'s exact
    string, not a re-prefixed `urn:aip:source-capture:...` value.
    """
    if normalized_provider_revision is None:
        return source_revision_id
    digest_input = length_delimited(
        _utf8(source_revision_id),
        _utf8(normalized_provider_revision),
    )
    return f"urn:aip:source-capture:{sha256_hex(digest_input)}"


def content_sha256(root_document_bytes: bytes) -> str:
    """I1 spec §5.3: "content_sha256 is the SHA-256 of the exact bytes received for the root
    document." """
    return sha256_hex(root_document_bytes)


def semantic_input_digest(canonical_projection_bytes: bytes) -> str:
    """I1 spec §5.3: hash of the already-built versioned source-kind canonical projection. Building
    that projection (key ordering, comment/path stripping, closure ordering) is an adapter's job (a
    later increment); this function owns only the final hash step - "the only digest used to decide
    semantic replay no-op."
    """
    return sha256_hex(canonical_projection_bytes)


@dataclass(frozen=True)
class ClosureEntry:
    normalized_relative_path: str
    file_bytes: bytes


def dependency_closure_digest(entries: Sequence[ClosureEntry]) -> str:
    """I1 spec §5.3: each referenced-file closure entry is length-delimited(path bytes, file bytes);
    entries are concatenated in normalized-path byte order and SHA-256 hashed. The root document is
    excluded (represented by `content_sha256` instead). An empty closure yields
    `EMPTY_CLOSURE_DIGEST`.
    """
    if not entries:
        return EMPTY_CLOSURE_DIGEST
    ordered = sorted(entries, key=lambda entry: _utf8(entry.normalized_relative_path))
    concatenated = length_delimited(
        *(
            part
            for entry in ordered
            for part in (_utf8(entry.normalized_relative_path), entry.file_bytes)
        )
    )
    return sha256_hex(concatenated)


def discovery_scope_id(
    *, configured_scope_id: str, stable_target_identity: str
) -> DiscoveryScopeId:
    """I1 spec §6:

        DiscoveryScopeId = urn:aip:discovery-scope:<sha256(configured scope id, stable target identity)>

    `stable_target_identity` MUST NOT be an absolute checkout path, resolved physical directory,
    mount point, or other mutable root location (§6). Only the *lifecycle* around this identity
    (SourceInventorySnapshot, tombstones) is out of scope for this PR - the identity formula itself
    is needed here because it's a required field of SourceDescriptor (§4).
    """
    digest_input = length_delimited(_utf8(configured_scope_id), _utf8(stable_target_identity))
    return DiscoveryScopeId(f"urn:aip:discovery-scope:{sha256_hex(digest_input)}")


def scope_definition_digest(
    *,
    discovery_scope_id: DiscoveryScopeId,
    normalized_roots: Sequence[str],
    filters: Sequence[str],
    inclusion_rules: Sequence[str],
) -> str:
    """I1 spec §6:

        scope_definition_digest = sha256(DiscoveryScopeId, normalized roots, filters, inclusion rules)

    "Physical roots, filters, and inclusion rules belong only to scope_definition_digest; changing
    them MUST NOT change DiscoveryScopeId." This function is order-sensitive within each sequence;
    producing a stable, deterministic order for them is the caller's responsibility. Each sequence is
    encoded as its own nested length-delimited group so that group boundaries can never collide (see
    `length_delimited_group`).
    """
    digest_input = length_delimited(
        _utf8(discovery_scope_id),
        length_delimited_group([_utf8(root) for root in normalized_roots]),
        length_delimited_group([_utf8(item) for item in filters]),
        length_delimited_group([_utf8(item) for item in inclusion_rules]),
    )
    return sha256_hex(digest_input)
