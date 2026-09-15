import pytest

from app.sources.pointers import (
    decode_pointer_tokens,
    encode_pointer_tokens,
    is_well_formed_pointer,
    pointer_prefix_matches,
)


def test_is_well_formed_pointer_accepts_root():
    assert is_well_formed_pointer("") is True


def test_is_well_formed_pointer_accepts_valid_pointer():
    assert is_well_formed_pointer("/paths/~1foo/get") is True


def test_is_well_formed_pointer_rejects_missing_leading_slash():
    assert is_well_formed_pointer("paths/foo") is False


def test_is_well_formed_pointer_rejects_dangling_tilde():
    assert is_well_formed_pointer("/paths/foo~") is False


def test_is_well_formed_pointer_rejects_invalid_escape():
    assert is_well_formed_pointer("/paths/foo~2") is False


def test_decode_pointer_tokens_root_is_empty_tuple():
    assert decode_pointer_tokens("") == ()


def test_decode_pointer_tokens_decodes_escapes():
    assert decode_pointer_tokens("/paths/~1foo/get") == ("paths", "/foo", "get")
    assert decode_pointer_tokens("/a~0b") == ("a~b",)


def test_decode_pointer_tokens_rejects_malformed_pointer():
    with pytest.raises(ValueError):
        decode_pointer_tokens("no-leading-slash")


def test_pointer_prefix_matches_spec_worked_example():
    # I1 spec §4.2/§11: `/paths/~1foo` must NOT match `/paths/~1foobar` - the decoded token 'foo'
    # is not equal to the decoded token 'foobar', so a raw-string prefix check would wrongly succeed
    # here while decoded-token matching correctly fails.
    assert pointer_prefix_matches(prefix="/paths/~1foo", candidate="/paths/~1foobar") is False


def test_pointer_prefix_matches_descendant():
    assert pointer_prefix_matches(prefix="/paths/~1foo", candidate="/paths/~1foo/get") is True


def test_pointer_prefix_matches_exact_equality():
    assert pointer_prefix_matches(prefix="/paths/~1foo", candidate="/paths/~1foo") is True


def test_pointer_prefix_matches_root_matches_everything():
    assert pointer_prefix_matches(prefix="", candidate="/paths/~1foo/get") is True
    assert pointer_prefix_matches(prefix="", candidate="") is True


def test_pointer_prefix_matches_rejects_shorter_candidate():
    assert pointer_prefix_matches(prefix="/paths/~1foo/get", candidate="/paths/~1foo") is False


def test_encode_pointer_tokens_root_is_empty_string():
    assert encode_pointer_tokens(()) == ""


def test_encode_pointer_tokens_escapes_reserved_characters():
    assert encode_pointer_tokens(("paths", "/foo", "get")) == "/paths/~1foo/get"
    assert encode_pointer_tokens(("a~b",)) == "/a~0b"


def test_encode_pointer_tokens_round_trips_with_decode():
    tokens = ("paths", "/orders/{id}", "get", "a~b")
    assert decode_pointer_tokens(encode_pointer_tokens(tokens)) == tokens
