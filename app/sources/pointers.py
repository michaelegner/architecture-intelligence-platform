import re

_POINTER_TOKEN_RE = re.compile(r"/([^/]*)")


def is_well_formed_pointer(pointer: str) -> bool:
    """RFC 6901: the empty string denotes the whole document; any other well-formed pointer starts
    with '/' and every '~' is immediately followed by '0' or '1'.
    """
    if pointer == "":
        return True
    if not pointer.startswith("/"):
        return False
    i = 0
    length = len(pointer)
    while i < length:
        if pointer[i] == "~":
            if i + 1 >= length or pointer[i + 1] not in "01":
                return False
            i += 2
        else:
            i += 1
    return True


def decode_pointer_tokens(pointer: str) -> tuple[str, ...]:
    """RFC 6901 decode: '' -> () (document root); '/a~1b/c~0d' -> ('a/b', 'c~d').

    Raises ValueError for a pointer that is not well-formed per `is_well_formed_pointer`.
    """
    if not is_well_formed_pointer(pointer):
        raise ValueError(f"not a well-formed RFC 6901 JSON Pointer: {pointer!r}")
    if pointer == "":
        return ()
    raw_tokens = _POINTER_TOKEN_RE.findall(pointer)
    return tuple(token.replace("~1", "/").replace("~0", "~") for token in raw_tokens)


def pointer_prefix_matches(*, prefix: str, candidate: str) -> bool:
    """I1 spec §4.2: "pointerPrefix is parsed into decoded RFC 6901 tokens; matching compares
    complete token sequences, not raw string prefixes." True iff the decoded tokens of `prefix` are a
    tuple-prefix of the decoded tokens of `candidate` - inclusive of exact equality, so that a root
    binding (`pointerPrefix: ""`) applies to the document root itself.

    Worked example from the spec: `/paths/~1foo` must NOT match `/paths/~1foobar`, because the
    decoded token 'foo' is not equal to the decoded token 'foobar' - only a raw-string prefix check
    would (wrongly) succeed here.
    """
    prefix_tokens = decode_pointer_tokens(prefix)
    candidate_tokens = decode_pointer_tokens(candidate)
    if len(prefix_tokens) > len(candidate_tokens):
        return False
    return candidate_tokens[: len(prefix_tokens)] == prefix_tokens
