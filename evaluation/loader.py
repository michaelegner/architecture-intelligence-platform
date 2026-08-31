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


def _require_mapping(value: Any, *, scenario_id: str, file: Path, field: str) -> dict:
    if not isinstance(value, dict):
        raise _error(scenario_id, file, field, f"expected a mapping, got {value!r}")
    return value


def _require_list(value: Any, *, scenario_id: str, file: Path, field: str) -> list:
    if not isinstance(value, list):
        raise _error(scenario_id, file, field, f"expected a list, got {value!r}")
    return value


def _optional_mapping(value: Any, *, scenario_id: str, file: Path, field: str) -> dict:
    """Like _require_mapping, but None/absent is allowed and normalized to {} - for optional
    nested blocks (observation, observation.window, a relation's evidence)."""
    if value is None:
        return {}
    return _require_mapping(value, scenario_id=scenario_id, file=file, field=field)


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
    evidence = _optional_mapping(
        raw.get("evidence"), scenario_id=scenario_id, file=file, field=f"{field}.evidence"
    )
    return RelationFact(
        type=relation_type,
        source=source,
        target=target,
        status=raw.get("status"),
        declared_evidence=evidence.get("declared"),
        observed_evidence=evidence.get("observed"),
    )


_FORBIDDEN_ALLOWED_KEYS = {"type", "source", "target"}


def _parse_forbidden_fact(raw: Any, *, scenario_id: str, file: Path, field: str) -> RelationFact:
    """A forbidden entry asserts only that a canonical identity must not exist (I2 spec §4.2) -
    status/evidence (or any other field, including a typo of one) are not part of its schema, so
    their presence is rejected rather than silently ignored (no conditional forbidding, no
    rules-DSL creep, and no typo silently producing an unconditional identity assertion the
    scenario author didn't intend)."""
    if not isinstance(raw, dict):
        raise _error(scenario_id, file, field, f"expected a mapping, got {raw!r}")
    unknown = set(raw) - _FORBIDDEN_ALLOWED_KEYS
    if unknown:
        raise _error(scenario_id, file, field, f"unknown field(s): {', '.join(sorted(unknown))}")
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
    return RelationFact(type=relation_type, source=source, target=target)


def _parse_timestamp(value: Any, *, scenario_id: str, file: Path, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(scenario_id, file, field, f"invalid timestamp: {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise _error(scenario_id, file, field, f"invalid timestamp: {value!r} ({exc})") from exc


def _has_telemetry_input(path: Path) -> bool:
    telemetry_dir = path / "input" / "telemetry"
    return telemetry_dir.is_dir() and any(telemetry_dir.iterdir())


def _reconciliation_declarations_dir(path: Path) -> Path:
    return path / "input" / "reconciliation" / "declarations"


def load_scenario(path: Path) -> Scenario:
    """Loads and validates one scenario directory's expected.yaml into a Scenario."""
    file = path / EXPECTED_FILENAME
    raw = yaml.safe_load(file.read_text())
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _error(path.name, file, "<root>", f"expected a mapping, got {raw!r}")

    scenario_id = raw.get("scenario")
    if not scenario_id or not isinstance(scenario_id, str):
        raise _error(path.name, file, "scenario", "missing scenario id")

    description = _require(raw, "description", scenario_id=scenario_id, file=file)

    scope_raw = _require_mapping(
        _require(raw, "scope", scenario_id=scenario_id, file=file),
        scenario_id=scenario_id,
        file=file,
        field="scope",
    )
    entities_raw = _require_list(
        _require(scope_raw, "entities", scenario_id=scenario_id, file=file, prefix="scope."),
        scenario_id=scenario_id,
        file=file,
        field="scope.entities",
    )
    entities = tuple(
        _validate_entity_id(e, scenario_id=scenario_id, file=file, field="scope.entities")
        for e in entities_raw
    )
    relation_types_raw = scope_raw.get("relation_types")
    if relation_types_raw is not None:
        relation_types_raw = _require_list(
            relation_types_raw, scenario_id=scenario_id, file=file, field="scope.relation_types"
        )
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

    observation_raw = _optional_mapping(
        raw.get("observation"), scenario_id=scenario_id, file=file, field="observation"
    )
    window_raw = _optional_mapping(
        observation_raw.get("window"),
        scenario_id=scenario_id,
        file=file,
        field="observation.window",
    )
    observation = Observation(
        environment=observation_raw.get("environment"),
        window_start=_parse_timestamp(
            window_raw.get("start"),
            scenario_id=scenario_id,
            file=file,
            field="observation.window.start",
        ),
        window_end=_parse_timestamp(
            window_raw.get("end"),
            scenario_id=scenario_id,
            file=file,
            field="observation.window.end",
        ),
    )
    if _has_telemetry_input(path) and not observation.environment:
        raise _error(
            scenario_id, file, "observation.environment", "required for a runtime scenario"
        )

    reconciliation_dir = _reconciliation_declarations_dir(path)
    if reconciliation_dir.is_dir() and not any(reconciliation_dir.iterdir()):
        raise _error(
            scenario_id,
            file,
            "input.reconciliation.declarations",
            "reconciliation directory exists but is empty",
        )

    expected_raw = _require_mapping(
        _require(raw, "expected", scenario_id=scenario_id, file=file),
        scenario_id=scenario_id,
        file=file,
        field="expected",
    )
    relations_raw = _require_list(
        _require(expected_raw, "relations", scenario_id=scenario_id, file=file, prefix="expected."),
        scenario_id=scenario_id,
        file=file,
        field="expected.relations",
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

    forbidden_raw = _require_mapping(
        _require(raw, "forbidden", scenario_id=scenario_id, file=file),
        scenario_id=scenario_id,
        file=file,
        field="forbidden",
    )
    forbidden_relations_raw = _require_list(
        _require(
            forbidden_raw, "relations", scenario_id=scenario_id, file=file, prefix="forbidden."
        ),
        scenario_id=scenario_id,
        file=file,
        field="forbidden.relations",
    )
    forbidden_relations = tuple(
        _parse_forbidden_fact(r, scenario_id=scenario_id, file=file, field="forbidden.relations")
        for r in forbidden_relations_raw
    )
    seen_forbidden: set[tuple[str, str, str]] = set()
    for fact in forbidden_relations:
        key = (fact.type, fact.source, fact.target)
        if key in seen_forbidden:
            raise _error(
                scenario_id, file, "forbidden.relations", f"duplicate forbidden fact: {key}"
            )
        seen_forbidden.add(key)
        if key in seen:
            raise _error(
                scenario_id,
                file,
                "forbidden.relations",
                f"identity also asserted as expected: {key}",
            )

    return Scenario(
        id=scenario_id,
        description=description,
        scope=scope,
        observation=observation,
        expected_relations=expected_relations,
        forbidden_relations=forbidden_relations,
        path=path,
    )


def load_scenarios(scenarios_dir: Path) -> list[Scenario]:
    return [load_scenario(p) for p in discover_scenarios(scenarios_dir)]
