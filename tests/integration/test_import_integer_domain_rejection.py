"""v0.6.3 I2 (#305) through the real `POST /api/import` on real Neo4j: a source holding an integer
outside RFC 8785's safe domain is rejected and reported, it does not turn the request into a 500, it
does not stop other configured directories from importing, and it leaves previously accepted state
unchanged."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from tests.integration.test_import_report import (
    DATABASE,
    EXAMPLES_DIR,
    _assert_runs_leak_nothing,
    _post_import,
)

BIG = 18446744073709551615


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _add_bad_source(root: Path) -> None:
    document = yaml.safe_load((EXAMPLES_DIR / "order-service" / "openapi.yaml").read_text())
    document["components"] = {"schemas": {"Big": {"type": "integer", "maximum": BIG}}}
    bad = root / "bad-service" / "openapi.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text(yaml.safe_dump(document))


def _service_ids(driver) -> set[str]:
    with driver.session(database=DATABASE) as session:
        return {r["id"] for r in session.run("MATCH (s:Service) RETURN s.id AS id")}


def test_bad_source_is_reported_and_does_not_stop_another_configured_directory(driver, tmp_path):
    good, mixed = tmp_path / "good", tmp_path / "mixed"
    shutil.copytree(EXAMPLES_DIR / "product-service", good / "product-service")
    shutil.copytree(EXAMPLES_DIR / "payment-service", mixed / "payment-service")
    _add_bad_source(mixed)

    body = _post_import(
        driver,
        {
            "directories": [
                {"id": "a-mixed", "root": str(mixed)},
                {"id": "b-good", "root": str(good)},
            ]
        },
    )

    statuses = sorted((r["inventory_status"], r["committed"]) for r in body["runs"])
    assert statuses == [("COMPLETE", True), ("PARTIAL", False)]
    partial = next(r for r in body["runs"] if r["inventory_status"] == "PARTIAL")
    rejected = next(r for r in partial["source_results"] if r["result"] == "REJECTED_INVALID")
    assert rejected["locator"] == "bad-service/openapi.yaml"
    assert {d["code"] for d in rejected["diagnostics"]} == {"DOCUMENT_PARSE_INVALID"}
    assert str(BIG) not in json.dumps(body)
    # Only the directory without the bad source committed.
    assert _service_ids(driver) == {"service:product-service"}
    _assert_runs_leak_nothing(body, tmp_path)


def test_previously_accepted_state_is_unchanged_when_a_bad_source_appears(driver, tmp_path):
    root = tmp_path / "root"
    shutil.copytree(EXAMPLES_DIR / "product-service", root / "product-service")
    sources = {"directories": [{"id": "stable", "root": str(root)}]}
    first = _post_import(driver, sources)
    assert first["committed"] is True
    before = _service_ids(driver)
    assert before == {"service:product-service"}

    _add_bad_source(root)
    second = _post_import(driver, sources)

    [run] = second["runs"]
    assert run["inventory_status"] == "PARTIAL" and run["committed"] is False
    assert second["committed"] is False
    assert _service_ids(driver) == before
