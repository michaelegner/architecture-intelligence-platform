"""End-to-end fixtures proving PR3b's bounded multi-file `$ref` resolution, schema composition,
and version enforcement through the real discoverer + adapter pipeline (`run_filesystem_discovery`)
- not just the `app.sources.reference_resolution` primitives already covered by
`test_sources_reference_resolution.py`. These are test-fixture-only trees built fresh per test via
`tmp_path`, not additions to the pinned `examples/` bundled-identity corpus (I1 spec §8.1's
"Component name... and matching content elsewhere are labels/comparison evidence only and MUST NOT
establish identity" means no bundled-identity contract is at stake here).
"""

from pathlib import Path

import yaml

from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.jcs import canonical_sha256_hex
from app.sources.model import DiagnosticCode, FilesystemSourceConfig, IngestionResult


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document))


def _outcome_for(result, suffix: str):
    return next(
        ro.outcome
        for ro in result.source_outcomes.values()
        if ro.descriptor_locator.endswith(suffix)
    )


def _write_schema_chain(service_dir: Path, num_files: int) -> None:
    """schemas/s0.yaml -> s1.yaml -> ... -> s{num_files - 1}.yaml, a chain of num_files - 1
    cross-file $refs, each linked via a 'next' property. The root openapi.yaml's own $ref to
    s0.yaml is one additional hop, so an openapi.yaml response schema referencing
    'schemas/s0.yaml#/S' has a closure-wide depth of exactly num_files hops from the root."""
    for i in range(num_files):
        content: dict = {"S": {"type": "object"}}
        if i < num_files - 1:
            content["S"]["properties"] = {"next": {"$ref": f"s{i + 1}.yaml#/S"}}
        _write(service_dir / "schemas" / f"s{i}.yaml", content)


