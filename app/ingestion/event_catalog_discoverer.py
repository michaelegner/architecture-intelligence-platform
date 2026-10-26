"""v0.8 I2a: the EventCatalog source discoverer (I1 §5.5, I2 §2). One registration is one generated
catalog plus its event -> Topic lookup. It mirrors `KafkaServiceMappingSourceDiscoverer`: discovery
needs only the registered files, and the source identity needs only configured values, so a missing
or invalid catalog still yields an identified source that the adapter rejects with the right
per-source result, and the run commits nothing. Every diagnostic message is fixed text.
"""

import dataclasses
import hashlib
import json

from app.sources.event_catalog_contract import DUPLICATE_SOURCE, EventCatalogProblem
from app.sources.event_catalog_loader import RejectedEventCatalog, load_event_catalog
from app.sources.identity import (
    discovery_scope_id,
    event_catalog_source_instance_id,
    normalize_relative_posix_path,
    scope_definition_digest,
)
from app.sources.model import (
    DiagnosticCode,
    EventCatalogSourceConfig,
    IngestionDiagnostic,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import DiscoveryOutcome

_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()
DECLARATIONS_KEY = "declarations"
CONFIGURED_SOURCE_ID_KEY = "configured_source_id"
ENVIRONMENT_KEY = "environment"


class EventCatalogSourceDiscoverer:
    source_kind = SourceKind.EVENT_CATALOG

    def __init__(self, config: EventCatalogSourceConfig, *, duplicate_registration: bool = False):
        self._config = config
        self._duplicate = duplicate_registration
        self.discoverer_identity = "event-catalog-discoverer@1"

    def discover(self) -> DiscoveryOutcome:
        config = self._config
        scope_id = discovery_scope_id(
            configured_scope_id=config.id,
            stable_target_identity=config.stable_target_identity,
        )
        scope_digest = scope_definition_digest(
            discovery_scope_id=scope_id,
            normalized_roots=[normalize_relative_posix_path(str(config.root))],
            filters=[],
            inclusion_rules=[],
        )
        if not config.root.is_dir():
            return DiscoveryOutcome(
                loaded_sources=(),
                enumeration_complete=False,
                diagnostics=(
                    IngestionDiagnostic(
                        code=DiagnosticCode.SOURCE_ROOT_UNAVAILABLE,
                        message="configured source root does not exist or is not a directory",
                        source_pointer=str(config.root),
                    ),
                ),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
            )

        def loaded(
            *,
            document: dict,
            diagnostics: list[IngestionDiagnostic],
            content_sha256: str,
            revision: str | None,
        ) -> DiscoveryOutcome:
            source = LoadedSource(
                descriptor=SourceDescriptor(
                    source_instance_id=event_catalog_source_instance_id(
                        configured_source_id=config.id, environment=config.environment
                    ),
                    source_kind=SourceKind.EVENT_CATALOG,
                    locator=str(config.root / config.catalog_relative_path),
                    discovery_scope_id=scope_id,
                    scope_definition_digest=scope_digest,
                    declared_provider_revision=revision,
                    content_sha256=content_sha256,
                    semantic_input_digest="",
                    mapping_context_digest="",
                    adapter_identity="",
                    mapping_rule_id="",
                    mapping_rule_version="",
                ),
                document=document,
                diagnostics=diagnostics,
                source_root=str(config.root),
            )
            return DiscoveryOutcome(
                loaded_sources=(source,),
                enumeration_complete=True,
                diagnostics=(),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
            )

        def reject(problem: EventCatalogProblem) -> DiscoveryOutcome:
            return loaded(
                document={},
                diagnostics=[
                    IngestionDiagnostic(
                        code=DiagnosticCode(problem.code),
                        message=problem.message,
                        source_pointer=problem.pointer or config.catalog_relative_path,
                    )
                ],
                content_sha256=_EMPTY_CONTENT_SHA256,
                revision=None,
            )

        if self._duplicate:
            return reject(EventCatalogProblem(DUPLICATE_SOURCE))
        result = load_event_catalog(config)
        if isinstance(result, RejectedEventCatalog):
            return reject(result.problem)
        declarations = result.declarations
        return loaded(
            document={
                # A JSON round trip turns the frozen tuples into plain lists for the digest.
                DECLARATIONS_KEY: json.loads(json.dumps(dataclasses.asdict(declarations))),
                CONFIGURED_SOURCE_ID_KEY: config.id,
                ENVIRONMENT_KEY: config.environment,
            },
            diagnostics=[],
            # One digest over both inputs: a lookup-only change is a content change (I2 D12).
            content_sha256=hashlib.sha256(declarations.source_revision.encode()).hexdigest(),
            revision=declarations.source_revision,
        )
