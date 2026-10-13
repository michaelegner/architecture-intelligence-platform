"""v0.7.0 I1.4: the APISIX gateway source against a real Neo4j - persistence as internal carriers,
the conditional snapshot key, authoritative removal, idempotent replay, rejection leaving prior
state untouched, the duplicate-instance conflict through the real import request, and the amended
import report. Independent expected data comes from the I1.1 vectors."""

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.import_runs import run_all_configured_sources
from app.graph.importer import import_apisix_source
from app.graph.schema import ensure_schema
from app.ingestion.import_report import build_import_report
from app.settings import SourcesConfig
from app.sources.model import ApisixSourceConfig, FilesystemSourceConfig, IngestionResult

DATABASE = "neo4j"
VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.0/i1-vectors"
REPO = Path(__file__).resolve().parents[2]
CARRIER_LABELS = (
    "GatewayConsumer",
    "GatewayRoute",
    "GatewayService",
    "GatewayConfiguredAccess",
    "GatewayLimitation",
    "GatewaySourceEvidence",
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _vectors() -> dict:
    return json.loads((VECTORS / "configured-access.json").read_text(encoding="utf-8"))


def _document(case_id: str, **patch) -> dict:
    vectors = _vectors()
    case = next(c for c in vectors["cases"] if c["id"] == case_id)
    document = copy.deepcopy(vectors["base_capture"])
    document.update(
        consumers=[], routes=[], services=[], upstreams=[], plugin_configs=[],
        consumer_groups=[], global_rules=[],
    )  # fmt: skip
    document.update(copy.deepcopy(case["capture"]))
    document.update(patch)
    return document


def _config(tmp_path: Path, document: dict, *, source_id="apisix-prod", instance="gw-prod-1"):
    root = tmp_path / source_id
    root.mkdir(exist_ok=True)
    config = ApisixSourceConfig(id=source_id, root=root, gateway_instance_id=instance)
    (root / config.capture_relative_path).write_text(json.dumps(document))
    return config


def _import(driver, config):
    return import_apisix_source(driver, database=DATABASE, source_config=config)


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportArgumentType]


def _counts(driver) -> dict[str, int]:
    return {
        label: _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") for label in CARRIER_LABELS
    }


def _state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def test_an_accepted_capture_persists_internal_carriers_without_relationships_or_evidence(
    driver, tmp_path
) -> None:
    stats = _import(driver, _config(tmp_path, _document("C14")))
    assert stats.committed
    assert _counts(driver) == {
        "GatewayConsumer": 2, "GatewayRoute": 2, "GatewayService": 0,
        "GatewayConfiguredAccess": 3, "GatewayLimitation": 0, "GatewaySourceEvidence": 1,
    }  # fmt: skip
    for label in CARRIER_LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0
    # gateway evidence is an internal carrier, never an :Evidence node (no public/NL exposure)
    assert _count(driver, "MATCH (e:Evidence) RETURN count(e) AS c") == 0
    assert _count(driver, "MATCH (e:Evidence {source_type: 'APISIX'}) RETURN count(e) AS c") == 0
    assert _count(driver, "MATCH (s:Service) RETURN count(s) AS c") == 0


def test_the_snapshot_gains_the_conditional_gateway_key_with_the_vector_content(
    driver, tmp_path
) -> None:
    before = _state(driver)
    assert "gateway_configuration_v1" not in before
    _import(driver, _config(tmp_path, _document("C14")))
    state = _state(driver)
    block = state["gateway_configuration_v1"]
    assert len(block["consumers"]) == 2 and len(block["routes"]) == 2
    assert len(block["configured_access"]) == 3 and block["limitations"] == []
    [evidence] = block["source_evidence"]
    assert evidence["source_revision"] == "apisix:3.19.0+etcd:18"
    assert evidence["environment"] == "prod"
    for rows in block.values():
        assert rows == sorted(rows, key=lambda row: row["id"])
    without = {k: v for k, v in state.items() if k != "gateway_configuration_v1"}
    assert snapshot_fingerprint(without)[0] == snapshot_fingerprint(before)[0]


def test_a_replay_of_the_same_capture_changes_nothing(driver, tmp_path) -> None:
    config = _config(tmp_path, _document("C14"))
    _import(driver, config)
    first = snapshot_fingerprint(_state(driver))[0]
    stats = _import(driver, config)
    assert stats.committed
    assert all(not s.graph_revision_advanced for s in stats.per_source.values())
    assert snapshot_fingerprint(_state(driver))[0] == first


