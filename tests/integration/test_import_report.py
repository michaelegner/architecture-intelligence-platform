"""v0.5.0 I5 finding F2: the I1 §10 import report through the real `POST /api/import` endpoint.

Every outcome the report must distinguish is driven through the real API on real Neo4j: COMPLETE,
PARTIAL (a rejected source), FAILED (no enumeration), REJECTED_CONFLICT, removal, accepted and
stale tombstones, and a rejected Kubernetes bundle. Each response is validated against the
committed `schemas/import/v0.5/import-report.schema.json`, and its `runs` never carry an absolute
path of the temporary roots or a diagnostic message.
"""

import hashlib
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
import yaml
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.ingestion.import_report_schema import IMPORT_REPORT_SCHEMA_PATH
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.identity import source_instance_id
from app.sources.kubernetes_envelope import EXPECTED_RESOURCE_TYPES
from app.sources.model import SourceKind

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"
_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)
SCHEMA = json.loads(IMPORT_REPORT_SCHEMA_PATH.read_text())


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _post_import(driver, sources: dict) -> dict:
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = None
    app.state.architecture_intelligence_service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=_PRODUCER
    )
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {"sources": sources, "graph": {"uri": "bolt://ignored:7687", "database": DATABASE}}
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored", openai_api_key=None),
    )
    response = TestClient(app).post("/api/import")
    assert response.status_code == 200, response.text
    body = response.json()
    jsonschema.validate(instance=body, schema=SCHEMA)
    return body


def _assert_runs_leak_nothing(body: dict, *roots: Path) -> None:
    runs = json.dumps(body["runs"])
    for root in roots:
        assert str(root) not in runs
        assert str(root.resolve()) not in runs
    assert '"message"' not in runs


def _only_run(body: dict) -> dict:
    [run] = body["runs"]
    return run


def _codes(diagnostics: list[dict]) -> set[str]:
    return {d["code"] for d in diagnostics}


def test_complete_run_reports_every_source_result_and_the_committed_revision(driver, tmp_path):
    root = tmp_path / "examples"
    shutil.copytree(EXAMPLES_DIR, root)
    body = _post_import(driver, {"directories": [{"id": "report-complete", "root": str(root)}]})

    run = _only_run(body)
    assert body["report_version"] == "aip-import-report/1"
    assert run["kind"] == "filesystem" and run["configured_source_id"] == "report-complete"
    assert run["inventory_status"] == "COMPLETE" and run["committed"] is True
    assert run["inventory_revision"].startswith("urn:aip:inventory-revision:")
    assert run["discovery_scope_id"].startswith("urn:aip:discovery-scope:")
    assert len(run["source_results"]) == len(body["sources"]) == 6
    assert {r["result"] for r in run["source_results"]} <= {"ACCEPTED", "ACCEPTED_WITH_LIMITATIONS"}
    # Locators are relative to the configured root, never absolute host paths.
    assert all(not r["locator"].startswith("/") for r in run["source_results"])
    assert {r["source_instance_id"] for r in run["source_results"]} == set(body["sources"])
    # I1 §10's dialects, identities, emitted counts and committed effects, per source.
    results = {r["locator"]: r for r in run["source_results"]}
    product = results["product-service/openapi.yaml"]
    assert product["source_kind"] == "filesystem"
    assert product["adapter_identity"] == "openapi-adapter@1"
    assert product["dialect_version"].startswith("3.")
    assert len(product["semantic_input_digest"]) == 64
    assert product["service_ids"] == ["service:product-service"]
    assert product["emitted"]["services"] == 1 and product["emitted"]["operations"] > 0
    # The first import adds every claim the source emits, by identity.
    effects = product["effects"]
    assert effects["graph_revision_advanced"] is True
    assert "service:product-service" in effects["added"]["node_ids"]
    assert any(
        k.startswith("PROVIDES:service:product-service:") for k in effects["added"]["relation_keys"]
    )
    assert effects["added"]["internal_count"] > 0  # its Evidence, counted but never listed
    assert not any(i.startswith("evidence:") for i in effects["added"]["node_ids"])
    assert effects["changed"] == effects["expired"] == effects["ownership_removed"] == _EMPTY
    _assert_runs_leak_nothing(body, tmp_path)


