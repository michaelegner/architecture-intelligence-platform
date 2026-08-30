import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from evaluation.loader import discover_scenarios, load_scenario, load_scenarios
from evaluation.model import Observation, RelationFact, ScenarioScope, ScenarioValidationError

EVALUATION_DIR = Path(__file__).resolve().parent.parent.parent / "evaluation"
SCENARIOS_DIR = EVALUATION_DIR / "scenarios"

_VALID = {
    "scenario": "rest-confirmed",
    "description": "OrderService calls ProductService, declared and observed.",
    "scope": {
        "entities": [
            "service:order-service",
            "operation:service:product-service:GET:/products/{id}",
        ],
        "relation_types": ["CALLS"],
    },
    "observation": {
        "environment": "test",
        "window": {"start": "2026-08-01T10:00:00Z", "end": "2026-08-01T11:00:00Z"},
    },
    "expected": {
        "relations": [
            {
                "type": "CALLS",
                "source": "service:order-service",
                "target": "operation:service:product-service:GET:/products/{id}",
                "status": "CONFIRMED",
                "evidence": {"declared": True, "observed": True},
            }
        ]
    },
    "forbidden": {"relations": []},
}


def _write_scenario(tmp_path: Path, data: dict, *, name: str = "scenario") -> Path:
    scenario_dir = tmp_path / name
    scenario_dir.mkdir()
    (scenario_dir / "expected.yaml").write_text(yaml.safe_dump(data))
    return scenario_dir


def _mutated(**overrides) -> dict:
    data = copy.deepcopy(_VALID)
    for path, value in overrides.items():
        keys = path.split(".")
        target = data
        for key in keys[:-1]:
            target = target[key]
        if value is _DELETE:
            del target[keys[-1]]
        else:
            target[keys[-1]] = value
    return data


_DELETE = object()


# --- discovery ------------------------------------------------------------------------------


def test_discover_scenarios_finds_the_three_real_i1_scenarios():
    discovered = discover_scenarios(SCENARIOS_DIR)
    assert [p.name for p in discovered] == [
        "01-rest-confirmed",
        "02-rest-observed-only",
        "03-async-confirmed",
    ]


def test_the_three_real_i1_scenarios_all_load_and_validate():
    scenarios = load_scenarios(SCENARIOS_DIR)
    assert [s.id for s in scenarios] == ["rest-confirmed", "rest-observed-only", "async-confirmed"]
    assert all(s.expected_relations for s in scenarios)
    for s in scenarios:
        assert s.observation.environment == "test"


def test_discover_scenarios_ignores_directories_without_expected_yaml(tmp_path):
    (tmp_path / "not-a-scenario").mkdir()
    _write_scenario(tmp_path, _VALID, name="real-scenario")
    assert [p.name for p in discover_scenarios(tmp_path)] == ["real-scenario"]


# --- loading a valid scenario -----------------------------------------------------------------


def test_loads_a_valid_scenario(tmp_path):
    scenario_dir = _write_scenario(tmp_path, _VALID)

    scenario = load_scenario(scenario_dir)

    assert scenario.id == "rest-confirmed"
    assert scenario.path == scenario_dir
    assert scenario.scope == ScenarioScope(
        entities=(
            "service:order-service",
            "operation:service:product-service:GET:/products/{id}",
        ),
        relation_types=("CALLS",),
    )
    assert scenario.observation == Observation(
        environment="test",
        window_start=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        window_end=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
    )
    assert scenario.expected_relations == (
        RelationFact(
            type="CALLS",
            source="service:order-service",
            target="operation:service:product-service:GET:/products/{id}",
            status="CONFIRMED",
            declared_evidence=True,
            observed_evidence=True,
        ),
    )


def test_scope_without_relation_types_means_all_relation_types(tmp_path):
    data = _mutated(**{"scope.relation_types": _DELETE})
    scenario_dir = _write_scenario(tmp_path, data)

    scenario = load_scenario(scenario_dir)

    assert scenario.scope.relation_types is None


# --- validation failures ------------------------------------------------------------------------


def test_rejects_missing_scenario_id(tmp_path):
    data = _mutated(scenario=_DELETE)
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "scenario"


def test_rejects_unknown_relation_type(tmp_path):
    data = _mutated(
        **{"expected.relations": [{**_VALID["expected"]["relations"][0], "type": "FROBNICATES"}]}
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown relation type" in excinfo.value.reason


def test_rejects_duplicate_expected_fact(tmp_path):
    fact = _VALID["expected"]["relations"][0]
    data = _mutated(**{"expected.relations": [fact, dict(fact)]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "duplicate" in excinfo.value.reason


def test_rejects_malformed_canonical_identifier(tmp_path):
    data = _mutated(
        **{
            "expected.relations": [
                {**_VALID["expected"]["relations"][0], "source": "order-service"}
            ]
        }
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "malformed canonical identifier" in excinfo.value.reason


def test_rejects_non_empty_forbidden_relations(tmp_path):
    data = _mutated(
        forbidden={"relations": [{"type": "CALLS", "source": "service:a", "target": "operation:b"}]}
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "forbidden.relations"
    assert "I2" in excinfo.value.reason


def test_rejects_missing_forbidden_relations(tmp_path):
    data = _mutated(forbidden=_DELETE)
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "forbidden"


def test_rejects_missing_expected_relations(tmp_path):
    data = _mutated(expected=_DELETE)
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "expected"


def test_runtime_scenario_requires_environment(tmp_path):
    data = _mutated(**{"observation.environment": _DELETE})
    scenario_dir = _write_scenario(tmp_path, data)
    telemetry_dir = scenario_dir / "input" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    (telemetry_dir / "spans.py").write_text("")

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "observation.environment"


def test_declaration_only_scenario_does_not_require_environment(tmp_path):
    data = _mutated(observation=_DELETE)
    scenario_dir = _write_scenario(tmp_path, data)

    scenario = load_scenario(scenario_dir)

    assert scenario.observation.environment is None
