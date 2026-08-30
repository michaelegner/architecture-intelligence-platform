"""Discovers and validates evaluation scenarios (I1 §7).

Ground truth is authored by hand in each scenario's expected.yaml and validated *before* AIP ever
runs (I1 §7.3) - a malformed scenario is a configuration error, never a scenario failure.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from evaluation.model import (
    KNOWN_RELATION_TYPES,
    Observation,
    RelationFact,
    Scenario,
    ScenarioScope,
    ScenarioValidationError,
    is_canonical_id,
)

EXPECTED_FILENAME = "expected.yaml"


def discover_scenarios(scenarios_dir: Path) -> list[Path]:
    """Scenario directories directly under scenarios_dir, sorted by name for deterministic order."""
    return sorted(
        p for p in scenarios_dir.iterdir() if p.is_dir() and (p / EXPECTED_FILENAME).is_file()
    )


def _error(scenario_id: str, file: Path, field: str, reason: str) -> ScenarioValidationError:
    return ScenarioValidationError(scenario=scenario_id, file=str(file), field=field, reason=reason)


def _require(data: dict, key: str, *, scenario_id: str, file: Path, prefix: str = "") -> Any:
    if not isinstance(data, dict) or key not in data or data[key] is None:
        raise _error(scenario_id, file, f"{prefix}{key}", "missing required field")
    return data[key]


def _validate_entity_id(value: Any, *, scenario_id: str, file: Path, field: str) -> str:
    if not is_canonical_id(value):
        raise _error(scenario_id, file, field, f"malformed canonical identifier: {value!r}")
    return value


def _validate_relation_type(value: Any, *, scenario_id: str, file: Path, field: str) -> str:
    if value not in KNOWN_RELATION_TYPES:
        raise _error(scenario_id, file, field, f"unknown relation type: {value!r}")
    return value


def _parse_relation_fact(raw: Any, *, scenario_id: str, file: Path, field: str) -> RelationFact:
    if not isinstance(raw, dict):
        raise _error(scenario_id, file, field, f"expected a mapping, got {raw!r}")
    relation_type = _validate_relation_type(
        _require(raw, "type", scenario_id=scenario_id, file=file, prefix=f"{field}."),
        scenario_id=scenario_id,
        file=file,
        field=f"{field}.type",
    )
    source = _validate_entity_id(
        _require(raw, "source", scenario_id=scenario_id, file=file, prefix=f"{field}."),
        scenario_id=scenario_id,
        file=file,
        field=f"{field}.source",
    )
    target = _validate_entity_id(
        _require(raw, "target", scenario_id=scenario_id, file=file, prefix=f"{field}."),
        scenario_id=scenario_id,
        file=file,
        field=f"{field}.target",
    )
    evidence = raw.get("evidence") or {}
    return RelationFact(
        type=relation_type,
        source=source,
        target=target,
        status=raw.get("status"),
        declared_evidence=evidence.get("declared"),
        observed_evidence=evidence.get("observed"),
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _has_telemetry_input(path: Path) -> bool:
    telemetry_dir = path / "input" / "telemetry"
    return telemetry_dir.is_dir() and any(telemetry_dir.iterdir())


def load_scenario(path: Path) -> Scenario:
    """Loads and validates one scenario directory's expected.yaml into a Scenario."""
    file = path / EXPECTED_FILENAME
    raw = yaml.safe_load(file.read_text()) or {}

    scenario_id = raw.get("scenario")
    if not scenario_id or not isinstance(scenario_id, str):
        raise _error(path.name, file, "scenario", "missing scenario id")

    description = _require(raw, "description", scenario_id=scenario_id, file=file)

    scope_raw = _require(raw, "scope", scenario_id=scenario_id, file=file)
    entities_raw = _require(
        scope_raw, "entities", scenario_id=scenario_id, file=file, prefix="scope."
    )
    entities = tuple(
        _validate_entity_id(e, scenario_id=scenario_id, file=file, field="scope.entities")
        for e in entities_raw
    )
    relation_types_raw = scope_raw.get("relation_types")
    relation_types = (
        tuple(
            _validate_relation_type(
                rt, scenario_id=scenario_id, file=file, field="scope.relation_types"
            )
            for rt in relation_types_raw
        )
        if relation_types_raw
        else None
    )
    scope = ScenarioScope(entities=entities, relation_types=relation_types)

    observation_raw = raw.get("observation") or {}
    window_raw = observation_raw.get("window") or {}
    observation = Observation(
        environment=observation_raw.get("environment"),
        window_start=_parse_timestamp(window_raw.get("start")),
        window_end=_parse_timestamp(window_raw.get("end")),
    )
    if _has_telemetry_input(path) and not observation.environment:
        raise _error(
            scenario_id, file, "observation.environment", "required for a runtime scenario"
        )

    expected_raw = _require(raw, "expected", scenario_id=scenario_id, file=file)
    relations_raw = _require(
        expected_raw, "relations", scenario_id=scenario_id, file=file, prefix="expected."
    )
    expected_relations = tuple(
        _parse_relation_fact(r, scenario_id=scenario_id, file=file, field="expected.relations")
        for r in relations_raw
    )
    seen: set[tuple[str, str, str]] = set()
    for fact in expected_relations:
        key = (fact.type, fact.source, fact.target)
        if key in seen:
            raise _error(scenario_id, file, "expected.relations", f"duplicate expected fact: {key}")
        seen.add(key)

    forbidden_raw = _require(raw, "forbidden", scenario_id=scenario_id, file=file)
    forbidden_relations = _require(
        forbidden_raw, "relations", scenario_id=scenario_id, file=file, prefix="forbidden."
    )
    if forbidden_relations:
        # I1 §7.2: the final scenario-file shape is used, but evaluating non-empty forbidden
        # assertions is deferred to I2 - reject rather than silently ignore.
        raise _error(
            scenario_id,
            file,
            "forbidden.relations",
            "non-empty forbidden.relations is not supported in I1 (deferred to I2)",
        )

    return Scenario(
        id=scenario_id,
        description=description,
        scope=scope,
        observation=observation,
        expected_relations=expected_relations,
        path=path,
    )


def load_scenarios(scenarios_dir: Path) -> list[Scenario]:
    return [load_scenario(p) for p in discover_scenarios(scenarios_dir)]