def test_cross_file_openapi_and_asyncapi_schema_refs_resolve_end_to_end(tmp_path):
    _write(
        tmp_path / "widget-service" / "schemas" / "common.yaml",
        {"Widget": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )
    _write(
        tmp_path / "widget-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "WidgetService"},
            "x-aip-service-id": "service:widget",
            "paths": {
                "/widgets/{id}": {
                    "get": {
                        "operationId": "getWidget",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "schemas/common.yaml#/Widget"}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )
    _write(
        tmp_path / "widget-service" / "asyncapi.yaml",
        {
            "asyncapi": "2.6.0",
            "info": {"title": "WidgetService"},
            "x-aip-service-id": "service:widget",
            "servers": {"broker": {"url": "amqp://x", "protocol": "amqp", "x-aip-broker-id": "b1"}},
            "channels": {
                "widget-q": {
                    "x-aip-destination-kind": "queue",
                    "publish": {
                        "message": {
                            "name": "WidgetCreated",
                            "payload": {"$ref": "schemas/common.yaml#/Widget"},
                        }
                    },
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="cross-file", root=tmp_path))

    openapi_outcome = _outcome_for(result, "openapi.yaml")
    asyncapi_outcome = _outcome_for(result, "asyncapi.yaml")
    assert openapi_outcome.result is IngestionResult.ACCEPTED
    assert asyncapi_outcome.result is IngestionResult.ACCEPTED

    expected_hash = canonical_sha256_hex(
        {"type": "object", "properties": {"id": {"type": "string"}}}
    )
    assert len(openapi_outcome.model.schemas) == 1
    assert openapi_outcome.model.schemas[0].canonical_hash == expected_hash
    assert len(asyncapi_outcome.model.schemas) == 1
    assert asyncapi_outcome.model.schemas[0].canonical_hash == expected_hash
    # Owner-scoped, not content-scoped: the identical resolved definition, referenced from two
    # different source documents, gets two different owner-scoped Schema IDs (each includes its
    # own SourceInstanceId) - equal canonical_hash is comparison evidence only, never identity.
    assert openapi_outcome.model.schemas[0].id != asyncapi_outcome.model.schemas[0].id


def test_a_dot_segment_normalized_ref_resolves_to_the_same_identity_as_the_direct_spelling(
    tmp_path,
):
    _write(
        tmp_path / "svc" / "schemas" / "widget.yaml",
        {"Widget": {"type": "object"}},
    )

    def _build(ref: str) -> dict:
        return {
            "openapi": "3.1.0",
            "info": {"title": "Svc"},
            "x-aip-service-id": "service:svc",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {"content": {"application/json": {"schema": {"$ref": ref}}}}
                        },
                    }
                }
            },
        }

    config = FilesystemSourceConfig(id="same-config", root=tmp_path)

    _write(tmp_path / "svc" / "openapi.yaml", _build("schemas/widget.yaml#/Widget"))
    direct = run_filesystem_discovery(config)
    direct_id = _outcome_for(direct, "openapi.yaml").model.schemas[0].id

    _write(tmp_path / "svc" / "openapi.yaml", _build("./schemas/../schemas/widget.yaml#/Widget"))
    dotted = run_filesystem_discovery(config)
    dotted_id = _outcome_for(dotted, "openapi.yaml").model.schemas[0].id

    assert direct_id == dotted_id


def test_valid_composition_is_accepted_with_limitations_and_diagnosed(tmp_path):
    _write(
        tmp_path / "compose-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "ComposeService"},
            "x-aip-service-id": "service:compose",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "allOf": [
                                                {"type": "object", "properties": {"a": {}}},
                                                {"type": "object", "properties": {"b": {}}},
                                            ]
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="compose", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED_WITH_LIMITATIONS
    assert any(
        d.code is DiagnosticCode.SCHEMA_COMPOSITION_UNINTERPRETED for d in outcome.diagnostics
    )
    assert len(outcome.model.schemas) == 1
    branch_a = canonical_sha256_hex({"type": "object", "properties": {"a": {}}})
    branch_b = canonical_sha256_hex({"type": "object", "properties": {"b": {}}})
    sorted_branches = sorted(
        [{"type": "object", "properties": {"a": {}}}, {"type": "object", "properties": {"b": {}}}],
        key=canonical_sha256_hex,
    )
    assert branch_a != branch_b  # sanity: the two branches really do hash differently
    expected_hash = canonical_sha256_hex({"allOf": sorted_branches})
    assert outcome.model.schemas[0].canonical_hash == expected_hash


def test_a_genuine_cross_file_reference_cycle_rejects_the_whole_source(tmp_path):
    _write(
        tmp_path / "cyclic-service" / "schemas" / "a.yaml",
        {"A": {"type": "object", "properties": {"self": {"$ref": "b.yaml#/B"}}}},
    )
    _write(
        tmp_path / "cyclic-service" / "schemas" / "b.yaml",
        {"B": {"type": "object", "properties": {"back": {"$ref": "a.yaml#/A"}}}},
    )
    _write(
        tmp_path / "cyclic-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "CyclicService"},
            "x-aip-service-id": "service:cyclic",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "schemas/a.yaml#/A"}}
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="cyclic", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REFERENCE_CYCLE_UNSUPPORTED for d in outcome.diagnostics)
    assert outcome.model.schemas == []


def test_a_remote_reference_rejects_the_whole_source(tmp_path):
    _write(
        tmp_path / "remote-ref-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "RemoteRefService"},
            "x-aip-service-id": "service:remote",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "https://example.com/x.yaml#/X"}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="remote", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REMOTE_REFERENCE_UNSUPPORTED for d in outcome.diagnostics)


def test_a_dot_dot_escape_past_the_source_root_rejects_the_whole_source(tmp_path):
    # The escape target lives as a SIBLING of the configured source root, one level up - a real
    # file that exists, so the failure is specifically the containment check, not a missing-file
    # side effect.
    (tmp_path / "outside.yaml").write_text(yaml.safe_dump({"Escaped": {"type": "object"}}))
    root = tmp_path / "root"
    _write(
        root / "escape-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "EscapeService"},
            "x-aip-service-id": "service:escape",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "../../outside.yaml#/Escaped"}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="escape", root=root))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_INVALID
    assert any(d.code is DiagnosticCode.REFERENCE_INVALID for d in outcome.diagnostics)


def _chain_response_schema_openapi_doc() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "ChainService"},
        "x-aip-service-id": "service:chain",
        "paths": {
            "/x": {
                "get": {
                    "operationId": "getX",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "schemas/s0.yaml#/S"}}
                            }
                        }
                    },
                }
            }
        },
    }


