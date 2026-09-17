"""I2 Draft 0.2 §4.2 ("Versioned envelope") and §4.3 ("Completeness and ingestion bounds") - v0.5.0
I2 §12 slice 2a: envelope shape validation, bounds/security enforcement, and bounded sanitized
loading of a frozen Kubernetes source snapshot bundle. Pure and in-memory except for the actual file
reads it must perform to enforce §4.3's bounds (byte size, object count, sha256 verification) -
mirrors the orchestrator's own "entirely in memory, with zero Neo4j I/O" discipline; there is no
Neo4j access anywhere in this module.

No `SourceDiscoverer`/`KubernetesSourceConfig`/`SourceKind.KUBERNETES` here - this module is called
by a later slice's discoverer, not the other way around. `validate_kubernetes_snapshot` is the one
entry point that slice does need; everything else here is its own implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.sources.encoding import sha256_hex
from app.sources.model import (
    DiagnosticCode,
    IngestionDiagnostic,
    IngestionResult,
    KubernetesResourceEntry,
)

# I2 Draft 0.2 §4.3: "parser nesting is bounded to 64 levels."
MAX_YAML_NESTING_DEPTH = 64
# I2 Draft 0.2 §4.3: "at most 256 files, 32 MiB total input bytes including envelope, and 10,000
# resource objects."
MAX_FILE_COUNT = 256
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_RESOURCE_OBJECT_COUNT = 10_000

# I2 Draft 0.2 §4.2: "The resourceTypes list is the exact eight-entry set above" (§4.2's own YAML
# example enumerates them; §5's admitted-resources table is the same eight, in the same content).
EXPECTED_RESOURCE_TYPES = frozenset(
    {
        "v1/Namespace",
        "v1/Pod",
        "v1/Service",
        "apps/v1/Deployment",
        "apps/v1/StatefulSet",
        "apps/v1/DaemonSet",
        "apps/v1/ReplicaSet",
        "networking.k8s.io/v1/Ingress",
    }
)


# --------------------------------------------------------------------------------------------
# Hardened YAML/JSON loading
#
# No other YAML consumer in this codebase (`app.ingestion.filesystem_discoverer`,
# `app.sources.migration_mappings`, `app.sources.tombstones`) has ever needed to reject an
# anchor/alias, bound nesting depth, or reject a duplicate mapping key - all three are new here.
# `yaml.SafeLoader` already rejects unknown/custom tags on its own (any tag not in its own
# constructor table falls through to `SafeConstructor.construct_undefined`, which raises) - no
# extra code is needed for that specific rule.
# --------------------------------------------------------------------------------------------


class KubernetesEnvelopeLimitExceeded(ValueError):
    """§4.3: "YAML alias expansion is unsupported, custom tags are rejected, and parser nesting is
    bounded to 64 levels... Limit violations are REJECTED_UNSUPPORTED." All three - alias/anchor
    use, an unrecognized/custom tag, and nesting beyond `MAX_YAML_NESTING_DEPTH` - are this same
    "limit violation" bucket per that one sentence, distinct from `KubernetesEnvelopeMalformedError`
    below. Callers convert this into `K8S_LIMIT_EXCEEDED` (`IngestionResult.REJECTED_UNSUPPORTED`).
    """


class KubernetesEnvelopeMalformedError(ValueError):
    """§4.3: "...malformed inputs are REJECTED_INVALID" - the bucket for a structural defect that
    is not itself one of the three named "limit violations" above, most notably a duplicate mapping
    key (§4.2: "duplicate YAML/JSON keys are rejected", stated separately from §4.3's limit trio).
    Callers convert this into `K8S_SNAPSHOT_INVALID` or `K8S_SNAPSHOT_INCOMPLETE`
    (`IngestionResult.REJECTED_INVALID`), depending on whether the envelope or a resource file was
    being parsed.
    """


def _sanitize_validation_error(exc: ValidationError) -> str:
    """§5: "Diagnostics never dump rejected resource payloads." / §10: "sanitized reasons... expose
    no raw Secret/environment contents." Pydantic's own `str(ValidationError)` embeds each failing
    field's raw `input_value` - e.g. an unrecognized field's actual value, verbatim - which is
    exactly that leak (confirmed: an `extra_forbidden` error's `input` is the rejected field's own
    value, not just its name). Rebuilds a stable message from only the field path and error
    type/message, never `error["input"]`.
    """
    parts = []
    for error in exc.errors(include_url=False):
        location = ".".join(str(segment) for segment in error["loc"])
        parts.append(f"{location}: {error['msg']}" if location else error["msg"])
    return "; ".join(parts)


def _sanitize_yaml_error(exc: yaml.YAMLError) -> str:
    """Same leak, different shape: a `MarkedYAMLError`'s own `str()` embeds a literal source-line
    snippet via its `Mark.get_snippet()` (confirmed against a real PyYAML error) - e.g. an
    unsupported tag's actual value or a malformed line's raw content. Keeps only the problem
    description and line/column position, both safe metadata."""
    problem = getattr(exc, "problem", None) or exc.__class__.__name__
    mark = getattr(exc, "problem_mark", None)
    if mark is not None:
        return f"{problem} (line {mark.line + 1}, column {mark.column + 1})"
    return str(problem)


def _sanitize_parse_error(exc: Exception) -> str:
    """Single dispatch point for every parse-failure message this module builds, so no call site
    can forget and fall back to a leaky `str(exc)`. `KubernetesEnvelopeLimitExceeded`/
    `KubernetesEnvelopeMalformedError` are this module's own hand-written messages (already safe -
    never interpolate raw field/document content, only field paths, type names, and counts) and
    fall through to the plain `str(exc)` branch unchanged.
    """
    if isinstance(exc, ValidationError):
        return _sanitize_validation_error(exc)
    if isinstance(exc, yaml.YAMLError):
        return _sanitize_yaml_error(exc)
    return str(exc)


class _BoundedSafeLoader(yaml.SafeLoader):
    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._compose_depth = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        # I2 Draft 0.2 §4.3: "YAML alias expansion is unsupported." `compose_node` is the single
        # recursive entry point the Composer uses for every node (scalar, sequence, or mapping),
        # including alias resolution - checking here, before delegating, catches an alias
        # regardless of where it appears.
        if self.check_event(yaml.events.AliasEvent):
            raise KubernetesEnvelopeLimitExceeded("YAML aliases/anchors are not supported")
        self._compose_depth += 1
        try:
            if self._compose_depth > MAX_YAML_NESTING_DEPTH:
                raise KubernetesEnvelopeLimitExceeded(
                    f"YAML/JSON nesting exceeds the {MAX_YAML_NESTING_DEPTH}-level bound"
                )
            return super().compose_node(parent, index)
        finally:
            self._compose_depth -= 1

    def construct_mapping(self, node: Any, deep: bool = False) -> dict:
        # Duplicate-key rejection: by the time `construct_mapping` returns a plain dict, a
        # repeated key has already silently overwritten its earlier value - no downstream Pydantic
        # model could ever detect that a duplicate existed. `node.value` is the raw ordered
        # (key_node, value_node) pair list *before* that collapse happens.
        seen_keys: set[Any] = set()
        for key_node, _value_node in node.value:
            key = self.construct_object(key_node, deep=True)
            # YAML permits complex mapping keys (e.g. a sequence), which are unhashable - `key in
            # seen_keys` would otherwise raise a raw TypeError instead of a clean rejection.
            # PyYAML's own base `construct_mapping` (which `super()` below would eventually reach)
            # already guards this the same way, but only *after* this loop's own membership check
            # would already have crashed first.
            # Never echoes the key's own value in the raised message - a mapping key can carry
            # attacker-controlled document content just as readily as a value can.
            try:
                is_duplicate = key in seen_keys
            except TypeError as exc:
                raise KubernetesEnvelopeMalformedError("unhashable YAML mapping key") from exc
            if is_duplicate:
                raise KubernetesEnvelopeMalformedError("duplicate mapping key")
            seen_keys.add(key)
        return super().construct_mapping(node, deep=deep)


def load_bounded_yaml_documents(raw_bytes: bytes) -> list[Any]:
    """Loads every document in a YAML document stream (or the single object in a JSON file - JSON
    is a YAML subset, the same convention `app.ingestion.filesystem_discoverer` already relies on),
    hardened per §4.3. Raises `KubernetesEnvelopeLimitExceeded` or `KubernetesEnvelopeMalformedError`
    for a hardening violation; a genuine `yaml.YAMLError` (a syntax error unrelated to hardening,
    e.g. bad indentation) is left to propagate to the caller, which already handles it the same way
    every other YAML consumer in this codebase does.

    A custom/unrecognized YAML tag raises PyYAML's own `yaml.constructor.ConstructorError` -
    `SafeLoader` already rejects any tag it has no registered constructor for, with no extra code
    needed for that specific rule - re-raised here as `KubernetesEnvelopeLimitExceeded` so it joins
    the same "limit violation" bucket alias/nesting violations use, per §4.3's own single sentence
    naming all three together.
    """
    try:
        return list(yaml.load_all(raw_bytes, Loader=_BoundedSafeLoader))
    except yaml.constructor.ConstructorError as exc:
        raise KubernetesEnvelopeLimitExceeded(
            f"unsupported YAML tag: {_sanitize_yaml_error(exc)}"
        ) from exc


# --------------------------------------------------------------------------------------------
# Envelope shape (I2 Draft 0.2 §4.2)
# --------------------------------------------------------------------------------------------


class _StrictModel(BaseModel):
    """§4.2: "Unknown envelope fields... are rejected." Every envelope-shape model shares this."""

    model_config = {"extra": "forbid"}


class KubernetesSourceSnapshotMetadata(_StrictModel):
    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    captured_at: str = Field(min_length=1, alias="capturedAt")


class KubernetesSourceSnapshotSource(_StrictModel):
    configured_source_id: str = Field(min_length=1, alias="configuredSourceId")
    configured_scope_id: str = Field(min_length=1, alias="configuredScopeId")
    cluster_uid: str = Field(min_length=1, alias="clusterUid")
    cluster_identity_evidence_ref: str = Field(min_length=1, alias="clusterIdentityEvidenceRef")
    # I2 Draft 0.2 §4.1's two evidence modes. A plain string, not `KubernetesEvidenceMode`
    # (`app.canonical.infrastructure`), on purpose: that enum lives in the Canonical Model layer,
    # and this module has no dependency on it - the value is validated against the exact two legal
    # strings here, independently, without introducing a cross-layer import for a single check.
    mode: str

    @model_validator(mode="after")
    def _check_mode(self) -> KubernetesSourceSnapshotSource:
        if self.mode not in ("DECLARED_MANIFEST", "CAPTURED_RESOURCE"):
            raise ValueError("source.mode must be DECLARED_MANIFEST or CAPTURED_RESOURCE")
        return self


class KubernetesSourceSnapshotScope(_StrictModel):
    namespaces: list[str]
    resource_types: list[str] = Field(alias="resourceTypes")

    @model_validator(mode="after")
    def _check_namespaces_and_resource_types(self) -> KubernetesSourceSnapshotScope:
        # §4.2: "Namespace lists are non-empty, sorted, duplicate-free explicit names: no wildcard
        # or implicit default namespace." Rejects rather than normalizes - an adapter emitting an
        # unsorted or duplicated list has a real determinism bug (the same discipline
        # `app.canonical.infrastructure._check_evidence_refs` already applies to evidence_refs).
        if not self.namespaces:
            raise ValueError("scope.namespaces must be non-empty")
        if any(not ns for ns in self.namespaces):
            raise ValueError("scope.namespaces must not contain empty names")
        if "*" in self.namespaces:
            raise ValueError("scope.namespaces must not contain a wildcard")
        if len(set(self.namespaces)) != len(self.namespaces):
            raise ValueError("scope.namespaces must be duplicate-free")
        if list(self.namespaces) != sorted(self.namespaces):
            raise ValueError("scope.namespaces must be sorted")
        # §4.2: "The resourceTypes list is the exact eight-entry set above." Set equality, not
        # list-order equality - the spec's own text says "set", and its YAML example shows only one
        # of several plausible orderings (an implementation decision, flagged in the plan/PR).
        # The expected set itself is a frozen, public constant, safe to echo; the submitted set is
        # not - it isn't included in the message (see `_sanitize_validation_error`'s own docstring).
        if set(self.resource_types) != EXPECTED_RESOURCE_TYPES:
            raise ValueError(
                f"scope.resourceTypes must be exactly the frozen eight-entry set: "
                f"{sorted(EXPECTED_RESOURCE_TYPES)!r}"
            )
        if len(self.resource_types) != len(EXPECTED_RESOURCE_TYPES):
            raise ValueError("scope.resourceTypes must not contain duplicates")
        return self


class KubernetesSourceSnapshotCompleteness(_StrictModel):
    # §4.2: "completeness: status: COMPLETE". Treated as an open string, not a rigid enum - the
    # spec never enumerates legal alternatives to "COMPLETE"; anything else is K8S_SNAPSHOT_INCOMPLETE
    # at the caller's own classification step, not a shape-validation failure here.
    status: str = Field(min_length=1)
    authority_ref: str = Field(min_length=1, alias="authorityRef")
    expected_prior_inventory_revision: str | None = Field(alias="expectedPriorInventoryRevision")

    @model_validator(mode="after")
    def _check_expected_prior_inventory_revision(self) -> KubernetesSourceSnapshotCompleteness:
        # §4.2: "IDs and attribution fields are non-empty strings" - `expectedPriorInventoryRevision`
        # is explicitly the one field allowed to be null (§4.2: "null only for a first import"), so
        # it needs its own non-empty-when-present check rather than a blanket Field(min_length=1).
        if self.expected_prior_inventory_revision is not None and not (
            self.expected_prior_inventory_revision.strip()
        ):
            raise ValueError(
                "completeness.expectedPriorInventoryRevision must not be an empty string"
            )
        return self


def _normalize_relative_file_path(raw_path: str) -> str:
    """§4.2: "File paths are unique normalized relative POSIX paths." This *requires* the producer
    to already supply a canonical path - it does not resolve one on the producer's behalf. Unlike
    `$ref` resolution elsewhere in this codebase (which legitimately collapses relative navigation
    such as `a/../b.yaml` while resolving one document against another), silently accepting and
    collapsing a non-normalized `files[].path` here would let two differently-spelled envelope
    entries alias the same underlying file, undermining the spec's own "unique...paths" requirement
    as stated over the *supplied* list. A backslash, an absolute leading `/`, or any `.`/`..`/empty
    path segment (the last covers a leading/trailing/doubled `/`) means the path was not already
    normalized, and is rejected outright rather than silently rewritten.
    """
    if not raw_path or "\\" in raw_path:
        raise ValueError("files[].path must be a normalized relative POSIX path")
    if raw_path.startswith("/"):
        raise ValueError("files[].path must not be an absolute path")
    if any(segment in ("", ".", "..") for segment in raw_path.split("/")):
        raise ValueError("files[].path must be a normalized relative POSIX path with no traversal")
    return raw_path


class KubernetesSourceSnapshotFileEntry(_StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_path_and_digest(self) -> KubernetesSourceSnapshotFileEntry:
        _normalize_relative_file_path(self.path)
        # §4.2: "lowercase-sha256-of-exact-file-bytes" - a hex digest is always lowercase hex, a
        # cheap structural check independent of verifying it against real file bytes later.
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("files[].sha256 must be a lowercase 64-character hex digest")
        return self


class KubernetesSourceSnapshot(_StrictModel):
    """I2 Draft 0.2 §4.2's exact envelope shape. `api_version`/`kind` are checked against their
    exact required literal values here (not just non-empty strings) - a snapshot with any other
    `kind` isn't a Kubernetes source snapshot at all, and `supports()`-style content-sniffing (a
    later slice's job) needs `kind` to be an exact, reliable discriminator, mirroring how
    `_is_identity_bindings_document` sniffs `document.get("kind") == "ArchitectureIdentityBindings"`
    elsewhere in this codebase.
    """

    api_version: str = Field(alias="apiVersion")
    kind: str
    metadata: KubernetesSourceSnapshotMetadata
    source: KubernetesSourceSnapshotSource
    scope: KubernetesSourceSnapshotScope
    completeness: KubernetesSourceSnapshotCompleteness
    files: list[KubernetesSourceSnapshotFileEntry]

    @model_validator(mode="after")
    def _check_api_version_kind_and_files(self) -> KubernetesSourceSnapshot:
        if self.api_version != "aip.dev/v1":
            raise ValueError("apiVersion must be 'aip.dev/v1'")
        if self.kind != "KubernetesSourceSnapshot":
            raise ValueError("kind must be 'KubernetesSourceSnapshot'")
        # §4.2: "File paths are unique normalized relative POSIX paths." A missing file list is
        # legal only via an explicit empty list (§4.3: "A bundle with no resources can be complete
        # only through an explicit empty file list") - `files: []` satisfies that; `files` being
        # absent entirely is already rejected by Pydantic's own required-field check.
        normalized_paths = [_normalize_relative_file_path(f.path) for f in self.files]
        if len(set(normalized_paths)) != len(normalized_paths):
            raise ValueError("files[].path must be unique")
        return self


def parse_kubernetes_envelope(raw_bytes: bytes) -> KubernetesSourceSnapshot:
    """Parses and shape-validates one envelope document. Raises `KubernetesEnvelopeLimitExceeded`,
    `KubernetesEnvelopeMalformedError`, `yaml.YAMLError`, or `pydantic.ValidationError` - all four
    are caught by `validate_kubernetes_snapshot`, which converts them into the appropriate
    diagnostic; this function itself never emits a diagnostic or `IngestionResult`, so it stays
    independently testable and reusable without pulling in `app.sources.model`'s result taxonomy.
    An envelope with more than one document, or a non-mapping root, is malformed - not a limit
    violation - matching §4.3's "malformed inputs are REJECTED_INVALID" bucket.
    """
    documents = load_bounded_yaml_documents(raw_bytes)
    if len(documents) != 1:
        raise KubernetesEnvelopeMalformedError(
            f"envelope must be exactly one YAML/JSON document, got {len(documents)}"
        )
    (document,) = documents
    if not isinstance(document, dict):
        raise KubernetesEnvelopeMalformedError("envelope root must be a mapping")
    return KubernetesSourceSnapshot.model_validate(document)


# --------------------------------------------------------------------------------------------
# Bounded sanitized loading (I2 Draft 0.2 §4.3)
# --------------------------------------------------------------------------------------------


def _is_list_container(document: dict) -> bool:
    """§4.3 authorizes only `v1/List` as a container - `kind == "List"` alone is not enough
    (a hypothetical `custom.io/v2` kind:List object is not this container, and treating it as one
    would silently flatten/reinterpret an object this slice has no authority to reclassify).
    A `kind: List` document with any other `apiVersion` instead falls through as an ordinary
    (opaque, at this layer) resource object - admissibility of *that* is a later slice's job."""
    return document.get("apiVersion") == "v1" and document.get("kind") == "List"


