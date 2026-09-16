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
from app.sources.identity import normalize_relative_posix_path
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult
from app.sources.reference_resolution import normalize_dot_segments

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
            try:
                is_duplicate = key in seen_keys
            except TypeError as exc:
                raise KubernetesEnvelopeMalformedError(
                    f"unhashable YAML mapping key: {key!r}"
                ) from exc
            if is_duplicate:
                raise KubernetesEnvelopeMalformedError(f"duplicate mapping key: {key!r}")
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
        raise KubernetesEnvelopeLimitExceeded(f"unsupported YAML tag: {exc}") from exc


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
            raise ValueError(
                f"source.mode must be DECLARED_MANIFEST or CAPTURED_RESOURCE, got {self.mode!r}"
            )
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
            raise ValueError(f"scope.namespaces must be duplicate-free: {self.namespaces!r}")
        if list(self.namespaces) != sorted(self.namespaces):
            raise ValueError(f"scope.namespaces must be sorted: {self.namespaces!r}")
        # §4.2: "The resourceTypes list is the exact eight-entry set above." Set equality, not
        # list-order equality - the spec's own text says "set", and its YAML example shows only one
        # of several plausible orderings (an implementation decision, flagged in the plan/PR).
        if set(self.resource_types) != EXPECTED_RESOURCE_TYPES:
            raise ValueError(
                "scope.resourceTypes must be exactly the frozen eight-entry set: "
                f"{sorted(EXPECTED_RESOURCE_TYPES)!r}, got {sorted(set(self.resource_types))!r}"
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
    """Fully normalizes a `files[].path` entry - used for both the traversal-safety check and the
    "unique paths" check, so both agree on what counts as "the same file". Absolute-path rejection
    happens *before* dot-segment normalization (which would otherwise silently strip a leading "/"
    and mask that the input was absolute at all), mirroring
    `app.sources.reference_resolution.reject_absolute_decoded_path`'s own "ordering is itself
    security-relevant" reasoning. Collapsing dot segments (via the same
    `normalize_dot_segments` this codebase's `$ref` resolution already uses) before the traversal
    check matters: a bare `normalize_relative_posix_path` never resolves `..` segments, so
    `"a/../../etc/passwd"` would otherwise pass a naive `startswith("../")` check (it starts with
    `"a/"`) despite escaping upward once collapsed, and `"a/../b.yaml"` would be wrongly treated as
    distinct from `"b.yaml"` by the uniqueness check.
    """
    posix_path = normalize_relative_posix_path(raw_path)
    if posix_path.startswith("/"):
        raise ValueError(f"files[].path must not be an absolute path: {raw_path!r}")
    normalized = normalize_dot_segments(posix_path)
    if normalized.startswith("../") or normalized == "..":
        raise ValueError(f"files[].path must be a relative path with no traversal: {raw_path!r}")
    return normalized


class KubernetesSourceSnapshotFileEntry(_StrictModel):
    path: str = Field(min_length=1)
    sha256: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_path_and_digest(self) -> KubernetesSourceSnapshotFileEntry:
        _normalize_relative_file_path(self.path)
        # §4.2: "lowercase-sha256-of-exact-file-bytes" - a hex digest is always lowercase hex, a
        # cheap structural check independent of verifying it against real file bytes later.
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError(
                f"files[].sha256 must be a lowercase 64-character hex digest: {self.sha256!r}"
            )
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
            raise ValueError(f"apiVersion must be 'aip.dev/v1', got {self.api_version!r}")
        if self.kind != "KubernetesSourceSnapshot":
            raise ValueError(f"kind must be 'KubernetesSourceSnapshot', got {self.kind!r}")
        # §4.2: "File paths are unique normalized relative POSIX paths." A missing file list is
        # legal only via an explicit empty list (§4.3: "A bundle with no resources can be complete
        # only through an explicit empty file list") - `files: []` satisfies that; `files` being
        # absent entirely is already rejected by Pydantic's own required-field check.
        normalized_paths = [_normalize_relative_file_path(f.path) for f in self.files]
        if len(set(normalized_paths)) != len(normalized_paths):
            raise ValueError(f"files[].path must be unique: {normalized_paths!r}")
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


def _expand_resource_documents(documents: list[Any], *, source_pointer: str) -> list[dict]:
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
    expanded: list[dict] = []
    for document in documents:
        if not isinstance(document, dict):
            raise KubernetesEnvelopeMalformedError(
                f"{source_pointer}: each document must be a mapping, got {type(document).__name__}"
            )
        if document.get("kind") == "List":
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
                if item.get("kind") == "List":
                    raise KubernetesEnvelopeLimitExceeded(
                        f"{source_pointer}: nested List containers are rejected"
                    )
                expanded.append(item)
        else:
            expanded.append(document)
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
    resources: tuple[dict, ...]
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
    real_path = candidate.resolve(strict=False)
    if not real_path.is_relative_to(root_real) or not real_path.is_file():
        return None
    return real_path


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
    root_real = root.resolve(strict=False)
    envelope_path = _resolve_contained_file(root, root_real, envelope_relative_path)
    if envelope_path is None:
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message=f"envelope file is missing or escapes the configured root: {envelope_relative_path!r}",
            source_pointer=envelope_relative_path,
        )

    envelope_bytes = envelope_path.read_bytes()
    try:
        envelope = parse_kubernetes_envelope(envelope_bytes)
    except KubernetesEnvelopeLimitExceeded as exc:
        return _rejected(
            result=IngestionResult.REJECTED_UNSUPPORTED,
            code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
            message=str(exc),
            source_pointer=envelope_relative_path,
        )
    except (KubernetesEnvelopeMalformedError, yaml.YAMLError, ValidationError) as exc:
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INVALID,
            message=str(exc),
            source_pointer=envelope_relative_path,
        )

    if envelope.completeness.status != "COMPLETE":
        return _rejected(
            result=IngestionResult.REJECTED_INVALID,
            code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
            message=f"completeness.status is not COMPLETE: {envelope.completeness.status!r}",
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
    if total_bytes > MAX_TOTAL_BYTES:
        # The envelope alone can exceed the bound with an empty (or short) files list, in which
        # case the loop below never runs at all - this check must not live only inside that loop.
        return _rejected(
            result=IngestionResult.REJECTED_UNSUPPORTED,
            code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
            message=f"total input bytes exceeds the {MAX_TOTAL_BYTES}-byte limit",
            source_pointer=envelope_relative_path,
        )

    resources: list[dict] = []
    for file_entry in envelope.files:
        normalized_path = _normalize_relative_file_path(file_entry.path)
        resolved = _resolve_contained_file(root, root_real, normalized_path)
        if resolved is None:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message=f"listed file is missing or escapes the configured root: {file_entry.path!r}",
                source_pointer=normalized_path,
            )

        file_bytes = resolved.read_bytes()
        total_bytes += len(file_bytes)
        if total_bytes > MAX_TOTAL_BYTES:
            return _rejected(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
                message=f"total input bytes exceeds the {MAX_TOTAL_BYTES}-byte limit",
                source_pointer=normalized_path,
            )
        if sha256_hex(file_bytes) != file_entry.sha256:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message=f"file digest does not match the declared sha256: {file_entry.path!r}",
                source_pointer=normalized_path,
            )

        try:
            documents = load_bounded_yaml_documents(file_bytes)
            resources.extend(_expand_resource_documents(documents, source_pointer=normalized_path))
        except KubernetesEnvelopeLimitExceeded as exc:
            return _rejected(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                code=DiagnosticCode.K8S_LIMIT_EXCEEDED,
                message=str(exc),
                source_pointer=normalized_path,
            )
        except (KubernetesEnvelopeMalformedError, yaml.YAMLError) as exc:
            return _rejected(
                result=IngestionResult.REJECTED_INVALID,
                code=DiagnosticCode.K8S_SNAPSHOT_INCOMPLETE,
                message=f"file cannot be parsed: {file_entry.path!r}: {exc}",
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
