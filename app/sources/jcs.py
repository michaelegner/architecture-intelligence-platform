from collections.abc import Sequence

import rfc8785

from app.sources.encoding import sha256_hex

type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


def canonical_json_bytes(value: JSONValue) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme bytes, via the `rfc8785` library.

    This is deliberately distinct from the non-RFC-8785 canonical form used elsewhere in this
    codebase for the v0.4 answer-contract fingerprint (a plain `sort_keys` JSON dump with no
    ECMA-262 number formatting) - that helper MUST NOT be reused here, and this one MUST NOT be
    reused there. I1 spec §8.1/§9.1 require RFC 8785 specifically for schema/message canonical
    hashing.
    """
    return rfc8785.dumps(value)


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
