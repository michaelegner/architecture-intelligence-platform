"""I1 spec §5.1.1/§8.1/§9/§9.1's explicit shared-identity mapping mechanism: a versioned artifact
binding exact `(SourceInstanceId, source pointer)` pairs to a full canonical Schema/Message/Queue
ID, so a source's owner-scoped default identity can be deliberately overridden to preserve a prior
(e.g. v0.4.2, pre-owner-scoped) canonical meaning, or to merge two independent sources' claims onto
one shared entity.

Structurally mirrors `app.sources.manifest_bindings` (shape validation via `Draft202012Validator`,
frozen dataclasses, then a sorted-dedup-then-conflict-detection index build) - the same "shape, then
pointer/target validity, then cross-entry conflict" pipeline. The one deliberate difference: Service
bindings match by *pointer prefix* (`app.sources.pointers.pointer_prefix_matches`, since one binding
can cover a whole subtree of an operation's constructs); a Schema/Message/Queue migration mapping
matches by *exact* pointer only (§8.1: "bind one or more *exact* `(SourceInstanceId, source
pointer)` pairs") - a schema/message/queue's own resolved definition pointer is always a single,
fully-resolved location, never a subtree.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from app.sources.model import DiagnosticCode, IngestionDiagnostic
from app.sources.pointers import decode_pointer_tokens, is_well_formed_pointer

_MAPPING_ENTRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sourceInstanceId", "pointer"],
    "properties": {
        "sourceInstanceId": {"type": "string", "minLength": 1},
        "pointer": {"type": "string"},
    },
}


def _entry_schema(id_field: str) -> dict:
    schema = dict(_MAPPING_ENTRY_SCHEMA)
    schema["required"] = [*_MAPPING_ENTRY_SCHEMA["required"], id_field]
    schema["properties"] = {
        **_MAPPING_ENTRY_SCHEMA["properties"],
        id_field: {"type": "string", "minLength": 1},
    }
    return schema


# I1 spec §5.1.1: "The migration artifact SHALL bind ... to ... prior qualified Schema, Message,
# and Queue IDs." `kind`/`apiVersion` naming is this module's own choice (not spec-given, flagged
# for review), mirroring `ArchitectureIdentityBindings`'s own additionalProperties-false discipline.
_MIGRATION_MAPPINGS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["apiVersion", "kind", "metadata"],
    "properties": {
        "apiVersion": {"const": "aip.dev/v1"},
        "kind": {"const": "AipSharedIdentityMappings"},
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id", "revision"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "revision": {"type": "string", "minLength": 1},
            },
        },
        "schemaMappings": {"type": "array", "items": _entry_schema("schemaId")},
        "messageMappings": {"type": "array", "items": _entry_schema("messageId")},
        "queueMappings": {"type": "array", "items": _entry_schema("queueId")},
    },
}

_VALIDATOR = Draft202012Validator(_MIGRATION_MAPPINGS_SCHEMA)

_TARGET_ID_RE = {
    "schema": re.compile(r"^schema:\S+$"),
    "message": re.compile(r"^message:\S+$"),
    "queue": re.compile(r"^queue:\S+$"),
}


@dataclass(frozen=True)
class IdentityMappingEntry:
    source_instance_id: str
    pointer: str
    pointer_tokens: tuple[str, ...]
    target_id: str


@dataclass(frozen=True)
class MigrationMappingsDocument:
    artifact_id: str
    artifact_revision: str
    locator: str
    schema_mappings: tuple[IdentityMappingEntry, ...] = field(default_factory=tuple)
    message_mappings: tuple[IdentityMappingEntry, ...] = field(default_factory=tuple)
    queue_mappings: tuple[IdentityMappingEntry, ...] = field(default_factory=tuple)


def _shape_errors(document: dict) -> list[str]:
    # jsonschema error paths mix str (property names) and int (array indices) elements - two
    # errors whose paths happen to disagree in type at the same position (e.g. one nested under an
    # array index, another under a differently-shaped branch) would raise TypeError from plain
    # `list` comparison. Stringifying each path element first keeps sorting deterministic without
    # requiring every element to be pairwise comparable.
    return [
        error.message
        for error in sorted(
            _VALIDATOR.iter_errors(document), key=lambda e: [str(p) for p in e.path]
        )
    ]


def _parse_entries(
    raw_entries: Sequence[dict], *, id_field: str, kind: str, locator: str, array_name: str
) -> tuple[tuple[IdentityMappingEntry, ...], list[IngestionDiagnostic]]:
    diagnostics: list[IngestionDiagnostic] = []
    entries: list[IdentityMappingEntry] = []
    for index, raw in enumerate(raw_entries):
        pointer = raw["pointer"]
        target_id = raw[id_field]
        source_pointer = f"/{array_name}/{index}"

        if not is_well_formed_pointer(pointer):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID,
                    message=f"{array_name}[{index}]: malformed pointer {pointer!r}",
                    source_pointer=f"{source_pointer}/pointer",
                    source_instance_id=raw["sourceInstanceId"],
                )
            )
            continue
        if not _TARGET_ID_RE[kind].fullmatch(target_id):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_TARGET_INVALID,
                    message=f"{array_name}[{index}]: {id_field} {target_id!r} is not a valid {kind} id",
                    source_pointer=f"{source_pointer}/{id_field}",
                    source_instance_id=raw["sourceInstanceId"],
                )
            )
            continue

        entries.append(
            IdentityMappingEntry(
                source_instance_id=raw["sourceInstanceId"],
                pointer=pointer,
                pointer_tokens=decode_pointer_tokens(pointer),
                target_id=target_id,
            )
        )
    return tuple(entries), diagnostics


def parse_migration_mappings(
    document: dict, *, locator: str
) -> tuple[MigrationMappingsDocument | None, list[IngestionDiagnostic]]:
    """Parses and validates one migration-mappings document - shape conformance, RFC 6901
    well-formedness of each `pointer`, and each target id's kind-specific grammar. Does not check
    cross-document/cross-entry duplicates or conflicts (that's `build_shared_identity_index`'s job,
    run across every configured document at once) or whether `sourceInstanceId` exists in a real
    inventory (mirroring `parse_architecture_identity_bindings`'s own scope split).
    """
    shape_errors = _shape_errors(document)
    if shape_errors:
        return None, [
            IngestionDiagnostic(
                code=DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID,
                message=message,
                source_pointer=locator,
            )
            for message in shape_errors
        ]

    diagnostics: list[IngestionDiagnostic] = []
    schema_mappings, schema_diagnostics = _parse_entries(
        document.get("schemaMappings") or (),
        id_field="schemaId",
        kind="schema",
        locator=locator,
        array_name="schemaMappings",
    )
    message_mappings, message_diagnostics = _parse_entries(
        document.get("messageMappings") or (),
        id_field="messageId",
        kind="message",
        locator=locator,
        array_name="messageMappings",
    )
    queue_mappings, queue_diagnostics = _parse_entries(
        document.get("queueMappings") or (),
        id_field="queueId",
        kind="queue",
        locator=locator,
        array_name="queueMappings",
    )
    diagnostics.extend(schema_diagnostics)
    diagnostics.extend(message_diagnostics)
    diagnostics.extend(queue_diagnostics)
    if diagnostics:
        return None, diagnostics

    parsed = MigrationMappingsDocument(
        artifact_id=document["metadata"]["id"],
        artifact_revision=document["metadata"]["revision"],
        locator=locator,
        schema_mappings=schema_mappings,
        message_mappings=message_mappings,
        queue_mappings=queue_mappings,
    )
    return parsed, []


def _kind_entries(
    document: MigrationMappingsDocument, *, kind: str
) -> tuple[IdentityMappingEntry, ...]:
    return {
        "schema": document.schema_mappings,
        "message": document.message_mappings,
        "queue": document.queue_mappings,
    }[kind]


def _entry_sort_key(entry: IdentityMappingEntry) -> tuple:
    return (entry.source_instance_id, entry.pointer_tokens, entry.target_id)


def _build_kind_index(
    documents: Sequence[MigrationMappingsDocument], *, kind: str
) -> tuple[dict[tuple[str, str], str], list[IngestionDiagnostic]]:
    """Sorted-dedup-then-conflict, mirroring `manifest_bindings.build_binding_index`: an identical
    (source_instance_id, pointer, target_id) triple repeated across files collapses silently
    (permutation-independent by construction); the same (source_instance_id, pointer) bound to two
    *different* target ids is `MIGRATION_MAPPING_CONFLICT`.
    """
    raw_entries = [entry for document in documents for entry in _kind_entries(document, kind=kind)]
    sorted_entries = sorted(raw_entries, key=_entry_sort_key)

    index: dict[tuple[str, str], str] = {}
    diagnostics: list[IngestionDiagnostic] = []
    seen_triples: set[tuple[str, str, str]] = set()
    for entry in sorted_entries:
        triple = (entry.source_instance_id, entry.pointer, entry.target_id)
        if triple in seen_triples:
            continue
        seen_triples.add(triple)

        key = (entry.source_instance_id, entry.pointer)
        if key in index and index[key] != entry.target_id:
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_CONFLICT,
                    message=(
                        f"conflicting {kind} migration mapping for {entry.source_instance_id!r} "
                        f"at {entry.pointer!r}: {index[key]!r} vs {entry.target_id!r}"
                    ),
                    source_pointer=entry.pointer,
                    source_instance_id=entry.source_instance_id,
                )
            )
            continue
        index[key] = entry.target_id

    return index, diagnostics


@dataclass(frozen=True)
class SharedIdentityMappingIndex:
    schema_index: dict[tuple[str, str], str] = field(default_factory=dict)
    message_index: dict[tuple[str, str], str] = field(default_factory=dict)
    queue_index: dict[tuple[str, str], str] = field(default_factory=dict)
    documents: tuple[MigrationMappingsDocument, ...] = field(default_factory=tuple)

    def schema_id_for(self, *, source_instance_id: str, pointer: str) -> str | None:
        return self.schema_index.get((source_instance_id, pointer))

    def message_id_for(self, *, source_instance_id: str, pointer: str) -> str | None:
        return self.message_index.get((source_instance_id, pointer))

    def queue_id_for(self, *, source_instance_id: str, pointer: str) -> str | None:
        return self.queue_index.get((source_instance_id, pointer))


EMPTY_SHARED_IDENTITY_INDEX = SharedIdentityMappingIndex()


def build_shared_identity_index(
    documents: Sequence[MigrationMappingsDocument],
) -> tuple[SharedIdentityMappingIndex, list[IngestionDiagnostic]]:
    """Merges every configured migration-mapping document into one lookup index, usable by any
    adapter regardless of which file(s) declared which entries - callers that need to distinguish
    the bundled-example artifact from any other configured one (e.g. for the mapping-context
    digest's `bundledMigrationMappings` vs. `sharedSchemaMappings`/etc. split) do so by filtering
    `documents` on `artifact_id` before or after this call, not by any flag this index itself
    carries.
    """
    schema_index, schema_diagnostics = _build_kind_index(documents, kind="schema")
    message_index, message_diagnostics = _build_kind_index(documents, kind="message")
    queue_index, queue_diagnostics = _build_kind_index(documents, kind="queue")
    diagnostics = [*schema_diagnostics, *message_diagnostics, *queue_diagnostics]
    return (
        SharedIdentityMappingIndex(
            schema_index=schema_index,
            message_index=message_index,
            queue_index=queue_index,
            documents=tuple(documents),
        ),
        diagnostics,
    )


def load_migration_mappings(
    paths: Sequence[Path],
) -> tuple[SharedIdentityMappingIndex, tuple[IngestionDiagnostic, ...]]:
    """Reads and parses every configured migration-mapping file (`app.settings.SourcesConfig.
    migrations`), then merges them into one index. A missing/unreadable file or one that isn't
    well-formed YAML/a mapping at its root is diagnosed rather than raised or silently skipped -
    §5.1.1: "Missing or modified migration configuration is diagnosed and MUST NOT fall back to a
    directory slug or name-derived identity."
    """
    diagnostics: list[IngestionDiagnostic] = []
    documents: list[MigrationMappingsDocument] = []

    for path in paths:
        locator = str(path)
        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_FILE_UNAVAILABLE,
                    message=f"{locator}: {exc}",
                    source_pointer=locator,
                )
            )
            continue

        try:
            parsed_yaml = yaml.safe_load(raw_bytes)
        except yaml.YAMLError as exc:
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID,
                    message=f"{locator}: {exc}",
                    source_pointer=locator,
                )
            )
            continue
        if not isinstance(parsed_yaml, dict):
            diagnostics.append(
                IngestionDiagnostic(
                    code=DiagnosticCode.MIGRATION_MAPPING_SHAPE_INVALID,
                    message=f"{locator}: root document is not a mapping",
                    source_pointer=locator,
                )
            )
            continue

        document, parse_diagnostics = parse_migration_mappings(parsed_yaml, locator=locator)
        diagnostics.extend(parse_diagnostics)
        if document is not None:
            documents.append(document)

    index, index_diagnostics = build_shared_identity_index(documents)
    diagnostics.extend(index_diagnostics)
    return index, tuple(diagnostics)
