"""Regenerate the frozen v0.5 import report JSON Schemas (v0.5.0 I5 finding F2).

    uv run python -m app.ingestion.import_report_schema

Run manually after a deliberate, recorded contract change. The committed schema files are treated
as frozen: tests/unit/test_import_report_schema_frozen.py fails if either drifts from what this
module generates (I1 spec §12: a public payload change needs an explicit versioned schema update).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ingestion.import_report import ImportReport, ServiceImportReport

_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas" / "import" / "v0.5"
IMPORT_REPORT_SCHEMA_PATH = _SCHEMA_DIR / "import-report.schema.json"
SERVICE_IMPORT_REPORT_SCHEMA_PATH = _SCHEMA_DIR / "service-import-report.schema.json"


def generate_import_report_schema() -> dict[str, Any]:
    return ImportReport.model_json_schema()


def generate_service_import_report_schema() -> dict[str, Any]:
    return ServiceImportReport.model_json_schema()


def render_import_report_schema() -> str:
    return json.dumps(generate_import_report_schema(), indent=2, sort_keys=True) + "\n"


def render_service_import_report_schema() -> str:
    return json.dumps(generate_service_import_report_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_REPORT_SCHEMA_PATH.write_text(render_import_report_schema())
    SERVICE_IMPORT_REPORT_SCHEMA_PATH.write_text(render_service_import_report_schema())


if __name__ == "__main__":
    main()