def _expand_resource_documents(
    documents: list[Any], *, source_pointer: str
) -> list[KubernetesResourceEntry]:
    """§4.3: "v1/List is a container whose items are validated individually, not an architecture
    entity. Nested List containers are rejected." Flattens each resource file's own top-level
    document list so every caller downstream sees a flat resource-object list, with each List's own
    wrapper discarded (never itself counted as a resource object).

    "Nested List containers are rejected" is classified as a limit violation, not a malformed input:
    it appears within §4.3's own "Limits:" paragraph, whose closing sentence ("Limit violations are
    REJECTED_UNSUPPORTED; malformed inputs are REJECTED_INVALID") reads as governing the whole
    paragraph - file-count/byte-size/object-count bounds, List nesting, and the alias/tag/nesting-
    depth trio together - not only the sentence immediately preceding it.
    """
    expanded: list[KubernetesResourceEntry] = []
    for document in documents:
        if not isinstance(document, dict):
            raise KubernetesEnvelopeMalformedError(
                f"{source_pointer}: each document must be a mapping, got {type(document).__name__}"
            )
        if _is_list_container(document):
            items = document.get("items")
            if not isinstance(items, list):
                raise KubernetesEnvelopeMalformedError(
                    f"{source_pointer}: List.items must be a list"
                )
            for item in items:
                if not isinstance(item, dict):
                    raise KubernetesEnvelopeMalformedError(
                        f"{source_pointer}: List item must be a mapping"
                    )
                if _is_list_container(item):
                    raise KubernetesEnvelopeLimitExceeded(
                        f"{source_pointer}: nested List containers are rejected"
                    )
                expanded.append(
                    KubernetesResourceEntry(source_pointer=source_pointer, document=item)
                )
        else:
            expanded.append(
                KubernetesResourceEntry(source_pointer=source_pointer, document=document)
            )
    return expanded


