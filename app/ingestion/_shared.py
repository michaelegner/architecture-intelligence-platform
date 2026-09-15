"""Small helpers shared by the concrete SourceAdapter implementations in this package. Not part of
the public seam (app.sources.registry) - just avoids duplicating the same few lines across
openapi_adapter.py/asyncapi_adapter.py/manifest_adapter.py.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.canonical.model import ArchitectureModel
from app.sources.identity import normalize_relative_posix_path
from app.sources.jcs import canonical_sha256_hex, sort_by_canonical_hash
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult, LoadedSource
from app.sources.reference_resolution import (
    ReferenceResolutionError,
    ResolutionCache,
    new_resolution_cache,
    resolve_and_read,
)
from app.sources.registry import AdapterOutcome
from app.sources.service_identity import ServiceIdentityOutcome, ServiceIdentityResolution

# I1 spec §8.1: "The canonical projection excludes only description, summary, example, examples,
# and externalDocs." Applied at every level of a normalized schema tree (top-level and every
# nested/referenced construct), not just the top - I1 §8's "map supported inline, array, and
# nested schemas" bullet.
EXCLUDED_SCHEMA_FIELDS = frozenset(
    {"description", "summary", "example", "examples", "externalDocs"}
)

_COMPOSITION_KEYS = ("allOf", "oneOf", "anyOf")

_IDENTITY_OUTCOME_TO_RESULT = {
    ServiceIdentityOutcome.REJECTED_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    ServiceIdentityOutcome.REJECTED_CONFLICT: IngestionResult.REJECTED_CONFLICT,
    ServiceIdentityOutcome.REJECTED_INVALID: IngestionResult.REJECTED_INVALID,
}


def rejected_outcome_for_identity(resolution: ServiceIdentityResolution) -> AdapterOutcome:
    return AdapterOutcome(
        result=_IDENTITY_OUTCOME_TO_RESULT[resolution.outcome],
        model=ArchitectureModel(),
        diagnostics=tuple(resolution.diagnostics),
        semantic_input_digest=None,
    )


def build_resolution_cache(loaded: LoadedSource) -> tuple[ResolutionCache, str]:
    """Builds the per-source `ResolutionCache` used for every `$ref` this source's adapter resolves
    (schema/message/payload definitions alike), plus the root document's own normalized relative
    path - the key both the cache and every `resolve_and_read`/`resolve_and_normalize_schema` call
    for this source key off.

    `loaded.source_root` is empty only for a `LoadedSource` built directly by a unit test with no
    real filesystem backing (see its own docstring) - there, no cross-file resolution is reachable
    anyway (only fragment-only `#/...` refs are), so the root's own locator string stands in for its
    relative path: self-consistent for cache keying, even though it isn't a real relative-to-root
    path.
    """
    locator = loaded.descriptor.locator
    if loaded.source_root:
        root_relative_path = normalize_relative_posix_path(
            str(Path(locator).relative_to(Path(loaded.source_root)))
        )
    else:
        root_relative_path = normalize_relative_posix_path(locator)

    source_root = Path(loaded.source_root) if loaded.source_root else Path(locator).parent
    root_bytes = Path(locator).read_bytes() if loaded.source_root else b""
    cache = new_resolution_cache(
        source_root,
        root_relative_path=root_relative_path,
        root_document=loaded.document,
        root_bytes=root_bytes,
    )
    return cache, root_relative_path


def _normalize_schema_node(
    node: Any,
    *,
    containing_document_relative_path: str,
    cache: ResolutionCache,
    path_stack: tuple[tuple[str, tuple[str, ...]], ...],
    composition_seen: list[bool],
) -> Any:
    """§8.1: "Every admitted schema is converted to a JSON-compatible value, all local references
    are expanded" - recursively substitutes every `$ref` node with its fully-normalized resolved
    target (never leaving a `$ref` key in the output), strips the excluded fields at every level,
    and sorts `allOf`/`oneOf`/`anyOf` branch arrays by canonical hash once their branches are
    themselves normalized. `path_stack` carries (document path, pointer tokens) pairs for the
    current resolution chain only - a target already on this chain is a genuine cycle
    (`REFERENCE_CYCLE_UNSUPPORTED`); a target visited via a different, already-completed branch
    (a diamond) is not tracked here at all and is simply re-normalized, which is safe since this
    walk has no side effects to duplicate.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            resolved = resolve_and_read(
                containing_document_relative_path=containing_document_relative_path,
                ref=ref,
                cache=cache,
            )
            cycle_key = (resolved.normalized_relative_path, resolved.pointer_tokens)
            if cycle_key in path_stack:
                raise ReferenceResolutionError(
                    code=DiagnosticCode.REFERENCE_CYCLE_UNSUPPORTED,
                    message=f"reference cycle detected at {cycle_key!r}",
                )
            return _normalize_schema_node(
                resolved.target_node,
                containing_document_relative_path=resolved.normalized_relative_path,
                cache=cache,
                path_stack=(*path_stack, cycle_key),
                composition_seen=composition_seen,
            )

        normalized = {
            key: _normalize_schema_node(
                value,
                containing_document_relative_path=containing_document_relative_path,
                cache=cache,
                path_stack=path_stack,
                composition_seen=composition_seen,
            )
            for key, value in node.items()
            if key not in EXCLUDED_SCHEMA_FIELDS
        }
        for composition_key in _COMPOSITION_KEYS:
            branches = normalized.get(composition_key)
            if isinstance(branches, list):
                composition_seen.append(True)
                normalized[composition_key] = sort_by_canonical_hash(branches)
        return normalized

    if isinstance(node, list):
        return [
            _normalize_schema_node(
                item,
                containing_document_relative_path=containing_document_relative_path,
                cache=cache,
                path_stack=path_stack,
                composition_seen=composition_seen,
            )
            for item in node
        ]

    return node


