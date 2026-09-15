import datetime
from pathlib import Path

import pytest

from app.sources.model import DiagnosticCode
from app.sources.reference_resolution import (
    ParsedRef,
    ReferenceResolutionError,
    new_resolution_cache,
    normalize_dot_segments,
    normalize_non_json_scalars,
    parse_ref_uri,
    percent_decode_path_once,
    reject_absolute_decoded_path,
    reject_remote_reference,
    resolve_and_read,
    resolve_pointer,
    resolve_relative_path,
)

# --- parse_ref_uri / reject_remote_reference -----------------------------------------------------


def test_parse_ref_uri_fragment_only():
    assert parse_ref_uri("#/components/schemas/Foo") == ParsedRef(
        scheme="", authority="", path="", fragment="/components/schemas/Foo"
    )


def test_parse_ref_uri_relative_path_with_fragment():
    assert parse_ref_uri("schemas/common.yaml#/Foo") == ParsedRef(
        scheme="", authority="", path="schemas/common.yaml", fragment="/Foo"
    )


def test_parse_ref_uri_relative_path_no_fragment():
    assert parse_ref_uri("schemas/common.yaml") == ParsedRef(
        scheme="", authority="", path="schemas/common.yaml", fragment=""
    )


def test_parse_ref_uri_does_not_decode_percent_escapes():
    assert parse_ref_uri("a%2Fb.yaml#/Foo").path == "a%2Fb.yaml"


def test_reject_remote_reference_accepts_local():
    reject_remote_reference(parse_ref_uri("schemas/common.yaml#/Foo"))  # no raise


@pytest.mark.parametrize(
    "ref",
    [
        "https://example.com/foo.yaml#/Bar",
        "http://example.com/foo.yaml",
        "//example.com/foo.yaml#/Bar",
        "file:///etc/passwd#/Bar",
    ],
)
def test_reject_remote_reference_rejects_scheme_or_authority(ref):
    with pytest.raises(ReferenceResolutionError) as exc_info:
        reject_remote_reference(parse_ref_uri(ref))
    assert exc_info.value.code is DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED


# --- percent_decode_path_once ---------------------------------------------------------------------


def test_percent_decode_path_once_decodes_valid_escapes():
    assert percent_decode_path_once("a%20b.yaml") == "a b.yaml"


def test_percent_decode_path_once_leaves_unescaped_path_unchanged():
    assert percent_decode_path_once("schemas/common.yaml") == "schemas/common.yaml"


def test_percent_decode_path_once_rejects_non_hex_escape():
    with pytest.raises(ReferenceResolutionError) as exc_info:
        percent_decode_path_once("a%zzb.yaml")
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_percent_decode_path_once_rejects_invalid_utf8_bytes():
    with pytest.raises(ReferenceResolutionError) as exc_info:
        percent_decode_path_once("a%e2%82b.yaml")  # incomplete 3-byte UTF-8 sequence
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_percent_decode_path_once_only_decodes_once():
    # A double-encoded traversal (%252e%252e = "%2e%2e" after one decode) must NOT become ".." -
    # decoding exactly once is itself a security property, not merely a formatting nicety.
    assert percent_decode_path_once("%252e%252e/evil.yaml") == "%2e%2e/evil.yaml"


# --- reject_absolute_decoded_path ------------------------------------------------------------------


def test_reject_absolute_decoded_path_accepts_relative():
    reject_absolute_decoded_path("schemas/common.yaml")  # no raise


def test_reject_absolute_decoded_path_rejects_absolute():
    with pytest.raises(ReferenceResolutionError) as exc_info:
        reject_absolute_decoded_path("/etc/passwd")
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_reject_absolute_decoded_path_catches_percent_encoded_absolute_path():
    # This is exactly why absolute-path rejection must run strictly AFTER percent-decoding.
    decoded = percent_decode_path_once("%2Fetc%2Fpasswd")
    assert decoded == "/etc/passwd"
    with pytest.raises(ReferenceResolutionError):
        reject_absolute_decoded_path(decoded)


