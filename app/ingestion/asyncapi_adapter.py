from app.canonical import ids
from app.canonical.model import (
    ArchitectureModel,
    Direction,
    Message,
    Queue,
    Relation,
    Schema,
    Service,
)
from app.ingestion._shared import rejected_outcome_for_identity, strip_excluded_schema_fields
from app.provenance.model import Provenance
from app.sources.encoding import unicode_nfc
from app.sources.identity import semantic_input_digest
from app.sources.jcs import canonical_json_bytes, canonical_sha256_hex
from app.sources.model import DiagnosticCode, IngestionDiagnostic, IngestionResult, LoadedSource
from app.sources.owner_ids import (
    MISSING,
    InvalidXVersionError,
    inline_payload_schema_id,
    message_owned_id,
    normalize_x_version,
    queue_owned_id,
    schema_owned_id,
)
from app.sources.pointers import encode_pointer_tokens
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver
from app.sources.service_identity import ServiceIdentityOutcome
from app.validation.source_validation import SourceValidationError, validate_asyncapi_document

# AsyncAPI 2.x: "publish" = the described application sends on the channel, "subscribe" = it
# receives from the channel (named from the app's own perspective, not the client's).
OPERATION_DIRECTIONS = {"publish": Direction.SEND, "subscribe": Direction.RECEIVE}
RELATION_TYPES = {Direction.SEND: "SENDS", Direction.RECEIVE: "RECEIVES_FROM"}


def _resolve_ref(ref: str, document: dict) -> dict:
    node = document
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _extract_message_defs(
    operation_def: dict, document: dict, *, channel_name: str, operation_key: str
) -> list[tuple[dict, tuple[str, ...]]]:
    """Returns (message_def, definition_pointer_tokens) pairs - the pointer is the resolved
    component pointer for a `$ref` (correctly shared across every channel/operation referencing the
    same named component), or the message's own document-unique inline operation-message pointer
    (`channel_name`/`operation_key` included: two different channels each declaring their own
    inline, non-`$ref` message must never collide onto the same owner-scoped identity just because
    both happen to sit at an operation's bare `message` key - a real bug found in PR review).
    """
    message_obj = operation_def.get("message")
    if not message_obj:
        return []
    if "oneOf" in message_obj:
        results = []
        for index, candidate in enumerate(message_obj["oneOf"]):
            if "$ref" in candidate:
                name = candidate["$ref"].rsplit("/", 1)[-1]
                results.append(
                    (_resolve_ref(candidate["$ref"], document), ("components", "messages", name))
                )
            else:
                results.append(
                    (
                        candidate,
                        ("channels", channel_name, operation_key, "message", "oneOf", str(index)),
                    )
                )
        return results
    if "$ref" in message_obj:
        name = message_obj["$ref"].rsplit("/", 1)[-1]
        return [(_resolve_ref(message_obj["$ref"], document), ("components", "messages", name))]
    return [(message_obj, ("channels", channel_name, operation_key, "message"))]


def _resolve_payload_schema_id(
    payload: dict | None,
    *,
    document: dict,
    canonical_service_id: str,
    source_instance_id: str,
    message_id: str,
    message_name: str,
    message_pointer_tokens: tuple[str, ...],
    schemas_by_id: dict[str, Schema],
) -> str | None:
    """I1 spec §9.1: "A payload $ref always uses the resolved definition's §8.1 Schema ID; only a
    payload defined inline uses the message-owned inline payload ID."
    """
    if not payload:
        return None
    if "$ref" in payload:
        name = payload["$ref"].rsplit("/", 1)[-1]
        schema_id_value = schema_owned_id(
            canonical_service_id=canonical_service_id,
            source_instance_id=source_instance_id,
            normalized_definition_document_path="",
            definition_pointer_tokens=("components", "schemas", name),
        )
        definition = _resolve_ref(payload["$ref"], document)
        schema_name = name
    else:
        schema_id_value = inline_payload_schema_id(
            message_id=message_id,
            normalized_inline_payload_document_path="",
            inline_payload_pointer_tokens=(*message_pointer_tokens, "payload"),
        )
        definition = payload
        # Schema.name is a display label only (identity comes from schema_id_value) - an inline
        # payload has no component name of its own, so fall back to its owning message's name.
        schema_name = f"{message_name} payload"

    if schema_id_value not in schemas_by_id:
        schemas_by_id[schema_id_value] = Schema(
            id=schema_id_value,
            name=schema_name,
            format="application/json",
            canonical_hash=canonical_sha256_hex(strip_excluded_schema_fields(definition)),
        )
    return schema_id_value


def _resolve_selected_servers(document: dict, channel_def: dict) -> list[dict]:
    servers_map = document.get("servers") or {}
    channel_servers = channel_def.get("servers")
    if channel_servers:
        return [servers_map[name] for name in channel_servers if name in servers_map]
    return list(servers_map.values())


