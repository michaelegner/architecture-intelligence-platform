import yaml

from app.sources.identity import (
    EMPTY_CLOSURE_DIGEST,
    content_sha256,
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
)

_DIALECT_KEYS = ("openapi", "asyncapi", "apiVersion")


def _document_dialect_version(document: dict) -> str | None:
    for key in _DIALECT_KEYS:
        value = document.get(key)
        if isinstance(value, str):
            return value
    return None


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

        for service_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            for filename in CANDIDATE_FILENAMES:
                candidate = service_dir / filename
                if not candidate.is_file():
                    continue

                raw_bytes = candidate.read_bytes()
                try:
                    document = yaml.safe_load(raw_bytes)
                except yaml.YAMLError as exc:
                    diagnostics.append(
                        IngestionDiagnostic(
                            code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                            message=f"{candidate}: {exc}",
                            source_pointer=str(candidate),
                        )
                    )
                    continue
                if not isinstance(document, dict):
                    diagnostics.append(
                        IngestionDiagnostic(
                            code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                            message=f"{candidate}: root document is not a mapping",
                            source_pointer=str(candidate),
                        )
                    )
                    continue

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
                    dependency_closure_digest=EMPTY_CLOSURE_DIGEST,
                    semantic_input_digest="",
                    mapping_context_digest="",
                    document_dialect_version=_document_dialect_version(document),
                    adapter_identity="",
                    mapping_rule_id="",
                    mapping_rule_version="",
                )
                loaded_sources.append(LoadedSource(descriptor=descriptor, document=document))

        return DiscoveryOutcome(
            loaded_sources=tuple(loaded_sources),
            enumeration_complete=True,
            diagnostics=tuple(diagnostics),
        )
