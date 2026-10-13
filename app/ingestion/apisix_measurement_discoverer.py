"""v0.7.0 I2.2b: the APISIX measurement source discoverer (I2.1 contract §1-§2, §5, §8). One
registration is one observation window: four fixed file names under the registered root, written by
`app.gateway_capture.apisix_metrics` (and, optionally, the operator's mapping artifact). It never
contacts a gateway.

Mirrors `ApisixSourceDiscoverer`: the source identity needs only configured values, so a missing or
invalid fixture still yields an identified source that the adapter rejects with the right per-source
result, and the run becomes PARTIAL (nothing commits). Every diagnostic message is fixed text: no
manifest, extract or mapping value ever reaches one.
"""

import hashlib
import json
from pathlib import Path

from app.common.encoding import length_delimited
from app.sources.apisix_measurement_contract import (
    END_FILE,
    MANIFEST_FILE,
    MAPPING_FILE,
    MAX_EXTRACT_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_MAPPING_BYTES,
    START_FILE,
    MeasurementRejection,
    measurement_window_id,
    parse_mapping,
    validate_fixture,
)
from app.sources.identity import (
    apisix_measurement_source_instance_id,
    discovery_scope_id,
    normalize_relative_posix_path,
    scope_definition_digest,
)
from app.sources.model import (
    ApisixMeasurementSourceConfig,
    DiagnosticCode,
    IngestionDiagnostic,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.registry import DiscoveryOutcome

_EMPTY_CONTENT_SHA256 = hashlib.sha256(b"").hexdigest()

_MESSAGES = {
    DiagnosticCode.GWM_MANIFEST_INVALID: "the APISIX measurement manifest is missing or malformed",
    DiagnosticCode.GWM_BINDING_MISMATCH: "an APISIX measurement extract does not match its manifest hash",
    DiagnosticCode.GWM_EXTRACT_INVALID: "an APISIX measurement extract is missing or not normalized",
    DiagnosticCode.GWM_INSTANCE_MISMATCH: "the measurement's gateway instance or environment does not match the registration",
    DiagnosticCode.GWM_MAPPING_INVALID: "the APISIX mapping artifact is malformed",
    DiagnosticCode.GWM_SCHEMA_UNSUPPORTED: "the APISIX measurement schema version is not supported",
    DiagnosticCode.GWM_LIMIT_EXCEEDED: "the APISIX measurement fixture exceeds an ingestion bound",
    DiagnosticCode.GWM_DUPLICATE_SOURCE: "another registration declares the same gateway instance and environment",
}  # fmt: skip


class ApisixMeasurementSourceDiscoverer:
    source_kind = SourceKind.APISIX_MEASUREMENT

    def __init__(
        self, config: ApisixMeasurementSourceConfig, *, duplicate_measurement_source: bool = False
    ):
        self._config = config
        self._duplicate = duplicate_measurement_source
        self.discoverer_identity = "apisix-measurement-discoverer@1"

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
                source_kind=SourceKind.APISIX_MEASUREMENT,
                locator=str(config.root / MANIFEST_FILE),
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

    def _file(self, name: str, root: Path) -> Path | None:
        path = (root / name).resolve()
        return path if path.is_relative_to(root.resolve()) and path.is_file() else None

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

        instance_id = apisix_measurement_source_instance_id(
            configured_source_id=config.id,
            gateway_instance_id=config.gateway_instance_id,
            environment=config.environment,
        )
        reject = {"instance_id": instance_id, "scope_id": scope_id, "scope_digest": scope_digest}
        if self._duplicate:
            return self._rejected(
                code=DiagnosticCode.GWM_DUPLICATE_SOURCE, pointer=MANIFEST_FILE, **reject
            )

        # Contract §2.3 / I2.2b reading: an absent required file is the file's own invalid code.
        manifest_path = self._file(MANIFEST_FILE, config.root)
        if manifest_path is None:
            return self._rejected(
                code=DiagnosticCode.GWM_MANIFEST_INVALID, pointer=MANIFEST_FILE, **reject
            )
        start_path = self._file(START_FILE, config.root)
        if start_path is None:
            return self._rejected(
                code=DiagnosticCode.GWM_EXTRACT_INVALID, pointer=START_FILE, **reject
            )
        end_path = self._file(END_FILE, config.root)
        if end_path is None:
            return self._rejected(
                code=DiagnosticCode.GWM_EXTRACT_INVALID, pointer=END_FILE, **reject
            )
        mapping_path = self._file(MAPPING_FILE, config.root)
        for path, limit, name in (
            (manifest_path, MAX_MANIFEST_BYTES, MANIFEST_FILE),
            (start_path, MAX_EXTRACT_BYTES, START_FILE),
            (end_path, MAX_EXTRACT_BYTES, END_FILE),
            (mapping_path, MAX_MAPPING_BYTES, MAPPING_FILE),
        ):
            if path is not None and path.stat().st_size > limit:
                return self._rejected(
                    code=DiagnosticCode.GWM_LIMIT_EXCEEDED, pointer=name, **reject
                )

        manifest_bytes = manifest_path.read_bytes()
        start_bytes, end_bytes = start_path.read_bytes(), end_path.read_bytes()
        mapping_bytes = mapping_path.read_bytes() if mapping_path is not None else b""
        digest = hashlib.sha256(
            length_delimited(manifest_bytes, start_bytes, end_bytes, mapping_bytes)
        ).hexdigest()
        reject["content_sha256"] = digest
        try:
            validated = validate_fixture(
                manifest_bytes,
                start_bytes,
                end_bytes,
                gateway_instance_id=config.gateway_instance_id,
                environment=config.environment,
            )
            if mapping_path is not None:
                parse_mapping(mapping_bytes, gateway_instance_id=config.gateway_instance_id)
        except MeasurementRejection as exc:
            return self._rejected(code=DiagnosticCode(exc.code), pointer=MANIFEST_FILE, **reject)

        document = {
            "manifest": json.loads(manifest_bytes),
            "start_extract": start_bytes.decode("utf-8"),
            "end_extract": end_bytes.decode("utf-8"),
            "mapping": json.loads(mapping_bytes) if mapping_path is not None else None,
        }
        loaded = LoadedSource(
            descriptor=SourceDescriptor(
                source_instance_id=instance_id,
                source_kind=SourceKind.APISIX_MEASUREMENT,
                locator=str(config.root / MANIFEST_FILE),
                discovery_scope_id=scope_id,
                scope_definition_digest=scope_digest,
                declared_provider_revision=measurement_window_id(validated.manifest),
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