def _resolve_broker_and_namespace(selected_servers: list[dict]) -> tuple[str, str] | None:
    """I1 spec §9: broker id from an explicit `x-aip-broker-id` on the selected server(s); when a
    channel selects multiple servers, all must agree on both broker id and namespace or the result
    is ambiguous (`None`). Namespace is the AMQP server binding `virtualHost`, else empty string -
    §9's "configured destination namespace" path is deferred (no config surface ships in 3a).
    """
    if not selected_servers:
        return None
    candidates: set[tuple[str, str]] = set()
    for server in selected_servers:
        broker_id = server.get("x-aip-broker-id")
        if not broker_id:
            return None
        namespace = ((server.get("bindings") or {}).get("amqp") or {}).get("virtualHost") or ""
        candidates.add((broker_id, namespace))
    if len(candidates) != 1:
        return None
    return next(iter(candidates))


def _resolve_queue_kind(channel_def: dict) -> bool | None:
    """True/False = evidence agrees the channel is/isn't a Queue; None = no evidence at all."""
    votes: set[bool] = set()
    if "x-aip-destination-kind" in channel_def:
        votes.add(channel_def["x-aip-destination-kind"] == "queue")
    amqp_binding = ((channel_def.get("bindings") or {}).get("amqp")) or {}
    if "is" in amqp_binding:
        votes.add(amqp_binding["is"] == "queue")
    if not votes:
        return None
    if len(votes) > 1:
        return None
    return next(iter(votes))