def test_a_later_complete_capture_authoritatively_removes_what_is_gone(driver, tmp_path) -> None:
    config = _config(tmp_path, _document("C14"))
    _import(driver, config)
    smaller = _document("C14")
    smaller["routes"] = [r for r in smaller["routes"] if r["id"] == "r1"]
    smaller["consumers"] = [c for c in smaller["consumers"] if c["username"] == "alice"]
    smaller["etcd_revision_before"] = smaller["etcd_revision_after"] = 19
    (config.root / config.capture_relative_path).write_text(json.dumps(smaller))
    stats = _import(driver, config)
    assert stats.committed
    counts = _counts(driver)
    assert counts["GatewayRoute"] == 1 and counts["GatewayConsumer"] == 1
    assert counts["GatewayConfiguredAccess"] == 1  # only alice -> r1 remains
    assert counts["GatewaySourceEvidence"] == 1  # the old revision's evidence was replaced
    block = _state(driver)["gateway_configuration_v1"]
    assert block["source_evidence"][0]["source_revision"] == "apisix:3.19.0+etcd:19"


@pytest.mark.parametrize(
    "bad",
    [
        {"etcd_revision_after": 99},
        {"lists_complete": {"routes": False}},
        {"admin_surface": "standalone-yaml"},
        {"schema": "aip-apisix-capture/2"},
    ],
    ids=["revision-changed", "incomplete-list", "standalone-yaml", "schema-version"],
)
def test_a_rejected_capture_commits_nothing_and_removes_nothing(driver, tmp_path, bad) -> None:
    config = _config(tmp_path, _document("C14"))
    _import(driver, config)
    before_counts, before_id = _counts(driver), snapshot_fingerprint(_state(driver))[0]
    document = _document("C14")
    if "lists_complete" in bad:
        document["lists_complete"].update(bad["lists_complete"])
    else:
        document.update(bad)
    document["routes"] = []  # a rejected capture must not erase the previously accepted routes
    (config.root / config.capture_relative_path).write_text(json.dumps(document))
    stats = _import(driver, config)
    assert not stats.committed
    assert {r.result for r in stats.source_results} <= {
        IngestionResult.REJECTED_INVALID,
        IngestionResult.REJECTED_UNSUPPORTED,
    }
    assert _counts(driver) == before_counts
    assert snapshot_fingerprint(_state(driver))[0] == before_id


def test_a_canary_secret_in_a_fixture_is_rejected_and_never_reaches_the_graph_or_stats(
    driver, tmp_path
) -> None:
    document = _document("C01")
    document["consumers"][0]["key"] = "CANARY-SECRET-VALUE"
    stats = _import(driver, _config(tmp_path, document))
    assert not stats.committed
    assert "CANARY-SECRET-VALUE" not in repr(stats)
    assert _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)


def test_the_same_username_on_two_instances_is_two_consumers(driver, tmp_path) -> None:
    for instance in ("gw-a", "gw-b"):
        doc = _document("C01", gateway_instance_id=instance)
        assert _import(
            driver, _config(tmp_path, doc, source_id=f"src-{instance}", instance=instance)
        ).committed
    assert _count(driver, "MATCH (c:GatewayConsumer {username: 'alice'}) RETURN count(c) AS c") == 2


def test_duplicate_gateway_instance_registrations_are_both_rejected_through_the_request(
    driver, tmp_path
) -> None:
    gateways = [
        _config(tmp_path, _document("C01"), source_id="apisix-a", instance="gw-dup"),
        _config(
            tmp_path,
            _document("C01", gateway_instance_id="gw-dup"),
            source_id="apisix-b",
            instance="gw-dup",
        ),
    ]
    _, runs = run_all_configured_sources(
        SourcesConfig(directories=[], gateways=gateways), driver=driver, database=DATABASE
    )
    assert [r.kind for r in runs] == ["apisix", "apisix"]
    for run in runs:
        assert not run.stats.committed
        assert {s.result for s in run.stats.source_results} == {IngestionResult.REJECTED_CONFLICT}
    assert _counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)


def test_the_request_runs_filesystem_and_gateway_sources_and_the_report_validates(
    driver, tmp_path
) -> None:
    examples = FilesystemSourceConfig(id="pin", root=REPO / "examples")
    gateway = _config(tmp_path, _document("C14"))
    import_id, runs = run_all_configured_sources(
        SourcesConfig(directories=[examples], gateways=[gateway]), driver=driver, database=DATABASE
    )
    assert [r.kind for r in runs] == ["filesystem", "apisix"]
    assert all(r.stats.committed for r in runs)
    report = build_import_report(import_id, runs)
    schema = json.loads((REPO / "schemas/import/v0.5/import-report.schema.json").read_text())
    jsonschema.validate(json.loads(report.model_dump_json()), schema)
    assert any(run.kind == "apisix" for run in report.runs)
    assert _counts(driver)["GatewayConfiguredAccess"] == 3
    # configuring a gateway also enables the OpenAPI contract carriers (I1.2)
    assert _count(driver, "MATCH (c:ApiContract) RETURN count(c) AS c") > 0
