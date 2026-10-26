"""v0.8 I2a B5, B6 and Q1: the EventCatalog promise record against a real Neo4j, through the real
import request - internal carriers only, the `event_catalog_v1` snapshot block, replay as a
semantic no-op, replacement on a lookup-only change (D12), a rejected catalog keeping the previous
record, retirement of a dropped registration, and the duplicate id / environment conflict.
Integration because reconciliation, retirement and the snapshot projection exist only in the real
import into Neo4j.
"""

import json
import shutil
from pathlib import Path

import jsonschema
import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state
from app.graph.import_runs import run_all_configured_sources
from app.graph.labels import NODE_LABELS
from app.ingestion.import_report import build_import_report
from app.settings import SourcesConfig
from app.sources.model import DiagnosticCode, EventCatalogSourceConfig, IngestionResult

DATABASE = "neo4j"
REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "docs/specifications/0.8.0/i1-evidence"
SCHEMA = json.loads((REPO / "schemas/import/v0.5/import-report.schema.json").read_text())
LABELS = ("CatalogPromise", "CatalogMembership", "CatalogEventTopic", "CatalogEvidence")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _catalog(tmp_path: Path, source_id: str = "sokol111-catalog", environment: str = "local"):
    root = tmp_path / f"{source_id}-{environment}"
    if not root.exists():
        shutil.copytree(PACKAGE / "catalog", root / "catalog")
        shutil.copy(PACKAGE / "event-topic-lookup.json", root / "event-topic-lookup.json")
    return EventCatalogSourceConfig(id=source_id, root=root, environment=environment)


def _request(driver, *catalogs: EventCatalogSourceConfig):
    import_id, runs = run_all_configured_sources(
        SourcesConfig(directories=[], event_catalogs=list(catalogs)),
        driver=driver,
        database=DATABASE,
    )
    report = build_import_report(import_id, runs)
    jsonschema.validate(json.loads(report.model_dump_json()), SCHEMA)
    return [r for r in runs if r.kind == "event-catalog"]


def _carriers(driver) -> list[dict]:
    with driver.session(database=DATABASE) as session:
        rows = session.run(
            "MATCH (n) WHERE n:CatalogPromise OR n:CatalogMembership OR n:CatalogEventTopic "
            "OR n:CatalogEvidence RETURN labels(n) AS labels, properties(n) AS props"
        )
        return sorted(
            ({"labels": r["labels"], **r["props"]} for r in rows), key=lambda row: row["id"]
        )


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportOptionalSubscript]


def _ids(carriers: list[dict], label: str) -> set[str]:
    return {row["id"] for row in carriers if row["labels"] == [label]}


def _rejected(run, code: DiagnosticCode, result: IngestionResult) -> None:
    assert not run.stats.committed
    assert {s.result for s in run.stats.source_results} == {result}
    assert {d.code for s in run.stats.source_results for d in s.diagnostics} == {code}


def test_an_accepted_catalog_persists_only_internal_carriers(driver, tmp_path) -> None:
    [run] = _request(driver, _catalog(tmp_path))
    assert run.stats.committed
    assert {s.result for s in run.stats.source_results} == {IngestionResult.ACCEPTED}
    carriers = _carriers(driver)
    counts = {label: len(_ids(carriers, label)) for label in LABELS}
    assert counts == {
        "CatalogPromise": 8,
        "CatalogMembership": 5,
        "CatalogEventTopic": 5,
        "CatalogEvidence": 1,
    }
    source_id = run.stats.source_results[0].source_instance_id
    assert all(row["owner_source_ids"] == [source_id] for row in carriers)
    for label in LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0
    # A promise never manufactures Current State.
    assert _count(driver, "MATCH (s:Service) RETURN count(s) AS c") == 0
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 0
    assert set(LABELS).isdisjoint(NODE_LABELS)

    with driver.session(database=DATABASE) as session:
        block = canonical_snapshot_state(session, coverage_qualification_enabled=True)[
            "event_catalog_v1"
        ]
    assert {name: len(rows) for name, rows in block.items()} == {
        "promises": 8,
        "memberships": 5,
        "event_topics": 5,
        "evidence": 1,
    }


def test_no_registration_leaves_no_snapshot_block(driver) -> None:
    _request(driver)
    with driver.session(database=DATABASE) as session:
        assert "event_catalog_v1" not in canonical_snapshot_state(
            session, coverage_qualification_enabled=True
        )


