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


def test_load_scenario_rejects_a_non_string_description(tmp_path):
    bad_yaml = _VALID_REQUEST_YAML.replace("description: minimal scenario", "description: [1, 2]")
    scenario_dir = _write_scenario(tmp_path, request_yaml=bad_yaml)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_a_non_string_environment(tmp_path):
    bad_yaml = _VALID_REQUEST_YAML.replace("environment: test", "environment: 42")
    scenario_dir = _write_scenario(tmp_path, request_yaml=bad_yaml)
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_a_non_string_snapshot_id(tmp_path):
    bad_yaml = _VALID_REQUEST_YAML + "  snapshot_id: 42\n"
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


# --- I3.3: tool-aware request.yaml (spec §29/§31) -------------------------------------------------

_MINIMAL_DRIFT_ANSWER = {
    **_MINIMAL_ANSWERED_ANSWER,
    "tool": "get_architecture_drift",
    "data": {
        "service": {"id": "service:product-service", "type": "SERVICE", "name": "ProductService"},
        "drift_claim_ids": [],
    },
}

_MINIMAL_EVIDENCE_ANSWER = {
    **_MINIMAL_ANSWERED_ANSWER,
    "tool": "get_evidence",
    "outcome": "NOT_ANSWERED",
    "observation_context": None,
    "data": {
        "requested_evidence_refs": ["evidence:manifest:order-service"],
        "records": [],
        "missing_evidence_refs": ["evidence:manifest:order-service"],
    },
    "limitations": [
        {
            "code": "INSUFFICIENT_EVIDENCE",
            "message": "1 of 1 requested evidence refs could not be resolved",
            "claim_ids": [],
        }
    ],
}

_DRIFT_REQUEST_YAML = """\
scenario: drift-empty-service
description: minimal drift scenario
request:
  tool: get_architecture_drift
  service_id: service:product-service
  observation:
    environment: test
    window:
      start: "2026-08-26T00:00:00Z"
      end: "2026-08-27T00:00:00Z"
"""

_EVIDENCE_REQUEST_YAML = """\
scenario: evidence-scenario
description: minimal evidence scenario
request:
  tool: get_evidence
  evidence_refs:
    - "evidence:manifest:order-service"
  snapshot_id: "aip:snapshot:v1:{}"
""".format("a" * 64)


def _write_named_scenario(tmp_path, *, name, request_yaml, expected_answer):
    scenario_dir = tmp_path / name
    scenario_dir.mkdir()
    (scenario_dir / loader.REQUEST_FILENAME).write_text(request_yaml)
    (scenario_dir / loader.EXPECTED_ANSWER_FILENAME).write_text(json.dumps(expected_answer))
    return scenario_dir


def test_a_request_with_no_tool_key_defaults_to_get_service_dependencies(tmp_path):
    scenario_dir = _write_scenario(tmp_path)
    scenario = loader.load_scenario(scenario_dir)
    assert scenario.request.tool == "get_service_dependencies"


def test_load_scenario_loads_a_drift_tool_scenario(tmp_path):
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="drift-empty-service",
        request_yaml=_DRIFT_REQUEST_YAML,
        expected_answer=_MINIMAL_DRIFT_ANSWER,
    )
    scenario = loader.load_scenario(scenario_dir)
    assert scenario.request.tool == "get_architecture_drift"
    assert scenario.request.service_id == "service:product-service"
    assert scenario.expected.tool == "get_architecture_drift"


def test_load_scenario_loads_an_evidence_tool_scenario(tmp_path):
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="evidence-scenario",
        request_yaml=_EVIDENCE_REQUEST_YAML,
        expected_answer=_MINIMAL_EVIDENCE_ANSWER,
    )
    scenario = loader.load_scenario(scenario_dir)
    assert scenario.request.tool == "get_evidence"
    assert scenario.request.evidence_refs == ("evidence:manifest:order-service",)
    assert scenario.request.snapshot_id == "aip:snapshot:v1:" + "a" * 64
    assert scenario.expected.tool == "get_evidence"


def test_load_scenario_rejects_an_unknown_tool_name(tmp_path):
    bad_yaml = _DRIFT_REQUEST_YAML.replace(
        "tool: get_architecture_drift", "tool: get_something_else"
    )
    scenario_dir = _write_named_scenario(
        tmp_path, name="bad-tool", request_yaml=bad_yaml, expected_answer=_MINIMAL_DRIFT_ANSWER
    )
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_an_evidence_request_with_an_observation_key(tmp_path):
    bad_yaml = _EVIDENCE_REQUEST_YAML + "  observation:\n    environment: test\n"
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="evidence-scenario",
        request_yaml=bad_yaml,
        expected_answer=_MINIMAL_EVIDENCE_ANSWER,
    )
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_an_evidence_request_missing_snapshot_id(tmp_path):
    bad_yaml = "\n".join(
        line for line in _EVIDENCE_REQUEST_YAML.splitlines() if not line.startswith("  snapshot_id")
    )
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="evidence-scenario",
        request_yaml=bad_yaml,
        expected_answer=_MINIMAL_EVIDENCE_ANSWER,
    )
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_an_evidence_request_with_no_evidence_refs(tmp_path):
    bad_yaml = _EVIDENCE_REQUEST_YAML.replace(
        '  evidence_refs:\n    - "evidence:manifest:order-service"\n', "  evidence_refs: []\n"
    )
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="evidence-scenario",
        request_yaml=bad_yaml,
        expected_answer=_MINIMAL_EVIDENCE_ANSWER,
    )
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)


def test_load_scenario_rejects_a_drift_request_whose_expected_answer_names_a_different_tool(
    tmp_path,
):
    """A `request.tool` naming one tool while `expected_answer.json`'s own `"tool"` field names
    another must fail - the runtime tool-const check on the specialization the loader picked to
    validate against catches this automatically (no separate cross-check needed)."""
    mismatched_answer = {**_MINIMAL_DRIFT_ANSWER, "tool": "get_service_dependencies"}
    scenario_dir = _write_named_scenario(
        tmp_path,
        name="drift-empty-service",
        request_yaml=_DRIFT_REQUEST_YAML,
        expected_answer=mismatched_answer,
    )
    with pytest.raises(ScenarioValidationError):
        loader.load_scenario(scenario_dir)
