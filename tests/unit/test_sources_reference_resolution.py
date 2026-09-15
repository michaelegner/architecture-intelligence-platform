import pytest

from app.sources.model import DiagnosticCode
from app.sources.reference_resolution import (
    ParsedRef,
    ReferenceResolutionError,
    normalize_dot_segments,
    parse_ref_uri,
    percent_decode_path_once,
    reject_absolute_decoded_path,
    reject_remote_reference,
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
