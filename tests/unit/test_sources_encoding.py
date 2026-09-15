import hashlib

from app.sources.encoding import length_delimited, length_delimited_group, sha256_hex, unicode_nfc


def test_length_delimited_is_unambiguous_across_part_boundaries():
    assert length_delimited(b"ab", b"c") != length_delimited(b"a", b"bc")


def test_length_delimited_empty_parts_list_is_empty_bytes():
    assert length_delimited() == b""


def test_length_delimited_single_part_roundtrips_length_prefix():
    encoded = length_delimited(b"hello")
    assert encoded[:8] == (5).to_bytes(8, "big")
    assert encoded[8:] == b"hello"


def test_length_delimited_group_preserves_boundary_between_groups():
    group_a = length_delimited_group([b"a", b"b"])
    group_b = length_delimited_group([])
    group_c = length_delimited_group([b"a"])
    group_d = length_delimited_group([b"b"])

    partition_one = length_delimited(group_a, group_b)
    partition_two = length_delimited(group_c, group_d)

    assert partition_one != partition_two


def test_sha256_hex_matches_stdlib():
    assert sha256_hex(b"hello") == hashlib.sha256(b"hello").hexdigest()


def test_sha256_hex_is_lowercase():
    digest = sha256_hex(b"anything")
    assert digest == digest.lower()


def test_unicode_nfc_normalizes_without_trimming_or_case_folding():
    # "e" + combining acute accent -> precomposed "é"
    decomposed = "é"
    assert unicode_nfc(decomposed) == "é"
    assert unicode_nfc(" Foo ") == " Foo "
