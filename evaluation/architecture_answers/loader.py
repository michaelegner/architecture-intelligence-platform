"""Discovers and validates architecture-answers scenarios.

Ground truth is frozen ahead of time in each scenario's `expected_answer.json` - a literal
`ArchitectureAnswer`, never computed from a live run (I1.4 review finding #1, restated as I3 spec
§28's explicit prohibition on generating a drift/evidence expected answer by running another tool
and filtering/reusing its output). `request.yaml` is the small, hand-authored input side; its own
schema is validated here with the same strictness as `evaluation.loader` applies to `expected.yaml`.

I3.3 (spec §29/§31) generalizes this to all three tools via an explicit `request.tool` key,
defaulting to `get_service_dependencies` so every existing I1 `request.yaml` file keeps parsing -
and keeps meaning - unchanged.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    EvidenceData,
    ServiceDependenciesData,
)
from evaluation.architecture_answers.model import (
    TOOL_ARCHITECTURE_DRIFT,
    TOOL_EVIDENCE,
    TOOL_NAMES,
    TOOL_SERVICE_DEPENDENCIES,
    ExpectedAnswer,
    Request,
    Scenario,
    ScenarioValidationError,
)

REQUEST_FILENAME = "request.yaml"
EXPECTED_ANSWER_FILENAME = "expected_answer.json"

_TOP_LEVEL_ALLOWED_KEYS = {"scenario", "description", "request"}
_DEPENDENCY_SHAPED_REQUEST_ALLOWED_KEYS = {"tool", "service_id", "observation", "snapshot_id"}
_EVIDENCE_REQUEST_ALLOWED_KEYS = {"tool", "evidence_refs", "snapshot_id"}
_OBSERVATION_ALLOWED_KEYS = {"environment", "window"}
_WINDOW_ALLOWED_KEYS = {"start", "end"}

# I3 spec §31's dispatch table: which real ArchitectureAnswer specialization a scenario's
# `expected_answer.json` validates against, keyed by the same `request.tool` name that picks the
# runner's own request type/service method (evaluation.architecture_answers.runner._DISPATCH).
_ANSWER_TYPE_BY_TOOL: dict[str, type] = {
    TOOL_SERVICE_DEPENDENCIES: ArchitectureAnswer[ServiceDependenciesData],
    TOOL_ARCHITECTURE_DRIFT: ArchitectureAnswer[ArchitectureDriftData],
    TOOL_EVIDENCE: ArchitectureAnswer[EvidenceData],
}


def discover_scenarios(scenarios_dir: Path) -> list[Path]:
    """Scenario directories directly under scenarios_dir, sorted by name for deterministic order."""
    return sorted(
        p for p in scenarios_dir.iterdir() if p.is_dir() and (p / REQUEST_FILENAME).is_file()
    )


def _error(scenario_id: str, file: Path, field: str, reason: str) -> ScenarioValidationError:
    return ScenarioValidationError(scenario=scenario_id, file=str(file), field=field, reason=reason)


def _reject_unknown_keys(
    data: dict, allowed: set[str], *, scenario_id: str, file: Path, field: str
) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise _error(scenario_id, file, field, f"unknown field(s): {', '.join(sorted(unknown))}")


def _require(data: dict, key: str, *, scenario_id: str, file: Path, prefix: str = "") -> Any:
    if not isinstance(data, dict) or key not in data or data[key] is None:
        raise _error(scenario_id, file, f"{prefix}{key}", "missing required field")
    return data[key]


def _require_mapping(value: Any, *, scenario_id: str, file: Path, field: str) -> dict:
    if not isinstance(value, dict):
        raise _error(scenario_id, file, field, f"expected a mapping, got {value!r}")
    return value


def _optional_mapping(value: Any, *, scenario_id: str, file: Path, field: str) -> dict:
    if value is None:
        return {}
    return _require_mapping(value, scenario_id=scenario_id, file=file, field=field)


def _require_string(value: Any, *, scenario_id: str, file: Path, field: str) -> str:
    if not isinstance(value, str):
        raise _error(scenario_id, file, field, f"expected a string, got {value!r}")
    return value


def _optional_string(value: Any, *, scenario_id: str, file: Path, field: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, scenario_id=scenario_id, file=file, field=field)


def _require_string_list(
    value: Any, *, scenario_id: str, file: Path, field: str
) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise _error(
            scenario_id, file, field, f"expected a non-empty list of strings, got {value!r}"
        )
    if len(value) > 20:
        raise _error(scenario_id, file, field, f"at most 20 evidence refs, got {len(value)}")
    if len(set(value)) != len(value):
        raise _error(scenario_id, file, field, "evidence_refs must not contain duplicates")
    return tuple(value)


def _parse_timestamp(value: Any, *, scenario_id: str, file: Path, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error(scenario_id, file, field, f"invalid timestamp: {value!r}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _error(scenario_id, file, field, f"invalid timestamp: {value!r} ({exc})") from exc
    if parsed.tzinfo is None:
        raise _error(scenario_id, file, field, f"timestamp must be timezone-aware: {value!r}")
    return parsed


def _load_dependency_shaped_request(
    request_raw: dict, *, tool: str, scenario_id: str, file: Path
) -> Request:
    _reject_unknown_keys(
        request_raw,
        _DEPENDENCY_SHAPED_REQUEST_ALLOWED_KEYS,
        scenario_id=scenario_id,
        file=file,
        field="request",
    )
    service_id = _require(
        request_raw, "service_id", scenario_id=scenario_id, file=file, prefix="request."
    )
    if not isinstance(service_id, str) or not service_id.startswith("service:"):
        raise _error(
            scenario_id, file, "request.service_id", f"malformed service id: {service_id!r}"
        )

    observation_raw = _optional_mapping(
        request_raw.get("observation"),
        scenario_id=scenario_id,
        file=file,
        field="request.observation",
    )
    _reject_unknown_keys(
        observation_raw,
        _OBSERVATION_ALLOWED_KEYS,
        scenario_id=scenario_id,
        file=file,
        field="request.observation",
    )
    window_raw = _optional_mapping(
        observation_raw.get("window"),
        scenario_id=scenario_id,
        file=file,
        field="request.observation.window",
    )
    _reject_unknown_keys(
        window_raw,
        _WINDOW_ALLOWED_KEYS,
        scenario_id=scenario_id,
        file=file,
        field="request.observation.window",
    )

    environment = _optional_string(
        observation_raw.get("environment"),
        scenario_id=scenario_id,
        file=file,
        field="request.observation.environment",
    )
    snapshot_id = _optional_string(
        request_raw.get("snapshot_id"),
        scenario_id=scenario_id,
        file=file,
        field="request.snapshot_id",
    )

    return Request(
        tool=tool,
        service_id=service_id,
        environment=environment,
        window_start=_parse_timestamp(
            window_raw.get("start"),
            scenario_id=scenario_id,
            file=file,
            field="request.observation.window.start",
        ),
        window_end=_parse_timestamp(
            window_raw.get("end"),
            scenario_id=scenario_id,
            file=file,
            field="request.observation.window.end",
        ),
        snapshot_id=snapshot_id,
    )


def _load_evidence_request(request_raw: dict, *, scenario_id: str, file: Path) -> Request:
    _reject_unknown_keys(
        request_raw,
        _EVIDENCE_REQUEST_ALLOWED_KEYS,
        scenario_id=scenario_id,
        file=file,
        field="request",
    )
    evidence_refs = _require_string_list(
        _require(
            request_raw, "evidence_refs", scenario_id=scenario_id, file=file, prefix="request."
        ),
        scenario_id=scenario_id,
        file=file,
        field="request.evidence_refs",
    )
    # get_evidence never defaults to the current snapshot (spec §11.1) - required here too, unlike
    # the dependency-shaped tools' optional snapshot_id.
    snapshot_id = _require_string(
        _require(request_raw, "snapshot_id", scenario_id=scenario_id, file=file, prefix="request."),
        scenario_id=scenario_id,
        file=file,
        field="request.snapshot_id",
    )
    return Request(tool=TOOL_EVIDENCE, evidence_refs=evidence_refs, snapshot_id=snapshot_id)


def _load_request(raw: dict, *, scenario_id: str, file: Path) -> Request:
    request_raw = _require_mapping(
        _require(raw, "request", scenario_id=scenario_id, file=file),
        scenario_id=scenario_id,
        file=file,
        field="request",
    )
    tool = _optional_string(
        request_raw.get("tool"), scenario_id=scenario_id, file=file, field="request.tool"
    )
    if tool is None:
        tool = TOOL_SERVICE_DEPENDENCIES
    elif tool not in TOOL_NAMES:
        raise _error(
            scenario_id,
            file,
            "request.tool",
            f"must be one of {sorted(TOOL_NAMES)}, got {tool!r}",
        )

    if tool == TOOL_EVIDENCE:
        return _load_evidence_request(request_raw, scenario_id=scenario_id, file=file)
    return _load_dependency_shaped_request(
        request_raw, tool=tool, scenario_id=scenario_id, file=file
    )


def _load_expected_answer(path: Path, *, scenario_id: str, tool: str) -> ExpectedAnswer:
    answer_type = _ANSWER_TYPE_BY_TOOL[tool]
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise _error(scenario_id, path, "<root>", f"could not read/parse: {exc}") from exc
    try:
        return answer_type.model_validate(payload)
    except ValidationError as exc:
        raise _error(
            scenario_id, path, "<root>", f"does not conform to ArchitectureAnswer: {exc}"
        ) from exc


def load_scenario(path: Path) -> Scenario:
    file = path / REQUEST_FILENAME
    raw = yaml.safe_load(file.read_text())
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _error(path.name, file, "<root>", f"expected a mapping, got {raw!r}")

    scenario_id = raw.get("scenario")
    if not scenario_id or not isinstance(scenario_id, str):
        raise _error(path.name, file, "scenario", "missing scenario id")

    _reject_unknown_keys(
        raw, _TOP_LEVEL_ALLOWED_KEYS, scenario_id=scenario_id, file=file, field="<root>"
    )
    description = _require_string(
        _require(raw, "description", scenario_id=scenario_id, file=file),
        scenario_id=scenario_id,
        file=file,
        field="description",
    )
    request = _load_request(raw, scenario_id=scenario_id, file=file)

    expected_answer_path = path / EXPECTED_ANSWER_FILENAME
    if not expected_answer_path.is_file():
        raise _error(scenario_id, expected_answer_path, "<root>", "expected_answer.json is missing")
    expected = _load_expected_answer(
        expected_answer_path, scenario_id=scenario_id, tool=request.tool
    )

    return Scenario(
        id=scenario_id, description=description, request=request, expected=expected, path=path
    )


def load_scenarios(scenarios_dir: Path) -> list[Scenario]:
    return [load_scenario(p) for p in discover_scenarios(scenarios_dir)]
