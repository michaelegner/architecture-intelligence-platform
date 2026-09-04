"""Regenerate the frozen v0.4 ArchitectureAnswer JSON Schemas.

    uv run python -m app.architecture_intelligence.schema_export

Run manually after a deliberate, recorded contract change. The committed schema files are treated as
frozen: tests/unit/test_architecture_intelligence_schema_frozen.py fails if either drifts from what
this module generates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.architecture_intelligence.contracts import (
    ArchitectureAnswer,
    EvidenceData,
    ServiceDependenciesData,
)

_SCHEMA_DIR = (
    Path(__file__).resolve().parent.parent.parent / "schemas" / "architecture_intelligence" / "v0.4"
)
DEPENDENCIES_SCHEMA_PATH = _SCHEMA_DIR / "architecture-answer.schema.json"
EVIDENCE_SCHEMA_PATH = _SCHEMA_DIR / "evidence-answer.schema.json"


def generate_dependencies_schema() -> dict[str, Any]:
    return ArchitectureAnswer[ServiceDependenciesData].model_json_schema()


def generate_evidence_schema() -> dict[str, Any]:
    return ArchitectureAnswer[EvidenceData].model_json_schema()


def render_dependencies_schema() -> str:
    return json.dumps(generate_dependencies_schema(), indent=2, sort_keys=True) + "\n"


def render_evidence_schema() -> str:
    return json.dumps(generate_evidence_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    DEPENDENCIES_SCHEMA_PATH.write_text(render_dependencies_schema())
    EVIDENCE_SCHEMA_PATH.write_text(render_evidence_schema())


if __name__ == "__main__":
    main()
