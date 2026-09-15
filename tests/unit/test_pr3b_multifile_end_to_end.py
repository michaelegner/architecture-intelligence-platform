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
