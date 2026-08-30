"""I1.3 exit condition: the REST CONFIRMED scenario passes end-to-end (setup -> canonical
projection -> comparison), using evaluation.runner.run_scenario against a real Neo4j.
"""

import shutil
from pathlib import Path

import pytest
import yaml
from testcontainers.community.neo4j import Neo4jContainer

from evaluation.loader import load_scenario
from evaluation.runner import run_scenario

SCENARIOS_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation" / "scenarios"
DATABASE = "neo4j"


@pytest.fixture(scope="module")
def neo4j_container():
    with Neo4jContainer("neo4j:5") as container:
        yield container


@pytest.fixture(scope="module")
def driver(neo4j_container):
    drv = neo4j_container.get_driver()
    yield drv
    drv.close()


def test_rest_confirmed_scenario_passes_end_to_end(driver):
    scenario = load_scenario(SCENARIOS_DIR / "01-rest-confirmed")

    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert result.passed, result.mismatches
    assert result.mismatches == ()


def test_wrong_expectation_is_reported_as_a_semantic_mismatch_not_a_pass(driver, tmp_path):
    """Sanity-break control: mutating the real scenario's expected status must turn this into a
    reported FAIL, proving the comparison is actually discriminating rather than vacuously true."""
    broken_dir = tmp_path / "01-rest-confirmed-broken"
    shutil.copytree(SCENARIOS_DIR / "01-rest-confirmed", broken_dir)
    expected_file = broken_dir / "expected.yaml"
    data = yaml.safe_load(expected_file.read_text())
    data["expected"]["relations"][0]["status"] = "OBSERVED_ONLY"
    expected_file.write_text(yaml.safe_dump(data))

    scenario = load_scenario(broken_dir)
    result = run_scenario(driver, database=DATABASE, scenario=scenario)

    assert not result.passed
    assert len(result.mismatches) == 1
    assert result.mismatches[0].kind == "semantic_mismatch"
    assert result.mismatches[0].actual.status == "CONFIRMED"
