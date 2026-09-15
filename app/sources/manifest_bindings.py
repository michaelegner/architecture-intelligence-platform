from collections.abc import Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from app.sources.model import DiagnosticCode, IngestionDiagnostic
from app.sources.pointers import (
    decode_pointer_tokens,
    is_well_formed_pointer,
    pointer_prefix_matches,
)
from app.sources.service_identity import is_valid_service_id

# I1 spec §4.2's exact ArchitectureIdentityBindings shape ("additional fields are rejected"). This is
# a distinct artifact type from the existing architecture.yaml CALLS-relation manifest schema owned
# by app.ingestion.manifest_adapter - the two MUST NOT be merged.
_BINDINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["apiVersion", "kind", "metadata", "bindings"],
    "properties": {
        "apiVersion": {"const": "aip.dev/v1"},
        "kind": {"const": "ArchitectureIdentityBindings"},
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "revision"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "revision": {"type": "string", "minLength": 1},
            },
        },
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["sourceInstanceId", "pointerPrefix", "serviceId"],
                "properties": {
                    "sourceInstanceId": {"type": "string", "minLength": 1},
                    "pointerPrefix": {"type": "string"},
                    "serviceId": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}

_VALIDATOR = Draft202012Validator(_BINDINGS_SCHEMA)


@dataclass(frozen=True)
class ArchitectureIdentityBinding:
    source_instance_id: str
    pointer_prefix: str
    pointer_tokens: tuple[str, ...]
    service_id: str


@dataclass(frozen=True)
class ArchitectureIdentityBindingsDocument:
    manifest_id: str
    manifest_revision: str
    locator: str
    bindings: tuple[ArchitectureIdentityBinding, ...]


def _shape_errors(document: dict) -> list[str]:
    return [
        error.message
        for error in sorted(_VALIDATOR.iter_errors(document), key=lambda e: list(e.path))
    ]


def parse_architecture_identity_bindings(
    document: dict, *, locator: str
) -> tuple[ArchitectureIdentityBindingsDocument | None, list[IngestionDiagnostic]]:
    """I1 spec §4.2: parse and validate one ArchitectureIdentityBindings document - shape conformance,
    RFC 6901 well-formedness of each `pointerPrefix`, and the §4.1 Service-ID grammar of each
    `serviceId`. Does not check cross-document duplicates/conflicts (that's `build_binding_index`'s
    job, run across every discovered binding document at once) or whether `sourceInstanceId` exists
    in a real inventory (no inventory exists yet in this PR).
    """
    shape_errors = _shape_errors(document)
    if shape_errors:
        return None, [
            IngestionDiagnostic(
                code=DiagnosticCode.MANIFEST_BINDING_SHAPE_INVALID,
                message=message,
                source_pointer=locator,
            )
            for message in shape_errors
        ]

    diagnostics: list[IngestionDiagnostic] = []
    bindings: list[ArchitectureIdentityBinding] = []
    for index, raw in enumerate(document["bindings"]):
        pointer_prefix = raw["pointerPrefix"]
        service_id = raw["serviceId"]
        source_instance_id = raw["sourceInstanceId"]

        if not is_well_formed_pointer(pointer_prefix):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MANIFEST_BINDING_POINTER_INVALID,
                    message=f"binding[{index}]: malformed pointerPrefix {pointer_prefix!r}",
                    source_pointer=f"/bindings/{index}/pointerPrefix",
                    source_instance_id=source_instance_id,
                )
            )
            continue
        if not is_valid_service_id(service_id):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.SERVICE_IDENTITY_INVALID,
                    message=f"binding[{index}]: malformed serviceId {service_id!r}",
                    source_pointer=f"/bindings/{index}/serviceId",
                    source_instance_id=source_instance_id,
                )
            )
            continue

        bindings.append(
            ArchitectureIdentityBinding(
                source_instance_id=source_instance_id,
                pointer_prefix=pointer_prefix,
                pointer_tokens=decode_pointer_tokens(pointer_prefix),
                service_id=service_id,
            )
        )

    if diagnostics:
        return None, diagnostics

    parsed = ArchitectureIdentityBindingsDocument(
        manifest_id=document["metadata"]["id"],
        manifest_revision=document["metadata"]["revision"],
        locator=locator,
        bindings=tuple(bindings),
    )
    return parsed, []


