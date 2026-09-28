"""Property-based tests for the source-identity encoding primitives: RFC 6901 pointers, the
length-delimited framing behind every identity hash, RFC 8785 canonical JSON, and the digests that
must not depend on input order. The example-based tests next to each module pin specific values;
these check the laws those values rely on across generated inputs.
"""

import json

from hypothesis import given
from hypothesis import strategies as st

from app.sources.encoding import length_delimited, length_delimited_group, unicode_nfc
from app.sources.identity import (
    ClosureEntry,
    dependency_closure_digest,
    normalize_relative_posix_path,
    normalized_document_and_reference_projection_bytes,
)
from app.sources.jcs import (
    canonical_json_bytes,
    canonical_sha256_hex,
    sort_by_canonical_hash,
    sort_entries_by_canonical_bytes,
)
from app.sources.pointers import (
    decode_pointer_tokens,
    encode_pointer_tokens,
    is_well_formed_pointer,
    pointer_prefix_matches,
)

# RFC 8785 numbers are IEEE-754 doubles, so integers stay within the exactly-representable range
# (the `rfc8785` library rejects larger Python ints outright).
_SAFE_INT = 2**53 - 1
json_values = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-_SAFE_INT, max_value=_SAFE_INT)
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=4) | st.dictionaries(st.text(max_size=8), children, max_size=4)
    ),
    max_leaves=12,
)
# Tokens are biased toward the characters RFC 6901 escapes, which plain random text rarely hits.
tokens = st.lists(st.text(alphabet="ab~/01", max_size=6) | st.text(), max_size=6)
# A well-formed RFC 6901 pointer, generated directly: "/"-separated segments of characters other
# than "/" and "~", plus the two legal escapes.
_pointer_segment = st.lists(
    st.text(min_size=1, max_size=3).filter(lambda s: "/" not in s and "~" not in s)
    | st.sampled_from(["~0", "~1"]),
    max_size=4,
).map("".join)
well_formed_pointers = st.lists(_pointer_segment, max_size=5).map(
    lambda segments: "".join("/" + segment for segment in segments)
)


def _loads_as_doubles(data: bytes):
    """Parse canonical JSON the way RFC 8785 (ECMAScript) does: every number is a double. Python's
    json.loads would read an integer-looking literal such as 64037512996116570 as an exact int, even
    though the double it came from is 64037512996116568."""
    return json.loads(data, parse_int=float)


# --- RFC 6901 pointers -------------------------------------------------------------------------


@given(tokens)
def test_pointer_encoding_round_trips(token_list):
    pointer = encode_pointer_tokens(token_list)
    assert is_well_formed_pointer(pointer)
    assert decode_pointer_tokens(pointer) == tuple(token_list)


@given(well_formed_pointers)
def test_every_well_formed_pointer_round_trips(pointer):
    assert is_well_formed_pointer(pointer)
    assert encode_pointer_tokens(decode_pointer_tokens(pointer)) == pointer


@given(st.text())
def test_pointer_decoding_accepts_exactly_the_well_formed_pointers(pointer):
    try:
        decode_pointer_tokens(pointer)
    except ValueError:
        assert not is_well_formed_pointer(pointer)
    else:
        assert is_well_formed_pointer(pointer)


@given(tokens, tokens)
def test_pointer_prefix_matching_is_token_prefix_matching(prefix_tokens, suffix_tokens):
    prefix = encode_pointer_tokens(prefix_tokens)
    candidate = encode_pointer_tokens(prefix_tokens + suffix_tokens)
    assert pointer_prefix_matches(prefix=prefix, candidate=candidate)


@given(tokens, tokens)
def test_pointer_prefix_matching_agrees_with_decoded_tokens(a_tokens, b_tokens):
    a, b = encode_pointer_tokens(a_tokens), encode_pointer_tokens(b_tokens)
    expected = tuple(b_tokens[: len(a_tokens)]) == tuple(a_tokens)
    assert pointer_prefix_matches(prefix=a, candidate=b) == expected


# --- length-delimited framing ------------------------------------------------------------------

parts = st.lists(st.binary(max_size=12), max_size=5)


@given(parts, parts)
def test_length_delimited_encoding_is_injective(a, b):
    assert (length_delimited(*a) == length_delimited(*b)) == (a == b)


@given(st.lists(parts, max_size=4), st.lists(parts, max_size=4))
def test_nested_groups_keep_their_boundaries(a_groups, b_groups):
    def encode(groups):
        return length_delimited(*(length_delimited_group(group) for group in groups))

    assert (encode(a_groups) == encode(b_groups)) == (a_groups == b_groups)


# --- RFC 8785 canonical JSON -------------------------------------------------------------------


@given(json_values)
def test_canonical_json_round_trips(value):
    assert _loads_as_doubles(canonical_json_bytes(value)) == value


@given(st.dictionaries(st.text(max_size=8), json_values, max_size=6), st.randoms())
def test_canonical_json_ignores_object_key_order(mapping, random):
    items = list(mapping.items())
    random.shuffle(items)
    assert canonical_json_bytes(dict(items)) == canonical_json_bytes(mapping)
    assert canonical_sha256_hex(dict(items)) == canonical_sha256_hex(mapping)


@given(json_values)
def test_canonical_json_is_a_fixed_point(value):
    canonical = canonical_json_bytes(value)
    assert canonical_json_bytes(_loads_as_doubles(canonical)) == canonical


@given(st.lists(json_values, max_size=6), st.randoms())
def test_canonical_sorts_ignore_input_order(values, random):
    shuffled = list(values)
    random.shuffle(shuffled)
    assert sort_by_canonical_hash(shuffled) == sort_by_canonical_hash(values)
    assert sort_entries_by_canonical_bytes(shuffled) == sort_entries_by_canonical_bytes(values)


# --- order-independent digests -----------------------------------------------------------------


@given(
    st.dictionaries(st.text(min_size=1, max_size=10), st.binary(max_size=16), max_size=6),
    st.randoms(),
)
def test_dependency_closure_digest_ignores_entry_order(files, random):
    entries = [ClosureEntry(path, content) for path, content in files.items()]
    shuffled = list(entries)
    random.shuffle(shuffled)
    assert dependency_closure_digest(shuffled) == dependency_closure_digest(entries)


@given(st.dictionaries(st.text(min_size=1, max_size=10), json_values, max_size=5), st.randoms())
def test_document_projection_ignores_document_order(documents, random):
    items = list(documents.items())
    random.shuffle(items)
    assert normalized_document_and_reference_projection_bytes(
        dict(items)
    ) == normalized_document_and_reference_projection_bytes(documents)


# --- normalization helpers ---------------------------------------------------------------------


@given(st.text(alphabet=st.sampled_from("ab/\\.")))
def test_relative_posix_path_normalization_is_idempotent(path):
    once = normalize_relative_posix_path(path)
    assert normalize_relative_posix_path(once) == once
    assert "\\" not in once and "//" not in once and not once.startswith("./")


@given(st.text())
def test_unicode_nfc_is_idempotent(text):
    once = unicode_nfc(text)
    assert unicode_nfc(once) == once