def test_a_reference_chain_within_the_depth_limit_is_accepted(tmp_path):
    service_dir = tmp_path / "chain-service"
    _write_schema_chain(
        service_dir, num_files=16
    )  # root -> s0 -> ... -> s15: 16 hops, at the limit
    _write(service_dir / "openapi.yaml", _chain_response_schema_openapi_doc())

    result = run_filesystem_discovery(FilesystemSourceConfig(id="chain-ok", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED


def test_a_reference_chain_exceeding_the_depth_limit_is_rejected_end_to_end(tmp_path):
    """Regression for a real review finding: no single per-construct schema resolution call ever
    counted total depth across a whole closure, so a chain of single-hop $refs - each individually
    resolving just fine - sailed straight through map() with no REFERENCE_LIMIT_EXCEEDED at all.
    Only a closure-wide walk, run authoritatively by the adapter (not just the discoverer's
    best-effort one), can catch this."""
    service_dir = tmp_path / "chain-service"
    _write_schema_chain(service_dir, num_files=17)  # 17 hops: one past the depth-16 limit
    _write(service_dir / "openapi.yaml", _chain_response_schema_openapi_doc())

    result = run_filesystem_discovery(FilesystemSourceConfig(id="chain-bad", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REFERENCE_LIMIT_EXCEEDED for d in outcome.diagnostics)
    assert outcome.model.schemas == []


def test_editing_only_a_referenced_schema_file_changes_the_semantic_input_digest(tmp_path):
    """Regression for a real review finding: semantic_input_digest previously hashed only the root
    document's own bytes, so an edit to a referenced-only file was completely invisible to it - the
    revision fence would never advance even though the resolved schema's real content changed."""
    _write(
        tmp_path / "svc" / "schemas" / "widget.yaml",
        {"Widget": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )
    _write(
        tmp_path / "svc" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Svc"},
            "x-aip-service-id": "service:svc",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "schemas/widget.yaml#/Widget"}
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )
    config = FilesystemSourceConfig(id="digest-test", root=tmp_path)
    before = run_filesystem_discovery(config)
    digest_before = _outcome_for(before, "openapi.yaml").semantic_input_digest

    # Only the referenced file changes - the root openapi.yaml is byte-identical.
    _write(
        tmp_path / "svc" / "schemas" / "widget.yaml",
        {"Widget": {"type": "object", "properties": {"id": {"type": "integer"}}}},
    )
    after = run_filesystem_discovery(config)
    digest_after = _outcome_for(after, "openapi.yaml").semantic_input_digest

    assert digest_before is not None
    assert digest_after is not None
    assert digest_before != digest_after


def test_asyncapi_payload_ref_inside_an_external_message_document_resolves_relative_to_it(
    tmp_path,
):
    """Regression for a real review finding: a payload $ref declared inside an externally
    referenced message document was resolved relative to the ROOT document's directory instead of
    the message document's own directory, incorrectly rejecting valid cross-file input whenever the
    message and its payload lived one level deeper than the root (e.g. under messages/)."""
    _write(
        tmp_path / "svc" / "messages" / "payload.yaml",
        {"P": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )
    _write(
        tmp_path / "svc" / "messages" / "message.yaml",
        {"Msg": {"name": "Msg", "payload": {"$ref": "payload.yaml#/P"}}},
    )
    _write(
        tmp_path / "svc" / "asyncapi.yaml",
        {
            "asyncapi": "2.6.0",
            "info": {"title": "Svc"},
            "x-aip-service-id": "service:svc",
            "servers": {"broker": {"url": "amqp://x", "protocol": "amqp", "x-aip-broker-id": "b1"}},
            "channels": {
                "svc-q": {
                    "x-aip-destination-kind": "queue",
                    "publish": {"message": {"$ref": "messages/message.yaml#/Msg"}},
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="nested-payload", root=tmp_path))
    outcome = _outcome_for(result, "asyncapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED
    assert len(outcome.model.schemas) == 1
    expected_hash = canonical_sha256_hex(
        {"type": "object", "properties": {"id": {"type": "string"}}}
    )
    assert outcome.model.schemas[0].canonical_hash == expected_hash


def test_a_property_literally_named_description_is_not_stripped_as_an_annotation(tmp_path):
    """Regression for a real review finding: EXCLUDED_SCHEMA_FIELDS filtering was applied to every
    dictionary uniformly, including the 'properties' map itself - so a property literally named
    'description' (a real, arbitrary property name) was silently deleted from the schema, exactly
    as if it were the schema-level `description` annotation keyword."""
    _write(
        tmp_path / "prop-name-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "PropNameService"},
            "x-aip-service-id": "service:propname",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "description": {"type": "string"},
                                                "id": {"type": "string"},
                                            },
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="propname", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED
    expected_hash = canonical_sha256_hex(
        {
            "type": "object",
            "properties": {"description": {"type": "string"}, "id": {"type": "string"}},
        }
    )
    assert outcome.model.schemas[0].canonical_hash == expected_hash


def _same_document_schema_chain(num_schemas: int) -> dict:
    """S0 -> S1 -> ... -> S{num_schemas - 1}, all same-document (`#/...`) refs - a fragment-only
    chain that never crosses a file, so it is invisible to walk_transitive_closure/
    enforce_reference_closure by design and can only be caught by _normalize_schema_node's own
    depth counter."""
    schemas: dict = {}
    for i in range(num_schemas):
        schemas[f"S{i}"] = {"type": "object"}
        if i < num_schemas - 1:
            schemas[f"S{i}"]["properties"] = {"next": {"$ref": f"#/components/schemas/S{i + 1}"}}
    return schemas


def _same_document_chain_openapi_doc(num_schemas: int) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "SameDocChainService"},
        "x-aip-service-id": "service:samedocchain",
        "paths": {
            "/x": {
                "get": {
                    "operationId": "getX",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/S0"}}
                            }
                        }
                    },
                }
            }
        },
        "components": {"schemas": _same_document_schema_chain(num_schemas)},
    }


def test_a_same_document_reference_chain_within_the_depth_limit_is_accepted(tmp_path):
    _write(
        tmp_path / "same-doc-service" / "openapi.yaml", _same_document_chain_openapi_doc(16)
    )  # 16 hops: response -> S0 (1) -> ... -> S15 (16), at the limit

    result = run_filesystem_discovery(FilesystemSourceConfig(id="samedoc-ok", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED


def test_a_same_document_reference_chain_exceeding_the_depth_limit_is_rejected(tmp_path):
    """Regression for a real review finding: enforce_reference_closure's walk_transitive_closure
    deliberately skips fragment-only ($ref within the same document) references entirely, and
    resolve_and_normalize_schema had no depth counter of its own - so a purely same-document chain
    of 21+ hops sailed through map() as ACCEPTED with no REFERENCE_LIMIT_EXCEEDED at all, even
    though ADR 0015 explicitly defines depth as counting every hop, same-file or not."""
    _write(
        tmp_path / "same-doc-service" / "openapi.yaml", _same_document_chain_openapi_doc(17)
    )  # 17 hops: one past the depth-16 limit, entirely within one document

    result = run_filesystem_discovery(FilesystemSourceConfig(id="samedoc-bad", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REFERENCE_LIMIT_EXCEEDED for d in outcome.diagnostics)


def test_a_mixed_cross_file_and_same_document_chain_shares_one_depth_budget(tmp_path):
    """A single cross-file hop into a file that then continues with 16 more same-document hops is
    17 hops total - the depth budget must be shared across the file boundary, not reset to zero
    once a same-document chain begins inside the referenced file."""
    service_dir = tmp_path / "mixed-chain-service"
    # 1 cross-file hop (root -> chain.yaml#/.../S0) + 16 same-document hops (S0 -> ... -> S16,
    # 17 schemas = 16 transitions) = 17 total, one past the depth-16 limit.
    _write(
        service_dir / "schemas" / "chain.yaml",
        {"components": {"schemas": _same_document_schema_chain(17)}},
    )
    _write(
        service_dir / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "MixedChainService"},
            "x-aip-service-id": "service:mixedchain",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "schemas/chain.yaml#/components/schemas/S0"
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="mixed-bad", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REFERENCE_LIMIT_EXCEEDED for d in outcome.diagnostics)


def test_extension_data_is_preserved_intact_in_the_canonical_hash(tmp_path):
    """Regression for a real review finding: EXCLUDED_SCHEMA_FIELDS filtering was still applied
    inside an arbitrary vendor extension's own nested data (any dict was treated as a schema node),
    so a key like "description" nested inside an `x-contract` extension was silently stripped -
    contrary to I1 spec §8.1's "every extension key are retained." Two schemas differing only in an
    extension's nested content must hash differently."""

    def _doc(inner_value: str) -> dict:
        return {
            "openapi": "3.1.0",
            "info": {"title": "ExtService"},
            "x-aip-service-id": "service:ext",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "x-contract": {"description": inner_value},
                                        }
                                    }
                                }
                            }
                        },
                    }
                }
            },
        }

    _write(tmp_path / "ext-service" / "openapi.yaml", _doc("before"))
    before = run_filesystem_discovery(FilesystemSourceConfig(id="ext", root=tmp_path))
    hash_before = _outcome_for(before, "openapi.yaml").model.schemas[0].canonical_hash

    _write(tmp_path / "ext-service" / "openapi.yaml", _doc("after"))
    after = run_filesystem_discovery(FilesystemSourceConfig(id="ext", root=tmp_path))
    hash_after = _outcome_for(after, "openapi.yaml").model.schemas[0].canonical_hash

    assert hash_before != hash_after


