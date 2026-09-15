import hashlib

from app.sources.jcs import (
    canonical_json_bytes,
    canonical_sha256_hex,
    sort_by_canonical_hash,
    sort_entries_by_canonical_bytes,
)


def test_canonical_json_bytes_reorders_object_keys():
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_bytes_has_no_insignificant_whitespace():
    assert canonical_json_bytes({"a": [1, 2], "b": {"c": 3}}) == b'{"a":[1,2],"b":{"c":3}}'


def test_canonical_json_bytes_normalizes_float_with_zero_fraction_to_integer_form():
    # RFC 8785 numbers use ECMA-262 Number::toString - a JSON float with a zero fractional part
    # serializes identically to the equivalent integer.
    assert canonical_json_bytes({"a": 1.0}) == b'{"a":1}'


def test_canonical_json_bytes_uses_exponential_notation_above_ecma262_threshold():
    assert canonical_json_bytes({"a": 1e21}) == b'{"a":1e+21}'


def test_canonical_sha256_hex_matches_manual_hash():
    value = {"b": 1, "a": 2}
    expected = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    assert canonical_sha256_hex(value) == expected


def test_canonical_sha256_hex_is_stable_across_equivalent_key_order():
    assert canonical_sha256_hex({"a": 1, "b": 2}) == canonical_sha256_hex({"b": 2, "a": 1})


def test_sort_by_canonical_hash_is_order_independent_of_input_order():
    branches = [{"type": "string"}, {"type": "integer"}, {"type": "boolean"}]
    forward = sort_by_canonical_hash(branches)
    backward = sort_by_canonical_hash(list(reversed(branches)))
    assert forward == backward


def test_sort_by_canonical_hash_is_idempotent():
    branches = [{"type": "string"}, {"type": "integer"}]
    once = sort_by_canonical_hash(branches)
    twice = sort_by_canonical_hash(once)
    assert once == twice


def test_sort_entries_by_canonical_bytes_is_order_independent_of_input_order():
    entries = [{"id": "c"}, {"id": "a"}, {"id": "b"}]
    forward = sort_entries_by_canonical_bytes(entries)
    backward = sort_entries_by_canonical_bytes(list(reversed(entries)))
    assert forward == backward


def test_sort_entries_by_canonical_bytes_sorts_by_raw_bytes_not_hash():
    # A byte-lexicographic sort is not the same ordering as a hash-based sort - use values whose
    # canonical JSON byte order is trivially known ("a" < "b" < "c" as JSON strings) to confirm this
    # function sorts by the bytes themselves, not by delegating to sort_by_canonical_hash.
    entries = [{"id": "c"}, {"id": "a"}, {"id": "b"}]
    sorted_entries = sort_entries_by_canonical_bytes(entries)
    assert sorted_entries == [{"id": "a"}, {"id": "b"}, {"id": "c"}]
