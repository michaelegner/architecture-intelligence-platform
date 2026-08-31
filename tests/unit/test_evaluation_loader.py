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


def test_discover_scenarios_finds_the_ten_real_scenarios():
    discovered = discover_scenarios(SCENARIOS_DIR)
    assert [p.name for p in discovered] == [
        "01-rest-confirmed",
        "02-rest-observed-only",
        "03-async-confirmed",
        "04-orphan-messaging",
        "05-mixed-rest-async",
        "06-request-response-queue-pair",
        "07-not-observed-in-window",
        "08-evidence-reconciliation",
        "09-partial-observation",
        "10-declared-rest-relation",
    ]


def test_the_ten_real_scenarios_all_load_and_validate():
    scenarios = load_scenarios(SCENARIOS_DIR)
    assert [s.id for s in scenarios] == [
        "rest-confirmed",
        "rest-observed-only",
        "async-confirmed",
        "orphan-messaging",
        "mixed-rest-async",
        "request-response-queue-pair",
        "not-observed-in-window",
        "evidence-reconciliation",
        "partial-observation",
        "declared-rest-relation",
    ]
    assert all(s.expected_relations for s in scenarios)

    # 01-09 are runtime scenarios (require a real observation environment/window); 10 is
    # declaration-only by design (I4 spec §7.3) and must not carry one.
    runtime_scenarios, declared_only = scenarios[:-1], scenarios[-1]
    assert all(s.observation.environment == "test" for s in runtime_scenarios)
    assert declared_only.id == "declared-rest-relation"
    assert declared_only.observation.environment is None
    assert declared_only.observation.window_start is None
    assert declared_only.observation.window_end is None


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


# --- nested type validation (I1 post-merge review F2) ------------------------------------------
# Every mapping/list boundary the loader assumes must be validated, not just presence, so a
# malformed value raises ScenarioValidationError with field context instead of a raw
# AttributeError/TypeError escaping the loader's error contract.


def test_rejects_a_non_mapping_document_root(tmp_path):
    scenario_dir = tmp_path / "scenario"
    scenario_dir.mkdir()
    (scenario_dir / "expected.yaml").write_text("- just\n- a\n- list\n")

    with pytest.raises(ScenarioValidationError):
        load_scenario(scenario_dir)


@pytest.mark.parametrize(
    "overrides",
    [
        {"scope": "not-a-mapping"},
        {"scope.entities": "not-a-list"},
        {"scope.relation_types": "CALLS"},
        {"observation": "not-a-mapping"},
        {"observation.window": "not-a-mapping"},
        {"expected": "not-a-mapping"},
        {"expected.relations": "not-a-list"},
        {"forbidden": "not-a-mapping"},
        {"forbidden.relations": "not-a-list"},
    ],
)
def test_rejects_non_mapping_or_non_list_nested_values(tmp_path, overrides):
    data = _mutated(**overrides)
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError):
        load_scenario(scenario_dir)


