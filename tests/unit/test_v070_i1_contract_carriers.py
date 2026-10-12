"""v0.7.0 I1.2: the OpenAPI adapter's internal API-contract carriers, the import-request gate in the
orchestrator, and that a no-gateway run is untouched (I1.1 contract §3, §6; I1 spec §3.6 amended)."""

import json
from pathlib import Path

import yaml

from app.canonical import ids
from app.canonical.api_contracts import (
    CONTRACT_VERSION_LIMITATION,
    api_contract_id,
    api_contract_version_id,
)
from app.canonical.merge import merge_models
from app.canonical.model import ArchitectureModel
from app.ingestion.openapi_adapter import OpenApiSourceAdapter
from app.ingestion.orchestrator import run_filesystem_discovery
from app.settings import SourcesConfig
from app.sources.migration_mappings import EMPTY_SHARED_IDENTITY_INDEX
from app.sources.model import (
    ApisixSourceConfig,
    FilesystemSourceConfig,
    LoadedSource,
    SourceDescriptor,
    SourceKind,
)
from app.sources.service_identity import resolve_service_identity

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i1-vectors/ids.json"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
SOURCE_INSTANCE_ID = "urn:aip:source:filesystem:abc123"


class _Resolver:
    def resolve(self, *, source_instance_id, construct_pointer, extension_value):
        return resolve_service_identity(
            source_instance_id=source_instance_id,
            construct_pointer=construct_pointer,
            extension_value=extension_value,
            configured_mappings=(),
            manifest_bindings=(),
        )


def _doc(version: object = "1.4.0", *, with_version: bool = True) -> dict:
    info: dict = {"title": "Orders"}
    if with_version:
        info["version"] = version
    return {
        "openapi": "3.1.0",
        "info": info,
        "x-aip-service-id": "service:orders",
        "paths": {
            "/orders": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/orders/{id}": {"get": {"responses": {"200": {"description": "ok"}}}},
        },
    }


def _map(document: dict):
    descriptor = SourceDescriptor(
        source_instance_id=SOURCE_INSTANCE_ID,
        source_kind=SourceKind.FILESYSTEM,
        locator="orders.yaml",
        discovery_scope_id="urn:aip:discovery-scope:" + "b" * 64,
        scope_definition_digest="c" * 64,
        content_sha256="d" * 64,
        semantic_input_digest="",
        mapping_context_digest="",
        adapter_identity="",
        mapping_rule_id="",
        mapping_rule_version="",
    )
    return OpenApiSourceAdapter().map(
        LoadedSource(descriptor=descriptor, document=document),
        service_identity=_Resolver(),
        shared_identity=EMPTY_SHARED_IDENTITY_INDEX,
        upstream_model=ArchitectureModel(),
        mapping_context_digest="e" * 64,
    )


def test_contract_ids_match_the_frozen_vectors() -> None:
    by_id = {v["id"]: v for v in json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]}
    v8, v9 = by_id["V08"], by_id["V09"]
    contract_id = api_contract_id(v8["inputs"]["openapi_source_instance_id"])
    assert contract_id == v8["expected"]
    assert api_contract_version_id(contract_id, v9["inputs"]["info_version"]) == v9["expected"]


def test_adapter_builds_one_contract_one_version_and_associations() -> None:
    outcome = _map(_doc())
    model = outcome.model
    [contract] = model.api_contracts
    [version] = model.api_contract_versions
    assert contract.id == api_contract_id(SOURCE_INSTANCE_ID)
    assert contract.limitations == []
    assert version.id == api_contract_version_id(contract.id, "1.4.0")
    assert version.contract_id == contract.id
    op_ids = sorted(o.id for o in model.operations)
    assert op_ids == sorted(
        [
            ids.operation_id("service:orders", "GET", "/orders"),
            ids.operation_id("service:orders", "GET", "/orders/{id}"),
        ]
    )  # fmt: skip - Operation ids are exactly the pre-v0.7 ones
    by_kind: dict[str, list[str]] = {}
    for association in model.api_contract_associations:
        assert association.contract_version_id == version.id
        assert association.evidence_ids == [model.provenance[0].id]
        by_kind.setdefault(association.kind, []).append(association.target_id)
    assert sorted(by_kind["OPERATION_IN_CONTRACT_VERSION"]) == op_ids
    assert by_kind["CONTRACT_VERSION_DECLARED_FOR_SERVICE"] == ["service:orders"]
    ids_ = [a.id for a in model.api_contract_associations]
    assert ids_ == sorted(ids_) and len(set(ids_)) == len(ids_)