@dataclass(frozen=True)
class KubernetesSnapshotValidationResult:
    """The one thing a later slice's `KubernetesSourceDiscoverer` needs from this module.
    `envelope`/`resources` are `None`/`()` whenever `result` is not `ACCEPTED` - a rejected snapshot
    carries no partial data forward, matching this codebase's "a source either fully succeeds or is
    entirely discarded" discipline. `result` is only ever `ACCEPTED`, `REJECTED_INVALID`, or
    `REJECTED_UNSUPPORTED` at this layer - `ACCEPTED_WITH_LIMITATIONS`/`REJECTED_CONFLICT` both
    depend on resource-projection/owner-chain/cross-source logic later slices own.
    """

    result: IngestionResult
    envelope: KubernetesSourceSnapshot | None
    resources: tuple[KubernetesResourceEntry, ...]
    envelope_content_sha256: str | None
    diagnostics: tuple[IngestionDiagnostic, ...]


def _rejected(
    *, result: IngestionResult, code: DiagnosticCode, message: str, source_pointer: str
) -> KubernetesSnapshotValidationResult:
    return KubernetesSnapshotValidationResult(
        result=result,
        envelope=None,
        resources=(),
        envelope_content_sha256=None,
        diagnostics=(
            IngestionDiagnostic(code=code, message=message, source_pointer=source_pointer),
        ),
    )


