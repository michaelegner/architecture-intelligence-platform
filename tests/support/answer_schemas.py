"""v0.6.1 I2c: version-aware validation of public architecture answers against the frozen schemas.

`get_service_dependencies` and `get_evidence` answers are data-dependent (spec §5.2): a Broker-free
answer is the released v0.5 shape and a Broker-aware answer is the v0.6 shape. A test that touches a
service or evidence id that may carry Broker data validates each answer against the frozen schema
file for *its own* `schema_version` - never by loosening a schema. An unknown version fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMAS = Path(__file__).resolve().parent.parent.parent / "schemas" / "architecture_intelligence"
_FILES = {
    ("dependencies", "0.5"): _SCHEMAS / "v0.5" / "architecture-answer.schema.json",
    ("dependencies", "0.6"): _SCHEMAS / "v0.6" / "architecture-answer.schema.json",
    ("evidence", "0.5"): _SCHEMAS / "v0.5" / "evidence-answer.schema.json",
    ("evidence", "0.6"): _SCHEMAS / "v0.6" / "evidence-answer.schema.json",
}


def _schema(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    version = payload.get("schema_version")
    path = _FILES.get((kind, version))  # type: ignore[arg-type]
    if path is None:
        raise AssertionError(f"no frozen {kind} schema for schema_version {version!r}")
    return json.loads(path.read_text())


def dependencies_schema_for(payload: dict[str, Any]) -> dict[str, Any]:
    return _schema("dependencies", payload)


def evidence_schema_for(payload: dict[str, Any]) -> dict[str, Any]:
    return _schema("evidence", payload)


def validate_dependencies(payload: dict[str, Any]) -> None:
    jsonschema.validate(instance=payload, schema=dependencies_schema_for(payload))


def validate_evidence(payload: dict[str, Any]) -> None:
    jsonschema.validate(instance=payload, schema=evidence_schema_for(payload))
