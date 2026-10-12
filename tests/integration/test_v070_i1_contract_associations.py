"""v0.7.0 I1.2: conditional OpenAPI API-contract associations against a real Neo4j (I1.1 contract
§3, §6; I1 spec §3.6 as amended): the no-gateway snapshot is byte-identical to before v0.7, the
carriers appear and disappear with the import request's gateway configuration, they have no
relationships, and Operation ids never change."""

from pathlib import Path

import pytest

from app.architecture_intelligence.repository import canonical_snapshot_state, snapshot_fingerprint
from app.graph.import_runs import run_all_configured_sources
from app.graph.importer import import_all_sources
from app.graph.schema import ensure_schema
from app.settings import SourcesConfig
from app.sources.model import ApisixSourceConfig, FilesystemSourceConfig

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"

# Recorded on the unmodified origin/main (3521d9e, before any I1.2 change) by importing the bundled
# examples/ directory with the default configuration. A no-gateway graph must keep it exactly.
PRE_V070_EXAMPLES_SNAPSHOT_ID = (
    "aip:snapshot:v1:7969e93169083d4f9ad5f2d8e4029967371b6fd0bf4f21f5a2e9ef9767322d8e"
)
CARRIER_LABELS = ("ApiContract", "ApiContractVersion", "ApiContractAssociation")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _config() -> FilesystemSourceConfig:
    return FilesystemSourceConfig(id="pin", root=EXAMPLES_DIR)


def _import(driver, *, gateway: bool):
    stats = import_all_sources(
        driver, database=DATABASE, source_config=_config(), api_contract_associations=gateway
    )
    assert stats.committed
    return stats


def _state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        return canonical_snapshot_state(session, coverage_qualification_enabled=True)


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]  # pyright: ignore[reportArgumentType]


def _carrier_counts(driver) -> dict[str, int]:
    return {
        label: _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") for label in CARRIER_LABELS
    }


def _operation_ids(driver) -> list[str]:
    with driver.session(database=DATABASE) as session:
        return sorted(r["id"] for r in session.run("MATCH (o:Operation) RETURN o.id AS id"))


def test_no_gateway_graph_keeps_the_pre_v070_snapshot_and_has_no_carriers(driver) -> None:
    _import(driver, gateway=False)
    state = _state(driver)
    assert "api_contracts_v1" not in state
    assert snapshot_fingerprint(state)[0] == PRE_V070_EXAMPLES_SNAPSHOT_ID
    assert _carrier_counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)


def test_gateway_configured_persists_carriers_and_adds_the_conditional_snapshot_key(driver) -> None:
    _import(driver, gateway=False)
    operation_ids = _operation_ids(driver)
    assert operation_ids

    _import(driver, gateway=True)
    counts = _carrier_counts(driver)
    assert all(count > 0 for count in counts.values())
    assert _operation_ids(driver) == operation_ids  # Operation ids are never changed

    state = _state(driver)
    block = state["api_contracts_v1"]
    assert {len(block["contracts"]), len(block["versions"]), len(block["associations"])} != {0}
    assert block["contracts"] == sorted(block["contracts"], key=lambda row: row["id"])
    assert snapshot_fingerprint(state)[0] != PRE_V070_EXAMPLES_SNAPSHOT_ID
    # every public part of the state is unchanged apart from the new conditional key
    without = {k: v for k, v in state.items() if k != "api_contracts_v1"}
    assert snapshot_fingerprint(without)[0] == PRE_V070_EXAMPLES_SNAPSHOT_ID


def test_toggling_the_gateway_configuration_adds_and_expires_the_carriers(driver) -> None:
    _import(driver, gateway=False)
    _import(driver, gateway=True)
    enabled_id = snapshot_fingerprint(_state(driver))[0]
    enabled_counts = _carrier_counts(driver)

    _import(driver, gateway=False)  # replay no-op must not keep stale carriers
    assert _carrier_counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)
    assert snapshot_fingerprint(_state(driver))[0] == PRE_V070_EXAMPLES_SNAPSHOT_ID

    _import(driver, gateway=True)
    assert _carrier_counts(driver) == enabled_counts
    assert snapshot_fingerprint(_state(driver))[0] == enabled_id


def test_carriers_have_no_relationships_to_any_entity(driver) -> None:
    _import(driver, gateway=True)
    for label in CARRIER_LABELS:
        assert _count(driver, f"MATCH (n:{label})-[r]-() RETURN count(r) AS c") == 0


def test_contract_uniqueness_constraints_exist(driver) -> None:
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        names = {r["name"] for r in session.run("SHOW CONSTRAINTS YIELD name RETURN name")}
    assert {"api_contract_id", "api_contract_version_id", "api_contract_association_id"} <= names


def test_request_configuration_is_the_gate(driver, tmp_path) -> None:
    gateway = ApisixSourceConfig(id="apisix-prod", root=tmp_path, gateway_instance_id="gw-prod-1")
    run_all_configured_sources(
        SourcesConfig(directories=[_config()]), driver=driver, database=DATABASE
    )
    assert _carrier_counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)

    run_all_configured_sources(
        SourcesConfig(directories=[_config()], gateways=[gateway]),
        driver=driver,
        database=DATABASE,
    )
    assert all(count > 0 for count in _carrier_counts(driver).values())

    run_all_configured_sources(
        SourcesConfig(directories=[_config()]), driver=driver, database=DATABASE
    )
    assert _carrier_counts(driver) == dict.fromkeys(CARRIER_LABELS, 0)