def test_absent_empty_or_non_string_version_mints_no_version() -> None:
    for document in (
        _doc(with_version=False), _doc(""), _doc(None), _doc(1.0), _doc(2), _doc(True), _doc(["1"])
    ):  # fmt: skip
        outcome = _map(document)
        model = outcome.model
        assert outcome.result.value == "ACCEPTED"  # the source result is never changed
        assert outcome.diagnostics == ()
        assert [s.version for s in outcome.model.services] in ([None], [""])
        assert model.api_contract_versions == []
        assert model.api_contract_associations == []
        [contract] = model.api_contracts
        assert contract.limitations == [CONTRACT_VERSION_LIMITATION]


def test_merge_models_dedupes_carriers_by_id() -> None:
    model = _map(_doc()).model
    merged = merge_models([model, model])
    assert len(merged.api_contracts) == 1
    assert len(merged.api_contract_versions) == 1
    assert len(merged.api_contract_associations) == len(model.api_contract_associations)


def _write_example(root: Path) -> FilesystemSourceConfig:
    root.mkdir(parents=True, exist_ok=True)
    (root / "orders").mkdir(exist_ok=True)
    (root / "orders" / "openapi.yaml").write_text(yaml.safe_dump(_doc()))
    return FilesystemSourceConfig(id="orders", root=root)


def test_run_without_gateway_keeps_no_carriers_and_the_pre_v070_digest(tmp_path) -> None:
    config = _write_example(tmp_path / "src")
    default = run_filesystem_discovery(config)
    assert default.merged_model.operations, "the fixture must really be discovered"
    disabled = run_filesystem_discovery(config, api_contract_associations=False)
    for run in (default, disabled):
        assert run.merged_model.api_contracts == []
        for outcome in run.source_outcomes.values():
            assert outcome.outcome.model.api_contract_versions == []
            assert outcome.outcome.model.api_contract_associations == []
    digests = lambda r: {k: v.outcome.semantic_input_digest for k, v in r.source_outcomes.items()}
    assert digests(default) == digests(disabled)


def test_run_with_gateway_configured_keeps_carriers_and_changes_the_digest(tmp_path) -> None:
    config = _write_example(tmp_path / "src")
    off = run_filesystem_discovery(config)
    on = run_filesystem_discovery(config, api_contract_associations=True)
    assert len(on.merged_model.api_contracts) == 1
    assert len(on.merged_model.api_contract_versions) == 1
    assert on.merged_model.api_contract_associations
    # Same document, different mapping context: the replay no-op must not swallow the toggle.
    [off_digest] = {o.outcome.semantic_input_digest for o in off.source_outcomes.values()}
    [on_digest] = {o.outcome.semantic_input_digest for o in on.source_outcomes.values()}
    assert off_digest != on_digest
    # Operation ids are identical either way.
    assert sorted(o.id for o in off.merged_model.operations) == sorted(
        o.id for o in on.merged_model.operations
    )
    # Other model content is untouched by the gate.
    assert off.merged_model.relations == on.merged_model.relations
    assert off.merged_model.services == on.merged_model.services


def test_sources_config_defaults_to_no_gateways_and_accepts_a_registration(tmp_path) -> None:
    assert SourcesConfig().gateways == []
    gateway = ApisixSourceConfig(id="apisix-prod", root=tmp_path, gateway_instance_id="gw-prod-1")
    assert gateway.capture_relative_path == "apisix-capture.json"
    assert gateway.resolved_scope_id == "apisix-prod"
    assert gateway.resolved_stable_target_identity == "urn:aip:apisix-gateway:gw-prod-1"
    assert SourcesConfig(gateways=[gateway]).gateways == [gateway]


def test_a_non_string_version_is_accepted_through_a_real_discovery_run(tmp_path) -> None:
    root = tmp_path / "src"
    (root / "orders").mkdir(parents=True)
    (root / "orders" / "openapi.yaml").write_text(yaml.safe_dump(_doc(1.0)))
    for flag in (False, True):
        run = run_filesystem_discovery(
            FilesystemSourceConfig(id="orders", root=root), api_contract_associations=flag
        )
        assert run.commit_eligible
        [outcome] = run.source_outcomes.values()
        assert outcome.outcome.result.value == "ACCEPTED"
        assert [s.version for s in run.merged_model.services] == [None]
        assert len(run.merged_model.api_contracts) == (1 if flag else 0)
        assert run.merged_model.api_contract_versions == []
