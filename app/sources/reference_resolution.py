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
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

from app.sources.identity import ClosureEntry
from app.sources.model import DiagnosticCode
from app.sources.pointers import decode_pointer_tokens

DEFAULT_MAX_REFERENCE_DEPTH = 16
DEFAULT_MAX_REFERENCE_FILES = 128
DEFAULT_MAX_REFERENCE_BYTES = 8 * 1024 * 1024

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


def normalize_non_json_scalars(value: Any) -> Any:
    """YAML's default schema auto-converts an unquoted date/timestamp-shaped scalar (e.g. an
    illustrative `examples:` value) into a native `datetime.date`/`datetime.datetime` - a type JSON
    has no representation for, which crashes RFC 8785 canonicalization deep in an adapter's
    identity/digest computation with an opaque library error instead of a clean diagnostic. Since a
    JSON-format equivalent of the same document could only ever have carried that value as a quoted
    string, converting it to its ISO 8601 string form here - once, centrally, for every parsed
    document (root or referenced) - loses no information and keeps every downstream consumer
    JSON-safe. Shared with `app.ingestion.filesystem_discoverer`, which applies it to root
    documents; this module applies it to every referenced document it reads too.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_non_json_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_non_json_scalars(item) for item in value]
    return value


@dataclass
class ResolutionCache:
    """Per-source-instance cache of every document read while resolving its `$ref` graph, keyed by
    normalized path relative to `source_root`. Shared across every `resolve_and_read` call for one
    source (and the discoverer's own closure walk) so a file referenced from multiple places is
    read and parsed exactly once, and so cycle/limit accounting has one consistent view of what's
    already been visited.
    """

    source_root: Path
    source_root_real: Path
    documents: dict[str, dict] = field(default_factory=dict)
    file_bytes: dict[str, bytes] = field(default_factory=dict)


def new_resolution_cache(
    source_root: Path, *, root_relative_path: str, root_document: dict, root_bytes: bytes
) -> ResolutionCache:
    """Builds a `ResolutionCache` pre-seeded with the already-loaded root document, so a
    fragment-only `$ref` inside it resolves without re-reading anything from disk."""
    cache = ResolutionCache(
        source_root=source_root, source_root_real=source_root.resolve(strict=False)
    )
    cache.documents[root_relative_path] = root_document
    cache.file_bytes[root_relative_path] = root_bytes
    return cache


def _load_and_validate_document(
    cache: ResolutionCache, normalized_relative_path: str
) -> tuple[dict, bytes]:
    """§8.1 steps 6-7: resolve symlinks to the real filesystem path, then require that real path to
    be a regular file inside the approved source root's own real path. `Path.resolve(strict=False)`
    both follows symlinks to their real target and normalizes the path, without raising for a
    missing target (that becomes a clean `REJECTED_INVALID`, never an uncaught OSError).
    `is_relative_to` (not a string-prefix check, which `"/root-evil".startswith("/root")` shows is
    bypassable) is the actual containment boundary.
    """
    if normalized_relative_path in cache.documents:
        return cache.documents[normalized_relative_path], cache.file_bytes[normalized_relative_path]

    candidate = cache.source_root / normalized_relative_path
    real_path = candidate.resolve(strict=False)
    if not real_path.is_relative_to(cache.source_root_real):
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"reference {normalized_relative_path!r} escapes the approved source root",
        )
    if not real_path.is_file():
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"referenced file does not exist or is not a regular file: {normalized_relative_path!r}",
        )

    raw_bytes = real_path.read_bytes()
    try:
        parsed = yaml.safe_load(raw_bytes)
    except yaml.YAMLError as exc:
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"malformed referenced document {normalized_relative_path!r}: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"referenced document root is not a mapping: {normalized_relative_path!r}",
        )
    document = normalize_non_json_scalars(parsed)

    cache.documents[normalized_relative_path] = document
    cache.file_bytes[normalized_relative_path] = raw_bytes
    return document, raw_bytes


def resolve_pointer(document: dict, pointer_tokens: tuple[str, ...]) -> Any:
    """§8.1 step 8's node walk, once the fragment's tokens are already decoded. A token that
    doesn't resolve - a missing dict key, a non-integer or out-of-range list index, or a walk past
    a scalar - is a dangling JSON Pointer, `REJECTED_INVALID`."""
    node: Any = document
    for token in pointer_tokens:
        if isinstance(node, dict):
            if token not in node:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_INVALID,
                    message=f"dangling JSON Pointer: no key {token!r}",
                )
            node = node[token]
        elif isinstance(node, list):
            if not token.lstrip("-").isdigit() or token.startswith("-"):
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_INVALID,
                    message=f"dangling JSON Pointer: not a valid array index {token!r}",
                )
            index = int(token)
            if index >= len(node):
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_INVALID,
                    message=f"dangling JSON Pointer: array index {index} out of range",
                )
            node = node[index]
        else:
            raise ReferenceResolutionError(
                code=DiagnosticCode.REFERENCE_INVALID,
                message=f"dangling JSON Pointer: cannot descend into a scalar at {token!r}",
            )
    return node


@dataclass(frozen=True)
class ResolvedRef:
    target_document: dict
    normalized_relative_path: str
    pointer_tokens: tuple[str, ...]
    target_node: Any


def resolve_and_read(
    *, containing_document_relative_path: str, ref: str, cache: ResolutionCache
) -> ResolvedRef:
    """The full §8.1 resolution order for one `$ref` string, end to end. `containing_document_
    relative_path` must already be a key in `cache.documents` (the discoverer/adapter seeds the
    cache with the root document via `new_resolution_cache`; every other document this function
    resolves gets cached as a side effect of resolving it). Raises `ReferenceResolutionError` on
    any step's failure; never lets a raw filesystem/YAML/lookup exception escape.
    """
    parsed = parse_ref_uri(ref)
    reject_remote_reference(parsed)
    decoded_path = percent_decode_path_once(parsed.path)

    if decoded_path:
        reject_absolute_decoded_path(decoded_path)
        target_relative_path = resolve_relative_path(
            containing_document_relative_path=containing_document_relative_path,
            ref_path=decoded_path,
        )
        target_document, _ = _load_and_validate_document(cache, target_relative_path)
    else:
        target_relative_path = containing_document_relative_path
        target_document = cache.documents[containing_document_relative_path]

    try:
        pointer_tokens = decode_pointer_tokens(parsed.fragment)
    except ValueError as exc:
        raise ReferenceResolutionError(
            code=DiagnosticCode.REFERENCE_INVALID,
            message=f"malformed JSON Pointer fragment {parsed.fragment!r}: {exc}",
        ) from exc

    target_node = resolve_pointer(target_document, pointer_tokens)
    return ResolvedRef(
        target_document=target_document,
        normalized_relative_path=target_relative_path,
        pointer_tokens=pointer_tokens,
        target_node=target_node,
    )


def _iter_ref_strings(node: Any) -> Any:
    """Generic (format-agnostic) recursive scan for every `$ref` string value anywhere in a parsed
    document tree - a `$ref` node has the identical shape in an OpenAPI and an AsyncAPI document,
    so this needs no per-format knowledge at all, matching §9's "reuse the complete... contract
    from §8" requirement by literal code sharing.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from _iter_ref_strings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_ref_strings(item)


def walk_transitive_closure(
    root_document: dict,
    *,
    root_relative_path: str,
    cache: ResolutionCache,
    max_depth: int = DEFAULT_MAX_REFERENCE_DEPTH,
    max_files: int = DEFAULT_MAX_REFERENCE_FILES,
    max_bytes: int = DEFAULT_MAX_REFERENCE_BYTES,
) -> tuple[ClosureEntry, ...]:
    """§8's bounded-closure requirement: "enforce a maximum reference depth of 16, 128 distinct
    referenced files, and 8 MiB total bytes across the root and closure; exceeding any limit is
    REJECTED_UNSUPPORTED with REFERENCE_LIMIT_EXCEEDED." Depth is a closure-wide `$ref` hop count
    from the root (a same-file chain of A -> B -> C is 2 hops even though it's 1 file) - the file
    count and byte limits are likewise closure-wide, not per-branch; the spec doesn't define
    "depth"'s unit precisely, so this is a deliberate, documented resolution of that ambiguity,
    flagged for review.

    File count and depth apply only to *referenced* files (the root itself is never counted against
    either); the byte budget is explicit "across the root and closure", so the root's own bytes do
    count there. Cycle detection here is file-level only (a target file already on the *current*
    resolution path, never merely "seen before" - that would wrongly reject a legitimate diamond/
    shared reference) - a *same-document* composition cycle (e.g. a schema's `allOf` referencing
    itself via a fragment-only `$ref`) adds no new file to this closure at all, so it is not this
    function's concern; the adapter's own recursive schema-normalization walk (which actually
    expands a fragment-only `$ref`'s content) carries its own, separate cycle guard for that case.

    Returns the closure entries actually visited (root excluded, matching `dependency_closure_
    digest`'s own "the root document is excluded" contract) for the discoverer to hash.
    """
    visited: set[str] = set()
    entries: list[ClosureEntry] = []
    total_bytes = len(cache.file_bytes.get(root_relative_path, b""))

    def visit(
        document: dict, document_relative_path: str, *, depth: int, path_stack: tuple[str, ...]
    ) -> None:
        nonlocal total_bytes
        for ref in _iter_ref_strings(document):
            parsed = parse_ref_uri(ref)
            reject_remote_reference(parsed)
            decoded_path = percent_decode_path_once(parsed.path)
            if not decoded_path:
                continue  # same-document reference: no new file, not this function's concern
            reject_absolute_decoded_path(decoded_path)
            target_relative_path = resolve_relative_path(
                containing_document_relative_path=document_relative_path, ref_path=decoded_path
            )
            if target_relative_path in path_stack:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_CYCLE_UNSUPPORTED,
                    message=f"reference cycle detected at {target_relative_path!r}",
                )
            new_depth = depth + 1
            if new_depth > max_depth:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_LIMIT_EXCEEDED,
                    message=f"reference depth exceeds the maximum of {max_depth}",
                )
            if target_relative_path in visited:
                continue  # already fully explored via another path - a diamond, not a cycle
            target_document, target_bytes = _load_and_validate_document(cache, target_relative_path)
            visited.add(target_relative_path)
            if len(visited) > max_files:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_LIMIT_EXCEEDED,
                    message=f"reference closure exceeds the maximum of {max_files} distinct files",
                )
            total_bytes += len(target_bytes)
            if total_bytes > max_bytes:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_LIMIT_EXCEEDED,
                    message=f"reference closure exceeds the maximum of {max_bytes} total bytes",
                )
            entries.append(
                ClosureEntry(normalized_relative_path=target_relative_path, file_bytes=target_bytes)
            )
            visit(
                target_document,
                target_relative_path,
                depth=new_depth,
                path_stack=(*path_stack, target_relative_path),
            )

    visit(root_document, root_relative_path, depth=0, path_stack=(root_relative_path,))
    return tuple(entries)
