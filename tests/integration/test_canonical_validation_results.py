"""v0.5.0 I5 finding F1: a canonically invalid discovery run is a per-source result, never a 500.

Slice 5's Quarkus L2/L5/L3 steps omitted `rest-fights/openapi.yml` while keeping its
`architecture.yaml`. The manifest's CALLS then had no source Service, and the canonical-validation
failure escaped `POST /api/import` as HTTP 500. Two layers now prevent that, and each is tested here
through the real API on real Neo4j:
- the manifest adapter rejects an undeclared caller (`MANIFEST_CALL_SOURCE_UNRESOLVED`);
- canonical validation runs in discovery, attributing any violation to the sources that emitted
  the offending elements (`CANONICAL_MODEL_INVALID`), as a safety net for any adapter defect.

In both cases the run is PARTIAL, every source keeps exactly one result (I1 §10), and the committed
graph is unchanged (I1 §6).
"""

import json
from pathlib import Path

import jsonschema
import pytest
import yaml
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical.model import Service
from app.ingestion.import_report_schema import IMPORT_REPORT_SCHEMA_PATH
from app.ingestion.manifest_adapter import ManifestSourceAdapter
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings

DATABASE = "neo4j"
SCHEMA = json.loads(IMPORT_REPORT_SCHEMA_PATH.read_text())
_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)
_GRAPH_QUERY = (
    "MATCH (n) OPTIONAL MATCH (n)-[r]->(m) "
    "RETURN n.id AS node, properties(n) AS props, type(r) AS rel, m.id AS target "
    "ORDER BY node, rel, target"
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _post_import(driver, root: Path) -> dict:
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = None
    app.state.architecture_intelligence_service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=_PRODUCER
    )
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {
                "sources": {"directories": [{"id": "f1", "root": str(root)}]},
                "graph": {"uri": "bolt://ignored:7687", "database": DATABASE},
            }
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored", openai_api_key=None),
    )
    response = TestClient(app).post("/api/import")
    assert response.status_code == 200, response.text
    body = response.json()
    jsonschema.validate(instance=body, schema=SCHEMA)
    return body


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document))


def _caller_and_callee(root: Path) -> Path:
    """rest-fights' shape in miniature: the caller's own OpenAPI declares its Service, and its
    manifest declares a CALLS to the callee. Returns the caller's OpenAPI path."""
    _write(
        root / "callee" / "openapi.yaml",
        {
            "openapi": "3.1.0",
            "info": {"title": "Callee", "version": "1"},
            "x-aip-service-id": "service:callee",
            "paths": {"/thing": {"get": {"operationId": "getThing", "responses": {"204": {}}}}},
        },
    )
    caller_openapi = root / "caller" / "openapi.yaml"
    _write(
        caller_openapi,
        {
            "openapi": "3.1.0",
            "info": {"title": "Caller", "version": "1"},
            "x-aip-service-id": "service:caller",
            "paths": {"/fight": {"get": {"operationId": "getFight", "responses": {"204": {}}}}},
        },
    )
    _write(
        root / "caller" / "architecture.yaml",
        {
            "service": "caller",
            "x-aip-service-id": "service:caller",
            "calls": [{"service": "service:callee", "operationId": "getThing"}],
        },
    )
    return caller_openapi


def _graph(driver) -> list[dict]:
    with driver.session(database=DATABASE) as session:
        return [record.data() for record in session.run(_GRAPH_QUERY)]


def _results(body: dict) -> dict[str, dict]:
    [run] = body["runs"]
    return {result["locator"]: result for result in run["source_results"]}


def _codes(result: dict) -> set[str]:
    return {diagnostic["code"] for diagnostic in result["diagnostics"]}


def test_manifest_without_its_callers_openapi_is_rejected_not_a_500(driver, tmp_path):
    root = tmp_path / "declarations"
    caller_openapi = _caller_and_callee(root)
    first = _post_import(driver, root)
    assert first["committed"] is True
    before = _graph(driver)

    caller_openapi.unlink()  # Slice 5's L2 shape: X's OpenAPI omitted, its manifest kept
    body = _post_import(driver, root)

    [run] = body["runs"]
    assert run["inventory_status"] == "PARTIAL" and run["committed"] is False
    results = _results(body)
    assert set(results) == {"callee/openapi.yaml", "caller/architecture.yaml"}
    manifest = results["caller/architecture.yaml"]
    assert manifest["result"] == "REJECTED_UNSUPPORTED"
    assert _codes(manifest) == {"MANIFEST_CALL_SOURCE_UNRESOLVED"}
    assert manifest["diagnostics"][0]["source_pointer"] == "/x-aip-service-id"
    assert manifest["emitted"]["relations"] == 0  # nothing minted, not even the CALLS
    assert results["callee/openapi.yaml"]["result"] == "ACCEPTED"
    assert _graph(driver) == before  # I1 §6: a PARTIAL run preserves the prior state


def test_canonical_validation_rejects_the_emitting_source_when_an_adapter_misses_it(
    driver, tmp_path, monkeypatch
):
    """The safety net: simulate an adapter defect by hiding the missing caller from the manifest
    adapter's own check. The merged model's dangling CALLS is then caught by canonical validation
    in discovery and attributed to the manifest, instead of escaping the import."""
    real_map = ManifestSourceAdapter.map

    def map_with_a_defective_caller_check(self, loaded, *, upstream_model, **kwargs):
        fooled = upstream_model.model_copy(
            update={
                "services": [
                    *upstream_model.services,
                    Service(id="service:caller", name="caller"),
                ]
            }
        )
        return real_map(self, loaded, upstream_model=fooled, **kwargs)

    monkeypatch.setattr(ManifestSourceAdapter, "map", map_with_a_defective_caller_check)
    root = tmp_path / "declarations"
    caller_openapi = _caller_and_callee(root)
    assert _post_import(driver, root)["committed"] is True
    before = _graph(driver)

    caller_openapi.unlink()
    body = _post_import(driver, root)

    [run] = body["runs"]
    assert run["inventory_status"] == "PARTIAL" and run["committed"] is False
    results = _results(body)
    manifest = results["caller/architecture.yaml"]
    assert manifest["result"] == "REJECTED_INVALID"
    assert _codes(manifest) == {"CANONICAL_MODEL_INVALID"}
    # The pointer names the offending relation by its element id.
    [diagnostic] = manifest["diagnostics"]
    assert diagnostic["source_pointer"].startswith("CALLS:service:caller:operation:service:callee:")
    assert diagnostic["source_instance_id"] == manifest["source_instance_id"]
    assert results["callee/openapi.yaml"]["result"] == "ACCEPTED"
    assert "CANONICAL_MODEL_INVALID" in {d["code"] for d in run["diagnostics"]}
    assert _graph(driver) == before