class AsyncApiSourceAdapter:
    """I1 spec §9: migrates `parse_asyncapi` onto the registry seam. Parsing fidelity is unchanged
    (single-file `$ref` only - no limits/cycles, that's 3b); identity changes throughout: owner-
    scoped RFC 8785 Message/Schema ids, and Queue kind/identity now require real evidence
    (`x-aip-destination-kind`/AMQP `is: queue` + `x-aip-broker-id`) instead of being derived from
    the bare channel name.
    """

    adapter_identity = "asyncapi-adapter@1"
    mapping_rule_version = "v1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return "asyncapi" in loaded.document

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
            validate_asyncapi_document(document, source_file=locator)
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
            return rejected_outcome_for_identity(root_resolution)
        canonical_service_id = root_resolution.service_id

        info = document.get("info") or {}
        channels = document.get("channels") or {}

        queues_by_id: dict[str, Queue] = {}
        messages_by_id: dict[str, Message] = {}
        schemas_by_id: dict[str, Schema] = {}
        relations: list[Relation] = []
        seen_relations: set[tuple[str, str, str]] = set()
        diagnostics: list[IngestionDiagnostic] = []

        def add_relation(relation_type: str, source_id: str, target_id: str) -> None:
            key = (relation_type, source_id, target_id)
            if key not in seen_relations:
                seen_relations.add(key)
                relations.append(
                    Relation(type=relation_type, source_id=source_id, target_id=target_id)
                )

        channel_queue_id: dict[str, str] = {}
        channel_broker_namespace: dict[str, tuple[str, str]] = {}
        any_channel_supported = False
        any_omission = False

        # Pass 1: resolve Queue kind/identity per channel.
        for channel_name, channel_def in channels.items():
            if not isinstance(channel_def, dict):
                continue

            kind = _resolve_queue_kind(channel_def)
            if kind is None:
                any_omission = True
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.QUEUE_EVIDENCE_MISSING,
                        message=f"channel {channel_name!r}: no Queue-kind evidence path succeeded",
                        source_pointer=encode_pointer_tokens(("channels", channel_name)),
                    )
                )
                continue
            if kind is False:
                any_omission = True
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.QUEUE_EVIDENCE_MISSING,
                        message=f"channel {channel_name!r}: destination kind evidence is not 'queue'",
                        source_pointer=encode_pointer_tokens(("channels", channel_name)),
                    )
                )
                continue

            selected_servers = _resolve_selected_servers(document, channel_def)
            broker_and_namespace = _resolve_broker_and_namespace(selected_servers)
            if broker_and_namespace is None:
                any_omission = True
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.AMBIGUOUS,
                        message=(
                            f"channel {channel_name!r}: no single agreeing broker id/namespace "
                            "across selected servers"
                        ),
                        source_pointer=encode_pointer_tokens(("channels", channel_name)),
                    )
                )
                continue

            stable_broker_id, namespace = broker_and_namespace
            channel_address = unicode_nfc(channel_name)
            queue_id_value = queue_owned_id(
                stable_broker_id=stable_broker_id,
                normalized_namespace_or_empty=namespace,
                exact_channel_address=channel_address,
            )
            protocol = next(iter(channel_def.get("bindings") or {}), None)
            queues_by_id[queue_id_value] = Queue(
                id=queue_id_value,
                name=channel_name,
                protocol=protocol,
                namespace=namespace or None,
            )
            channel_queue_id[channel_name] = queue_id_value
            channel_broker_namespace[channel_name] = (stable_broker_id, namespace)

        # DLQ links inherit their declaring channel's resolved broker/namespace (§9 gives no
        # separate evidence path for a DLQ target's own kind/identity).
        for channel_name, channel_def in channels.items():
            if not isinstance(channel_def, dict):
                continue
            dlq_target_name = channel_def.get("x-dead-letter-queue")
            if not dlq_target_name:
                continue
            if channel_name not in channel_queue_id:
                any_omission = True
                diagnostics.append(
                    IngestionDiagnostic(
                        code=DiagnosticCode.QUEUE_EVIDENCE_MISSING,
                        message=(
                            f"channel {channel_name!r}: cannot establish DEAD_LETTERS_TO target "
                            "without a resolved declaring Queue"
                        ),
                        source_pointer=encode_pointer_tokens(("channels", channel_name)),
                    )
                )
                continue
            stable_broker_id, namespace = channel_broker_namespace[channel_name]
            target_address = unicode_nfc(dlq_target_name)
            target_queue_id = queue_owned_id(
                stable_broker_id=stable_broker_id,
                normalized_namespace_or_empty=namespace,
                exact_channel_address=target_address,
            )
            if target_queue_id not in queues_by_id:
                queues_by_id[target_queue_id] = Queue(
                    id=target_queue_id, name=dlq_target_name, namespace=namespace or None
                )
            add_relation("DEAD_LETTERS_TO", channel_queue_id[channel_name], target_queue_id)

        # Pass 2: publish/subscribe operations and their messages, only for channels with a
        # resolved Queue.
        for channel_name, channel_def in channels.items():
            if not isinstance(channel_def, dict) or channel_name not in channel_queue_id:
                continue
            queue_id_value = channel_queue_id[channel_name]

            for operation_key, direction in OPERATION_DIRECTIONS.items():
                operation_def = channel_def.get(operation_key)
                if not isinstance(operation_def, dict):
                    continue

                any_channel_supported = True
                add_relation(RELATION_TYPES[direction], canonical_service_id, queue_id_value)

                for message_def, message_pointer_tokens in _extract_message_defs(
                    operation_def, document, channel_name=channel_name, operation_key=operation_key
                ):
                    try:
                        normalized_x_version = normalize_x_version(
                            message_def.get("x-version", MISSING)
                        )
                    except InvalidXVersionError as exc:
                        return AdapterOutcome(
                            result=IngestionResult.REJECTED_INVALID,
                            model=ArchitectureModel(),
                            diagnostics=(
                                IngestionDiagnostic(
                                    code=DiagnosticCode.SERVICE_IDENTITY_INVALID,
                                    message=str(exc),
                                    source_pointer=encode_pointer_tokens(
                                        ("channels", channel_name, operation_key)
                                    ),
                                ),
                            ),
                            semantic_input_digest=None,
                        )

                    message_id_value = message_owned_id(
                        canonical_service_id=canonical_service_id,
                        source_instance_id=source_instance_id,
                        normalized_definition_document_path="",
                        definition_pointer_tokens=message_pointer_tokens,
                        normalized_x_version_or_empty=normalized_x_version,
                    )
                    message_name = (
                        message_def.get("name")
                        or message_def.get("title")
                        or f"{channel_name}:{operation_key}"
                    )
                    if message_id_value not in messages_by_id:
                        payload = message_def.get("payload")
                        schema_id_value = _resolve_payload_schema_id(
                            payload,
                            document=document,
                            canonical_service_id=canonical_service_id,
                            source_instance_id=source_instance_id,
                            message_id=message_id_value,
                            message_name=message_name,
                            message_pointer_tokens=message_pointer_tokens,
                            schemas_by_id=schemas_by_id,
                        )
                        messages_by_id[message_id_value] = Message(
                            id=message_id_value,
                            name=message_name,
                            version=normalized_x_version or None,
                            schema_id=schema_id_value,
                        )
                        if schema_id_value:
                            add_relation("CONFORMS_TO", message_id_value, schema_id_value)
                    add_relation("CARRIES", queue_id_value, message_id_value)

        if not channels:
            result = IngestionResult.ACCEPTED
        elif not any_channel_supported:
            return AdapterOutcome(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                model=ArchitectureModel(),
                diagnostics=tuple(diagnostics),
                semantic_input_digest=None,
            )
        elif any_omission:
            result = IngestionResult.ACCEPTED_WITH_LIMITATIONS
        else:
            result = IngestionResult.ACCEPTED

        evidence = Provenance(
            id=ids.evidence_id(
                "ASYNCAPI", source_instance_id, loaded.descriptor.declared_provider_revision
            ),
            source_type="ASYNCAPI",
            source_file=locator,
            source_revision=loaded.descriptor.declared_provider_revision,
        )
        relations = [r.model_copy(update={"evidence_ids": [evidence.id]}) for r in relations]

        model = ArchitectureModel(
            services=[
                Service(
                    id=canonical_service_id,
                    name=info.get("title", canonical_service_id),
                    version=info.get("version"),
                )
            ],
            queues=list(queues_by_id.values()),
            messages=list(messages_by_id.values()),
            schemas=list(schemas_by_id.values()),
            relations=relations,
            provenance=[evidence],
        )

        digest = semantic_input_digest(
            normalized_document_projection_bytes=canonical_json_bytes(document),
            mapping_context_digest=mapping_context_digest,
        )

        return AdapterOutcome(
            result=result, model=model, diagnostics=tuple(diagnostics), semantic_input_digest=digest
        )
