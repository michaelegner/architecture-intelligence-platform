"""Regenerate the frozen v0.4 ArchitectureAnswer JSON Schema.

    uv run python -m app.architecture_intelligence.schema_export

Run manually after a deliberate, recorded contract change. The committed schema file is treated as
frozen: tests/unit/test_architecture_intelligence_schema_frozen.py fails if it drifts from what this
module generates.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.architecture_intelligence.contracts import ArchitectureAnswer, ServiceDependenciesData

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "schemas"
    / "architecture_intelligence"
    / "v0.4"
    / "architecture-answer.schema.json"
)


def generate_schema() -> dict[str, Any]:
    return ArchitectureAnswer[ServiceDependenciesData].model_json_schema()


def render_schema() -> str:
    return json.dumps(generate_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCHEMA_PATH.write_text(render_schema())


if __name__ == "__main__":
    main()
