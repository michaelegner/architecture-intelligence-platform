from pathlib import Path

import yaml

from app.sources.identity import (
    content_sha256,
    dependency_closure_digest,
    discovery_scope_id,
    normalize_relative_posix_path,
    scope_definition_digest,
    source_instance_id,
)
from app.sources.model import (
    DiagnosticCode,
    FilesystemSourceConfig,
    IngestionDiagnostic,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.reference_resolution import (
    ReferenceResolutionError,
    new_resolution_cache,
    normalize_non_json_scalars,
    walk_transitive_closure,
)
from app.sources.registry import DiscoveryOutcome

# Enumeration convenience only (ADR 0009: "keeping today's openapi.yaml/asyncapi.yaml/
# architecture.yaml conventions intact for existing users") - NOT a dispatch table. Which adapter
# actually claims a discovered document is decided by SourceAdapterRegistry.adapter_for(), which
# inspects parsed content, never the filename.
CANDIDATE_FILENAMES = (
    "openapi.yaml",
    "openapi.yml",
    "openapi.json",
    "asyncapi.yaml",
    "asyncapi.yml",
    "asyncapi.json",
    "architecture.yaml",
    # I1 spec §4.2's new ArchitectureIdentityBindings artifact - a distinct filename from the
    # existing architecture.yaml CALLS-relation manifest, since both may coexist per service.
    "architecture-identity-bindings.yaml",
    "architecture-identity-bindings.yml",
)

_DIALECT_KEYS = ("openapi", "asyncapi", "apiVersion")


def _document_dialect_version(document: dict) -> str | None:
    for key in _DIALECT_KEYS:
        value = document.get(key)
        if isinstance(value, str):
            return value
    return None


def _best_effort_closure_digest(
    *, source_root: Path, relative_path: str, document: dict, raw_bytes: bytes
) -> str | None:
    """Best-effort, non-fatal closure walk at discovery time - purely to compute the provenance
    digest up front (co-located with `content_sha256`). Any failure here (a bad ref, a limit
    exceeded, a cycle) is deliberately swallowed: the adapter's own resolution during `map()`, using
    the identical shared primitives, is the authoritative pass that raises the real `REJECTED_*` +
    diagnostic. Two independent walks disagreeing about what failed would be worse than one of them
    staying silent.
    """
    cache = new_resolution_cache(
        source_root,
        root_relative_path=relative_path,
        root_document=document,
        root_bytes=raw_bytes,
    )
    try:
        entries = walk_transitive_closure(document, root_relative_path=relative_path, cache=cache)
    except ReferenceResolutionError:
        return None
    return dependency_closure_digest(entries)


class FilesystemSourceDiscoverer:
    """I1 spec §7's filesystem source discoverer - one instance per configured
    `FilesystemSourceConfig`, replacing `app.ingestion.scanner`. Preserves today's
    one-directory-per-service layout and filename conventions; adapter dispatch itself moved to
    `SourceAdapterRegistry.adapter_for()` (content-based, not filename-based).
    """

    source_kind = SourceKind.FILESYSTEM

    def __init__(self, config: FilesystemSourceConfig):
        self._config = config
        self.discoverer_identity = "filesystem-discoverer@1"

    def discover(self) -> DiscoveryOutcome:
        root = self._config.root
        if not root.is_dir():
            return DiscoveryOutcome(
                loaded_sources=(),
                enumeration_complete=False,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.SOURCE_ROOT_UNAVAILABLE,
                        message=f"configured source root does not exist or is not a directory: {root}",
                    ),
                ),
            )

        scope_id = discovery_scope_id(
            configured_scope_id=self._config.resolved_scope_id,
            stable_target_identity=self._config.resolved_stable_target_identity,
        )
        scope_digest = scope_definition_digest(
            discovery_scope_id=scope_id,
            normalized_roots=[normalize_relative_posix_path(str(root))],
            filters=[],
            inclusion_rules=[],
        )

        loaded_sources: list[LoadedSource] = []
        diagnostics: list[IngestionDiagnostic] = []
        enumeration_complete = True

        for service_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            for filename in CANDIDATE_FILENAMES:
                candidate = service_dir / filename
                if not candidate.is_file():
                    continue

                raw_bytes = candidate.read_bytes()
                try:
                    document = yaml.safe_load(raw_bytes)
                except yaml.YAMLError as exc:
                    # A parse failure means this candidate's presence/absence can never be trusted -
                    # unlike a file that legitimately doesn't exist, we saw bytes here but couldn't
                    # understand them. Treating this as "cleanly absent" would let a single corrupted
                    # or mid-edit file authorize deleting that source's previously-committed facts
                    # (I1 spec §6's own FAILED trigger list: "truncation, pagination error" - this is
                    # the filesystem-discoverer analog). enumeration_complete=False forces FAILED,
                    # never COMPLETE, for the whole run.
                    enumeration_complete = False
                    diagnostics.append(
                        IngestionDiagnostic(
                            code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                            message=f"{candidate}: {exc}",
                            source_pointer=str(candidate),
                        )
                    )
                    continue
                if not isinstance(document, dict):
                    enumeration_complete = False
                    diagnostics.append(
                        IngestionDiagnostic(
                            code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                            message=f"{candidate}: root document is not a mapping",
                            source_pointer=str(candidate),
                        )
                    )
                    continue
                document = normalize_non_json_scalars(document)

                relative_path = normalize_relative_posix_path(str(candidate.relative_to(root)))
                instance_id = source_instance_id(
                    configured_source_id=self._config.id,
                    source_kind=SourceKind.FILESYSTEM,
                    normalized_root_document_path=relative_path,
                )

                # Adapter-specific fields (semantic_input_digest, mapping_context_digest,
                # adapter_identity, mapping_rule_id, mapping_rule_version) are not yet knowable at
                # discovery time: semantic_input_digest depends on the claiming adapter's own
                # normalized projection (I1 spec §5.3 - "an adapter's job"), and adapter/mapping-rule
                # identity depend on which adapter the registry matches. The orchestrator enriches
                # `adapter_identity`/`mapping_rule_id`/`mapping_rule_version` once an adapter is
                # matched; the authoritative `semantic_input_digest` is reported on `AdapterOutcome`,
                # not re-derived here.
                descriptor = SourceDescriptor(
                    source_instance_id=instance_id,
                    source_kind=SourceKind.FILESYSTEM,
                    locator=str(candidate),
                    discovery_scope_id=scope_id,
                    scope_definition_digest=scope_digest,
                    content_sha256=content_sha256(raw_bytes),
                    dependency_closure_digest=_best_effort_closure_digest(
                        source_root=root,
                        relative_path=relative_path,
                        document=document,
                        raw_bytes=raw_bytes,
                    ),
                    semantic_input_digest="",
                    mapping_context_digest="",
                    document_dialect_version=_document_dialect_version(document),
                    adapter_identity="",
                    mapping_rule_id="",
                    mapping_rule_version="",
                )
                loaded_sources.append(
                    LoadedSource(descriptor=descriptor, document=document, source_root=str(root))
                )

        return DiscoveryOutcome(
            loaded_sources=tuple(loaded_sources),
            enumeration_complete=enumeration_complete,
            diagnostics=tuple(diagnostics),
            discovery_scope_id=scope_id,
            scope_definition_digest=scope_digest,
        )