_EMPTY = {"node_ids": [], "relation_keys": [], "internal_count": 0}
_NO_EFFECTS = {
    "graph_revision_advanced": False,
    "added": _EMPTY,
    "changed": _EMPTY,
    "expired": _EMPTY,
    "ownership_removed": _EMPTY,
}


def test_unchanged_replay_has_an_empty_canonical_effect_set(driver, tmp_path):
    """I1 §10: the report's effects are canonical, not write counts. An unchanged replay still
    executes idempotent MERGEs (`sources` counts them), but its canonical effect set is empty."""
    root = tmp_path / "examples"
    shutil.copytree(EXAMPLES_DIR, root)
    config = {"directories": [{"id": "report-replay", "root": str(root)}]}
    _post_import(driver, config)

    replay = _post_import(driver, config)
    run = _only_run(replay)
    assert run["committed"] is True
    assert sum(stats["nodes_written"] for stats in replay["sources"].values()) > 0
    for result in run["source_results"]:
        assert result["effects"] == _NO_EFFECTS, result["locator"]


def test_property_only_change_is_a_changed_effect_by_identity(driver, tmp_path):
    root = tmp_path / "examples"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    config = {"directories": [{"id": "report-changed", "root": str(root)}]}
    _post_import(driver, config)

    openapi = root / "product-service" / "openapi.yaml"
    openapi.write_text(openapi.read_text().replace('version: "1.0.0"', 'version: "2.0.0"'))
    [result] = _only_run(_post_import(driver, config))["source_results"]
    effects = result["effects"]
    assert effects["graph_revision_advanced"] is True
    assert effects["changed"]["node_ids"] == ["service:product-service"]
    assert effects["added"] == effects["expired"] == effects["ownership_removed"] == _EMPTY


def test_partial_run_reports_the_rejected_source_although_nothing_commits(driver, tmp_path):
    root = tmp_path / "partial"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    unbound = root / "unbound" / "openapi.yaml"
    unbound.parent.mkdir()
    unbound.write_text(
        (EXAMPLES_DIR / "product-service" / "openapi.yaml")
        .read_text()
        .replace("x-aip-service-id: service:product-service\n", "")
    )
    body = _post_import(driver, {"directories": [{"id": "report-partial", "root": str(root)}]})

    run = _only_run(body)
    assert body["committed"] is False and body["sources"] == {}
    assert run["inventory_status"] == "PARTIAL" and run["committed"] is False
    assert run["inventory_revision"] is None
    results = {r["locator"]: r for r in run["source_results"]}
    assert results["unbound/openapi.yaml"]["result"] == "REJECTED_UNSUPPORTED"
    assert _codes(results["unbound/openapi.yaml"]["diagnostics"]) == {"SERVICE_IDENTITY_UNRESOLVED"}
    assert results["product-service/openapi.yaml"]["result"] == "ACCEPTED"
    # A run that does not commit still reports what each source emitted, but no effects (I1 §6).
    assert results["product-service/openapi.yaml"]["emitted"]["services"] == 1
    assert results["unbound/openapi.yaml"]["service_ids"] == []
    assert all(r["effects"] is None for r in run["source_results"])
    assert run["removals"] == []
    _assert_runs_leak_nothing(body, tmp_path)


def test_failed_run_reports_the_missing_root_without_its_absolute_path(driver, tmp_path):
    missing = tmp_path / "does-not-exist"
    body = _post_import(driver, {"directories": [{"id": "report-failed", "root": str(missing)}]})

    run = _only_run(body)
    assert run["inventory_status"] == "FAILED" and run["committed"] is False
    assert run["source_results"] == []
    [diagnostic] = run["diagnostics"]
    assert diagnostic["code"] == "SOURCE_ROOT_UNAVAILABLE"
    # The discoverer names the root only in its message, which the report never exposes.
    assert diagnostic["source_pointer"] is None
    _assert_runs_leak_nothing(body, tmp_path)


