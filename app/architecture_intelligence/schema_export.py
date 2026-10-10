"""Regenerate the frozen v0.5 ArchitectureAnswer JSON Schemas (all three since v0.4.0 I3.1) and the
v0.6 locality request/answer schemas (v0.6.0 I3.1b, I3 decision record D2), plus the v0.6
Broker-aware dependency/evidence answer schemas (v0.6.1 I2a, spec §5.2).

    uv run python -m app.architecture_intelligence.schema_export

Run manually after a deliberate, recorded contract change. The committed schema files are treated as
frozen: tests/unit/test_architecture_intelligence_schema_frozen.py fails if either drifts from what
this module generates (tests/unit/test_locality_contracts_schema_frozen.py for the v0.6 pair).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.architecture_intelligence.broker_contracts import (
    ArchitectureAnswerV06,
    EvidenceDataV06,
    ServiceDependenciesDataV06,
)
from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    ArchitectureDriftData,
    EvidenceData,
    ServiceDependenciesData,
)
from app.architecture_intelligence.locality_contracts import (
    LocalityAnswer,
    ServiceDependenciesByLocalityRequest,
)

_SCHEMA_DIR = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "architecture_intelligence" / "v0.5"
)
DEPENDENCIES_SCHEMA_PATH = _SCHEMA_DIR / "architecture-answer.schema.json"
EVIDENCE_SCHEMA_PATH = _SCHEMA_DIR / "evidence-answer.schema.json"
DRIFT_SCHEMA_PATH = _SCHEMA_DIR / "drift-answer.schema.json"

_LOCALITY_SCHEMA_DIR = _SCHEMA_DIR.parent / "v0.6"
LOCALITY_REQUEST_SCHEMA_PATH = (
    _LOCALITY_SCHEMA_DIR / "service-dependencies-by-locality-request.schema.json"
)
LOCALITY_ANSWER_SCHEMA_PATH = (
    _LOCALITY_SCHEMA_DIR / "service-dependencies-by-locality-answer.schema.json"
)
# v0.6.1 I2a: the Broker-aware pair lives beside the locality pair; the v0.5 files are immutable.
BROKER_DEPENDENCIES_SCHEMA_PATH = _LOCALITY_SCHEMA_DIR / "architecture-answer.schema.json"
BROKER_EVIDENCE_SCHEMA_PATH = _LOCALITY_SCHEMA_DIR / "evidence-answer.schema.json"


def generate_dependencies_schema() -> dict[str, Any]:
    return ArchitectureAnswer[ServiceDependenciesData].model_json_schema()


def generate_evidence_schema() -> dict[str, Any]:
    return ArchitectureAnswer[EvidenceData].model_json_schema()


def generate_drift_schema() -> dict[str, Any]:
    return ArchitectureAnswer[ArchitectureDriftData].model_json_schema()


def generate_broker_dependencies_schema() -> dict[str, Any]:
    return ArchitectureAnswerV06[ServiceDependenciesDataV06].model_json_schema()


def generate_broker_evidence_schema() -> dict[str, Any]:
    return ArchitectureAnswerV06[EvidenceDataV06].model_json_schema()


def generate_locality_request_schema() -> dict[str, Any]:
    return ServiceDependenciesByLocalityRequest.model_json_schema()


def generate_locality_answer_schema() -> dict[str, Any]:
    return LocalityAnswer.model_json_schema()


def _render(schema: dict[str, Any]) -> str:
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def render_dependencies_schema() -> str:
    return _render(generate_dependencies_schema())


def render_evidence_schema() -> str:
    return _render(generate_evidence_schema())


def render_drift_schema() -> str:
    return _render(generate_drift_schema())


def render_broker_dependencies_schema() -> str:
    return _render(generate_broker_dependencies_schema())


def render_broker_evidence_schema() -> str:
    return _render(generate_broker_evidence_schema())


def render_locality_request_schema() -> str:
    return _render(generate_locality_request_schema())


def render_locality_answer_schema() -> str:
    return _render(generate_locality_answer_schema())


def main() -> None:
    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    DEPENDENCIES_SCHEMA_PATH.write_text(render_dependencies_schema())
    EVIDENCE_SCHEMA_PATH.write_text(render_evidence_schema())
    DRIFT_SCHEMA_PATH.write_text(render_drift_schema())
    _LOCALITY_SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    LOCALITY_REQUEST_SCHEMA_PATH.write_text(render_locality_request_schema())
    LOCALITY_ANSWER_SCHEMA_PATH.write_text(render_locality_answer_schema())
    BROKER_DEPENDENCIES_SCHEMA_PATH.write_text(render_broker_dependencies_schema())
    BROKER_EVIDENCE_SCHEMA_PATH.write_text(render_broker_evidence_schema())


if __name__ == "__main__":
    main()