def test_a_ref_to_a_whole_document_with_no_fragment_gets_a_synthetic_schema_name(tmp_path):
    """Regression for a real review finding: Schema.name is a required string in the canonical
    model, but a $ref with no fragment (e.g. "other.yaml", resolving to the entire document as the
    schema) has empty definition_pointer_tokens and thus no "last path segment" to use as a name -
    constructing Schema(name=None, ...) raised a pydantic validation error at runtime."""
    _write(
        tmp_path / "whole-doc-service" / "schemas" / "whole.yaml",
        {"type": "object", "properties": {"id": {"type": "string"}}},
    )
    _write(
        tmp_path / "whole-doc-service" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "WholeDocService"},
            "x-aip-service-id": "service:wholedoc",
            "paths": {
                "/x": {
                    "get": {
                        "operationId": "getX",
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "schemas/whole.yaml"}}
                                }
                            }
                        },
                    }
                }
            },
        },
    )

    result = run_filesystem_discovery(FilesystemSourceConfig(id="wholedoc", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.ACCEPTED
    assert outcome.model.schemas[0].name == "<root>"


def test_a_root_document_with_no_references_over_the_byte_budget_is_rejected_end_to_end(tmp_path):
    """Regression for a real review finding: a root document with no references at all (a large
    info.description, no $ref anywhere) was never checked against the 8 MiB budget, since the only
    byte-budget check lived inside a per-reference loop that a reference-free document never
    enters. Proven through the real discovery+adapter pipeline, at the real wired default (not a
    reduced test-only limit)."""
    from app.sources.reference_resolution import DEFAULT_MAX_REFERENCE_BYTES

    service_dir = tmp_path / "big-root-service"
    path = service_dir / "openapi.yaml"
    doc = {
        "openapi": "3.1.0",
        "info": {"title": "BigRootService", "description": "x"},
        "x-aip-service-id": "service:bigroot",
        "paths": {},
    }
    _write(path, doc)
    current_size = len(path.read_bytes())
    # Comfortably over the real default budget - the primitive-level tests already prove exact
    # boundary/boundary+1 precision with a custom max_bytes; this just proves the wired default
    # rejects a realistically oversized root end to end.
    doc["info"]["description"] = "x" * (DEFAULT_MAX_REFERENCE_BYTES - current_size + 1024)
    _write(path, doc)
    assert len(path.read_bytes()) > DEFAULT_MAX_REFERENCE_BYTES

    result = run_filesystem_discovery(FilesystemSourceConfig(id="bigroot", root=tmp_path))
    outcome = _outcome_for(result, "openapi.yaml")

    assert outcome.result is IngestionResult.REJECTED_UNSUPPORTED
    assert any(d.code is DiagnosticCode.REFERENCE_LIMIT_EXCEEDED for d in outcome.diagnostics)