def _resolve_contained_file(root: Path, root_real: Path, relative_path: str) -> Path | None:
    """Mirrors `app.sources.reference_resolution._load_and_validate_document`'s exact containment
    check - resolve symlinks to the real filesystem path, then require that real path be a regular
    file inside the approved root's own real path (`is_relative_to`, not a string-prefix check,
    which is bypassable). Returns `None` for "doesn't exist/isn't a file" or "escapes the root" -
    the caller distinguishes those two outcomes itself, since they map to different diagnostics here
    (missing/incomplete vs. a genuine security violation).
    """
    candidate = root / relative_path
    try:
        real_path = candidate.resolve(strict=False)
        is_contained_file = real_path.is_relative_to(root_real) and real_path.is_file()
    except RuntimeError:
        # A circular symlink chain - Path.resolve() raises RuntimeError for this specific case
        # (not OSError), and it is no more a valid, resolvable target than a missing one.
        return None
    except OSError:
        # A permission error resolving or stat()-ing the path (e.g. a non-traversable intermediate
        # directory) - is_file() does not uniformly swallow this the way it does a plain "doesn't
        # exist", so it must be caught explicitly here too.
        return None
    if not is_contained_file:
        return None
    return real_path


def _read_at_most(path: Path, limit: int) -> bytes | None:
    """Reads at most `limit + 1` bytes from `path`, returning `None` (without ever holding more
    than `limit + 1` bytes of it in memory) if the file turns out to contain more than `limit`
    bytes. A prior `stat()` followed by an unbounded `read_bytes()` is a TOCTOU race - the file can
    grow between those two calls, so the size actually read is never guaranteed to match what was
    measured. Reading with an explicit cap removes the race entirely: the bound is enforced by the
    read itself, not by trusting a separate measurement taken beforehand.
    """
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        return None
    return data