def test_replay_is_a_semantic_no_op(driver, tmp_path) -> None:
    config = _catalog(tmp_path)
    _request(driver, config)
    before = _carriers(driver)
    [run] = _request(driver, config)
    assert run.stats.committed
    assert all(not s.graph_revision_advanced for s in run.stats.per_source.values())
    assert _carriers(driver) == before


def test_a_lookup_only_change_is_re_evaluated_d12(driver, tmp_path) -> None:
    config = _catalog(tmp_path)
    [first] = _request(driver, config)
    before = _carriers(driver)
    lookup = config.root / "event-topic-lookup.json"
    text = lookup.read_text()
    old = '"event_id": "ProductUpdated",\n      "source": {'
    assert old in text
    lookup.write_text(
        text.replace(
            '"topic": "catalog.product.events"\n    },\n    {\n      "event_id": "TenantUpdated"',
            '"topic": "catalog.renamed.events"\n    },\n    {\n      "event_id": "TenantUpdated"',
        )
    )
    assert lookup.read_text() != text
    [run] = _request(driver, config)
    assert run.stats.committed
    assert any(s.graph_revision_advanced for s in run.stats.per_source.values())
    after = _carriers(driver)
    [evidence_before] = [r for r in before if r["labels"] == ["CatalogEvidence"]]
    [evidence_after] = [r for r in after if r["labels"] == ["CatalogEvidence"]]
    assert evidence_after["source_revision"] != evidence_before["source_revision"]
    assert evidence_after["catalog_digest"] == evidence_before["catalog_digest"]
    assert first.stats.source_results[0].semantic_input_digest != (
        run.stats.source_results[0].semantic_input_digest
    )
    topics = {r["event_id"]: r["topic"] for r in after if r["labels"] == ["CatalogEventTopic"]}
    assert topics["ProductUpdated"] == "catalog.renamed.events"
    # Unrelated promise and membership identities stay stable.
    for label in ("CatalogPromise", "CatalogMembership", "CatalogEventTopic"):
        assert _ids(after, label) == _ids(before, label)


def test_a_rejected_catalog_keeps_the_previous_record(driver, tmp_path) -> None:
    config = _catalog(tmp_path)
    _request(driver, config)
    before = _carriers(driver)
    (config.root / "catalog/flows").mkdir()
    (config.root / "catalog/flows/index.mdx").write_text("---\nid: x\n---\n")
    [run] = _request(driver, config)
    _rejected(run, DiagnosticCode.EVENTCATALOG_UNSUPPORTED, IngestionResult.REJECTED_UNSUPPORTED)
    assert _carriers(driver) == before


def test_dropping_the_registration_retires_the_record(driver, tmp_path) -> None:
    _request(driver, _catalog(tmp_path))
    assert _carriers(driver)
    _request(driver)
    assert _carriers(driver) == []


@pytest.mark.parametrize("same", ["id", "environment"])
def test_a_duplicate_registration_rejects_both_and_keeps_the_record(driver, tmp_path, same) -> None:
    config = _catalog(tmp_path)
    _request(driver, config)
    before = _carriers(driver)
    other = (
        _catalog(tmp_path, environment="prod")
        if same == "id"
        else _catalog(tmp_path, source_id="second-catalog")
    )
    runs = _request(driver, config, other)
    assert len(runs) == 2
    for run in runs:
        _rejected(
            run, DiagnosticCode.EVENTCATALOG_DUPLICATE_SOURCE, IngestionResult.REJECTED_CONFLICT
        )
    # The previously accepted catalog stays protected while its registration is configured.
    assert _carriers(driver) == before


def test_the_committed_package_imports_with_the_i2_profile_registration(driver) -> None:
    """The `event_catalogs` entry of `0.8.0/i2-evidence/config.yaml` (root = the I1 package, default
    relative paths) loads through the real discovery path."""
    [run] = _request(
        driver, EventCatalogSourceConfig(id="sokol111-catalog", root=PACKAGE, environment="local")
    )
    assert run.stats.committed
    [evidence] = [r for r in _carriers(driver) if r["labels"] == ["CatalogEvidence"]]
    ids = json.loads((REPO / "docs/specifications/0.8.0/i2-vectors/ids.json").read_text())
    assert (evidence["id"], evidence["source_revision"]) == (
        ids["evidence_id"],
        ids["source_revision"],
    )
