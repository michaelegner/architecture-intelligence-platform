"""v0.6.3 I2 (#305, spec §4): a source holding an integer outside RFC 8785's safe integer domain is
rejected as a source, with a diagnostic that names where but never the value, instead of aborting the
whole import run. The run is then PARTIAL and commits nothing (the existing commit gate)."""

import pytest
import yaml

from app.common.jcs import CanonicalIntegerDomainError, canonical_json_bytes
from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.inventory import InventoryStatus
from app.sources.model import DiagnosticCode, FilesystemSourceConfig, IngestionResult

BIG = 18446744073709551615
DIGITS = str(BIG)


def _write(path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document))


def _openapi(service: str, schema: dict | None = None) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": service},
        "x-aip-service-id": f"service:{service}",
        "paths": {"/p": {"get": {"operationId": f"get-{service}", "responses": {"200": {}}}}},
        **({"components": {"schemas": {"Thing": schema}}} if schema is not None else {}),
    }


def _asyncapi(service: str, *, payload: dict, message_extra: dict | None = None) -> dict:
    return {
        "asyncapi": "2.6.0",
        "info": {"title": service, "version": "1"},
        "x-aip-service-id": f"service:{service}",
        "servers": {
            "asb": {
                "url": "amqps://asb.example.com",
                "protocol": "amqp",
                "x-aip-broker-id": "asb",
                "bindings": {"amqp": {"virtualHost": "commerce"}},
            }
        },
        "channels": {
            "orders": {
                "x-aip-destination-kind": "queue",
                "publish": {
                    "operationId": f"send-{service}",
                    "message": {"name": "M", "payload": payload, **(message_extra or {})},
                },
            }
        },
    }


def _manifest(service: str, **extra) -> dict:
    return {"service": service, "x-aip-service-id": f"service:{service}", "calls": [], **extra}


def _run(tmp_path):
    return run_filesystem_discovery(FilesystemSourceConfig(id="mixed", root=tmp_path))


def _assert_bad_source_rejected_and_run_partial(result, *, pointer: str):
    assert result.inventory_status is InventoryStatus.PARTIAL
    assert result.commit_eligible is False
    by_result = {}
    for run_outcome in result.source_outcomes.values():
        by_result.setdefault(run_outcome.outcome.result, []).append(run_outcome.outcome)
    assert len(by_result[IngestionResult.ACCEPTED]) >= 1  # the valid source is still evaluated
    [rejected] = by_result[IngestionResult.REJECTED_INVALID]
    assert rejected.semantic_input_digest is None
    assert rejected.model.services == [] and rejected.model.relations == []
    [diagnostic] = rejected.diagnostics
    assert diagnostic.code is DiagnosticCode.DOCUMENT_PARSE_INVALID
    assert f"at {pointer}" in diagnostic.message
    assert DIGITS not in diagnostic.message
    assert all(DIGITS not in d.message for d in result.diagnostics)


def test_canonical_json_bytes_rejects_out_of_domain_integers_without_echoing_them():
    for value in (2**53, -(2**53), BIG):
        with pytest.raises(CanonicalIntegerDomainError) as exc_info:
            canonical_json_bytes({"a": [value]})
        assert str(value) not in str(exc_info.value)
        assert exc_info.value.__cause__ is None


def test_canonical_json_bytes_unchanged_inside_the_domain():
    safe = 2**53 - 1
    assert canonical_json_bytes({"a": safe, "b": -safe, "c": 1.5, "d": True}) == (
        b'{"a":9007199254740991,"b":-9007199254740991,"c":1.5,"d":true}'
    )


def test_openapi_source_with_a_uint64_bound_is_rejected_and_the_good_source_still_evaluated(
    tmp_path,
):
    _write(tmp_path / "good" / "openapi.yaml", _openapi("good"))
    _write(
        tmp_path / "bad" / "openapi.yaml",
        _openapi("bad", {"type": "integer", "maximum": BIG}),
    )
    _assert_bad_source_rejected_and_run_partial(
        _run(tmp_path), pointer="/components/schemas/Thing/maximum"
    )


def test_asyncapi_schema_bound_is_rejected(tmp_path):
    _write(tmp_path / "good" / "openapi.yaml", _openapi("good"))
    _write(
        tmp_path / "bad" / "asyncapi.yaml",
        _asyncapi("bad", payload={"type": "object", "properties": {"n": {"maximum": BIG}}}),
    )
    _assert_bad_source_rejected_and_run_partial(
        _run(tmp_path),
        pointer="/channels/orders/publish/message/payload/properties/n/maximum",
    )