def validate_kubernetes_snapshot(
    *, root: Path, envelope_relative_path: str
) -> KubernetesSnapshotValidationResult:
    """The one entry point a later slice's `KubernetesSourceDiscoverer` needs: reads and validates
    the envelope at `root/envelope_relative_path`, then bounds-checks and loads every file it lists,
    returning a fully validated, flattened resource-object list on success or the single diagnostic
    explaining why not. Never raises for a source/construct-level problem - every failure mode below
    is converted to a `KubernetesSnapshotValidationResult`, mirroring `AdapterOutcome`'s own
    "adapters MUST NOT raise" discipline (I1 spec §10) even though this runs before any adapter.
    """
    try:
        root_real = root.resolve(strict=False)
    except (RuntimeError, OSError):
        # RuntimeError: a circular symlink chain in the configured root itself. OSError: a
        # permission error resolving it (e.g. a non-traversable intermediate directory) - see
        # _resolve_contained_file's own handling of the same two cases for a listed file.
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message="configured root could not be resolved",
            source_pointer=envelope_relative_path,
        )
    envelope_path = _resolve_contained_file(root, root_real, envelope_relative_path)
    if envelope_path is None:
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message="envelope file is missing or escapes the configured root",
            source_pointer=envelope_relative_path,
        )

    # A bounded read, not stat()-then-read_bytes(): the latter is a TOCTOU race (the file can grow
    # between the two calls), so the byte-total bound is enforced by the read itself. A permission
    # error or other I/O failure while opening/reading a file this codebase already confirmed
    # exists (via _resolve_contained_file's own is_file() check) must not raise past this function's
    # own "never raises for a source/construct-level problem" contract - it is exactly the kind of
    # acquisition failure §10's REJECTED_INVALID/PARTIAL outcome for a required file exists for.
    try:
        envelope_bytes = _read_at_most(envelope_path, MAX_TOTAL_BYTES)
    except OSError:
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message="envelope file could not be read",
            source_pointer=envelope_relative_path,
        )
    if envelope_bytes is None:
        return _rejected(
            result=IngestionResult.REJECTED_UNSUPPORTED,
            code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
            message=f"total input bytes exceeds the {MAX_TOTAL_BYTES}-byte limit",
            source_pointer=envelope_relative_path,
        )

    try:
        envelope = parse_kubernetes_envelope(envelope_bytes)
    except KubernetesEnvelopeLimitExceeded as exc:
        return _rejected(
            result=IngestionResult.REJECTED_UNSUPPORTED,
            code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
            message=_sanitize_parse_error(exc),
            source_pointer=envelope_relative_path,
        )
    except (KubernetesEnvelopeMalformedError, yaml.YAMLError, ValidationError) as exc:
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INVALID,
            message=_sanitize_parse_error(exc),
            source_pointer=envelope_relative_path,
        )

    if envelope.completeness.status != "COMPLETE":
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message="completeness.status is not COMPLETE",
            source_pointer=envelope_relative_path,
        )

    if len(envelope.files) > MAX_FILE_COUNT:
        return _rejected(
            result=IngestionResult.REJECTED_UNSUPPORTED,
            code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
            message=f"{len(envelope.files)} files exceeds the {MAX_FILE_COUNT}-file limit",
            source_pointer=envelope_relative_path,
        )

    total_bytes = len(envelope_bytes)
    resources: list[KubernetesResourceEntry] = []
    for file_entry in envelope.files:
        normalized_path = _normalize_relative_file_path(file_entry.path)
        resolved = _resolve_contained_file(root, root_real, normalized_path)
        if resolved is None:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message="listed file is missing or escapes the configured root",
                source_pointer=normalized_path,
            )

        # Bounded by the *remaining* budget, not stat()-then-read_bytes() - see _read_at_most's own
        # docstring for why a separate size measurement before the read is a TOCTOU race. A
        # permission error or other I/O failure is a required-file acquisition failure (§10), not a
        # limit violation - it must not raise past this function's "never raises" contract.
        try:
            file_bytes = _read_at_most(resolved, MAX_TOTAL_BYTES - total_bytes)
        except OSError:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message="listed file could not be read",
                source_pointer=normalized_path,
            )
        if file_bytes is None:
            return _rejected(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
                message=f"total input bytes exceeds the {MAX_TOTAL_BYTES}-byte limit",
                source_pointer=normalized_path,
            )
        total_bytes += len(file_bytes)
        if sha256_hex(file_bytes) != file_entry.sha256:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message="file digest does not match the declared sha256",
                source_pointer=normalized_path,
            )

        try:
            documents = load_bounded_yaml_documents(file_bytes)
            resources.extend(_expand_resource_documents(documents, source_pointer=normalized_path))
        except KubernetesEnvelopeLimitExceeded as exc:
            return _rejected(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
                message=_sanitize_parse_error(exc),
                source_pointer=normalized_path,
            )
        except (KubernetesEnvelopeMalformedError, yaml.YAMLError) as exc:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message=f"file cannot be parsed: {_sanitize_parse_error(exc)}",
                source_pointer=normalized_path,
            )

        if len(resources) > MAX_RESOURCE_OBJECT_COUNT:
            return _rejected(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
                message=f"resource object count exceeds the {MAX_RESOURCE_OBJECT_COUNT} limit",
                source_pointer=normalized_path,
            )

    return KubernetesSnapshotValidationResult(
        result=IngestionResult.ACCEPTED,
        envelope=envelope,
        resources=tuple(resources),
        envelope_content_sha256=sha256_hex(envelope_bytes),
        diagnostics=(),
    )