# --- normalize_dot_segments -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("a/b/c", "a/b/c"),
        ("a/./b", "a/b"),
        ("a/b/../c", "a/c"),
        ("a/b/../../c", "c"),
        ("./a/b", "a/b"),
        ("a//b", "a/b"),
        ("", ""),
        (".", ""),
        ("a/..", ""),
    ],
)
def test_normalize_dot_segments_resolves_within_bounds(path, expected):
    assert normalize_dot_segments(path) == expected


def test_normalize_dot_segments_keeps_an_unresolvable_leading_dotdot_literal():
    # No security decision is made here - an unresolved leading ".." reliably fails the later
    # real-filesystem containment check by joining outside the source root, which is the correct
    # place for a genuine escape attempt to be caught, not this pure string function.
    assert normalize_dot_segments("../evil.yaml") == "../evil.yaml"
    assert normalize_dot_segments("a/../../evil.yaml") == "../evil.yaml"


# --- resolve_relative_path -------------------------------------------------------------------------


def test_resolve_relative_path_from_root_document():
    assert (
        resolve_relative_path(
            containing_document_relative_path="openapi.yaml", ref_path="common.yaml"
        )
        == "common.yaml"
    )


def test_resolve_relative_path_from_nested_document():
    assert (
        resolve_relative_path(
            containing_document_relative_path="schemas/order.yaml",
            ref_path="common.yaml",
        )
        == "schemas/common.yaml"
    )


def test_resolve_relative_path_walks_up_a_directory():
    assert (
        resolve_relative_path(
            containing_document_relative_path="schemas/orders/order.yaml",
            ref_path="../shared/common.yaml",
        )
        == "schemas/shared/common.yaml"
    )


def test_resolve_relative_path_escape_attempt_stays_unresolved_for_later_containment_check():
    result = resolve_relative_path(
        containing_document_relative_path="openapi.yaml", ref_path="../../evil.yaml"
    )
    assert result == "../../evil.yaml"


# --- normalize_non_json_scalars --------------------------------------------------------------------


def test_normalize_non_json_scalars_converts_dates_and_datetimes_to_iso_strings():
    value = {
        "a": datetime.date(2026, 1, 1),
        "b": [datetime.datetime(2026, 1, 1, 12, 30, tzinfo=datetime.UTC)],
    }
    normalized = normalize_non_json_scalars(value)
    assert normalized["a"] == "2026-01-01"
    assert normalized["b"] == ["2026-01-01T12:30:00+00:00"]


def test_normalize_non_json_scalars_leaves_json_safe_values_unchanged():
    value = {"a": 1, "b": "text", "c": [1, "two", {"d": None}]}
    assert normalize_non_json_scalars(value) == value


# --- resolve_pointer ---------------------------------------------------------------------------


def test_resolve_pointer_walks_dict_and_list():
    document = {"components": {"schemas": ["first", {"name": "second"}]}}
    assert resolve_pointer(document, ("components", "schemas", "1", "name")) == "second"


def test_resolve_pointer_root_returns_whole_document():
    document = {"a": 1}
    assert resolve_pointer(document, ()) == document


def test_resolve_pointer_dangling_dict_key():
    with pytest.raises(ReferenceResolutionError) as exc_info:
        resolve_pointer({"a": 1}, ("b",))
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_resolve_pointer_dangling_list_index():
    with pytest.raises(ReferenceResolutionError):
        resolve_pointer({"a": [1, 2]}, ("a", "5"))


def test_resolve_pointer_non_integer_list_index():
    with pytest.raises(ReferenceResolutionError):
        resolve_pointer({"a": [1, 2]}, ("a", "not-a-number"))


def test_resolve_pointer_cannot_descend_into_scalar():
    with pytest.raises(ReferenceResolutionError):
        resolve_pointer({"a": 1}, ("a", "b"))


# --- resolve_and_read (real filesystem I/O via tmp_path) -------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_resolve_and_read_fragment_only_resolves_within_root_document(tmp_path):
    root_document = {"components": {"schemas": {"Foo": {"type": "object"}}}}
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document=root_document, root_bytes=b""
    )
    result = resolve_and_read(
        containing_document_relative_path="openapi.yaml",
        ref="#/components/schemas/Foo",
        cache=cache,
    )
    assert result.target_node == {"type": "object"}
    assert result.normalized_relative_path == "openapi.yaml"