def test_asyncapi_message_level_integer_is_rejected(tmp_path):
    # Outside the payload schema: reaches the message-document digest, not schema normalization.
    _write(tmp_path / "good" / "openapi.yaml", _openapi("good"))
    _write(
        tmp_path / "bad" / "asyncapi.yaml",
        _asyncapi("bad", payload={"type": "object"}, message_extra={"x-big": BIG}),
    )
    _assert_bad_source_rejected_and_run_partial(
        _run(tmp_path), pointer="/channels/orders/publish/message/x-big"
    )


def test_manifest_source_is_rejected(tmp_path):
    _write(tmp_path / "good" / "openapi.yaml", _openapi("good"))
    _write(tmp_path / "bad" / "architecture.yaml", _manifest("bad", x_big=BIG))
    result = _run(tmp_path)
    assert result.inventory_status is InventoryStatus.PARTIAL
    assert result.commit_eligible is False
    rejected = [
        ro.outcome
        for ro in result.source_outcomes.values()
        if ro.outcome.result is IngestionResult.REJECTED_INVALID
    ]
    assert len(rejected) == 1 and rejected[0].semantic_input_digest is None
    assert all(DIGITS not in d.message for d in result.diagnostics)


def test_the_diagnostic_is_deterministic_and_independent_of_key_order(tmp_path):
    schema = {"type": "integer", "maximum": BIG, "minimum": -BIG}
    _write(tmp_path / "bad" / "openapi.yaml", _openapi("bad", schema))
    first = _run(tmp_path)
    reordered = _openapi("bad", dict(reversed(list(schema.items()))))
    (tmp_path / "bad" / "openapi.yaml").write_text(yaml.safe_dump(reordered, sort_keys=False))
    second = _run(tmp_path)

    def messages(result):
        return sorted(
            d.message for ro in result.source_outcomes.values() for d in ro.outcome.diagnostics
        )

    assert messages(first) == messages(second)
    assert "/components/schemas/Thing/maximum" in messages(first)[0]


def test_integers_at_the_boundary_keep_their_canonical_identity(tmp_path):
    """2**53 - 1 is inside the domain: accepted, and hashed exactly as the same document with the
    value written as a float of the same magnitude would be (no coercion path was added)."""
    _write(
        tmp_path / "ok" / "openapi.yaml",
        _openapi("ok", {"type": "integer", "maximum": 2**53 - 1, "flag": True, "ratio": 1.5}),
    )
    result = _run(tmp_path)
    assert result.inventory_status is InventoryStatus.COMPLETE
    assert result.commit_eligible is True
    [run_outcome] = result.source_outcomes.values()
    assert run_outcome.outcome.result is IngestionResult.ACCEPTED
    assert run_outcome.outcome.semantic_input_digest is not None


def test_a_rejected_source_changes_nothing_when_the_guard_is_removed(tmp_path, monkeypatch):
    """Guard proof: with the containment removed, the same run raises instead of reporting."""
    from app.ingestion import orchestrator

    _write(tmp_path / "bad" / "openapi.yaml", _openapi("bad", {"type": "integer", "maximum": BIG}))

    class _NeverMatches(Exception):
        pass

    monkeypatch.setattr(orchestrator, "CanonicalIntegerDomainError", _NeverMatches)
    with pytest.raises(CanonicalIntegerDomainError):
        _run(tmp_path)


def test_kubernetes_snapshot_with_an_out_of_domain_service_port_is_rejected(tmp_path):
    """The Kubernetes mapping hashes its resource projection with the same canonicalizer, and only
    checks that `spec.ports[].port` is an integer, so this failure class is reachable there too."""
    from app.ingestion.kubernetes_discoverer import KubernetesSourceDiscoverer
    from app.ingestion.orchestrator import run_discovery
    from tests.unit.test_ingestion_kubernetes_adapter import (
        _config,
        _deployment_and_pod_yaml,
        _write_bundle,
    )

    documents = list(yaml.safe_load_all(_deployment_and_pod_yaml()))
    documents[2]["spec"]["ports"] = [{"port": BIG}]
    _write_bundle(tmp_path, resource_bytes=yaml.safe_dump_all(documents).encode())

    result = run_discovery(KubernetesSourceDiscoverer(_config(tmp_path)))

    assert result.inventory_status is InventoryStatus.PARTIAL
    assert result.commit_eligible is False
    [run_outcome] = result.source_outcomes.values()
    assert run_outcome.outcome.result is IngestionResult.REJECTED_INVALID
    assert run_outcome.outcome.semantic_input_digest is None
    assert all(DIGITS not in d.message for d in result.diagnostics)
