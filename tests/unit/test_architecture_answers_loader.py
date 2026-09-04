import json

import pytest

from evaluation.architecture_answers import loader
from evaluation.architecture_answers.model import ScenarioValidationError

_MINIMAL_ANSWERED_ANSWER = {
    "schema_version": "0.4",
    "producer": {
        "name": "architecture-intelligence-platform",
        "version": "0.4.0",
        "build_revision": "f" * 40,
    },
    "tool": "get_service_dependencies",
    "outcome": "ANSWERED",
    "snapshot": {
        "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
        "model_revision": "sha256:" + "a" * 64,
    },
    "observation_context": {
        "context_id": "aip:observation-context:v1:" + "b" * 64,
        "environment": "test",
        "window_start": "2026-08-26T00:00:00.000000Z",
        "window_end": "2026-08-27T00:00:00.000000Z",
    },
    "data": {
        "service": {"id": "service:product-service", "type": "SERVICE", "name": "ProductService"},
        "dependency_claim_ids": [],
    },
    "claims": [],
    "evidence_refs": [],
    "limitations": [],
}

_VALID_REQUEST_YAML = """\
scenario: empty-service
description: minimal scenario
request:
  service_id: service:product-service
  observation:
    environment: test
    window:
      start: "2026-08-26T00:00:00Z"
      end: "2026-08-27T00:00:00Z"
"""


def _write_scenario(
    tmp_path, *, request_yaml=_VALID_REQUEST_YAML, expected_answer=_MINIMAL_ANSWERED_ANSWER
):
    scenario_dir = tmp_path / "empty-service"
    scenario_dir.mkdir()
    (scenario_dir / loader.REQUEST_FILENAME).write_text(request_yaml)
    if expected_answer is not None:
        (scenario_dir / loader.EXPECTED_ANSWER_FILENAME).write_text(json.dumps(expected_answer))
    return scenario_dir


def test_discover_scenarios_finds_directories_with_a_request_file(tmp_path):
    _write_scenario(tmp_path)
    (tmp_path / "not-a-scenario").mkdir()
    assert [p.name for p in loader.discover_scenarios(tmp_path)] == ["empty-service"]


def test_load_scenario_round_trips_a_valid_scenario(tmp_path):
    scenario_dir = _write_scenario(tmp_path)
    scenario = loader.load_scenario(scenario_dir)

    assert scenario.id == "empty-service"
    assert scenario.request.service_id == "service:product-service"
    assert scenario.request.environment == "test"
    assert scenario.expected.outcome == "ANSWERED"


def test_load_scenario_rejects_unknown_top_level_keys(tmp_path):
    scenario_dir = _write_scenario(tmp_path, request_yaml=_VALID_REQUEST_YAML + "extra: 1\n")
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_a_malformed_service_id(tmp_path):
    bad_yaml = _VALID_REQUEST_YAML.replace("service:product-service", "not-a-service-id")
    scenario_dir = _write_scenario(tmp_path, request_yaml=bad_yaml)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_a_timestamp_without_explicit_offset(tmp_path):
    bad_yaml = _VALID_REQUEST_YAML.replace('"2026-08-26T00:00:00Z"', '"2026-08-26T00:00:00"')
    scenario_dir = _write_scenario(tmp_path, request_yaml=bad_yaml)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_requires_expected_answer_file(tmp_path):
    scenario_dir = _write_scenario(tmp_path, expected_answer=None)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_an_expected_answer_that_fails_contract_validation(tmp_path):
    broken_answer = {**_MINIMAL_ANSWERED_ANSWER, "outcome": "NOT_A_REAL_OUTCOME"}
    scenario_dir = _write_scenario(tmp_path, expected_answer=broken_answer)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_malformed_json_in_expected_answer(tmp_path):
    scenario_dir = _write_scenario(tmp_path)
    (scenario_dir / loader.EXPECTED_ANSWER_FILENAME).write_text("{not valid json")
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenarios_loads_every_discovered_scenario(tmp_path):
    _write_scenario(tmp_path)
    scenarios = loader.load_scenarios(tmp_path)
    assert [s.id for s in scenarios] == ["empty-service"]
