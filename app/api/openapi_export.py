"""Regenerate the committed REST API OpenAPI snapshot. Run from the repository root (importing
`app.main` reads `config.yaml` relative to the working directory, or `CONFIG_PATH`):

    uv run python -m app.api.openapi_export

Run it after a deliberate REST API change and commit the result alongside it:
tests/unit/test_openapi_snapshot.py fails whenever the generated OpenAPI document drifts from the
snapshot, so every REST surface change shows up as an explicit, reviewed diff. The snapshot is a
change detector, not a published contract or a stability promise - see ROADMAP.md for what's
stable pre-1.0.

`info.version` is required by OpenAPI, so it's kept but normalized to `SNAPSHOT_VERSION`: the real
value is the package version (checked by test_main_health.py), and keeping it would make every
release bump rewrite the snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.main import create_app

OPENAPI_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "snapshots" / "openapi.json"
)
SNAPSHOT_VERSION = "snapshot"


def generate_openapi() -> dict[str, Any]:
    document = create_app().openapi()
    document["info"]["version"] = SNAPSHOT_VERSION
    return document


def render_openapi() -> str:
    return json.dumps(generate_openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OPENAPI_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_SNAPSHOT_PATH.write_text(render_openapi())


if __name__ == "__main__":
    main()