def test_conflicting_identity_is_a_distinguishable_rejected_conflict(driver, tmp_path):
    root = tmp_path / "conflict"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    sid = source_instance_id(
        configured_source_id="report-conflict",
        source_kind=SourceKind.FILESYSTEM,
        normalized_root_document_path="product-service/openapi.yaml",
    )
    bindings = root / "bindings" / "architecture-identity-bindings.yaml"
    bindings.parent.mkdir()
    bindings.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "ArchitectureIdentityBindings",
                "metadata": {"id": "conflicting-bindings", "revision": "1"},
                "bindings": [
                    {"sourceInstanceId": str(sid), "pointerPrefix": "", "serviceId": "service:x"}
                ],
            }
        )
    )
    body = _post_import(driver, {"directories": [{"id": "report-conflict", "root": str(root)}]})

    run = _only_run(body)
    assert run["inventory_status"] == "PARTIAL" and run["committed"] is False
    [result] = run["source_results"]
    assert result["source_instance_id"] == str(sid)
    assert result["result"] == "REJECTED_CONFLICT"
    assert "SERVICE_IDENTITY_CONFLICT" in _codes(result["diagnostics"])
    _assert_runs_leak_nothing(body, tmp_path)


def test_removal_and_accepted_and_stale_tombstones_are_reported(driver, tmp_path):
    root_a = tmp_path / "root-a"
    shutil.copytree(EXAMPLES_DIR / "product-service", root_a / "product-service")
    root_b = tmp_path / "root-b"
    root_b.mkdir()

    first = _only_run(_post_import(driver, {"directories": [{"id": "tomb", "root": str(root_a)}]}))
    [removed_sid] = [r["source_instance_id"] for r in first["source_results"]]

    second = _only_run(_post_import(driver, {"directories": [{"id": "tomb", "root": str(root_b)}]}))
    assert second["committed"] is True
    assert second["removals"] == []  # the scope changed: removal denied

    def tombstone_file(name: str, expected_revision: str) -> Path:
        path = tmp_path / name
        path.write_text(
            yaml.safe_dump(
                {
                    "tombstones": [
                        {
                            "target_source_instance_id": removed_sid,
                            "discovery_scope_id": second["discovery_scope_id"],
                            "expected_prior_inventory_revision": expected_revision,
                            "scope_definition_digest": second["scope_definition_digest"],
                            "actor": "operator@example.com",
                            "reason": "decommissioned",
                            "tombstone_revision": "1",
                        }
                    ]
                }
            )
        )
        return path

    stale = tombstone_file("stale.yaml", "urn:aip:inventory-revision:" + "0" * 64)
    denied = _only_run(
        _post_import(
            driver,
            {"directories": [{"id": "tomb", "root": str(root_b)}], "tombstones": [str(stale)]},
        )
    )
    assert denied["removals"] == []
    assert denied["tombstones"] == [
        {
            "target_source_instance_id": removed_sid,
            "tombstone_revision": "1",
            "accepted": False,
            "reason": "STALE_PRIOR_REVISION",
        }
    ]
    assert "TOMBSTONE_STALE" in _codes(denied["diagnostics"])

    valid = tombstone_file("valid.yaml", denied["inventory_revision"])
    body = _post_import(
        driver, {"directories": [{"id": "tomb", "root": str(root_b)}], "tombstones": [str(valid)]}
    )
    accepted = _only_run(body)
    [removal] = accepted["removals"]
    assert removal["source_instance_id"] == removed_sid
    # The removal's canonical effects: everything the removed source solely owned expires (I1 §10).
    expired = removal["effects"]["expired"]
    assert "service:product-service" in expired["node_ids"]
    assert any(k.startswith("PROVIDES:service:product-service:") for k in expired["relation_keys"])
    assert removal["effects"]["added"] == removal["effects"]["changed"] == _EMPTY
    assert accepted["tombstones"][0]["accepted"] is True
    assert accepted["tombstones"][0]["reason"] is None
    _assert_runs_leak_nothing(body, tmp_path)