@dataclass(frozen=True)
class NormalizedSchema:
    normalized_definition_document_path: str
    definition_pointer_tokens: tuple[str, ...]
    canonical_hash: str
    has_uninterpreted_composition: bool


def resolve_and_normalize_schema(
    top_node: dict,
    *,
    own_document_relative_path: str,
    own_pointer_tokens: tuple[str, ...],
    cache: ResolutionCache,
) -> NormalizedSchema:
    """§8.1's full per-construct identity + canonical-hash computation for one top-level schema
    slot (an operation's request/response media-type schema, or a message's payload). `top_node`
    may itself be a `$ref` (identity comes from the resolved target's own document path + pointer)
    or inline (identity is `own_pointer_tokens`, "its own stable request/response/media-type
    pointer"). Raises `ReferenceResolutionError` on any resolution failure anywhere in the tree
    (dangling/invalid/remote/cyclic) - callers convert that into the appropriate whole-source
    `REJECTED_*` outcome, per §8.1's construct-outcome table.
    """
    composition_seen: list[bool] = []
    ref = top_node.get("$ref") if isinstance(top_node, dict) else None
    if isinstance(ref, str):
        resolved = resolve_and_read(
            containing_document_relative_path=own_document_relative_path, ref=ref, cache=cache
        )
        definition_document_path = resolved.normalized_relative_path
        definition_pointer_tokens = resolved.pointer_tokens
        normalized = _normalize_schema_node(
            resolved.target_node,
            containing_document_relative_path=resolved.normalized_relative_path,
            cache=cache,
            path_stack=((resolved.normalized_relative_path, resolved.pointer_tokens),),
            composition_seen=composition_seen,
        )
    else:
        definition_document_path = own_document_relative_path
        definition_pointer_tokens = own_pointer_tokens
        normalized = _normalize_schema_node(
            top_node,
            containing_document_relative_path=own_document_relative_path,
            cache=cache,
            path_stack=((own_document_relative_path, own_pointer_tokens),),
            composition_seen=composition_seen,
        )

    return NormalizedSchema(
        normalized_definition_document_path=definition_document_path,
        definition_pointer_tokens=definition_pointer_tokens,
        canonical_hash=canonical_sha256_hex(normalized),
        has_uninterpreted_composition=bool(composition_seen),
    )


_REFERENCE_ERROR_RESULT = {
    DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.REFERENCE_CYCLE_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.REFERENCE_LIMIT_EXCEEDED: IngestionResult.REJECTED_UNSUPPORTED,
    DiagnosticCode.REFERENCE_INVALID: IngestionResult.REJECTED_INVALID,
}


def rejected_outcome_for_reference_error(
    exc: ReferenceResolutionError, *, source_pointer: str
) -> AdapterOutcome:
    """§8.1's construct-outcome table: any `$ref` resolution failure anywhere in a schema/message/
    payload tree rejects the *whole source* - "Whole-source rejection occurs only for ... reference
    cycle/limit, invalid structure/reference..." - never just the one affected relation.
    """
    return AdapterOutcome(
        result=_REFERENCE_ERROR_RESULT[exc.code],
        model=ArchitectureModel(),
        diagnostics=(
            IngestionDiagnostic(code=exc.code, message=exc.message, source_pointer=source_pointer),
        ),
        semantic_input_digest=None,
    )
