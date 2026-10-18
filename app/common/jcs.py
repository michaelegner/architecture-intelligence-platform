from collections.abc import Sequence

import rfc8785

from app.common.encoding import sha256_hex


class CanonicalIntegerDomainError(ValueError):
    """A value contains an integer outside RFC 8785's safe integer domain (|n| > 2**53 - 1).

    Raised in place of the `rfc8785` library's own error, whose message embeds the value: this
    one never does, so it is safe to log or turn into a diagnostic."""


type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


def canonical_json_bytes(value: JSONValue) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme bytes, via the `rfc8785` library.

    This is deliberately distinct from the non-RFC-8785 canonical form used elsewhere in this
    codebase for the v0.4 answer-contract fingerprint (a plain `sort_keys` JSON dump with no
    ECMA-262 number formatting) - that helper MUST NOT be reused here, and this one MUST NOT be
    reused there. I1 spec §8.1/§9.1 require RFC 8785 specifically for schema/message canonical
    hashing.
    """
    try:
        return rfc8785.dumps(value)
    except rfc8785.IntegerDomainError:
        raise CanonicalIntegerDomainError(
            "value contains an integer outside the RFC 8785 safe integer domain"
        ) from None


def canonical_sha256_hex(value: JSONValue) -> str:
    """SHA-256 (lowercase hex) of `canonical_json_bytes(value)` - the primitive behind
    `canonical_hash` (I1 spec §8.1), `message_document_digest`, and `message_contract_digest`
    (§9.1).
    """
    return sha256_hex(canonical_json_bytes(value))


def sort_by_canonical_hash(branches: Sequence[JSONValue]) -> list[JSONValue]:
    """I1 spec §8.1: "The branch arrays of allOf, oneOf, and anyOf are sorted by the full canonical
    hash of each normalized branch because their order has no architectural meaning." Generic and
    OpenAPI-unaware - just sorts arbitrary JSON values by their canonical SHA-256. The actual
    normalized branch values are supplied by the OpenAPI adapter (a later increment); this function
    only supplies the deterministic ordering primitive.
    """
    return sorted(branches, key=canonical_sha256_hex)


def sort_entries_by_canonical_bytes(entries: Sequence[JSONValue]) -> list[JSONValue]:
    """I1 spec §5.3 (mapping_context_digest, Draft 0.2): "sort unordered entry arrays by their
    complete canonical JSON bytes before hashing." This sorts by each entry's raw canonical JSON
    bytes directly - deliberately distinct from `sort_by_canonical_hash` (§8.1's allOf/oneOf/anyOf
    branch ordering, which sorts by each branch's SHA-256 instead). The two orderings are not
    equivalent and must not be used interchangeably.
    """
    return sorted(entries, key=canonical_json_bytes)


def json_nesting_depth(node: object) -> int:
    """Depth of a parsed JSON document (a scalar is 1), computed iteratively so a hostile document
    cannot exhaust the stack."""
    deepest = 0
    stack: list[tuple[object, int]] = [(node, 1)]
    while stack:
        current, depth = stack.pop()
        deepest = max(deepest, depth)
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
    return deepest