def test_rejects_a_non_mapping_relation_evidence(tmp_path):
    data = _mutated(
        **{"expected.relations": [{**_VALID["expected"]["relations"][0], "evidence": "invalid"}]}
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "evidence" in excinfo.value.field


# --- timestamp validation (I1 post-merge review F3) ---------------------------------------------


def test_rejects_an_invalid_window_start_timestamp(tmp_path):
    data = _mutated(**{"observation.window.start": "not-a-timestamp"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "observation.window.start"


def test_rejects_an_invalid_window_end_timestamp(tmp_path):
    data = _mutated(**{"observation.window.end": "not-a-timestamp"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "observation.window.end"


# --- forbidden-fact evaluation (I2 §6.1/§9) ------------------------------------------------------

_FORBIDDEN_FACT = {
    "type": "CALLS",
    "source": "service:order-service",
    "target": "operation:service:product-service:GET:/other",
}


def test_non_empty_forbidden_relations_now_loads_successfully(tmp_path):
    data = _mutated(forbidden={"relations": [_FORBIDDEN_FACT]})
    scenario_dir = _write_scenario(tmp_path, data)

    scenario = load_scenario(scenario_dir)

    assert scenario.forbidden_relations == (
        RelationFact(
            type="CALLS",
            source="service:order-service",
            target="operation:service:product-service:GET:/other",
        ),
    )


def test_rejects_a_forbidden_entry_with_status(tmp_path):
    data = _mutated(forbidden={"relations": [{**_FORBIDDEN_FACT, "status": "CONFIRMED"}]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason
    assert "status" in excinfo.value.reason


def test_rejects_a_forbidden_entry_with_evidence(tmp_path):
    data = _mutated(forbidden={"relations": [{**_FORBIDDEN_FACT, "evidence": {"declared": True}}]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason
    assert "evidence" in excinfo.value.reason


def test_rejects_a_forbidden_entry_with_an_unknown_typo_field(tmp_path):
    data = _mutated(forbidden={"relations": [{**_FORBIDDEN_FACT, "evidnece": {"observed": True}}]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason
    assert "evidnece" in excinfo.value.reason


def test_rejects_duplicate_forbidden_fact(tmp_path):
    data = _mutated(forbidden={"relations": [_FORBIDDEN_FACT, dict(_FORBIDDEN_FACT)]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "duplicate forbidden fact" in excinfo.value.reason


def test_rejects_a_forbidden_identity_duplicated_in_expected(tmp_path):
    contradiction = {
        "type": _VALID["expected"]["relations"][0]["type"],
        "source": _VALID["expected"]["relations"][0]["source"],
        "target": _VALID["expected"]["relations"][0]["target"],
    }
    data = _mutated(forbidden={"relations": [contradiction]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "also asserted as expected" in excinfo.value.reason


# --- I3: reconciliation input convention ------------------------------------------------------


def test_rejects_an_empty_reconciliation_declarations_directory(tmp_path):
    """I3 spec §10.3: an existing-but-empty reconciliation directory must be rejected as an
    invalid fixture, not silently treated as no reconciliation phase at all."""
    scenario_dir = _write_scenario(tmp_path, _VALID)
    (scenario_dir / "input" / "reconciliation" / "declarations").mkdir(parents=True)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "input.reconciliation.declarations" in excinfo.value.field
    assert "no importable declaration sources" in excinfo.value.reason


def test_a_scenario_with_a_populated_reconciliation_directory_loads_normally(tmp_path):
    """The Scenario model itself is unchanged by I3 (spec §6.2) - a reconciliation phase is a
    runner-level input-directory convention, not a new loaded field."""
    scenario_dir = _write_scenario(tmp_path, _VALID)
    reconciliation_dir = (
        scenario_dir / "input" / "reconciliation" / "declarations" / "order-service"
    )
    reconciliation_dir.mkdir(parents=True)
    (reconciliation_dir / "architecture.yaml").write_text("service: order-service\ncalls: []\n")

    scenario = load_scenario(scenario_dir)

    assert scenario.id == "rest-confirmed"


def test_rejects_a_reconciliation_service_directory_with_no_recognized_file(tmp_path):
    """I4 spec §9.4: a subdirectory can exist under input/reconciliation/declarations/ while
    containing zero files app.ingestion.scanner.scan_directory would recognize - that must not
    silently no-op the reconciliation phase."""
    scenario_dir = _write_scenario(tmp_path, _VALID)
    service_dir = scenario_dir / "input" / "reconciliation" / "declarations" / "order-service"
    service_dir.mkdir(parents=True)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "input.reconciliation.declarations" in excinfo.value.field
    assert "no importable declaration sources" in excinfo.value.reason


def test_rejects_a_reconciliation_directory_with_only_a_placeholder_file(tmp_path):
    """I4 spec §9.4: a file with an unrecognized name (not openapi/asyncapi/architecture.yaml)
    must not be mistaken for a real declaration source."""
    scenario_dir = _write_scenario(tmp_path, _VALID)
    service_dir = scenario_dir / "input" / "reconciliation" / "declarations" / "order-service"
    service_dir.mkdir(parents=True)
    (service_dir / "notes.txt").write_text("not a real declaration")

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "no importable declaration sources" in excinfo.value.reason


# --- I4: strict scenario-schema validation (spec §8) --------------------------------------------


def test_rejects_an_unknown_top_level_field(tmp_path):
    data = _mutated(bogus="oops")
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason
    assert "bogus" in excinfo.value.reason


def test_rejects_an_unknown_scope_field(tmp_path):
    data = _mutated(**{"scope.bogus": "oops"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason


def test_rejects_empty_scope_entities(tmp_path):
    data = _mutated(**{"scope.entities": []})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "must not be empty" in excinfo.value.reason


def test_rejects_duplicate_scope_entities(tmp_path):
    data = _mutated(**{"scope.entities": ["service:order-service", "service:order-service"]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "duplicate" in excinfo.value.reason


def test_rejects_an_explicitly_empty_scope_relation_types(tmp_path):
    """Closes a latent bug: relation_types: [] previously fell through to "all types" via a
    truthiness check instead of being rejected as an explicitly-empty-but-present list."""
    data = _mutated(**{"scope.relation_types": []})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "must not be empty" in excinfo.value.reason


def test_rejects_duplicate_scope_relation_types(tmp_path):
    data = _mutated(**{"scope.relation_types": ["CALLS", "CALLS"]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "duplicate" in excinfo.value.reason


def test_rejects_an_unknown_observation_field(tmp_path):
    data = _mutated(**{"observation.bogus": "oops"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason


def test_rejects_an_unknown_observation_window_field(tmp_path):
    data = _mutated(**{"observation.window.bogus": "oops"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason


def test_rejects_a_naive_window_timestamp(tmp_path):
    data = _mutated(**{"observation.window.start": "2026-08-01T10:00:00"})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "timezone-aware" in excinfo.value.reason


def test_runtime_scenario_requires_window_start(tmp_path):
    data = _mutated(**{"observation.window.start": _DELETE})
    scenario_dir = _write_scenario(tmp_path, data)
    telemetry_dir = scenario_dir / "input" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    (telemetry_dir / "spans.py").write_text("")

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "observation.window.start"


def test_runtime_scenario_requires_window_end(tmp_path):
    data = _mutated(**{"observation.window.end": _DELETE})
    scenario_dir = _write_scenario(tmp_path, data)
    telemetry_dir = scenario_dir / "input" / "telemetry"
    telemetry_dir.mkdir(parents=True)
    (telemetry_dir / "spans.py").write_text("")

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert excinfo.value.field == "observation.window.end"


def test_rejects_a_window_where_start_is_not_before_end(tmp_path):
    data = _mutated(
        **{
            "observation.window.start": "2026-08-01T11:00:00Z",
            "observation.window.end": "2026-08-01T10:00:00Z",
        }
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "start must be before end" in excinfo.value.reason


def test_rejects_an_unknown_expected_relation_field(tmp_path):
    data = _mutated(
        **{"expected.relations": [{**_VALID["expected"]["relations"][0], "bogus": "oops"}]}
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason


def test_rejects_an_unknown_status_value(tmp_path):
    data = _mutated(
        **{"expected.relations": [{**_VALID["expected"]["relations"][0], "status": "BOGUS"}]}
    )
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown status" in excinfo.value.reason


def test_rejects_an_unknown_evidence_field_on_an_expected_relation(tmp_path):
    fact = {**_VALID["expected"]["relations"][0], "evidence": {"delcared": True}}
    data = _mutated(**{"expected.relations": [fact]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "unknown field" in excinfo.value.reason


def test_rejects_a_string_evidence_value(tmp_path):
    fact = {
        **_VALID["expected"]["relations"][0],
        "evidence": {"declared": "true", "observed": True},
    }
    data = _mutated(**{"expected.relations": [fact]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "must be a boolean" in excinfo.value.reason


def test_rejects_an_integer_evidence_value(tmp_path):
    fact = {**_VALID["expected"]["relations"][0], "evidence": {"declared": True, "observed": 1}}
    data = _mutated(**{"expected.relations": [fact]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "must be a boolean" in excinfo.value.reason


def test_rejects_an_expected_relation_excluded_by_its_own_scope(tmp_path):
    fact = {
        "type": "CALLS",
        "source": "service:totally-unrelated",
        "target": "operation:service:totally-unrelated:GET:/x",
    }
    data = _mutated(**{"expected.relations": [fact]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "excluded by scenario scope" in excinfo.value.reason


def test_rejects_a_forbidden_relation_excluded_by_its_own_scope(tmp_path):
    forbidden = {
        "type": "CALLS",
        "source": "service:totally-unrelated",
        "target": "operation:service:totally-unrelated:GET:/x",
    }
    data = _mutated(forbidden={"relations": [forbidden]})
    scenario_dir = _write_scenario(tmp_path, data)

    with pytest.raises(ScenarioValidationError) as excinfo:
        load_scenario(scenario_dir)
    assert "excluded by scenario scope" in excinfo.value.reason
