"""v0.7.0 I1.4: the APISIX gateway source discoverer (I1.1 contract §1-§2, §7). One registration, one
bounded JSON capture file written by `app.gateway_capture.apisix`; it never contacts a gateway.

Mirrors `KubernetesSourceDiscoverer`: the source identity needs only configured values, so a missing
or invalid capture still yields an identified source that the adapter then rejects with the right
per-source result, and the run becomes PARTIAL (nothing commits). Every diagnostic message is fixed
text: no source value, path content or Admin API detail ever reaches one.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.sources.apisix_contract import ApisixCaptureEnvelope, validate_capture_document
from app.sources.identity import (
    apisix_source_instance_id,
    discovery_scope_id,
    normalize_relative_posix_path,
    scope_definition_digest,
)
from app.sources.model import (
    ApisixSourceConfig,
    DiagnosticCode,
    IngestionDiagnostic,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import DiscoveryOutcome

# Contract §2: ≤ 8 MiB, ≤ 10,000 resource objects, nesting ≤ 64.
MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_RESOURCE_OBJECTS = 10_000
MAX_NESTING_DEPTH = 64
_RESOURCE_ARRAYS = (
    "consumers",
    "routes",
    "services",
    "upstreams",
    "plugin_configs",
    "consumer_groups",
    "global_rules",
)
_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()

_MESSAGES = {
    DiagnosticCode.GW_CAPTURE_INVALID: "the APISIX capture is missing, unreadable or malformed",
    DiagnosticCode.GW_CAPTURE_INCONSISTENT: "the APISIX capture's etcd revision changed during the read",
    DiagnosticCode.GW_CAPTURE_INCOMPLETE: "the APISIX capture declares an incomplete resource list",
    DiagnosticCode.GW_CAPTURE_UNREDACTED: "the APISIX capture still carries credential material",
    DiagnosticCode.GW_INSTANCE_MISMATCH: "the capture's gateway instance does not match the registration",
    DiagnosticCode.GW_CAPTURE_SURFACE_UNSUPPORTED: "the capture surface is not an admitted APISIX surface",
    DiagnosticCode.GW_CAPTURE_SCHEMA_UNSUPPORTED: "the APISIX capture schema version is not supported",
    DiagnosticCode.GW_CAPTURE_LIMIT_EXCEEDED: "the APISIX capture exceeds an ingestion bound",
    DiagnosticCode.GW_DUPLICATE_INSTANCE: "another registration declares the same gateway instance",
}


class _DuplicateKeyError(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _DuplicateKeyError
    return dict(pairs)


def _depth(node: object, level: int = 1) -> int:
    if isinstance(node, dict):
        return max((_depth(child, level + 1) for child in node.values()), default=level)
    if isinstance(node, list):
        return max((_depth(child, level + 1) for child in node), default=level)
    return level


class ApisixSourceDiscoverer:
    source_kind = SourceKind.APISIX

    def __init__(self, config: ApisixSourceConfig, *, duplicate_gateway_instance: bool = False):
        self._config = config
        self._duplicate = duplicate_gateway_instance
        self.discoverer_identity = "apisix-discoverer@1"

    def _rejected(
        self,
        *,
        code: DiagnosticCode,
        instance_id: str,
        scope_id: str,
        scope_digest: str,
        pointer: str,
        content_sha256: str = _EMPTY_CONTENT_SHA256,
    ) -> DiscoveryOutcome:
        config = self._config
        loaded = LoadedSource(
            descriptor=SourceDescriptor(
                source_instance_id=instance_id,
                source_kind=SourceKind.APISIX,
                locator=str(config.root / config.capture_relative_path),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
                content_sha256=content_sha256,
                semantic_input_digest="",
                mapping_context_digest="",
                adapter_identity="",
                mapping_rule_id="",
                mapping_rule_version="",
            ),
            document={},
            diagnostics=[
                IngestionDiagnostic(code=code, message=_MESSAGES[code], source_pointer=pointer)
            ],
            source_root=str(config.root),
        )
        return DiscoveryOutcome(
            loaded_sources=(loaded,),
            enumeration_complete=True,
            diagnostics=(),
            discovery_scope_id=scope_id,
            scope_definition_digest=scope_digest,
        )

    def discover(self) -> DiscoveryOutcome:
        config = self._config
        scope_id = discovery_scope_id(
            configured_scope_id=config.resolved_scope_id,
            stable_target_identity=config.resolved_stable_target_identity,
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

        instance_id = apisix_source_instance_id(
            configured_apisix_source_id=config.id, gateway_instance_id=config.gateway_instance_id
        )
        reject = {
            "instance_id": instance_id,
            "scope_id": scope_id,
            "scope_digest": scope_digest,
            "pointer": config.capture_relative_path,
        }
        if self._duplicate:
            return self._rejected(code=DiagnosticCode.GW_DUPLICATE_INSTANCE, **reject)

        capture_path = (config.root / config.capture_relative_path).resolve()
        if not capture_path.is_relative_to(config.root.resolve()) or not capture_path.is_file():
            return self._rejected(code=DiagnosticCode.GW_CAPTURE_INVALID, **reject)
        if capture_path.stat().st_size > MAX_CAPTURE_BYTES:
            return self._rejected(code=DiagnosticCode.GW_CAPTURE_LIMIT_EXCEEDED, **reject)
        raw = capture_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        try:
            document = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
        except (ValueError, RecursionError):
            return self._rejected(
                code=DiagnosticCode.GW_CAPTURE_INVALID, content_sha256=digest, **reject
            )
        if _depth(document) > MAX_NESTING_DEPTH or (
            isinstance(document, dict)
            and sum(
                len(document[name])
                for name in _RESOURCE_ARRAYS
                if isinstance(document.get(name), list)
            )
            > MAX_RESOURCE_OBJECTS
        ):
            return self._rejected(
                code=DiagnosticCode.GW_CAPTURE_LIMIT_EXCEEDED, content_sha256=digest, **reject
            )
        problem = validate_capture_document(document)
        if problem is not None:
            return self._rejected(
                code=DiagnosticCode(problem.code), content_sha256=digest, **reject
            )
        envelope = ApisixCaptureEnvelope.model_validate(document)
        if envelope.gateway_instance_id != config.gateway_instance_id:
            return self._rejected(
                code=DiagnosticCode.GW_INSTANCE_MISMATCH, content_sha256=digest, **reject
            )

        loaded = LoadedSource(
            descriptor=SourceDescriptor(
                source_instance_id=instance_id,
                source_kind=SourceKind.APISIX,
                locator=str(Path(config.root) / config.capture_relative_path),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
                declared_provider_revision=envelope.source_revision,
                content_sha256=digest,
                semantic_input_digest="",
                mapping_context_digest="",
                adapter_identity="",
                mapping_rule_id="",
                mapping_rule_version="",
            ),
            document=document,
            source_root=str(config.root),
        )
        return DiscoveryOutcome(
            loaded_sources=(loaded,),
            enumeration_complete=True,
            diagnostics=(),
            discovery_scope_id=scope_id,
            scope_definition_digest=scope_digest,
        )