def test_resolve_and_read_crosses_into_a_sibling_file(tmp_path):
    _write(tmp_path / "schemas" / "common.yaml", "Foo:\n  type: object\n")
    root_document = {"info": {}}
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document=root_document, root_bytes=b""
    )
    result = resolve_and_read(
        containing_document_relative_path="openapi.yaml",
        ref="schemas/common.yaml#/Foo",
        cache=cache,
    )
    assert result.target_node == {"type": "object"}
    assert result.normalized_relative_path == "schemas/common.yaml"
    assert "schemas/common.yaml" in cache.documents  # cached for reuse


def test_resolve_and_read_resolves_relative_to_the_containing_documents_own_directory(tmp_path):
    _write(tmp_path / "a" / "root.yaml", "x: 1\n")
    _write(tmp_path / "a" / "sibling.yaml", "Foo:\n  type: string\n")
    cache = new_resolution_cache(
        tmp_path, root_relative_path="a/root.yaml", root_document={"x": 1}, root_bytes=b""
    )
    result = resolve_and_read(
        containing_document_relative_path="a/root.yaml", ref="sibling.yaml#/Foo", cache=cache
    )
    assert result.normalized_relative_path == "a/sibling.yaml"


def test_resolve_and_read_rejects_a_path_that_escapes_the_source_root(tmp_path):
    (tmp_path / "root").mkdir()
    (tmp_path / "outside.yaml").write_text("Foo: {}\n")
    cache = new_resolution_cache(
        tmp_path / "root", root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    with pytest.raises(ReferenceResolutionError) as exc_info:
        resolve_and_read(
            containing_document_relative_path="openapi.yaml",
            ref="../outside.yaml#/Foo",
            cache=cache,
        )
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_resolve_and_read_rejects_a_symlink_escaping_the_source_root(tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("Foo: {}\n")
    root = tmp_path / "root"
    root.mkdir()
    (root / "escape.yaml").symlink_to(outside)
    cache = new_resolution_cache(
        root, root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    with pytest.raises(ReferenceResolutionError) as exc_info:
        resolve_and_read(
            containing_document_relative_path="openapi.yaml",
            ref="escape.yaml#/Foo",
            cache=cache,
        )
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_resolve_and_read_rejects_a_missing_file(tmp_path):
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    with pytest.raises(ReferenceResolutionError) as exc_info:
        resolve_and_read(
            containing_document_relative_path="openapi.yaml",
            ref="missing.yaml#/Foo",
            cache=cache,
        )
    assert exc_info.value.code is DiagnosticCode.REFERENCE_INVALID


def test_resolve_and_read_rejects_a_directory_target(tmp_path):
    (tmp_path / "a-directory").mkdir()
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    with pytest.raises(ReferenceResolutionError):
        resolve_and_read(
            containing_document_relative_path="openapi.yaml",
            ref="a-directory#/Foo",
            cache=cache,
        )


def test_resolve_and_read_rejects_a_remote_reference(tmp_path):
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    with pytest.raises(ReferenceResolutionError) as exc_info:
        resolve_and_read(
            containing_document_relative_path="openapi.yaml",
            ref="https://example.com/foo.yaml#/Bar",
            cache=cache,
        )
    assert exc_info.value.code is DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED


def test_resolve_and_read_caches_a_document_read_more_than_once(tmp_path):
    _write(tmp_path / "common.yaml", "Foo:\n  type: object\nBar:\n  type: string\n")
    cache = new_resolution_cache(
        tmp_path, root_relative_path="openapi.yaml", root_document={}, root_bytes=b""
    )
    resolve_and_read(
        containing_document_relative_path="openapi.yaml", ref="common.yaml#/Foo", cache=cache
    )
    real_common_path = (tmp_path / "common.yaml").resolve()
    common_bytes_after_first = real_common_path.read_bytes()
    # Mutate the file on disk; a cached second resolution must still see the FIRST read's content,
    # proving it didn't re-read the file.
    real_common_path.write_text("Foo:\n  type: object\nBar:\n  type: number\n")
    result = resolve_and_read(
        containing_document_relative_path="openapi.yaml", ref="common.yaml#/Bar", cache=cache
    )
    assert result.target_node == {"type": "string"}
    assert cache.file_bytes["common.yaml"] == common_bytes_after_first