def test_malformed_tombstone_target_cannot_fail_the_committed_report(driver, tmp_path):
    """A rejected tombstone's diagnostic carries its operator-supplied target. After the run has
    committed, a target that is not a source id must be reported as null, not fail the report."""
    root = tmp_path / "root"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    first = _only_run(
        _post_import(driver, {"directories": [{"id": "malformed", "root": str(root)}]})
    )

    tombstones = tmp_path / "malformed.yaml"
    tombstones.write_text(
        yaml.safe_dump(
            {
                "tombstones": [
                    {
                        "target_source_instance_id": "../../not a source id",
                        "discovery_scope_id": first["discovery_scope_id"],
                        "expected_prior_inventory_revision": "urn:aip:inventory-revision:"
                        + "0" * 64,
                        "scope_definition_digest": first["scope_definition_digest"],
                        "actor": "operator@example.com",
                        "reason": "typo",
                        "tombstone_revision": "1",
                    }
                ]
            }
        )
    )
    body = _post_import(
        driver,
        {"directories": [{"id": "malformed", "root": str(root)}], "tombstones": [str(tombstones)]},
    )

    run = _only_run(body)
    assert run["committed"] is True
    assert run["tombstones"][0]["target_source_instance_id"] == "../../not a source id"
    [stale] = [d for d in run["diagnostics"] if d["code"] == "TOMBSTONE_STALE"]
    assert stale["source_instance_id"] is None
    _assert_runs_leak_nothing(body, tmp_path)


def _namespaceless_bundle(root: Path) -> dict:
    resources = yaml.safe_dump(
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "checkout"},
            "spec": {"template": {"metadata": {"labels": {"app": "checkout"}}}},
        }
    ).encode()
    root.mkdir()
    (root / "resources.yaml").write_bytes(resources)
    config = {
        "id": "report-k8s",
        "root": str(root),
        "envelope_relative_path": "envelope.yaml",
        "configured_scope_id": "report-k8s-scope",
        "cluster_uid": "report-k8s-cluster",
        "evidence_mode": "DECLARED_MANIFEST",
        "authorized_producer": "report-producer",
        "authority_record": "report-authority",
    }
    envelope = {
        "apiVersion": "aip.dev/v1",
        "kind": "KubernetesSourceSnapshot",
        "metadata": {
            "id": "report-k8s-snapshot",
            "revision": "1",
            "producer": "report-producer",
            "capturedAt": "2026-09-25T00:00:00Z",
        },
        "source": {
            "configuredSourceId": "report-k8s",
            "configuredScopeId": "report-k8s-scope",
            "clusterUid": "report-k8s-cluster",
            "clusterIdentityEvidenceRef": "report-cluster-evidence",
            "mode": "DECLARED_MANIFEST",
        },
        "scope": {"namespaces": ["checkout"], "resourceTypes": sorted(EXPECTED_RESOURCE_TYPES)},
        "completeness": {
            "status": "COMPLETE",
            "authorityRef": "report-authority",
            "expectedPriorInventoryRevision": None,
        },
        "files": [{"path": "resources.yaml", "sha256": hashlib.sha256(resources).hexdigest()}],
    }
    (root / "envelope.yaml").write_text(yaml.safe_dump(envelope))
    return config


def test_rejected_kubernetes_bundle_reports_its_result_and_code(driver, tmp_path):
    config = _namespaceless_bundle(tmp_path / "bundle")
    body = _post_import(driver, {"directories": [], "clusters": [config]})

    run = _only_run(body)
    assert run["kind"] == "kubernetes" and run["configured_source_id"] == "report-k8s"
    assert run["committed"] is False
    [result] = run["source_results"]
    assert result["result"] == "REJECTED_INVALID"
    assert "K8S_RESOURCE_INVALID" in _codes(result["diagnostics"]) | _codes(run["diagnostics"])
    _assert_runs_leak_nothing(body, tmp_path)
