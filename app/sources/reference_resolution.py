"""Bounded, path-safe multi-file `$ref` resolution (I1 spec §8.1, reused by AsyncAPI per §9: "the
complete OpenAPI containment, URI/pointer normalization, cycle handling... contract from §8").

One shared module for both adapters rather than two independent resolvers - §9 requires literal
code/contract sharing, not just behavioral parity, and PR3a left OpenAPI's `$ref` handling as a
crude same-document name lookup and AsyncAPI's as its own separate, real-but-same-document-only
pointer walker.

The exact §8.1 resolution order, split across this module's functions:

    parse reference URI
      -> reject non-empty URI schemes and authorities                    (parse_ref_uri)
      -> percent-decode the path exactly once; reject invalid encoding   (percent_decode_path_once)
      -> reject an absolute decoded path                                 (is_absolute_decoded_path)
      -> resolve the decoded relative path against the containing
         document's directory, then normalize dot segments               (resolve_relative_path)
      -> resolve symlinks to the real filesystem path
      -> require the real path to be a regular file inside the
         approved source root real path                                  (commit 3: I/O layer)
      -> decode and resolve the fragment as an RFC 6901 JSON Pointer
         (reuses app.sources.pointers.decode_pointer_tokens - already correct, unchanged here)

Containment is checked only after decoding, normalization, and symlink resolution - never on the
raw or partially-normalized string, which is exactly the class of bug that makes a naive
string-prefix containment check bypassable (encoded traversal, `..` escape, symlink escape).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from app.sources.model import DiagnosticCode

_VALID_PERCENT_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


class ReferenceResolutionError(Exception):
    """Carries the exact §8.1 outcome (REJECTED_INVALID vs. REJECTED_UNSUPPORTED) and diagnostic
    code for one `$ref` resolution failure - callers convert this into an `AdapterOutcome`
    diagnostic, never let it propagate as a bare exception."""

    def __init__(self, *, code: DiagnosticCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ParsedRef:
    scheme: str
    authority: str
    path: str
    fragment: str


def parse_ref_uri(ref: str) -> ParsedRef:
    """§8.1 step 1: parse the `$ref` string's URI structure. Percent-encoding in `path` is left
    untouched here - decoding happens exactly once, in `percent_decode_path_once`, as its own
    explicit step, never folded into parsing.
    """
    split = urlsplit(ref)
    return ParsedRef(
        scheme=split.scheme, authority=split.netloc, path=split.path, fragment=split.fragment
    )


def reject_remote_reference(parsed: ParsedRef) -> None:
    """§8.1 step 1's rejection: a non-empty scheme or authority makes the whole reference remote/
    non-local, which is `REJECTED_UNSUPPORTED` for the *whole source* (§8.1: "remote/non-local
    reference -> REJECTED_UNSUPPORTED for the whole source") - not a per-construct omission."""
    if parsed.scheme or parsed.authority:
        raise ReferenceResolutionError(
            code=DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED,
            message=f"remote/non-local reference is not supported: {parsed.scheme or parsed.authority!r}",
        )


def percent_decode_path_once(path: str) -> str:
    """§8.1 step 2: percent-decode the path exactly once. Two distinct malformed-encoding cases are
    rejected: a `%` not followed by two hex digits (`unquote` silently leaves this literal instead
    of raising, so it's checked explicitly first), and a syntactically valid `%XX` escape whose
    decoded bytes are not valid UTF-8 (`unquote(..., errors='strict')` raises `UnicodeDecodeError`
    for this case). Both convert to a typed `ReferenceResolutionError`, never a raw exception."""
    if "%" in path and "%" in _VALID_PERCENT_ESCAPE.sub("", path):
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"malformed percent-encoding in reference path {path!r}",
        )
    try:
        return unquote(path, errors="strict")
    except UnicodeDecodeError as exc:
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"malformed percent-encoding in reference path {path!r}: {exc}",
        ) from exc


def reject_absolute_decoded_path(decoded_path: str) -> None:
    """§8.1 step 3, applied strictly after decoding (step 2) - this ordering is itself
    security-relevant: it catches a percent-encoded absolute path (e.g. `%2Fetc%2Fpasswd`) that a
    check performed *before* decoding would miss entirely."""
    if decoded_path.startswith("/"):
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"absolute reference path is not supported: {decoded_path!r}",
        )


def normalize_dot_segments(path: str) -> str:
    """§8.1 step 5: resolves '.'/'..' segments in a relative POSIX-style path. The caller already
    rejects an absolute decoded path (step 3) before this ever runs, so this is specialized for a
    path that is always relative - a full RFC 3986 §5.2.4 remove_dot_segments handles the absolute
    ('/'-rooted) case too, which never applies here.

    A leading '..' that would climb above the path's own start is kept literally (unresolved), not
    silently dropped or resolved against nothing - this function is pure string canonicalization,
    never a security boundary by itself. The real containment check happens later (I/O layer),
    against the real, symlink-resolved source root; an unresolved leading '..' reliably fails that
    later check by joining outside the root, which is the intended outcome for a genuine escape
    attempt, not something this function needs to detect itself.
    """
    output: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if output and output[-1] != "..":
                output.pop()
            else:
                output.append("..")
            continue
        output.append(segment)
    return "/".join(output)


def resolve_relative_path(*, containing_document_relative_path: str, ref_path: str) -> str:
    """§8.1 steps 4-5 combined: "resolve the decoded relative path against the containing
    document's directory" (join), then "normalize dot segments". Both `containing_document_
    relative_path` and `ref_path` are already-decoded, already-relative (never absolute - the
    caller rejects that in step 3) paths, relative to the approved source root. An empty
    `containing_document_relative_path` (the root document, at the source root's own top level) is
    the identity join - `ref_path` alone.
    """
    containing_dir = (
        containing_document_relative_path.rsplit("/", 1)[0]
        if ("/" in containing_document_relative_path)
        else ""
    )
    joined = f"{containing_dir}/{ref_path}" if containing_dir else ref_path
    return normalize_dot_segments(joined)