@dataclass(frozen=True)
class BindingIndexEntry:
    source_instance_id: str
    pointer_prefix: str
    pointer_tokens: tuple[str, ...]
    service_id: str
    manifest_id: str
    manifest_revision: str


@dataclass(frozen=True)
class BindingIndex:
    entries: tuple[BindingIndexEntry, ...]

    def applicable_to(
        self, *, source_instance_id: str, construct_pointer: str
    ) -> tuple[BindingIndexEntry, ...]:
        return tuple(
            entry
            for entry in self.entries
            if entry.source_instance_id == source_instance_id
            and pointer_prefix_matches(prefix=entry.pointer_prefix, candidate=construct_pointer)
        )


def _entry_sort_key(entry: BindingIndexEntry) -> tuple:
    return (
        entry.manifest_id,
        entry.manifest_revision,
        entry.source_instance_id,
        entry.pointer_tokens,
        entry.service_id,
    )


def build_binding_index(
    documents: Sequence[ArchitectureIdentityBindingsDocument],
    *,
    known_source_instance_ids: AbstractSet[str] | None = None,
) -> tuple[BindingIndex, list[IngestionDiagnostic]]:
    """I1 spec §4.2 phase 1: "discover every source and binding manifest ... collect and canonicalize
    one binding index ... reject unresolved/duplicate/conflicting bindings." Documents and bindings
    are canonically sorted and exact duplicates collapsed, so "permuting source discovery order MUST
    produce the same binding index" holds by construction - feeding the same documents in different
    list orders (or a shuffled `bindings` array within one document) produces an equal `BindingIndex`.

    Conflict detection is one unified rule: for a given source, any two entries whose pointer tokens
    are in a prefix relation (including exact equality) but whose `service_id` differs is
    `SERVICE_IDENTITY_CONFLICT` - this subsumes both "duplicate bindings must be identical" and
    "overlapping prefixes conflict" from the spec text.
    """
    diagnostics: list[IngestionDiagnostic] = []
    raw_entries: list[BindingIndexEntry] = []

    for document in documents:
        for binding in document.bindings:
            if (
                known_source_instance_ids is not None
                and binding.source_instance_id not in known_source_instance_ids
            ):
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.MANIFEST_BINDING_UNKNOWN_SOURCE,
                        message=f"unknown sourceInstanceId: {binding.source_instance_id!r}",
                        source_pointer=binding.pointer_prefix,
                        source_instance_id=binding.source_instance_id,
                    )
                )
                continue
            raw_entries.append(
                BindingIndexEntry(
                    source_instance_id=binding.source_instance_id,
                    pointer_prefix=binding.pointer_prefix,
                    pointer_tokens=binding.pointer_tokens,
                    service_id=binding.service_id,
                    manifest_id=document.manifest_id,
                    manifest_revision=document.manifest_revision,
                )
            )

    sorted_entries = sorted(raw_entries, key=_entry_sort_key)

    deduped: list[BindingIndexEntry] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    for entry in sorted_entries:
        dedupe_key = (entry.source_instance_id, entry.pointer_tokens, entry.service_id)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(entry)

    by_source: dict[str, list[BindingIndexEntry]] = {}
    for entry in deduped:
        by_source.setdefault(entry.source_instance_id, []).append(entry)

    for source_instance_id, entries in by_source.items():
        for i, first in enumerate(entries):
            for second in entries[i + 1 :]:
                if first.service_id == second.service_id:
                    continue
                shorter, longer = (
                    (first, second)
                    if len(first.pointer_tokens) <= len(second.pointer_tokens)
                    else (second, first)
                )
                if longer.pointer_tokens[: len(shorter.pointer_tokens)] == shorter.pointer_tokens:
                    diagnostics.append(
                        IngestionDiagnostic(
                            code=DiagnosticCode.SERVICE_IDENTITY_CONFLICT,
                            message=(
                                f"conflicting Service identity bindings for source "
                                f"{source_instance_id!r} at overlapping pointer prefixes "
                                f"{shorter.pointer_prefix!r} / {longer.pointer_prefix!r}: "
                                f"{first.service_id!r} vs {second.service_id!r}"
                            ),
                            source_pointer=longer.pointer_prefix,
                            source_instance_id=source_instance_id,
                        )
                    )

    return BindingIndex(entries=tuple(deduped)), diagnostics
