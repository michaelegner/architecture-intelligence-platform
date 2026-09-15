from app.canonical import ids
from app.canonical.model import ArchitectureModel, Operation, Relation, Schema, Service
from app.provenance.model import Provenance
from app.sources.identity import semantic_input_digest
from app.sources.jcs import canonical_json_bytes, canonical_sha256_hex
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult, LoadedSource
from app.sources.owner_ids import schema_owned_id
from app.sources.pointers import encode_pointer_tokens
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver
from app.sources.service_identity import ServiceIdentityOutcome
from app.validation.source_validation import SourceValidationError, validate_openapi_document

HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

# I1 spec §8.1: "The canonical projection excludes only description, summary, example, examples,
# and externalDocs." 3a applies this exclusion at the top level of each named-component schema
# only (today's parsing fidelity - no recursive/inline/composition handling; that's 3b).
_EXCLUDED_SCHEMA_FIELDS = frozenset(
    {"description", "summary", "example", "examples", "externalDocs"}
)

_OUTCOME_TO_RESULT = {
    ServiceIdentityOutcome.REJECTED_UNSUPPORTED: IngestionResult.REJECTED_UNSUPPORTED,
    ServiceIdentityOutcome.REJECTED_CONFLICT: IngestionResult.REJECTED_CONFLICT,
    ServiceIdentityOutcome.REJECTED_INVALID: IngestionResult.REJECTED_INVALID,
}


def _strip_excluded_schema_fields(definition: dict) -> dict:
    return {key: value for key, value in definition.items() if key not in _EXCLUDED_SCHEMA_FIELDS}


def _rejected(resolution) -> AdapterOutcome:
    return AdapterOutcome(
        result=_OUTCOME_TO_RESULT[resolution.outcome],
        model=ArchitectureModel(),
        diagnostics=tuple(resolution.diagnostics),
        semantic_input_digest=None,
    )


