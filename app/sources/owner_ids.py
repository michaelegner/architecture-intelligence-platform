from collections.abc import Sequence

from app.sources.encoding import length_delimited, length_delimited_group, sha256_hex


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def _encode_source_pointer(document_path: str, pointer_tokens: Sequence[str]) -> bytes:
    """I1 spec §8.1/§9.1: "The normalized definition source pointer is the normalized relative
    document path plus decoded RFC 6901 pointer." Encoded as the document path and the pointer's
    decoded tokens (as their own nested group) - two separate fields rather than one joined string,
    to avoid delimiter-collision risk between a path segment and a pointer token (e.g. either could
    contain '/' or '#').
    """
    return length_delimited(
        _utf8(document_path),
        length_delimited_group([_utf8(token) for token in pointer_tokens]),
    )


class InvalidXVersionError(ValueError):
    """I1 spec §9.1: "another type is REJECTED_INVALID" for a non-string, non-absent `x-version`."""


def normalize_x_version(value: object) -> str:
    """I1 spec §9.1: "x-version participates in the owner key only when it is a non-empty string;
    another type is REJECTED_INVALID." `None`, a missing value, and an empty string all normalize
    identically to the empty placeholder; only a genuinely non-empty string participates distinctly.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    raise InvalidXVersionError(f"x-version must be a string or absent, got {type(value).__name__}")


def schema_owned_id(
    *,
    canonical_service_id: str,
    source_instance_id: str,
    normalized_definition_document_path: str,
    definition_pointer_tokens: Sequence[str],
) -> str:
    """I1 spec §8.1:

    schema_owner_key
      = length-delimited(canonical Service id, SourceInstanceId, normalized definition source pointer)

    default schema id = schema:owned:<sha256(schema_owner_key)>
    """
    schema_owner_key = length_delimited(
        _utf8(canonical_service_id),
        _utf8(source_instance_id),
        _encode_source_pointer(normalized_definition_document_path, definition_pointer_tokens),
    )
    return f"schema:owned:{sha256_hex(schema_owner_key)}"


def message_owned_id(
    *,
    canonical_service_id: str,
    source_instance_id: str,
    normalized_definition_document_path: str,
    definition_pointer_tokens: Sequence[str],
    normalized_x_version_or_empty: str = "",
) -> str:
    """I1 spec §9.1:

    message_owner_key
      = length-delimited(canonical Service id, SourceInstanceId,
          normalized resolved message-definition source pointer, normalized x-version-or-empty)

    default message id = message:owned:<sha256(message_owner_key)>
    """
    message_owner_key = length_delimited(
        _utf8(canonical_service_id),
        _utf8(source_instance_id),
        _encode_source_pointer(normalized_definition_document_path, definition_pointer_tokens),
        _utf8(normalized_x_version_or_empty),
    )
    return f"message:owned:{sha256_hex(message_owner_key)}"


def inline_payload_schema_id(
    *,
    message_id: str,
    normalized_inline_payload_document_path: str,
    inline_payload_pointer_tokens: Sequence[str],
) -> str:
    """I1 spec §9.1:

    inline payload schema id
      = schema:owned:<sha256(length-delimited(message id, normalized inline payload source pointer))>
    """
    key = length_delimited(
        _utf8(message_id),
        _encode_source_pointer(
            normalized_inline_payload_document_path, inline_payload_pointer_tokens
        ),
    )
    return f"schema:owned:{sha256_hex(key)}"


def queue_owned_id(
    *,
    stable_broker_id: str,
    normalized_namespace_or_empty: str,
    exact_channel_address: str,
) -> str:
    """I1 spec §9:

        derived queue id
          = queue:owned:<sha256(length-delimited(
              stable broker id, normalized namespace-or-empty, exact channel address))>

    The caller is responsible for applying Unicode NFC normalization to the raw channel key before
    calling this (`app.sources.encoding.unicode_nfc`) - channel-address normalization is kept out of
    this function so it stays a pure hash-formula function.
    """
    key = length_delimited(
        _utf8(stable_broker_id),
        _utf8(normalized_namespace_or_empty),
        _utf8(exact_channel_address),
    )
    return f"queue:owned:{sha256_hex(key)}"