class OpenApiSourceAdapter:
    """I1 spec §8: migrates `parse_openapi` onto the registry seam. Preserves today's parsing
    fidelity exactly (named-component `$ref` schemas only, single document, no limits/cycles/
    composition handling - all 3b); what changes here is *identity*: owner-scoped RFC 8785 Schema
    ids instead of name-based ones, and Service identity resolved via `resolve_service_identity`
    (root + per-operation `x-aip-service-id`) instead of a bare directory-derived parameter.
    """

    adapter_identity = "openapi-adapter@1"
    mapping_rule_version = "v1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return "openapi" in loaded.document

    def map(
        self,
        loaded: LoadedSource,
        *,
        service_identity: ServiceIdentityResolver,
        upstream_model: ArchitectureModel,
        mapping_context_digest: str,
    ) -> AdapterOutcome:
        document = loaded.document
        locator = loaded.descriptor.locator
        source_instance_id = loaded.descriptor.source_instance_id

        try:
            validate_openapi_document(document, source_file=locator)
        except SourceValidationError as exc:
            return AdapterOutcome(
                result=IngestionResult.REJECTED_INVALID,
                model=ArchitectureModel(),
                diagnostics=tuple(
                    IngestionDiagnostic(
                        code=DiagnosticCode.DOCUMENT_PARSE_INVALID,
                        message=message,
                        source_pointer=locator,
                    )
                    for message in exc.errors
                ),
                semantic_input_digest=None,
            )

        root_resolution = service_identity.resolve(
            source_instance_id=source_instance_id,
            construct_pointer="",
            extension_value=document.get("x-aip-service-id"),
        )
        if root_resolution.outcome is not ServiceIdentityOutcome.RESOLVED:
            return _rejected(root_resolution)

        info = document.get("info") or {}
        components_schemas = ((document.get("components") or {}).get("schemas")) or {}

        operations: list[Operation] = []
        relations: list[Relation] = []
        schemas_by_id: dict[str, Schema] = {}
        resolved_service_ids: set[str] = {root_resolution.service_id}

        def resolve_schema_ref(
            schema_obj: dict | None, *, canonical_service_id: str, media_type: str | None
        ) -> str | None:
            if not schema_obj:
                return None
            ref = schema_obj.get("$ref")
            if not ref:
                return None
            name = ref.rsplit("/", 1)[-1]
            schema_id_value = schema_owned_id(
                canonical_service_id=canonical_service_id,
                source_instance_id=source_instance_id,
                normalized_definition_document_path="",
                definition_pointer_tokens=("components", "schemas", name),
            )
            if schema_id_value not in schemas_by_id:
                definition = components_schemas.get(name) or {}
                canonical_hash = canonical_sha256_hex(_strip_excluded_schema_fields(definition))
                schemas_by_id[schema_id_value] = Schema(
                    id=schema_id_value, name=name, format=media_type, canonical_hash=canonical_hash
                )
            return schema_id_value

        for path, path_item in (document.get("paths") or {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, op in path_item.items():
                if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                    continue

                op_extension = op.get("x-aip-service-id")
                if op_extension is not None:
                    resolution = service_identity.resolve(
                        source_instance_id=source_instance_id,
                        construct_pointer=encode_pointer_tokens(("paths", path, method)),
                        extension_value=op_extension,
                    )
                    if resolution.outcome is not ServiceIdentityOutcome.RESOLVED:
                        return _rejected(resolution)
                    canonical_service_id = resolution.service_id
                    resolved_service_ids.add(canonical_service_id)
                else:
                    canonical_service_id = root_resolution.service_id

                operation_id_value = ids.operation_id(canonical_service_id, method, path)

                request_schema_ids: list[str] = []
                request_content = ((op.get("requestBody") or {}).get("content")) or {}
                for media_type, media_obj in request_content.items():
                    schema_id_value = resolve_schema_ref(
                        media_obj.get("schema"),
                        canonical_service_id=canonical_service_id,
                        media_type=media_type,
                    )
                    if schema_id_value and schema_id_value not in request_schema_ids:
                        request_schema_ids.append(schema_id_value)

                response_schema_ids: list[str] = []
                for response_obj in (op.get("responses") or {}).values():
                    if not isinstance(response_obj, dict):
                        continue
                    for media_type, media_obj in (response_obj.get("content") or {}).items():
                        schema_id_value = resolve_schema_ref(
                            media_obj.get("schema"),
                            canonical_service_id=canonical_service_id,
                            media_type=media_type,
                        )
                        if schema_id_value and schema_id_value not in response_schema_ids:
                            response_schema_ids.append(schema_id_value)

                operations.append(
                    Operation(
                        id=operation_id_value,
                        service_id=canonical_service_id,
                        operation_id=op.get("operationId"),
                        method=method.upper(),
                        path=path,
                        request_schema_ids=request_schema_ids,
                        response_schema_ids=response_schema_ids,
                    )
                )
                relations.append(
                    Relation(
                        type="PROVIDES",
                        source_id=canonical_service_id,
                        target_id=operation_id_value,
                    )
                )
                relations.extend(
                    Relation(
                        type="REQUEST_SCHEMA",
                        source_id=operation_id_value,
                        target_id=schema_id_value,
                    )
                    for schema_id_value in request_schema_ids
                )
                relations.extend(
                    Relation(
                        type="RESPONSE_SCHEMA",
                        source_id=operation_id_value,
                        target_id=schema_id_value,
                    )
                    for schema_id_value in response_schema_ids
                )

        evidence = Provenance(
            id=ids.evidence_id(
                "OPENAPI", source_instance_id, loaded.descriptor.declared_provider_revision
            ),
            source_type="OPENAPI",
            source_file=locator,
            source_revision=loaded.descriptor.declared_provider_revision,
        )
        relations = [r.model_copy(update={"evidence_ids": [evidence.id]}) for r in relations]

        services = [
            Service(id=service_id, name=info.get("title", service_id), version=info.get("version"))
            for service_id in sorted(resolved_service_ids)
        ]

        model = ArchitectureModel(
            services=services,
            operations=operations,
            schemas=list(schemas_by_id.values()),
            relations=relations,
            provenance=[evidence],
        )

        digest = semantic_input_digest(
            normalized_document_projection_bytes=canonical_json_bytes(document),
            mapping_context_digest=mapping_context_digest,
        )

        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=model,
            diagnostics=(),
            semantic_input_digest=digest,
        )
